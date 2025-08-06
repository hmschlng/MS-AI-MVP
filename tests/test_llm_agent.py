import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_test_generator.core.vcs_models import FileChange, CommitAnalysis
from ai_test_generator.utils.config import Config
from datetime import datetime
from dotenv import load_dotenv
import os

from ai_test_generator.core.llm_agent import (
    LLMAgent, TestCase, TestStrategy, TestScenario, AgentState
)

@pytest.fixture
def dummy_config():
    class DummyAzureOpenAI:
        load_dotenv()
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "dummy")
        deployment_name_agent = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME_AGENT", "dummy-deploy")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
    class DummyConfig:
        azure_openai = DummyAzureOpenAI()
    return DummyConfig()

@pytest.fixture
def llm_agent(dummy_config):
    with patch("ai_test_generator.core.llm_agent.AzureChatOpenAI") as mock_llm, \
         patch("ai_test_generator.core.llm_agent.Langfuse"):
        agent = LLMAgent(dummy_config)
        # Patch async LLM methods
        agent.llm.ainvoke = AsyncMock(return_value=MagicMock(content="test code"))
        agent.analysis_llm.ainvoke = AsyncMock(return_value=MagicMock(content="analysis"))
        return agent

@pytest.fixture
def file_change():
    return FileChange(
        file_path="src/foo.py",
        change_type="modified",
        additions=10,
        deletions=2,
        diff_content="def foo():\n    return 42",
        language="python",
        functions_changed=["foo"],
        classes_changed=[]
    )

@pytest.fixture
def commit_analysis(file_change):
    return CommitAnalysis(
        commit_hash="abc123",
        author="Alice",
        author_email="alice@example.com",
        commit_date=datetime.now(),
        message="Update foo",
        files_changed=[file_change],
        total_additions=10,
        total_deletions=2,
        branch="main",
        tags=[]
    )

@pytest.mark.asyncio
async def test_analyze_changes_success(llm_agent, file_change):
    state = AgentState(
        messages=[],
        file_changes=[file_change],
        commit_analysis=None,
        test_strategy=None,
        generated_tests=[],
        test_scenarios=[],
        rag_context=None,
        error=None,
        current_step=""
    )
    result = await llm_agent.analyze_changes(state)
    assert "analyzing_changes" == result["current_step"]
    assert result["messages"]
    assert result["error"] is None

@pytest.mark.asyncio
async def test_analyze_changes_exception(llm_agent, file_change):
    llm_agent.analysis_llm.ainvoke = AsyncMock(side_effect=Exception("fail"))
    state = AgentState(
        messages=[],
        file_changes=[file_change],
        commit_analysis=None,
        test_strategy=None,
        generated_tests=[],
        test_scenarios=[],
        rag_context=None,
        error=None,
        current_step=""
    )
    result = await llm_agent.analyze_changes(state)
    assert result["error"] is not None

def test_route_by_strategy(llm_agent):
    state = {"test_strategy": TestStrategy.UNIT_TEST}
    assert llm_agent.route_by_strategy(state) == "unit"
    state = {"test_strategy": TestStrategy.INTEGRATION_TEST}
    assert llm_agent.route_by_strategy(state) == "integration"
    state = {"test_strategy": None}
    assert llm_agent.route_by_strategy(state) == "unit"

def test_group_related_files(llm_agent, file_change):
    fc2 = FileChange(
        file_path="src/foo_test.py",
        change_type="modified",
        additions=1,
        deletions=0,
        diff_content="def test_foo(): pass",
        language="python",
        functions_changed=["test_foo"],
        classes_changed=[]
    )
    groups = llm_agent._group_related_files([file_change, fc2])
    assert isinstance(groups, list)

def test_are_files_related(llm_agent, file_change):
    fc2 = FileChange(
        file_path="src/foo_test.py",
        change_type="modified",
        additions=1,
        deletions=0,
        diff_content="def test_foo(): pass",
        language="python",
        functions_changed=["test_foo"],
        classes_changed=[]
    )
    assert llm_agent._are_files_related(file_change, fc2) is True

def test_create_integration_context(llm_agent, file_change):
    context = llm_agent._create_integration_context([file_change])
    assert "src/foo.py" in context

@pytest.mark.asyncio
async def test__generate_integration_tests_for_group(llm_agent, file_change):
    tests = await llm_agent._generate_integration_tests_for_group(
        main_file=file_change,
        file_group=[file_change],
        integration_context="context"
    )
    assert isinstance(tests, list)
    assert tests and isinstance(tests[0], TestCase)

def test__get_test_generation_prompt(llm_agent):
    prompt = llm_agent._get_test_generation_prompt("python", TestStrategy.UNIT_TEST)
    assert "pytest" in prompt
    prompt = llm_agent._get_test_generation_prompt("java", TestStrategy.UNIT_TEST)
    assert "JUnit" in prompt

def test__parse_test_response(llm_agent):
    tc = llm_agent._parse_test_response("code", "foo", TestStrategy.UNIT_TEST)
    assert isinstance(tc, TestCase)
    assert tc.name == "test_foo"

def test__summarize_changes(llm_agent, file_change):
    summary = llm_agent._summarize_changes([file_change])
    assert "src/foo.py" in summary

def test__summarize_tests(llm_agent):
    tests = [
        TestCase(
            name="test_foo",
            description="desc",
            test_type=TestStrategy.UNIT_TEST,
            code="code",
            assertions=[],
            dependencies=[],
            priority=1
        )
    ]
    summary = llm_agent._summarize_tests(tests)
    assert "Total tests generated" in summary

@pytest.mark.asyncio
async def test__generate_tests_for_file(llm_agent, file_change):
    tests = await llm_agent._generate_tests_for_file(file_change, TestStrategy.UNIT_TEST)
    assert isinstance(tests, list)