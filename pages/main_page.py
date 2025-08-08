import streamlit as st

def main_page():
    """메인 페이지"""
    st.title("🏠 메인 페이지")
    
    # 환영 메시지
    st.markdown("""
    ## 환영합니다! 👋
    
    이 앱은 **LangChain**과 **Azure**를 활용한 AI 기반 애플리케이션입니다.
    """)
    
    # 기능 소개 카드
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **🤖 AI 기능**
        
        Azure OpenAI를 활용한
        강력한 AI 기능
        """)
        
    with col2:
        st.success("""
        **🔗 LangChain**
        
        체인 기반의 
        구조화된 AI 워크플로우
        """)
        
    with col3:
        st.warning("""
        **☁️ Azure 통합**
        
        클라우드 기반의
        확장 가능한 인프라
        """)
    
    st.divider()
    
    # 최근 활동
    st.markdown("### 📈 대시보드")
    
    # 메트릭 표시
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 작업", "0", "0")
    with col2:
        st.metric("완료", "0", "0")
    with col3:
        st.metric("진행중", "0", "0")
    with col4:
        st.metric("성공률", "0%", "0%")
    
    # 빠른 시작 버튼
    st.markdown("### 🚀 빠른 시작")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("새 작업 시작", type="primary", use_container_width=True):
            st.switch_page("pages/work_page.py")
            
    with col2:
        if st.button("설정 확인", use_container_width=True):
            st.session_state.show_settings = True
            st.rerun()