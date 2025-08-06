"""
Git Analyzer Unit Tests

GitAnalyzer 클래스의 단위 테스트
"""
import os
import tempfile
from pathlib import Path
from datetime import datetime, time
import pytest
import git
from git import Repo

# 프로젝트 루트를 Python 경로에 추가
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_test_generator.core.git_analyzer import GitAnalyzer, CommitAnalysis, FileChange


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
    
    def test_init_valid_repo(self, temp_repo):
        """유효한 저장소로 GitAnalyzer 초기화 테스트"""
        repo, temp_dir = temp_repo
        analyzer = GitAnalyzer(temp_dir)
        
        assert analyzer.repo_path == Path(temp_dir).resolve()
        assert analyzer.default_branch == "main"
        assert analyzer.repo is not None

    def test_clone_remote_repo_and_from_remote(self, tmp_path):
        """원격 저장소 클론 및 from_remote 메서드 테스트"""
        # # 로컬 임시 저장소 생성 및 커밋
        # repo_dir = tmp_path / "origin_repo"
        # repo = Repo.init(repo_dir)
        # file_path = repo_dir / "test.py"
        # file_path.write_text("print('hello')\n")
        # repo.index.add([str(file_path)])
        # repo.index.commit("init commit")
        # # 로컬 저장소를 file:// URL로 사용
        remote_url = "https://github.com/hmschlng/key-board.git"
        # 클론 테스트
        clone_dir = GitAnalyzer.clone_remote_repo(remote_url)
        assert os.path.exists(clone_dir)
        assert os.path.isdir(clone_dir)
        # from_remote 테스트
        analyzer = GitAnalyzer.from_remote(remote_url)
        assert isinstance(analyzer, GitAnalyzer)
        assert analyzer.repo is not None
        # 클린업
        analyzer.repo.close()

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
                if fc.file_path.endswith("a.py"):
                    found = True
        assert found

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
            assert any(fc.file_path.endswith("b.py") for fc in analysis.files_changed)

    def test_get_branch_diff(self, temp_repo):
        """브랜치 간 차이 분석 테스트"""
        repo, temp_dir = temp_repo
        file1 = Path(temp_dir) / "c.py"
        file1.write_text("print('main')\n")
        repo.index.add([str(file1)])
        repo.index.commit("main commit")
        # 새 브랜치 생성 및 파일 수정
        repo.git.checkout("-b", "feature")
        file1.write_text("print('feature')\n")
        repo.index.add([str(file1)])
        repo.index.commit("feature commit")
        analyzer = GitAnalyzer(temp_dir)
        changes = analyzer.get_branch_diff("feature", "main")
        assert isinstance(changes, list)
        assert any(fc.file_path.endswith("c.py") for fc in changes)

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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
