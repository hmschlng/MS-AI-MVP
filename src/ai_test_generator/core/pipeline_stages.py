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
import traceback

from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange
from ai_test_generator.core.git_analyzer import GitAnalyzer
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
    
    # 클래스 객체를 직접 저장하기 위한 필드들
    test_strategies: Optional[List[TestStrategy]] = None
    test_cases: Optional[List['TestCase']] = None  
    test_scenarios: Optional[List['TestScenario']] = None
    commit_analysis: Optional['CommitAnalysis'] = None
    
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
        git_analyzer: GitAnalyzer, 
        selected_commits: List[str]
    ) -> Dict[str, Any]:
        """선택된 커밋들의 변경사항을 통합 분석"""
        
        if len(selected_commits) < 2:
            # 단일 커밋인 경우 해당 커밋만 분석
            commit = git_analyzer.repo.commit(selected_commits[0])
            return git_analyzer.analyze_commit(commit).__dict__
        
        # 첫 번째 커밋의 부모와 마지막 커밋 사이의 diff 계산
        start_commit = selected_commits[0] + "^"  # 첫 번째 커밋의 부모
        end_commit = selected_commits[-1]
        
        # Git diff 실행
        logger.info(f"Running git diff between {start_commit} and {end_commit}")
        diffs = git_analyzer.repo.git.diff(
            start_commit, 
            end_commit, 
            name_status=True
        ).split('\n')
        logger.info(f"Git diff result: {len(diffs)} lines, content: {diffs[:5]}")
        
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
            
            # VCS 분석 결과 가져오기 (커밋 선택에서 생성된 데이터 사용)
            logger.info("=== Test Strategy 시작 - VCS 분석 결과 확인 ===")
            
            vcs_result = context.vcs_analysis_result
            combined_changes = context.combined_changes
            
            logger.info(f"vcs_analysis_result: {vcs_result is not None}")
            logger.info(f"combined_changes: {combined_changes is not None}")
            if combined_changes:
                logger.info(f"combined_changes keys: {list(combined_changes.keys()) if isinstance(combined_changes, dict) else type(combined_changes)}")
                logger.info(f"combined_changes content preview: {str(combined_changes)[:300]}...")
            
            # VCS 결과가 없으면 combined_changes 사용
            if not vcs_result or not vcs_result.data:
                if not combined_changes:
                    result.add_error("Neither VCS analysis result nor combined_changes available")
                    return result
                logger.info("Using combined_changes from commit selection instead of vcs_analysis_result")
            
            # LLM을 통한 전략 결정
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            self._report_progress(context, 0.3, "AI를 통한 테스트 전략 분석 중...")
            
            # 변경사항 기반 전략 분석 - combined_changes 우선 사용
            if combined_changes:
                analysis_data = combined_changes
                logger.info("Using combined_changes as analysis_data")
            elif vcs_result and vcs_result.data:
                analysis_data = vcs_result.data.get("combined_analysis") or vcs_result.data.get("commit_analyses", [])
                logger.info("Using vcs_result.data as analysis_data")
            else:
                analysis_data = []
                logger.warning("No analysis data available")
                
            logger.info(f"Final analysis_data type: {type(analysis_data)}, preview: {str(analysis_data)[:200]}...")
            
            strategy_result = await llm_agent._determine_test_strategy_step({
                'file_changes': analysis_data,
                'messages': [],
                'current_step': 'determine_strategy'
            })
            
            # 전략 결과를 StageResult에 직접 저장
            strategies = strategy_result.get("test_strategies", [])
            # 문자열을 TestStrategy enum으로 변환
            strategy_mapping = {
                "unit": TestStrategy.UNIT_TEST,
                "integration": TestStrategy.INTEGRATION_TEST,
                "performance": TestStrategy.PERFORMANCE_TEST,
                "security": TestStrategy.SECURITY_TEST,
                "unit_test": TestStrategy.UNIT_TEST,
                "integration_test": TestStrategy.INTEGRATION_TEST,
                "performance_test": TestStrategy.PERFORMANCE_TEST,
                "security_test": TestStrategy.SECURITY_TEST
            }
            
            result.test_strategies = []
            for s in strategies:
                if isinstance(s, str):
                    mapped_strategy = strategy_mapping.get(s.lower(), TestStrategy.UNIT_TEST)
                    result.test_strategies.append(mapped_strategy)
                else:
                    result.test_strategies.append(s)
            
            # UI 전달을 위한 데이터도 함께 저장
            result.data["test_strategies"] = strategies
            result.data["priority_order"] = strategy_result.get("priority_order", [])
            result.data["estimated_effort"] = strategy_result.get("estimated_effort", {})
            result.data["llm_recommendations"] = strategy_result.get("llm_recommendations", {})
            
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
                
                # 개별 전략에 대한 테스트 생성 - combined_changes 우선 사용
                if context.combined_changes:
                    file_changes_data = context.combined_changes
                elif context.vcs_analysis_result and context.vcs_analysis_result.data:
                    file_changes_data = context.vcs_analysis_result.data.get('combined_analysis', []) or context.vcs_analysis_result.data.get('commit_analyses', [])
                else:
                    file_changes_data = []
                
                logger.info(f"=== Test Generation Debug ===")
                logger.info(f"Strategy: {strategy_name}")
                logger.info(f"File changes data type: {type(file_changes_data)}")
                if isinstance(file_changes_data, dict):
                    logger.info(f"File changes keys: {list(file_changes_data.keys())}")
                    if 'files_changed' in file_changes_data:
                        logger.info(f"files_changed count: {len(file_changes_data['files_changed'])}")
                logger.info(f"Repo path: {context.repo_path}")
                    
                test_result = await llm_agent._generate_tests_step({
                    'test_strategy': strategy_name,
                    'file_changes': file_changes_data,
                    'messages': [],
                    'current_step': 'generate_tests',
                    'generated_tests': [],
                    'repo_path': context.repo_path  # 저장소 경로 추가
                })
                
                if 'tests' in test_result:
                    generated_tests.extend(test_result['tests'])
            
            # TestCase 객체들을 직접 저장
            result.test_cases = generated_tests
            logger.info(f"=== 테스트코드 생성 단계 완료 - 결과 저장 ===")
            logger.info(f"생성된 테스트 개수: {len(generated_tests)}")
            logger.info(f"result.test_cases에 저장된 테스트 개수: {len(result.test_cases) if result.test_cases else 0}")
            
            # 첫 번째 테스트의 샘플 정보 로깅 (전체 코드 포함)
            if generated_tests:
                first_test = generated_tests[0]
                logger.info(f"첫 번째 테스트 정보 - 타입: {type(first_test)}")
                if hasattr(first_test, 'name'):
                    logger.info(f"  - name: {first_test.name}")
                if hasattr(first_test, 'description'):
                    logger.info(f"  - description: {first_test.description}")
                if hasattr(first_test, 'test_type'):
                    logger.info(f"  - test_type: {first_test.test_type}")
                if hasattr(first_test, 'code'):
                    code_content = first_test.code if first_test.code else ""
                    logger.info(f"  - code 길이: {len(code_content)} 문자")
                    logger.info(f"  - 생성된 테스트 코드 전체 내용:")
                    logger.info("=" * 60)
                    logger.info(code_content)
                    logger.info("=" * 60)
            
            # UI 전달을 위해 직렬화 가능한 형태로도 저장
            try:
                logger.info(f"=== 테스트코드 직렬화 시작 ===")
                logger.info(f"Converting {len(generated_tests)} tests to dict format")
                logger.info(f"First test type: {type(generated_tests[0]) if generated_tests else 'No tests'}")
                
                serialized_tests = []
                for i, tc in enumerate(generated_tests):
                    try:
                        if hasattr(tc, 'name'):
                            # TestCase 객체인 경우
                            serialized_dict = self._test_case_to_dict(tc)
                            serialized_tests.append(serialized_dict)
                            logger.debug(f"테스트 {i+1} 직렬화 완료: {serialized_dict.get('name', 'unnamed')}")
                        elif isinstance(tc, dict):
                            # 이미 딕셔너리인 경우
                            logger.warning(f"Test {i} is already a dict: {tc.keys() if tc else 'empty'}")
                            serialized_tests.append(tc)
                        else:
                            logger.error(f"Unknown test type: {type(tc)}")
                            # 알 수 없는 타입인 경우도 기본값으로 처리
                            serialized_tests.append({
                                "name": f"Unknown_Test_{i+1}",
                                "description": f"Unknown test type: {type(tc)}",
                                "test_type": "unit",
                                "code": str(tc) if tc else "",
                                "assertions": [],
                                "dependencies": [],
                                "priority": 3
                            })
                    except Exception as inner_e:
                        logger.error(f"Error processing test {i}: {inner_e}")
                        # 개별 테스트 오류는 해당 테스트만 스킵하고 계속 진행
                        serialized_tests.append({
                            "name": f"Error_Test_{i+1}",
                            "description": f"Error processing test: {str(inner_e)}",
                            "test_type": "unit",
                            "code": "# Test processing error",
                            "assertions": [],
                            "dependencies": [],
                            "priority": 3
                        })
                
                result.data["generated_tests"] = serialized_tests
                result.data["test_count_by_type"] = self._count_tests_by_type(generated_tests)
                
                logger.info(f"=== 테스트코드 직렬화 완료 ===")
                logger.info(f"Successfully serialized {len(serialized_tests)} tests")
                logger.info(f"result.data['generated_tests'] 크기: {len(result.data['generated_tests'])}")
                
                # 직렬화된 데이터 샘플 로깅 (전체 코드 포함)
                if serialized_tests:
                    first_serialized = serialized_tests[0]
                    logger.info(f"첫 번째 직렬화된 테스트:")
                    logger.info(f"  - name: {first_serialized.get('name', 'N/A')}")
                    logger.info(f"  - test_type: {first_serialized.get('test_type', 'N/A')}")
                    logger.info(f"  - description: {first_serialized.get('description', 'N/A')}")
                    
                    serialized_code = first_serialized.get('code', '')
                    logger.info(f"  - code 길이: {len(serialized_code) if serialized_code else 0} 문자")
                    logger.info(f"  - 직렬화된 테스트 코드 전체 내용:")
                    logger.info("=" * 60)
                    logger.info(serialized_code if serialized_code else "(코드 없음)")
                    logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"=== 테스트코드 직렬화 실패 ===")
                logger.error(f"Error serializing tests: {e}")
                logger.error(f"Full stack trace: {traceback.format_exc()}")
                
                # 직렬화가 실패해도 TestCase 객체들은 유지되므로 UI에서 처리 가능
                result.data["generated_tests"] = []
                result.data["test_count_by_type"] = {}
                logger.warning("Test serialization failed, but TestCase objects are preserved for UI fallback")
                logger.warning(f"원본 TestCase 객체는 여전히 사용 가능: {len(result.test_cases) if result.test_cases else 0}개")
            
            self._report_progress(context, 1.0, f"테스트 코드 생성 완료: {len(generated_tests)}개")
            result.status = StageStatus.COMPLETED
            
        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Test code generation failed: {str(e)}\nStack trace:\n{tb_str}")
            result.add_error(f"Test code generation failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _count_tests_by_type(self, tests: List['TestCase']) -> Dict[str, int]:
        """테스트 타입별 개수 집계"""
        counts = {}
        
        for i, test in enumerate(tests):
            try:
                if hasattr(test, 'test_type') and test.test_type:
                    test_type = test.test_type.value if hasattr(test.test_type, 'value') else str(test.test_type)
                elif isinstance(test, dict) and 'test_type' in test:
                    test_type = test['test_type']
                else:
                    test_type = 'unknown'
                    
                counts[test_type] = counts.get(test_type, 0) + 1
                
            except Exception as e:
                logger.warning(f"Error counting test type for test {i}: {e}")
                counts['unknown'] = counts.get('unknown', 0) + 1
                
        logger.info(f"Test count by type: {counts}")
        return counts
    
    def _test_case_to_dict(self, test_case: 'TestCase') -> Dict[str, Any]:
        """TestCase 객체를 딕셔너리로 변환"""
        try:
            name = getattr(test_case, 'name', 'unknown_test')
            description = getattr(test_case, 'description', '')
            
            # test_type 처리: enum 객체인 경우 value 속성 사용
            if hasattr(test_case, 'test_type'):
                test_type_obj = test_case.test_type
                if hasattr(test_type_obj, 'value'):
                    test_type = test_type_obj.value
                else:
                    test_type = str(test_type_obj)
            else:
                test_type = 'unit'
            
            code = getattr(test_case, 'code', '')
            assertions = getattr(test_case, 'assertions', [])
            dependencies = getattr(test_case, 'dependencies', [])
            priority = getattr(test_case, 'priority', 3)
            
            result_dict = {
                "name": name,
                "description": description,
                "test_type": test_type,
                "code": code,
                "assertions": assertions,
                "dependencies": dependencies,
                "priority": priority
            }
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error converting test case to dict: {e}")
            # 오류 발생시 기본값으로 반환
            return {
                "name": "error_test",
                "description": f"Error converting test: {str(e)}",
                "test_type": "unit",
                "code": "# Error occurred during test case conversion",
                "assertions": [],
                "dependencies": [],
                "priority": 3
            }


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
            logger.info("=== 테스트 시나리오 생성 단계 시작 ===")
            self._report_progress(context, 0.1, "테스트 시나리오 생성 시작")
            
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            # 이전 단계 결과들 수집 - 객체 우선 사용
            logger.info("이전 단계 결과 수집 중...")
            vcs_data = context.vcs_analysis_result.data if context.vcs_analysis_result else {}
            logger.info(f"VCS 데이터 존재: {bool(vcs_data)}, 키들: {list(vcs_data.keys()) if vcs_data else '없음'}")
            
            # 생성된 테스트 객체들을 직접 사용
            generated_test_objects = context.test_code_result.test_cases if context.test_code_result and context.test_code_result.test_cases else []
            logger.info(f"생성된 테스트 객체 개수: {len(generated_test_objects)}")
            
            # 테스트 객체들의 상세 정보 로깅
            if generated_test_objects:
                logger.info("생성된 테스트 객체들 상세 정보:")
                for i, test_obj in enumerate(generated_test_objects[:3]):  # 처음 3개만 로깅
                    logger.info(f"  테스트 {i+1}:")
                    logger.info(f"    - name: {getattr(test_obj, 'name', 'N/A')}")
                    logger.info(f"    - description: {getattr(test_obj, 'description', 'N/A')}")
                    logger.info(f"    - test_type: {getattr(test_obj, 'test_type', 'N/A')}")
                    logger.info(f"    - code 길이: {len(getattr(test_obj, 'code', '')) if getattr(test_obj, 'code', '') else 0} 문자")
                if len(generated_test_objects) > 3:
                    logger.info(f"  ... 그 외 {len(generated_test_objects) - 3}개 테스트")
            else:
                logger.warning("생성된 테스트 객체가 없습니다")
            
            self._report_progress(context, 0.3, "시나리오 생성 중...")
            
            # 시나리오 생성을 위한 입력 데이터 구성
            scenario_input_data = {
                'file_changes': vcs_data,
                'generated_tests': generated_test_objects,
                'messages': [],
                'current_step': 'generate_scenarios',
                'test_scenarios': []
            }
            
            logger.info("LLM 에이전트로 시나리오 생성 요청 시작")
            logger.info(f"입력 데이터 구성:")
            logger.info(f"  - file_changes 타입: {type(vcs_data)}")
            logger.info(f"  - generated_tests 개수: {len(generated_test_objects)}")
            logger.info(f"  - current_step: {scenario_input_data['current_step']}")
            
            # 시나리오 생성 - TestCase 객체들을 직접 전달
            scenario_result = await llm_agent._generate_scenarios_step(scenario_input_data)
            
            # 시나리오 생성 결과 처리
            logger.info("시나리오 생성 결과 분석 시작")
            logger.info(f"scenario_result 타입: {type(scenario_result)}")
            logger.info(f"scenario_result 키들: {list(scenario_result.keys()) if isinstance(scenario_result, dict) else 'dict가 아님'}")
            
            # 딕셔너리 형태의 시나리오를 TestScenario 객체로 변환
            scenario_dicts = scenario_result.get('test_scenarios', [])
            logger.info(f"시나리오 딕셔너리 개수: {len(scenario_dicts)}")
            
            if scenario_dicts:
                logger.info("생성된 시나리오들 상세 정보:")
                for i, scenario_dict in enumerate(scenario_dicts[:2]):  # 처음 2개만 로깅
                    logger.info(f"  시나리오 {i+1}:")
                    logger.info(f"    - scenario_id: {scenario_dict.get('scenario_id', 'N/A')}")
                    logger.info(f"    - feature: {scenario_dict.get('feature', 'N/A')}")
                    logger.info(f"    - description: {scenario_dict.get('description', 'N/A')[:100]}...")
                    logger.info(f"    - test_steps 개수: {len(scenario_dict.get('test_steps', []))}")
                    logger.info(f"    - expected_results 개수: {len(scenario_dict.get('expected_results', []))}")
                    logger.info(f"    - priority: {scenario_dict.get('priority', 'N/A')}")
                    logger.info(f"    - test_type: {scenario_dict.get('test_type', 'N/A')}")
                if len(scenario_dicts) > 2:
                    logger.info(f"  ... 그 외 {len(scenario_dicts) - 2}개 시나리오")
            
            scenarios = []
            logger.info("시나리오 딕셔너리를 TestScenario 객체로 변환 중...")
            
            for i, scenario_dict in enumerate(scenario_dicts):
                try:
                    scenario = TestScenario(
                        scenario_id=scenario_dict.get('scenario_id', f'S{i+1}'),
                        feature=scenario_dict.get('feature', ''),
                        description=scenario_dict.get('description', ''),
                        preconditions=scenario_dict.get('preconditions', []),
                        test_steps=scenario_dict.get('test_steps', []),
                        expected_results=scenario_dict.get('expected_results', []),
                        test_data=scenario_dict.get('test_data'),
                        priority=scenario_dict.get('priority', 'Medium'),
                        test_type=scenario_dict.get('test_type', 'Functional')
                    )
                    scenarios.append(scenario)
                    logger.debug(f"시나리오 {i+1} 변환 성공: {scenario.scenario_id}")
                    
                except Exception as scenario_error:
                    logger.error(f"시나리오 {i+1} 변환 중 오류: {scenario_error}")
                    logger.error(f"문제가 된 시나리오 데이터: {scenario_dict}")
            
            logger.info(f"최종 변환된 TestScenario 객체 개수: {len(scenarios)}")
            
            # TestScenario 객체들을 직접 저장
            result.test_scenarios = scenarios
            
            # UI 전달을 위해 직렬화 가능한 형태로도 저장  
            try:
                logger.info("시나리오 직렬화 시작")
                serialized_scenarios = [self._test_scenario_to_dict(sc) for sc in scenarios]
                result.data["test_scenarios"] = serialized_scenarios
                result.data["scenario_count_by_priority"] = self._count_scenarios_by_priority(scenarios)
                logger.info(f"시나리오 직렬화 완료: {len(serialized_scenarios)}개")
                
                # 직렬화된 첫 번째 시나리오 샘플 로깅
                if serialized_scenarios:
                    first_serialized = serialized_scenarios[0]
                    logger.info("첫 번째 직렬화된 시나리오:")
                    logger.info("=" * 60)
                    logger.info(json.dumps(first_serialized, indent=2, ensure_ascii=False))
                    logger.info("=" * 60)
                    
            except Exception as serialization_error:
                logger.error(f"시나리오 직렬화 중 오류: {serialization_error}")
                logger.error(f"스택 트레이스: {traceback.format_exc()}")
                result.data["test_scenarios"] = []
                result.data["scenario_count_by_priority"] = {}
            
            self._report_progress(context, 1.0, f"테스트 시나리오 생성 완료: {len(scenarios)}개")
            result.status = StageStatus.COMPLETED
            logger.info("=== 테스트 시나리오 생성 단계 완료 ===")
            
        except Exception as e:
            result.add_error(f"Test scenario generation failed: {str(e)}")
        
        finally:
            result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _count_scenarios_by_priority(self, scenarios: List['TestScenario']) -> Dict[str, int]:
        """시나리오 우선순위별 개수 집계"""
        counts = {}
        for scenario in scenarios:
            priority = scenario.priority if hasattr(scenario, 'priority') else 'Medium'
            counts[priority] = counts.get(priority, 0) + 1
        return counts
    
    def _test_scenario_to_dict(self, scenario: 'TestScenario') -> Dict[str, Any]:
        """TestScenario 객체를 딕셔너리로 변환"""
        return {
            "scenario_id": scenario.scenario_id,
            "feature": scenario.feature,
            "description": scenario.description,
            "preconditions": scenario.preconditions,
            "test_steps": scenario.test_steps,
            "expected_results": scenario.expected_results,
            "test_data": scenario.test_data,
            "priority": scenario.priority,
            "test_type": scenario.test_type
        }


class ReviewGenerationStage(BaseStage):
    """리뷰 생성 단계"""
    
    def __init__(self, config: Config):
        super().__init__(PipelineStage.REVIEW_GENERATION)
        self.config = config
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """리뷰 생성 실행"""
        logger.info("=== 리뷰 생성 단계 시작 ===")
        result = self._create_result(StageStatus.RUNNING)
        start_time = datetime.now()
        
        try:
            self._report_progress(context, 0.1, "리뷰 및 개선 분석 시작")
            logger.info("이전 단계 결과 수집 중...")
            
            from ai_test_generator.core.llm_agent import LLMAgent
            llm_agent = LLMAgent(self.config)
            
            # 모든 이전 단계 결과 수집 - 객체 우선 사용
            vcs_data = context.vcs_analysis_result.data if context.vcs_analysis_result else {}
            test_objects = context.test_code_result.test_cases if context.test_code_result and context.test_code_result.test_cases else []
            scenario_objects = context.test_scenario_result.test_scenarios if context.test_scenario_result and context.test_scenario_result.test_scenarios else []
            
            logger.info("수집된 이전 단계 데이터:")
            logger.info(f"  - VCS 데이터 키 개수: {len(vcs_data.keys()) if vcs_data else 0}")
            if vcs_data:
                logger.info(f"  - VCS 데이터 키: {list(vcs_data.keys())}")
            logger.info(f"  - 테스트 객체 개수: {len(test_objects)}")
            for i, test in enumerate(test_objects[:3]):  # 처음 3개만 로깅
                if hasattr(test, 'name'):
                    logger.info(f"    테스트 {i+1}: {test.name} ({getattr(test, 'test_type', 'unknown')})")
                else:
                    logger.info(f"    테스트 {i+1}: {type(test)} 타입")
            if len(test_objects) > 3:
                logger.info(f"    ... 외 {len(test_objects) - 3}개 테스트")
            
            logger.info(f"  - 시나리오 객체 개수: {len(scenario_objects)}")
            for i, scenario in enumerate(scenario_objects[:3]):  # 처음 3개만 로깅
                if hasattr(scenario, 'scenario_id'):
                    logger.info(f"    시나리오 {i+1}: {scenario.scenario_id} - {getattr(scenario, 'description', 'No description')[:50]}")
                else:
                    logger.info(f"    시나리오 {i+1}: {type(scenario)} 타입")
            if len(scenario_objects) > 3:
                logger.info(f"    ... 외 {len(scenario_objects) - 3}개 시나리오")
            
            self._report_progress(context, 0.3, "LLM Agent 초기화 완료")
            logger.info("LLM Agent를 통한 리뷰 및 개선 분석 요청 준비")
            
            # LLM Agent 입력 데이터 구성
            llm_input = {
                'file_changes': vcs_data,
                'generated_tests': test_objects,
                'test_scenarios': scenario_objects,
                'messages': [],
                'current_step': 'review_and_refine'
            }
            
            logger.info("LLM Agent 입력 데이터 구성 완료:")
            logger.info(f"  - file_changes 타입: {type(vcs_data)}")
            logger.info(f"  - generated_tests 타입: {type(test_objects)}, 개수: {len(test_objects)}")
            logger.info(f"  - test_scenarios 타입: {type(scenario_objects)}, 개수: {len(scenario_objects)}")
            
            self._report_progress(context, 0.5, "리뷰 분석 중...")
            
            # 리뷰 및 개선 분석 - 객체들을 직접 전달
            logger.info("LLM Agent._review_and_refine_step 호출 시작")
            review_result = await llm_agent._review_and_refine_step(llm_input)
            logger.info("LLM Agent._review_and_refine_step 호출 완료")
            
            logger.info("리뷰 결과 분석:")
            logger.info(f"  - 결과 타입: {type(review_result)}")
            logger.info(f"  - 결과 키: {list(review_result.keys()) if isinstance(review_result, dict) else 'Not a dict'}")
            
            # 결과 저장
            review_summary = review_result.get("review_summary", {})
            improvement_suggestions = review_result.get("improvement_suggestions", [])
            quality_metrics = review_result.get("quality_metrics", {})
            
            result.data["review_summary"] = review_summary
            result.data["improvement_suggestions"] = improvement_suggestions
            result.data["quality_metrics"] = quality_metrics
            
            logger.info("리뷰 결과 저장 완료:")
            logger.info(f"  - review_summary: {len(review_summary) if isinstance(review_summary, dict) else type(review_summary)} 항목")
            if isinstance(review_summary, dict):
                logger.info(f"    키: {list(review_summary.keys())}")
            
            logger.info(f"  - improvement_suggestions: {len(improvement_suggestions)}개 제안사항")
            for i, suggestion in enumerate(improvement_suggestions[:3]):
                if isinstance(suggestion, dict):
                    logger.info(f"    제안 {i+1}: {suggestion.get('title', 'No title')}")
                else:
                    logger.info(f"    제안 {i+1}: {str(suggestion)[:100]}")
            if len(improvement_suggestions) > 3:
                logger.info(f"    ... 외 {len(improvement_suggestions) - 3}개 제안사항")
            
            logger.info(f"  - quality_metrics: {len(quality_metrics) if isinstance(quality_metrics, dict) else type(quality_metrics)} 메트릭")
            if isinstance(quality_metrics, dict):
                logger.info(f"    메트릭 키: {list(quality_metrics.keys())}")
                for key, value in list(quality_metrics.items())[:3]:
                    logger.info(f"    {key}: {value}")
            
            self._report_progress(context, 1.0, "리뷰 생성 완료")
            result.status = StageStatus.COMPLETED
            logger.info("=== 리뷰 생성 단계 완료 ===")
            
        except Exception as e:
            logger.error("=== 리뷰 생성 단계 오류 ===")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            result.add_error(f"Review generation failed: {str(e)}")
            result.status = StageStatus.FAILED
        
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            logger.info(f"리뷰 생성 단계 실행 시간: {execution_time:.2f}초")
        
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
        from datetime import datetime
        
        pipeline_start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("=== 파이프라인 오케스트레이터: 파이프라인 실행 시작 ===")
        logger.info("=" * 80)
        
        if stages_to_run is None:
            stages_to_run = self.stage_order
        
        logger.info(f"파이프라인 설정:")
        logger.info(f"  - Pipeline ID: {context.pipeline_id}")
        logger.info(f"  - Repository Path: {context.repo_path}")
        logger.info(f"  - Selected Commits: {len(context.selected_commits)}개")
        for i, commit in enumerate(context.selected_commits[:3]):
            logger.info(f"    커밋 {i+1}: {commit[:8]}...")
        if len(context.selected_commits) > 3:
            logger.info(f"    ... 외 {len(context.selected_commits) - 3}개 커밋")
        
        logger.info(f"  - 실행할 단계: {len(stages_to_run)}개")
        for i, stage in enumerate(stages_to_run):
            logger.info(f"    단계 {i+1}: {stage.value}")
        
        if context.combined_changes:
            logger.info(f"  - 통합 변경사항: {context.combined_changes.get('summary', {}).get('total_files', 0)}개 파일")
            summary = context.combined_changes.get('summary', {})
            logger.info(f"    변경 라인: +{summary.get('total_additions', 0)}/-{summary.get('total_deletions', 0)}")
        
        logger.info(f"  - 프로젝트 정보: {context.project_info if context.project_info else '미설정'}")
        
        results = {}
        successful_stages = 0
        failed_stages = 0
        skipped_stages = 0
        
        with LogContext(f"Pipeline execution: {context.pipeline_id}"):
            logger.info("\n파이프라인 단계 실행 시작...")
            
            for stage_index, stage in enumerate(stages_to_run):
                stage_start_time = datetime.now()
                logger.info("-" * 60)
                logger.info(f"단계 {stage_index + 1}/{len(stages_to_run)}: {stage.value} 시작")
                logger.info("-" * 60)
                
                if stage not in self.stages:
                    logger.warning(f"알 수 없는 단계: {stage}")
                    continue
                
                logger.info(f"단계 인스턴스: {self.stages[stage].__class__.__name__}")
                logger.info(f"현재 컨텍스트 상태:")
                logger.info(f"  - VCS 분석 결과: {'있음' if context.vcs_analysis_result else '없음'}")
                logger.info(f"  - 테스트 전략 결과: {'있음' if context.test_strategy_result else '없음'}")
                logger.info(f"  - 테스트 코드 결과: {'있음' if context.test_code_result else '없음'}")
                logger.info(f"  - 시나리오 결과: {'있음' if context.test_scenario_result else '없음'}")
                logger.info(f"  - 리뷰 결과: {'있음' if context.review_result else '없음'}")
                
                try:
                    # 단계 실행
                    stage_instance = self.stages[stage]
                    logger.info(f"단계 실행 시작: {stage_instance.__class__.__name__}")
                    
                    result = await stage_instance.execute(context)
                    results[stage] = result
                    
                    # 단계 실행 시간 계산
                    stage_execution_time = (datetime.now() - stage_start_time).total_seconds()
                    
                    # 컨텍스트에 결과 저장
                    logger.info("컨텍스트에 결과 저장 중...")
                    self._store_result_in_context(context, stage, result)
                    
                    # 결과 상태 확인 및 로깅
                    logger.info(f"단계 실행 완료:")
                    logger.info(f"  - 상태: {result.status.value}")
                    logger.info(f"  - 실행 시간: {stage_execution_time:.2f}초")
                    logger.info(f"  - 데이터 키 개수: {len(result.data) if result.data else 0}")
                    if result.data:
                        logger.info(f"  - 데이터 키: {list(result.data.keys())}")
                    logger.info(f"  - 오류 개수: {len(result.errors)}")
                    logger.info(f"  - 경고 개수: {len(result.warnings)}")
                    
                    # 단계별 상세 결과 로깅
                    if stage == PipelineStage.VCS_ANALYSIS and result.data:
                        analyses = result.data.get('commit_analyses', [])
                        logger.info(f"    VCS 분석: {len(analyses)}개 커밋 분석")
                    elif stage == PipelineStage.TEST_STRATEGY and result.data:
                        strategy = result.data.get('test_strategy', {})
                        logger.info(f"    테스트 전략: {strategy.get('primary_strategy', 'Unknown')}")
                    elif stage == PipelineStage.TEST_CODE_GENERATION and result.data:
                        tests = result.data.get('generated_tests', [])
                        logger.info(f"    생성된 테스트: {len(tests)}개")
                        if hasattr(result, 'test_cases') and result.test_cases:
                            logger.info(f"    테스트 객체: {len(result.test_cases)}개")
                    elif stage == PipelineStage.TEST_SCENARIO_GENERATION and result.data:
                        scenarios = result.data.get('test_scenarios', [])
                        logger.info(f"    생성된 시나리오: {len(scenarios)}개")
                    elif stage == PipelineStage.REVIEW_GENERATION and result.data:
                        suggestions = result.data.get('improvement_suggestions', [])
                        logger.info(f"    개선 제안: {len(suggestions)}개")
                    
                    # 실패한 경우 중단
                    if result.status == StageStatus.FAILED:
                        failed_stages += 1
                        logger.error(f"단계 {stage.value} 실패, 파이프라인 중단")
                        logger.error(f"실패 원인:")
                        for error in result.errors:
                            logger.error(f"  - {error}")
                        break
                    
                    # 스킵된 경우 로그
                    if result.status == StageStatus.SKIPPED:
                        skipped_stages += 1
                        logger.info(f"단계 {stage.value} 스킵됨")
                        for warning in result.warnings:
                            logger.warning(f"  - {warning}")
                    elif result.status == StageStatus.COMPLETED:
                        successful_stages += 1
                        logger.info(f"단계 {stage.value} 성공적으로 완료")
                    
                except Exception as e:
                    failed_stages += 1
                    stage_execution_time = (datetime.now() - stage_start_time).total_seconds()
                    logger.error(f"단계 {stage.value}에서 치명적 오류 발생:")
                    logger.error(f"  - 오류 메시지: {str(e)}")
                    logger.error(f"  - 오류 타입: {type(e)}")
                    logger.error(f"  - 실행 시간: {stage_execution_time:.2f}초")
                    
                    import traceback
                    logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                    
                    error_result = StageResult(stage=stage, status=StageStatus.FAILED)
                    error_result.add_error(f"Critical error: {str(e)}")
                    error_result.execution_time = stage_execution_time
                    results[stage] = error_result
                    break
        
        # 파이프라인 실행 완료 로깅
        pipeline_execution_time = (datetime.now() - pipeline_start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("=== 파이프라인 오케스트레이터: 파이프라인 실행 완료 ===")
        logger.info("=" * 80)
        logger.info(f"전체 실행 통계:")
        logger.info(f"  - 총 실행 시간: {pipeline_execution_time:.2f}초")
        logger.info(f"  - 성공한 단계: {successful_stages}개")
        logger.info(f"  - 실패한 단계: {failed_stages}개") 
        logger.info(f"  - 스킵된 단계: {skipped_stages}개")
        logger.info(f"  - 전체 단계: {len(stages_to_run)}개")
        
        if failed_stages == 0:
            logger.info("✅ 파이프라인이 성공적으로 완료되었습니다!")
        else:
            logger.error(f"❌ 파이프라인이 {failed_stages}개 단계에서 실패했습니다.")
        
        logger.info("=" * 80)
        
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