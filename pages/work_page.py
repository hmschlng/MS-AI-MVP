import streamlit as st

def work_page():
    """작업 페이지"""
    st.title("🔧 작업 페이지")
    
    # 작업 영역 탭
    tab1, tab2, tab3 = st.tabs(["💬 채팅", "📄 문서 처리", "📊 분석"])
    
    with tab1:
        st.markdown("### AI 채팅")
        
        # 채팅 메시지 표시 영역
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # 채팅 입력
        if prompt := st.chat_input("메시지를 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # AI 응답 (임시)
            with st.chat_message("assistant"):
                response = "안녕하세요! Azure OpenAI 설정을 완료한 후 사용해주세요."
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    with tab2:
        st.markdown("### 문서 처리")
        
        # 파일 업로드
        uploaded_file = st.file_uploader(
            "파일을 업로드하세요",
            type=['txt', 'pdf', 'docx', 'md'],
            help="지원 형식: TXT, PDF, DOCX, MD"
        )
        
        if uploaded_file is not None:
            st.success(f"파일 업로드 완료: {uploaded_file.name}")
            
            # 처리 옵션
            col1, col2 = st.columns(2)
            with col1:
                chunk_size = st.number_input("청크 크기", 100, 2000, 1000)
            with col2:
                overlap = st.number_input("오버랩", 0, 500, 200)
                
            if st.button("문서 처리 시작", type="primary"):
                with st.spinner("문서를 처리중입니다..."):
                    st.success("문서 처리가 완료되었습니다!")
    
    with tab3:
        st.markdown("### 데이터 분석")
        
        # 분석 옵션
        analysis_type = st.selectbox(
            "분석 유형",
            ["텍스트 요약", "감정 분석", "키워드 추출", "질문 답변"]
        )
        
        input_text = st.text_area(
            "분석할 텍스트를 입력하세요",
            height=200,
            placeholder="여기에 텍스트를 입력하세요..."
        )
        
        if st.button("분석 시작", type="primary") and input_text:
            with st.spinner(f"{analysis_type} 진행중..."):
                st.info(f"{analysis_type} 결과가 여기에 표시됩니다. Azure OpenAI 설정을 완료해주세요.")
    
    # 작업 히스토리
    st.divider()
    st.markdown("### 📋 작업 히스토리")
    
    if "work_history" not in st.session_state:
        st.session_state.work_history = []
    
    if st.session_state.work_history:
        for i, work in enumerate(st.session_state.work_history):
            with st.expander(f"작업 {i+1}: {work['type']}"):
                st.write(f"시간: {work['timestamp']}")
                st.write(f"상태: {work['status']}")
    else:
        st.info("아직 작업 히스토리가 없습니다.")