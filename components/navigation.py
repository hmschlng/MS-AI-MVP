import streamlit as st
from utils.azure_client import get_azure_client

def setup_navigation():
    """사이드바 네비게이션 설정"""
    with st.sidebar:
        st.title("🚀 MVP App")
        st.divider()
        
        # 페이지 선택
        page = st.radio(
            "페이지 선택",
            ["메인", "작업"],
            index=0
        )
        
        st.divider()
        
        # 설정 버튼
        if st.button("⚙️ 설정"):
            st.session_state.show_settings = True
            
        # 상태 섹션
        st.markdown("---")
        st.markdown("### 📊 Azure OpenAI 상태")
        
        # Azure OpenAI 연결 상태 확인
        client = get_azure_client()
        if client.is_connected():
            st.success("✅ 연결됨")
            
            # 빠른 연결 테스트 버튼
            if st.button("🔍 연결 테스트", use_container_width=True):
                with st.spinner("테스트 중..."):
                    success, message = client.test_connection()
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        else:
            st.error("❌ 설정 필요")
            if st.button("⚙️ 설정하기", use_container_width=True):
                st.session_state.show_settings = True
                st.rerun()
        
    return page