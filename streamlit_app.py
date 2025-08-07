"""
Streamlit UI Application - 대화형 테스트 생성 인터페이스

사용자가 웹 브라우저에서 직접 커밋을 선택하고, 단계별로 테스트 생성 과정을 모니터링할 수 있는 UI를 제공합니다.
"""
import asyncio
import json
import os
import tempfile
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
setup_logger('INFO')
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


def main():
    """메인 애플리케이션"""
    st.title("🤖 AI 테스트 생성기")
    st.markdown("### VCS 변경사항으로부터 자동화된 테스트 생성")
    
    # 사이드바 메뉴
    with st.sidebar:
        selected = option_menu(
            "메인 메뉴",
            ["저장소 설정", "커밋 선택", "파이프라인 실행", "결과 및 내보내기"],
            icons=['folder', 'git', 'play-circle', 'download'],
            menu_icon="cast",
            default_index=0,
        )
    
    # 페이지 라우팅
    if selected == "저장소 설정":
        show_repository_setup()
    elif selected == "커밋 선택":
        show_commit_selection()
    elif selected == "파이프라인 실행":
        show_pipeline_execution()
    elif selected == "결과 및 내보내기":
        show_results_export()


def show_repository_setup():
    """저장소 설정 페이지"""
    st.header("📁 저장소 설정")
    
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
        "Branch",
        value=st.session_state.get('branch', 'main'),
        help="Branch to analyze (default: main)"
    )
    
    # 인증 설정
    with st.expander("Authentication Settings (if required)"):
        auth_method = st.selectbox(
            "Authentication Method",
            ["None (Public Repository)", "Username/Password", "Personal Access Token"],
            help="Select authentication method for private repositories"
        )
        
        if auth_method == "Username/Password":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
        elif auth_method == "Personal Access Token":
            token = st.text_input("Personal Access Token", type="password", 
                                help="GitHub Personal Access Token or GitLab Access Token")
    
    # URL 형식 도우미
    st.markdown("""
    💡 **Supported URL formats**:
    - HTTPS: `https://github.com/user/repo.git`
    - SSH: `git@github.com:user/repo.git`  
    - GitLab: `https://gitlab.com/user/repo.git`
    - Azure DevOps: `https://dev.azure.com/org/project/_git/repo`
    """)
    
    # 원격 저장소 연결 버튼
    if st.button("🌐 Connect to Remote Repository", type="primary"):
        if repo_url:
            try:
                with st.spinner("🔄 Cloning remote repository and checking Git configuration..."):
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
                st.error(f"❌ Failed to connect to remote repository: {e}")
                st.markdown("""
                **Possible issues:**
                - Repository URL is incorrect
                - Repository is private and requires authentication
                - Network connectivity issues
                - Git is not installed on the system
                """)
        else:
            st.error("❌ Please provide a valid repository URL")
    
    # Git 설정 변경 대화상자 처리 (원격 저장소도 동일하게)
    if 'git_config_changes' in st.session_state and st.session_state['git_config_changes']:
        st.markdown("---")
        handle_git_config_dialog()


