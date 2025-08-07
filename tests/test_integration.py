"""
Main Integration Tests

메인 통합 로직의 단위 테스트 및 통합 테스트
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# 테스트 대상 모듈
from ai_test_generator.main import AITestGenerator, TestGenerationResult
from ai_test_generator.utils.config import Config
from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange
from ai_test_generator.core.llm_agent import TestCase, TestScenario, TestStrategy


class TestTestGenerationResult:
    """TestGenerationResult 클래스 테스트"""
    
    def test_initialization(self):
        """초기화 테스트"""
        result = TestGenerationResult()
        
        assert result.commit_analyses == []
        assert result.generated_tests == []
        assert result.test_scenarios == []
        assert result.excel_scenarios == []
        assert result.output_files == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.execution_time is None
    
    def test_add_error(self):
        """에러 추가 테스트"""
        result = TestGenerationResult()
        error_message = "Test error message"
        
        result.add_error(error_message)
        
        assert len(result.errors) == 1
        assert result.errors[0] == error_message
    
    def test_add_warning(self):
        """경고 추가 테스트"""
        result = TestGenerationResult()
        warning_message = "Test warning message"
        
        result.add_warning(warning_message)
        
        assert len(result.warnings) == 1
        assert result.warnings[0] == warning_message
    
    def test_to_summary_dict(self):
        """요약 딕셔너리 변환 테스트"""
        result = TestGenerationResult()
        
        # 테스트 데이터 설정
        result.commit_analyses = [Mock(), Mock()]  # 2개의 mock 커밋
        result.generated_tests = [Mock(), Mock(), Mock()]  # 3개의 mock 테스트
        result.test_scenarios = [Mock()]  # 1개의 mock 시나리오
        result.output_files = {"excel": "test.xlsx", "report": "test.md"}
        result.execution_time = 15.5
        result.errors = ["error1", "error2"]
        result.warnings = ["warning1"]
        
        # 커밋 분석에 files_changed 속성 추가
        for commit in result.commit_analyses:
            commit.files_changed = [Mock(), Mock()]  # 각 커밋당 2개 파일
        
        summary = result.to_summary_dict()
        
        assert summary["total_commits_analyzed"] == 2
        assert summary["total_files_changed"] == 4  # 2 커밋 * 2 파일
        assert summary["total_tests_generated"] == 3
        assert summary["total_scenarios_generated"] == 1
        assert summary["execution_time_seconds"] == 15.5
        assert summary["errors"] == ["error1", "error2"]
        assert summary["warnings"] == ["warning1"]
        assert summary["success"] == False  # 에러가 있으므로 실패
    
    def test_success_when_no_errors(self):
        """에러가 없을 때 성공 상태 테스트"""
        result = TestGenerationResult()
        result.commit_analyses = [Mock()]
        
        # files_changed 속성 추가
        result.commit_analyses[0].files_changed = [Mock()]
        
        summary = result.to_summary_dict()
        
        assert summary["success"] == True  # 에러가 없으므로 성공


class TestAITestGenerator:
    """AITestGenerator 클래스 테스트"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock 설정 픽스처"""
        config = Mock(spec=Config)
        config.app = Mock()
        
        # Mock Path objects for directories  
        temp_output_dir = tempfile.mkdtemp()
        temp_temp_dir = tempfile.mkdtemp()
        
        mock_output_dir = Mock()
        mock_output_dir.mkdir = Mock()
        mock_output_dir.__truediv__ = Mock(side_effect=lambda x: Path(temp_output_dir) / x)
        mock_output_dir.__str__ = Mock(return_value=temp_output_dir)
        
        mock_temp_dir = Mock()
        mock_temp_dir.mkdir = Mock()
        mock_temp_dir.__truediv__ = Mock(side_effect=lambda x: Path(temp_temp_dir) / x)
        mock_temp_dir.__str__ = Mock(return_value=temp_temp_dir)
        
        config.app.output_directory = mock_output_dir
        config.app.temp_directory = mock_temp_dir
        
        return config
    
    @pytest.fixture
    def mock_file_change(self):
        """Mock 파일 변경사항 픽스처"""
        return FileChange(
            file_path="test.py",
            change_type="modified",
            additions=10,
            deletions=5,
            language="python",
            functions_changed=["test_function"],
            classes_changed=["TestClass"]
        )
    
    @pytest.fixture
    def mock_commit_analysis(self, mock_file_change):
        """Mock 커밋 분석 픽스처"""
        from datetime import datetime
        
        return CommitAnalysis(
            commit_hash="abc123",
            author="Test Author",
            author_email="test@example.com",
            commit_date=datetime.now(),
            message="Test commit message",
            files_changed=[mock_file_change],
            total_additions=10,
            total_deletions=5
        )
    
    @pytest.fixture
    def mock_test_case(self):
        """Mock 테스트 케이스 픽스처"""
        return TestCase(
            name="test_example",
            description="Test case description",
            test_type=TestStrategy.UNIT_TEST,
            code="def test_example(): pass",
            assertions=["assert True"],
            dependencies=["pytest"],
            priority=1
        )
    
    @pytest.fixture
    def mock_test_scenario(self):
        """Mock 테스트 시나리오 픽스처"""
        return TestScenario(
            scenario_id="TS001",
            feature="Test Feature",
            description="Test scenario description",
            preconditions=["Precondition 1"],
            test_steps=[{"action": "Step 1", "data": "test data"}],
            expected_results=["Expected result 1"],
            priority="High",
            test_type="Functional"
        )
    
    def test_initialization(self, mock_config):
        """초기화 테스트"""
        with patch('ai_test_generator.main.LLMAgent') as mock_llm, \
             patch('ai_test_generator.main.ExcelGenerator') as mock_excel, \
             patch('ai_test_generator.main.PromptLoader') as mock_prompt:
            
            generator = AITestGenerator(mock_config)
            
            assert generator.config == mock_config
            mock_llm.assert_called_once_with(mock_config)
            mock_excel.assert_called_once()
            mock_prompt.assert_called_once()
            
            # 디렉토리 생성 확인
            mock_config.app.output_directory.mkdir.assert_called_once()
            mock_config.app.temp_directory.mkdir.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_from_git_repo_success(
        self, 
        mock_config, 
        mock_commit_analysis, 
        mock_test_case, 
        mock_test_scenario
    ):
        """Git 저장소에서 성공적인 테스트 생성"""
        
        with patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent') as mock_llm_agent_class, \
             patch('ai_test_generator.main.ExcelGenerator') as mock_excel_class, \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정
            mock_analyzer_instance = Mock()
            mock_git_analyzer.return_value = mock_analyzer_instance
            mock_analyzer_instance.get_commits_between.return_value = [Mock(hexsha="abc123")]
            mock_analyzer_instance.analyze_commit.return_value = mock_commit_analysis
            
            mock_llm_agent = Mock()
            mock_llm_agent_class.return_value = mock_llm_agent
            mock_llm_agent.generate_tests = AsyncMock(return_value={
                "tests": [mock_test_case],
                "scenarios": [mock_test_scenario],
                "error": None
            })
            
            mock_excel_generator = Mock()
            mock_excel_class.return_value = mock_excel_generator
            mock_excel_generator.generate_from_llm_scenarios.return_value = Mock()
            mock_excel_generator.save_workbook.return_value = "test.xlsx"
            mock_excel_generator.get_default_project_info.return_value = {}
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            
            # _generate_test_code_files 메소드 mock
            generator._generate_test_code_files = AsyncMock(return_value={"python": "test.py"})
            generator._generate_summary_report = AsyncMock(return_value="summary.md")
            
            result = await generator.generate_from_git_repo(
                repo_path="/test/repo",
                max_commits=1
            )
            
            # 검증
            assert len(result.commit_analyses) == 1
            assert len(result.generated_tests) == 1
            assert len(result.test_scenarios) == 1
            assert len(result.errors) == 0
            assert result.execution_time is not None
            assert result.execution_time >= 0
    
    @pytest.mark.asyncio
    async def test_generate_from_git_repo_no_commits(self, mock_config):
        """커밋이 없는 경우 테스트"""
        
        with patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정 - 커밋이 없음
            mock_analyzer_instance = Mock()
            mock_git_analyzer.return_value = mock_analyzer_instance
            mock_analyzer_instance.get_commits_between.return_value = []
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            result = await generator.generate_from_git_repo(
                repo_path="/test/repo",
                max_commits=1
            )
            
            # 검증
            assert len(result.commit_analyses) == 0
            assert len(result.errors) == 1
            assert "No commits found" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_generate_from_remote_git_success(self, mock_config):
        """원격 Git 저장소에서 성공적인 테스트 생성"""
        
        with patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'), \
             patch('shutil.rmtree') as mock_rmtree:
            
            # Mock 설정
            mock_git_analyzer.clone_remote_repo.return_value = "/tmp/cloned_repo"
            
            # generate_from_git_repo 메소드를 mock으로 대체
            generator = AITestGenerator(mock_config)
            generator.generate_from_git_repo = AsyncMock()
            
            mock_result = TestGenerationResult()
            mock_result.generated_tests = [Mock()]
            generator.generate_from_git_repo.return_value = mock_result
            
            # 테스트 실행
            result = await generator.generate_from_remote_git(
                remote_url="https://github.com/test/repo.git",
                max_commits=1
            )
            
            # 검증
            mock_git_analyzer.clone_remote_repo.assert_called_once()
            generator.generate_from_git_repo.assert_called_once()
            mock_rmtree.assert_called_once_with("/tmp/cloned_repo")
            assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_generate_from_remote_git_clone_failure(self, mock_config):
        """원격 저장소 클론 실패 테스트"""
        
        with patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정 - 클론 실패
            mock_git_analyzer.clone_remote_repo.side_effect = Exception("Clone failed")
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            result = await generator.generate_from_remote_git(
                remote_url="https://invalid-url.git",
                max_commits=1
            )
            
            # 검증
            assert len(result.errors) == 1
            assert "Failed to clone remote repository" in result.errors[0]
    
    def test_detect_test_language(self, mock_config):
        """테스트 언어 감지 테스트"""
        
        with patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            generator = AITestGenerator(mock_config)
            
            # Python 테스트
            python_code = "def test_something(): import pytest"
            assert generator._detect_test_language(python_code) == "python"
            
            # Java 테스트
            java_code = "@Test public void testSomething() { import org.junit; }"
            assert generator._detect_test_language(java_code) == "java"
            
            # JavaScript 테스트
            js_code = "describe('test', () => { it('should work', () => {}); });"
            assert generator._detect_test_language(js_code) == "javascript"
            
            # 알 수 없는 언어
            unknown_code = "some random code"
            assert generator._detect_test_language(unknown_code) == "unknown"
    
    @pytest.mark.asyncio
    async def test_create_test_file(self, mock_config):
        """테스트 파일 생성 테스트"""
        
        with patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            generator = AITestGenerator(mock_config)
            
            # Mock 테스트 케이스
            test_cases = [
                TestCase(
                    name="test_example",
                    description="Example test",
                    test_type=TestStrategy.UNIT_TEST,
                    code="def test_example(): assert True",
                    assertions=["assert True"],
                    dependencies=["pytest"],
                    priority=1
                )
            ]
            
            # 테스트 실행
            file_path = await generator._create_test_file("python", test_cases)
            
            # 검증
            assert file_path.endswith(".py")
            assert Path(file_path).exists()
            
            # 파일 내용 확인
            with open(file_path, 'r') as f:
                content = f.read()
                assert "def test_example(): assert True" in content
                assert "import pytest" in content
            
            # 정리
            Path(file_path).unlink()


