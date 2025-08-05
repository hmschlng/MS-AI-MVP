import streamlit as st
from components.navigation import setup_navigation
from pages.main_page import main_page
from pages.work_page import work_page
from components.settings_modal import settings_modal

def main():
    st.set_page_config(
        page_title="MVP App",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 사이드바 네비게이션 설정
    page = setup_navigation()
    
    # 설정 모달
    settings_modal()
    
    # 페이지 라우팅
    if page == "메인":
        main_page()
    elif page == "작업":
        work_page()

if __name__ == "__main__":
    main()