"""
Git Analyzer Module - VCS 변경사항 분석

이 모듈은 Git 저장소에서 커밋 간 변경사항을 분석하고,
테스트 생성에 필요한 정보를 추출합니다.
"""
import os
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import git
from git import Commit, Diff, Repo
from tenacity import retry, stop_after_attempt, wait_exponential

from .vcs_models import FileChange, CommitAnalysis

# 로깅 설정
logger = logging.getLogger(__name__)


class GitAnalyzer:
    """Git 저장소 분석 클래스"""
    
    SUPPORTED_LANGUAGES = {
        '.py': 'python',
        '.java': 'java',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.cpp': 'cpp',
        '.c': 'c',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
    }
    
    def __init__(self, repo_path: str, default_branch: str = "main"):
        """
        GitAnalyzer 초기화
        
        Args:
            repo_path: Git 저장소 경로
            default_branch: 기본 브랜치 이름 (기본값: "main")
        """
        self.repo_path = Path(repo_path).resolve()
        self.default_branch = default_branch
        self._repo: Optional[Repo] = None
        self._initialize_repo()
    
    def _initialize_repo(self) -> None:
        """Git 저장소 초기화 및 검증"""
        try:
            self._repo = Repo(self.repo_path)
            if self._repo.bare:
                raise ValueError(f"Cannot analyze bare repository at {self.repo_path}")
            logger.info(f"Successfully initialized repository at {self.repo_path}")
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Invalid Git repository at {self.repo_path}")
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            raise
    
    @staticmethod
    def clone_remote_repo(remote_url: str, clone_dir: Optional[str] = None, branch: Optional[str] = None) -> str:
        """
        원격 Git 저장소(GitHub/GitLab 등)에서 저장소를 클론하여 로컬 경로 반환

        Args:
            remote_url: 원격 저장소 URL (예: https://github.com/user/repo.git)
            clone_dir: 클론할 임시 디렉터리 (None이면 임시 디렉터리 생성)
            branch: 특정 브랜치만 클론하려면 브랜치명 지정

        Returns:
            클론된 저장소의 로컬 경로(str)
        """

        if clone_dir is None:
            clone_dir = tempfile.mkdtemp(prefix="git_analyzer_clone_")

        try:
            clone_args = {}
            if branch:
                clone_args["branch"] = branch
            Repo.clone_from(remote_url, clone_dir, **clone_args)

            logger.info(f"Cloned remote repo {remote_url} to {clone_dir}")

            return clone_dir
        
        except Exception as e:
            logger.error(f"Failed to clone remote repo: {e}")
            # 클론 실패 시 임시 디렉터리 정리
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
            raise

    @classmethod
    def from_remote(cls, remote_url: str, branch: Optional[str] = None, default_branch: str = "main"):
        """
        원격 저장소를 클론하여 GitAnalyzer 인스턴스 생성

        Args:
            remote_url: 원격 저장소 URL
            branch: 분석할 브랜치명 (None이면 기본 브랜치)
            default_branch: 기본 브랜치명

        Returns:
            GitAnalyzer 인스턴스
        """
        clone_dir = cls.clone_remote_repo(remote_url, branch=branch or default_branch)

        return cls(clone_dir, default_branch=branch or default_branch)

    @property
    def repo(self) -> Repo:
        """Git 저장소 객체 반환"""
        if self._repo is None:
            self._initialize_repo()
        return self._repo
    
    def get_commits_between(
        self,
        start_commit: Optional[str] = None,
        end_commit: Optional[str] = None,
        branch: Optional[str] = None,
        max_count: int = 50
    ) -> List[Commit]:
        """
        두 커밋 사이의 커밋 목록 반환
        
        Args:
            start_commit: 시작 커밋 (None이면 최초 커밋)
            end_commit: 종료 커밋 (None이면 최신 커밋)
            branch: 분석할 브랜치 (None이면 현재 브랜치)
            max_count: 최대 분석할 커밋 수
            
        Returns:
            커밋 목록
        """
        branch = branch or self.repo.active_branch.name
        
        try:
            if end_commit:
                commits = list(self.repo.iter_commits(
                    f"{start_commit or ''}..{end_commit}",
                    max_count=max_count
                ))
            else:
                commits = list(self.repo.iter_commits(
                    branch,
                    max_count=max_count
                ))
            
            logger.info(f"Found {len(commits)} commits to analyze")
            return commits
            
        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            raise
    
    def analyze_commit(self, commit: Commit) -> CommitAnalysis:
        """
        단일 커밋 분석
        
        Args:
            commit: 분석할 커밋 객체
            
        Returns:
            커밋 분석 결과
        """
        logger.debug(f"Analyzing commit {commit.hexsha}")
        
        # 기본 커밋 정보 추출
        analysis = CommitAnalysis(
            commit_hash=commit.hexsha,
            author=commit.author.name,
            author_email=commit.author.email,
            commit_date=datetime.fromtimestamp(commit.committed_date),
            message=commit.message.strip(),
            files_changed=[],
            tags=[tag.name for tag in self.repo.tags if tag.commit == commit]
        )
        
        # 파일 변경사항 분석
        if commit.parents:
            # 일반 커밋인 경우
            parent = commit.parents[0]
            diffs = parent.diff(commit)
        else:
            # 초기 커밋인 경우
            diffs = commit.diff(None)
        
        for diff in diffs:
            file_change = self._analyze_diff(diff)
            if file_change:
                analysis.files_changed.append(file_change)
                analysis.total_additions += file_change.additions
                analysis.total_deletions += file_change.deletions
        
        return analysis
    
    def _analyze_diff(self, diff: Diff) -> Optional[FileChange]:
        """
        Diff 객체 분석하여 파일 변경사항 추출
        
        Args:
            diff: Git diff 객체
            
        Returns:
            파일 변경사항 또는 None
        """
        try:
            # 변경 유형 결정
            if diff.new_file:
                change_type = 'added'
                file_path = diff.b_path
            elif diff.deleted_file:
                change_type = 'deleted'
                file_path = diff.a_path
            elif diff.renamed_file:
                change_type = 'renamed'
                file_path = diff.b_path
            else:
                change_type = 'modified'
                file_path = diff.b_path or diff.a_path
            
            # 파일 확장자로 언어 추측
            ext = Path(file_path).suffix.lower()
            language = self.SUPPORTED_LANGUAGES.get(ext)
            
            # 변경사항 생성
            file_change = FileChange(
                file_path=file_path,
                change_type=change_type,
                old_path=diff.a_path if diff.renamed_file else None,
                language=language
            )
            
            # diff 내용 분석 (삭제된 파일 제외)
            if change_type != 'deleted' and diff.diff:
                diff_content = diff.diff.decode('utf-8', errors='ignore')
                file_change.diff_content = diff_content
                
                # 추가/삭제 라인 수 계산
                additions = 0
                deletions = 0
                for line in diff_content.split('\n'):
                    if line.startswith('+') and not line.startswith('+++'):
                        additions += 1
                    elif line.startswith('-') and not line.startswith('---'):
                        deletions += 1
                
                file_change.additions = additions
                file_change.deletions = deletions
                
                # 언어별 함수/클래스 변경사항 추출
                if language:
                    file_change.functions_changed = self._extract_changed_functions(
                        diff_content, language
                    )
                    file_change.classes_changed = self._extract_changed_classes(
                        diff_content, language
                    )
            
            return file_change
            
        except Exception as e:
            logger.warning(f"Failed to analyze diff: {e}")
            return None
    
    def _extract_changed_functions(self, diff_content: str, language: str) -> List[str]:
        """
        diff에서 변경된 함수 추출 (언어별 간단한 휴리스틱)
        
        Args:
            diff_content: diff 내용
            language: 프로그래밍 언어
            
        Returns:
            변경된 함수 이름 목록
        """
        functions = set()
        lines = diff_content.split('\n')
        
        # 언어별 함수 패턴 (간단한 버전)
        patterns = {
            'python': r'^\s*def\s+(\w+)\s*\(',
            'java': r'^\s*(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(',
            'javascript': r'^\s*(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()',
            'typescript': r'^\s*(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()',
            'go': r'^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(',
        }
        
        import re
        pattern = patterns.get(language)
        if not pattern:
            return []
        
        for line in lines:
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                match = re.search(pattern, line[1:])
                if match:
                    # 여러 그룹 중 첫 번째 매치된 것 사용
                    for group in match.groups():
                        if group:
                            functions.add(group)
                            break
        
        return list(functions)
    
    def _extract_changed_classes(self, diff_content: str, language: str) -> List[str]:
        """
        diff에서 변경된 클래스 추출 (언어별 간단한 휴리스틱)
        
        Args:
            diff_content: diff 내용
            language: 프로그래밍 언어
            
        Returns:
            변경된 클래스 이름 목록
        """
        classes = set()
        lines = diff_content.split('\n')
        
        # 언어별 클래스 패턴 (간단한 버전)
        patterns = {
            'python': r'^\s*class\s+(\w+)',
            'java': r'^\s*(?:public|private|protected)?\s*class\s+(\w+)',
            'javascript': r'^\s*class\s+(\w+)',
            'typescript': r'^\s*(?:export\s+)?class\s+(\w+)',
            'csharp': r'^\s*(?:public|private|protected)?\s*class\s+(\w+)',
            'cpp': r'^\s*class\s+(\w+)',
        }
        
        import re
        pattern = patterns.get(language)
        if not pattern:
            return []
        
        for line in lines:
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
                match = re.search(pattern, line[1:])
                if match:
                    classes.add(match.group(1))
        
        return list(classes)
    
    def analyze_commit_range(
        self,
        start_commit: Optional[str] = None,
        end_commit: Optional[str] = None,
        branch: Optional[str] = None,
        max_count: int = 50
    ) -> List[CommitAnalysis]:
        """
        커밋 범위 분석
        
        Args:
            start_commit: 시작 커밋
            end_commit: 종료 커밋
            branch: 분석할 브랜치
            max_count: 최대 분석할 커밋 수
            
        Returns:
            커밋 분석 결과 목록
        """
        commits = self.get_commits_between(start_commit, end_commit, branch, max_count)
        analyses = []
        
        for i, commit in enumerate(commits):
            logger.info(f"Analyzing commit {i+1}/{len(commits)}: {commit.hexsha[:8]}")
            try:
                analysis = self.analyze_commit(commit)
                analyses.append(analysis)
            except Exception as e:
                logger.error(f"Failed to analyze commit {commit.hexsha}: {e}")
                continue
        
        return analyses
    
    def get_file_history(self, file_path: str, max_count: int = 10) -> List[CommitAnalysis]:
        """
        특정 파일의 변경 이력 분석
        
        Args:
            file_path: 파일 경로
            max_count: 최대 분석할 커밋 수
            
        Returns:
            파일과 관련된 커밋 분석 결과 목록
        """
        try:
            commits = list(self.repo.iter_commits(paths=file_path, max_count=max_count))
            analyses = []
            
            for commit in commits:
                analysis = self.analyze_commit(commit)
                # 해당 파일과 관련된 변경사항만 필터링
                relevant_changes = [
                    fc for fc in analysis.files_changed
                    if fc.file_path == file_path or fc.old_path == file_path
                ]
                analysis.files_changed = relevant_changes
                analyses.append(analysis)
            
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to get file history for {file_path}: {e}")
            return []
    
    def get_branch_diff(self, source_branch: str, target_branch: str) -> List[FileChange]:
        """
        두 브랜치 간 차이 분석
        
        Args:
            source_branch: 소스 브랜치
            target_branch: 타겟 브랜치
            
        Returns:
            파일 변경사항 목록
        """
        try:
            source = self.repo.heads[source_branch].commit
            target = self.repo.heads[target_branch].commit
            
            diffs = target.diff(source)
            changes = []
            
            for diff in diffs:
                change = self._analyze_diff(diff)
                if change:
                    changes.append(change)
            
            return changes
            
        except Exception as e:
            logger.error(f"Failed to get branch diff: {e}")
            return []
    
    def find_related_files(self, file_path: str) -> List[str]:
        """
        특정 파일과 관련된 파일 찾기 (같이 자주 변경되는 파일)
        
        Args:
            file_path: 기준 파일 경로
            
        Returns:
            관련 파일 경로 목록
        """
        try:
            # 해당 파일이 변경된 커밋들 찾기
            commits = list(self.repo.iter_commits(paths=file_path, max_count=50))
            
            # 각 커밋에서 함께 변경된 파일들 수집
            related_files = {}
            for commit in commits:
                for item in commit.stats.files:
                    if item != file_path:
                        related_files[item] = related_files.get(item, 0) + 1
            
            # 빈도순으로 정렬
            sorted_files = sorted(
                related_files.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [f[0] for f in sorted_files[:10]]  # 상위 10개만 반환
            
        except Exception as e:
            logger.error(f"Failed to find related files: {e}")
            return []
