"""
Configuration Management Module

환경 변수 및 설정 파일을 관리하는 모듈
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI 서비스 설정"""
    endpoint: str
    api_key: str
    deployment_name_agent: str
    deployment_name_rag: str
    deployment_name_embedding: str
    api_version: str
    
    @classmethod
    def from_env(cls) -> 'AzureOpenAIConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            deployment_name_agent=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_AGENT'),
            deployment_name_rag=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_RAG'),
            deployment_name_embedding=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_TEXT_EMBEDDING'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION')
        )




@dataclass
class AppConfig:
    """애플리케이션 전체 설정"""
    output_directory: Path
    temp_directory: Path
    log_level: str
    max_concurrent_requests: int
    request_timeout: int
    retry_attempts: int
    cache_ttl: int
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            output_directory=Path(os.getenv('OUTPUT_DIRECTORY', './output')),
            temp_directory=Path(os.getenv('TEMP_DIRECTORY', './temp')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            max_concurrent_requests=int(os.getenv('MAX_CONCURRENT_REQUESTS', '5')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '60')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            cache_ttl=int(os.getenv('CACHE_TTL', '3600'))
        )


class Config:
    """통합 설정 관리 클래스"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        설정 초기화
        
        Args:
            config_file: 설정 파일 경로 (선택사항)
        """
        # 기본 환경 변수에서 로드
        self.azure_openai = AzureOpenAIConfig.from_env()
        self.app = AppConfig.from_env()
        
        # 설정 파일이 있으면 오버라이드
        if config_file:
            self.load_from_file(config_file)
        
        # 디렉토리 생성
        self.app.output_directory.mkdir(parents=True, exist_ok=True)
        self.app.temp_directory.mkdir(parents=True, exist_ok=True)
    
    def load_from_file(self, config_file: str):
        """설정 파일에서 설정 로드"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 설정 업데이트
        self._update_from_dict(data)
    
    def _update_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 설정 업데이트"""
        if 'azure_openai' in data:
            for key, value in data['azure_openai'].items():
                if hasattr(self.azure_openai, key):
                    setattr(self.azure_openai, key, value)
        
        
        if 'app' in data:
            for key, value in data['app'].items():
                if hasattr(self.app, key):
                    if key.endswith('_directory'):
                        value = Path(value)
                    setattr(self.app, key, value)
    
    def validate(self) -> List[str]:
        """설정 유효성 검증"""
        errors = []
        
        # Azure OpenAI 설정 검증
        if not self.azure_openai.endpoint:
            errors.append("Azure OpenAI endpoint is not configured")
        if not self.azure_openai.api_key:
            errors.append("Azure OpenAI API key is not configured")
        
        
        return errors
