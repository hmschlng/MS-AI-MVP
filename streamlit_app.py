"""
Streamlit UI Application - 대화형 테스트 생성 인터페이스

사용자가 웹 브라우저에서 직접 커밋을 선택하고, 단계별로 테스트 생성 과정을 모니터링할 수 있는 UI를 제공합니다.
"""
import asyncio
import json
import os
import tempfile
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu

# 프로젝트 루트를 Python 경로에 추가
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ai_test_generator.core.commit_selector import CommitSelector, CommitInfo
from src.ai_test_generator.core.pipeline_stages import (
    PipelineOrchestrator, PipelineContext, PipelineStage, StageStatus
)
from src.ai_test_generator.utils.config import Config
from src.ai_test_generator.utils.logger import setup_logger, get_logger

# 로거 초기화
log_level = os.getenv('LOG_LEVEL', 'INFO')
log_file = 'logs/streamlit_app.log'
setup_logger(log_level, log_file=log_file)
logger = get_logger(__name__)

# 페이지 설정
st.set_page_config(
    page_title="AI 테스트 생성기",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
def init_session_state():
    """세션 상태 초기화"""
    if 'config' not in st.session_state:
        st.session_state.config = Config()
    
    if 'commit_selector' not in st.session_state:
        st.session_state.commit_selector = None
    
    if 'pipeline_orchestrator' not in st.session_state:
        st.session_state.pipeline_orchestrator = None
    
    if 'pipeline_context' not in st.session_state:
        st.session_state.pipeline_context = None
    
    if 'pipeline_results' not in st.session_state:
        st.session_state.pipeline_results = {}
    
    if 'selected_commits' not in st.session_state:
        st.session_state.selected_commits = []
    
    if 'current_stage' not in st.session_state:
        st.session_state.current_stage = None
    
    if 'progress_logs' not in st.session_state:
        st.session_state.progress_logs = []

init_session_state()


def show_sidebar_info():
    """사이드바에 저장소 및 선택된 커밋 정보 표시"""
    # 저장소 정보가 있는 경우에만 표시
    if st.session_state.get('repo_path'):
        st.markdown("---")
        
        # 저장소 정보 카드 (구획화)
        with st.container():
            st.markdown("""
            <div style="background-color: #1f2937; padding: 15px; border-radius: 10px; border-left: 4px solid #3b82f6; margin: 10px 0;">
            <h4 style="margin-top: 0; color: #60a5fa;">🏠 저장소 정보</h4>
            """, unsafe_allow_html=True)
            
            repo_type = st.session_state.get('repo_type', 'unknown')
            
            if repo_type == 'local':
                st.markdown(f"""
                **📂 로컬 저장소 사용중..**  
                
                **📍 로컬 경로**  
                `{st.session_state.repo_path}`
                
                **🌿 브랜치**  
                `{st.session_state.branch}`
                """)
            elif repo_type == 'remote':
                st.markdown(f"""
                **🌐 원격 저장소 사용중..**  
                
                **🔗 원격 URL**  
                `{st.session_state.repo_url}`
                
                **📁 로컬 캐시**  
                `{st.session_state.repo_path}`
                
                **🌿 브랜치**  
                `{st.session_state.branch}`
                """)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    # 선택된 커밋 정보
    if st.session_state.get('selected_commits'):
        # 선택된 커밋 목록 (구획화)
        with st.container():
            st.markdown(f"""
            <div style="background-color: #1f2937; padding: 15px; border-radius: 10px; border-left: 4px solid #10b981; margin: 10px 0;">
            <h4 style="margin-top: 0; color: #34d399;">📝 선택된 커밋 ({len(st.session_state.selected_commits)}개)</h4>
            """, unsafe_allow_html=True)
            
            # 커밋 세부 정보를 표시하기 위해 commit_selector 사용
            if st.session_state.get('commit_selector'):
                commit_selector = st.session_state.commit_selector
                try:
                    # 커밋 목록 가져오기
                    commits = commit_selector.get_commit_list(max_commits=100)
                    
                    # 선택된 커밋들을 더 예쁘게 표시
                    for i, commit_hash in enumerate(st.session_state.selected_commits[:5], 1):  # 최대 5개만 표시
                        commit = next((c for c in commits if c.hash == commit_hash), None)
                        if commit:
                            st.markdown(f"""
                            <div style="background-color: #374151; padding: 10px; border-radius: 6px; margin: 8px 0;">
                            <div style="color: #f3f4f6; font-weight: bold;">{i}. {commit.short_hash}</div>
                            <div style="color: #d1d5db; font-size: 0.85em; margin: 5px 0;">💬 {commit.message[:35]}{'...' if len(commit.message) > 35 else ''}</div>
                            <div style="color: #9ca3af; font-size: 0.8em;">
                            👤 {commit.author.split()[0] if commit.author else 'Unknown'} • 
                            📅 {commit.date.strftime('%m-%d %H:%M')}
                            </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    if len(st.session_state.selected_commits) > 5:
                        st.markdown(f"""
                        <div style="color: #9ca3af; text-align: center; margin: 10px 0;">
                        ... 외 {len(st.session_state.selected_commits) - 5}개 더
                        </div>
                        """, unsafe_allow_html=True)
                except:
                    # 커밋 정보를 가져올 수 없는 경우 간단히 표시
                    for i, commit_hash in enumerate(st.session_state.selected_commits[:5], 1):
                        st.markdown(f"{i}. `{commit_hash[:8]}`")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # 액션 버튼 (구획화)
        with st.container():
            st.markdown("""
            <div style="margin: 15px 0;">
            """, unsafe_allow_html=True)
            
            if st.button("🗑️ 선택 초기화", use_container_width=True, type="secondary"):
                st.session_state.selected_commits = []
                st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)


def main():
    """메인 애플리케이션"""
    st.title("🤖 AI Test Generator")
    st.markdown("#### 코드 변경사항을 기반으로 AI가 자동으로 테스트를 생성합니다.\n\n"
                "이 도구는 개발자의 커밋 내역을 분석하여, 변경된 코드에 맞는 테스트를 쉽고 빠르게 만들어줍니다.\n"
                "아래 단계에 따라 저장소를 연결하고, 원하는 커밋을 선택한 뒤, 테스트 생성 파이프라인을 실행해보세요.\n\n ---")
    
    # 사이드바 메뉴
    with st.sidebar:
        selected = option_menu(
            "메인 메뉴",
            ["저장소 설정", "커밋 선택", "파이프라인 실행"],
            icons=['folder', 'git', 'play-circle'],
            menu_icon="cast",
            default_index=0,
        )
        
        # 모든 페이지에서 사이드바 정보 표시
        show_sidebar_info()
    
    # 페이지 라우팅
    if selected == "저장소 설정":
        show_repository_setup()
    elif selected == "커밋 선택":
        show_commit_selection()
    elif selected == "파이프라인 실행":
        show_pipeline_execution()


def show_repository_setup():
    """코드 저장소 설정 페이지"""
    st.markdown("## 📁 저장소 설정")
    
    # 페이지 사용 설명 추가
    st.markdown("""
    > #### 🚀 시작하기:
    > 
    > 1. **📂 저장소 선택**: 로컬 또는 원격 Git 저장소를 선택하세요
    > 2. **🔗 연결 설정**: 저장소 경로/URL과 분석할 브랜치를 입력하세요
    > 
    > 💡 **팁**: 처음 사용하시는 경우 로컬 저장소로 시작해보세요!
    """)
    
    st.divider()
    
    # 저장소 타입 선택
    repo_type = st.radio(
        "저장소 타입",
        ["로컬 저장소", "원격 저장소"],
        horizontal=True
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if repo_type == "로컬 저장소":
            show_local_repository_setup()
        else:
            show_remote_repository_setup()
    
    with col2:
        show_configuration_status()


def show_local_repository_setup():
    """로컬 저장소 설정"""
    st.subheader("🖥️ 로컬 Git 저장소 설정")
    
    # 저장소 경로 입력
    repo_path = st.text_input(
        "저장소 경로",
        value=st.session_state.get('repo_path', ''),
        help="로컬 Git 저장소 경로를 입력하세요",
        placeholder="/path/to/your/repository"
    )
    
    # 브랜치 선택
    branch = st.text_input(
        "브랜치",
        value=st.session_state.get('branch', 'main'),
        help="분석할 브랜치 (기본값: main)"
    )
    
    # 폴더 선택 도우미
    st.markdown("💡 **안내**: 절대경로를 사용하세요. 예: `/Users/username/projects/myrepo` 또는 `C:\\Users\\username\\projects\\myrepo`")
    
    # 저장소 연결 버튼
    if st.button("🔗 로컬 저장소 연결", type="primary"):
        if repo_path and Path(repo_path).exists():
            try:
                with st.spinner("저장소 연결 및 Git 설정 확인 중..."):
                    # 1단계: Git 설정 확인을 위한 임시 CommitSelector 생성
                    temp_selector = CommitSelector.__new__(CommitSelector)
                    temp_selector.repo_path = Path(repo_path)
                    temp_selector.branch = branch
                    temp_selector.repo = None  # GitPython 초기화는 나중에
                    
                    # Git 설정 확인
                    current_config = temp_selector._check_git_encoding_config()
                    required_config = {
                        'core.quotepath': 'false',
                        'i18n.logoutputencoding': 'utf-8',
                        'i18n.commitencoding': 'utf-8'
                    }
                    
                    changes_needed = []
                    for key, required_value in required_config.items():
                        if current_config.get(key) != required_value:
                            changes_needed.append({
                                'key': key,
                                'current': current_config.get(key, 'not set'),
                                'required': required_value,
                                'description': temp_selector._get_config_description(key)
                            })
                    
                    # Git 설정 변경이 필요한 경우 사용자에게 확인
                    auto_configure = True  # 기본값
                    if changes_needed:
                        st.session_state['git_config_changes'] = changes_needed
                        st.session_state['git_config_approved'] = None  # 초기화
                        st.session_state['pending_repo_connection'] = {
                            'repo_path': repo_path,
                            'branch': branch,
                            'repo_type': 'local'
                        }
                        st.rerun()
                
                # 실제 CommitSelector 초기화 (설정 변경 후)
                commit_selector = CommitSelector(repo_path, branch)
                st.session_state.commit_selector = commit_selector
                st.session_state.repo_path = repo_path
                st.session_state.repo_url = None  # 로컬이므로 URL 초기화
                st.session_state.branch = branch
                st.session_state.repo_type = "local"
                
                # PipelineOrchestrator 초기화
                st.session_state.pipeline_orchestrator = PipelineOrchestrator(st.session_state.config)
                
                st.success("✅ 로컬 저장소 연결 성공!")
                
                # 저장소 정보 표시
                with st.expander("저장소 정보", expanded=True):
                    repo_info = get_repository_info(commit_selector)
                    display_repository_info(repo_info)
                
            except Exception as e:
                st.error(f"❌ 연결 실패: {e}")
                st.info("유효한 Git 저장소 경로인지 확인해주세요")
        else:
            st.error("❌ 시스템에 존재하는 유효한 저장소 경로를 입력해주세요")
    
    # Git 설정 변경 대화상자 처리
    if 'git_config_changes' in st.session_state and st.session_state['git_config_changes']:
        st.markdown("---")
        handle_git_config_dialog()


def show_remote_repository_setup():
    """원격 저장소 설정"""
    st.subheader("🌐 원격 Git 저장소 설정")
    
    # 원격 저장소 URL 입력
    repo_url = st.text_input(
        "저장소 URL",
        value=st.session_state.get('repo_url', ''),
        help="원격 Git 저장소 URL을 입력하세요",
        placeholder="https://github.com/username/repository.git"
    )
    
    # 브랜치 선택
    branch = st.text_input(
        "브랜치",
        value=st.session_state.get('branch', 'main'),
        help="분석할 브랜치 (기본값: main)"
    )
    
    # 인증 설정
    with st.expander("인증 설정 (필요시)"):
        auth_method = st.selectbox(
            "인증 방법",
            ["없음 (공개 저장소)", "사용자명/비밀번호", "개인 액세스 토큰"],
            help="비공개 저장소의 경우 인증 방법을 선택하세요"
        )
        
        if auth_method == "사용자명/비밀번호":
            username = st.text_input("사용자명")
            password = st.text_input("비밀번호", type="password")
        elif auth_method == "개인 액세스 토큰":
            token = st.text_input("개인 액세스 토큰", type="password", 
                                help="GitHub 개인 액세스 토큰 또는 GitLab 액세스 토큰")
    
    # URL 형식 도우미
    st.markdown("""
    💡 **지원되는 URL 형식**:
    - HTTPS: `https://github.com/user/repo.git`
    - SSH: `git@github.com:user/repo.git`  
    - GitLab: `https://gitlab.com/user/repo.git`
    - Azure DevOps: `https://dev.azure.com/org/project/_git/repo`
    """)
    
    # 원격 저장소 연결 버튼
    if st.button("🌐 원격 저장소 연결", type="primary"):
        if repo_url:
            try:
                with st.spinner("🔄 원격 저장소를 복제하고 Git 설정을 확인하는 중..."):
                    # 1단계: 원격 저장소 클론
                    from src.ai_test_generator.core.git_analyzer import GitAnalyzer
                    temp_path = GitAnalyzer.clone_remote_repo(repo_url, branch=branch)
                    
                    # 2단계: Git 설정 확인을 위한 임시 CommitSelector 생성
                    temp_selector = CommitSelector.__new__(CommitSelector)
                    temp_selector.repo_path = Path(temp_path)
                    temp_selector.branch = branch
                    temp_selector.repo = None  # GitPython 초기화는 나중에
                    
                    # Git 설정 확인
                    current_config = temp_selector._check_git_encoding_config()
                    required_config = {
                        'core.quotepath': 'false',
                        'i18n.logoutputencoding': 'utf-8',
                        'i18n.commitencoding': 'utf-8'
                    }
                    
                    changes_needed = []
                    for key, required_value in required_config.items():
                        if current_config.get(key) != required_value:
                            changes_needed.append({
                                'key': key,
                                'current': current_config.get(key, 'not set'),
                                'required': required_value,
                                'description': temp_selector._get_config_description(key)
                            })
                    
                    # Git 설정 변경이 필요한 경우 사용자에게 확인
                    if changes_needed:
                        st.session_state['git_config_changes'] = changes_needed
                        st.session_state['git_config_approved'] = None  # 초기화
                        st.session_state['pending_repo_connection'] = {
                            'repo_path': temp_path,
                            'repo_url': repo_url,
                            'branch': branch,
                            'repo_type': 'remote'
                        }
                        st.rerun()
                
                # 실제 CommitSelector 초기화 (설정 변경 후)
                commit_selector = CommitSelector(temp_path, branch)
                st.session_state.commit_selector = commit_selector
                st.session_state.repo_path = temp_path
                st.session_state.repo_url = repo_url
                st.session_state.branch = branch
                st.session_state.repo_type = "remote"
                
                # PipelineOrchestrator 초기화
                st.session_state.pipeline_orchestrator = PipelineOrchestrator(st.session_state.config)
                
                st.success("✅ Successfully connected to remote repository!")
                st.info(f"📁 Repository cloned to temporary location: {temp_path}")
                
                # 저장소 정보 표시
                with st.expander("Repository Information", expanded=True):
                    repo_info = get_repository_info(commit_selector)
                    display_repository_info(repo_info)
                
            except Exception as e:
                st.error(f"❌ 원격 저장소 연결 실패: {e}")
                st.markdown("""
                **가능한 원인들:**
                - 저장소 URL이 올바르지 않음
                - 저장소가 비공개이며 인증이 필요함
                - 네트워크 연결 문제
                - 시스템에 Git이 설치되지 않음
                """)
        else:
            st.error("❌ 유효한 저장소 URL을 입력해주세요")
    
    # Git 설정 변경 대화상자 처리 (원격 저장소도 동일하게)
    if 'git_config_changes' in st.session_state and st.session_state['git_config_changes']:
        st.markdown("---")
        handle_git_config_dialog()


@st.dialog("Git 저장소 설정 최적화")
def git_config_modal():
    """Git 설정 변경 모달 대화상자"""
    changes_needed = st.session_state['git_config_changes']
    
    st.markdown("### 🔧 Git 저장소 설정 최적화")
    
    st.markdown("""
    **한글 커밋 메시지와 파일명을 올바르게 처리하기 위해 Git 설정을 최적화합니다.**
    
    이 설정은 다음과 같은 문제를 해결합니다:
    - 한글 커밋 메시지가 깨져서 표시되는 문제
    - 한글 파일명이 이상한 문자로 표시되는 문제  
    - 커밋 로그에서 한글이 제대로 표시되지 않는 문제
    
    다음 Git 저장소 설정을 업데이트해야 합니다:
    """)
    
    # 변경사항 표시
    for i, change in enumerate(changes_needed, 1):
        with st.expander(f"설정 {i}: {change['key']}", expanded=False):
            st.text(f"설명: {change['description']}")
            st.text(f"현재 값: '{change['current']}'")
            st.text(f"필요한 값: '{change['required']}'")
    
    st.info("""
    ℹ️ **중요 안내사항:**
    - 이 설정 변경은 현재 저장소에만 적용됩니다 (로컬 설정)
    - 전역 Git 설정은 영향을 받지 않습니다
    - 나중에 이 설정을 되돌리려면: `git config --local --unset <설정명>`
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ 설정 변경 적용", type="primary", key="proceed_git_config_modal"):
            # Git 설정 변경 승인 및 모달 닫기
            st.session_state.git_config_approved = True
            st.rerun()
    
    with col2:
        if st.button("❌ 설정 변경 건너뛰기", key="skip_git_config_modal"):
            # Git 설정 변경 없이 진행 및 모달 닫기
            st.session_state.git_config_approved = False
            st.rerun()


def handle_git_config_dialog():
    """Git 설정 변경 대화상자 처리"""
    # 모달이 필요한 경우 표시
    if 'git_config_changes' in st.session_state and st.session_state.get('git_config_approved') is None:
        git_config_modal()
    
    # 사용자가 결정을 내린 경우 처리
    if st.session_state.get('git_config_approved') is not None:
        auto_configure = st.session_state.git_config_approved
        complete_repository_connection(auto_configure)
        
        # 상태 초기화
        del st.session_state.git_config_approved
        if 'git_config_changes' in st.session_state:
            del st.session_state.git_config_changes


def complete_repository_connection(auto_configure: bool):
    """저장소 연결 완료"""
    try:
        pending_connection = st.session_state.get('pending_repo_connection')
        if not pending_connection:
            st.error("No pending connection found")
            return
        
        repo_path = pending_connection['repo_path']
        branch = pending_connection['branch']
        repo_type = pending_connection['repo_type']
        
        with st.spinner("Finalizing repository connection..."):
            # CommitSelector 초기화 (Git 설정 적용)
            commit_selector = CommitSelector(repo_path, branch)
            if auto_configure:
                # 명시적으로 Git 설정 적용
                changes_needed = st.session_state['git_config_changes']
                commit_selector._setup_git_encoding(auto_configure=True)
                st.success(f"✅ Git 설정 {len(changes_needed)}개 항목이 성공적으로 적용되었습니다")
            else:
                st.info("Git 설정 최적화를 건너뛰었습니다")
            
            # 세션 상태 업데이트
            st.session_state.commit_selector = commit_selector
            st.session_state.repo_path = repo_path
            st.session_state.branch = branch
            st.session_state.repo_type = repo_type
            
            if repo_type == 'local':
                st.session_state.repo_url = None
            elif repo_type == 'remote':
                st.session_state.repo_url = pending_connection.get('repo_url')
            
            # PipelineOrchestrator 초기화
            st.session_state.pipeline_orchestrator = PipelineOrchestrator(st.session_state.config)
            
            # 정리
            del st.session_state['git_config_changes']
            del st.session_state['pending_repo_connection']
            
            if repo_type == 'remote':
                st.success("✅ 원격 저장소 연결 성공!")
                st.info(f"📁 저장소가 임시 위치에 복제되었습니다: {repo_path}")
            else:
                st.success("✅ 로컬 저장소 연결 성공!")
            
            # 저장소 정보 표시
            with st.expander("저장소 정보", expanded=True):
                repo_info = get_repository_info(commit_selector)
                display_repository_info(repo_info)
            
            st.rerun()
    
    except Exception as e:
        st.error(f"❌ Failed to complete repository connection: {e}")
        # 오류 발생시 세션 정리
        for key in ['git_config_changes', 'pending_repo_connection']:
            if key in st.session_state:
                del st.session_state[key]


def show_configuration_status():
    """설정 상태 표시"""
    st.subheader("설정 상태")
    
    # 연결 상태 표시
    if st.session_state.commit_selector:
        st.success("🟢 저장소 연결됨")
        
        repo_type = st.session_state.get('repo_type', 'unknown')
        if repo_type == 'local':
            st.info(f"📍 로컬 경로: {st.session_state.repo_path}")
        elif repo_type == 'remote':
            st.info(f"🌐 원격 URL: {st.session_state.repo_url}")
            st.info(f"📁 로컬 캐시: {st.session_state.repo_path}")
        
        st.info(f"🌿 브랜치: {st.session_state.branch}")
        
        # 저장소 관리 버튼들
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 저장소 변경"):
                # 세션 상태 초기화
                for key in ['commit_selector', 'repo_path', 'repo_url', 'branch', 'repo_type']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        
        with col2:
            if st.button("🔧 Git 설정 초기화"):
                try:
                    if st.session_state.commit_selector.reset_git_encoding_config():
                        st.success("Git 인코딩 설정이 기본값으로 초기화되었습니다")
                    else:
                        st.error("Git 설정 초기화에 실패했습니다")
                except Exception as e:
                    st.error(f"Git 설정 초기화 오류: {e}")
    else:
        st.warning("🟡 저장소가 연결되지 않음")
    
    st.divider()
    
    # Azure OpenAI 설정 상태
    config = st.session_state.config
    if config.azure_openai.api_key and config.azure_openai.endpoint:
        st.success("🟢 Azure OpenAI 설정됨")
    else:
        st.warning("🟡 Azure OpenAI 설정되지 않음")
        with st.expander("Azure OpenAI 설정"):
            new_api_key = st.text_input("API 키", type="password", help="Azure OpenAI API 키를 입력하세요")
            new_endpoint = st.text_input("엔드포인트", help="Azure OpenAI 엔드포인트 URL을 입력하세요")
            
            if st.button("Azure OpenAI 설정 저장"):
                if new_api_key and new_endpoint:
                    # 환경변수 또는 설정에 저장 (실제 구현에서는 보안을 고려해야 함)
                    import os
                    os.environ['AZURE_OPENAI_API_KEY'] = new_api_key
                    os.environ['AZURE_OPENAI_ENDPOINT'] = new_endpoint
                    
                    # Config 재로드
                    st.session_state.config = Config()
                    st.success("Azure OpenAI 설정이 저장되었습니다!")
                    st.rerun()
                else:
                    st.error("API 키와 엔드포인트를 모두 입력해주세요")
    
    # 추가 설정 정보
    with st.expander("시스템 정보"):
        st.text(f"Python 경로: {sys.path[0]}")
        st.text(f"작업 디렉토리: {Path.cwd()}")
        if hasattr(st.session_state, 'config'):
            st.text(f"출력 디렉토리: {st.session_state.config.app.output_directory}")
            st.text(f"임시 디렉토리: {st.session_state.config.app.temp_directory}")


def get_repository_info(commit_selector: CommitSelector) -> Dict[str, Any]:
    """저장소 정보 조회"""
    try:
        # 최근 커밋 정보
        recent_commits = commit_selector.get_commit_list(max_commits=10)
        
        # 브랜치 정보
        branches = commit_selector.get_branch_list()
        
        # 기본 통계
        total_commits = len(commit_selector.get_commit_list(max_commits=1000))
        
        return {
            'total_commits': total_commits,
            'recent_commits': recent_commits,
            'branches': branches,
            'last_updated': datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to get repository info: {e}")
        return {}


def display_repository_info(repo_info: Dict[str, Any]):
    """저장소 정보 표시"""
    if not repo_info:
        st.warning("Unable to load repository information")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Commits", repo_info.get('total_commits', 'N/A'))
    
    with col2:
        st.metric("Branches", len(repo_info.get('branches', [])))
    
    with col3:
        st.metric("Recent Activity", f"{len(repo_info.get('recent_commits', []))} commits")
    
    # 최근 커밋들 표시
    if repo_info.get('recent_commits'):
        st.subheader("Recent Commits")
        commits_df = pd.DataFrame([
            {
                'Hash': commit.short_hash,
                'Message': commit.message[:50] + ('...' if len(commit.message) > 50 else ''),
                'Author': commit.author,
                'Date': commit.date.strftime('%Y-%m-%d %H:%M'),
                'Files': len(commit.files_changed),
                'Test Commit': '🧪' if commit.is_test_commit else ''
            }
            for commit in repo_info['recent_commits'][:5]
        ])
        st.dataframe(commits_df, use_container_width=True)


def show_commit_selection():
    """커밋 선택 페이지"""
    st.header("📝 커밋 선택")
    
    # 페이지 사용 설명 추가
    st.markdown("""
    > #### 🔍 테스트하고 싶은 커밋 범위를 설정해요
    > 
    > 1. **📋 커밋 필터링**: 날짜, 작성자, 키워드로 원하는 커밋을 찾아보세요. 커밋 정보나 변경 내용도 확인할 수 있어요
    > 2. **✅ 커밋 선택**: 테스트를 생성할 커밋을 체크박스로 선택하면 선택한 커밋들의 변경사항을 한꺼번에 합쳐줘요.  
    > 3. **🚀 분석 시작**: 변경사항 분석을 요청하면 보고서와 함께 테스트 생성을 준비할게요.
    >
    > 💡 **팁**: 서로 관련된 커밋들을 함께 선택하면 더 수준 높은 테스트를 생성할 수 있어요!
    """)
    st.divider()
    
    if not st.session_state.commit_selector:
        st.warning("⚠️ 먼저 저장소에 연결해주세요 (저장소 설정)")
        return
    
    commit_selector = st.session_state.commit_selector
    
    # 필터 옵션 - 예쁜 구획화
    with st.expander("🔍 필터 및 검색 옵션", expanded=True):
        # 상단: 기본 설정
        st.markdown("##### 📊 기본 설정")
        col1, col2 = st.columns(2)
        
        with col1:
            max_commits = st.slider(
                "표시할 커밋 수", 
                min_value=10, 
                max_value=200, 
                value=50,
                help="한 번에 표시할 최대 커밋 수를 설정합니다"
            )
        
        with col2:
            exclude_test_commits = st.checkbox(
                "🧪 테스트 관련 커밋 제외", 
                value=True,
                help="테스트 파일만 변경한 커밋을 목록에서 제외합니다"
            )
        
        st.divider()
        
        # 중단: 날짜 및 작성자 필터
        st.markdown("##### 📅 작성자/날짜")
        col1, col2 = st.columns(2)
        
        with col1:
            author_filter = st.text_input(
                "👤 작성자 필터", 
                value="",
                placeholder="작성자명 입력 (예: hmschung)",
                help="특정 작성자의 커밋만 표시합니다"
            )
        
        with col2:
            date_range = st.date_input(
                "📅 날짜 범위",
                value=(datetime.now() - timedelta(days=30), datetime.now()),
                max_value=datetime.now(),
                help="지정된 기간 내의 커밋만 표시합니다"
            )
        
        st.divider()
        
        # 하단: 검색
        st.markdown("##### 🔎 키워드 검색")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_query = st.text_input(
                "💬 커밋 메시지 검색", 
                value="",
                placeholder="검색할 키워드 입력 (예: feat, fix, refactor)",
                help="커밋 메시지에서 키워드를 검색합니다"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # 버튼 높이 맞추기
            search_button = st.button(
                "🔍 검색", 
                type="secondary",
                use_container_width=True,
                help="입력된 키워드로 커밋을 검색합니다"
            )
            
            if search_button and search_query:
                search_results = commit_selector.search_commits(search_query, "message", max_commits)
                if search_results:
                    st.success(f"✅ '{search_query}' 검색 결과: {len(search_results)}개 커밋 발견")
                else:
                    st.warning(f"⚠️ '{search_query}' 검색 결과가 없습니다")
                display_commit_list(search_results, f"🔎 '{search_query}' 검색 결과")
    
    # 커밋 리스트 로드
    try:
        since = datetime.combine(date_range[0], datetime.min.time()) if len(date_range) > 0 else None
        until = datetime.combine(date_range[1], datetime.max.time()) if len(date_range) > 1 else None
        
        commits = commit_selector.get_commit_list(
            max_commits=max_commits,
            since=since,
            until=until,
            author=author_filter if author_filter else None,
            exclude_test_commits=exclude_test_commits
        )
        
        if commits:
            display_commit_selection_ui(commits, commit_selector)
        else:
            st.info("조건에 맞는 커밋을 찾을 수 없습니다")
            
    except Exception as e:
        st.error(f"커밋 로드 실패: {e}")


def display_commit_selection_ui(commits: List[CommitInfo], commit_selector: CommitSelector):
    """커밋 선택 UI 표시"""
    st.subheader(f"사용 가능한 커밋 ({len(commits)}개)")
    
    # 커밋 선택 체크박스
    selected_commits = []
    
    # 데이터프레임으로 표시하되, 선택 기능 추가
    commit_data = []
    for i, commit in enumerate(commits):
        commit_data.append({
            'Select': False,
            'Hash': commit.short_hash,
            'Message': commit.message[:60] + ('...' if len(commit.message) > 60 else ''),
            'Author': commit.author.split()[0] if commit.author else '',  # 이름만
            'Date': commit.date.strftime('%m-%d %H:%M'),
            'Files': len(commit.files_changed),
            '+/-': f"+{commit.additions}/-{commit.deletions}",
            'Test': '🧪' if commit.is_test_commit else '',
            'commit_obj': commit  # 실제 커밋 객체는 숨김
        })
    
    # 전체 선택/해제 토글 버튼들
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 전체 선택", use_container_width=True):
            st.session_state.select_all_commits = True
            st.rerun()
    with col2:
        if st.button("🔄 전체 해제", use_container_width=True):
            st.session_state.select_all_commits = False
            st.session_state.clear_all_commits = True
            st.rerun()
    
    # 상호작용 가능한 테이블
    with st.form("commit_selection_form"):
        st.markdown("분석할 커밋을 선택하세요:")
        
        # 커밋별 체크박스
        commit_checkboxes = {}
        for i, commit in enumerate(commits):
            col1, col2, col3, col4, col5 = st.columns([0.5, 1.5, 3, 1.5, 1])
            
            with col1:
                # 전체 선택/해제 상태 반영
                default_checked = False
                if st.session_state.get('select_all_commits', False):
                    default_checked = True
                elif st.session_state.get('clear_all_commits', False):
                    default_checked = False
                
                is_selected = st.checkbox("", key=f"commit_{i}", value=default_checked)
                commit_checkboxes[commit.hash] = is_selected
            
            with col2:
                st.code(commit.short_hash)
            
            with col3:
                st.text(commit.message[:50] + ('...' if len(commit.message) > 50 else ''))
            
            with col4:
                st.text(f"{commit.author.split()[0] if commit.author else ''}")
            
            with col5:
                st.text(commit.date.strftime('%m-%d'))
                if commit.is_test_commit:
                    st.text("🧪")
            
            # 커밋 상세 정보 (확장 가능)
            with st.expander(f"상세정보: {commit.short_hash}", expanded=False):
                show_commit_details(commit, commit_selector)
        
        # 분석 실행 버튼 (크고 명확하게)
        submit = st.form_submit_button(
            "🚀 선택된 커밋 분석 시작", 
            type="primary",
            use_container_width=True
        )
        
        # 선택된 커밋들 분석 처리
        if submit:
            # 진행상황 표시를 위한 플레이스홀더를 먼저 생성
            progress_placeholder = st.empty()
            
            selected_commits = [commit_hash for commit_hash, is_selected in commit_checkboxes.items() if is_selected]
            
            if selected_commits:
                # 선택된 커밋들의 통합 변경사항 계산
                try:
                    # 1단계: 커밋 분석
                    progress_placeholder.info("🔍 선택된 커밋들을 분석하는 중...")
                    time.sleep(0.5)
                    
                    # 2단계: 변경사항 통합
                    progress_placeholder.info("📊 변경사항을 통합하는 중...")
                    combined_changes = commit_selector.calculate_combined_changes(selected_commits)
                    time.sleep(0.3)
                    
                    # 3단계: 파이프라인 컨텍스트 생성
                    progress_placeholder.info("⚙️ 파이프라인 컨텍스트를 생성하는 중...")
                    st.session_state.pipeline_context = create_pipeline_context(
                        st.session_state.config,
                        st.session_state.repo_path,
                        selected_commits,
                        combined_changes
                    )
                    time.sleep(0.2)
                    
                    # 완료 메시지로 교체
                    progress_placeholder.success(f"✅ {len(selected_commits)}개 커밋 분석 완료")
                    
                    # 통합 변경사항 미리보기
                    show_combined_changes_preview(combined_changes)
                    
                    # 다음 단계로 진행 안내
                    st.info("📍 **파이프라인 실행** 메뉴로 이동하여 테스트 생성 프로세스를 시작하세요")
                    
                except Exception as e:
                    progress_placeholder.error(f"❌ 선택된 커밋 분석 실패: {e}")
            else:
                progress_placeholder.warning("⚠️ 분석할 커밋을 선택해주세요")
            
            st.session_state.selected_commits = selected_commits
            
            # 전체 선택/해제 상태 초기화
            if 'select_all_commits' in st.session_state:
                del st.session_state.select_all_commits
            if 'clear_all_commits' in st.session_state:
                del st.session_state.clear_all_commits
    


def show_commit_details(commit: CommitInfo, commit_selector: CommitSelector):
    """커밋 상세 정보 표시"""
    # 커밋 ID만 간단하게 표시
    st.text(f"🔖 커밋 ID: {commit.short_hash}")
    
    if commit.is_test_commit:
        st.warning("🧪 테스트 관련 커밋")
    
    # 전체 커밋 정보 조회 (form 내부에서는 버튼 대신 자동으로 표시)
    try:
        full_details = commit_selector.get_commit_details(commit.hash)
        if full_details:
            with st.expander("📋 전체 커밋 상세정보", expanded=False):
                display_commit_details_with_diff_highlighting(full_details)
    except Exception as e:
        st.text(f"상세정보 조회 불가: {e}")


def display_commit_details_with_diff_highlighting(full_details: Dict[str, Any]):
    """커밋 상세정보를 diff 하이라이팅과 함께 표시"""
    
    # diff 정보가 있는지 확인
    diff_content = full_details.get('diff', '')
    
    if diff_content:
        # diff 섹션을 분리해서 표시
        st.subheader("📝 변경사항 (Diff)")
        display_highlighted_diff(diff_content)
        
        st.divider()
        
        # 나머지 정보는 기본 JSON으로 표시 (diff 제외)
        details_without_diff = {k: v for k, v in full_details.items() if k != 'diff'}
        if details_without_diff:
            st.subheader("📊 커밋 메타데이터")
            st.json(details_without_diff, expanded=False)
    else:
        # diff가 없으면 기본 JSON 표시
        st.json(full_details, expanded=False)


def display_highlighted_diff(diff_content: str):
    """diff 내용을 색상 하이라이팅하여 표시"""
    
    if not diff_content:
        st.info("변경사항이 없습니다.")
        return
    
    # CSS 스타일 정의
    st.markdown("""
    <style>
    .diff-container {
        background-color: #1a1a1a;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.4;
        max-height: 500px;
        overflow-y: auto;
        white-space: pre-wrap;
        color: #ffffff;
    }
    .diff-added {
        background-color: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border-left: 3px solid #22c55e;
        padding-left: 8px;
        margin: 1px 0;
    }
    .diff-removed {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border-left: 3px solid #ef4444;
        padding-left: 8px;
        margin: 1px 0;
    }
    .diff-context {
        color: #9ca3af;
        padding-left: 8px;
        margin: 1px 0;
    }
    .diff-header {
        color: #60a5fa;
        font-weight: bold;
        padding-left: 8px;
        margin: 1px 0;
    }
    .diff-hunk {
        color: #a78bfa;
        font-weight: bold;
        padding-left: 8px;
        margin: 1px 0;
        border-bottom: 1px solid #374151;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # diff 내용을 줄별로 분석하여 HTML 생성
    lines = diff_content.split('\n')
    html_content = '<div class="diff-container">'
    
    for line in lines:
        if not line:
            html_content += '<br>'
            continue
            
        # 이스케이프 처리
        escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        if line.startswith('+++') or line.startswith('---'):
            # 파일 헤더
            html_content += f'<div class="diff-header">{escaped_line}</div>'
        elif line.startswith('@@'):
            # Hunk 헤더 (@@ -n,n +n,n @@)
            html_content += f'<div class="diff-hunk">{escaped_line}</div>'
        elif line.startswith('+'):
            # 추가된 줄 (초록색)
            html_content += f'<div class="diff-added">{escaped_line}</div>'
        elif line.startswith('-'):
            # 삭제된 줄 (빨간색)
            html_content += f'<div class="diff-removed">{escaped_line}</div>'
        else:
            # 컨텍스트 줄 (회색)
            html_content += f'<div class="diff-context">{escaped_line}</div>'
    
    html_content += '</div>'
    
    # HTML 표시
    st.markdown(html_content, unsafe_allow_html=True)
    
    # 통계 정보 표시
    lines_added = len([line for line in lines if line.startswith('+')])
    lines_removed = len([line for line in lines if line.startswith('-')])
    
    if lines_added > 0 or lines_removed > 0:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("추가된 줄", lines_added, delta=f"+{lines_added}" if lines_added > 0 else None)
        with col2:
            st.metric("삭제된 줄", lines_removed, delta=f"-{lines_removed}" if lines_removed > 0 else None)
        with col3:
            net_change = lines_added - lines_removed
            st.metric("순 변경", net_change, delta=f"+{net_change}" if net_change > 0 else f"{net_change}" if net_change < 0 else "0")


def show_combined_changes_preview(combined_changes: Dict[str, Any]):
    """통합 변경사항 미리보기"""
    st.subheader("📊 통합 변경사항 미리보기")
    
    summary = combined_changes.get('summary', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("변경된 파일", summary.get('total_files', 0))
    with col2:
        st.metric("추가된 라인", summary.get('total_additions', 0))
    with col3:
        st.metric("삭제된 라인", summary.get('total_deletions', 0))
    with col4:
        st.metric("순 변경량", summary.get('net_changes', 0))
    
    # 파일별 변경사항 차트
    files_changed = combined_changes.get('files_changed', [])
    if files_changed:
        # 가장 많이 변경된 파일들 표시 (상위 10개)
        sorted_files = sorted(files_changed, key=lambda f: f['additions'] + f['deletions'], reverse=True)
        top_files = sorted_files[:10]
        
        if top_files:
            chart_data = pd.DataFrame([
                {
                    'File': f['filename'].split('/')[-1],  # 파일명만
                    'Additions': f['additions'],
                    'Deletions': f['deletions']
                }
                for f in top_files
            ])
            
            fig = px.bar(
                chart_data, 
                x=['Additions', 'Deletions'], 
                y='File',
                orientation='h',
                title="주요 변경 파일",
                color_discrete_map={'Additions': 'green', 'Deletions': 'red'}
            )
            st.plotly_chart(fig, use_container_width=True)


def create_pipeline_context(
    config: Config,
    repo_path: str,
    selected_commits: List[str],
    combined_changes: Dict[str, Any]
) -> PipelineContext:
    """파이프라인 컨텍스트 생성"""
    context = PipelineContext(
        config=config,
        repo_path=repo_path,
        selected_commits=selected_commits,
        combined_changes=combined_changes,
        progress_callback=log_progress,
        user_confirmation_callback=request_user_confirmation
    )
    
    return context


def log_progress(stage: str, progress: float, message: str):
    """진행상황 로그"""
    log_entry = {
        'timestamp': datetime.now(),
        'stage': stage,
        'progress': progress,
        'message': message
    }
    
    st.session_state.progress_logs.append(log_entry)
    st.session_state.current_stage = stage
    
    logger.info(f"[{stage}] {progress:.1%}: {message}")


def request_user_confirmation(title: str, data: Dict[str, Any]) -> bool:
    """사용자 확인 요청 (Streamlit에서는 기본적으로 True 반환)"""
    # Streamlit UI에서는 실시간 상호작용이 제한적이므로 기본적으로 승인
    return True


def show_pipeline_execution():
    """파이프라인 실행 페이지"""
    st.header("⚙️ 파이프라인 실행")
    
    # 페이지 사용 설명 추가
    st.markdown("""
    ### 🔥 테스트 생성 프로세스:
    
    1. **🎯 테스트 전략**: 변경사항에 맞는 최적의 테스트 전략을 AI가 결정합니다  
    2. **🧪 테스트 코드 생성**: AI가 실제 실행 가능한 테스트 코드를 생성합니다
    3. **📝 시나리오 생성**: 사용자 관점의 테스트 시나리오를 작성합니다
    4. **📊 결과 검토**: 생성된 테스트를 검토하고 개선 제안을 제공합니다
    5. **📥 내보내기**: 생성된 결과를 다양한 형식으로 다운로드할 수 있습니다
    
    💡 **참고**: VCS 분석은 이미 커밋 선택 단계에서 완료되었으므로 여기서는 생략됩니다.
    
    💡 **참고**: 전체 프로세스는 보통 1-3분 정도 소요되며, 실시간으로 진행상황을 확인할 수 있습니다!
    """)
    
    if not st.session_state.pipeline_context:
        st.warning("⚠️ 먼저 커밋을 선택해주세요 (커밋 선택)")
        return
    
    context = st.session_state.pipeline_context
    orchestrator = st.session_state.pipeline_orchestrator
    
    # 파이프라인 설정
    st.subheader("파이프라인 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"📍 저장소: {context.repo_path}")
        st.info(f"🔄 선택된 커밋: {len(context.selected_commits)}개")
    
    with col2:
        # 실행할 단계 선택
        # VCS 분석은 이미 커밋 선택에서 완료되었으므로 기본에서 제외
        available_stages = [stage for stage in orchestrator.stage_order if stage != PipelineStage.VCS_ANALYSIS]
        
        # 단계명을 한글로 매핑
        stage_name_map = {
            'test_strategy': '테스트 전략',
            'test_code_generation': '테스트 코드 생성',
            'test_scenario_generation': '테스트 시나리오 생성',
            'review_generation': '리뷰 생성'
        }
        
        korean_options = [stage_name_map.get(stage.value, stage.value) for stage in available_stages]
        
        stages_to_run = st.multiselect(
            "실행할 단계",
            options=korean_options,
            default=korean_options,
            help="실행할 파이프라인 단계를 선택하세요 (VCS 분석은 커밋 선택에서 이미 완료됨)"
        )
        
        # 선택된 한글명을 다시 영문으로 변환
        reverse_map = {v: k for k, v in stage_name_map.items()}
        stages_to_run = [reverse_map.get(stage, stage) for stage in stages_to_run]
        
        # 실행 모드
        execution_mode = st.radio(
            "실행 모드",
            ["전체 파이프라인", "단계별 실행"],
            help="전체 파이프라인은 모든 단계를 한 번에 실행, 단계별 실행은 각 단계를 개별적으로 실행"
        )
    
    # 파이프라인 실행 버튼
    if st.button("🚀 파이프라인 실행 시작", type="primary"):
        if stages_to_run:
            # 선택된 단계들 변환
            selected_stages = [PipelineStage(stage) for stage in stages_to_run]
            
            if execution_mode == "전체 파이프라인":
                asyncio.run(execute_full_pipeline(orchestrator, context, selected_stages))
            else:
                st.session_state.pipeline_stages = selected_stages
                st.session_state.current_stage_index = 0
                st.info("단계별 실행 모드가 선택되었습니다. 아래 컨트롤을 사용하여 각 단계를 실행하세요.")
        else:
            st.error("실행할 단계를 하나 이상 선택해주세요")
    
    # 단계별 실행 모드 UI
    if execution_mode == "단계별 실행" and hasattr(st.session_state, 'pipeline_stages'):
        show_stage_by_stage_execution(orchestrator, context)
    
    # 진행상황 표시
    show_progress_monitoring()
    
    # 현재 결과 표시
    if st.session_state.pipeline_results:
        show_pipeline_results_preview()


async def execute_full_pipeline(orchestrator, context, stages):
    """전체 파이프라인 실행"""
    logger.info("=== UI: 파이프라인 실행 시작 ===")
    logger.info(f"실행할 단계들: {[stage.value for stage in stages]}")
    st.info("🔄 파이프라인 실행 중...")
    
    # 진행상황 표시를 위한 플레이스홀더
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    try:
        # 비동기 실행
        logger.info("파이프라인 오케스트레이터 실행 시작")
        results = await orchestrator.execute_pipeline(context, stages)
        logger.info(f"파이프라인 실행 완료 - 결과 개수: {len(results)}")
        
        # 결과 세부 로깅
        for stage, result in results.items():
            logger.info(f"단계 {stage.value}: 상태={result.status.value}, "
                       f"실행시간={result.execution_time:.2f}s, "
                       f"오류={len(result.errors)}, 경고={len(result.warnings)}")
            
            # 테스트 코드 생성 단계의 경우 특별히 상세 로깅
            if stage == PipelineStage.TEST_CODE_GENERATION:
                logger.info(f"=== 테스트 코드 생성 단계 결과 분석 ===")
                if hasattr(result, 'test_cases') and result.test_cases:
                    logger.info(f"원본 TestCase 객체: {len(result.test_cases)}개")
                if result.data and 'generated_tests' in result.data:
                    logger.info(f"직렬화된 테스트: {len(result.data['generated_tests'])}개")
                else:
                    logger.warning("직렬화된 테스트 데이터가 없음")
        
        st.session_state.pipeline_results = results
        logger.info("파이프라인 결과를 세션 상태에 저장 완료")
        
        # 실행 완료 알림
        success_count = sum(1 for result in results.values() if result.status == StageStatus.COMPLETED)
        total_count = len(results)
        
        logger.info(f"파이프라인 완료 - 성공: {success_count}/{total_count}")
        
        if success_count == total_count:
            logger.info("모든 파이프라인 단계가 성공적으로 완료됨")
            st.success(f"✅ Pipeline completed successfully! ({success_count}/{total_count} stages)")
        else:
            logger.warning(f"일부 파이프라인 단계에서 문제 발생: {total_count - success_count}개 실패")
            st.warning(f"⚠️ Pipeline completed with issues ({success_count}/{total_count} stages successful)")
        
    except Exception as e:
        logger.error(f"파이프라인 실행 중 예외 발생: {e}")
        logger.error(f"예외 스택 트레이스: {traceback.format_exc()}" if 'traceback' in globals() else "스택 트레이스 없음")
        st.error(f"❌ Pipeline execution failed: {e}")
        logger.error(f"Pipeline execution error: {e}")


def show_stage_by_stage_execution(orchestrator, context):
    """단계별 실행 UI"""
    st.subheader("Stage by Stage Execution")
    
    stages = st.session_state.pipeline_stages
    current_index = st.session_state.get('current_stage_index', 0)
    
    if current_index < len(stages):
        current_stage = stages[current_index]
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            st.info(f"Stage {current_index + 1}/{len(stages)}")
        
        with col2:
            st.info(f"🔄 {current_stage.value.replace('_', ' ').title()}")
        
        with col3:
            if st.button("Execute Stage"):
                asyncio.run(execute_single_stage(orchestrator, context, current_stage))
                st.session_state.current_stage_index += 1
                st.rerun()
    else:
        st.success("✅ All stages completed!")


async def execute_single_stage(orchestrator, context, stage):
    """단일 스테이지 실행"""
    st.info(f"Executing {stage.value}...")
    
    try:
        result = await orchestrator.execute_single_stage(stage, context)
        
        if not st.session_state.pipeline_results:
            st.session_state.pipeline_results = {}
        
        st.session_state.pipeline_results[stage] = result
        
        if result.status == StageStatus.COMPLETED:
            st.success(f"✅ {stage.value} completed successfully")
        elif result.status == StageStatus.FAILED:
            st.error(f"❌ {stage.value} failed: {'; '.join(result.errors)}")
        
    except Exception as e:
        st.error(f"❌ Failed to execute {stage.value}: {e}")


def show_progress_monitoring():
    """진행상황 모니터링 표시"""
    if st.session_state.progress_logs:
        st.subheader("📈 Progress Monitoring")
        
        # 최근 로그 표시
        recent_logs = st.session_state.progress_logs[-10:]  # 최근 10개만
        
        for log in reversed(recent_logs):  # 최신 순으로
            timestamp = log['timestamp'].strftime('%H:%M:%S')
            stage = log['stage']
            progress = log['progress']
            message = log['message']
            
            st.text(f"[{timestamp}] {stage}: {message} ({progress:.1%})")
        
        # 전체 진행상황 바
        if st.session_state.current_stage:
            current_progress = recent_logs[-1]['progress'] if recent_logs else 0
            st.progress(current_progress, text=f"Current Stage: {st.session_state.current_stage}")


def show_pipeline_results_preview():
    """파이프라인 결과 미리보기"""
    st.subheader("📊 파이프라인 결과 미리보기")
    
    # 소스코드 정보를 표시하는 탭 추가
    tabs = st.tabs(["실행 결과 요약", "테스트 전략", "소스코드 분석", "테스트 시나리오", "리뷰 및 제안", "내보내기"])
    
    with tabs[0]:
        show_results_summary_tab()
    
    with tabs[1]:
        show_test_strategy_tab()
    
    with tabs[2]:
        show_source_code_analysis_tab()
    
    with tabs[3]:
        show_test_scenarios_preview_tab()
    
    with tabs[4]:
        show_review_preview_tab()
    
    with tabs[5]:
        show_export_options(st.session_state.pipeline_results)


def show_results_summary_tab():
    """결과 요약 탭"""
    results = st.session_state.pipeline_results
    
    if not results:
        st.info("파이프라인 실행 결과가 없습니다")
        return
        
    # 단계별 상태 표시
    col1, col2, col3, col4 = st.columns(4)
    
    completed = sum(1 for r in results.values() if r.status == StageStatus.COMPLETED)
    failed = sum(1 for r in results.values() if r.status == StageStatus.FAILED)
    running = sum(1 for r in results.values() if r.status == StageStatus.RUNNING)
    pending = sum(1 for r in results.values() if r.status == StageStatus.PENDING)
    
    with col1:
        st.metric("완료", completed, delta=None)
    with col2:
        st.metric("실패", failed, delta=None)
    with col3:
        st.metric("실행 중", running, delta=None)
    with col4:
        st.metric("대기 중", pending, delta=None)
    
    # 단계별 상세 결과
    for stage, result in results.items():
        with st.expander(f"{stage.value.replace('_', ' ').title()} - {result.status.value}"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.text(f"Status: {result.status.value}")
                if result.execution_time:
                    st.text(f"Execution Time: {result.execution_time:.2f}s")
                st.text(f"Errors: {len(result.errors)}")
                st.text(f"Warnings: {len(result.warnings)}")
            
            with col2:
                if result.data:
                    st.text("Generated Data:")
                    for key, value in result.data.items():
                        if key == "llm_recommendations" and isinstance(value, dict):
                            st.text(f"  {key}: AI 추천사항 있음")
                        elif isinstance(value, list):
                            st.text(f"  {key}: {len(value)} items")
                        elif isinstance(value, dict):
                            st.text(f"  {key}: {len(value)} keys")
                        else:
                            st.text(f"  {key}: {str(value)[:50]}...")
                            
            
            # 오류 및 경고 표시
            if result.errors:
                st.error("Errors:")
                for error in result.errors:
                    st.text(f"  • {error}")
            
            if result.warnings:
                st.warning("Warnings:")
                for warning in result.warnings:
                    st.text(f"  • {warning}")


def show_source_code_analysis_tab():
    """소스코드 분석 탭 - 변경된 소스코드와 생성된 테스트코드 표시"""
    st.subheader("📄 Source Code Analysis")
    
    if not st.session_state.pipeline_context:
        st.info("No pipeline context available")
        return
    
    context = st.session_state.pipeline_context
    results = st.session_state.pipeline_results
    
    # 변경된 소스코드 섹션
    st.markdown("### 🔍 Changed Source Code")
    
    if hasattr(context, 'combined_changes') and context.combined_changes:
        combined_changes = context.combined_changes
        
        if 'files_changed' in combined_changes:
            files_changed = combined_changes['files_changed']
            
            if files_changed:
                st.write(f"**총 {len(files_changed)}개 파일이 변경되었습니다.**")
                
                # 파일 선택 드롭다운
                file_options = [f"({i+1}) {file_info.get('filename', 'Unknown')}" for i, file_info in enumerate(files_changed)]
                selected_file_idx = st.selectbox("변경된 파일 선택:", range(len(file_options)), format_func=lambda x: file_options[x])
                
                if selected_file_idx is not None:
                    selected_file = files_changed[selected_file_idx]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("추가된 라인", selected_file.get('additions', 0))
                    with col2:
                        st.metric("삭제된 라인", selected_file.get('deletions', 0))
                    with col3:
                        st.metric("상태", selected_file.get('status', 'M'))
                    
                    # Diff 내용 표시
                    if 'content_diff' in selected_file and selected_file['content_diff']:
                        st.markdown("**📝 Diff Content:**")
                        st.code(selected_file['content_diff'], language='diff')
                    else:
                        st.info("Diff 정보가 없습니다.")
            else:
                st.info("변경된 파일 정보가 없습니다.")
        else:
            st.info("파일 변경 정보를 찾을 수 없습니다.")
    else:
        st.info("변경사항 정보가 없습니다.")
    
    st.divider()
    
    # 생성된 테스트코드 섹션
    st.markdown("### 🧪 Generated Test Code")
    
    if results and PipelineStage.TEST_CODE_GENERATION in results:
        test_result = results[PipelineStage.TEST_CODE_GENERATION]
        
        # 직렬화된 테스트나 원본 TestCase 객체에서 테스트 코드 가져오기
        generated_tests = test_result.data.get('generated_tests', []) if test_result.data else []
        
        if not generated_tests and hasattr(test_result, 'test_cases') and test_result.test_cases:
            # 원본 객체에서 변환
            generated_tests = []
            for test_case in test_result.test_cases:
                generated_tests.append({
                    'name': getattr(test_case, 'name', 'Unknown Test'),
                    'description': getattr(test_case, 'description', ''),
                    'test_type': getattr(test_case.test_type, 'value', 'unit') if hasattr(test_case, 'test_type') else 'unit',
                    'code': getattr(test_case, 'code', ''),
                    'assertions': getattr(test_case, 'assertions', []),
                    'dependencies': getattr(test_case, 'dependencies', []),
                    'priority': getattr(test_case, 'priority', 3)
                })
        
        if generated_tests:
            st.write(f"**총 {len(generated_tests)}개의 테스트가 생성되었습니다.**")
            
            # 테스트 선택 드롭다운
            test_options = [f"({i+1}) {test.get('name', 'Unknown')}" for i, test in enumerate(generated_tests)]
            selected_test_idx = st.selectbox("생성된 테스트 선택:", range(len(test_options)), format_func=lambda x: test_options[x])
            
            if selected_test_idx is not None:
                selected_test = generated_tests[selected_test_idx]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("테스트 타입", selected_test.get('test_type', 'N/A'))
                with col2:
                    st.metric("우선순위", selected_test.get('priority', 'N/A'))
                with col3:
                    st.metric("어서션 개수", len(selected_test.get('assertions', [])))
                
                # 테스트 설명
                if selected_test.get('description'):
                    st.markdown("**📄 설명:**")
                    st.info(selected_test['description'])
                
                # 테스트 코드
                test_code = selected_test.get('code', '')
                if test_code:
                    st.markdown("**💻 테스트 코드:**")
                    
                    # 코드 언어 감지
                    code_language = "python"
                    if "def test_" in test_code:
                        code_language = "python"
                    elif "public void test" in test_code or "@Test" in test_code:
                        code_language = "java"
                    elif "describe(" in test_code or "it(" in test_code:
                        code_language = "javascript"
                    
                    st.code(test_code, language=code_language)
                    
                    # 코드 통계
                    code_lines = test_code.split('\n')
                    non_empty_lines = [line for line in code_lines if line.strip()]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("총 라인 수", len(code_lines))
                    with col2:
                        st.metric("코드 라인 수", len(non_empty_lines))
                    
                    # 복사 가능한 텍스트 영역
                    st.text_area(
                        "코드 복사용:",
                        value=test_code,
                        height=150,
                        key=f"copy_test_code_{selected_test_idx}"
                    )
                else:
                    st.warning("테스트 코드가 없습니다.")
        else:
            st.info("생성된 테스트가 없습니다.")
    else:
        st.info("테스트 코드 생성 결과가 없습니다.")


def show_test_strategy_tab():
    """테스트 전략 탭"""
    results = st.session_state.pipeline_results
    
    if not results:
        st.info("파이프라인이 실행되지 않았습니다.")
        return
    
    strategy_result = results.get(PipelineStage.TEST_STRATEGY)
    
    if not strategy_result:
        st.info("테스트 전략 생성 단계가 실행되지 않았습니다.")
        return
    
    if strategy_result.status != StageStatus.COMPLETED:
        st.warning(f"테스트 전략 생성이 완료되지 않았습니다. 상태: {strategy_result.status}")
        return
    
    # 테스트 전략 데이터 추출
    strategy_data = strategy_result.data if strategy_result.data else {}
    llm_rec = strategy_data.get("llm_recommendations", {})
    
    if not llm_rec:
        st.info("AI 테스트 전략 분석 결과가 없습니다.")
        return
    
    # 메인 헤더
    st.markdown("### 🤖 AI 테스트 전략 분석")
    
    # 주요 전략 표시 (가장 중요)
    col1, col2 = st.columns([2, 1])
    
    with col1:
        primary_strategy = llm_rec.get("primary_strategy", "unknown")
        strategy_icons = {
            'unit': '🧩',
            'integration': '🔗',
            'end_to_end': '🌐',
            'performance': '⚡',
            'security': '🔒',
            'unknown': '❓'
        }
        icon = strategy_icons.get(primary_strategy, '🎯')
        st.success(f"{icon} **선택된 주요 전략:** {primary_strategy.upper()}")
    
    with col2:
        # 예상 작업량
        if "estimated_effort" in llm_rec:
            effort = llm_rec['estimated_effort']
            effort_color = 'green' if 'low' in effort.lower() else 'orange' if 'medium' in effort.lower() else 'red'
            st.markdown(f"**예상 작업량**")
            st.markdown(f":{effort_color}[{effort}]")
    
    # 전략 선택 이유
    if "reasoning" in llm_rec:
        with st.expander("📝 전략 선택 이유", expanded=True):
            st.info(llm_rec['reasoning'])
    
    # 상세 분석 섹션
    st.markdown("### 📊 상세 분석")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 추가 고려사항
        if "secondary_strategies" in llm_rec and llm_rec["secondary_strategies"]:
            st.markdown("#### 🔄 추가 고려 전략")
            for strategy in llm_rec["secondary_strategies"]:
                st.markdown(f"• {strategy}")
        
        # 위험도 평가
        if "risk_assessment" in llm_rec:
            st.markdown("#### ⚠️ 위험도 평가")
            risk = llm_rec['risk_assessment']
            risk_level = 'Low' if 'low' in risk.lower() else 'Medium' if 'medium' in risk.lower() else 'High'
            risk_color = '🟢' if risk_level == 'Low' else '🟡' if risk_level == 'Medium' else '🔴'
            st.markdown(f"{risk_color} **위험 수준:** {risk_level}")
            st.write(risk)
    
    with col2:
        # AI 추천사항
        if "recommendations" in llm_rec and llm_rec["recommendations"]:
            st.markdown("#### 💡 AI 추천사항")
            for i, rec in enumerate(llm_rec["recommendations"], 1):
                st.markdown(f"{i}. {rec}")
    
    # 테스트 전략 세부 계획
    if "test_plan" in llm_rec:
        st.markdown("### 📋 테스트 계획")
        test_plan = llm_rec["test_plan"]
        if isinstance(test_plan, list):
            for item in test_plan:
                st.checkbox(item, key=f"plan_{item[:20]}")
        else:
            st.write(test_plan)
    
    # 메트릭 및 통계
    st.markdown("### 📈 전략 메트릭")
    
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    
    with metrics_col1:
        # 변경된 파일 수 (strategy_data에서 가져오기)
        files_count = len(strategy_data.get("file_changes", []))
        st.metric("분석 파일", f"{files_count}개")
    
    with metrics_col2:
        # 예상 테스트 수
        expected_tests = llm_rec.get("expected_test_count", "N/A")
        st.metric("예상 테스트 수", expected_tests)
    
    with metrics_col3:
        # 커버리지 목표
        coverage_goal = llm_rec.get("coverage_goal", "80%")
        st.metric("커버리지 목표", coverage_goal)
    
    # 실행 시간 및 상태 정보
    if strategy_result.execution_time:
        st.info(f"⏱️ 전략 분석 시간: {strategy_result.execution_time:.2f}초")


def show_test_scenarios_preview_tab():
    """테스트 시나리오 미리보기 탭"""
    results = st.session_state.pipeline_results
    
    if not results:
        st.info("파이프라인이 실행되지 않았습니다.")
        return
    
    scenario_result = results.get(PipelineStage.TEST_SCENARIO_GENERATION)
    
    if not scenario_result:
        st.info("테스트 시나리오 생성 단계가 실행되지 않았습니다.")
        return
    
    # 시나리오 데이터 추출
    test_scenarios = scenario_result.data.get('test_scenarios', []) if scenario_result.data else []
    
    # 직렬화된 시나리오가 없는 경우 원본 객체 사용
    if not test_scenarios and hasattr(scenario_result, 'test_scenarios') and scenario_result.test_scenarios:
        test_scenarios = []
        for i, scenario in enumerate(scenario_result.test_scenarios):
            try:
                test_scenarios.append({
                    'scenario_id': getattr(scenario, 'scenario_id', f'S{i+1}'),
                    'feature': getattr(scenario, 'feature', 'N/A'),
                    'description': getattr(scenario, 'description', ''),
                    'preconditions': getattr(scenario, 'preconditions', []),
                    'test_steps': getattr(scenario, 'test_steps', []),
                    'expected_results': getattr(scenario, 'expected_results', []),
                    'test_data': getattr(scenario, 'test_data', None),
                    'priority': getattr(scenario, 'priority', 'Medium'),
                    'test_type': getattr(scenario, 'test_type', 'Functional')
                })
            except Exception as e:
                st.warning(f"시나리오 {i+1} 변환 중 오류 발생: {e}")
    
    if not test_scenarios:
        st.info("생성된 테스트 시나리오가 없습니다.")
        return
    
    st.write(f"📋 **생성된 테스트 시나리오: {len(test_scenarios)}개**")
    
    # 엑셀 형식으로 시나리오 표시
    show_scenarios_excel_format(test_scenarios)


def show_review_preview_tab():
    """리뷰 및 개선 제안 미리보기 탭"""
    results = st.session_state.pipeline_results
    
    if not results:
        st.info("파이프라인이 실행되지 않았습니다.")
        return
    
    review_result = results.get(PipelineStage.REVIEW_GENERATION)
    
    if not review_result:
        st.info("리뷰 생성 단계가 실행되지 않았습니다.")
        return
    
    if review_result.status != StageStatus.COMPLETED:
        st.warning(f"리뷰 생성이 완료되지 않았습니다. 상태: {review_result.status}")
        return
    
    # 리뷰 데이터 추출
    review_data = review_result.data if review_result.data else {}
    review_summary = review_data.get('review_summary', {})
    improvement_suggestions = review_data.get('improvement_suggestions', [])
    quality_metrics = review_data.get('quality_metrics', {})
    
    # 리뷰 요약 표시
    st.subheader("📋 리뷰 요약")
    
    if review_summary:
        # 품질 메트릭 표시
        if quality_metrics:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                overall_score = quality_metrics.get('overall_score', 'N/A')
                st.metric("전체 점수", overall_score)
            
            with col2:
                overall_quality = quality_metrics.get('overall_quality', 'Unknown')
                quality_color = {
                    'Excellent': '🟢',
                    'Good': '🟡', 
                    'Fair': '🟠',
                    'Needs Improvement': '🔴'
                }.get(overall_quality, '⚪')
                st.metric("품질 등급", f"{quality_color} {overall_quality}")
            
            with col3:
                coverage = quality_metrics.get('test_coverage_estimate', 'N/A')
                st.metric("추정 커버리지", coverage)
        
        # 리뷰 내용 표시
        review_content = review_summary.get('review_content', '')
        if review_content:
            st.subheader("📝 상세 리뷰")
            
            # 전체 리뷰 내용을 바로 표시 (마크다운 지원)
            st.markdown(review_content)
        
        # 기본 통계
        col1, col2, col3 = st.columns(3)
        with col1:
            total_tests = review_summary.get('total_tests', 0)
            st.info(f"🧪 총 테스트: {total_tests}개")
        with col2:
            total_scenarios = review_summary.get('total_scenarios', 0)
            st.info(f"📋 총 시나리오: {total_scenarios}개") 
        with col3:
            total_files = review_summary.get('total_files', 0)
            st.info(f"📄 분석 파일: {total_files}개")
    
    # 개선 제안사항 표시
    st.subheader("💡 개선 제안사항")
    
    if improvement_suggestions:
        st.write(f"총 **{len(improvement_suggestions)}개**의 개선사항이 제안되었습니다:")
        
        for i, suggestion in enumerate(improvement_suggestions, 1):
            # 우선순위에 따른 아이콘 표시
            priority_icon = "🔴" if i <= 3 else "🟡" if i <= 6 else "🟢"
            priority_text = "높음" if i <= 3 else "보통" if i <= 6 else "낮음"
            
            with st.expander(f"{priority_icon} 제안 {i}: {suggestion[:50]}...", expanded=i <= 2):
                st.write(f"**우선순위:** {priority_text}")
                st.write(f"**내용:** {suggestion}")
                
                # 체크리스트로 만들기
                if st.checkbox(f"✅ 적용 완료", key=f"suggestion_{i}"):
                    st.success("이 제안사항을 적용 완료로 표시했습니다.")
    else:
        st.info("생성된 개선 제안사항이 없습니다.")
    
    # 품질 상세 메트릭
    if quality_metrics:
        st.subheader("📊 품질 상세 메트릭")
        
        # 메트릭을 표 형태로 표시
        metrics_data = []
        for key, value in quality_metrics.items():
            # 키 이름을 한국어로 변환
            key_mapping = {
                'overall_score': '전체 점수',
                'overall_quality': '전체 품질',
                'test_coverage_estimate': '테스트 커버리지 추정',
                'scenario_completeness': '시나리오 완성도',
                'test_to_file_ratio': '테스트/파일 비율'
            }
            
            korean_key = key_mapping.get(key, key)
            metrics_data.append({'항목': korean_key, '값': str(value)})
        
        if metrics_data:
            import pandas as pd
            df = pd.DataFrame(metrics_data)
            st.dataframe(df, use_container_width=True, hide_index=True)


def generate_review_report(review_summary, improvement_suggestions, quality_metrics):
    """리뷰 보고서 텍스트 생성"""
    from datetime import datetime
    
    report = f"""
테스트 코드 및 시나리오 리뷰 보고서
생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== 리뷰 요약 ===
"""
    
    # 기본 통계
    if review_summary:
        report += f"총 테스트 수: {review_summary.get('total_tests', 0)}개\n"
        report += f"총 시나리오 수: {review_summary.get('total_scenarios', 0)}개\n"
        report += f"분석 파일 수: {review_summary.get('total_files', 0)}개\n\n"
    
    # 품질 메트릭
    if quality_metrics:
        report += "=== 품질 메트릭 ===\n"
        for key, value in quality_metrics.items():
            key_mapping = {
                'overall_score': '전체 점수',
                'overall_quality': '전체 품질',
                'test_coverage_estimate': '테스트 커버리지 추정',
                'scenario_completeness': '시나리오 완성도',
                'test_to_file_ratio': '테스트/파일 비율'
            }
            korean_key = key_mapping.get(key, key)
            report += f"{korean_key}: {value}\n"
        report += "\n"
    
    # 상세 리뷰
    if review_summary and review_summary.get('review_content'):
        report += "=== 상세 리뷰 ===\n"
        report += review_summary['review_content'] + "\n\n"
    
    # 개선 제안사항
    if improvement_suggestions:
        report += "=== 개선 제안사항 ===\n"
        for i, suggestion in enumerate(improvement_suggestions, 1):
            priority = "높음" if i <= 3 else "보통" if i <= 6 else "낮음"
            report += f"{i}. [{priority}] {suggestion}\n"
        report += "\n"
    
    report += "=== 보고서 끝 ===\n"
    
    return report


def show_detailed_logs_tab():
    """상세 로그 탭 - 향상된 로그 표시 및 필터링 기능"""
    st.subheader("📋 Detailed Logs")
    
    # 진행상황 로그 표시
    if st.session_state.progress_logs:
        st.markdown("### 📈 Progress Logs")
        
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            # 로그 레벨 필터
            log_levels = st.multiselect(
                "로그 레벨 필터:",
                ["All", "Info", "Warning", "Error", "Debug"],
                default=["All"]
            )
        
        with col2:
            # 단계별 필터
            all_stages = list(set([log['stage'] for log in st.session_state.progress_logs]))
            stage_filter = st.multiselect(
                "단계별 필터:",
                ["All"] + all_stages,
                default=["All"]
            )
        
        with col3:
            # 로그 개수 제한
            log_limit = st.selectbox(
                "표시할 로그 수:",
                [25, 50, 100, 200, "모든 로그"],
                index=1
            )
        
        # 검색 기능
        search_term = st.text_input("🔍 로그 검색:", placeholder="검색할 키워드 입력...")
        
        # 로그 필터링
        filtered_logs = st.session_state.progress_logs
        
        # 단계 필터 적용
        if stage_filter and "All" not in stage_filter:
            filtered_logs = [log for log in filtered_logs if log['stage'] in stage_filter]
        
        # 검색어 필터 적용
        if search_term:
            filtered_logs = [log for log in filtered_logs 
                           if search_term.lower() in log['message'].lower() 
                           or search_term.lower() in log['stage'].lower()]
        
        # 로그 개수 제한 적용
        if log_limit != "모든 로그":
            filtered_logs = filtered_logs[-log_limit:]
        
        # 통계 표시
        st.info(f"총 {len(st.session_state.progress_logs)}개 로그 중 {len(filtered_logs)}개 표시")
        
        if filtered_logs:
            # 로그 표시 옵션
            col1, col2 = st.columns([1, 1])
            with col1:
                show_timestamps = st.checkbox("타임스탬프 표시", value=True)
            with col2:
                show_progress = st.checkbox("진행률 표시", value=True)
            
            # 로그별로 카테고리 분류
            categorized_logs = {
                "파이프라인": [],
                "VCS 분석": [],
                "테스트 전략": [],
                "테스트 생성": [],
                "시나리오 생성": [],
                "리뷰 생성": [],
                "LLM": [],
                "기타": []
            }
            
            for log in reversed(filtered_logs):
                stage = log['stage'].upper()
                message = log['message'].lower()
                
                if "pipeline" in stage or "파이프라인" in message:
                    category = "파이프라인"
                elif "vcs" in stage or "git" in message or "분석" in message:
                    category = "VCS 분석"
                elif "strategy" in stage or "전략" in message:
                    category = "테스트 전략"
                elif "test_code" in stage or "테스트코드" in message or "테스트 생성" in message:
                    category = "테스트 생성"
                elif "scenario" in stage or "시나리오" in message:
                    category = "시나리오 생성"
                elif "review" in stage or "리뷰" in message:
                    category = "리뷰 생성"
                elif "llm" in message or "agent" in message or "openai" in message:
                    category = "LLM"
                else:
                    category = "기타"
                
                categorized_logs[category].append(log)
            
            # 카테고리별 로그 표시
            for category, logs in categorized_logs.items():
                if not logs:
                    continue
                    
                with st.expander(f"📂 {category} ({len(logs)}개)", expanded=(category == "파이프라인")):
                    for log in logs:
                        timestamp = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        stage = log['stage']
                        progress = log['progress']
                        message = log['message']
                        
                        # 로그 레벨에 따른 아이콘 및 색상
                        if 'error' in message.lower() or 'failed' in message.lower() or '오류' in message:
                            icon = "🔴"
                            log_level = "Error"
                            color = "red"
                        elif 'warning' in message.lower() or '경고' in message:
                            icon = "🟡"
                            log_level = "Warning"
                            color = "orange"
                        elif '완료' in message or 'completed' in message.lower() or '성공' in message:
                            icon = "🟢"
                            log_level = "Success"
                            color = "green"
                        elif 'debug' in message.lower() or '디버그' in message:
                            icon = "🔍"
                            log_level = "Debug"
                            color = "gray"
                        else:
                            icon = "🔵"
                            log_level = "Info"
                            color = "blue"
                        
                        # 로그 레벨 필터 확인
                        if log_levels and "All" not in log_levels and log_level not in log_levels:
                            continue
                        
                        # 로그 엔트리 표시
                        log_header = f"{icon} {stage}"
                        if show_timestamps:
                            log_header = f"[{timestamp}] " + log_header
                        if show_progress and progress > 0:
                            log_header += f" ({progress:.1%})"
                        
                        # 메시지 길이에 따라 표시 방식 결정
                        if len(message) > 100:
                            with st.expander(f"{log_header}: {message[:80]}...", expanded=False):
                                st.markdown(f"**시간:** {timestamp}")
                                st.markdown(f"**단계:** {stage}")
                                if progress > 0:
                                    st.markdown(f"**진행률:** {progress:.1%}")
                                st.markdown(f"**로그 레벨:** :{color}[{log_level}]")
                                st.markdown("**전체 메시지:**")
                                st.code(message, language="text")
                        else:
                            st.markdown(f":{color}[{log_header}]: {message}")
        else:
            st.warning("필터 조건에 맞는 로그가 없습니다.")
    else:
        st.info("진행상황 로그가 없습니다.")
    
    # 로그 파일 다운로드 및 분석 옵션
    st.markdown("### 📁 Log Files & Analysis")
    
    log_file_paths = [
        Path("logs/streamlit_app.log"),
        Path("logs/pipeline.log"), 
        Path("logs/llm_agent.log")
    ]
    
    available_log_files = [path for path in log_file_paths if path.exists()]
    
    if available_log_files:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            selected_log_file = st.selectbox(
                "로그 파일 선택:",
                available_log_files,
                format_func=lambda x: x.name
            )
        
        with col2:
            analysis_type = st.selectbox(
                "분석 타입:",
                ["미리보기", "오류 분석", "성능 분석", "전체 내용"]
            )
        
        if st.button("📊 로그 분석 실행"):
            try:
                with open(selected_log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                if analysis_type == "미리보기":
                    log_lines = log_content.split('\n')
                    recent_log_lines = log_lines[-50:]  # 최근 50줄
                    st.code('\n'.join(recent_log_lines), language="text")
                
                elif analysis_type == "오류 분석":
                    error_lines = [line for line in log_content.split('\n') 
                                 if 'error' in line.lower() or 'exception' in line.lower() or '오류' in line]
                    if error_lines:
                        st.error(f"총 {len(error_lines)}개의 오류 발견:")
                        for i, error_line in enumerate(error_lines[-20:]):  # 최근 20개 오류
                            st.code(f"{i+1}. {error_line}", language="text")
                    else:
                        st.success("오류가 발견되지 않았습니다!")
                
                elif analysis_type == "성능 분석":
                    performance_lines = [line for line in log_content.split('\n') 
                                       if '실행 시간' in line or 'execution time' in line.lower() or '완료' in line]
                    if performance_lines:
                        st.info(f"성능 관련 로그 {len(performance_lines)}개:")
                        for line in performance_lines[-15:]:  # 최근 15개
                            st.text(line)
                    else:
                        st.warning("성능 관련 로그를 찾을 수 없습니다.")
                
                elif analysis_type == "전체 내용":
                    st.code(log_content, language="text")
                
                # 다운로드 버튼
                st.download_button(
                    label=f"📥 {selected_log_file.name} 다운로드",
                    data=log_content,
                    file_name=f"{selected_log_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                    mime="text/plain"
                )
                
            except Exception as e:
                st.error(f"로그 파일 분석 중 오류 발생: {e}")
    else:
        st.info("로그 파일을 찾을 수 없습니다.")


def show_results_export():
    """결과 내보내기 페이지"""
    st.header("📥 결과 및 내보내기")
    
    # 페이지 사용 설명 추가
    st.markdown("""
    ### 📊 생성된 결과 확인하기:
    
    1. **📈 결과 요약**: 생성된 테스트와 시나리오의 전체 통계를 확인하세요
    2. **🧪 테스트 코드**: AI가 생성한 실행 가능한 테스트 코드를 검토하세요
    3. **📝 테스트 시나리오**: 사용자 관점의 테스트 시나리오를 확인하세요
    4. **📁 내보내기**: JSON, Excel, Markdown 등 다양한 형식으로 결과를 저장하세요
    
    💡 **활용팁**: 생성된 결과를 팀과 공유하거나 CI/CD 파이프라인에 통합해보세요!
    """)
    
    if not st.session_state.pipeline_results:
        st.warning("⚠️ 파이프라인 결과가 없습니다. 먼저 파이프라인을 실행해주세요.")
        return
    
    results = st.session_state.pipeline_results
    
    # 결과 요약
    st.subheader("📊 Results Summary")
    
    # 통계 카드들
    col1, col2, col3, col4 = st.columns(4)
    
    total_tests = 0
    total_scenarios = 0
    total_files = 0
    
    for result in results.values():
        if 'generated_tests' in result.data:
            total_tests += len(result.data['generated_tests'])
        if 'test_scenarios' in result.data:
            total_scenarios += len(result.data['test_scenarios'])
        if 'files_changed' in result.data:
            if isinstance(result.data['files_changed'], list):
                total_files += len(result.data['files_changed'])
            elif isinstance(result.data['files_changed'], dict):
                total_files += result.data['files_changed'].get('total_files', 0)
    
    with col1:
        st.metric("Generated Tests", total_tests)
    with col2:
        st.metric("Test Scenarios", total_scenarios)
    with col3:
        st.metric("Files Analyzed", total_files)
    with col4:
        st.metric("Pipeline Stages", len(results))
    
    # 상세 결과 표시 - 파이프라인 결과 미리보기와 동일한 형식 사용
    st.subheader("📋 상세 결과")
    
    # 파이프라인 결과 미리보기와 동일한 탭 구조
    tabs = st.tabs(["실행 결과 요약", "테스트 전략", "소스코드 분석", "테스트 시나리오", "리뷰 및 제안", "내보내기"])
    
    with tabs[0]:
        show_results_summary_tab()
    
    with tabs[1]:
        show_test_strategy_tab()
    
    with tabs[2]:
        show_source_code_analysis_tab()
    
    with tabs[3]:
        show_test_scenarios_preview_tab()
    
    with tabs[4]:
        show_review_preview_tab()
    
    with tabs[5]:
        show_export_options(results)


def show_test_code_results(results):
    """테스트 코드 결과 표시"""
    logger.info("=== UI: 테스트 코드 결과 표시 시작 ===")
    
    test_code_result = results.get(PipelineStage.TEST_CODE_GENERATION)
    logger.info(f"test_code_result 존재 여부: {test_code_result is not None}")
    
    if not test_code_result:
        logger.warning("test_code_result가 None입니다")
        st.info("No test code generated")
        return
    
    # StageResult 객체의 상태 정보 로깅
    logger.info(f"테스트코드 생성 단계 상태: {test_code_result.status.value}")
    logger.info(f"테스트코드 생성 단계 data 존재: {test_code_result.data is not None}")
    if test_code_result.data:
        logger.info(f"test_code_result.data 키들: {list(test_code_result.data.keys())}")
    
    logger.info(f"test_code_result.test_cases 존재: {hasattr(test_code_result, 'test_cases') and test_code_result.test_cases is not None}")
    if hasattr(test_code_result, 'test_cases') and test_code_result.test_cases:
        logger.info(f"test_code_result.test_cases 개수: {len(test_code_result.test_cases)}")
    
    # 먼저 직렬화된 테스트를 확인하고, 없으면 원본 객체 사용
    generated_tests = test_code_result.data.get('generated_tests', []) if test_code_result.data else []
    logger.info(f"직렬화된 테스트 개수: {len(generated_tests)}")
    
    # 직렬화된 테스트가 없거나 빈 리스트인 경우, 원본 TestCase 객체들을 직접 사용
    if not generated_tests and hasattr(test_code_result, 'test_cases') and test_code_result.test_cases:
        logger.info("=== UI: 원본 TestCase 객체 변환 시작 ===")
        st.info("📝 직렬화된 테스트 데이터가 없어 원본 객체를 직접 표시합니다.")
        
        original_tests_count = len(test_code_result.test_cases)
        logger.info(f"변환할 원본 테스트 개수: {original_tests_count}")
        
        generated_tests = []
        for i, test_case in enumerate(test_code_result.test_cases):
            logger.debug(f"테스트 케이스 {i+1} 변환 중 - 타입: {type(test_case)}")
            
            # TestCase 객체를 딕셔너리로 변환
            try:
                test_name = getattr(test_case, 'name', f'Test_{i+1}')
                test_description = getattr(test_case, 'description', '설명 없음')
                test_type = getattr(test_case.test_type, 'value', 'unit') if hasattr(test_case, 'test_type') else 'unit'
                test_code = getattr(test_case, 'code', '코드 없음')
                
                converted_test = {
                    'name': test_name,
                    'description': test_description,
                    'test_type': test_type,
                    'code': test_code,
                    'assertions': getattr(test_case, 'assertions', []),
                    'dependencies': getattr(test_case, 'dependencies', []),
                    'priority': getattr(test_case, 'priority', 3)
                }
                generated_tests.append(converted_test)
                
                logger.debug(f"테스트 케이스 {i+1} 변환 성공:")
                logger.debug(f"  - name: {test_name}")
                logger.debug(f"  - test_type: {test_type}")
                logger.debug(f"  - code 길이: {len(test_code) if test_code and test_code != '코드 없음' else 0} 문자")
                
                # 첫 번째 테스트의 경우 전체 코드도 로깅
                if i == 0 and test_code and test_code != '코드 없음':
                    logger.info(f"원본 TestCase 객체에서 변환된 첫 번째 테스트 코드:")
                    logger.info("=" * 60)
                    logger.info(test_code)
                    logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"테스트 케이스 {i+1} 변환 중 오류 발생: {e}")
                st.warning(f"테스트 케이스 {i+1} 변환 중 오류 발생: {e}")
                generated_tests.append({
                    'name': f'Test_{i+1}_ERROR',
                    'description': f'변환 오류: {str(e)}',
                    'test_type': 'unit',
                    'code': '# 테스트 코드 변환 중 오류가 발생했습니다',
                    'assertions': [],
                    'dependencies': [],
                    'priority': 3
                })
        
        logger.info(f"=== UI: 원본 TestCase 객체 변환 완료 - 총 {len(generated_tests)}개 변환 ===")
    
    if not generated_tests:
        logger.warning("변환된 테스트가 없습니다")
        st.info("No test code generated")
        return
    
    logger.info(f"=== UI: 최종적으로 표시할 테스트 개수: {len(generated_tests)} ===")
    
    # 첫 번째 테스트 샘플 로깅 (전체 코드 포함)
    if generated_tests:
        first_test = generated_tests[0]
        logger.info(f"첫 번째 테스트 정보:")
        logger.info(f"  - name: {first_test.get('name', 'N/A')}")
        logger.info(f"  - test_type: {first_test.get('test_type', 'N/A')}")
        logger.info(f"  - description: {first_test.get('description', 'N/A')}")
        
        test_code = first_test.get('code', '')
        logger.info(f"  - code 길이: {len(test_code) if test_code else 0} 문자")
        logger.info(f"  - UI에서 표시할 테스트 코드 전체 내용:")
        logger.info("=" * 60)
        logger.info(test_code if test_code else "(코드 없음)")
        logger.info("=" * 60)
    
    if generated_tests:
        st.write(f"**생성된 테스트 케이스: {len(generated_tests)}개**")
        
        for i, test in enumerate(generated_tests):
            # test가 딕셔너리인지 객체인지 확인
            if isinstance(test, dict):
                test_name = test.get('name', f'Test_{i+1}')
                test_description = test.get('description', '설명 없음')
                test_type = test.get('test_type', 'unknown')
                test_priority = test.get('priority', 'N/A')
                test_code = test.get('code', '코드 없음')
                test_assertions = test.get('assertions', [])
                test_dependencies = test.get('dependencies', [])
            else:
                # 객체인 경우 (기존 방식)
                test_name = getattr(test, 'name', f'Test_{i+1}')
                test_description = getattr(test, 'description', '설명 없음')
                test_type = getattr(test, 'test_type', 'unknown')
                test_priority = getattr(test, 'priority', 'N/A')
                test_code = getattr(test, 'code', '코드 없음')
                test_assertions = getattr(test, 'assertions', [])
                test_dependencies = getattr(test, 'dependencies', [])
            
            with st.expander(f"🧪 {test_name}", expanded=True):
                # 테스트 정보
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"**타입:** `{test_type}`")
                    st.markdown(f"**우선순위:** `{test_priority}`")
                
                with col2:
                    st.markdown(f"**어서션:** `{len(test_assertions)}개`")
                    st.markdown(f"**의존성:** `{len(test_dependencies)}개`")
                
                with col3:
                    st.markdown(f"**코드 길이:** `{len(str(test_code))}자`")
                
                # 설명
                if test_description and test_description != '설명 없음':
                    st.markdown("**📝 설명:**")
                    st.info(test_description)
                
                # 테스트 코드 - 가장 중요한 부분!
                st.markdown("**💻 테스트 코드:**")
                if test_code and test_code != '코드 없음':
                    # 코드 언어 자동 감지
                    code_language = "python"
                    if "def test_" in test_code:
                        code_language = "python"
                    elif "public void test" in test_code:
                        code_language = "java"
                    elif "describe(" in test_code or "it(" in test_code:
                        code_language = "javascript"
                    
                    st.code(test_code, language=code_language)
                    
                    # 복사 버튼을 위한 텍스트 영역 (숨겨진 상태)
                    st.text_area(
                        f"테스트 코드 복사용 (Test {i+1})",
                        value=test_code,
                        height=1,
                        key=f"copy_test_{i}",
                        label_visibility="collapsed"
                    )
                else:
                    st.warning("테스트 코드가 생성되지 않았습니다.")
                
                # 의존성과 어서션 상세 정보 (있는 경우만)
                if test_dependencies:
                    st.markdown("**🔗 의존성:**")
                    for dep in test_dependencies:
                        st.write(f"- {dep}")
                
                if test_assertions:
                    st.markdown("**✅ 어서션:**")
                    for assertion in test_assertions:
                        st.write(f"- {assertion}")
        
        # 전체 코드 다운로드 버튼
        st.markdown("---")
        
        # 모든 테스트 코드를 하나의 파일로 결합
        all_test_code = []
        for i, test in enumerate(generated_tests):
            test_code = test.get('code', '') if isinstance(test, dict) else getattr(test, 'code', '')
            test_name = test.get('name', f'Test_{i+1}') if isinstance(test, dict) else getattr(test, 'name', f'Test_{i+1}')
            
            if test_code:
                all_test_code.append(f"# {test_name}")
                all_test_code.append(test_code)
                all_test_code.append("")  # 빈 줄 추가
        
        combined_code = "\n".join(all_test_code)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 모든 테스트 코드 다운로드",
                data=combined_code,
                file_name="generated_tests.py",
                mime="text/plain"
            )
        
        with col2:
            if st.button("📋 전체 코드 보기"):
                st.code(combined_code, language="python")


def show_test_scenario_results(results):
    """테스트 시나리오 결과 표시"""
    scenario_result = results.get(PipelineStage.TEST_SCENARIO_GENERATION)
    
    if not scenario_result:
        st.info("No test scenarios generated")
        return
    
    # 먼저 직렬화된 시나리오를 확인하고, 없으면 원본 객체 사용
    test_scenarios = scenario_result.data.get('test_scenarios', []) if scenario_result.data else []
    
    # 직렬화된 시나리오가 없거나 빈 리스트인 경우, 원본 TestScenario 객체들을 직접 사용
    if not test_scenarios and hasattr(scenario_result, 'test_scenarios') and scenario_result.test_scenarios:
        st.info("📝 직렬화된 시나리오 데이터가 없어 원본 객체를 직접 표시합니다.")
        test_scenarios = []
        for i, scenario in enumerate(scenario_result.test_scenarios):
            # TestScenario 객체를 딕셔너리로 변환
            try:
                test_scenarios.append({
                    'scenario_id': getattr(scenario, 'scenario_id', f'S{i+1}'),
                    'feature': getattr(scenario, 'feature', 'N/A'),
                    'description': getattr(scenario, 'description', ''),
                    'preconditions': getattr(scenario, 'preconditions', []),
                    'test_steps': getattr(scenario, 'test_steps', []),
                    'expected_results': getattr(scenario, 'expected_results', []),
                    'test_data': getattr(scenario, 'test_data', None),
                    'priority': getattr(scenario, 'priority', 'Medium'),
                    'test_type': getattr(scenario, 'test_type', 'Functional')
                })
            except Exception as e:
                st.warning(f"시나리오 {i+1} 변환 중 오류 발생: {e}")
    
    if not test_scenarios:
        st.info("No test scenarios generated")
        return
    
    if test_scenarios:
        st.write(f"📋 **생성된 테스트 시나리오: {len(test_scenarios)}개**")
        
        # 표시 방식 선택
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            view_mode = st.selectbox(
                "표시 방식:",
                ["엑셀 표 형식", "카드 형식", "상세 뷰"]
            )
        with col2:
            show_all = st.checkbox("모든 시나리오 표시", value=True)
        with col3:
            if not show_all:
                max_scenarios = st.slider("표시할 개수", 1, len(test_scenarios), 5)
            else:
                max_scenarios = len(test_scenarios)
        
        scenarios_to_show = test_scenarios[:max_scenarios]
        
        if view_mode == "엑셀 표 형식":
            show_scenarios_excel_format(scenarios_to_show)
        elif view_mode == "카드 형식":
            show_scenarios_card_format(scenarios_to_show)
        else:
            show_scenarios_detailed_view(scenarios_to_show)
        
        # Excel 다운로드 기능
        if st.button("📊 Excel로 내보내기"):
            excel_data = create_scenarios_excel_data(test_scenarios)
            st.download_button(
                label="📥 테스트 시나리오 Excel 다운로드",
                data=excel_data,
                file_name=f"test_scenarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


def show_scenarios_excel_format(test_scenarios):
    """엑셀 양식으로 시나리오 표시"""
    import pandas as pd
    
    # 엑셀 스타일의 데이터프레임 생성
    excel_data = []
    for i, scenario in enumerate(test_scenarios):
        # 딕셔너리인지 객체인지 확인
        if isinstance(scenario, dict):
            scenario_id = scenario.get('scenario_id', f'TS_{i+1:03d}')
            feature = scenario.get('feature', 'N/A')
            description = scenario.get('description', '')
            priority = scenario.get('priority', 'Medium')
            test_type = scenario.get('test_type', 'Functional')
            preconditions = scenario.get('preconditions', [])
            test_steps = scenario.get('test_steps', [])
            expected_results = scenario.get('expected_results', [])
            test_data = scenario.get('test_data', {})
        else:
            scenario_id = getattr(scenario, 'scenario_id', f'TS_{i+1:03d}')
            feature = getattr(scenario, 'feature', 'N/A')
            description = getattr(scenario, 'description', '')
            priority = getattr(scenario, 'priority', 'Medium')
            test_type = getattr(scenario, 'test_type', 'Functional')
            preconditions = getattr(scenario, 'preconditions', [])
            test_steps = getattr(scenario, 'test_steps', [])
            expected_results = getattr(scenario, 'expected_results', [])
            test_data = getattr(scenario, 'test_data', {})
        
        # 테스트 단계를 문자열로 변환
        steps_text = ""
        if test_steps:
            for j, step in enumerate(test_steps):
                if isinstance(step, dict):
                    step_num = step.get('step', j+1)
                    action = step.get('action', '')
                    desc = step.get('description', '')
                    steps_text += f"{step_num}. {action}"
                    if desc and desc != action:
                        steps_text += f" - {desc}"
                    steps_text += "\n"
                else:
                    steps_text += f"{j+1}. {str(step)}\n"
        
        # 전제조건을 문자열로 변환
        precond_text = "\n".join([str(p) for p in preconditions]) if preconditions else ""
        
        # 예상결과를 문자열로 변환
        expected_text = "\n".join([str(r) for r in expected_results]) if expected_results else ""
        
        excel_data.append({
            '시나리오 ID': scenario_id,
            '기능': feature,
            '시나리오 설명': description,
            '우선순위': priority,
            '테스트 타입': test_type,
            '전제조건': precond_text,
            '테스트 단계': steps_text.strip(),
            '예상 결과': expected_text,
            '테스트 데이터': str(test_data) if test_data else ""
        })
    
    # 데이터프레임 생성 및 표시
    df = pd.DataFrame(excel_data)
    
    st.markdown("### 📊 엑셀 표 형식")
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        column_config={
            '시나리오 ID': st.column_config.TextColumn(width="small"),
            '기능': st.column_config.TextColumn(width="medium"),
            '시나리오 설명': st.column_config.TextColumn(width="large"),
            '우선순위': st.column_config.SelectboxColumn(
                options=['높음', '보통', '낮음', 'High', 'Medium', 'Low']
            ),
            '테스트 타입': st.column_config.TextColumn(width="small"),
            '전제조건': st.column_config.TextColumn(width="medium"),
            '테스트 단계': st.column_config.TextColumn(width="large"),
            '예상 결과': st.column_config.TextColumn(width="medium"),
            '테스트 데이터': st.column_config.TextColumn(width="small")
        }
    )


def show_scenarios_card_format(test_scenarios):
    """카드 형식으로 시나리오 표시"""
    st.markdown("### 🃏 카드 형식")
    
    cols_per_row = 2
    for i in range(0, len(test_scenarios), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(test_scenarios):
                scenario = test_scenarios[idx]
                
                # 딕셔너리인지 객체인지 확인
                if isinstance(scenario, dict):
                    scenario_id = scenario.get('scenario_id', f'TS_{idx+1:03d}')
                    feature = scenario.get('feature', 'N/A')
                    description = scenario.get('description', '')
                    priority = scenario.get('priority', 'Medium')
                    test_type = scenario.get('test_type', 'Functional')
                    test_steps = scenario.get('test_steps', [])
                    expected_results = scenario.get('expected_results', [])
                else:
                    scenario_id = getattr(scenario, 'scenario_id', f'TS_{idx+1:03d}')
                    feature = getattr(scenario, 'feature', 'N/A')
                    description = getattr(scenario, 'description', '')
                    priority = getattr(scenario, 'priority', 'Medium')
                    test_type = getattr(scenario, 'test_type', 'Functional')
                    test_steps = getattr(scenario, 'test_steps', [])
                    expected_results = getattr(scenario, 'expected_results', [])
                
                # 우선순위에 따른 색상
                if priority in ['높음', 'High']:
                    priority_color = "red"
                elif priority in ['보통', 'Medium']:
                    priority_color = "orange"
                else:
                    priority_color = "green"
                
                with col:
                    with st.container():
                        st.markdown(f"""
                        <div style="
                            border: 1px solid #ddd;
                            border-radius: 10px;
                            padding: 15px;
                            margin: 10px 0;
                            background-color: #f9f9f9;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        ">
                            <h4 style="margin: 0 0 10px 0; color: #333;">🔖 {scenario_id}</h4>
                            <p style="margin: 5px 0; font-weight: bold; color: #555;">📋 {feature}</p>
                            <p style="margin: 5px 0; color: #666; font-size: 14px;">{description[:100]}{'...' if len(description) > 100 else ''}</p>
                            <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                                <span style="background-color: {priority_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                                    🔥 {priority}
                                </span>
                                <span style="background-color: #007bff; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                                    🧪 {test_type}
                                </span>
                            </div>
                            <div style="margin-top: 10px; font-size: 12px; color: #888;">
                                📝 단계: {len(test_steps)}개 | ✅ 예상결과: {len(expected_results)}개
                            </div>
                        </div>
                        """, unsafe_allow_html=True)


def show_scenarios_detailed_view(test_scenarios):
    """상세 뷰로 시나리오 표시"""
    st.markdown("### 🔍 상세 뷰")
    
    for i, scenario in enumerate(test_scenarios):
        # 딕셔너리인지 객체인지 확인
        if isinstance(scenario, dict):
            scenario_id = scenario.get('scenario_id', f'TS_{i+1:03d}')
            feature = scenario.get('feature', 'N/A')
            description = scenario.get('description', '')
            priority = scenario.get('priority', 'Medium')
            test_type = scenario.get('test_type', 'Functional')
            preconditions = scenario.get('preconditions', [])
            test_steps = scenario.get('test_steps', [])
            expected_results = scenario.get('expected_results', [])
            test_data = scenario.get('test_data', {})
        else:
            scenario_id = getattr(scenario, 'scenario_id', f'TS_{i+1:03d}')
            feature = getattr(scenario, 'feature', 'N/A')
            description = getattr(scenario, 'description', '')
            priority = getattr(scenario, 'priority', 'Medium')
            test_type = getattr(scenario, 'test_type', 'Functional')
            preconditions = getattr(scenario, 'preconditions', [])
            test_steps = getattr(scenario, 'test_steps', [])
            expected_results = getattr(scenario, 'expected_results', [])
            test_data = getattr(scenario, 'test_data', {})
        
        with st.expander(f"🔖 {scenario_id}: {feature}", expanded=(i == 0)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**📋 기능:** {feature}")
                st.markdown(f"**📝 설명:** {description}")
                
                if preconditions:
                    st.markdown("**⚙️ 전제조건:**")
                    for j, precond in enumerate(preconditions):
                        st.markdown(f"   {j+1}. {precond}")
                
                if test_steps:
                    st.markdown("**📋 테스트 단계:**")
                    for j, step in enumerate(test_steps):
                        if isinstance(step, dict):
                            step_num = step.get('step', j+1)
                            action = step.get('action', '')
                            desc = step.get('description', '')
                            st.markdown(f"   **{step_num}.** {action}")
                            if desc and desc != action:
                                st.markdown(f"      *{desc}*")
                        else:
                            st.markdown(f"   **{j+1}.** {step}")
                
                if expected_results:
                    st.markdown("**✅ 예상 결과:**")
                    for j, result in enumerate(expected_results):
                        st.markdown(f"   {j+1}. {result}")
            
            with col2:
                st.markdown(f"**🔥 우선순위:** {priority}")
                st.markdown(f"**🧪 테스트 타입:** {test_type}")
                
                if test_data and isinstance(test_data, dict):
                    st.markdown("**💾 테스트 데이터:**")
                    for key, value in test_data.items():
                        st.markdown(f"   • **{key}:** {value}")
                elif test_data:
                    st.markdown(f"**💾 테스트 데이터:** {test_data}")
        
        st.divider()


def create_scenarios_excel_data(test_scenarios):
    """Excel 파일 생성용 데이터 준비"""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Excel 데이터 준비
        excel_data = []
        for i, scenario in enumerate(test_scenarios):
            if isinstance(scenario, dict):
                scenario_id = scenario.get('scenario_id', f'TS_{i+1:03d}')
                feature = scenario.get('feature', 'N/A')
                description = scenario.get('description', '')
                priority = scenario.get('priority', 'Medium')
                test_type = scenario.get('test_type', 'Functional')
                preconditions = scenario.get('preconditions', [])
                test_steps = scenario.get('test_steps', [])
                expected_results = scenario.get('expected_results', [])
                test_data = scenario.get('test_data', {})
            else:
                scenario_id = getattr(scenario, 'scenario_id', f'TS_{i+1:03d}')
                feature = getattr(scenario, 'feature', 'N/A')
                description = getattr(scenario, 'description', '')
                priority = getattr(scenario, 'priority', 'Medium')
                test_type = getattr(scenario, 'test_type', 'Functional')
                preconditions = getattr(scenario, 'preconditions', [])
                test_steps = getattr(scenario, 'test_steps', [])
                expected_results = getattr(scenario, 'expected_results', [])
                test_data = getattr(scenario, 'test_data', {})
            
            # 테스트 단계 포맷팅
            steps_formatted = []
            for j, step in enumerate(test_steps):
                if isinstance(step, dict):
                    step_num = step.get('step', j+1)
                    action = step.get('action', '')
                    desc = step.get('description', '')
                    step_text = f"{step_num}. {action}"
                    if desc and desc != action:
                        step_text += f" - {desc}"
                    steps_formatted.append(step_text)
                else:
                    steps_formatted.append(f"{j+1}. {str(step)}")
            
            excel_data.append({
                '시나리오 ID': scenario_id,
                '기능': feature,
                '시나리오 설명': description,
                '우선순위': priority,
                '테스트 타입': test_type,
                '전제조건': '\n'.join([str(p) for p in preconditions]),
                '테스트 단계': '\n'.join(steps_formatted),
                '예상 결과': '\n'.join([str(r) for r in expected_results]),
                '테스트 데이터': str(test_data) if test_data else '',
                '실행 결과': '',  # 사용자가 채울 수 있도록 빈 컬럼
                '실제 결과': '',   # 사용자가 채울 수 있도록 빈 컬럼
                '테스터': '',     # 사용자가 채울 수 있도록 빈 컬럼
                '테스트 일시': '',  # 사용자가 채울 수 있도록 빈 컬럼
                '비고': ''       # 사용자가 채울 수 있도록 빈 컬럼
            })
        
        # Excel 파일 생성
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df = pd.DataFrame(excel_data)
            df.to_excel(writer, sheet_name='테스트 시나리오', index=False)
            
            # 워크시트 포맷팅
            worksheet = writer.sheets['테스트 시나리오']
            
            # 컬럼 너비 조정
            worksheet.column_dimensions['A'].width = 15  # 시나리오 ID
            worksheet.column_dimensions['B'].width = 25  # 기능
            worksheet.column_dimensions['C'].width = 40  # 시나리오 설명
            worksheet.column_dimensions['D'].width = 10  # 우선순위
            worksheet.column_dimensions['E'].width = 15  # 테스트 타입
            worksheet.column_dimensions['F'].width = 30  # 전제조건
            worksheet.column_dimensions['G'].width = 50  # 테스트 단계
            worksheet.column_dimensions['H'].width = 30  # 예상 결과
            worksheet.column_dimensions['I'].width = 20  # 테스트 데이터
            worksheet.column_dimensions['J'].width = 15  # 실행 결과
            worksheet.column_dimensions['K'].width = 30  # 실제 결과
            worksheet.column_dimensions['L'].width = 15  # 테스터
            worksheet.column_dimensions['M'].width = 20  # 테스트 일시
            worksheet.column_dimensions['N'].width = 25  # 비고
        
        output.seek(0)
        return output.read()
    
    except ImportError:
        st.error("Excel 파일 생성을 위해 openpyxl 패키지가 필요합니다.")
        return None
    except Exception as e:
        st.error(f"Excel 파일 생성 중 오류 발생: {e}")
        return None


def show_analysis_results(results):
    """분석 결과 표시"""
    vcs_result = results.get(PipelineStage.VCS_ANALYSIS)
    
    if not vcs_result or not vcs_result.data:
        st.info("No analysis results available")
        return
    
    # VCS 분석 결과
    st.subheader("VCS Analysis Results")
    
    combined_analysis = vcs_result.data.get('combined_analysis')
    if combined_analysis:
        summary = combined_analysis.get('summary', {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Files Changed", summary.get('total_files', 0))
        with col2:
            st.metric("Lines Added", summary.get('total_additions', 0))
        with col3:
            st.metric("Lines Deleted", summary.get('total_deletions', 0))
        
        # 파일별 변경사항
        files_changed = combined_analysis.get('files_changed', [])
        if files_changed:
            st.subheader("Changed Files")
            
            file_data = []
            for file_info in files_changed[:20]:  # 상위 20개만 표시
                file_data.append({
                    'File': file_info.get('filename', '').split('/')[-1],
                    'Full Path': file_info.get('filename', ''),
                    'Additions': file_info.get('additions', 0),
                    'Deletions': file_info.get('deletions', 0),
                    'Status': file_info.get('status', 'M')
                })
            
            file_df = pd.DataFrame(file_data)
            st.dataframe(file_df, use_container_width=True)
    
    # 전략 분석 결과
    strategy_result = results.get(PipelineStage.TEST_STRATEGY)
    if strategy_result and strategy_result.data:
        st.subheader("Test Strategy Analysis")
        
        strategies = strategy_result.data.get('test_strategies', [])
        if strategies:
            for i, strategy in enumerate(strategies):
                st.text(f"Strategy {i+1}: {strategy}")


def show_export_options(results):
    """내보내기 옵션 표시"""
    st.subheader("📥 내보내기 설정")
    
    # 내보낼 콘텐츠 선택
    st.markdown("### 📋 내보낼 콘텐츠 선택")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 분석 결과")
        export_test_strategy = st.checkbox("🎯 테스트 전략", value=True, help="AI가 분석한 테스트 전략 및 추천사항")
        export_source_analysis = st.checkbox("📝 소스코드 분석", value=True, help="변경된 파일 및 코드 분석 결과")
        export_test_scenarios = st.checkbox("📋 테스트 시나리오", value=True, help="생성된 테스트 시나리오 (QA팀용)")
    
    with col2:
        st.markdown("#### 생성 결과")
        export_test_code = st.checkbox("🧪 테스트 코드", value=True, help="생성된 실행 가능한 테스트 코드")
        export_review = st.checkbox("📊 리뷰 및 제안", value=True, help="품질 평가 및 개선 제안사항")
        export_summary = st.checkbox("📈 전체 요약", value=True, help="파이프라인 실행 전체 요약")
    
    st.divider()
    
    # 내보내기 형식 선택
    st.markdown("### 📁 내보내기 형식")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        format_json = st.checkbox("JSON", value=True, help="개발자를 위한 구조화된 데이터")
    with col2:
        format_excel = st.checkbox("Excel", value=True, help="팀 공유를 위한 스프레드시트")
    with col3:
        format_markdown = st.checkbox("Markdown", value=False, help="문서화를 위한 마크다운")
    
    # 추가 옵션
    with st.expander("🔧 고급 설정", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            include_raw_data = st.checkbox("원본 데이터 포함", value=False, help="처리되지 않은 원본 데이터 포함")
            include_metadata = st.checkbox("메타데이터 포함", value=True, help="실행 시간, 버전 정보 등 포함")
        
        with col2:
            compress_output = st.checkbox("압축하여 내보내기", value=False, help="ZIP 파일로 압축")
            timestamp_filename = st.checkbox("파일명에 타임스탬프 추가", value=True, help="중복 방지를 위한 시간 정보 추가")
    
    st.divider()
    
    # 내보내기 실행
    if st.button("🚀 선택한 항목 내보내기", type="primary", use_container_width=True):
        # 선택된 콘텐츠 확인
        selected_content = {
            'test_strategy': export_test_strategy,
            'source_analysis': export_source_analysis,
            'test_scenarios': export_test_scenarios,
            'test_code': export_test_code,
            'review': export_review,
            'summary': export_summary
        }
        
        # 선택된 형식 확인
        selected_formats = []
        if format_json:
            selected_formats.append("JSON")
        if format_excel:
            selected_formats.append("Excel")
        if format_markdown:
            selected_formats.append("Markdown")
        
        if not any(selected_content.values()):
            st.error("❌ 내보낼 콘텐츠를 하나 이상 선택해주세요.")
            return
        
        if not selected_formats:
            st.error("❌ 내보낼 형식을 하나 이상 선택해주세요.")
            return
        
        try:
            with st.spinner("내보내기 진행 중..."):
                export_files = export_selected_results(
                    results,
                    selected_content,
                    selected_formats,
                    include_raw_data,
                    include_metadata,
                    compress_output,
                    timestamp_filename
                )
            
            st.success(f"✅ {len(export_files)}개 파일 내보내기 완료!")
            
            # 다운로드 버튼들을 컬럼으로 정리
            st.markdown("### 📥 다운로드")
            
            # 파일 형식별로 그룹화
            download_cols = st.columns(min(len(export_files), 3))
            for idx, file_info in enumerate(export_files):
                col_idx = idx % min(len(export_files), 3)
                with download_cols[col_idx]:
                    with open(file_info['path'], 'rb') as f:
                        st.download_button(
                            label=f"📄 {file_info['name']}",
                            data=f.read(),
                            file_name=file_info['name'],
                            mime=file_info['mime'],
                            help=file_info['description']
                        )
                    
        except Exception as e:
            st.error(f"❌ 내보내기 실패: {e}")
            import traceback
            st.error(traceback.format_exc())


def export_selected_results(
    results,
    selected_content,
    formats,
    include_raw_data,
    include_metadata,
    compress_output,
    timestamp_filename
):
    """선택된 결과 내보내기 실행"""
    export_files = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if timestamp_filename else ''
    
    # 출력 디렉토리 확인
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # JSON 내보내기
    if "JSON" in formats:
        json_data = {}
        
        # 선택된 콘텐츠만 포함
        if selected_content['summary']:
            json_data['summary'] = {
                'total_tests': sum(1 for r in results.values() if r.data and 'generated_tests' in r.data),
                'total_scenarios': sum(1 for r in results.values() if r.data and 'test_scenarios' in r.data),
                'pipeline_stages': len(results)
            }
        
        if selected_content['test_strategy'] and PipelineStage.TEST_STRATEGY in results:
            result = results[PipelineStage.TEST_STRATEGY]
            json_data['test_strategy'] = {
                'status': result.status.value,
                'data': result.data if include_raw_data else result.data.get('llm_recommendations', {}) if result.data else {}
            }
        
        if selected_content['source_analysis'] and PipelineStage.VCS_ANALYSIS in results:
            result = results[PipelineStage.VCS_ANALYSIS]
            json_data['source_analysis'] = {
                'status': result.status.value,
                'data': result.data if include_raw_data else {'summary': result.data.get('summary', {})} if result.data else {}
            }
        
        if selected_content['test_code'] and PipelineStage.TEST_CODE_GENERATION in results:
            result = results[PipelineStage.TEST_CODE_GENERATION]
            json_data['test_code'] = {
                'status': result.status.value,
                'tests': result.data.get('generated_tests', []) if result.data else []
            }
        
        if selected_content['test_scenarios'] and PipelineStage.TEST_SCENARIO_GENERATION in results:
            result = results[PipelineStage.TEST_SCENARIO_GENERATION]
            json_data['test_scenarios'] = {
                'status': result.status.value,
                'scenarios': result.data.get('test_scenarios', []) if result.data else []
            }
        
        if selected_content['review'] and PipelineStage.REVIEW_GENERATION in results:
            result = results[PipelineStage.REVIEW_GENERATION]
            json_data['review'] = {
                'status': result.status.value,
                'data': result.data if result.data else {}
            }
        
        json_filename = f"test_results{'_' + timestamp if timestamp else ''}.json"
        json_path = output_dir / json_filename
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        
        export_files.append({
            'path': str(json_path),
            'name': json_filename,
            'mime': 'application/json',
            'description': 'JSON 형식 데이터'
        })
    
    # Excel 내보내기
    if "Excel" in formats:
        excel_filename = f"test_results{'_' + timestamp if timestamp else ''}.xlsx"
        excel_path = output_dir / excel_filename
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # 요약 시트
            if selected_content['summary']:
                summary_data = []
                for stage, result in results.items():
                    summary_data.append({
                        '단계': stage.value.replace('_', ' ').title(),
                        '상태': result.status.value,
                        '실행 시간(초)': result.execution_time if result.execution_time else 0,
                        '오류': len(result.errors),
                        '경고': len(result.warnings)
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='요약', index=False)
            
            # 테스트 시나리오 시트 (완전한 형태로)
            if selected_content['test_scenarios'] and PipelineStage.TEST_SCENARIO_GENERATION in results:
                result = results[PipelineStage.TEST_SCENARIO_GENERATION]
                if result.data and 'test_scenarios' in result.data:
                    scenarios = result.data['test_scenarios']
                    if scenarios:
                        scenario_excel_data = []
                        for i, scenario in enumerate(scenarios):
                            if isinstance(scenario, dict):
                                scenario_id = scenario.get('scenario_id', f'TS_{i+1:03d}')
                                feature = scenario.get('feature', 'N/A')
                                description = scenario.get('description', '')
                                priority = scenario.get('priority', 'Medium')
                                test_type = scenario.get('test_type', 'Functional')
                                preconditions = scenario.get('preconditions', [])
                                test_steps = scenario.get('test_steps', [])
                                expected_results = scenario.get('expected_results', [])
                                test_data = scenario.get('test_data', {})
                            else:
                                scenario_id = getattr(scenario, 'scenario_id', f'TS_{i+1:03d}')
                                feature = getattr(scenario, 'feature', 'N/A')
                                description = getattr(scenario, 'description', '')
                                priority = getattr(scenario, 'priority', 'Medium')
                                test_type = getattr(scenario, 'test_type', 'Functional')
                                preconditions = getattr(scenario, 'preconditions', [])
                                test_steps = getattr(scenario, 'test_steps', [])
                                expected_results = getattr(scenario, 'expected_results', [])
                                test_data = getattr(scenario, 'test_data', {})
                            
                            # 테스트 단계 포맷팅
                            steps_formatted = []
                            for j, step in enumerate(test_steps):
                                if isinstance(step, dict):
                                    step_num = step.get('step', j+1)
                                    action = step.get('action', '')
                                    desc = step.get('description', '')
                                    step_text = f"{step_num}. {action}"
                                    if desc and desc != action:
                                        step_text += f" - {desc}"
                                    steps_formatted.append(step_text)
                                else:
                                    steps_formatted.append(f"{j+1}. {str(step)}")
                            
                            scenario_excel_data.append({
                                '시나리오 ID': scenario_id,
                                '기능': feature,
                                '시나리오 설명': description,
                                '우선순위': priority,
                                '테스트 타입': test_type,
                                '전제조건': '\n'.join([str(p) for p in preconditions]),
                                '테스트 단계': '\n'.join(steps_formatted),
                                '예상 결과': '\n'.join([str(r) for r in expected_results]),
                                '테스트 데이터': str(test_data) if test_data else '',
                                '실행 결과': '',  # 사용자가 채울 수 있도록 빈 컬럼
                                '실제 결과': '',   # 사용자가 채울 수 있도록 빈 컬럼
                                '테스터': '',     # 사용자가 채울 수 있도록 빈 컬럼
                                '테스트 일시': '',  # 사용자가 채울 수 있도록 빈 컬럼
                                '비고': ''       # 사용자가 채울 수 있도록 빈 컬럼
                            })
                        
                        if scenario_excel_data:
                            scenario_df = pd.DataFrame(scenario_excel_data)
                            scenario_df.to_excel(writer, sheet_name='테스트 시나리오', index=False)
                            
                            # 워크시트 포맷팅
                            worksheet = writer.sheets['테스트 시나리오']
                            
                            # 컬럼 너비 조정
                            worksheet.column_dimensions['A'].width = 15  # 시나리오 ID
                            worksheet.column_dimensions['B'].width = 25  # 기능
                            worksheet.column_dimensions['C'].width = 40  # 시나리오 설명
                            worksheet.column_dimensions['D'].width = 10  # 우선순위
                            worksheet.column_dimensions['E'].width = 15  # 테스트 타입
                            worksheet.column_dimensions['F'].width = 30  # 전제조건
                            worksheet.column_dimensions['G'].width = 50  # 테스트 단계
                            worksheet.column_dimensions['H'].width = 30  # 예상 결과
                            worksheet.column_dimensions['I'].width = 20  # 테스트 데이터
                            worksheet.column_dimensions['J'].width = 15  # 실행 결과
                            worksheet.column_dimensions['K'].width = 30  # 실제 결과
                            worksheet.column_dimensions['L'].width = 15  # 테스터
                            worksheet.column_dimensions['M'].width = 20  # 테스트 일시
                            worksheet.column_dimensions['N'].width = 25  # 비고
            
            # 소스코드 분석 시트
            if selected_content['source_analysis'] and PipelineStage.VCS_ANALYSIS in results:
                result = results[PipelineStage.VCS_ANALYSIS]
                if result.data and 'combined_analysis' in result.data:
                    files = result.data['combined_analysis'].get('files_changed', [])
                    if files:
                        file_data = []
                        for file in files[:50]:  # 최대 50개 파일
                            file_data.append({
                                '파일명': file.get('filename', ''),
                                '상태': file.get('status', ''),
                                '추가': file.get('additions', 0),
                                '삭제': file.get('deletions', 0)
                            })
                        
                        if file_data:
                            file_df = pd.DataFrame(file_data)
                            file_df.to_excel(writer, sheet_name='파일 변경사항', index=False)
        
        export_files.append({
            'path': str(excel_path),
            'name': excel_filename,
            'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'description': 'Excel 스프레드시트'
        })
    
    # Markdown 리포트
    if "Markdown" in formats:
        md_filename = f"test_report{'_' + timestamp if timestamp else ''}.md"
        md_path = output_dir / md_filename
        
        md_content = generate_selected_markdown_report(results, selected_content)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        export_files.append({
            'path': str(md_path),
            'name': md_filename,
            'mime': 'text/markdown',
            'description': 'Markdown 문서'
        })
    
    # 압축 처리
    if compress_output and export_files:
        import zipfile
        zip_filename = f"test_results{'_' + timestamp if timestamp else ''}.zip"
        zip_path = output_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_info in export_files:
                zipf.write(file_info['path'], arcname=file_info['name'])
        
        # 압축 파일만 반환
        return [{
            'path': str(zip_path),
            'name': zip_filename,
            'mime': 'application/zip',
            'description': '압축된 결과 파일'
        }]
    
    return export_files


def generate_selected_markdown_report(results, selected_content):
    """선택된 콘텐츠만 포함한 마크다운 리포트 생성"""
    md_content = f"""# AI 테스트 생성 리포트

생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

"""
    
    # 요약
    if selected_content['summary']:
        md_content += "## 📊 전체 요약\n\n"
        total_tests = sum(len(r.data.get('generated_tests', [])) for r in results.values() if r.data)
        total_scenarios = sum(len(r.data.get('test_scenarios', [])) for r in results.values() if r.data)
        md_content += f"- **생성된 테스트**: {total_tests}개\n"
        md_content += f"- **테스트 시나리오**: {total_scenarios}개\n"
        md_content += f"- **파이프라인 단계**: {len(results)}개\n\n"
    
    # 테스트 전략
    if selected_content['test_strategy'] and PipelineStage.TEST_STRATEGY in results:
        result = results[PipelineStage.TEST_STRATEGY]
        md_content += "## 🎯 테스트 전략\n\n"
        if result.data and 'llm_recommendations' in result.data:
            rec = result.data['llm_recommendations']
            md_content += f"- **주요 전략**: {rec.get('primary_strategy', 'N/A')}\n"
            md_content += f"- **전략 선택 이유**: {rec.get('reasoning', 'N/A')}\n"
            if rec.get('recommendations'):
                md_content += "\n### AI 추천사항:\n"
                for r in rec['recommendations']:
                    md_content += f"- {r}\n"
        md_content += "\n"
    
    # 소스코드 분석
    if selected_content['source_analysis'] and PipelineStage.VCS_ANALYSIS in results:
        result = results[PipelineStage.VCS_ANALYSIS]
        md_content += "## 📝 소스코드 분석\n\n"
        if result.data and 'summary' in result.data:
            summary = result.data['summary']
            md_content += f"- **변경된 파일**: {summary.get('total_files', 0)}개\n"
            md_content += f"- **추가된 라인**: {summary.get('total_additions', 0)}줄\n"
            md_content += f"- **삭제된 라인**: {summary.get('total_deletions', 0)}줄\n\n"
    
    # 테스트 시나리오
    if selected_content['test_scenarios'] and PipelineStage.TEST_SCENARIO_GENERATION in results:
        result = results[PipelineStage.TEST_SCENARIO_GENERATION]
        md_content += "## 📋 테스트 시나리오\n\n"
        if result.data and 'test_scenarios' in result.data:
            scenarios = result.data['test_scenarios']
            for i, scenario in enumerate(scenarios[:10], 1):  # 최대 10개
                if isinstance(scenario, dict):
                    md_content += f"### {i}. {scenario.get('feature', 'N/A')}\n"
                    md_content += f"- **ID**: {scenario.get('scenario_id', 'N/A')}\n"
                    md_content += f"- **설명**: {scenario.get('description', 'N/A')}\n"
                    md_content += f"- **우선순위**: {scenario.get('priority', 'N/A')}\n\n"
    
    # 리뷰 및 제안
    if selected_content['review'] and PipelineStage.REVIEW_GENERATION in results:
        result = results[PipelineStage.REVIEW_GENERATION]
        md_content += "## 📊 리뷰 및 제안\n\n"
        if result.data:
            review_summary = result.data.get('review_summary', {})
            if review_summary.get('review_content'):
                md_content += f"### 리뷰 내용\n{review_summary['review_content']}\n\n"
            
            suggestions = result.data.get('improvement_suggestions', [])
            if suggestions:
                md_content += "### 개선 제안사항\n"
                for suggestion in suggestions:
                    md_content += f"- {suggestion}\n"
                md_content += "\n"
    
    return md_content


def generate_markdown_report(results):
    """마크다운 리포트 생성"""
    md_content = f"""# AI Test Generation Report

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Pipeline Summary

"""
    
    for stage, result in results.items():
        md_content += f"### {stage.value.replace('_', ' ').title()}\n\n"
        md_content += f"- **Status**: {result.status.value}\n"
        md_content += f"- **Execution Time**: {result.execution_time:.2f}s\n" if result.execution_time else "- **Execution Time**: N/A\n"
        md_content += f"- **Errors**: {len(result.errors)}\n"
        md_content += f"- **Warnings**: {len(result.warnings)}\n"
        
        if result.data:
            md_content += f"- **Generated Items**: {len(result.data)} data keys\n"
        
        if result.errors:
            md_content += "\n**Errors:**\n"
            for error in result.errors:
                md_content += f"- {error}\n"
        
        if result.warnings:
            md_content += "\n**Warnings:**\n"
            for warning in result.warnings:
                md_content += f"- {warning}\n"
        
        md_content += "\n"
    
    return md_content


if __name__ == "__main__":
    main()