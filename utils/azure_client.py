from typing import Optional, Dict, Any
import streamlit as st
from openai import AzureOpenAI
from config.settings import AppSettings

class AzureOpenAIClient:
    """Azure OpenAI 클라이언트 관리 클래스"""
    
    def __init__(self):
        self.client: Optional[AzureOpenAI] = None
        self.settings = AppSettings()
        self._initialize_client()
    
    def _initialize_client(self):
        """Azure OpenAI 클라이언트 초기화"""
        try:
            if self.settings.azure_openai.is_configured():
                config = self.settings.azure_openai.get_client_config()
                self.client = AzureOpenAI(
                    azure_endpoint=config["azure_endpoint"],
                    api_key=config["api_key"],
                    api_version=config["api_version"]
                )
        except Exception as e:
            st.error(f"Azure OpenAI 클라이언트 초기화 실패: {str(e)}")
            self.client = None
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None and self.settings.azure_openai.is_configured()
    
    def test_connection(self) -> tuple[bool, str]:
        """연결 테스트"""
        if not self.is_connected():
            return False, "Azure OpenAI가 설정되지 않았습니다."
        
        try:
            # 간단한 테스트 요청
            response = self.client.chat.completions.create(
                model=self.settings.azure_openai.deployment_name,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return True, "연결 성공!"
        except Exception as e:
            return False, f"연결 실패: {str(e)}"
    
    def chat_completion(self, messages: list, **kwargs) -> Optional[Any]:
        """채팅 완성 요청"""
        if not self.is_connected():
            raise Exception("Azure OpenAI가 연결되지 않았습니다.")
        
        try:
            # 기본 설정 적용
            default_params = {
                "model": self.settings.azure_openai.deployment_name,
                "messages": messages,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens
            }
            
            # 추가 파라미터 병합
            default_params.update(kwargs)
            
            response = self.client.chat.completions.create(**default_params)
            return response
        except Exception as e:
            st.error(f"채팅 완성 요청 실패: {str(e)}")
            return None
    
    def chat_completion_stream(self, messages: list, **kwargs):
        """스트리밍 채팅 완성 요청"""
        if not self.is_connected():
            raise Exception("Azure OpenAI가 연결되지 않았습니다.")
        
        try:
            default_params = {
                "model": self.settings.azure_openai.deployment_name,
                "messages": messages,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "stream": True
            }
            
            default_params.update(kwargs)
            
            stream = self.client.chat.completions.create(**default_params)
            return stream
        except Exception as e:
            st.error(f"스트리밍 채팅 완성 요청 실패: {str(e)}")
            return None
    
    def reload_settings(self):
        """설정 다시 로드 및 클라이언트 재초기화"""
        self.settings = AppSettings()
        self._initialize_client()

# 전역 클라이언트 인스턴스
@st.cache_resource
def get_azure_client() -> AzureOpenAIClient:
    """캐시된 Azure OpenAI 클라이언트 인스턴스 반환"""
    return AzureOpenAIClient()