class TestConvenienceFunctions:
    """편의 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_generate_tests_from_git(self):
        """generate_tests_from_git 편의 함수 테스트"""
        
        with patch('ai_test_generator.main.Config') as mock_config_class, \
             patch('ai_test_generator.main.AITestGenerator') as mock_generator_class:
            
            # Mock 설정
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            
            mock_generator = Mock()
            mock_generator_class.return_value = mock_generator
            mock_generator.generate_from_git_repo = AsyncMock()
            
            mock_result = TestGenerationResult()
            mock_generator.generate_from_git_repo.return_value = mock_result
            
            # 테스트 실행
            from ai_test_generator.main import generate_tests_from_git
            
            result = await generate_tests_from_git(
                repo_path="/test/repo",
                max_commits=5
            )
            
            # 검증
            mock_config_class.assert_called_once()
            mock_generator_class.assert_called_once_with(mock_config)
            mock_generator.generate_from_git_repo.assert_called_once_with(
                "/test/repo", 
                max_commits=5
            )
            assert result == mock_result


@pytest.mark.performance
class TestPerformance:
    """성능 테스트"""
    
    @pytest.mark.asyncio
    async def test_multiple_commits_performance(self):
        """다중 커밋 성능 테스트"""
        import time
        
        with patch('ai_test_generator.main.Config') as mock_config_class, \
             patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent') as mock_llm_class, \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정
            mock_config = Mock()
            mock_config.app = Mock()
            
            # Mock Path objects for directories
            mock_output_dir = Mock()
            mock_output_dir.mkdir = Mock()
            mock_temp_dir = Mock()
            mock_temp_dir.mkdir = Mock()
            
            mock_config.app.output_directory = mock_output_dir
            mock_config.app.temp_directory = mock_temp_dir
            mock_config_class.return_value = mock_config
            
            # 많은 커밋 시뮬레이션 (10개)
            mock_commits = []
            for i in range(10):
                mock_commit = Mock()
                mock_commit.hexsha = f"commit{i:03d}"
                mock_commits.append(mock_commit)
            
            mock_analyzer = Mock()
            mock_git_analyzer.return_value = mock_analyzer
            mock_analyzer.get_commits_between.return_value = mock_commits
            
            # 각 커밋에 대한 분석 결과
            def create_mock_analysis(i):
                analysis = Mock()
                analysis.commit_hash = f"commit{i:03d}"
                analysis.files_changed = [Mock() for _ in range(2)]  # 각 커밋당 2개 파일
                return analysis
            
            mock_analyzer.analyze_commit.side_effect = [create_mock_analysis(i) for i in range(10)]
            
            # LLM Agent Mock - 빠른 응답 시뮬레이션
            mock_llm_agent = Mock()
            mock_llm_class.return_value = mock_llm_agent
            
            async def fast_generate_tests(*args, **kwargs):
                await asyncio.sleep(0.01)  # 10ms 지연
                return {
                    "tests": [Mock()],
                    "scenarios": [Mock()],
                    "error": None
                }
            
            mock_llm_agent.generate_tests = fast_generate_tests
            
            # 성능 측정
            start_time = time.time()
            
            generator = AITestGenerator(mock_config)
            generator._generate_excel_output = AsyncMock(return_value="test.xlsx")
            generator._generate_test_code_files = AsyncMock(return_value={"python": "test.py"})
            generator._generate_summary_report = AsyncMock(return_value="summary.md")
            
            result = await generator.generate_from_git_repo(
                repo_path="/test/repo",
                max_commits=10
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # 성능 검증 (10개 커밋을 5초 내에 처리)
            assert execution_time < 5.0, f"Performance too slow: {execution_time:.2f}s"
            assert len(result.commit_analyses) == 10
            assert len(result.generated_tests) == 10
            assert len(result.test_scenarios) == 10


class TestErrorScenarios:
    """에러 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_git_analyzer_failure(self):
        """Git Analyzer 실패 시나리오"""
        
        with patch('ai_test_generator.main.Config') as mock_config_class, \
             patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent'), \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정
            mock_config = Mock()
            mock_config.app = Mock()
            
            # Mock Path objects for directories
            mock_output_dir = Mock()
            mock_output_dir.mkdir = Mock()
            mock_temp_dir = Mock()
            mock_temp_dir.mkdir = Mock()
            
            mock_config.app.output_directory = mock_output_dir
            mock_config.app.temp_directory = mock_temp_dir
            mock_config_class.return_value = mock_config
            
            # GitAnalyzer 초기화 실패
            mock_git_analyzer.side_effect = Exception("Git repository not found")
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            result = await generator.generate_from_git_repo(
                repo_path="/invalid/repo",
                max_commits=1
            )
            
            # 검증
            assert len(result.errors) >= 1
            assert any("Git repository not found" in error or "Critical error" in error 
                      for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_llm_agent_failure(self):
        """LLM Agent 실패 시나리오"""
        
        with patch('ai_test_generator.main.Config') as mock_config_class, \
             patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent') as mock_llm_class, \
             patch('ai_test_generator.main.ExcelGenerator'), \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정
            mock_config = Mock()
            mock_config.app = Mock()
            
            # Mock Path objects for directories
            mock_output_dir = Mock()
            mock_output_dir.mkdir = Mock()
            mock_temp_dir = Mock()
            mock_temp_dir.mkdir = Mock()
            
            mock_config.app.output_directory = mock_output_dir
            mock_config.app.temp_directory = mock_temp_dir
            mock_config_class.return_value = mock_config
            
            # Git Analyzer는 정상 작동
            mock_analyzer = Mock()
            mock_git_analyzer.return_value = mock_analyzer
            mock_analyzer.get_commits_between.return_value = [Mock(hexsha="abc123")]
            
            mock_analysis = Mock()
            mock_analysis.commit_hash = "abc123"
            mock_analysis.files_changed = [Mock()]
            mock_analyzer.analyze_commit.return_value = mock_analysis
            
            # LLM Agent는 실패
            mock_llm_agent = Mock()
            mock_llm_class.return_value = mock_llm_agent
            mock_llm_agent.generate_tests = AsyncMock(return_value={
                "tests": [],
                "scenarios": [],
                "error": "LLM API failed"
            })
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            result = await generator.generate_from_git_repo(
                repo_path="/test/repo",
                max_commits=1
            )
            
            # 검증
            assert len(result.commit_analyses) == 1
            assert len(result.errors) >= 1
            assert any("LLM API failed" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_excel_generation_failure(self):
        """Excel 생성 실패 시나리오"""
        
        with patch('ai_test_generator.main.Config') as mock_config_class, \
             patch('ai_test_generator.main.GitAnalyzer') as mock_git_analyzer, \
             patch('ai_test_generator.main.LLMAgent') as mock_llm_class, \
             patch('ai_test_generator.main.ExcelGenerator') as mock_excel_class, \
             patch('ai_test_generator.main.PromptLoader'):
            
            # Mock 설정
            mock_config = Mock()
            mock_config.app = Mock()
            
            # Mock Path objects for directories
            mock_output_dir = Mock()
            mock_output_dir.mkdir = Mock()
            mock_temp_dir = Mock()
            mock_temp_dir.mkdir = Mock()
            
            mock_config.app.output_directory = mock_output_dir
            mock_config.app.temp_directory = mock_temp_dir
            mock_config_class.return_value = mock_config
            
            # Git Analyzer 정상
            mock_analyzer = Mock()
            mock_git_analyzer.return_value = mock_analyzer
            mock_analyzer.get_commits_between.return_value = [Mock(hexsha="abc123")]
            
            mock_analysis = Mock()
            mock_analysis.files_changed = [Mock()]
            mock_analyzer.analyze_commit.return_value = mock_analysis
            
            # LLM Agent 정상
            mock_llm_agent = Mock()
            mock_llm_class.return_value = mock_llm_agent
            mock_llm_agent.generate_tests = AsyncMock(return_value={
                "tests": [Mock()],
                "scenarios": [Mock()],
                "error": None
            })
            
            # Excel Generator 실패
            mock_excel = Mock()
            mock_excel_class.return_value = mock_excel
            mock_excel.generate_from_llm_scenarios.side_effect = Exception("Excel generation failed")
            mock_excel.get_default_project_info.return_value = {}
            
            # 테스트 실행
            generator = AITestGenerator(mock_config)
            result = await generator.generate_from_git_repo(
                repo_path="/test/repo",
                max_commits=1
            )
            
            # 검증 - Excel 생성은 실패했지만 다른 결과는 있어야 함
            assert len(result.generated_tests) == 1
            assert len(result.test_scenarios) == 1
            assert len(result.errors) >= 1
            assert any("Failed to generate Excel file" in error for error in result.errors)


if __name__ == "__main__":
    # pytest 실행 설정
    pytest_args = [
        __file__,
        "-v",  # verbose
        "-x",  # stop on first failure
        "--tb=short",  # short traceback format
    ]
    
    # 마커별 실행 옵션
    import sys
    if len(sys.argv) > 1:
        marker = sys.argv[1]
        if marker in ["unit", "integration", "performance", "error"]:
            pytest_args.extend(["-m", marker])
    
    pytest.main(pytest_args)