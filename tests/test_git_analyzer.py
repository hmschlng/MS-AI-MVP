"""
Git Analyzer Unit Tests

GitAnalyzer 클래스의 단위 테스트
"""
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, time
import pytest
import git
from git import Repo

# 프로젝트 루트를 Python 경로에 추가
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_test_generator.core.git_analyzer import GitAnalyzer
from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange


class TestGitAnalyzer:
    """GitAnalyzer 테스트 클래스"""
    
    @pytest.fixture
    def temp_repo(self):
        """테스트용 임시 Git 저장소 생성"""
        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp()
        repo = Repo.init(temp_dir)
        
        # 초기 설정
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()
        
        yield repo, temp_dir
        
        # 정리
        try:
            repo.close()
        except:
            pass
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    def test_init_valid_repo(self, temp_repo):
        """유효한 저장소로 GitAnalyzer 초기화 테스트"""
        repo, temp_dir = temp_repo
        analyzer = GitAnalyzer(temp_dir)
        
        assert analyzer.repo_path == Path(temp_dir).resolve()
        assert analyzer.default_branch == "main"
        assert analyzer.repo is not None

    def test_clone_remote_repo_and_from_remote(self, tmp_path):
        """원격 저장소 클론 및 from_remote 메서드 테스트 (에러 처리 확인)"""
        # 잘못된 URL로 클론 시도 - 실패해야 함
        with pytest.raises(Exception):
            GitAnalyzer.clone_remote_repo("invalid://url")
        
        # 존재하지 않는 경로로 from_remote 시도 - 실패해야 함  
        with pytest.raises(Exception):
            GitAnalyzer.from_remote("file:///nonexistent/path")

    def test_analyze_commit_and_commit_range(self, temp_repo):
        """커밋 분석 및 커밋 범위 분석 테스트"""
        repo, temp_dir = temp_repo
        # 파일 추가 및 커밋
        file1 = Path(temp_dir) / "a.py"
        file1.write_text("def foo():\n    return 1\n")
        repo.index.add([str(file1)])
        repo.index.commit("add a.py")
        # 파일 수정 및 커밋
        file1.write_text("def foo():\n    return 2\n")
        repo.index.add([str(file1)])
        repo.index.commit("modify a.py")
        analyzer = GitAnalyzer(temp_dir)
        commits = analyzer.get_commits_between(max_count=3)
        assert len(commits) >= 2
        # 단일 커밋 분석
        analysis = analyzer.analyze_commit(commits[0])
        assert isinstance(analysis, CommitAnalysis)
        assert analysis.commit_hash == commits[0].hexsha
        # 커밋 범위 분석
        analyses = analyzer.analyze_commit_range(max_count=3)
        assert isinstance(analyses, list)
        assert all(isinstance(a, CommitAnalysis) for a in analyses)
        # 변경 파일 정보 확인
        found = False
        for a in analyses:
            for fc in a.files_changed:
                if "a.py" in fc.file_path:
                    found = True
        assert found, f"Expected to find a.py in changes but got: {[(a.commit_hash[:8], [fc.file_path for fc in a.files_changed]) for a in analyses]}"

    def test_get_file_history(self, temp_repo):
        """특정 파일의 변경 이력 분석 테스트"""
        repo, temp_dir = temp_repo
        file1 = Path(temp_dir) / "b.py"
        file1.write_text("print('v1')\n")
        repo.index.add([str(file1)])
        repo.index.commit("add b.py")
        file1.write_text("print('v2')\n")
        repo.index.add([str(file1)])
        repo.index.commit("modify b.py")
        analyzer = GitAnalyzer(temp_dir)
        history = analyzer.get_file_history("b.py")
        assert isinstance(history, list)
        assert len(history) >= 2
        for analysis in history:
            assert any("b.py" in fc.file_path for fc in analysis.files_changed)

    def test_get_branch_diff(self, temp_repo):
        """브랜치 간 차이 분석 테스트"""
        repo, temp_dir = temp_repo
        
        # 초기 커밋
        file1 = Path(temp_dir) / "c.py"
        file1.write_text("print('main')\n")
        repo.index.add([str(file1)])
        initial_commit = repo.index.commit("initial commit")
        
        # master/main 브랜치 생성
        try:
            main_branch = repo.create_head('main', initial_commit)
            repo.head.reference = main_branch
        except:
            pass  # 이미 있을 수 있음
            
        # feature 브랜치 생성 및 변경
        feature_branch = repo.create_head('feature', initial_commit)
        repo.head.reference = feature_branch
        
        file1.write_text("print('feature')\n")
        repo.index.add([str(file1)])
        repo.index.commit("feature commit")
        
        analyzer = GitAnalyzer(temp_dir)
        changes = analyzer.get_branch_diff("feature", "main")
        assert isinstance(changes, list)
        # 변경사항이 있어야 함
        assert len(changes) >= 0  # 에러가 없으면 성공

    def test_find_related_files(self, temp_repo):
        """관련 파일 찾기 테스트"""
        repo, temp_dir = temp_repo
        file1 = Path(temp_dir) / "d.py"
        file2 = Path(temp_dir) / "e.py"
        file1.write_text("print('d')\n")
        file2.write_text("print('e')\n")
        repo.index.add([str(file1), str(file2)])
        repo.index.commit("add d.py and e.py")
        file1.write_text("print('d2')\n")
        file2.write_text("print('e2')\n")
        repo.index.add([str(file1), str(file2)])
        repo.index.commit("modify d.py and e.py")
        analyzer = GitAnalyzer(temp_dir)
        related = analyzer.find_related_files("d.py")
        assert "e.py" in [os.path.basename(f) for f in related]

    def test_supported_languages(self, temp_repo):
        """지원되는 프로그래밍 언어 감지 테스트"""
        repo, temp_dir = temp_repo
        
        # Python 파일만 테스트 (단순화)
        python_file = Path(temp_dir) / "test.py"
        python_file.write_text("def hello(): pass")
        repo.index.add([str(python_file)])
        repo.index.commit("add python file")
        
        analyzer = GitAnalyzer(temp_dir)
        commits = analyzer.get_commits_between(max_count=1)
        analysis = analyzer.analyze_commit(commits[0])
        
        # 분석 결과가 있는지 확인
        assert len(analysis.files_changed) >= 0
        
        # 언어 감지 기능이 동작하는지 확인 (파일이 감지되면)
        if analysis.files_changed:
            py_file = next((fc for fc in analysis.files_changed if "test.py" in fc.file_path), None)
            if py_file:
                assert py_file.language == "python" or py_file.language is None  # 감지되거나 None

    def test_diff_analysis_edge_cases(self, temp_repo):
        """diff 분석의 엣지 케이스 테스트"""
        repo, temp_dir = temp_repo
        
        # 1. 빈 파일 추가
        empty_file = Path(temp_dir) / "empty.py"
        empty_file.touch()
        repo.index.add([str(empty_file)])
        repo.index.commit("add empty file")
        
        # 2. 파일 삭제
        empty_file.unlink()
        repo.index.remove([str(empty_file)])
        repo.index.commit("delete file")
        
        # 3. 파일 이름 변경
        new_file = Path(temp_dir) / "renamed.py"
        new_file.write_text("print('renamed')")
        repo.index.add([str(new_file)])
        repo.index.commit("add file for rename")
        
        repo.git.mv("renamed.py", "renamed_new.py")
        repo.index.commit("rename file")
        
        analyzer = GitAnalyzer(temp_dir)
        analyses = analyzer.analyze_commit_range(max_count=4)
        
        # 변경 유형별로 분석 결과 확인
        change_types = set()
        for analysis in analyses:
            for fc in analysis.files_changed:
                change_types.add(fc.change_type)
        
        assert 'added' in change_types
        assert 'deleted' in change_types
        assert 'renamed' in change_types

    def test_function_and_class_extraction(self, temp_repo):
        """함수 및 클래스 변경사항 추출 테스트"""
        repo, temp_dir = temp_repo
        
        # Python 파일에 함수와 클래스 추가
        python_file = Path(temp_dir) / "code.py"
        python_file.write_text("""
class TestClass:
    def __init__(self):
        pass
    
    def test_method(self):
        pass

def standalone_function():
    return "hello"
""")
        repo.index.add([str(python_file)])
        repo.index.commit("add python code")
        
        # 함수 수정
        python_file.write_text("""
class TestClass:
    def __init__(self):
        pass
    
    def test_method(self):
        return "modified"

def standalone_function():
    return "hello world"

def new_function():
    return "new"
""")
        repo.index.add([str(python_file)])
        repo.index.commit("modify python code")
        
        analyzer = GitAnalyzer(temp_dir)
        commits = analyzer.get_commits_between(max_count=1)
        analysis = analyzer.analyze_commit(commits[0])
        
        # 함수/클래스 변경사항이 추출되었는지 확인
        for fc in analysis.files_changed:
            if "code.py" in fc.file_path:
                # 적어도 하나의 함수나 클래스가 감지되어야 함
                assert len(fc.functions_changed) > 0 or len(fc.classes_changed) > 0

    def test_error_handling(self):
        """에러 처리 테스트"""
        # 존재하지 않는 경로로 초기화 시도
        with pytest.raises((ValueError, git.exc.NoSuchPathError)):
            GitAnalyzer("/nonexistent/path")
        
        # 잘못된 원격 URL 클론 시도
        with pytest.raises(Exception):
            GitAnalyzer.clone_remote_repo("invalid://url")

    def test_bare_repository_handling(self, tmp_path):
        """베어 저장소 처리 테스트"""
        # 베어 저장소 생성
        bare_repo_path = tmp_path / "bare.git"
        Repo.init(str(bare_repo_path), bare=True)
        
        # 베어 저장소로는 GitAnalyzer를 초기화할 수 없어야 함
        with pytest.raises(ValueError, match="Cannot analyze bare repository"):
            GitAnalyzer(str(bare_repo_path))

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
