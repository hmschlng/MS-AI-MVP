"""
Git Analyzer Unit Tests

GitAnalyzer 클래스의 단위 테스트
"""
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
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
        shutil.rmtree(temp_dir)
    
    def test_init_valid_repo(self, temp_repo):
        """유효한 저장소로 GitAnalyzer 초기화 테스트"""
        repo, temp_dir = temp_repo
        analyzer = GitAnalyzer(temp_dir)
        
        assert analyzer.repo_path == Path(temp_dir).resolve()
        assert analyzer.default_branch == "main"
        assert analyzer.repo is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
