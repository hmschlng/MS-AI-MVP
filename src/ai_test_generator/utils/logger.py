"""
Logging Utility Module

애플리케이션 전체에서 사용할 로깅 설정 및 유틸리티
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console


# 전역 콘솔 객체
console = Console()

# 로거 이름
LOGGER_NAME = "ai_test_generator"


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    use_rich: bool = True
) -> logging.Logger:
    """
    로거 설정
    
    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (선택사항)
        use_rich: Rich 핸들러 사용 여부
        
    Returns:
        설정된 로거 객체
    """
    # 로거 가져오기
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 기존 핸들러 제거
    logger.handlers.clear()
    
    # 포맷 설정
    if use_rich:
        # Rich 핸들러 (콘솔 출력)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True
        )
        rich_handler.setLevel(getattr(logging, log_level.upper()))
        logger.addHandler(rich_handler)
    else:
        # 기본 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택사항)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 로그 저장
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    로거 인스턴스 가져오기
    
    Args:
        name: 하위 로거 이름 (선택사항)
        
    Returns:
        로거 객체
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)


def log_execution_time(func):
    """함수 실행 시간을 로깅하는 데코레이터"""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        try:
            logger.debug(f"Starting {func.__name__}")
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed_time:.2f} seconds")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed after {elapsed_time:.2f} seconds: {str(e)}"
            )
            raise
    
    return wrapper


class LogContext:
    """로깅 컨텍스트 관리자"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        """
        로깅 컨텍스트 초기화
        
        Args:
            operation: 작업 이름
            logger: 사용할 로거 (선택사항)
        """
        self.operation = operation
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        """컨텍스트 진입"""
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation} in {elapsed_time:.2f} seconds"
            )
        else:
            self.logger.error(
                f"Failed {self.operation} after {elapsed_time:.2f} seconds: {exc_val}"
            )
        
        return False  # 예외를 다시 발생시킴


# 기본 로거 설정
_default_logger = None


def initialize_default_logger(log_level: str = "INFO", log_file: Optional[str] = None):
    """기본 로거 초기화"""
    global _default_logger
    _default_logger = setup_logger(log_level, log_file)
    return _default_logger


# 모듈 임포트 시 기본 로거 설정
initialize_default_logger()
