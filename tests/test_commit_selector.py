"""
CommitSelector 모듈 테스트
"""
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.ai_test_generator.core.commit_selector import CommitSelector, CommitInfo, CommitSelection


class TestCommitSelector:
    """CommitSelector 클래스 테스트"""
    
    def test_init_with_valid_repo(self):
        """유효한 Git 저장소로 초기화 테스트"""
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            mock_repo.return_value = MagicMock()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # 임시 디렉토리를 Git 저장소처럼 처리
                Path(temp_dir).mkdir(exist_ok=True)
                
                selector = CommitSelector(temp_dir, "main")
                
                assert selector.repo_path == Path(temp_dir)
                assert selector.branch == "main"
                mock_repo.assert_called_once_with(Path(temp_dir))
    
    def test_init_with_invalid_repo(self):
        """존재하지 않는 경로로 초기화 테스트"""
        with pytest.raises(ValueError, match="Repository path does not exist"):
            CommitSelector("/nonexistent/path", "main")
    
    def test_parse_selection_all(self):
        """'all' 선택 파싱 테스트"""
        from src.ai_test_generator.core.commit_selector import parse_selection
        
        result = parse_selection("all", 5)
        assert result == [0, 1, 2, 3, 4]
    
    def test_parse_selection_single_numbers(self):
        """개별 숫자 선택 파싱 테스트"""
        from src.ai_test_generator.core.commit_selector import parse_selection
        
        result = parse_selection("1,3,5", 5)
        assert result == [0, 2, 4]
    
    def test_parse_selection_range(self):
        """범위 선택 파싱 테스트"""
        from src.ai_test_generator.core.commit_selector import parse_selection
        
        result = parse_selection("1-3", 5)
        assert result == [0, 1, 2]
    
    def test_parse_selection_mixed(self):
        """혼합 선택 파싱 테스트"""
        from src.ai_test_generator.core.commit_selector import parse_selection
        
        result = parse_selection("1,3-5", 5)
        assert result == [0, 2, 3, 4]
    
    def test_parse_selection_invalid_range(self):
        """잘못된 범위 선택 테스트"""
        from src.ai_test_generator.core.commit_selector import parse_selection
        
        with pytest.raises(ValueError, match="out of range"):
            parse_selection("10", 5)
    
    def test_is_test_commit_by_message(self):
        """커밋 메시지로 테스트 커밋 판별 테스트"""
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            mock_repo.return_value = MagicMock()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                Path(temp_dir).mkdir(exist_ok=True)
                selector = CommitSelector(temp_dir, "main")
                
                # 테스트 관련 메시지
                assert selector._is_test_commit("Add unit tests for user service", [])
                assert selector._is_test_commit("Fix test failure in integration test", [])
                assert selector._is_test_commit("Update test coverage", [])
                
                # 일반 커밋 메시지
                assert not selector._is_test_commit("Add user authentication feature", [])
                assert not selector._is_test_commit("Fix bug in payment processing", [])
    
    def test_is_test_file(self):
        """테스트 파일 판별 테스트"""
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            mock_repo.return_value = MagicMock()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                Path(temp_dir).mkdir(exist_ok=True)
                selector = CommitSelector(temp_dir, "main")
                
                # 테스트 파일 패턴
                assert selector._is_test_file("test_user.py")
                assert selector._is_test_file("user_test.py")
                assert selector._is_test_file("tests/test_auth.py")
                assert selector._is_test_file("src/spec/user.spec.js")
                
                # 일반 파일
                assert not selector._is_test_file("user.py")
                assert not selector._is_test_file("auth.js")
                assert not selector._is_test_file("README.md")


class TestCommitInfo:
    """CommitInfo 데이터 클래스 테스트"""
    
    def test_commit_info_creation(self):
        """CommitInfo 객체 생성 테스트"""
        commit_info = CommitInfo(
            hash="abc123def456",
            short_hash="abc123",
            message="Add new feature",
            author="John Doe <john@example.com>",
            date=datetime.now(),
            files_changed=["file1.py", "file2.js"],
            additions=50,
            deletions=10,
            is_test_commit=False
        )
        
        assert commit_info.hash == "abc123def456"
        assert commit_info.short_hash == "abc123"
        assert commit_info.message == "Add new feature"
        assert len(commit_info.files_changed) == 2
        assert commit_info.additions == 50
        assert commit_info.deletions == 10
        assert not commit_info.is_test_commit


