"""
Core modules for AI Test Generator
"""


# from .svn_analyzer import SvnAnalyzer  # pysvn 의존성 문제로 비활성화
from .git_analyzer import GitAnalyzer
from .llm_agent import LLMAgent, TestCase, TestStrategy, TestScenario
from .vcs_models import FileChange, CommitAnalysis

__all__ = [
    "GitAnalyzer",
    "CommitAnalysis", 
    "FileChange",
    # "SvnAnalyzer",  # pysvn 의존성 문제로 비활성화
    "LLMAgent",
    "TestCase",
    "TestStrategy",
    "TestScenario",
]