import streamlit as st

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
            
        # 정보 섹션
        st.markdown("---")
        st.markdown("### 📊 상태")
        st.success("연결됨")
        
    return page