class TestCommitSelection:
    """CommitSelection 데이터 클래스 테스트"""
    
    def test_commit_selection_creation(self):
        """CommitSelection 객체 생성 테스트"""
        combined_diff = {
            "base_commit": "base123",
            "latest_commit": "latest456",
            "files_changed": ["file1.py"],
            "summary": {
                "total_files": 1,
                "total_additions": 25,
                "total_deletions": 5
            }
        }
        
        selection = CommitSelection(
            selected_commits=["abc123", "def456"],
            comparison_base="base123",
            combined_diff=combined_diff
        )
        
        assert len(selection.selected_commits) == 2
        assert selection.comparison_base == "base123"
        assert selection.combined_diff["summary"]["total_files"] == 1


@pytest.mark.asyncio
class TestCommitSelectorIntegration:
    """CommitSelector 통합 테스트 (실제 Git 명령 모킹)"""
    
    @patch('subprocess.run')
    def test_get_commit_list_success(self, mock_subprocess):
        """커밋 리스트 조회 성공 테스트"""
        # subprocess.run 모킹
        mock_result = Mock()
        mock_result.stdout = """abc123|abc1|Add feature|John Doe|2023-01-01T10:00:00+00:00
5	2	file1.py
def456|def4|Fix bug|Jane Smith|2023-01-02T11:00:00+00:00
3	1	file2.py"""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            mock_repo.return_value = MagicMock()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                Path(temp_dir).mkdir(exist_ok=True)
                selector = CommitSelector(temp_dir, "main")
                
                commits = selector.get_commit_list(max_commits=10)
                
                assert len(commits) == 2
                assert commits[0].short_hash == "abc1"
                assert commits[0].message == "Add feature"
                assert commits[0].author == "John Doe"
                assert len(commits[0].files_changed) == 1
                assert commits[0].additions == 5
                assert commits[0].deletions == 2
    
    @patch('subprocess.run')
    def test_get_commit_list_with_git_error(self, mock_subprocess):
        """Git 명령 실패 시 테스트"""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ['git'])
        
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            mock_repo.return_value = MagicMock()
            
            with tempfile.TemporaryDirectory() as temp_dir:
                Path(temp_dir).mkdir(exist_ok=True)
                selector = CommitSelector(temp_dir, "main")
                
                commits = selector.get_commit_list()
                assert commits == []
    
    @patch('subprocess.run')
    def test_calculate_combined_changes(self, mock_subprocess):
        """통합 변경사항 계산 테스트"""
        # Git diff 결과 모킹
        mock_result = Mock()
        mock_result.stdout = """10	5	file1.py
15	3	file2.py"""
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        with patch('src.ai_test_generator.core.commit_selector.Repo') as mock_repo:
            # Mock commit objects
            mock_commit1 = Mock()
            mock_commit1.hexsha = "abc123"
            mock_commit1.authored_datetime = datetime.now() - timedelta(days=1)
            mock_commit1.message = "First commit"
            mock_commit1.author.name = "John"
            
            mock_commit2 = Mock()
            mock_commit2.hexsha = "def456"
            mock_commit2.authored_datetime = datetime.now()
            mock_commit2.message = "Second commit"
            mock_commit2.author.name = "Jane"
            mock_commit2.parents = [mock_commit1]
            
            mock_repo_instance = MagicMock()
            mock_repo_instance.commit.side_effect = [mock_commit1, mock_commit2]
            mock_repo.return_value = mock_repo_instance
            
            with tempfile.TemporaryDirectory() as temp_dir:
                Path(temp_dir).mkdir(exist_ok=True)
                selector = CommitSelector(temp_dir, "main")
                
                result = selector.calculate_combined_changes(["abc123", "def456"])
                
                assert "files_changed" in result
                assert "summary" in result
                assert result["summary"]["total_files"] == 2
                assert result["summary"]["total_additions"] == 25
                assert result["summary"]["total_deletions"] == 8
                assert len(result["commit_details"]) == 2


if __name__ == "__main__":
    pytest.main([__file__])