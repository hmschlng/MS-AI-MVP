import os
from typing import Optional
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

class AzureOpenAISettings:
    """Azure OpenAI 설정 관리 클래스"""
    
    def __init__(self):
        self.endpoint = self._get_setting("AZURE_OPENAI_ENDPOINT")
        self.api_key = self._get_setting("AZURE_OPENAI_API_KEY")
        self.deployment_name = self._get_setting("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = self._get_setting("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
    def _get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """환경변수 또는 Streamlit 세션에서 설정 값 가져오기"""
        # 1. Streamlit 세션 상태에서 먼저 확인
        session_key = key.lower().replace("azure_openai_", "azure_").replace("_", "_")
        if session_key in st.session_state:
            return st.session_state[session_key]
        
        # 2. 환경변수에서 확인
        return os.getenv(key, default)
    
    def is_configured(self) -> bool:
        """Azure OpenAI가 올바르게 설정되었는지 확인"""
        return all([
            self.endpoint,
            self.api_key,
            self.deployment_name
        ])
    
    def get_client_config(self) -> dict:
        """Azure OpenAI 클라이언트 설정 반환"""
        return {
            "azure_endpoint": self.endpoint,
            "api_key": self.api_key,
            "api_version": self.api_version
        }

class AppSettings:
    """앱 전체 설정 관리"""
    
    def __init__(self):
        self.azure_openai = AzureOpenAISettings()
        self.temperature = float(st.session_state.get("temperature", 0.7))
        self.max_tokens = int(st.session_state.get("max_tokens", 1000))
        
    def update_from_session(self):
        """세션 상태에서 설정 업데이트"""
        self.temperature = float(st.session_state.get("temperature", 0.7))
        self.max_tokens = int(st.session_state.get("max_tokens", 1000))