"""
LLM Agent Module - AI 기반 테스트 생성 에이전트

LangGraph를 사용하여 상태 기반 워크플로우를 구현하고,
Azure OpenAI Service와 연동하여 테스트 코드를 생성합니다.
"""
import os
import json
from textwrap import dedent
from typing import List, Dict, Any, Optional, TypedDict, Annotated, Literal
import datetime
from dataclasses import dataclass
import logging
from enum import Enum

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langfuse import Langfuse
from langfuse import observe

from ai_test_generator.core.git_analyzer import FileChange, CommitAnalysis
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
    """LangGraph 에이전트 상태"""
    messages: Annotated[List[Any], add_messages]
    file_changes: List[FileChange]
    commit_analysis: Optional[CommitAnalysis]
    test_strategy: Optional[TestStrategy]
    generated_tests: List[TestCase]
    test_scenarios: List[TestScenario]
    rag_context: Optional[str]
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
        self._initialize_llm()
        self._initialize_langfuse()
        self._build_graph()
    
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
            temperature=0.2,  # 일관된 테스트 생성을 위해 낮은 temperature
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
    
    def _build_graph(self) -> None:
        """
        LangGraph 워크플로우를 구축하는 메서드입니다.
        이 메서드는 테스트 생성 에이전트의 상태 그래프를 정의하고, 각 단계별 노드를 추가하며, 
        노드 간의 전이(엣지) 및 조건부 라우팅을 설정합니다. 
        구체적으로는 다음과 같은 단계로 구성됩니다:
        1. 상태 그래프(StateGraph) 객체를 생성합니다.
        2. 코드 변경 분석, 테스트 전략 결정, 단위 테스트/통합 테스트/테스트 시나리오 생성, 
            리뷰 및 개선 등 각 단계별 노드를 그래프에 추가합니다.
        3. 각 노드 간의 전이(엣지)를 정의하여 워크플로우의 흐름을 설정합니다.
        4. 테스트 전략 결정 단계에서는 조건부 라우팅을 통해 전략에 따라 다음 노드를 동적으로 선택합니다.
            - "unit": 단위 테스트 생성 노드로 이동
            - "integration": 통합 테스트 생성 노드로 이동
            - "both": 단위 테스트 생성 노드로 이동
            - "scenarios": 테스트 시나리오 생성 노드로 이동
        5. 모든 테스트 생성 단계가 끝나면 리뷰 및 개선 노드로 이동하고, 
            마지막으로 워크플로우를 종료(END)합니다.
        6. 최종적으로 그래프를 컴파일하여 self.graph에 저장합니다.
        이 과정을 통해 테스트 생성 에이전트의 전체 동작 흐름을 LangGraph로 시각화하고, 
        유연하게 확장 가능한 테스트 생성 파이프라인을 구성할 수 있습니다.
        """
        # 상태 그래프 생성
        workflow = StateGraph(AgentState)
        
        # 노드 추가
        workflow.add_node("analyze_changes", self.analyze_changes)
        workflow.add_node("determine_strategy", self.determine_test_strategy)
        workflow.add_node("generate_unit_tests", self.generate_unit_tests)
        workflow.add_node("generate_integration_tests", self.generate_integration_tests)
        workflow.add_node("generate_test_scenarios", self.generate_test_scenarios)
        workflow.add_node("review_and_refine", self.review_and_refine)
        
        # 엣지 추가
        workflow.set_entry_point("analyze_changes")
        workflow.add_edge("analyze_changes", "determine_strategy")
        
        # 조건부 라우팅
        workflow.add_conditional_edges(
            "determine_strategy",
            self.route_by_strategy,
            {
                "unit": "generate_unit_tests",
                "integration": "generate_integration_tests",
                "both": "generate_unit_tests",
                "scenarios": "generate_test_scenarios"
            }
        )
        
        workflow.add_edge("generate_unit_tests", "generate_test_scenarios")
        workflow.add_edge("generate_integration_tests", "generate_test_scenarios")
        workflow.add_edge("generate_test_scenarios", "review_and_refine")
        workflow.add_edge("review_and_refine", END)
        
        # 컴파일
        self.graph = workflow.compile()
        logger.info("LangGraph workflow built successfully")
    
    @observe(name="analyze_changes")
    async def analyze_changes(self, state: AgentState) -> AgentState:
        """
        코드 변경사항을 분석하여 테스트 전략을 제안하는 비동기 메서드입니다.
        Args:
            state (AgentState): 에이전트의 현재 상태를 담고 있는 딕셔너리로,
                'file_changes' 키에 코드 변경사항 정보가 포함되어 있습니다.
        Returns:
            AgentState: 분석 결과 및 메시지가 추가된 에이전트 상태를 반환합니다.
        동작 설명:
            1. 'current_step'을 'analyzing_changes'로 설정하여 현재 단계 표시
            2. 'file_changes' 정보를 요약하여 변경사항 요약문 생성
            3. 시스템 프롬프트와 사용자 프롬프트를 구성하여 LLM에 전달
            4. LLM의 응답(분석 결과)을 state["messages"]에 추가
            5. 분석 성공 시 로그 기록, 예외 발생 시 에러 메시지와 함께 state에 저장
        예외 처리:
            분석 과정에서 예외가 발생하면 에러 로그를 남기고, state["error"]에 에러 메시지를 저장합니다.
        주의:
            이 메서드는 LLM(대형 언어 모델) 호출에 의존하므로 네트워크 지연이나 LLM 오류에 영향을 받을 수 있습니다.
        """
        try:
            state["current_step"] = "analyzing_changes"
            
            # 변경사항 요약
            changes_summary = self._summarize_changes(state["file_changes"])
            
            # 분석 프롬프트
            system_prompt = """You are an expert software test engineer analyzing code changes.
            Analyze the following code changes and provide insights about:
            1. The nature and scope of changes
            2. Potential impact on the system
            3. Risk areas that need testing
            4. Suggested testing approach
            
            Output your analysis in a structured format."""
            
            human_prompt = f"""Code changes summary:
            {changes_summary}
            
            Provide a comprehensive analysis of these changes."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.analysis_llm.ainvoke(messages)
            
            state["messages"].append(response)
            logger.info("Code changes analyzed successfully")
            
        except Exception as e:
            logger.error(f"Error analyzing changes: {e}")
            state["error"] = str(e)
        
        return state
    
    @observe(name="determine_strategy")
    async def determine_test_strategy(self, state: AgentState) -> AgentState:
        """테스트 전략 결정"""
        try:
            state["current_step"] = "determining_strategy"
            
            # 이전 분석 결과 가져오기
            last_analysis = state["messages"][-1].content if state["messages"] else ""
            
            # 전략 결정 프롬프트
            strategy_prompt = ChatPromptTemplate.from_messages([
                ("system", """Based on the code analysis, determine the appropriate testing strategy.
                Consider:
                - File types and changes
                - Complexity of changes
                - Dependencies affected
                - Risk level
                
                Output a JSON with:
                {
                    "primary_strategy": "unit|integration|performance|security",
                    "secondary_strategies": ["list", "of", "strategies"],
                    "reasoning": "explanation of why these strategies were chosen",
                    "priority_areas": ["list", "of", "focus", "areas"]
                }"""),
                ("human", "Analysis: {analysis}")
            ])
            
            chain = strategy_prompt | self.llm | JsonOutputParser()
            strategy_result = await chain.ainvoke({"analysis": last_analysis})
            
            # 주요 전략 설정
            primary = strategy_result.get("primary_strategy", "unit")
            if primary == "unit":
                state["test_strategy"] = TestStrategy.UNIT_TEST
            elif primary == "integration":
                state["test_strategy"] = TestStrategy.INTEGRATION_TEST
            else:
                state["test_strategy"] = TestStrategy.UNIT_TEST
            
            state["messages"].append(AIMessage(content=json.dumps(strategy_result)))
            logger.info(f"Test strategy determined: {state['test_strategy']}")
            
        except Exception as e:
            logger.error(f"Error determining strategy: {e}")
            state["error"] = str(e)
            state["test_strategy"] = TestStrategy.UNIT_TEST  # 기본값
        
        return state
    
    @observe(name="generate_unit_tests")
    async def generate_unit_tests(self, state: AgentState) -> AgentState:
        """단위 테스트 생성"""
        try:
            state["current_step"] = "generating_unit_tests"
            
            for file_change in state["file_changes"]:
                if file_change.language and file_change.change_type != "deleted":
                    tests = await self._generate_tests_for_file(
                        file_change,
                        TestStrategy.UNIT_TEST,
                        state.get("rag_context")
                    )
                    state["generated_tests"].extend(tests)
            
            logger.info(f"Generated {len(state['generated_tests'])} unit tests")
            
        except Exception as e:
            logger.error(f"Error generating unit tests: {e}")
            state["error"] = str(e)
        
        return state

    @observe(name="generate_integration_tests")
    async def generate_integration_tests(self, state: AgentState) -> AgentState:
        """통합 테스트 생성"""
        try:
            state["current_step"] = "generating_integration_tests"

            # 통합 테스트는 여러 파일 간의 상호작용을 테스트
            # 관련 파일들을 그룹화
            related_files = self._group_related_files(state["file_changes"])

            for file_group in related_files[:3]:  # 최대 3개 그룹만 처리
                if len(file_group) > 1:  # 2개 이상의 파일이 관련된 경우만
                    # 그룹의 주요 파일 선택
                    main_file = max(file_group, key=lambda f: f.additions + f.deletions)

                    if main_file.language and main_file.change_type != "deleted":
                        # 통합 테스트 생성 시 관련 파일 정보 포함
                        integration_context = self._create_integration_context(file_group)

                        tests = await self._generate_integration_tests_for_group(
                            main_file,
                            file_group,
                            integration_context,
                            state.get("rag_context")
                        )
                        state["generated_tests"].extend(tests)

            logger.info(f"Generated {len(state['generated_tests'])} integration tests")

        except Exception as e:
            logger.error(f"Error generating integration tests: {e}")
            state["error"] = str(e)

        return state

    def _group_related_files(self, file_changes: List[FileChange]) -> List[List[FileChange]]:
        """관련 파일들을 그룹화"""
        groups = []
        processed = set()

        for i, file1 in enumerate(file_changes):
            if i in processed:
                continue

            group = [file1]
            processed.add(i)

            # 같은 디렉토리나 유사한 이름의 파일 찾기
            for j, file2 in enumerate(file_changes[i+1:], i+1):
                if j not in processed:
                    if self._are_files_related(file1, file2):
                        group.append(file2)
                        processed.add(j)

            if len(group) > 1:
                groups.append(group)

        return groups

    def _are_files_related(self, file1: FileChange, file2: FileChange) -> bool:
        """두 파일이 관련있는지 판단"""
        path1 = Path(file1.file_path)
        path2 = Path(file2.file_path)

        # 같은 디렉토리
        if path1.parent == path2.parent:
            return True

        # 유사한 이름 (예: service.py와 service_test.py)
        if path1.stem in path2.stem or path2.stem in path1.stem:
            return True

        # 임포트 관계 (diff 내용에서 확인)
        if file1.diff_content and file2.file_path in file1.diff_content:
            return True

        return False

    def _create_integration_context(self, file_group: List[FileChange]) -> str:
        """통합 테스트를 위한 컨텍스트 생성"""
        context = "Related files in this integration:\n"
        for file in file_group:
            context += f"- {file.file_path} ({file.change_type})\n"
            if file.functions_changed:
                context += f"  Functions: {', '.join(file.functions_changed[:3])}\n"
        return context

    async def _generate_integration_tests_for_group(
        self,
        main_file: FileChange,
        file_group: List[FileChange],
        integration_context: str,
        rag_context: Optional[str] = None
    ) -> List[TestCase]:
        """파일 그룹에 대한 통합 테스트 생성"""

        tests = []

        try:
            # 통합 테스트 생성 프롬프트
            prompt = dedent(f"""
                Generate integration tests for the following group of related files.

                {integration_context}

                Main file: {main_file.file_path}
                Language: {main_file.language}

                Focus on:
                1. Component interactions and dependencies
                2. Data flow between modules
                3. API contracts and interfaces
                4. Error propagation across components
                5. Integration with external services or databases

                {rag_context or ''}

                Code changes:
                {main_file.diff_content[:2000]}

                Generate comprehensive integration tests that verify the components work together correctly.
            """)

            response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert test engineer specializing in integration testing."),
            HumanMessage(content=prompt)
            ])

            # 파싱하여 TestCase 객체 생성
            test_case = TestCase(
            name=f"test_integration_{Path(main_file.file_path).stem}",
            description=f"Integration test for {main_file.file_path} and related files",
            test_type=TestStrategy.INTEGRATION_TEST,
            code=response.content,
            assertions=[],
            dependencies=[f.file_path for f in file_group],
            priority=2
            )
            tests.append(test_case)

        except Exception as e:
            logger.error(f"Error generating integration tests for {main_file.file_path}: {e}")

        return tests

    @observe(name="generate_test_scenarios")
    async def generate_test_scenarios(self, state: AgentState) -> AgentState:
        """
        테스트 시나리오 생성 (엑셀 문서용)

        이 메서드는 코드 변경사항과 이미 생성된 테스트 케이스를 바탕으로
        QA 문서(예: 엑셀 시트)에 사용할 수 있는 상세한 테스트 시나리오를 생성합니다.

        동작 과정:
        1. current_step을 'generating_test_scenarios'로 설정하여 현재 단계를 표시합니다.
        2. 시스템 프롬프트와 사용자 프롬프트를 조합하여 시나리오 생성을 위한 LLM 체인을 구성합니다.
           - 시스템 프롬프트: 시나리오에 포함되어야 할 필수 항목(시나리오 ID, 기능명, 설명, 사전조건, 테스트 단계, 기대 결과, 테스트 데이터, 우선순위, 테스트 타입 등)을 안내합니다.
           - 사용자 프롬프트: 코드 변경 요약 및 생성된 테스트 요약을 제공합니다.
        3. 파일 변경사항과 생성된 테스트 케이스를 요약하여 프롬프트에 삽입합니다.
        4. LLM 체인을 실행하여 JSON 배열 형태의 시나리오 데이터를 생성합니다.
        5. 각 시나리오 데이터를 TestScenario 데이터 클래스로 변환하여 state["test_scenarios"]에 추가합니다.
        6. 성공적으로 생성된 시나리오 개수를 로그로 남깁니다.
        7. 예외 발생 시 에러 메시지를 state["error"]에 저장하고 로그를 남깁니다.

        반환값:
            AgentState: 생성된 테스트 시나리오가 추가된 상태 객체를 반환합니다.
        """
        try:
            state["current_step"] = "generating_test_scenarios"
            
            # 시나리오 생성 프롬프트
            scenario_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are creating test scenarios for QA documentation.
                Generate detailed test scenarios based on the code changes and generated tests.
                
                For each scenario, provide:
                - Unique scenario ID
                - Feature/Module name
                - Description
                - Preconditions
                - Detailed test steps
                - Expected results
                - Test data (if applicable)
                - Priority (High/Medium/Low)
                - Test type (Functional/Integration/Performance/Security)
                
                Output as JSON array."""),
                ("human", """Code changes: {changes}
                Generated tests: {tests}
                
                Create comprehensive test scenarios.""")
            ])
            
            # 변경사항과 테스트 요약
            changes_summary = self._summarize_changes(state["file_changes"])
            tests_summary = self._summarize_tests(state["generated_tests"])
            
            chain = scenario_prompt | self.llm | JsonOutputParser()
            scenarios_data = await chain.ainvoke({
                "changes": changes_summary,
                "tests": tests_summary
            })
            
            # TestScenario 객체로 변환
            for scenario_data in scenarios_data:
                scenario = TestScenario(
                    scenario_id=scenario_data.get("scenario_id", ""),
                    feature=scenario_data.get("feature", ""),
                    description=scenario_data.get("description", ""),
                    preconditions=scenario_data.get("preconditions", []),
                    test_steps=scenario_data.get("test_steps", []),
                    expected_results=scenario_data.get("expected_results", []),
                    test_data=scenario_data.get("test_data"),
                    priority=scenario_data.get("priority", "Medium"),
                    test_type=scenario_data.get("test_type", "Functional")
                )
                state["test_scenarios"].append(scenario)
            
            logger.info(f"Generated {len(state['test_scenarios'])} test scenarios")
            
        except Exception as e:
            logger.error(f"Error generating test scenarios: {e}")
            state["error"] = str(e)
        
        return state
    
    @observe(name="review_and_refine")
    async def review_and_refine(self, state: AgentState) -> AgentState:
        """
        생성된 테스트와 시나리오를 검토하고 개선점을 제안하는 비동기 메서드입니다.
        이 메서드는 다음과 같은 절차로 동작합니다:
        1. 현재 단계를 'reviewing'으로 설정합니다.
        2. 테스트의 완전성, 품질, 정확성, 그리고 테스트 관례 준수 여부를 평가하는 프롬프트를 생성합니다.
        3. 생성된 테스트와 시나리오를 요약하여 프롬프트에 입력값으로 전달합니다.
        4. LLM(대형 언어 모델)을 통해 테스트에 대한 리뷰 및 개선 피드백, 품질 점수를 요청합니다.
        5. 리뷰 결과를 상태(state)의 메시지 목록에 추가하고, 로그를 남깁니다.
        6. 예외 발생 시 에러 로그를 남기고 상태에 에러 메시지를 저장합니다.
        Args:
            state (AgentState): 테스트 생성 및 검토 과정의 현재 상태를 담고 있는 객체입니다.
        Returns:
            AgentState: 리뷰 및 개선 결과가 반영된 상태 객체를 반환합니다.
        """
        try:
            state["current_step"] = "reviewing"
            
            # 품질 검토 프롬프트
            review_prompt = ChatPromptTemplate.from_messages([
                ("system", """Review the generated tests and scenarios for:
                1. Completeness - Are all changes covered?
                2. Quality - Are tests well-structured and meaningful?
                3. Correctness - Do tests properly validate the functionality?
                4. Best practices - Do they follow testing conventions?
                
                Provide improvement suggestions and a quality score (1-10)."""),
                ("human", """Generated tests: {tests}
                Test scenarios: {scenarios}
                
                Review and provide feedback.""")
            ])
            
            tests_summary = self._summarize_tests(state["generated_tests"])
            scenarios_summary = json.dumps([
                {
                    "id": s.scenario_id,
                    "feature": s.feature,
                    "description": s.description
                }
                for s in state["test_scenarios"]
            ], indent=2)
            
            chain = review_prompt | self.llm
            review_result = await chain.ainvoke({
                "tests": tests_summary,
                "scenarios": scenarios_summary
            })
            
            state["messages"].append(review_result)
            logger.info("Test review completed")
            
        except Exception as e:
            logger.error(f"Error reviewing tests: {e}")
            state["error"] = str(e)
        
        return state
    
    def route_by_strategy(self, state: AgentState) -> str:
        """
        주어진 에이전트 상태(state)에서 테스트 전략(test_strategy)에 따라 라우팅 경로를 결정합니다.
        Args:
            state (AgentState): 테스트 전략 정보가 포함된 에이전트 상태 객체입니다.
        Returns:
            str: 테스트 전략에 따라 'unit' 또는 'integration' 문자열을 반환합니다.
                 만약 테스트 전략이 명시되지 않았거나 알 수 없는 경우 기본값으로 'unit'을 반환합니다.
        예시:
            test_strategy가 UNIT_TEST인 경우 'unit'을 반환하고,
            INTEGRATION_TEST인 경우 'integration'을 반환합니다.
            그 외의 경우에는 'unit'을 반환합니다.
        """
        strategy = state.get("test_strategy")
        
        if strategy == TestStrategy.UNIT_TEST:
            return "unit"
        elif strategy == TestStrategy.INTEGRATION_TEST:
            return "integration"
        else:
            return "unit"  # 기본값
    
    async def _generate_tests_for_file(
        self,
        file_change: FileChange,
        test_type: TestStrategy,
        rag_context: Optional[str] = None
    ) -> List[TestCase]:
        """
        특정 파일의 변경된 함수들에 대해 지정된 테스트 전략에 따라 테스트 케이스를 비동기적으로 생성합니다.
        Args:
            file_change (FileChange): 테스트를 생성할 파일의 변경 정보(경로, 변경 함수 목록, diff 등)를 담고 있는 객체입니다.
            test_type (TestStrategy): 생성할 테스트의 유형(예: 단위 테스트, 통합 테스트 등)을 지정합니다.
            rag_context (Optional[str], optional): 테스트 생성 시 참고할 추가적인 RAG(검색 증강 생성) 컨텍스트 정보입니다. 기본값은 None입니다.
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
            # 언어별 테스트 생성 프롬프트
            test_prompt = self._get_test_generation_prompt(
                file_change.language,
                test_type
            )
            
            # RAG 컨텍스트 포함
            context = f"Testing conventions:\n{rag_context}\n\n" if rag_context else ""
            
            # 변경된 함수별로 테스트 생성
            for function_name in file_change.functions_changed[:5]:  # 최대 5개
                prompt = test_prompt.format(
                    context=context,
                    file_path=file_change.file_path,
                    function_name=function_name,
                    diff_content=file_change.diff_content[:2000]  # 일부만
                )
                
                response = await self.llm.ainvoke([
                    SystemMessage(content="You are an expert test engineer."),
                    HumanMessage(content=prompt)
                ])
                
                # 테스트 코드 파싱
                test_case = self._parse_test_response(
                    response.content,
                    function_name,
                    test_type
                )
                if test_case:
                    tests.append(test_case)
            
        except Exception as e:
            logger.error(f"Error generating tests for {file_change.file_path}: {e}")
        
        return tests
    
    def _get_test_generation_prompt(
        
        self,
        language: str,
        test_type: TestStrategy
    ) -> str:
        """언어와 테스트 전략에 따라 코드 변경에 대한 테스트 케이스 생성을 위한 프롬프트 문자열을 반환합니다.
        Args:
            language (str): 테스트를 생성할 프로그래밍 언어. 예시: "python", "java", "javascript".
            test_type (TestStrategy): 생성할 테스트의 유형 또는 전략.
        Returns:
            str: 코드 변경(diff)와 함수 정보, 테스트 목적에 맞는 상세 지침이 포함된 프롬프트 문자열.
                 언어별로 pytest, JUnit 5, Jest 등 적합한 테스트 프레임워크와 작성 방식이 추가 안내됩니다.
        설명:
            이 함수는 코드 변경(diff)와 함수 정보, 테스트 목적에 맞는 상세 지침이 포함된 프롬프트를 반환합니다.
            반환되는 프롬프트에는 테스트 이름, 설명, 코드, 검증(assertion), 필요한 의존성/임포트 등 테스트 케이스 작성에 필요한 모든 요소가 포함됩니다.
            언어별로 적합한 테스트 프레임워크와 작성 방식(예: pytest, JUnit 5, Jest 등)이 추가 안내되어,
            LLM이 해당 언어와 전략에 맞는 테스트 코드를 생성할 수 있도록 돕습니다."""
        
        base_prompt =  dedent("""{context}
        Generate a {test_type} test for the following code change:
        
        File: {file_path}
        Function: {function_name}
        
        Code diff:
        ```
        {diff_content}
        ```
        
        Generate a complete test case with:
        1. Test name
        2. Test description
        3. Test code
        4. Assertions
        5. Required dependencies/imports
        """)
        
        # 언어별 커스터마이징
        if language == "python":
            base_prompt += "\n\nUse pytest framework with proper fixtures and assertions."
        elif language == "java":
            base_prompt += "\n\nUse JUnit 5 with appropriate annotations and assertions."
        elif language == "javascript":
            base_prompt += "\n\nUse Jest framework with proper describe/it blocks."
        
        return base_prompt
    
    def _parse_test_response(
        self,
        response: str,
        function_name: str,
        test_type: TestStrategy
    ) -> Optional[TestCase]:
        """LLM 응답에서 테스트 케이스 파싱"""
        try:
            # 간단한 파싱 로직 (실제로는 더 정교하게)
            return TestCase(
                name=f"test_{function_name}",
                description=f"Test for {function_name}",
                test_type=test_type,
                code=response,
                assertions=[],
                dependencies=[],
                priority=3
            )
        except Exception as e:
            logger.error(f"Error parsing test response: {e}")
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
    
    @observe(name="generate_tests")
    async def generate_tests(
        self,
        commit_analysis: CommitAnalysis,
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        메인 테스트 생성 함수
        
        Args:
            commit_analysis: 커밋 분석 결과
            rag_context: RAG에서 검색한 컨텍스트
            
        Returns:
            생성된 테스트와 시나리오
        """
        with LogContext(f"Generating tests for commit {commit_analysis.commit_hash[:8]}"):
            # 초기 상태 생성
            initial_state: AgentState = {
                "messages": [],
                "file_changes": commit_analysis.files_changed,
                "commit_analysis": commit_analysis,
                "test_strategy": None,
                "generated_tests": [],
                "test_scenarios": [],
                "rag_context": rag_context,
                "error": None,
                "current_step": "starting"
            }
            
            # 워크플로우 실행
            try:
                final_state = await self.graph.ainvoke(initial_state)
                
                if final_state.get("error"):
                    logger.error(f"Workflow error: {final_state['error']}")
                
                return {
                    "tests": final_state["generated_tests"],
                    "scenarios": final_state["test_scenarios"],
                    "messages": final_state["messages"],
                    "error": final_state.get("error")
                }
                
            except Exception as e:
                logger.error(f"Error in test generation workflow: {e}")
                return {
                    "tests": [],
                    "scenarios": [],
                    "messages": [],
                    "error": str(e)
                }