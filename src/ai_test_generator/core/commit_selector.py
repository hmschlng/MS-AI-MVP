"""
Commit Selector Module - 커밋 선택 및 변경사항 통합 모듈

사용자가 특정 커밋들을 선택하고, 선택된 커밋들의 변경사항을 통합하는 기능을 제공합니다.
"""
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from git import Repo, Commit

from ai_test_generator.utils.logger import get_logger

logger = get_logger(__name__)


def _get_utf8_env():
    """UTF-8 인코딩을 위한 환경변수 설정"""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['LC_ALL'] = 'C.UTF-8'
    # Windows에서 Git 출력 인코딩 설정
    env['LANG'] = 'en_US.UTF-8'
    return env


@dataclass
class CommitInfo:
    """커밋 정보"""
    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    files_changed: List[str]
    additions: int
    deletions: int
    is_test_commit: bool = False


@dataclass
class CommitSelection:
    """커밋 선택 정보"""
    selected_commits: List[str]
    comparison_base: Optional[str] = None  # 비교 기준 커밋 (None이면 첫 번째 커밋의 부모)
    combined_diff: Optional[Dict[str, Any]] = None


class CommitSelector:
    """커밋 선택 및 분석 클래스"""
    
    def __init__(self, repo_path: str, branch: str = "main"):
        """
        초기화
        
        Args:
            repo_path: Git 저장소 경로
            branch: 분석할 브랜치
        """
        self.repo_path = Path(repo_path)
        self.branch = branch
        
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        
        try:
            self.repo = Repo(self.repo_path)
        except Exception as e:
            raise ValueError(f"Invalid Git repository: {e}")
        
        # Windows에서 Git 인코딩 설정 확인 및 설정
        self._setup_git_encoding()
        
        logger.info(f"CommitSelector initialized for {repo_path} on branch {branch}")
    
    def _check_git_encoding_config(self) -> Dict[str, str]:
        """현재 Git 인코딩 설정 확인"""
        config_checks = {
            'core.quotepath': 'false',
            'i18n.logoutputencoding': 'utf-8',
            'i18n.commitencoding': 'utf-8'
        }
        
        current_config = {}
        for config_key in config_checks.keys():
            try:
                result = subprocess.run([
                    'git', 'config', '--local', config_key
                ], cwd=self.repo_path, capture_output=True, text=True, 
                  encoding='utf-8', errors='replace', env=_get_utf8_env())
                
                current_config[config_key] = result.stdout.strip() if result.returncode == 0 else None
            except Exception:
                current_config[config_key] = None
        
        return current_config
    
    def _setup_git_encoding(self, auto_configure: bool = None, interactive_callback=None):
        """Git 인코딩 설정"""
        try:
            # 현재 설정 확인
            current_config = self._check_git_encoding_config()
            
            # 변경이 필요한 설정 확인
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
                        'description': self._get_config_description(key)
                    })
            
            if not changes_needed:
                logger.info("Git encoding configuration is already optimal")
                return
            
            # 사용자에게 알림 및 동의 요청
            if auto_configure is None:
                should_configure = self._ask_user_permission(changes_needed, interactive_callback)
            else:
                should_configure = auto_configure
            
            if not should_configure:
                logger.info("Git encoding configuration skipped by user")
                return
            
            # 설정 변경 실행
            for change in changes_needed:
                config_key = change['key']
                config_value = change['required']
                
                subprocess.run([
                    'git', 'config', '--local', config_key, config_value
                ], cwd=self.repo_path, capture_output=True, env=_get_utf8_env(), check=True)
                
                logger.info(f"Git config updated: {config_key} = {config_value}")
            
            logger.info(f"Git encoding configuration updated successfully ({len(changes_needed)} changes)")
            
        except Exception as e:
            logger.warning(f"Could not set Git encoding configuration: {e}")
    
    def _get_config_description(self, config_key: str) -> str:
        """설정 키에 대한 설명"""
        descriptions = {
            'core.quotepath': 'Prevents Git from quoting non-ASCII characters in file paths',
            'i18n.logoutputencoding': 'Sets UTF-8 encoding for Git log output',
            'i18n.commitencoding': 'Sets UTF-8 encoding for commit messages'
        }
        return descriptions.get(config_key, f'Git configuration: {config_key}')
    
    def _ask_user_permission(self, changes_needed: List[Dict], interactive_callback=None) -> bool:
        """사용자에게 Git 설정 변경 허가 요청"""
        if interactive_callback:
            # Streamlit이나 다른 UI에서 호출되는 경우
            return interactive_callback(changes_needed)
        
        # UI 환경에서 실행되는 경우 (Streamlit 등) CLI 대화상자를 표시하지 않음
        # 이는 UI에서 별도 처리될 것으로 예상함
        try:
            import streamlit
            # Streamlit 환경에서는 CLI 대화상자를 표시하지 않고 기본값으로 처리
            logger.info("Detected Streamlit environment - skipping CLI permission dialog")
            return True  # UI에서 처리될 것으로 가정
        except ImportError:
            pass
        
        # CLI 환경에서의 기본 처리
        print("\n" + "="*80)
        print("🔧 Git Configuration Optimization Required")
        print("="*80)
        print("To properly handle non-ASCII characters (Korean, Chinese, etc.) in commit messages,")
        print("the following Git repository settings need to be updated:")
        print()
        
        for i, change in enumerate(changes_needed, 1):
            print(f"{i}. {change['key']}")
            print(f"   Description: {change['description']}")
            print(f"   Current value: '{change['current']}'")
            print(f"   Required value: '{change['required']}'")
            print()
        
        print("ℹ️  These changes will be made to the LOCAL repository configuration only.")
        print("   Your global Git settings will not be affected.")
        print("   You can revert these changes later using: git config --local --unset <key>")
        print()
        
        while True:
            response = input("Do you want to proceed with these changes? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no', '']:
                print("Git configuration optimization skipped.")
                print("Note: You may experience encoding issues with non-ASCII commit messages.")
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def reset_git_encoding_config(self):
        """Git 인코딩 설정 초기화 (사용자 요청시)"""
        try:
            config_keys = ['core.quotepath', 'i18n.logoutputencoding', 'i18n.commitencoding']
            
            for config_key in config_keys:
                subprocess.run([
                    'git', 'config', '--local', '--unset', config_key
                ], cwd=self.repo_path, capture_output=True, env=_get_utf8_env())
            
            logger.info("Git encoding configuration reset to defaults")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset Git encoding configuration: {e}")
            return False
    
    def _validate_branch(self) -> Optional[str]:
        """
        브랜치 존재 여부 확인 및 유효한 브랜치 반환
        
        Returns:
            유효한 브랜치명 또는 None (모든 브랜치 대상)
        """
        if not self.branch:
            return None
            
        try:
            # 지정된 브랜치가 존재하는지 확인
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', f'{self.branch}'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                env=_get_utf8_env()
            )
            
            if result.returncode == 0:
                logger.debug(f"Branch '{self.branch}' exists and is valid")
                return self.branch
                
            # 지정된 브랜치가 없으면 현재 브랜치 사용
            current_branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                env=_get_utf8_env()
            )
            
            if current_branch_result.returncode == 0:
                current_branch = current_branch_result.stdout.strip()
                if current_branch:
                    logger.info(f"Branch '{self.branch}' not found, using current branch '{current_branch}'")
                    return current_branch
            
            # 모든 브랜치에서 검색
            logger.info(f"Branch '{self.branch}' not found, searching all branches")
            return None
            
        except Exception as e:
            logger.warning(f"Error validating branch '{self.branch}': {e}. Using current branch.")
            return None
    
    def get_commit_list(
        self, 
        max_commits: int = 50,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
        exclude_merges: bool = True,
        exclude_test_commits: bool = True
    ) -> List[CommitInfo]:
        """
        커밋 리스트 조회
        
        Args:
            max_commits: 최대 커밋 수
            since: 시작 날짜
            until: 종료 날짜  
            author: 작성자 필터
            exclude_merges: 머지 커밋 제외
            exclude_test_commits: 테스트 커밋 제외
            
        Returns:
            커밋 정보 리스트
        """
        try:
            # Git log 명령 구성
            git_args = [
                'log',
                f'--max-count={max_commits}',
                '--pretty=format:%H|%h|%s|%an|%ai',
                '--numstat'
            ]
            
            if exclude_merges:
                git_args.append('--no-merges')
                
            if since:
                git_args.append(f'--since={since.isoformat()}')
                
            if until:
                git_args.append(f'--until={until.isoformat()}')
                
            if author:
                git_args.append(f'--author={author}')
            
            # 브랜치 존재 여부 확인 및 처리
            branch_to_use = self._validate_branch()
            if branch_to_use:
                git_args.append(branch_to_use)
            
            # Git 명령 실행 (Windows 한글 인코딩 문제 해결)
            result = subprocess.run(
                ['git'] + git_args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 디코딩 오류시 대체 문자 사용
                env=_get_utf8_env(),
                check=True
            )
            
            return self._parse_git_log_output(result.stdout, exclude_test_commits)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get commit list: {e}")
            return []
    
    def _parse_git_log_output(self, output: str, exclude_test_commits: bool) -> List[CommitInfo]:
        """Git log 출력 파싱"""
        if not output or not output.strip():
            logger.warning(f"Empty git log output received for branch '{self.branch}'. This may indicate the branch has no commits or doesn't exist.")
            return []
        
        commits = []
        lines = output.strip().split('\n')
        i = 0
        
        while i < len(lines):
            # 커밋 정보 라인
            if '|' in lines[i]:
                parts = lines[i].split('|')
                if len(parts) >= 5:
                    hash_full = parts[0]
                    hash_short = parts[1]
                    message = parts[2]
                    author = parts[3]
                    date_str = parts[4]
                    
                    try:
                        commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except ValueError:
                        # 날짜 파싱 실패시 현재 시간 사용
                        commit_date = datetime.now()
                    
                    # 다음 라인들에서 파일 변경 정보 수집
                    i += 1
                    files_changed = []
                    total_additions = 0
                    total_deletions = 0
                    
                    while i < len(lines) and not ('|' in lines[i] and len(lines[i].split('|')) >= 5):
                        if lines[i].strip():
                            # numstat 형식: additions    deletions    filename
                            parts = lines[i].split('\t')
                            if len(parts) >= 3:
                                try:
                                    additions = int(parts[0]) if parts[0] != '-' else 0
                                    deletions = int(parts[1]) if parts[1] != '-' else 0
                                    filename = parts[2]
                                    
                                    files_changed.append(filename)
                                    total_additions += additions
                                    total_deletions += deletions
                                except ValueError:
                                    pass
                        i += 1
                    
                    # 테스트 커밋 여부 판별
                    is_test_commit = self._is_test_commit(message, files_changed)
                    
                    if exclude_test_commits and is_test_commit:
                        logger.debug(f"Excluding test commit: {hash_short} - {message[:50]}")
                        continue
                    
                    commit_info = CommitInfo(
                        hash=hash_full,
                        short_hash=hash_short,
                        message=message,
                        author=author,
                        date=commit_date,
                        files_changed=files_changed,
                        additions=total_additions,
                        deletions=total_deletions,
                        is_test_commit=is_test_commit
                    )
                    
                    commits.append(commit_info)
                    continue
            
            i += 1
        
        logger.info(f"Found {len(commits)} commits")
        return commits
    
    def _is_test_commit(self, message: str, files_changed: List[str]) -> bool:
        """커밋이 테스트 관련인지 판별"""
        # 커밋 메시지 키워드 검사
        test_keywords_in_message = [
            'test', 'spec', 'unittest', 'integration test', 'e2e test',
            'add test', 'update test', 'fix test', 'test fix',
            'testing', 'coverage', 'mock', 'stub'
        ]
        
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in test_keywords_in_message):
            return True
        
        # 파일 경로 검사
        test_file_patterns = [
            'test_', '_test.', '.test.', 'spec_', '_spec.',
            '/test/', '/tests/', '/spec/', '/specs/',
            '__test__', '__tests__', '.spec.', '_spec.js',
            'test.py', 'spec.py', '_test.py', '_spec.py'
        ]
        
        test_file_count = 0
        for file_path in files_changed:
            file_path_lower = file_path.lower()
            if any(pattern in file_path_lower for pattern in test_file_patterns):
                test_file_count += 1
        
        # 변경된 파일의 50% 이상이 테스트 파일인 경우
        if files_changed and (test_file_count / len(files_changed)) >= 0.5:
            return True
        
        return False
    
    def get_commit_details(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """특정 커밋의 상세 정보 조회"""
        try:
            commit = self.repo.commit(commit_hash)
            
            # 파일 변경 정보 수집
            files_changed = []
            for item in commit.stats.files:
                file_info = commit.stats.files[item]
                files_changed.append({
                    'filename': item,
                    'additions': file_info.get('insertions', 0),
                    'deletions': file_info.get('deletions', 0),
                    'changes': file_info.get('lines', 0)
                })
            
            # Diff 정보 가져오기 (부모 커밋과 비교)
            diff_text = ""
            if commit.parents:
                diff = commit.parents[0].diff(commit, create_patch=True)
                diff_text = "\n".join([d.diff.decode('utf-8', errors='ignore') if d.diff else "" for d in diff])
            
            return {
                'hash': commit.hexsha,
                'short_hash': commit.hexsha[:8],
                'message': commit.message.strip(),
                'author': f"{commit.author.name} <{commit.author.email}>",
                'date': commit.authored_datetime,
                'parents': [p.hexsha for p in commit.parents],
                'files_changed': files_changed,
                'total_additions': commit.stats.total.get('insertions', 0),
                'total_deletions': commit.stats.total.get('deletions', 0),
                'diff': diff_text[:5000]  # 처음 5000자만 저장
            }
            
        except Exception as e:
            logger.error(f"Failed to get commit details for {commit_hash}: {e}")
            return None
    
    def calculate_combined_changes(
        self, 
        selected_commits: List[str],
        base_commit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        선택된 커밋들의 통합 변경사항 계산
        
        Args:
            selected_commits: 선택된 커밋 해시 리스트
            base_commit: 비교 기준 커밋 (None이면 자동 결정)
            
        Returns:
            통합된 변경사항 정보
        """
        if not selected_commits:
            raise ValueError("No commits selected")
        
        try:
            # 커밋들을 시간순으로 정렬
            commits = [self.repo.commit(hash_str) for hash_str in selected_commits]
            commits.sort(key=lambda c: c.authored_datetime)
            
            # 기준 커밋 결정
            if base_commit is None:
                # 가장 이른 커밋의 부모를 기준으로 사용
                earliest_commit = commits[0]
                if earliest_commit.parents:
                    base_commit = earliest_commit.parents[0].hexsha
                else:
                    # 루트 커밋인 경우 빈 트리와 비교
                    base_commit = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # Git의 empty tree SHA
            
            latest_commit = commits[-1].hexsha
            
            # Git diff를 사용하여 통합 변경사항 계산
            diff_result = subprocess.run([
                'git', 'diff', '--numstat', base_commit, latest_commit
            ], cwd=self.repo_path, capture_output=True, text=True, 
              encoding='utf-8', errors='replace', env=_get_utf8_env(), check=True)
            
            # 변경된 파일들 파싱
            files_changed = []
            total_additions = 0
            total_deletions = 0
            
            for line in diff_result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            additions = int(parts[0]) if parts[0] != '-' else 0
                            deletions = int(parts[1]) if parts[1] != '-' else 0
                            filename = parts[2]
                            
                            files_changed.append({
                                'filename': filename,
                                'additions': additions,
                                'deletions': deletions
                            })
                            
                            total_additions += additions
                            total_deletions += deletions
                        except ValueError:
                            continue
            
            # 커밋 정보들 수집
            commit_infos = []
            for commit in commits:
                commit_infos.append({
                    'hash': commit.hexsha,
                    'short_hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': commit.author.name,
                    'date': commit.authored_datetime.isoformat()
                })
            
            # 대표적인 diff 샘플 가져오기 (처음 몇 개 파일만)
            sample_diff = ""
            if files_changed[:3]:  # 처음 3개 파일의 diff만 샘플로 저장
                sample_files = [f['filename'] for f in files_changed[:3]]
                for filename in sample_files:
                    try:
                        file_diff_result = subprocess.run([
                            'git', 'diff', base_commit, latest_commit, '--', filename
                        ], cwd=self.repo_path, capture_output=True, text=True, 
                          encoding='utf-8', errors='replace', env=_get_utf8_env(), check=True)
                        
                        sample_diff += f"\n=== {filename} ===\n"
                        sample_diff += file_diff_result.stdout[:1000]  # 파일당 최대 1000자
                        sample_diff += "\n"
                        
                        if len(sample_diff) > 5000:  # 전체 샘플이 너무 커지면 중단
                            break
                            
                    except subprocess.CalledProcessError:
                        continue
            
            result = {
                'base_commit': base_commit,
                'latest_commit': latest_commit,
                'commit_range': f"{base_commit[:8]}..{latest_commit[:8]}",
                'selected_commits': selected_commits,
                'commit_details': commit_infos,
                'files_changed': files_changed,
                'summary': {
                    'total_files': len(files_changed),
                    'total_additions': total_additions,
                    'total_deletions': total_deletions,
                    'net_changes': total_additions - total_deletions
                },
                'sample_diff': sample_diff.strip()
            }
            
            logger.info(f"Combined changes calculated: {len(files_changed)} files, +{total_additions}/-{total_deletions}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate combined changes: {e}")
            raise
    
    def get_file_content_at_commit(self, commit_hash: str, file_path: str) -> Optional[str]:
        """특정 커밋에서의 파일 내용 조회"""
        try:
            result = subprocess.run([
                'git', 'show', f"{commit_hash}:{file_path}"
            ], cwd=self.repo_path, capture_output=True, text=True, 
              encoding='utf-8', errors='replace', env=_get_utf8_env(), check=True)
            
            return result.stdout
            
        except subprocess.CalledProcessError:
            # 파일이 해당 커밋에 존재하지 않음
            return None
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None
    
    def search_commits(
        self, 
        query: str,
        search_type: str = "message",  # "message", "author", "file"
        max_results: int = 20
    ) -> List[CommitInfo]:
        """커밋 검색"""
        try:
            git_args = [
                'log', 
                f'--max-count={max_results}',
                '--pretty=format:%H|%h|%s|%an|%ai',
                '--numstat'
            ]
            
            if search_type == "message":
                git_args.append(f'--grep={query}')
            elif search_type == "author":
                git_args.append(f'--author={query}')
            elif search_type == "file":
                git_args.extend(['--', query])
            
            result = subprocess.run(
                ['git'] + git_args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=_get_utf8_env(),
                check=True
            )
            
            return self._parse_git_log_output(result.stdout, exclude_test_commits=False)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git search failed: {e}")
            return []
    
    def get_branch_list(self) -> List[Dict[str, str]]:
        """브랜치 리스트 조회"""
        try:
            result = subprocess.run([
                'git', 'branch', '-a', '--format=%(refname:short)|%(HEAD)|%(upstream:short)'
            ], cwd=self.repo_path, capture_output=True, text=True, 
              encoding='utf-8', errors='replace', env=_get_utf8_env(), check=True)
            
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 2:
                        branch_name = parts[0]
                        is_current = parts[1] == '*'
                        upstream = parts[2] if len(parts) > 2 else ""
                        
                        branches.append({
                            'name': branch_name,
                            'is_current': is_current,
                            'upstream': upstream
                        })
            
            return branches
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get branch list: {e}")
            return []
    
    def create_commit_selection(self, commit_hashes: List[str], base_commit: Optional[str] = None) -> CommitSelection:
        """커밋 선택 객체 생성"""
        if not commit_hashes:
            raise ValueError("At least one commit must be selected")
        
        # 통합 변경사항 계산
        combined_diff = self.calculate_combined_changes(commit_hashes, base_commit)
        
        return CommitSelection(
            selected_commits=commit_hashes,
            comparison_base=base_commit,
            combined_diff=combined_diff
        )