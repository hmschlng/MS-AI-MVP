"""
Pipeline Stages Module - 단계별 프로세스 처리 모듈

각 단계별로 독립적으로 실행 가능한 파이프라인 스테이지를 정의하고 관리합니다.
사용자가 각 단계의 진행상황을 확인하고 개입할 수 있도록 설계되었습니다.
"""
import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from uuid import uuid4

from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange
from ai_test_generator.core.llm_agent import TestCase, TestScenario, TestStrategy
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import get_logger, LogContext

logger = get_logger(__name__)


class StageStatus(str, Enum):
    """스테이지 실행 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStage(str, Enum):
    """파이프라인 단계 정의"""
    VCS_ANALYSIS = "vcs_analysis"
    TEST_STRATEGY = "test_strategy"
    TEST_CODE_GENERATION = "test_code_generation"
    TEST_SCENARIO_GENERATION = "test_scenario_generation"
    REVIEW_GENERATION = "review_generation"


@dataclass
class StageResult:
    """스테이지 실행 결과"""
    stage: PipelineStage
    status: StageStatus
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: str):
        """오류 추가"""
        self.errors.append(error)
        self.status = StageStatus.FAILED
        logger.error(f"Stage {self.stage}: {error}")
    
    def add_warning(self, warning: str):
        """경고 추가"""
        self.warnings.append(warning)
        logger.warning(f"Stage {self.stage}: {warning}")


@dataclass
class PipelineContext:
    """파이프라인 실행 컨텍스트"""
    pipeline_id: str = field(default_factory=lambda: str(uuid4()))
    config: Optional[Config] = None
    repo_path: Optional[str] = None
    selected_commits: List[str] = field(default_factory=list)
    combined_changes: Optional[Dict[str, Any]] = None
    project_info: Optional[Dict[str, str]] = None
    
    # 단계별 결과
    vcs_analysis_result: Optional[StageResult] = None
    test_strategy_result: Optional[StageResult] = None
    test_code_result: Optional[StageResult] = None
    test_scenario_result: Optional[StageResult] = None
    review_result: Optional[StageResult] = None
    
    # 콜백 함수들
    progress_callback: Optional[Callable[[str, float, str], None]] = None
    user_confirmation_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None


class BaseStage(ABC):
    """기본 스테이지 클래스"""
    
    def __init__(self, stage_name: PipelineStage):
        self.stage_name = stage_name
        
    @abstractmethod
    async def execute(self, context: PipelineContext) -> StageResult:
        """스테이지 실행"""
        pass
    
    def _create_result(self, status: StageStatus = StageStatus.PENDING) -> StageResult:
        """결과 객체 생성"""
        return StageResult(stage=self.stage_name, status=status)
    
    def _report_progress(self, context: PipelineContext, progress: float, message: str):
        """진행상황 보고"""
        if context.progress_callback:
            context.progress_callback(self.stage_name.value, progress, message)


class VCSAnalysisStage(BaseStage):
    """VCS 분석 단계"""
    
    def __init__(self):
        super().__init__(PipelineStage.VCS_ANALYSIS)
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """VCS 분석 실행"""
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "VCS 분석 시작")
            
            # Git 분석기 초기화
            from ai_test_generator.core.git_analyzer import GitAnalyzer
            
            if not context.repo_path:
                result.add_error("Repository path not specified")
                return result
            
            self._report_progress(context, 0.2, "Git 저장소 분석 중...")
            
            git_analyzer = GitAnalyzer(context.repo_path)
            
            # 선택된 커밋들에 대한 변경사항 통합 계산
            if context.selected_commits:
                combined_analysis = await self._analyze_combined_changes(
                    git_analyzer, context.selected_commits
                )
                result.data["combined_analysis"] = combined_analysis
                context.combined_changes = combined_analysis
            else:
                # 기본적으로 최근 커밋들 분석
                commits = git_analyzer.get_commits_between(None, None, None, 10)
                commit_analyses = []
                
                for i, commit in enumerate(commits):
                    self._report_progress(
                        context, 
                        0.3 + (0.6 * (i + 1) / len(commits)), 
                        f"커밋 분석 중: {commit.hexsha[:8]} ({i+1}/{len(commits)})"
                    )
                    
                    # 테스트 파일인지 확인
                    if self._is_test_commit(commit):
                        logger.info(f"Skipping test commit: {commit.hexsha[:8]}")
                        continue
                    
                    analysis = git_analyzer.analyze_commit(commit)
                    commit_analyses.append(analysis)
                
                result.data["commit_analyses"] = commit_analyses
            
            self._report_progress(context, 1.0, "VCS 분석 완료")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            result.add_error(f"VCS analysis failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    async def _analyze_combined_changes(
        self, 
        git_analyzer: "GitAnalyzer", 
        selected_commits: List[str]
    ) -> Dict[str, Any]:
        """선택된 커밋들의 변경사항을 통합 분석"""
        from ai_test_generator.core.git_analyzer import GitAnalyzer
        
        if len(selected_commits) < 2:
            # 단일 커밋인 경우 해당 커밋만 분석
            commit = git_analyzer.repo.commit(selected_commits[0])
            return git_analyzer.analyze_commit(commit).__dict__
        
        # 첫 번째 커밋의 부모와 마지막 커밋 사이의 diff 계산
        start_commit = selected_commits[0] + "^"  # 첫 번째 커밋의 부모
        end_commit = selected_commits[-1]
        
        # Git diff 실행
        diffs = git_analyzer.repo.git.diff(
            start_commit, 
            end_commit, 
            name_status=True
        ).split('\n')
        
        # 변경된 파일들 수집
        file_changes = []
        for diff_line in diffs:
            if not diff_line.strip():
                continue
                
            parts = diff_line.split('\t')
            if len(parts) >= 2:
                status = parts[0]
                file_path = parts[1]
                
                # 파일 내용 변경 분석
                try:
                    content_diff = git_analyzer.repo.git.diff(
                        start_commit, end_commit, file_path
                    )
                    
                    # 추가/삭제 라인 수 계산
                    additions = len([l for l in content_diff.split('\n') if l.startswith('+')])
                    deletions = len([l for l in content_diff.split('\n') if l.startswith('-')])
                    
                    file_changes.append({
                        'filename': file_path,
                        'status': status,
                        'additions': additions,
                        'deletions': deletions,
                        'content_diff': content_diff[:1000]  # 처음 1000자만 저장
                    })
                except Exception as e:
                    logger.warning(f"Failed to analyze file {file_path}: {e}")
        
        return {
            'commit_range': f"{start_commit}...{end_commit}",
            'selected_commits': selected_commits,
            'files_changed': file_changes,
            'total_files': len(file_changes),
            'total_additions': sum(f.get('additions', 0) for f in file_changes),
            'total_deletions': sum(f.get('deletions', 0) for f in file_changes)
        }
    
    def _is_test_commit(self, commit) -> bool:
        """커밋이 테스트 관련인지 판별"""
        # 커밋 메시지 확인
        message_lower = commit.message.lower()
        test_keywords = ['test', 'spec', 'unittest', 'integration test', 'e2e']
        
        if any(keyword in message_lower for keyword in test_keywords):
            return True
        
        # 변경된 파일들 확인
        try:
            for item in commit.stats.files:
                if self._is_test_file(item):
                    return True
        except Exception:
            pass
        
        return False
    
    def _is_test_file(self, file_path: str) -> bool:
        """파일이 테스트 파일인지 판별"""
        test_patterns = [
            'test_', '_test.', '.test.', 'spec_', '_spec.',
            '/test/', '/tests/', '/spec/', '/specs/',
            '__test__', '__tests__'
        ]
        
        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in test_patterns)


class TestStrategyStage(BaseStage):
    """테스트 전략 결정 단계"""
    
    def __init__(self, config: Config):
        super().__init__(PipelineStage.TEST_STRATEGY)
        self.config = config
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """테스트 전략 결정 실행"""
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "테스트 전략 분석 시작")
            
            # VCS 분석 결과 가져오기
            vcs_result = context.vcs_analysis_result
            if not vcs_result or not vcs_result.data:
                result.add_error("VCS analysis result not available")
                return result
            
            # LLM을 통한 전략 결정
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            self._report_progress(context, 0.3, "AI를 통한 테스트 전략 분석 중...")
            
            # 변경사항 기반 전략 분석
            analysis_data = vcs_result.data.get("combined_analysis") or vcs_result.data.get("commit_analyses", [])
            
            strategy_result = await llm_agent._determine_test_strategy_step({
                'file_changes': analysis_data,
                'messages': [],
                'current_step': 'determine_strategy'
            })
            
            result.data["test_strategies"] = strategy_result.get("test_strategies", [])
            result.data["priority_order"] = strategy_result.get("priority_order", [])
            result.data["estimated_effort"] = strategy_result.get("estimated_effort", {})
            
            # 사용자 확인 요청
            if context.user_confirmation_callback:
                confirmed = context.user_confirmation_callback(
                    "테스트 전략이 결정되었습니다. 계속 진행하시겠습니까?",
                    result.data
                )
                if not confirmed:
                    result.status = StageStatus.SKIPPED
                    return result
            
            self._report_progress(context, 1.0, "테스트 전략 결정 완료")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            result.add_error(f"Test strategy determination failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result


class TestCodeGenerationStage(BaseStage):
    """테스트 코드 생성 단계"""
    
    def __init__(self, config: Config):
        super().__init__(PipelineStage.TEST_CODE_GENERATION)
        self.config = config
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """테스트 코드 생성 실행"""
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "테스트 코드 생성 시작")
            
            # 전략 결과 가져오기
            strategy_result = context.test_strategy_result
            if not strategy_result or not strategy_result.data:
                result.add_error("Test strategy result not available")
                return result
            
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            test_strategies = strategy_result.data.get("test_strategies", [])
            generated_tests = []
            
            for i, strategy in enumerate(test_strategies):
                # strategy는 문자열 (예: "unit", "integration", "scenarios")
                strategy_name = strategy if isinstance(strategy, str) else str(strategy)
                
                self._report_progress(
                    context, 
                    0.2 + (0.7 * (i + 1) / len(test_strategies)),
                    f"테스트 코드 생성 중: {strategy_name} ({i+1}/{len(test_strategies)})"
                )
                
                # 개별 전략에 대한 테스트 생성
                test_result = await llm_agent._generate_tests_step({
                    'test_strategy': strategy_name,
                    'file_changes': context.vcs_analysis_result.data.get('combined_analysis', []) or context.vcs_analysis_result.data.get('commit_analyses', []),
                    'messages': [],
                    'current_step': 'generate_tests',
                    'generated_tests': []
                })
                
                if 'tests' in test_result:
                    generated_tests.extend(test_result['tests'])
            
            result.data["generated_tests"] = generated_tests
            result.data["test_count_by_type"] = self._count_tests_by_type(generated_tests)
            
            self._report_progress(context, 1.0, f"테스트 코드 생성 완료: {len(generated_tests)}개")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            result.add_error(f"Test code generation failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _count_tests_by_type(self, tests: List[Dict[str, Any]]) -> Dict[str, int]:
        """테스트 타입별 개수 집계"""
        counts = {}
        for test in tests:
            if isinstance(test, dict):
                test_type = test.get('test_type', 'unknown')
            else:
                # TestCase 객체인 경우
                test_type = test.test_type.value if hasattr(test, 'test_type') else 'unknown'
            counts[test_type] = counts.get(test_type, 0) + 1
        return counts


class TestScenarioGenerationStage(BaseStage):
    """테스트 시나리오 생성 단계"""
    
    def __init__(self, config: Config):
        super().__init__(PipelineStage.TEST_SCENARIO_GENERATION)
        self.config = config
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """테스트 시나리오 생성 실행"""
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "테스트 시나리오 생성 시작")
            
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            # 이전 단계 결과들 수집
            vcs_data = context.vcs_analysis_result.data if context.vcs_analysis_result else {}
            test_data = context.test_code_result.data if context.test_code_result else {}
            
            self._report_progress(context, 0.3, "시나리오 생성 중...")
            
            # 시나리오 생성
            scenario_result = await llm_agent._generate_scenarios_step({
                'file_changes': vcs_data,
                'generated_tests': test_data.get('generated_tests', []),
                'messages': [],
                'current_step': 'generate_scenarios',
                'test_scenarios': []
            })
            
            scenarios = scenario_result.get('test_scenarios', [])
            result.data["test_scenarios"] = scenarios
            result.data["scenario_count_by_priority"] = self._count_scenarios_by_priority(scenarios)
            
            self._report_progress(context, 1.0, f"테스트 시나리오 생성 완료: {len(scenarios)}개")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            result.add_error(f"Test scenario generation failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _count_scenarios_by_priority(self, scenarios: List[Dict[str, Any]]) -> Dict[str, int]:
        """시나리오 우선순위별 개수 집계"""
        counts = {}
        for scenario in scenarios:
            if isinstance(scenario, dict):
                priority = scenario.get('priority', 'Medium')
            else:
                # TestScenario 객체인 경우
                priority = scenario.priority if hasattr(scenario, 'priority') else 'Medium'
            counts[priority] = counts.get(priority, 0) + 1
        return counts


class ReviewGenerationStage(BaseStage):
    """리뷰 생성 단계"""
    
    def __init__(self, config: Config):
        super().__init__(PipelineStage.REVIEW_GENERATION)
        self.config = config
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """리뷰 생성 실행"""
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "리뷰 및 개선 분석 시작")
            
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            # 모든 이전 단계 결과 수집
            all_results = {
                'vcs_analysis': context.vcs_analysis_result.data if context.vcs_analysis_result else {},
                'test_strategy': context.test_strategy_result.data if context.test_strategy_result else {},
                'test_code': context.test_code_result.data if context.test_code_result else {},
                'test_scenarios': context.test_scenario_result.data if context.test_scenario_result else {}
            }
            
            self._report_progress(context, 0.5, "리뷰 분석 중...")
            
            # 리뷰 및 개선 분석
            review_result = await llm_agent._review_and_refine_step({
                'file_changes': all_results['vcs_analysis'],
                'generated_tests': all_results['test_code'].get('generated_tests', []),
                'test_scenarios': all_results['test_scenarios'].get('test_scenarios', []),
                'messages': [],
                'current_step': 'review_and_refine'
            })
            
            result.data["review_summary"] = review_result.get("review_summary", {})
            result.data["improvement_suggestions"] = review_result.get("improvement_suggestions", [])
            result.data["quality_metrics"] = review_result.get("quality_metrics", {})
            
            self._report_progress(context, 1.0, "리뷰 생성 완료")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            result.add_error(f"Review generation failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result


class PipelineOrchestrator:
    """파이프라인 오케스트레이터"""
    
    def __init__(self, config: Config):
        self.config = config
        self.stages = {
            PipelineStage.VCS_ANALYSIS: VCSAnalysisStage(),
            PipelineStage.TEST_STRATEGY: TestStrategyStage(config),
            PipelineStage.TEST_CODE_GENERATION: TestCodeGenerationStage(config),
            PipelineStage.TEST_SCENARIO_GENERATION: TestScenarioGenerationStage(config),
            PipelineStage.REVIEW_GENERATION: ReviewGenerationStage(config)
        }
        
        # 단계 순서 정의
        self.stage_order = [
            PipelineStage.VCS_ANALYSIS,
            PipelineStage.TEST_STRATEGY,
            PipelineStage.TEST_CODE_GENERATION,
            PipelineStage.TEST_SCENARIO_GENERATION,
            PipelineStage.REVIEW_GENERATION
        ]
    
    async def execute_pipeline(
        self, 
        context: PipelineContext,
        stages_to_run: Optional[List[PipelineStage]] = None
    ) -> Dict[PipelineStage, StageResult]:
        """파이프라인 실행"""
        if stages_to_run is None:
            stages_to_run = self.stage_order
        
        results = {}
        
        with LogContext(f"Pipeline execution: {context.pipeline_id}"):
            for stage in stages_to_run:
                if stage not in self.stages:
                    logger.warning(f"Unknown stage: {stage}")
                    continue
                
                logger.info(f"Executing stage: {stage.value}")
                
                try:
                    # 단계 실행
                    stage_instance = self.stages[stage]
                    result = await stage_instance.execute(context)
                    results[stage] = result
                    
                    # 컨텍스트에 결과 저장
                    self._store_result_in_context(context, stage, result)
                    
                    # 실패한 경우 중단
                    if result.status == StageStatus.FAILED:
                        logger.error(f"Stage {stage.value} failed, stopping pipeline")
                        break
                    
                    # 스킵된 경우 로그
                    if result.status == StageStatus.SKIPPED:
                        logger.info(f"Stage {stage.value} was skipped")
                    
                except Exception as e:
                    logger.error(f"Critical error in stage {stage.value}: {e}")
                    error_result = StageResult(stage=stage, status=StageStatus.FAILED)
                    error_result.add_error(f"Critical error: {str(e)}")
                    results[stage] = error_result
                    break
        
        return results
    
    def _store_result_in_context(self, context: PipelineContext, stage: PipelineStage, result: StageResult):
        """컨텍스트에 결과 저장"""
        if stage == PipelineStage.VCS_ANALYSIS:
            context.vcs_analysis_result = result
        elif stage == PipelineStage.TEST_STRATEGY:
            context.test_strategy_result = result
        elif stage == PipelineStage.TEST_CODE_GENERATION:
            context.test_code_result = result
        elif stage == PipelineStage.TEST_SCENARIO_GENERATION:
            context.test_scenario_result = result
        elif stage == PipelineStage.REVIEW_GENERATION:
            context.review_result = result
    
    async def execute_single_stage(
        self, 
        stage: PipelineStage, 
        context: PipelineContext
    ) -> StageResult:
        """단일 스테이지 실행"""
        if stage not in self.stages:
            raise ValueError(f"Unknown stage: {stage}")
        
        stage_instance = self.stages[stage]
        result = await stage_instance.execute(context)
        self._store_result_in_context(context, stage, result)
        
        return result
    
    def get_pipeline_progress(self, results: Dict[PipelineStage, StageResult]) -> Dict[str, Any]:
        """파이프라인 진행상황 조회"""
        total_stages = len(self.stage_order)
        completed_stages = sum(1 for stage in self.stage_order 
                              if stage in results and results[stage].status == StageStatus.COMPLETED)
        
        return {
            'total_stages': total_stages,
            'completed_stages': completed_stages,
            'progress_percentage': (completed_stages / total_stages) * 100,
            'current_stage': self._get_current_stage(results),
            'stage_statuses': {stage.value: results.get(stage, StageResult(stage=stage, status=StageStatus.PENDING)).status.value 
                              for stage in self.stage_order}
        }
    
    def _get_current_stage(self, results: Dict[PipelineStage, StageResult]) -> Optional[str]:
        """현재 실행 중인 스테이지 조회"""
        for stage in self.stage_order:
            if stage not in results:
                return stage.value
            elif results[stage].status == StageStatus.RUNNING:
                return stage.value
        return None