@st.dialog("Git Configuration Required")
def git_config_modal():
    """Git 설정 변경 모달 대화상자"""
    changes_needed = st.session_state['git_config_changes']
    
    st.markdown("### 🔧 Git Configuration Optimization")
    
    st.markdown("""
    To properly handle non-ASCII characters (Korean, Chinese, etc.) in commit messages,
    the following Git repository settings need to be updated:
    """)
    
    # 변경사항 표시
    for i, change in enumerate(changes_needed, 1):
        with st.expander(f"Setting {i}: {change['key']}", expanded=False):
            st.text(f"Description: {change['description']}")
            st.text(f"Current value: '{change['current']}'")
            st.text(f"Required value: '{change['required']}'")
    
    st.info("""
    ℹ️ **Important Notes:**
    - These changes will be made to the LOCAL repository configuration only
    - Your global Git settings will not be affected
    - You can revert these changes later using: `git config --local --unset <key>`
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Proceed with Changes", type="primary", key="proceed_git_config_modal"):
            # Git 설정 변경 승인 및 모달 닫기
            st.session_state.git_config_approved = True
            st.rerun()
    
    with col2:
        if st.button("❌ Skip Configuration", key="skip_git_config_modal"):
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
                st.success(f"✅ Applied {len(changes_needed)} Git configuration changes")
            else:
                st.info("Git configuration optimization was skipped")
            
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
                st.success("✅ Successfully connected to remote repository!")
                st.info(f"📁 Repository cloned to temporary location: {repo_path}")
            else:
                st.success("✅ Successfully connected to local repository!")
            
            # 저장소 정보 표시
            with st.expander("Repository Information", expanded=True):
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
    st.subheader("Configuration Status")
    
    # 연결 상태 표시
    if st.session_state.commit_selector:
        st.success("🟢 Repository Connected")
        
        repo_type = st.session_state.get('repo_type', 'unknown')
        if repo_type == 'local':
            st.info(f"📍 Local Path: {st.session_state.repo_path}")
        elif repo_type == 'remote':
            st.info(f"🌐 Remote URL: {st.session_state.repo_url}")
            st.info(f"📁 Local Cache: {st.session_state.repo_path}")
        
        st.info(f"🌿 Branch: {st.session_state.branch}")
        
        # 저장소 관리 버튼들
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Change Repository"):
                # 세션 상태 초기화
                for key in ['commit_selector', 'repo_path', 'repo_url', 'branch', 'repo_type']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        
        with col2:
            if st.button("🔧 Reset Git Config"):
                try:
                    if st.session_state.commit_selector.reset_git_encoding_config():
                        st.success("Git encoding configuration reset to defaults")
                    else:
                        st.error("Failed to reset Git configuration")
                except Exception as e:
                    st.error(f"Error resetting Git config: {e}")
    else:
        st.warning("🟡 Repository Not Connected")
    
    st.divider()
    
    # Azure OpenAI 설정 상태
    config = st.session_state.config
    if config.azure_openai.api_key and config.azure_openai.endpoint:
        st.success("🟢 Azure OpenAI Configured")
    else:
        st.warning("🟡 Azure OpenAI Not Configured")
        with st.expander("Configure Azure OpenAI"):
            new_api_key = st.text_input("API Key", type="password", help="Enter your Azure OpenAI API key")
            new_endpoint = st.text_input("Endpoint", help="Enter your Azure OpenAI endpoint URL")
            
            if st.button("Save Azure OpenAI Settings"):
                if new_api_key and new_endpoint:
                    # 환경변수 또는 설정에 저장 (실제 구현에서는 보안을 고려해야 함)
                    import os
                    os.environ['AZURE_OPENAI_API_KEY'] = new_api_key
                    os.environ['AZURE_OPENAI_ENDPOINT'] = new_endpoint
                    
                    # Config 재로드
                    st.session_state.config = Config()
                    st.success("Azure OpenAI settings saved!")
                    st.rerun()
                else:
                    st.error("Please provide both API Key and Endpoint")
    
    # 추가 설정 정보
    with st.expander("System Information"):
        st.text(f"Python Path: {sys.path[0]}")
        st.text(f"Working Directory: {Path.cwd()}")
        if hasattr(st.session_state, 'config'):
            st.text(f"Output Directory: {st.session_state.config.app.output_directory}")
            st.text(f"Temp Directory: {st.session_state.config.app.temp_directory}")


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
    st.header("📝 Commit Selection")
    
    if not st.session_state.commit_selector:
        st.warning("⚠️ Please connect to a repository first (Repository Setup)")
        return
    
    commit_selector = st.session_state.commit_selector
    
    # 필터 옵션
    col1, col2, col3 = st.columns(3)
    
    with col1:
        max_commits = st.slider("Max Commits to Show", 10, 200, 50)
        exclude_test_commits = st.checkbox("Exclude Test Commits", True)
    
    with col2:
        author_filter = st.text_input("Filter by Author", "")
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=30), datetime.now()),
            max_value=datetime.now()
        )
    
    with col3:
        search_query = st.text_input("Search in Messages", "")
        if st.button("🔍 Search Commits"):
            if search_query:
                search_results = commit_selector.search_commits(search_query, "message", max_commits)
                display_commit_list(search_results, "Search Results")
    
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
            st.info("No commits found matching the criteria")
            
    except Exception as e:
        st.error(f"Failed to load commits: {e}")


def display_commit_selection_ui(commits: List[CommitInfo], commit_selector: CommitSelector):
    """커밋 선택 UI 표시"""
    st.subheader(f"Available Commits ({len(commits)})")
    
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
    
    # 상호작용 가능한 테이블
    with st.form("commit_selection_form"):
        st.markdown("Select commits to analyze:")
        
        # 커밋별 체크박스
        commit_checkboxes = {}
        for i, commit in enumerate(commits):
            col1, col2, col3, col4, col5 = st.columns([0.5, 1.5, 3, 1.5, 1])
            
            with col1:
                is_selected = st.checkbox("", key=f"commit_{i}")
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
            with st.expander(f"Details: {commit.short_hash}", expanded=False):
                show_commit_details(commit, commit_selector)
        
        # 액션 선택
        action = st.selectbox(
            "Action:",
            ["Select Action", "Select All", "Clear All", "Analyze Selected"],
            help="Choose what to do with the commit selection"
        )
        
        # 단일 제출 버튼
        submit = st.form_submit_button("Execute Action", type="primary")
        
        # 선택된 커밋들 처리
        if submit and action != "Select Action":
            if action == "Select All":
                selected_commits = [commit.hash for commit in commits]
                st.success(f"✅ Selected all {len(selected_commits)} commits")
            elif action == "Clear All":
                selected_commits = []
                st.info("🔄 Cleared all selections")
            else:  # Analyze Selected
                selected_commits = [commit_hash for commit_hash, is_selected in commit_checkboxes.items() if is_selected]
            
            st.session_state.selected_commits = selected_commits
            
            if action == "Analyze Selected" and selected_commits:
                # 선택된 커밋들의 통합 변경사항 계산
                try:
                    combined_changes = commit_selector.calculate_combined_changes(selected_commits)
                    
                    # 파이프라인 컨텍스트 생성
                    st.session_state.pipeline_context = create_pipeline_context(
                        st.session_state.config,
                        st.session_state.repo_path,
                        selected_commits,
                        combined_changes
                    )
                    
                    st.success(f"✅ Selected {len(selected_commits)} commits for analysis")
                    
                    # 통합 변경사항 미리보기
                    show_combined_changes_preview(combined_changes)
                    
                    # 다음 단계로 진행 안내
                    st.info("📍 Go to **Pipeline Execution** to start the test generation process")
                    
                except Exception as e:
                    st.error(f"❌ Failed to analyze selected commits: {e}")
    
    # 현재 선택된 커밋들 표시
    if st.session_state.selected_commits:
        with st.sidebar:
            st.subheader("Selected Commits")
            for commit_hash in st.session_state.selected_commits:
                commit = next((c for c in commits if c.hash == commit_hash), None)
                if commit:
                    st.text(f"• {commit.short_hash}: {commit.message[:30]}...")


def show_commit_details(commit: CommitInfo, commit_selector: CommitSelector):
    """커밋 상세 정보 표시"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.text(f"Hash: {commit.hash}")
        st.text(f"Author: {commit.author}")
        st.text(f"Date: {commit.date}")
        st.text(f"Changes: +{commit.additions}/-{commit.deletions}")
    
    with col2:
        st.text(f"Files changed: {len(commit.files_changed)}")
        if commit.is_test_commit:
            st.warning("🧪 Test-related commit")
    
    # 변경된 파일 목록
    if commit.files_changed:
        st.text("Changed files:")
        for file_path in commit.files_changed[:10]:  # 최대 10개만 표시
            st.code(file_path, language="text")
        
        if len(commit.files_changed) > 10:
            st.text(f"... and {len(commit.files_changed) - 10} more files")
    
    # 전체 커밋 정보 조회 (form 내부에서는 버튼 대신 자동으로 표시)
    try:
        full_details = commit_selector.get_commit_details(commit.hash)
        if full_details:
            with st.expander("📋 Full Commit Details", expanded=False):
                st.json(full_details, expanded=False)
    except Exception as e:
        st.text(f"Details unavailable: {e}")


def show_combined_changes_preview(combined_changes: Dict[str, Any]):
    """통합 변경사항 미리보기"""
    st.subheader("📊 Combined Changes Preview")
    
    summary = combined_changes.get('summary', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Files Changed", summary.get('total_files', 0))
    with col2:
        st.metric("Lines Added", summary.get('total_additions', 0))
    with col3:
        st.metric("Lines Deleted", summary.get('total_deletions', 0))
    with col4:
        st.metric("Net Changes", summary.get('net_changes', 0))
    
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
                title="Top Changed Files",
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
    st.header("⚙️ Pipeline Execution")
    
    if not st.session_state.pipeline_context:
        st.warning("⚠️ Please select commits first (Commit Selection)")
        return
    
    context = st.session_state.pipeline_context
    orchestrator = st.session_state.pipeline_orchestrator
    
    # 파이프라인 설정
    st.subheader("Pipeline Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"📍 Repository: {context.repo_path}")
        st.info(f"🔄 Selected Commits: {len(context.selected_commits)}")
    
    with col2:
        # 실행할 단계 선택
        stages_to_run = st.multiselect(
            "Stages to Execute",
            options=[stage.value for stage in orchestrator.stage_order],
            default=[stage.value for stage in orchestrator.stage_order],
            help="Select which pipeline stages to run"
        )
        
        # 실행 모드
        execution_mode = st.radio(
            "Execution Mode",
            ["Full Pipeline", "Stage by Stage"],
            help="Full Pipeline runs all stages at once, Stage by Stage allows step-by-step execution"
        )
    
    # 파이프라인 실행 버튼
    if st.button("🚀 Start Pipeline Execution", type="primary"):
        if stages_to_run:
            # 선택된 단계들 변환
            selected_stages = [PipelineStage(stage) for stage in stages_to_run]
            
            if execution_mode == "Full Pipeline":
                asyncio.run(execute_full_pipeline(orchestrator, context, selected_stages))
            else:
                st.session_state.pipeline_stages = selected_stages
                st.session_state.current_stage_index = 0
                st.info("Stage by Stage mode selected. Use the controls below to execute each stage.")
        else:
            st.error("Please select at least one stage to execute")
    
    # 단계별 실행 모드 UI
    if execution_mode == "Stage by Stage" and hasattr(st.session_state, 'pipeline_stages'):
        show_stage_by_stage_execution(orchestrator, context)
    
    # 진행상황 표시
    show_progress_monitoring()
    
    # 현재 결과 표시
    if st.session_state.pipeline_results:
        show_pipeline_results_preview()


async def execute_full_pipeline(orchestrator, context, stages):
    """전체 파이프라인 실행"""
    st.info("🔄 Executing pipeline...")
    
    # 진행상황 표시를 위한 플레이스홀더
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    try:
        # 비동기 실행
        results = await orchestrator.execute_pipeline(context, stages)
        st.session_state.pipeline_results = results
        
        # 실행 완료 알림
        success_count = sum(1 for result in results.values() if result.status == StageStatus.COMPLETED)
        total_count = len(results)
        
        if success_count == total_count:
            st.success(f"✅ Pipeline completed successfully! ({success_count}/{total_count} stages)")
        else:
            st.warning(f"⚠️ Pipeline completed with issues ({success_count}/{total_count} stages successful)")
        
    except Exception as e:
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
    st.subheader("📊 Pipeline Results Preview")
    
    results = st.session_state.pipeline_results
    
    # 단계별 상태 표시
    col1, col2, col3, col4 = st.columns(4)
    
    completed = sum(1 for r in results.values() if r.status == StageStatus.COMPLETED)
    failed = sum(1 for r in results.values() if r.status == StageStatus.FAILED)
    running = sum(1 for r in results.values() if r.status == StageStatus.RUNNING)
    pending = sum(1 for r in results.values() if r.status == StageStatus.PENDING)
    
    with col1:
        st.metric("Completed", completed, delta=None)
    with col2:
        st.metric("Failed", failed, delta=None)
    with col3:
        st.metric("Running", running, delta=None)
    with col4:
        st.metric("Pending", pending, delta=None)
    
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
                        if isinstance(value, list):
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


def show_results_export():
    """결과 내보내기 페이지"""
    st.header("📥 Results & Export")
    
    if not st.session_state.pipeline_results:
        st.warning("⚠️ No pipeline results available. Please execute the pipeline first.")
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
    
    # 상세 결과 표시
    st.subheader("📋 Detailed Results")
    
    # 탭으로 구분
    tabs = st.tabs(["Test Code", "Test Scenarios", "Analysis Results", "Export Options"])
    
    with tabs[0]:
        show_test_code_results(results)
    
    with tabs[1]:
        show_test_scenario_results(results)
    
    with tabs[2]:
        show_analysis_results(results)
    
    with tabs[3]:
        show_export_options(results)


def show_test_code_results(results):
    """테스트 코드 결과 표시"""
    test_code_result = results.get(PipelineStage.TEST_CODE_GENERATION)
    
    if not test_code_result or not test_code_result.data:
        st.info("No test code generated")
        return
    
    generated_tests = test_code_result.data.get('generated_tests', [])
    
    if generated_tests:
        st.write(f"Generated {len(generated_tests)} test cases:")
        
        for i, test in enumerate(generated_tests):
            with st.expander(f"Test {i+1}: {test.name if hasattr(test, 'name') else f'Test_{i+1}'}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if hasattr(test, 'description'):
                        st.text(f"Description: {test.description}")
                    if hasattr(test, 'test_type'):
                        st.text(f"Type: {test.test_type}")
                    if hasattr(test, 'priority'):
                        st.text(f"Priority: {test.priority}")
                
                with col2:
                    if hasattr(test, 'assertions'):
                        st.text(f"Assertions: {len(test.assertions)}")
                    if hasattr(test, 'dependencies'):
                        st.text(f"Dependencies: {len(test.dependencies)}")
                
                # 테스트 코드 표시
                if hasattr(test, 'code'):
                    st.code(test.code, language="python")


def show_test_scenario_results(results):
    """테스트 시나리오 결과 표시"""
    scenario_result = results.get(PipelineStage.TEST_SCENARIO_GENERATION)
    
    if not scenario_result or not scenario_result.data:
        st.info("No test scenarios generated")
        return
    
    test_scenarios = scenario_result.data.get('test_scenarios', [])
    
    if test_scenarios:
        st.write(f"Generated {len(test_scenarios)} test scenarios:")
        
        # 시나리오 테이블
        scenario_data = []
        for i, scenario in enumerate(test_scenarios):
            scenario_data.append({
                'ID': getattr(scenario, 'scenario_id', f'S{i+1}'),
                'Feature': getattr(scenario, 'feature', 'N/A'),
                'Description': getattr(scenario, 'description', '')[:50] + '...',
                'Priority': getattr(scenario, 'priority', 'Medium'),
                'Type': getattr(scenario, 'test_type', 'Functional'),
                'Steps': len(getattr(scenario, 'test_steps', []))
            })
        
        scenario_df = pd.DataFrame(scenario_data)
        st.dataframe(scenario_df, use_container_width=True)
        
        # 개별 시나리오 상세보기
        selected_scenario = st.selectbox(
            "Select scenario for details:",
            options=range(len(test_scenarios)),
            format_func=lambda x: f"{scenario_data[x]['ID']}: {scenario_data[x]['Feature']}"
        )
        
        if selected_scenario is not None:
            scenario = test_scenarios[selected_scenario]
            
            st.subheader(f"Scenario Details: {getattr(scenario, 'scenario_id', 'N/A')}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.text(f"Feature: {getattr(scenario, 'feature', 'N/A')}")
                st.text(f"Priority: {getattr(scenario, 'priority', 'Medium')}")
                st.text(f"Type: {getattr(scenario, 'test_type', 'Functional')}")
            
            with col2:
                st.text(f"Preconditions: {len(getattr(scenario, 'preconditions', []))}")
                st.text(f"Test Steps: {len(getattr(scenario, 'test_steps', []))}")
                st.text(f"Expected Results: {len(getattr(scenario, 'expected_results', []))}")
            
            # 상세 내용
            if hasattr(scenario, 'description'):
                st.text(f"Description: {scenario.description}")
            
            if hasattr(scenario, 'test_steps') and scenario.test_steps:
                st.subheader("Test Steps:")
                for i, step in enumerate(scenario.test_steps):
                    st.text(f"{i+1}. {step}")


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
    st.subheader("Export Options")
    
    # 내보내기 형식 선택
    export_formats = st.multiselect(
        "Select Export Formats:",
        ["JSON", "Excel", "Markdown Report", "Test Code Files"],
        default=["JSON", "Excel"]
    )
    
    # 내보내기 설정
    col1, col2 = st.columns(2)
    
    with col1:
        include_raw_data = st.checkbox("Include Raw Data", True)
        include_metadata = st.checkbox("Include Metadata", True)
    
    with col2:
        compress_output = st.checkbox("Compress Output", False)
        timestamp_filename = st.checkbox("Add Timestamp to Filename", True)
    
    # 내보내기 실행
    if st.button("📥 Export Results", type="primary"):
        try:
            export_files = export_results(
                results,
                export_formats,
                include_raw_data,
                include_metadata,
                compress_output,
                timestamp_filename
            )
            
            st.success(f"✅ Exported {len(export_files)} files successfully!")
            
            # 다운로드 링크 제공
            for file_path in export_files:
                with open(file_path, 'rb') as f:
                    st.download_button(
                        label=f"Download {Path(file_path).name}",
                        data=f.read(),
                        file_name=Path(file_path).name,
                        mime='application/octet-stream'
                    )
                    
        except Exception as e:
            st.error(f"❌ Export failed: {e}")


def export_results(
    results,
    formats,
    include_raw_data,
    include_metadata,
    compress_output,
    timestamp_filename
):
    """결과 내보내기 실행"""
    export_files = []
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if timestamp_filename else ''
    
    # 출력 디렉토리 확인
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # JSON 내보내기
    if "JSON" in formats:
        json_data = {}
        
        for stage, result in results.items():
            json_data[stage.value] = {
                'status': result.status.value,
                'execution_time': result.execution_time,
                'errors': result.errors,
                'warnings': result.warnings
            }
            
            if include_raw_data:
                json_data[stage.value]['data'] = result.data
            
            if include_metadata:
                json_data[stage.value]['metadata'] = result.metadata
        
        json_filename = f"test_generation_results{'_' + timestamp if timestamp else ''}.json"
        json_path = output_dir / json_filename
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        
        export_files.append(str(json_path))
    
    # Excel 내보내기 (기본적인 데이터만)
    if "Excel" in formats:
        excel_filename = f"test_results{'_' + timestamp if timestamp else ''}.xlsx"
        excel_path = output_dir / excel_filename
        
        # 간단한 결과 요약을 Excel로 내보내기
        summary_data = []
        for stage, result in results.items():
            summary_data.append({
                'Stage': stage.value,
                'Status': result.status.value,
                'Execution Time': result.execution_time,
                'Errors': len(result.errors),
                'Warnings': len(result.warnings),
                'Data Items': len(result.data) if result.data else 0
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(excel_path, index=False, sheet_name='Pipeline Summary')
        
        export_files.append(str(excel_path))
    
    # Markdown 리포트
    if "Markdown Report" in formats:
        md_filename = f"test_generation_report{'_' + timestamp if timestamp else ''}.md"
        md_path = output_dir / md_filename
        
        md_content = generate_markdown_report(results)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        export_files.append(str(md_path))
    
    return export_files


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