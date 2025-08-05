import streamlit as st
from utils.azure_client import get_azure_client

def settings_modal():
    """설정 모달 컴포넌트"""
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False
        
    if st.session_state.show_settings:
        with st.container():
            st.markdown("## ⚙️ 설정")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("### Azure OpenAI 설정")
                azure_endpoint = st.text_input("Azure OpenAI Endpoint", 
                                             value=st.session_state.get("azure_endpoint", ""),
                                             help="예: https://your-resource.openai.azure.com/")
                azure_api_key = st.text_input("Azure API Key", 
                                            type="password",
                                            value=st.session_state.get("azure_api_key", ""))
                azure_deployment = st.text_input("Deployment Name",
                                               value=st.session_state.get("azure_deployment", ""),
                                               help="Azure OpenAI에서 생성한 배포 이름")
                
                st.markdown("### 일반 설정")
                temperature = st.slider("Temperature", 0.0, 2.0, 
                                       value=st.session_state.get("temperature", 0.7),
                                       help="응답의 창의성 조절 (0: 결정적, 2: 창의적)")
                max_tokens = st.number_input("Max Tokens", 100, 4000, 
                                           value=st.session_state.get("max_tokens", 1000),
                                           help="최대 응답 토큰 수")
                
            with col2:
                if st.button("🔍 연결 테스트"):
                    if azure_endpoint and azure_api_key and azure_deployment:
                        # 임시로 세션에 저장하여 테스트
                        st.session_state.azure_endpoint = azure_endpoint
                        st.session_state.azure_api_key = azure_api_key
                        st.session_state.azure_deployment = azure_deployment
                        
                        # 클라이언트 다시 로드
                        client = get_azure_client()
                        client.reload_settings()
                        
                        # 연결 테스트
                        with st.spinner("연결 테스트 중..."):
                            success, message = client.test_connection()
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                    else:
                        st.warning("모든 Azure 설정을 입력해주세요.")
                
                if st.button("💾 저장"):
                    st.session_state.azure_endpoint = azure_endpoint
                    st.session_state.azure_api_key = azure_api_key
                    st.session_state.azure_deployment = azure_deployment
                    st.session_state.temperature = temperature
                    st.session_state.max_tokens = max_tokens
                    
                    # 클라이언트 설정 다시 로드
                    client = get_azure_client()
                    client.reload_settings()
                    
                    st.success("설정이 저장되었습니다!")
                    
                if st.button("❌ 닫기"):
                    st.session_state.show_settings = False
                    st.rerun()