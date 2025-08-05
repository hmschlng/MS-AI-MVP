import streamlit as st

def settings_modal():
    """설정 모달 컴포넌트"""
    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False
        
    if st.session_state.show_settings:
        with st.container():
            st.markdown("## ⚙️ 설정")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("### Azure 설정")
                azure_endpoint = st.text_input("Azure OpenAI Endpoint", 
                                             value=st.session_state.get("azure_endpoint", ""))
                azure_api_key = st.text_input("Azure API Key", 
                                            type="password",
                                            value=st.session_state.get("azure_api_key", ""))
                azure_deployment = st.text_input("Deployment Name",
                                               value=st.session_state.get("azure_deployment", ""))
                
                st.markdown("### 일반 설정")
                temperature = st.slider("Temperature", 0.0, 2.0, 
                                       value=st.session_state.get("temperature", 0.7))
                max_tokens = st.number_input("Max Tokens", 100, 4000, 
                                           value=st.session_state.get("max_tokens", 1000))
                
            with col2:
                if st.button("💾 저장"):
                    st.session_state.azure_endpoint = azure_endpoint
                    st.session_state.azure_api_key = azure_api_key
                    st.session_state.azure_deployment = azure_deployment
                    st.session_state.temperature = temperature
                    st.session_state.max_tokens = max_tokens
                    st.success("설정이 저장되었습니다!")
                    
                if st.button("❌ 닫기"):
                    st.session_state.show_settings = False
                    st.rerun()