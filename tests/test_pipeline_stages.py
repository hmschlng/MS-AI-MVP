"""
Pipeline Stages 모듈 테스트
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.ai_test_generator.core.pipeline_stages import (
    PipelineOrchestrator, PipelineContext, PipelineStage, StageStatus,
    StageResult, VCSAnalysisStage, TestStrategyStage, TestCodeGenerationStage,
    TestScenarioGenerationStage, ReviewGenerationStage
)
from src.ai_test_generator.utils.config import Config


class TestStageResult:
    """StageResult 클래스 테스트"""
    
    def test_stage_result_creation(self):
        """StageResult 객체 생성 테스트"""
        result = StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.PENDING)
        
        assert result.stage == PipelineStage.VCS_ANALYSIS
        assert result.status == StageStatus.PENDING
        assert result.data == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.execution_time is None
    
    def test_add_error(self):
        """에러 추가 테스트"""
        result = StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.RUNNING)
        
        result.add_error("Test error")
        
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
        assert result.status == StageStatus.FAILED
    
    def test_add_warning(self):
        """경고 추가 테스트"""
        result = StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.RUNNING)
        
        result.add_warning("Test warning")
        
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
        assert result.status == StageStatus.RUNNING  # 경고는 상태를 변경하지 않음


class TestPipelineContext:
    """PipelineContext 클래스 테스트"""
    
    def test_pipeline_context_creation(self):
        """PipelineContext 객체 생성 테스트"""
        config = Mock()
        
        context = PipelineContext(
            config=config,
            repo_path="/test/repo",
            selected_commits=["abc123", "def456"],
            project_info={"name": "test project"}
        )
        
        assert context.config == config
        assert context.repo_path == "/test/repo"
        assert len(context.selected_commits) == 2
        assert context.project_info["name"] == "test project"
        assert context.pipeline_id is not None  # UUID가 생성됨


@pytest.mark.asyncio
class TestVCSAnalysisStage:
    """VCSAnalysisStage 테스트"""
    
    async def test_vcs_analysis_stage_success(self):
        """VCS 분석 단계 성공 테스트"""
        stage = VCSAnalysisStage()
        context = PipelineContext(repo_path="/test/repo")
        
        with patch('src.ai_test_generator.core.pipeline_stages.GitAnalyzer') as mock_analyzer_class:
            # GitAnalyzer 모킹
            mock_analyzer = Mock()
            mock_commit = Mock()
            mock_commit.hexsha = "abc123"
            mock_analyzer.get_commits_between.return_value = [mock_commit]
            mock_analyzer.analyze_commit.return_value = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            
            result = await stage.execute(context)
            
            assert result.stage == PipelineStage.VCS_ANALYSIS
            assert result.status == StageStatus.COMPLETED
            assert "commit_analyses" in result.data
    
    async def test_vcs_analysis_stage_no_repo_path(self):
        """저장소 경로가 없을 때 테스트"""
        stage = VCSAnalysisStage()
        context = PipelineContext()  # repo_path가 None
        
        result = await stage.execute(context)
        
        assert result.status == StageStatus.FAILED
        assert len(result.errors) > 0
        assert "Repository path not specified" in result.errors[0]
    
    async def test_vcs_analysis_with_selected_commits(self):
        """선택된 커밋들이 있을 때 테스트"""
        stage = VCSAnalysisStage()
        context = PipelineContext(
            repo_path="/test/repo",
            selected_commits=["abc123", "def456"]
        )
        
        with patch.object(stage, '_analyze_combined_changes') as mock_analyze:
            mock_analyze.return_value = {"test": "data"}
            
            result = await stage.execute(context)
            
            mock_analyze.assert_called_once()
            assert result.status == StageStatus.COMPLETED
            assert "combined_analysis" in result.data


@pytest.mark.asyncio
class TestTestStrategyStage:
    """TestStrategyStage 테스트"""
    
    async def test_test_strategy_stage_success(self):
        """테스트 전략 단계 성공 테스트"""
        config = Mock()
        stage = TestStrategyStage(config)
        
        # VCS 분석 결과가 있는 컨텍스트 생성
        vcs_result = StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.COMPLETED)
        vcs_result.data = {"commit_analyses": [{"test": "data"}]}
        
        context = PipelineContext()
        context.vcs_analysis_result = vcs_result
        
        with patch('src.ai_test_generator.core.pipeline_stages.LLMAgent') as mock_agent_class:
            # LLMAgent 모킹
            mock_agent = AsyncMock()
            mock_agent._determine_test_strategy_step.return_value = {
                "test_strategies": ["unit", "integration"],
                "priority_order": [1, 2]
            }
            mock_agent_class.return_value = mock_agent
            
            result = await stage.execute(context)
            
            assert result.status == StageStatus.COMPLETED
            assert "test_strategies" in result.data
    
    async def test_test_strategy_stage_no_vcs_result(self):
        """VCS 분석 결과가 없을 때 테스트"""
        config = Mock()
        stage = TestStrategyStage(config)
        context = PipelineContext()  # vcs_analysis_result가 None
        
        result = await stage.execute(context)
        
        assert result.status == StageStatus.FAILED
        assert "VCS analysis result not available" in result.errors[0]


@pytest.mark.asyncio
class TestPipelineOrchestrator:
    """PipelineOrchestrator 테스트"""
    
    def test_pipeline_orchestrator_creation(self):
        """PipelineOrchestrator 생성 테스트"""
        config = Mock()
        orchestrator = PipelineOrchestrator(config)
        
        assert orchestrator.config == config
        assert len(orchestrator.stages) == 5  # 5개 단계
        assert len(orchestrator.stage_order) == 5
        assert PipelineStage.VCS_ANALYSIS in orchestrator.stages
    
    async def test_execute_single_stage(self):
        """단일 스테이지 실행 테스트"""
        config = Mock()
        orchestrator = PipelineOrchestrator(config)
        context = PipelineContext()
        
        # VCS Analysis 스테이지 모킹
        mock_stage = AsyncMock()
        mock_result = StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.COMPLETED)
        mock_stage.execute.return_value = mock_result
        orchestrator.stages[PipelineStage.VCS_ANALYSIS] = mock_stage
        
        result = await orchestrator.execute_single_stage(PipelineStage.VCS_ANALYSIS, context)
        
        assert result.stage == PipelineStage.VCS_ANALYSIS
        assert result.status == StageStatus.COMPLETED
        assert context.vcs_analysis_result == result
        mock_stage.execute.assert_called_once_with(context)
    
    async def test_execute_pipeline_success(self):
        """전체 파이프라인 실행 성공 테스트"""
        config = Mock()
        orchestrator = PipelineOrchestrator(config)
        context = PipelineContext()
        
        # 모든 스테이지를 성공으로 모킹
        for stage_key in orchestrator.stages:
            mock_stage = AsyncMock()
            mock_result = StageResult(stage=stage_key, status=StageStatus.COMPLETED)
            mock_stage.execute.return_value = mock_result
            orchestrator.stages[stage_key] = mock_stage
        
        results = await orchestrator.execute_pipeline(context)
        
        assert len(results) == 5
        for stage_key, result in results.items():
            assert result.status == StageStatus.COMPLETED
    
    async def test_execute_pipeline_with_failure(self):
        """파이프라인 실행 중 실패 테스트"""
        config = Mock()
        orchestrator = PipelineOrchestrator(config)
        context = PipelineContext()
        
        # 첫 번째 스테이지는 성공, 두 번째는 실패로 설정
        stage_keys = list(orchestrator.stage_order)
        
        # 첫 번째 스테이지 - 성공
        mock_stage1 = AsyncMock()
        mock_result1 = StageResult(stage=stage_keys[0], status=StageStatus.COMPLETED)
        mock_stage1.execute.return_value = mock_result1
        orchestrator.stages[stage_keys[0]] = mock_stage1
        
        # 두 번째 스테이지 - 실패
        mock_stage2 = AsyncMock()
        mock_result2 = StageResult(stage=stage_keys[1], status=StageStatus.FAILED)
        mock_stage2.execute.return_value = mock_result2
        orchestrator.stages[stage_keys[1]] = mock_stage2
        
        results = await orchestrator.execute_pipeline(context)
        
        # 실패한 단계 이후는 실행되지 않아야 함
        assert len(results) == 2
        assert results[stage_keys[0]].status == StageStatus.COMPLETED
        assert results[stage_keys[1]].status == StageStatus.FAILED
    
    def test_get_pipeline_progress(self):
        """파이프라인 진행상황 조회 테스트"""
        config = Mock()
        orchestrator = PipelineOrchestrator(config)
        
        # 일부 완료된 결과 생성
        results = {
            PipelineStage.VCS_ANALYSIS: StageResult(stage=PipelineStage.VCS_ANALYSIS, status=StageStatus.COMPLETED),
            PipelineStage.TEST_STRATEGY: StageResult(stage=PipelineStage.TEST_STRATEGY, status=StageStatus.RUNNING),
        }
        
        progress = orchestrator.get_pipeline_progress(results)
        
        assert progress['total_stages'] == 5
        assert progress['completed_stages'] == 1
        assert progress['progress_percentage'] == 20.0  # 1/5 * 100
        assert progress['current_stage'] == 'test_strategy'


@pytest.mark.asyncio
class TestPipelineIntegration:
    """파이프라인 통합 테스트"""
    
    async def test_full_pipeline_mock_execution(self):
        """전체 파이프라인 모킹 실행 테스트"""
        config = Mock()
        
        # 파이프라인 컨텍스트 설정
        context = PipelineContext(
            config=config,
            repo_path="/test/repo",
            selected_commits=["abc123", "def456"],
            project_info={"name": "test project"}
        )
        
        orchestrator = PipelineOrchestrator(config)
        
        # 간단한 성공 응답을 반환하는 모든 스테이지 모킹
        for stage_key in orchestrator.stages:
            mock_stage = AsyncMock()
            mock_result = StageResult(stage=stage_key, status=StageStatus.COMPLETED)
            mock_result.data = {f"{stage_key.value}_output": ["test_data"]}
            mock_stage.execute.return_value = mock_result
            orchestrator.stages[stage_key] = mock_stage
        
        # 실행
        results = await orchestrator.execute_pipeline(context)
        
        # 검증
        assert len(results) == 5
        for stage_key, result in results.items():
            assert result.status == StageStatus.COMPLETED
            assert f"{stage_key.value}_output" in result.data
        
        # 컨텍스트에 결과가 저장되었는지 확인
        assert context.vcs_analysis_result is not None
        assert context.test_strategy_result is not None
        assert context.test_code_result is not None
        assert context.test_scenario_result is not None
        assert context.review_result is not None


if __name__ == "__main__":
    pytest.main([__file__])