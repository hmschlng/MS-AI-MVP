"""
AI Test Generator

테스트코드 및 테스트 시나리오 자동 생성 도우미
"""

__version__ = "0.1.0"
__author__ = "AI Test Generator Team"

# Core modules - Version Control System analyzers
from .core.git_analyzer import GitAnalyzer
from .core.svn_analyzer import SvnAnalyzer

# Core modules - AI/ML components
from .core.llm_agent import LLMAgent, TestCase, TestStrategy, TestScenario

# Core modules - Data models
from .core.vcs_models import FileChange, CommitAnalysis

# Utility modules - Configuration and logging
from .utils.config import Config
from .utils.logger import get_logger, setup_logger, LogContext
from .utils.prompt_loader import PromptLoader

__all__ = [
    # Version Control System analyzers
    "GitAnalyzer",
    "SvnAnalyzer",
    
    # AI/ML components
    "LLMAgent",
    "TestCase",
    "TestStrategy", 
    "TestScenario",
    
    # Data models
    "FileChange",
    "CommitAnalysis",
    
    # Configuration and utilities
    "Config",
    "get_logger",
    "setup_logger",
    "LogContext",
    "PromptLoader",
    
    # Convenience functions
    "create_git_analyzer",
    "create_llm_agent", 
    "setup_default_logger",
]


# Convenience functions for easy module usage
def create_git_analyzer(repo_path: str = ".") -> GitAnalyzer:
    """
    Git 저장소 분석기를 생성합니다.
    
    Args:
        repo_path: Git 저장소 경로 (기본값: 현재 디렉토리)
        
    Returns:
        GitAnalyzer 인스턴스
    """
    return GitAnalyzer(repo_path)


def create_llm_agent(config_path: str = None) -> LLMAgent:
    """
    LLM 에이전트를 생성합니다.
    
    Args:
        config_path: 설정 파일 경로 (기본값: None, 환경변수 사용)
        
    Returns:
        LLMAgent 인스턴스
    """
    config = Config.from_file(config_path) if config_path else Config.from_env()
    return LLMAgent(config)


def setup_default_logger(name: str = None, level: str = "INFO") -> None:
    """
    기본 로거를 설정합니다.
    
    Args:
        name: 로거 이름 (기본값: None, 루트 로거 사용)
        level: 로그 레벨 (기본값: INFO)
    """
    import logging
    setup_logger(name or __name__, level=getattr(logging, level.upper()))


# Module metadata
__title__ = "AI Test Generator"
__description__ = "테스트코드 및 테스트 시나리오 자동 생성 도우미"
__url__ = "https://github.com/hmschlng/MS-AI-MVP"
__author_email__ = "hmschlng@naver.com"
