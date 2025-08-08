import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

"""
LLM Agent Module - AI 기반 테스트 생성 에이전트

Pipeline 시스템을 사용하여 테스트 생성 단계를 처리하고,
Azure OpenAI Service와 연동하여 테스트 코드를 생성합니다.
"""
import os
import json
from textwrap import dedent
from typing import List, Dict, Any, Optional, TypedDict
from dataclasses import dataclass
import logging
from enum import Enum
import traceback

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
# LangGraph imports removed - now using Pipeline system only
from langfuse import Langfuse
from langfuse import observe

from ai_test_generator.core.vcs_models import FileChange, CommitAnalysis
from ai_test_generator.utils.prompt_loader import PromptLoader
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import get_logger, LogContext
from pathlib import Path

# 로깅 설정
logger = get_logger(__name__)


class TestStrategy(str, Enum):
    """테스트 전략 타입"""
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    PERFORMANCE_TEST = "performance_test"
    SECURITY_TEST = "security_test"


@dataclass
class TestCase:
    """생성된 테스트 케이스"""
    name: str
    description: str
    test_type: TestStrategy
    code: str
    assertions: List[str]
    dependencies: List[str]
    priority: int  # 1-5, 1이 가장 높음


@dataclass
class TestScenario:
    """테스트 시나리오 (엑셀 문서용)"""
    scenario_id: str
    feature: str
    description: str
    preconditions: List[str]
    test_steps: List[Dict[str, str]]
    expected_results: List[str]
    test_data: Optional[Dict[str, Any]] = None
    priority: str = "Medium"
    test_type: str = "Functional"


class AgentState(TypedDict):
    """에이전트 상태 (Pipeline 시스템용으로 단순화)"""
    messages: List[Any]
    file_changes: List[FileChange]
    commit_analysis: Optional[CommitAnalysis]
    test_strategy: Optional[TestStrategy]
    generated_tests: List[TestCase]
    test_scenarios: List[TestScenario]
    error: Optional[str]
    current_step: str


class LLMAgent:
    """LLM 기반 테스트 생성 에이전트"""
    
    def __init__(self, config: Config):
        """
        LLMAgent 초기화
        
        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self.prompt_loader = PromptLoader()
        self._initialize_llm()
        self._initialize_langfuse()
        # LangGraph workflow initialization removed - now using Pipeline system only
    
    def _initialize_llm(self) -> None:
        """
        Azure OpenAI LLM을 초기화하는 메서드입니다.
        이 메서드는 두 개의 LLM 인스턴스를 생성합니다.
        - self.llm: 테스트 생성을 위한 LLM으로, 일관성 있는 결과를 위해 낮은 temperature(0.2)와 높은 max_tokens(4000)를 사용합니다.
        - self.analysis_llm: 분석 작업을 위한 LLM으로, 더 창의적인 결과를 위해 높은 temperature(0.7)와 적당한 max_tokens(2000)를 사용합니다.
        각 LLM 인스턴스는 Azure OpenAI 서비스의 엔드포인트, API 키, 배포 이름, API 버전 등 구성 정보를 사용하여 초기화됩니다.
        초기화가 완료되면 성공적으로 LLM이 초기화되었다는 로그를 남깁니다.
        """
        self.llm = AzureChatOpenAI(
            azure_endpoint=self.config.azure_openai.endpoint,
            api_key=self.config.azure_openai.api_key,
            azure_deployment=self.config.azure_openai.deployment_name_agent,
            api_version=self.config.azure_openai.api_version,
            temperature=0.4,  # 일관된 테스트 생성을 위해 낮은 temperature
            max_tokens=4000,
            timeout=60
        )
        
        # 분석용 LLM
        self.analysis_llm = AzureChatOpenAI(
            azure_endpoint=self.config.azure_openai.endpoint,
            api_key=self.config.azure_openai.api_key,
            azure_deployment=self.config.azure_openai.deployment_name_agent,
            api_version=self.config.azure_openai.api_version,
            temperature=0.7,  # 더 창의적인 분석을 위해 높은 temperature
            max_tokens=2000,
            timeout=60
        )
        
        logger.info("Azure OpenAI LLM initialized successfully")
    
    def _initialize_langfuse(self) -> None:
        """LangFuse 모니터링 초기화"""
        if all([
            os.getenv('LANGFUSE_PUBLIC_KEY'),
            os.getenv('LANGFUSE_SECRET_KEY'),
            os.getenv('LANGFUSE_HOST')
        ]):
            self.langfuse = Langfuse()
            logger.info("LangFuse monitoring initialized")
        else:
            self.langfuse = None
            logger.warning("LangFuse not configured, monitoring disabled")
    
    # LangGraph workflow build method removed - now using Pipeline system only
    
    
    



    
    
    async def _determine_test_strategy_step(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        테스트 전략 결정 단계 - 파이프라인에서 사용하는 메서드
        
        Args:
            input_data: 입력 데이터 (file_changes, messages, current_step 포함)
            
        Returns:
            Dict[str, Any]: 테스트 전략 결과
        """
        try:
            logger.info("=== LLM Agent: 테스트 전략 결정 단계 시작 ===")
            
            # 입력 데이터에서 파일 변경사항 추출
            file_changes = input_data.get('file_changes', [])
            messages = input_data.get('messages', [])
            current_step = input_data.get('current_step', 'determine_strategy')
            
            logger.info("입력 데이터 분석:")
            logger.info(f"  - file_changes 타입: {type(file_changes)}")
            logger.info(f"  - file_changes 개수: {len(file_changes) if hasattr(file_changes, '__len__') else 'N/A'}")
            logger.info(f"  - messages 개수: {len(messages) if messages else 0}")
            logger.info(f"  - current_step: {current_step}")
            
            # 파일 변경사항 상세 분석
            if file_changes:
                logger.info("파일 변경사항 상세:")
                if isinstance(file_changes, dict):
                    logger.info(f"  - 딕셔너리 키: {list(file_changes.keys())}")
                    if 'file_changes' in file_changes:
                        actual_files = file_changes['file_changes']
                        logger.info(f"  - 실제 파일 개수: {len(actual_files) if actual_files else 0}")
                elif isinstance(file_changes, list):
                    logger.info(f"  - 리스트 항목 수: {len(file_changes)}")
                    for i, fc in enumerate(file_changes[:3]):
                        if hasattr(fc, 'file_path'):
                            logger.info(f"    파일 {i+1}: {fc.file_path} ({getattr(fc, 'language', 'unknown')})")
                        elif isinstance(fc, dict):
                            logger.info(f"    파일 {i+1}: {fc.get('file_path', 'unknown')} ({fc.get('language', 'unknown')})")
                    if len(file_changes) > 3:
                        logger.info(f"    ... 외 {len(file_changes) - 3}개 파일")
            
            # AgentState 형태로 변환
            temp_state: AgentState = {
                "messages": messages,
                "file_changes": file_changes,
                "commit_analysis": None,
                "test_strategy": None,
                "generated_tests": [],
                "test_scenarios": [],
                "error": None,
                "current_step": current_step
            }
            
            logger.info("AgentState 생성 완료")
            
            # 실제 LLM을 통한 전략 결정
            try:
                # 파일 변경사항을 구조화된 형태로 변환
                analysis_text = self._format_file_changes_for_llm(file_changes)
                logger.info(f"Formatted analysis data: {analysis_text[:500]}...")
                
                system_prompt, human_prompt = self.prompt_loader.get_prompt(
                    "determine_strategy", 
                    analysis=analysis_text
                )
                logger.info(f"LLM prompts loaded - system: {len(system_prompt)} chars, human: {len(human_prompt)} chars")
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
                
                logger.info(f"=== LLM Request for Test Strategy ===")
                logger.info(f"System prompt:")
                logger.info("=" * 80)
                logger.info(system_prompt)
                logger.info("=" * 80)
                logger.info(f"Human prompt:")
                logger.info("=" * 80)
                logger.info(human_prompt)
                logger.info("=" * 80)
                
                logger.info(f"Calling LLM with {len(messages)} messages...")
                response = await self.llm.ainvoke(messages)
                response_text = response.content.strip()
                logger.info(f"LLM response received: {len(response_text)} characters")
                logger.info(f"Full LLM response content:")
                logger.info("=" * 80)
                logger.info(response_text)
                logger.info("=" * 80)
                
                # JSON 응답 파싱
                import json
                try:
                    strategy_data = json.loads(response_text)
                    primary_strategy = strategy_data.get("primary_strategy", "unit").lower()
                    
                    # 전략 문자열을 enum으로 변환
                    if primary_strategy == "integration":
                        result_state = temp_state.copy()
                        result_state["test_strategy"] = TestStrategy.INTEGRATION_TEST
                        result_state["llm_recommendations"] = strategy_data
                    else:
                        result_state = temp_state.copy()
                        result_state["test_strategy"] = TestStrategy.UNIT_TEST
                        result_state["llm_recommendations"] = strategy_data
                        
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM response as JSON: {response_text}")
                    result_state = temp_state.copy()
                    result_state["test_strategy"] = TestStrategy.UNIT_TEST
                    result_state["llm_recommendations"] = {
                        "reasoning": response_text,
                        "traceback": traceback.format_exc()
                    }
                    
            except Exception as e:
                logger.error(f"Error calling LLM for strategy determination: {e}\n{traceback.format_exc()}")
                result_state = temp_state.copy()
                result_state["test_strategy"] = TestStrategy.UNIT_TEST
                result_state["llm_recommendations"] = {
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            
            # 결과 처리
            logger.info("LLM 응답 결과 처리 중...")
            if result_state.get("error"):
                logger.error(f"LLM 호출 중 오류 발생: {result_state.get('error')}")
                logger.info("기본 전략(unit test)으로 fallback")
                return {
                    "test_strategies": ["unit"],  # 기본값
                    "priority_order": [1],
                    "estimated_effort": {"unit": "medium"},
                    "error": result_state["error"]
                }
            
            # LLM 응답을 기반으로 전략 결정
            primary_strategy = result_state.get("test_strategy", TestStrategy.UNIT_TEST)
            llm_recommendations = result_state.get("llm_recommendations", {})
            
            logger.info(f"LLM 추천 전략: {primary_strategy}")
            logger.info(f"추천사항 키: {list(llm_recommendations.keys()) if isinstance(llm_recommendations, dict) else type(llm_recommendations)}")
            
            strategies = []
            priority_order = []
            
            if primary_strategy == TestStrategy.UNIT_TEST:
                strategies = ["unit"]
                priority_order = [1]
                logger.info("단위 테스트 전략 선택")
            elif primary_strategy == TestStrategy.INTEGRATION_TEST:
                strategies = ["integration"]
                priority_order = [1]
                logger.info("통합 테스트 전략 선택")
            else:
                strategies = ["unit"]
                priority_order = [1]
                logger.info(f"기본 전략 선택 (원래 전략: {primary_strategy})")
            
            result = {
                "test_strategies": strategies,
                "priority_order": priority_order,
                "estimated_effort": {
                    "unit": "medium",
                    "integration": "high"
                },
                "llm_recommendations": llm_recommendations  # LLM의 상세 추천사항 포함
            }
            
            logger.info("=== LLM Agent: 테스트 전략 결정 단계 완료 ===")
            logger.info(f"최종 결정된 전략: {strategies}")
            logger.info(f"우선순위: {priority_order}")
            
            return result
            
        except Exception as e:
            logger.error("=== LLM Agent: 테스트 전략 결정 단계 오류 ===")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            logger.info("기본 전략(unit test)으로 fallback")
            
            return {
                "test_strategies": ["unit"],  # 기본값
                "priority_order": [1],
                "estimated_effort": {"unit": "medium"},
                "error": str(e)
            }
    
    def _format_file_changes_for_llm(self, file_changes) -> str:
        """파일 변경사항을 LLM이 이해할 수 있는 형태로 포맷"""
        if not file_changes:
            return "변경된 파일이 없습니다."
        
        formatted_text = "## 코드 변경 분석 결과\n\n"
        
        # file_changes가 딕셔너리 형태인지 확인
        if isinstance(file_changes, dict):
            # combined_analysis 형태인 경우
            if 'file_changes' in file_changes:
                files = file_changes['file_changes']
                formatted_text += f"**전체 변경 요약:**\n"
                formatted_text += f"- 변경된 파일 수: {file_changes.get('total_files', 0)}개\n"
                formatted_text += f"- 추가된 줄 수: {file_changes.get('total_additions', 0)}줄\n"
                formatted_text += f"- 삭제된 줄 수: {file_changes.get('total_deletions', 0)}줄\n\n"
            else:
                files = file_changes
        elif isinstance(file_changes, list):
            files = file_changes
        else:
            return f"분석 데이터 형태: {type(file_changes)}, 내용: {str(file_changes)[:200]}"
        
        formatted_text += "**파일별 상세 변경사항:**\n"
        
        # files가 딕셔너리인지 리스트인지 확인
        if isinstance(files, dict):
            file_items = list(files.items())[:10]  # 딕셔너리의 경우 items()를 리스트로 변환 후 슬라이싱
        else:
            file_items = files[:10] if isinstance(files, list) else []
        
        for i, file_info in enumerate(file_items, 1):  # 최대 10개 파일만 표시
            # 딕셔너리 items()의 경우 (key, value) 튜플을 처리
            if isinstance(file_info, tuple) and len(file_info) == 2:
                file_key, file_data = file_info
                if isinstance(file_data, dict):
                    file_path = file_data.get('file_path', file_key)
                    change_type = file_data.get('change_type', 'modified')
                    language = file_data.get('language', 'unknown')
                    additions = file_data.get('additions', 0)
                    deletions = file_data.get('deletions', 0)
                    
                    formatted_text += f"\n{i}. **파일:** `{file_path}`\n"
                    formatted_text += f"   - 변경 타입: {change_type}\n"
                    formatted_text += f"   - 언어: {language}\n"
                    formatted_text += f"   - 추가: +{additions}줄, 삭제: -{deletions}줄\n"
                    
                    if 'functions_changed' in file_data and file_data['functions_changed']:
                        formatted_text += f"   - 변경된 함수: {', '.join(file_data['functions_changed'])}\n"
                    
                    if 'diff_content' in file_data and file_data['diff_content']:
                        diff_preview = file_data['diff_content'][:200]
                        formatted_text += f"   - 변경 내용 미리보기: {diff_preview}...\n"
                else:
                    formatted_text += f"\n{i}. **파일:** `{file_key}` - {str(file_data)[:100]}\n"
            elif isinstance(file_info, dict):
                file_path = file_info.get('file_path', 'Unknown')
                change_type = file_info.get('change_type', 'modified')
                language = file_info.get('language', 'unknown')
                additions = file_info.get('additions', 0)
                deletions = file_info.get('deletions', 0)
                
                formatted_text += f"\n{i}. **파일:** `{file_path}`\n"
                formatted_text += f"   - 변경 타입: {change_type}\n"
                formatted_text += f"   - 언어: {language}\n"
                formatted_text += f"   - 추가: +{additions}줄, 삭제: -{deletions}줄\n"
                
                if 'functions_changed' in file_info and file_info['functions_changed']:
                    formatted_text += f"   - 변경된 함수: {', '.join(file_info['functions_changed'])}\n"
                
                if 'diff_content' in file_info and file_info['diff_content']:
                    diff_preview = file_info['diff_content'][:200]
                    formatted_text += f"   - 변경 내용 미리보기: {diff_preview}...\n"
            else:
                formatted_text += f"\n{i}. {str(file_info)}\n"
        
        total_files = len(files) if hasattr(files, '__len__') else 0
        if total_files > 10:
            formatted_text += f"\n... 총 {total_files}개 파일 중 10개만 표시됨\n"
        
        return formatted_text
    
    async def _enrich_file_change_with_content(self, file_change, repo_path: Optional[str]):
        """
        파일 변경사항에 전체 파일 내용을 추가합니다.
        
        Args:
            file_change: 파일 변경사항 객체
            repo_path: Git 저장소 경로
            
        Returns:
            향상된 파일 변경사항 객체 (full_content 추가)
        """
        if not repo_path:
            logger.warning("No repo_path provided, cannot enrich file content")
            return file_change
            
        try:
            from ai_test_generator.core.git_analyzer import GitAnalyzer
            git_analyzer = GitAnalyzer(repo_path)
            
            # 파일 경로 가져오기
            if hasattr(file_change, 'file_path'):
                file_path = file_change.file_path
            elif isinstance(file_change, dict):
                file_path = file_change.get('file_path', '')
            else:
                logger.warning(f"Cannot get file_path from file_change: {type(file_change)}")
                return file_change
            
            # 현재 워킹 디렉토리에서 파일 내용 가져오기 (최신 상태)
            full_content = git_analyzer.get_current_file_content(file_path)
            
            if full_content:
                # 파일 변경사항에 전체 내용 추가
                if hasattr(file_change, '__dict__'):
                    # 객체인 경우
                    file_change.full_content = full_content
                elif isinstance(file_change, dict):
                    # 딕셔너리인 경우
                    file_change['full_content'] = full_content
                
                logger.info(f"Added full content to {file_path}: {len(full_content)} characters")
            else:
                logger.warning(f"Could not get content for file: {file_path}")
                
        except Exception as e:
            logger.error(f"Error enriching file change with content: {e}")
            
        return file_change
    
    async def _generate_tests_step(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        테스트 코드 생성 단계 - 파이프라인에서 사용하는 메서드
        
        Args:
            input_data: 입력 데이터 (test_strategy, file_changes, messages 등 포함)
            
        Returns:
            Dict[str, Any]: 생성된 테스트 결과
        """
        try:
            logger.info("=== LLM Agent: 테스트 코드 생성 단계 시작 ===")
            
            # 입력 데이터 추출
            test_strategy = input_data.get('test_strategy', 'unit')
            file_changes = input_data.get('file_changes', [])
            messages = input_data.get('messages', [])
            current_step = input_data.get('current_step', 'generate_tests')
            repo_path = input_data.get('repo_path')  # 저장소 경로
            
            logger.info("입력 데이터 분석:")
            logger.info(f"  - test_strategy: {test_strategy}")
            logger.info(f"  - file_changes 타입: {type(file_changes)}")
            logger.info(f"  - file_changes 개수: {len(file_changes) if hasattr(file_changes, '__len__') else 'N/A'}")
            logger.info(f"  - messages 개수: {len(messages) if messages else 0}")
            logger.info(f"  - current_step: {current_step}")
            logger.info(f"  - repo_path: {repo_path}")
            
            # 파일 변경사항 타입 분석 및 처리
            
            # 파일 변경사항을 FileChange 객체로 변환 (필요한 경우)
            logger.info(f"Initial file_changes type: {type(file_changes)}")
            
            # combined_changes의 경우 딕셔너리로 전달됨
            if isinstance(file_changes, dict) and 'files_changed' in file_changes:
                logger.info(f"Extracting files_changed from dict, count: {len(file_changes['files_changed'])}")
                file_changes = file_changes['files_changed']
            
            if isinstance(file_changes, list):
                if file_changes and isinstance(file_changes[0], dict):
                    from ai_test_generator.core.vcs_models import FileChange
                    
                    # filename 필드를 file_path로 매핑
                    converted_changes = []
                    for fc in file_changes:
                        # filename 또는 file_path 사용
                        file_path = fc.get('filename', fc.get('file_path', ''))
                        
                        # status를 change_type으로 매핑
                        status_map = {
                            'A': 'added',
                            'M': 'modified',
                            'D': 'deleted',
                            'R': 'renamed'
                        }
                        change_type = status_map.get(fc.get('status', 'M'), fc.get('change_type', 'modified'))
                        
                        # content_diff 필드 확인
                        diff_content = fc.get('content_diff', fc.get('diff_content', ''))
                        
                        # 언어 감지
                        language = fc.get('language', '')
                        if not language and file_path:
                            # GitAnalyzer의 언어 감지 로직 사용
                            import os
                            SUPPORTED_LANGUAGES = {
                                '.py': 'python',
                                '.java': 'java',
                                '.js': 'javascript',
                                '.ts': 'typescript',
                                '.cpp': 'cpp',
                                '.c': 'c',
                                '.cs': 'csharp',
                                '.go': 'go',
                                '.rs': 'rust',
                                '.rb': 'ruby',
                                '.php': 'php',
                                '.swift': 'swift',
                                '.kt': 'kotlin',
                                '.scala': 'scala',
                            }
                            ext = os.path.splitext(file_path)[1].lower()
                            language = SUPPORTED_LANGUAGES.get(ext, '')
                        
                        converted_changes.append(FileChange(
                            file_path=file_path,
                            change_type=change_type,
                            additions=fc.get('additions', 0),
                            deletions=fc.get('deletions', 0),
                            language=language,
                            functions_changed=fc.get('functions_changed', []),
                            diff_content=diff_content
                        ))
                    
                    file_changes = converted_changes
                    logger.info(f"Converted {len(file_changes)} file changes to FileChange objects")
                elif file_changes and isinstance(file_changes[0], str):
                    from ai_test_generator.core.vcs_models import FileChange
                    from typing import Optional
                    import os
                    
                    # GitAnalyzer의 언어 감지 로직 사용
                    SUPPORTED_LANGUAGES = {
                        '.py': 'python',
                        '.java': 'java',
                        '.js': 'javascript',
                        '.ts': 'typescript',
                        '.cpp': 'cpp',
                        '.c': 'c',
                        '.cs': 'csharp',
                        '.go': 'go',
                        '.rs': 'rust',
                        '.rb': 'ruby',
                        '.php': 'php',
                        '.swift': 'swift',
                        '.kt': 'kotlin',
                        '.scala': 'scala',
                    }
                    
                    def detect_language(file_path: str) -> Optional[str]:
                        ext = os.path.splitext(file_path)[1].lower()
                        return SUPPORTED_LANGUAGES.get(ext)
                    
                    file_changes = [
                        FileChange(
                            file_path=fp,
                            change_type='modified',
                            additions=0,
                            deletions=0,
                            language=detect_language(fp),
                            functions_changed=[],
                            diff_content=''
                        ) for fp in file_changes
                    ]
            
            # AgentState 형태로 변환
            temp_state: AgentState = {
                "messages": messages,
                "file_changes": file_changes,
                "commit_analysis": None,
                "test_strategy": None,
                "generated_tests": [],
                "test_scenarios": [],
                "error": None,
                "current_step": current_step
            }
            
            # 디버깅: file_changes 타입 확인
            logger.info(f"=== Test Code Generation Debug ===")
            logger.info(f"test_strategy: {test_strategy}")
            logger.info(f"file_changes type: {type(file_changes)}")
            logger.info(f"file_changes length: {len(file_changes) if hasattr(file_changes, '__len__') else 'N/A'}")
            if file_changes and hasattr(file_changes, '__iter__'):
                try:
                    if isinstance(file_changes, dict):
                        logger.info(f"file_changes keys: {list(file_changes.keys())}")
                    elif len(file_changes) > 0:
                        logger.info(f"first file_change type: {type(file_changes[0])}")
                        logger.info(f"first file_change content: {str(file_changes[0])[:200]}...")
                except:
                    logger.info("Error accessing file_changes details")
            
            # 전략에 따라 적절한 테스트 생성 메서드 호출
            generated_tests = []
            
            logger.info(f"=== Starting test generation for strategy: {test_strategy} ===")
            print(f"\n{'='*60}")
            print(f"TEST GENERATION START - Strategy: {test_strategy}")
            print(f"{'='*60}")
            
            if test_strategy == 'unit':
                # 모든 파일 변경사항을 한 번에 처리
                logger.info(f"Processing {len(file_changes)} file changes for unit tests")
                print(f"Number of file changes to process: {len(file_changes)}")
                
                # 삭제되지 않은 파일들만 필터링하고 전체 내용 추가
                valid_file_changes = []
                for idx, file_change in enumerate(file_changes):
                    if hasattr(file_change, 'language') and hasattr(file_change, 'change_type'):
                        if file_change.language and file_change.change_type != "deleted":
                            logger.info(f"Enriching file {idx+1}/{len(file_changes)}: {getattr(file_change, 'file_path', 'unknown')}")
                            enhanced_file_change = await self._enrich_file_change_with_content(
                                file_change, repo_path
                            )
                            valid_file_changes.append(enhanced_file_change)
                
                logger.info(f"Valid files to process: {len(valid_file_changes)}")
                print(f"\nValid files for test generation: {len(valid_file_changes)}")
                
                if valid_file_changes:
                    # 모든 파일을 한 번에 처리
                    tests = await self._generate_tests_for_multiple_files(
                        valid_file_changes,
                        TestStrategy.UNIT_TEST
                    )
                    generated_tests.extend(tests)
                    print(f"\nTotal tests generated: {len(tests)}")
            elif test_strategy == 'integration':
                # 통합 테스트도 모든 파일을 한 번에 처리
                logger.info(f"Processing {len(file_changes)} file changes for integration tests")
                print(f"Number of file changes to process: {len(file_changes)}")
                
                # 삭제되지 않은 파일들만 필터링하고 전체 내용 추가
                valid_file_changes = []
                for idx, file_change in enumerate(file_changes):
                    if hasattr(file_change, 'language') and hasattr(file_change, 'change_type'):
                        if file_change.language and file_change.change_type != "deleted":
                            logger.info(f"Enriching file {idx+1}/{len(file_changes)}: {getattr(file_change, 'file_path', 'unknown')}")
                            enhanced_file_change = await self._enrich_file_change_with_content(
                                file_change, repo_path
                            )
                            valid_file_changes.append(enhanced_file_change)
                
                if valid_file_changes:
                    tests = await self._generate_tests_for_multiple_files(
                        valid_file_changes,
                        TestStrategy.INTEGRATION_TEST
                    )
                    generated_tests.extend(tests)
                    print(f"\nTotal tests generated: {len(tests)}")
            else:
                # 기본값으로 단위 테스트 생성
                for file_change in file_changes:
                    if hasattr(file_change, 'language') and hasattr(file_change, 'change_type'):
                        if file_change.language and file_change.change_type != "deleted":
                            enhanced_file_change = await self._enrich_file_change_with_content(
                                file_change, repo_path
                            )
                            tests = await self._generate_tests_for_file(
                                enhanced_file_change,
                                TestStrategy.UNIT_TEST
                            )
                            generated_tests.extend(tests)
            
            # TestCase 객체를 그대로 반환
            logger.info("=== 테스트 생성 결과 분석 ===")
            logger.info(f"총 생성된 테스트 개수: {len(generated_tests)}")
            
            # 테스트별 상세 정보 로깅
            for i, test in enumerate(generated_tests):
                logger.info(f"테스트 {i+1}:")
                logger.info(f"  - 타입: {type(test)}")
                logger.info(f"  - name 속성 존재: {hasattr(test, 'name')}")
                if hasattr(test, 'name'):
                    logger.info(f"  - 이름: {test.name}")
                if hasattr(test, 'test_type'):
                    logger.info(f"  - 테스트 타입: {test.test_type}")
                if hasattr(test, 'code'):
                    code_length = len(test.code) if test.code else 0
                    logger.info(f"  - 코드 길이: {code_length}자")
                    if test.code:
                        logger.info(f"  - 코드 미리보기: {test.code[:100]}...")
            
            # 전략별 통계
            if generated_tests:
                strategy_counts = {}
                for test in generated_tests:
                    if hasattr(test, 'test_type'):
                        test_type = str(test.test_type)
                        strategy_counts[test_type] = strategy_counts.get(test_type, 0) + 1
                
                logger.info("테스트 타입별 통계:")
                for test_type, count in strategy_counts.items():
                    logger.info(f"  - {test_type}: {count}개")
            
            result = {
                "tests": generated_tests,  # TestCase 객체 리스트를 그대로 반환
                "test_count": len(generated_tests),
                "strategy": test_strategy
            }
            
            logger.info("=== LLM Agent: 테스트 코드 생성 단계 완료 ===")
            logger.info(f"최종 결과: {len(generated_tests)}개 테스트, 전략: {test_strategy}")
            
            return result
            
        except Exception as e:
            logger.error("=== LLM Agent: 테스트 코드 생성 단계 오류 ===")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            
            return {
                "tests": [],
                "test_count": 0,
                "strategy": input_data.get('test_strategy', 'unit'),
                "error": f"{e}\n{traceback.format_exc()}"
            }
    
    async def _generate_scenarios_step(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        테스트 시나리오 생성 단계 - 파이프라인에서 사용하는 메서드
        
        Args:
            input_data: 입력 데이터 (file_changes, generated_tests, messages 등 포함)
            
        Returns:
            Dict[str, Any]: 생성된 시나리오 결과
        """
        try:
            logger.info("=== LLM Agent: 시나리오 생성 단계 시작 ===")
            
            # 입력 데이터 추출
            file_changes = input_data.get('file_changes', {})
            generated_tests = input_data.get('generated_tests', [])
            messages = input_data.get('messages', [])
            current_step = input_data.get('current_step', 'generate_scenarios')
            
            logger.info(f"입력 데이터 분석:")
            logger.info(f"  - file_changes 타입: {type(file_changes)}")
            logger.info(f"  - generated_tests 개수: {len(generated_tests) if generated_tests else 0}")
            logger.info(f"  - messages 개수: {len(messages) if messages else 0}")
            logger.info(f"  - current_step: {current_step}")
            
            # 파일 변경사항을 FileChange 객체로 변환 (VCS 결과에서 오는 경우)
            if isinstance(file_changes, dict):
                file_changes_list = file_changes.get('combined_analysis', []) or file_changes.get('commit_analyses', [])
                logger.info(f"파일 변경사항을 dict에서 추출: {len(file_changes_list)}개 파일")
            else:
                file_changes_list = file_changes
                logger.info(f"파일 변경사항을 직접 사용: {len(file_changes_list) if file_changes_list else 0}개 파일")
            
            # FileChange 객체로 변환
            if file_changes_list and isinstance(file_changes_list[0], dict):
                logger.info("파일 변경사항을 FileChange 객체로 변환 중...")
                from ai_test_generator.core.vcs_models import FileChange
                file_changes_objects = [
                    FileChange(
                        file_path=fc.get('file_path', ''),
                        change_type=fc.get('change_type', 'modified'),
                        additions=fc.get('additions', 0),
                        deletions=fc.get('deletions', 0),
                        language=fc.get('language', ''),
                        functions_changed=fc.get('functions_changed', []),
                        diff_content=fc.get('diff_content', '')
                    ) for fc in file_changes_list
                ]
                logger.info(f"FileChange 객체로 변환 완료: {len(file_changes_objects)}개")
            else:
                file_changes_objects = file_changes_list or []
                logger.info(f"FileChange 객체 그대로 사용: {len(file_changes_objects)}개")
            
            # 생성된 테스트 처리 - 이미 TestCase 객체인 경우와 dict인 경우 모두 처리
            test_cases = []
            logger.info("생성된 테스트를 TestCase 객체로 변환 중...")
            for i, test in enumerate(generated_tests):
                if isinstance(test, TestCase):
                    # 이미 TestCase 객체인 경우 그대로 사용
                    test_cases.append(test)
                    logger.info(f"  테스트 {i+1}: TestCase 객체 그대로 사용 - {test.name}")
                elif isinstance(test, dict):
                    # dict인 경우 TestCase 객체로 변환
                    test_case = TestCase(
                        name=test.get('name', ''),
                        description=test.get('description', ''),
                        test_type=TestStrategy(test.get('test_type', 'unit_test')),
                        code=test.get('code', ''),
                        assertions=test.get('assertions', []),
                        dependencies=test.get('dependencies', []),
                        priority=test.get('priority', 3)
                    )
                    test_cases.append(test_case)
                    logger.info(f"  테스트 {i+1}: dict에서 TestCase로 변환 - {test_case.name}")
                else:
                    # 기타 경우는 그대로 추가
                    test_cases.append(test)
                    logger.info(f"  테스트 {i+1}: 기타 타입으로 그대로 추가 - {type(test)}")
            
            logger.info(f"TestCase 변환 완료: 총 {len(test_cases)}개 테스트")
            
            # AgentState 형태로 변환
            temp_state: AgentState = {
                "messages": messages,
                "file_changes": file_changes_objects,
                "commit_analysis": None,
                "test_strategy": None,
                "generated_tests": test_cases,
                "test_scenarios": [],
                "error": None,
                "current_step": current_step
            }
            
            logger.info("AgentState 구성 완료:")
            logger.info(f"  - file_changes: {len(file_changes_objects)}개")
            logger.info(f"  - generated_tests: {len(test_cases)}개") 
            logger.info(f"  - current_step: {current_step}")
            
            # 실제 시나리오 생성 로직 구현
            logger.info("=== LLM을 통한 시나리오 생성 시작 ===")
            
            # 시나리오 생성을 위한 데이터 준비
            scenarios_data = []
            
            if test_cases and len(test_cases) > 0:
                logger.info("테스트 케이스를 기반으로 시나리오 생성 중...")
                
                try:
                    # 테스트 케이스들을 요약하여 LLM에 전달할 데이터 구성
                    test_summary = self._summarize_tests_for_scenarios(test_cases)
                    file_summary = self._summarize_file_changes_for_scenarios(file_changes_objects)
                    
                    logger.info(f"테스트 요약 길이: {len(test_summary)}자")
                    logger.info(f"파일 요약 길이: {len(file_summary)}자")
                    
                    # 시나리오 생성용 프롬프트 로드 (test_scenarios.yaml 사용)
                    system_prompt, human_prompt = self.prompt_loader.get_prompt(
                        "test_scenarios",
                        changes=file_summary,
                        tests=test_summary
                    )
                    
                    logger.info("=== 시나리오 생성 LLM 요청 ===")
                    logger.info(f"System prompt:")
                    logger.info("=" * 80)
                    logger.info(system_prompt)
                    logger.info("=" * 80)
                    logger.info(f"Human prompt:")
                    logger.info("=" * 80)
                    logger.info(human_prompt)
                    logger.info("=" * 80)
                    
                    # LLM 호출
                    logger.info("LLM 시나리오 생성 요청 시작...")
                    response = await self.llm.ainvoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=human_prompt)
                    ])
                    
                    logger.info("=== LLM 시나리오 생성 응답 ===")
                    logger.info(f"응답 길이: {len(response.content)}자")
                    logger.info(f"응답 내용:")
                    logger.info("=" * 80)
                    logger.info(response.content)
                    logger.info("=" * 80)
                    
                    # 응답 파싱 시도
                    parsed_scenarios = self._parse_scenario_response(response.content)
                    logger.info(f"파싱된 시나리오 수: {len(parsed_scenarios)}")
                    
                    for i, scenario in enumerate(parsed_scenarios):
                        logger.info(f"시나리오 {i+1}: {scenario.get('scenario_id', 'Unknown ID')}")
                        logger.info(f"  - 기능: {scenario.get('feature', 'Unknown')}")
                        logger.info(f"  - 설명: {scenario.get('description', 'No description')[:100]}...")
                    
                    scenarios_data.extend(parsed_scenarios)
                    
                except Exception as e:
                    logger.error(f"LLM 시나리오 생성 중 오류: {e}")
                    logger.error(f"오류 타입: {type(e)}")
                    import traceback
                    logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
                    
                    # 오류 시 기본 시나리오 생성
                    logger.info("기본 시나리오 생성으로 fallback")
                    scenarios_data = self._generate_default_scenarios(test_cases, file_changes_objects)
                    
            else:
                logger.warning("테스트 케이스가 없어 시나리오 생성 불가")
                logger.info("기본 시나리오만 생성합니다.")
                scenarios_data = self._generate_default_scenarios([], file_changes_objects)
            
            result_state = temp_state.copy()
            # TestScenario 객체들을 생성 (시나리오 데이터가 있는 경우)
            scenario_objects = []
            for scenario_data in scenarios_data:
                try:
                    scenario_obj = TestScenario(
                        scenario_id=scenario_data.get('scenario_id', f'scenario_{len(scenario_objects)+1}'),
                        feature=scenario_data.get('feature', 'Unknown Feature'),
                        description=scenario_data.get('description', 'No description'),
                        preconditions=scenario_data.get('preconditions', []),
                        test_steps=scenario_data.get('test_steps', []),
                        expected_results=scenario_data.get('expected_results', []),
                        test_data=scenario_data.get('test_data'),
                        priority=scenario_data.get('priority', 'Medium'),
                        test_type=scenario_data.get('test_type', 'Functional')
                    )
                    scenario_objects.append(scenario_obj)
                    logger.info(f"TestScenario 객체 생성: {scenario_obj.scenario_id}")
                except Exception as e:
                    logger.error(f"TestScenario 객체 생성 실패: {e}")
            
            result_state["test_scenarios"] = scenario_objects
            
            # 결과를 딕셔너리로 변환
            scenarios_data = []
            for scenario in result_state.get("test_scenarios", []):
                scenario_dict = {
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
                scenarios_data.append(scenario_dict)
            
            logger.info(f"시나리오 생성 결과: {len(scenarios_data)}개 시나리오")
            logger.info("=== LLM Agent: 시나리오 생성 단계 완료 ===")
            
            return {
                "test_scenarios": scenarios_data,
                "scenario_count": len(scenarios_data)
            }
            
        except Exception as e:
            logger.error(f"=== LLM Agent: 시나리오 생성 단계 오류 ===")
            logger.error(f"오류 메시지: {e}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            return {
                "test_scenarios": [],
                "scenario_count": 0,
                "error": str(e)
            }
    
    async def _review_and_refine_step(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        리뷰 및 개선 단계 - 파이프라인에서 사용하는 메서드
        
        Args:
            input_data: 입력 데이터 (file_changes, generated_tests, test_scenarios 등 포함)
            
        Returns:
            Dict[str, Any]: 리뷰 결과
        """
        try:
            logger.info("=== LLM Agent: 리뷰 및 개선 단계 시작 ===")
            
            # 입력 데이터 추출
            file_changes = input_data.get('file_changes', {})
            generated_tests = input_data.get('generated_tests', [])
            test_scenarios = input_data.get('test_scenarios', [])
            messages = input_data.get('messages', [])
            current_step = input_data.get('current_step', 'review_and_refine')
            
            logger.info("입력 데이터 분석:")
            logger.info(f"  - file_changes 타입: {type(file_changes)}")
            logger.info(f"  - generated_tests 개수: {len(generated_tests) if generated_tests else 0}")
            logger.info(f"  - test_scenarios 개수: {len(test_scenarios) if test_scenarios else 0}")
            logger.info(f"  - messages 개수: {len(messages) if messages else 0}")
            logger.info(f"  - current_step: {current_step}")
            
            # 파일 변경사항 분석
            if isinstance(file_changes, dict):
                logger.info(f"파일 변경사항 키: {list(file_changes.keys())}")
            elif hasattr(file_changes, '__len__'):
                logger.info(f"파일 변경사항 개수: {len(file_changes)}")
            
            # 파일 변경사항을 FileChange 객체로 변환
            if isinstance(file_changes, dict):
                file_changes_list = file_changes.get('combined_analysis', []) or file_changes.get('commit_analyses', [])
            else:
                file_changes_list = file_changes
            
            if file_changes_list and isinstance(file_changes_list[0], dict):
                from ai_test_generator.core.vcs_models import FileChange
                file_changes_objects = [
                    FileChange(
                        file_path=fc.get('file_path', ''),
                        change_type=fc.get('change_type', 'modified'),
                        additions=fc.get('additions', 0),
                        deletions=fc.get('deletions', 0),
                        language=fc.get('language', ''),
                        functions_changed=fc.get('functions_changed', []),
                        diff_content=fc.get('diff_content', '')
                    ) for fc in file_changes_list
                ]
            else:
                file_changes_objects = file_changes_list or []
            
            # 생성된 테스트 처리 - 이미 TestCase 객체인 경우와 dict인 경우 모두 처리
            test_cases = []
            for test in generated_tests:
                if isinstance(test, TestCase):
                    # 이미 TestCase 객체인 경우 그대로 사용
                    test_cases.append(test)
                elif isinstance(test, dict):
                    # dict인 경우 TestCase 객체로 변환
                    test_case = TestCase(
                        name=test.get('name', ''),
                        description=test.get('description', ''),
                        test_type=TestStrategy(test.get('test_type', 'unit_test')),
                        code=test.get('code', ''),
                        assertions=test.get('assertions', []),
                        dependencies=test.get('dependencies', []),
                        priority=test.get('priority', 3)
                    )
                    test_cases.append(test_case)
                else:
                    # 기타 경우는 그대로 추가
                    test_cases.append(test)
            
            # 시나리오 처리 - 이미 TestScenario 객체인 경우와 dict인 경우 모두 처리
            scenario_objects = []
            for scenario in test_scenarios:
                if isinstance(scenario, TestScenario):
                    # 이미 TestScenario 객체인 경우 그대로 사용
                    scenario_objects.append(scenario)
                elif isinstance(scenario, dict):
                    # dict인 경우 TestScenario 객체로 변환
                    scenario_obj = TestScenario(
                        scenario_id=scenario.get('scenario_id', ''),
                        feature=scenario.get('feature', ''),
                        description=scenario.get('description', ''),
                        preconditions=scenario.get('preconditions', []),
                        test_steps=scenario.get('test_steps', []),
                        expected_results=scenario.get('expected_results', []),
                        test_data=scenario.get('test_data'),
                        priority=scenario.get('priority', 'Medium'),
                        test_type=scenario.get('test_type', 'Functional')
                    )
                    scenario_objects.append(scenario_obj)
                else:
                    # 기타 경우는 그대로 추가
                    scenario_objects.append(scenario)
            
            # AgentState 형태로 변환
            temp_state: AgentState = {
                "messages": messages,
                "file_changes": file_changes_objects,
                "commit_analysis": None,
                "test_strategy": None,
                "generated_tests": test_cases,
                "test_scenarios": scenario_objects,
                "error": None,
                "current_step": current_step
            }
            
            logger.info("=== 데이터 변환 완료 ===")
            logger.info(f"변환된 데이터:")
            logger.info(f"  - FileChange 객체: {len(file_changes_objects)}개")
            logger.info(f"  - TestCase 객체: {len(test_cases)}개")
            logger.info(f"  - TestScenario 객체: {len(scenario_objects)}개")
            
            # 실제 LLM을 사용한 리뷰 및 개선 로직 구현
            logger.info("=== 실제 LLM을 통한 리뷰 분석 시작 ===")
            
            # 테스트와 시나리오 데이터 요약
            tests_summary = self._summarize_tests_for_review(test_cases)
            scenarios_summary = self._summarize_scenarios_for_review(scenario_objects)
            
            logger.info(f"테스트 요약 완료: {len(tests_summary)} 글자")
            logger.info(f"시나리오 요약 완료: {len(scenarios_summary)} 글자")
            
            # 프롬프트 로드
            logger.info("review_refine.yaml 프롬프트 로드 중...")
            try:
                system_prompt, human_prompt = self.prompt_loader.get_prompt(
                    "review_refine",
                    tests=tests_summary,
                    scenarios=scenarios_summary
                )
                logger.info("프롬프트 로드 성공")
                logger.info(f"시스템 프롬프트 길이: {len(system_prompt)}")
                logger.info(f"휴먼 프롬프트 길이: {len(human_prompt)}")
            except Exception as e:
                logger.error(f"프롬프트 로드 실패: {e}")
                raise
            
            # LLM 호출
            logger.info("LLM 호출 시작 - 리뷰 분석 요청")
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
                
                response = await self.llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ])
                
                logger.info("LLM 호출 성공")
                logger.info(f"LLM 응답 길이: {len(response.content)}")
                
                # 응답 파싱
                review_result = self._parse_review_response(response.content)
                logger.info("리뷰 응답 파싱 완료")
                
            except Exception as e:
                logger.error(f"LLM 호출 실패: {e}")
                # 폴백 처리
                review_result = self._generate_default_review(test_cases, scenario_objects)
                logger.info("기본 리뷰 결과로 폴백 처리 완료")
            
            # 기본 메트릭 추가
            total_tests = len(test_cases)
            total_scenarios = len(scenario_objects)
            total_files = len(file_changes_objects)
            
            # LLM 결과와 기본 메트릭 결합
            result = {
                "review_summary": {
                    **review_result.get("review_summary", {}),
                    "total_tests": total_tests,
                    "total_scenarios": total_scenarios,
                    "total_files": total_files,
                },
                "improvement_suggestions": review_result.get("improvement_suggestions", []),
                "quality_metrics": {
                    **review_result.get("quality_metrics", {}),
                    "test_to_file_ratio": f"{total_tests}/{total_files}" if total_files > 0 else "0/0"
                }
            }
            
            logger.info("=== LLM Agent: 리뷰 및 개선 단계 완료 ===")
            logger.info(f"리뷰 완료: {total_tests}개 테스트, {total_scenarios}개 시나리오")
            
            # 리뷰 결과 로깅
            if "review_summary" in result and "review_content" in result["review_summary"]:
                logger.info(f"리뷰 내용: {result['review_summary']['review_content'][:100]}...")
            
            suggestions_count = len(result.get("improvement_suggestions", []))
            logger.info(f"개선사항: {suggestions_count}개 제안")
            
            return result
            
        except Exception as e:
            logger.error("=== LLM Agent: 리뷰 및 개선 단계 오류 ===")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            
            return {
                "review_summary": {"error": str(e)},
                "improvement_suggestions": [],
                "quality_metrics": {},
                "error": str(e)
            }
    
    
    async def _generate_tests_for_file(
        self,
        file_change: FileChange,
        test_type: TestStrategy,
    ) -> List[TestCase]:
        """
        특정 파일의 변경된 함수들에 대해 지정된 테스트 전략에 따라 테스트 케이스를 비동기적으로 생성합니다.
        Args:
            file_change (FileChange): 테스트를 생성할 파일의 변경 정보(경로, 변경 함수 목록, diff 등)를 담고 있는 객체입니다.
            test_type (TestStrategy): 생성할 테스트의 유형(예: 단위 테스트, 통합 테스트 등)을 지정합니다.
        Returns:
            List[TestCase]: 생성된 테스트 케이스(TestCase) 객체들의 리스트를 반환합니다. 
                            테스트 생성에 실패하거나 파싱에 실패한 경우 해당 함수에 대한 테스트는 리스트에 포함되지 않습니다.
        상세 설명:
            - 파일의 변경된 함수들(최대 5개)에 대해 반복적으로 테스트 생성 프롬프트를 구성합니다.
            - 필요 시 RAG 컨텍스트를 프롬프트에 포함시켜 테스트 생성의 품질을 높입니다.
            - LLM(대형 언어 모델)을 비동기적으로 호출하여 각 함수별 테스트 코드를 생성합니다.
            - LLM의 응답을 파싱하여 TestCase 객체로 변환하고, 유효한 경우 리스트에 추가합니다.
            - 예외 발생 시 에러 로그를 남기고, 이미 생성된 테스트 리스트를 반환합니다.
        """
        tests = []
        
        try:
            logger.info("=== LLM Agent: 단일 파일 테스트 생성 시작 ===")
            logger.info(f"파일: {file_change.file_path}")
            logger.info(f"테스트 타입: {test_type}")
            logger.info(f"언어: {file_change.language}")
            logger.info(f"변경 타입: {file_change.change_type}")
            logger.info(f"추가/삭제 라인: +{file_change.additions}/-{file_change.deletions}")
            logger.info(f"변경된 함수: {file_change.functions_changed}")
            logger.info(f"전체 내용 보유: {hasattr(file_change, 'full_content') and file_change.full_content is not None}")
            
            if hasattr(file_change, 'full_content') and file_change.full_content:
                logger.info(f"전체 내용 길이: {len(file_change.full_content)}자")
            elif file_change.diff_content:
                logger.info(f"diff 내용 길이: {len(file_change.diff_content)}자")
            else:
                logger.warning("파일 내용이나 diff 정보가 없음")
            
            # 언어별 특화 텍스트 준비
            language_specific = ""
            if file_change.language == "python":
                language_specific = "Use pytest framework with proper fixtures and assertions."
            elif file_change.language == "java":
                language_specific = "Use JUnit 5 with appropriate annotations and assertions."
            elif file_change.language == "javascript":
                language_specific = "Use Jest framework with proper describe/it blocks."
            
            # functions_changed가 비어있는 경우 전체 파일에 대해 테스트 생성
            if not file_change.functions_changed:
                logger.info("No specific functions found, generating tests for entire file")
                function_targets = [f"entire_{file_change.file_path.split('/')[-1]}"]
            else:
                function_targets = file_change.functions_changed[:5]  # 최대 5개
            
            # 변경된 함수별로 테스트 생성
            for function_name in function_targets:
                logger.info(f"Generating test for function: {function_name}")
                
                # full_content가 있으면 diff_content 대신 사용
                content_for_prompt = ""
                if hasattr(file_change, 'full_content') and file_change.full_content:
                    content_for_prompt = file_change.full_content[:3000]  # 처음 3000자
                    logger.info(f"Using full_content (first 200 chars): {content_for_prompt[:200]}...")
                else:
                    content_for_prompt = file_change.diff_content[:2000] if file_change.diff_content else ""
                    logger.info(f"Using diff_content (first 200 chars): {content_for_prompt[:200]}...")
                
                system_prompt, human_prompt = self.prompt_loader.get_prompt(
                    "test_generation",
                    test_type=test_type.value,
                    file_path=file_change.file_path,
                    function_name=function_name,
                    diff_content=content_for_prompt,
                    language_specific=language_specific
                )
                
                logger.info(f"=== LLM Request for {function_name} ===")
                logger.info(f"System prompt: {system_prompt[:300]}...")
                logger.info(f"Human prompt: {human_prompt[:300]}...")
                
                # 디버깅을 위해 콘솔에도 출력
                print(f"\n{'='*50}")
                print(f"LLM REQUEST for {function_name}")
                logger.info(f"=== LLM Request for {function_name} ===")
                logger.info(f"System prompt:")
                logger.info("=" * 80)
                logger.info(system_prompt)
                logger.info("=" * 80)
                logger.info(f"Human prompt:")
                logger.info("=" * 80)
                logger.info(human_prompt)
                logger.info("=" * 80)
                
                print(f"{'='*50}")
                print(f"System prompt preview: {system_prompt[:200]}...")
                print(f"Human prompt preview: {human_prompt[:200]}...")
                
                try:
                    response = await self.llm.ainvoke([
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=human_prompt)
                    ])
                    
                    logger.info(f"=== LLM Response for {function_name} ===")
                    logger.info(f"Response content (first 500 chars): {response.content[:500]}...")
                    
                    # 디버깅을 위해 콘솔에도 출력
                    print(f"\n{'='*50}")
                    print(f"LLM RESPONSE for {function_name}")
                    print(f"{'='*50}")
                    print(f"Response preview: {response.content[:300]}...")
                    
                except Exception as e:
                    logger.error(f"LLM invocation failed: {e}")
                    print(f"\nERROR: LLM invocation failed: {e}")
                    raise
                
                # 테스트 코드 파싱
                logger.info(f"테스트 응답 파싱 시작: {function_name}")
                test_case = self._parse_test_response(
                    response.content,
                    function_name,
                    test_type
                )
                if test_case:
                    tests.append(test_case)
                    logger.info(f"테스트 케이스 생성 성공: {test_case.name}")
                    logger.info(f"  - 테스트 타입: {test_case.test_type}")
                    logger.info(f"  - 코드 길이: {len(test_case.code) if test_case.code else 0}자")
                else:
                    logger.warning(f"테스트 케이스 파싱 실패: {function_name}")
            
            logger.info("=== 단일 파일 테스트 생성 결과 ===")
            logger.info(f"총 생성된 테스트: {len(tests)}개")
            logger.info(f"처리된 함수: {len(function_targets)}개")
            logger.info("=== LLM Agent: 단일 파일 테스트 생성 완료 ===")
            
        except Exception as e:
            logger.error("=== LLM Agent: 단일 파일 테스트 생성 오류 ===")
            logger.error(f"파일: {file_change.file_path}")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
        
        return tests
    
    async def _generate_tests_for_multiple_files(
        self,
        file_changes: List[FileChange],
        test_type: TestStrategy,
    ) -> List[TestCase]:
        """
        여러 파일의 변경사항을 한 번에 분석하여 테스트 케이스를 생성합니다.
        모든 파일 내용을 하나로 합쳐서 단일 LLM 요청으로 처리합니다.
        """
        tests = []
        
        try:
            logger.info("=== LLM Agent: 다중 파일 테스트 생성 시작 ===")
            logger.info(f"처리할 파일 수: {len(file_changes)}개")
            
            # 파일별 상세 정보 로깅
            logger.info("파일별 상세 정보:")
            for i, fc in enumerate(file_changes):
                logger.info(f"  파일 {i+1}: {fc.file_path}")
                logger.info(f"    - 언어: {fc.language}")
                logger.info(f"    - 변경 타입: {fc.change_type}")
                logger.info(f"    - 변경 라인: +{fc.additions}/-{fc.deletions}")
                logger.info(f"    - 변경 함수 수: {len(fc.functions_changed)}")
                has_content = hasattr(fc, 'full_content') and fc.full_content
                logger.info(f"    - 전체 내용 보유: {has_content}")
                if has_content:
                    logger.info(f"    - 내용 길이: {len(fc.full_content)}자")
            
            print(f"\n{'='*50}")
            print(f"COMBINED TEST GENERATION - {len(file_changes)} files")
            print(f"{'='*50}")
            
            # 모든 파일 변경사항을 하나의 문자열로 결합
            logger.info("파일 내용 결합 시작...")
            combined_content = self._prepare_combined_file_content(file_changes)
            logger.info(f"결합된 내용 길이: {len(combined_content)}자")
            
            # 언어 감지 (가장 많이 사용된 언어)
            language_counts = {}
            for fc in file_changes:
                lang = fc.language or 'unknown'
                language_counts[lang] = language_counts.get(lang, 0) + 1
            
            primary_language = max(language_counts.keys(), key=lambda k: language_counts[k])
            logger.info(f"언어 분포: {language_counts}")
            logger.info(f"주 언어: {primary_language}")
            print(f"Primary language: {primary_language}")
            
            # 언어별 특화 지시사항
            language_specific = self._get_language_specific_instructions(primary_language)
            logger.info(f"언어별 지시사항: {language_specific}")
            
            # 기존 test_generation 프롬프트 사용
            system_prompt, human_prompt = self.prompt_loader.get_prompt(
                "test_generation",
                test_type=test_type.value,
                file_path=f"Multiple files ({len(file_changes)} files)",
                function_name="combined_changes",
                diff_content=combined_content,  # 모든 파일 내용을 여기에
                language_specific=language_specific
            )
            
            logger.info(f"=== LLM Request for combined files ===")
            logger.info(f"Combined content length: {len(combined_content)} chars")
            print(f"\nSending combined request to LLM...")
            print(f"Content length: {len(combined_content)} characters")
            
            # 디버깅을 위한 출력
            logger.info(f"=== LLM Request for Multiple Files ===")
            logger.info(f"System prompt:")
            logger.info("=" * 80)
            logger.info(system_prompt)
            logger.info("=" * 80)
            logger.info(f"Human prompt:")
            logger.info("=" * 80)
            logger.info(human_prompt)
            logger.info("=" * 80)
            logger.info(f"Combined content (full):")
            logger.info("=" * 80)
            logger.info(combined_content)
            logger.info("=" * 80)
            
            print(f"\n{'='*50}")
            print("COMBINED CONTENT PREVIEW:")
            print(f"{'='*50}")
            print(combined_content[:500] + "...")
            
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            
            logger.info(f"=== LLM Response received ===")
            logger.info(f"Response length: {len(response.content)} chars")
            print(f"\nResponse received: {len(response.content)} characters")
            print(f"Response preview: {response.content[:300]}...")
            
            print(f"\n{'='*50}")
            print("PARSING TEST RESPONSE")
            print(f"{'='*50}")
            
            # 응답을 하나의 테스트 케이스로 파싱
            test_case = self._parse_test_response(
                response.content,
                "combined_test_suite",
                test_type
            )
            
            print(f"\nAfter parsing:")
            print(f"test_case type: {type(test_case)}")
            print(f"test_case is None: {test_case is None}")
            
            if test_case:
                print(f"test_case attributes: {dir(test_case)}")
                print(f"test_case.name: {getattr(test_case, 'name', 'NO NAME ATTR')}")
                print(f"test_case has name attr: {hasattr(test_case, 'name')}")
                
                tests.append(test_case)
                logger.info(f"다중 파일 테스트 케이스 생성 성공")
                logger.info(f"  - 테스트 이름: {test_case.name}")
                logger.info(f"  - 테스트 타입: {test_case.test_type}")
                logger.info(f"  - 코드 길이: {len(test_case.code) if test_case.code else 0}자")
                
                print(f"\nSuccessfully created test case")
                print(f"tests list now contains {len(tests)} items")
                print(f"First test type: {type(tests[0])}")
            else:
                logger.warning("다중 파일 테스트 케이스 파싱 실패")
                print(f"\nFailed to parse test response")
            
            logger.info("=== 다중 파일 테스트 생성 결과 ===")
            logger.info(f"처리된 파일 수: {len(file_changes)}개")
            logger.info(f"생성된 테스트 수: {len(tests)}개")
            logger.info(f"주 언어: {primary_language}")
            logger.info(f"결합된 내용 크기: {len(combined_content)}자")
            logger.info("=== LLM Agent: 다중 파일 테스트 생성 완료 ===")
            
        except Exception as e:
            logger.error("=== LLM Agent: 다중 파일 테스트 생성 오류 ===")
            logger.error(f"처리 중이던 파일 수: {len(file_changes)}개")
            logger.error(f"오류 메시지: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            
            print(f"\nERROR in combined test generation: {e}")
            import traceback
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            traceback.print_exc()
        
        return tests
    
    def _prepare_combined_file_content(self, file_changes: List[FileChange]) -> str:
        """여러 파일의 내용을 하나의 문자열로 결합"""
        combined = []
        
        for fc in file_changes:
            combined.append(f"\n{'='*60}")
            combined.append(f"FILE: {fc.file_path}")
            combined.append(f"LANGUAGE: {fc.language}")
            combined.append(f"CHANGE TYPE: {fc.change_type}")
            combined.append(f"{'='*60}\n")
            
            if hasattr(fc, 'full_content') and fc.full_content:
                combined.append("FULL CONTENT:")
                combined.append(fc.full_content[:2000])  # 각 파일당 2000자 제한
                combined.append("\n")
            elif fc.diff_content:
                combined.append("DIFF CONTENT:")
                combined.append(fc.diff_content[:1000])
                combined.append("\n")
        
        return "\n".join(combined)
    
    def _get_language_specific_instructions(self, language: str) -> str:
        """언어별 특화 지시사항 반환"""
        instructions = {
            "python": "Use pytest framework with proper fixtures and assertions. Include type hints where appropriate.",
            "java": "Use JUnit 5 with appropriate annotations (@Test, @BeforeEach, etc.) and assertions.",
            "javascript": "Use Jest framework with proper describe/it blocks and expect assertions.",
            "typescript": "Use Jest with TypeScript support, include proper type definitions.",
            "go": "Use the standard testing package with proper test function naming (TestXxx).",
            "csharp": "Use xUnit or NUnit with appropriate attributes and assertions.",
        }
        return instructions.get(language, "Use appropriate testing framework for the language.")
    
    
    def _parse_test_response(
        self,
        response: str,
        function_name: str,
        test_type: TestStrategy
    ) -> Optional[TestCase]:
        """LLM 응답에서 테스트 케이스 파싱"""
        try:
            print(f"\n{'='*40}")
            print(f"_parse_test_response called")
            print(f"function_name: {function_name}")
            print(f"test_type: {test_type}")
            print(f"response length: {len(response)}")
            print(f"{'='*40}")
            
            logger.info(f"=== Parsing test response for {function_name} ===")
            logger.info(f"Response length: {len(response)}")
            logger.info(f"Response preview: {response[:200]}...")
            
            # 응답이 비어있거나 너무 짧은 경우
            if not response or len(response.strip()) < 10:
                logger.warning(f"Response too short or empty for {function_name}")
                print(f"WARNING: Response too short or empty")
                return None
            
            print(f"Creating TestCase object...")
            print(f"TestCase class: {TestCase}")
            
            # 간단한 파싱 로직 (실제로는 더 정교하게)
            test_case = TestCase(
                name=f"test_{function_name}",
                description=f"Test for {function_name}",
                test_type=test_type,
                code=response,
                assertions=[],
                dependencies=[],
                priority=3
            )
            
            print(f"TestCase created successfully!")
            print(f"test_case type: {type(test_case)}")
            print(f"test_case.name: {test_case.name}")
            print(f"hasattr(test_case, 'name'): {hasattr(test_case, 'name')}")
            print(f"test_case.__dict__: {test_case.__dict__}")
            
            logger.info(f"Successfully created test case: {test_case.name}")
            return test_case
            
        except Exception as e:
            logger.error(f"Error parsing test response for {function_name}: {e}")
            print(f"ERROR in _parse_test_response: {e}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def _summarize_changes(self, file_changes: List[FileChange]) -> str:
        """파일 변경사항 요약"""
        summary = f"Total files changed: {len(file_changes)}\n\n"
        
        for change in file_changes[:10]:  # 최대 10개
            summary += f"- {change.file_path} ({change.change_type})\n"
            summary += f"  Language: {change.language or 'unknown'}\n"
            summary += f"  Changes: +{change.additions} -{change.deletions}\n"
            if change.functions_changed:
                summary += f"  Functions: {', '.join(change.functions_changed[:3])}\n"
            summary += "\n"
        
        return summary
    
    def _summarize_tests(self, tests: List[TestCase]) -> str:
        """생성된 테스트 요약"""
        if not tests:
            return "No tests generated yet."
        
        summary = f"Total tests generated: {len(tests)}\n\n"
        
        # 타입별 집계
        by_type = {}
        for test in tests:
            by_type[test.test_type] = by_type.get(test.test_type, 0) + 1
        
        for test_type, count in by_type.items():
            summary += f"- {test_type}: {count}\n"
        
        return summary
    
    def _summarize_tests_for_scenarios(self, test_cases: List[TestCase]) -> str:
        """시나리오 생성을 위한 테스트 케이스 요약"""
        if not test_cases:
            return "테스트 케이스가 없습니다."
        
        summary = f"생성된 테스트 케이스 ({len(test_cases)}개):\n\n"
        
        for i, test in enumerate(test_cases[:5]):  # 최대 5개만 요약
            summary += f"{i+1}. 테스트명: {test.name}\n"
            summary += f"   설명: {test.description}\n"
            summary += f"   타입: {test.test_type}\n"
            summary += f"   우선순위: {test.priority}\n"
            if test.code:
                # 코드 일부 포함 (첫 200자)
                code_preview = test.code.replace('\n', ' ')[:200]
                summary += f"   코드 미리보기: {code_preview}...\n"
            summary += "\n"
        
        if len(test_cases) > 5:
            summary += f"... 외 {len(test_cases) - 5}개 테스트 더 있음\n"
        
        return summary
    
    def _summarize_file_changes_for_scenarios(self, file_changes: List) -> str:
        """시나리오 생성을 위한 파일 변경사항 요약"""
        if not file_changes:
            return "파일 변경사항이 없습니다."
        
        summary = f"변경된 파일 ({len(file_changes)}개):\n\n"
        
        for i, fc in enumerate(file_changes[:5]):  # 최대 5개만 요약
            if hasattr(fc, 'file_path'):
                summary += f"{i+1}. 파일: {fc.file_path}\n"
                summary += f"   언어: {fc.language or 'unknown'}\n"
                summary += f"   변경타입: {fc.change_type}\n"
                summary += f"   변경된 함수: {', '.join(fc.functions_changed[:3]) if fc.functions_changed else '없음'}\n"
                if hasattr(fc, 'diff_content') and fc.diff_content:
                    summary += f"   변경 내용: {fc.diff_content[:100]}...\n"
            elif isinstance(fc, dict):
                summary += f"{i+1}. 파일: {fc.get('file_path', 'unknown')}\n"
                summary += f"   언어: {fc.get('language', 'unknown')}\n"
                summary += f"   변경타입: {fc.get('change_type', 'unknown')}\n"
            summary += "\n"
        
        if len(file_changes) > 5:
            summary += f"... 외 {len(file_changes) - 5}개 파일 더 있음\n"
        
        return summary
    
    def _parse_scenario_response(self, response_content: str) -> List[Dict[str, Any]]:
        """LLM 응답에서 시나리오 파싱 (JSON 형태)"""
        scenarios = []
        
        try:
            import json
            
            # JSON 블록 추출 시도 (```json으로 감싸져 있는 경우)
            json_content = response_content
            if "```json" in response_content:
                start_idx = response_content.find("```json") + 7
                end_idx = response_content.find("```", start_idx)
                if end_idx > start_idx:
                    json_content = response_content[start_idx:end_idx].strip()
                    logger.info("JSON 블록에서 내용 추출")
            elif "```" in response_content:
                # 일반 코드 블록인 경우
                start_idx = response_content.find("```") + 3
                end_idx = response_content.rfind("```")
                if end_idx > start_idx:
                    json_content = response_content[start_idx:end_idx].strip()
                    logger.info("코드 블록에서 내용 추출")
            
            # JSON 파싱 시도
            parsed_data = json.loads(json_content)
            if isinstance(parsed_data, list):
                scenarios = parsed_data
                logger.info(f"JSON 배열 파싱 성공: {len(scenarios)}개 시나리오")

            elif isinstance(parsed_data, dict):
                scenarios = [parsed_data]
                logger.info("JSON 객체 파싱 성공: 1개 시나리오")
            else:
                logger.warning(f"예상치 못한 JSON 구조: {type(parsed_data)}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.info("텍스트 기반 파싱으로 fallback")
            scenarios = self._parse_scenario_text(response_content)
        except Exception as e:
            logger.error(f"시나리오 응답 파싱 오류: {e}")
            scenarios = self._generate_default_scenarios([], [])
            
        return scenarios
    
    def _parse_scenario_text(self, response_content: str) -> List[Dict[str, Any]]:
        """텍스트 형태의 LLM 응답에서 시나리오 추출"""
        scenarios = []
        
        logger.info("텍스트 기반 시나리오 파싱 시작")
        
        # 간단한 텍스트 파싱 로직 - 기본 시나리오 생성
        lines = response_content.split('\n')
        scenario_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 시나리오 키워드 감지
            if any(keyword in line.lower() for keyword in ['시나리오', 'scenario', '테스트']):
                scenario_count += 1
                scenario = {
                    'scenario_id': f'TS_{scenario_count:03d}',
                    'feature': f'텍스트 기반 기능 {scenario_count}',
                    'description': line[:100] if line else f'자동 생성된 시나리오 {scenario_count}',
                    'priority': '보통',
                    'test_type': '기능',
                    'preconditions': ['시스템이 정상 작동 중'],
                    'test_steps': [
                        {'step': 1, 'action': '기능 실행', 'description': '대상 기능을 실행합니다'},
                        {'step': 2, 'action': '결과 확인', 'description': '실행 결과를 확인합니다'}
                    ],
                    'expected_results': ['기능이 정상적으로 작동함'],
                    'test_data': {}
                }
                scenarios.append(scenario)
                
                if scenario_count >= 3:  # 최대 3개로 제한
                    break
        
        if not scenarios:
            # 아무것도 파싱되지 않은 경우 기본 시나리오 1개 생성
            scenarios = [{
                'scenario_id': 'TS_001',
                'feature': '기본 기능 테스트',
                'description': 'LLM 응답을 파싱할 수 없어 생성된 기본 시나리오',
                'priority': '보통',
                'test_type': '기능',
                'preconditions': ['시스템이 정상 작동 중'],
                'test_steps': [
                    {'step': 1, 'action': '시스템 초기화', 'description': '테스트 대상 시스템을 초기화합니다'},
                    {'step': 2, 'action': '기본 기능 실행', 'description': '시스템의 기본 기능을 실행합니다'},
                    {'step': 3, 'action': '결과 검증', 'description': '실행 결과가 예상과 일치하는지 확인합니다'}
                ],
                'expected_results': ['시스템이 정상적으로 초기화됨', '기본 기능이 올바르게 작동함'],
                'test_data': {}
            }]
        
        logger.info(f"텍스트 파싱으로 {len(scenarios)}개 시나리오 추출")
        return scenarios
    
    def _generate_default_scenarios(self, test_cases: List[TestCase], file_changes: List) -> List[Dict[str, Any]]:
        """기본 시나리오 생성 (LLM 실패 시 fallback)"""
        scenarios = []
        
        logger.info("기본 시나리오 생성 시작")
        
        # 테스트 케이스 기반 시나리오
        if test_cases:
            for i, test in enumerate(test_cases[:2]):  # 최대 2개
                scenario = {
                    'scenario_id': f'TS_TEST_{i+1:02d}',
                    'feature': f'테스트 기반 기능 - {test.name}',
                    'description': f'{test.description} 실행을 위한 시나리오',
                    'priority': '높음' if test.priority <= 2 else '보통',
                    'test_type': '기능',
                    'preconditions': ['테스트 환경이 준비됨', '필요한 테스트 데이터가 준비됨'],
                    'test_steps': [
                        {'step': 1, 'action': '테스트 환경 설정', 'description': '테스트 실행을 위한 환경을 설정합니다'},
                        {'step': 2, 'action': f'{test.name} 실행', 'description': f'{test.name} 테스트를 실행합니다'},
                        {'step': 3, 'action': '결과 확인', 'description': '테스트 실행 결과를 확인하고 검증합니다'}
                    ],
                    'expected_results': [
                        f'{test.name} 테스트가 성공적으로 실행됨',
                        '모든 검증 조건이 통과됨',
                        '예상된 결과값이 반환됨'
                    ],
                    'test_data': {
                        'test_name': test.name,
                        'test_type': str(test.test_type)
                    }
                }
                scenarios.append(scenario)
        
        # 파일 변경사항 기반 시나리오
        if file_changes:
            for i, fc in enumerate(file_changes[:2]):  # 최대 2개
                if hasattr(fc, 'file_path'):
                    file_name = fc.file_path.split("/")[-1] if "/" in fc.file_path else fc.file_path
                    functions = fc.functions_changed[:2] if fc.functions_changed else ['변경된 기능']
                    language = fc.language or 'unknown'
                else:
                    file_name = 'unknown_file'
                    functions = ['변경된 기능']
                    language = 'unknown'
                
                scenario = {
                    'scenario_id': f'TS_FILE_{i+1:02d}',
                    'feature': f'파일 변경 검증 - {file_name}',
                    'description': f'{file_name} 파일의 변경사항이 정상 동작하는지 검증',
                    'priority': '높음',
                    'test_type': '통합',
                    'preconditions': [
                        f'{file_name} 파일이 정상적으로 수정됨',
                        '관련 의존성이 모두 해결됨',
                        '테스트 환경이 최신 코드로 업데이트됨'
                    ],
                    'test_steps': [
                        {'step': 1, 'action': '변경사항 배포', 'description': f'{file_name} 파일의 변경사항을 테스트 환경에 배포합니다'},
                        {'step': 2, 'action': '기능 실행', 'description': f'{", ".join(functions)} 기능을 실행합니다'},
                        {'step': 3, 'action': '동작 검증', 'description': '변경된 기능이 예상대로 동작하는지 확인합니다'},
                        {'step': 4, 'action': '회귀 테스트', 'description': '기존 기능에 영향이 없는지 확인합니다'}
                    ],
                    'expected_results': [
                        '변경된 기능이 정상적으로 작동함',
                        '기존 기능에 부작용이 발생하지 않음',
                        f'{language} 코드가 올바르게 실행됨'
                    ],
                    'test_data': {
                        'file_path': file_name,
                        'language': language,
                        'functions': functions
                    }
                }
                scenarios.append(scenario)
        
        # 기본 시나리오 (아무것도 없는 경우)
        if not scenarios:
            scenarios.append({
                'scenario_id': 'TS_DEFAULT_01',
                'feature': '기본 시스템 동작 검증',
                'description': '시스템의 기본적인 동작과 상태를 확인하는 시나리오',
                'priority': '보통',
                'test_type': '기능',
                'preconditions': [
                    '시스템이 정상적으로 시작됨',
                    '모든 필수 서비스가 실행 중',
                    '네트워크 연결이 정상'
                ],
                'test_steps': [
                    {'step': 1, 'action': '시스템 상태 확인', 'description': '시스템의 현재 상태와 설정을 확인합니다'},
                    {'step': 2, 'action': '기본 기능 실행', 'description': '시스템의 핵심 기능들을 차례로 실행합니다'},
                    {'step': 3, 'action': '응답 검증', 'description': '각 기능의 응답이 올바른지 검증합니다'},
                    {'step': 4, 'action': '로그 확인', 'description': '실행 과정에서 발생한 로그를 확인합니다'}
                ],
                'expected_results': [
                    '모든 시스템 상태가 정상으로 표시됨',
                    '기본 기능들이 오류 없이 실행됨',
                    '적절한 응답값이 반환됨',
                    '오류 로그가 발생하지 않음'
                ],
                'test_data': {
                    'system_type': 'default',
                    'test_mode': 'basic_validation'
                }
            })
        
        logger.info(f"기본 시나리오 {len(scenarios)}개 생성 완료")
        return scenarios
    
    def _summarize_tests_for_review(self, test_cases: List[TestCase]) -> str:
        """리뷰를 위한 테스트 요약"""
        if not test_cases:
            return "생성된 테스트가 없습니다."
        
        summary = f"총 {len(test_cases)}개의 테스트가 생성되었습니다.\n\n"
        
        for i, test in enumerate(test_cases[:10]):  # 최대 10개까지만 요약
            summary += f"## 테스트 {i+1}: {test.name}\n"
            summary += f"- 설명: {test.description}\n"
            summary += f"- 타입: {test.test_type}\n"
            summary += f"- 우선순위: {test.priority}\n"
            
            # 코드가 너무 길면 줄임
            code_preview = test.code[:200] + "..." if len(test.code) > 200 else test.code
            summary += f"- 코드 미리보기:\n```\n{code_preview}\n```\n\n"
        
        if len(test_cases) > 10:
            summary += f"... 외 {len(test_cases) - 10}개 테스트\n"
        
        return summary
    
    def _summarize_scenarios_for_review(self, scenario_objects: List[TestScenario]) -> str:
        """리뷰를 위한 시나리오 요약"""
        if not scenario_objects:
            return "생성된 테스트 시나리오가 없습니다."
        
        summary = f"총 {len(scenario_objects)}개의 테스트 시나리오가 생성되었습니다.\n\n"
        
        for i, scenario in enumerate(scenario_objects[:10]):  # 최대 10개까지만 요약
            summary += f"## 시나리오 {i+1}: {scenario.scenario_id}\n"
            summary += f"- 기능: {scenario.feature}\n"
            summary += f"- 설명: {scenario.description}\n"
            summary += f"- 우선순위: {scenario.priority}\n"
            summary += f"- 테스트 타입: {scenario.test_type}\n"
            summary += f"- 사전조건: {len(scenario.preconditions)}개\n"
            summary += f"- 테스트 단계: {len(scenario.test_steps)}개\n"
            summary += f"- 기대결과: {len(scenario.expected_results)}개\n\n"
        
        if len(scenario_objects) > 10:
            summary += f"... 외 {len(scenario_objects) - 10}개 시나리오\n"
        
        return summary
    
    def _parse_review_response(self, response_content: str) -> Dict[str, Any]:
        """LLM 리뷰 응답 파싱"""
        try:
            logger.info("LLM 리뷰 응답 파싱 시작")
            
            # 응답 내용에서 주요 정보 추출
            content = response_content.strip()
            
            # 기본 구조 생성 - 전체 내용 유지
            result = {
                "review_summary": {
                    "review_content": content  # 전체 리뷰 내용 저장
                },
                "improvement_suggestions": [],
                "quality_metrics": {}
            }
            
            # 점수나 평가 추출 시도
            import re
            
            # 점수 패턴 찾기 (예: "8점", "7/10", "점수: 8" 등)
            score_patterns = [
                r'(\d+)\s*점',
                r'(\d+)\s*/\s*10',
                r'점수\s*:\s*(\d+)',
                r'품질\s*점수\s*:\s*(\d+)',
                r'전체\s*품질\s*:\s*(\d+)'
            ]
            
            score = None
            for pattern in score_patterns:
                match = re.search(pattern, content)
                if match:
                    score = int(match.group(1))
                    break
            
            if score:
                result["quality_metrics"]["overall_score"] = f"{score}/10"
                result["quality_metrics"]["overall_quality"] = "Excellent" if score >= 8 else "Good" if score >= 6 else "Needs Improvement"
            
            # 개선사항 추출
            suggestions = []
            
            # 번호가 매겨진 목록 찾기
            numbered_items = re.findall(r'\d+\.\s*([^\n]+)', content)
            suggestions.extend(numbered_items[:10])  # 최대 10개
            
            # 불릿 포인트 찾기
            bullet_items = re.findall(r'[-•]\s*([^\n]+)', content)
            suggestions.extend(bullet_items[:5])  # 최대 5개 추가
            
            # 중복 제거 및 정리
            cleaned_suggestions = []
            for suggestion in suggestions:
                cleaned = suggestion.strip()
                if cleaned and len(cleaned) > 10 and cleaned not in cleaned_suggestions:
                    cleaned_suggestions.append(cleaned)
            
            result["improvement_suggestions"] = cleaned_suggestions[:8]  # 최대 8개
            
            logger.info(f"파싱 완료 - 점수: {score}, 개선사항: {len(result['improvement_suggestions'])}개")
            return result
            
        except Exception as e:
            logger.error(f"리뷰 응답 파싱 실패: {e}")
            return {
                "review_summary": {"review_content": response_content[:200] + "..."},
                "improvement_suggestions": ["응답 파싱 중 오류 발생"],
                "quality_metrics": {"parsing_error": str(e)}
            }
    
    def _generate_default_review(self, test_cases: List[TestCase], scenario_objects: List[TestScenario]) -> Dict[str, Any]:
        """기본 리뷰 결과 생성 (폴백용)"""
        total_tests = len(test_cases)
        total_scenarios = len(scenario_objects)
        
        # 기본 품질 평가
        if total_tests == 0 and total_scenarios == 0:
            quality = "Needs Improvement"
            score = "3/10"
        elif total_tests > 0 and total_scenarios > 0:
            quality = "Good"
            score = "7/10"
        else:
            quality = "Fair"
            score = "5/10"
        
        suggestions = [
            "생성된 테스트의 코드 품질 검토 필요",
            "엣지 케이스에 대한 테스트 커버리지 확인",
            "테스트 시나리오의 완성도 점검",
            "성능 테스트 케이스 추가 고려"
        ]
        
        if total_tests < 3:
            suggestions.insert(0, "테스트 케이스 수가 부족합니다. 더 많은 테스트가 필요합니다.")
        
        if total_scenarios < 5:
            suggestions.insert(1, "테스트 시나리오 수가 부족합니다. 더 다양한 시나리오가 필요합니다.")
        
        return {
            "review_summary": {
                "review_content": f"자동 생성된 리뷰: {total_tests}개 테스트와 {total_scenarios}개 시나리오 분석 완료. 전체 품질은 {quality} 수준입니다."
            },
            "improvement_suggestions": suggestions,
            "quality_metrics": {
                "overall_score": score,
                "overall_quality": quality,
                "test_coverage_estimate": "60-80%",
                "scenario_completeness": "기본 수준"
            }
        }

