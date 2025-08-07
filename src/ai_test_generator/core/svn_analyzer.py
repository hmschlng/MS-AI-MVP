"""
Svn Analyzer Module - VCS 변경사항 분석

이 모듈은 Svn 저장소에서 리비전 간 변경사항을 분석하고,
테스트 생성에 필요한 정보를 추출합니다.
"""
import os
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import pysvn
    from pysvn.client import Client
    PYSVN_AVAILABLE = True
except ImportError:
    PYSVN_AVAILABLE = False
    # pysvn이 없을 때 더미 클래스 정의
    class Client:
        pass

from .vcs_models import FileChange, CommitAnalysis

# 로깅 설정
logger = logging.getLogger(__name__)


class SvnAnalyzer:
    """Svn 저장소 분석 클래스"""

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

    def __init__(self, repo_url: str, local_path: Optional[str] = None):
        """
        SvnAnalyzer 초기화

        Args:
            repo_url: Svn 저장소 URL
            local_path: 체크아웃할 로컬 경로 (None이면 임시 디렉터리 생성)
        """
        if not PYSVN_AVAILABLE:
            raise ImportError("pysvn is not available. Please install pysvn to use SvnAnalyzer")
            
        self.repo_url = repo_url
        self.local_path = Path(local_path or tempfile.mkdtemp(prefix="Svn_analyzer_checkout_")).resolve()
        self.client = Client()
        self._initialize_repo()

    def _initialize_repo(self) -> None:
        """Svn 저장소 체크아웃 및 검증"""
        if not self.local_path.exists() or not any(self.local_path.iterdir()):
            try:
                logger.info(f"Checking out Svn repo {self.repo_url} to {self.local_path}")
                self.client.checkout(self.repo_url, str(self.local_path))
            except Exception as e:
                logger.error(f"Failed to checkout Svn repository: {e}")
                raise

    @staticmethod
    def checkout_remote_repo(remote_url: str, checkout_dir: Optional[str] = None) -> str:
        """
        원격 Svn 저장소에서 체크아웃하여 로컬 경로 반환

        Args:
            remote_url: 원격 저장소 URL
            checkout_dir: 체크아웃할 임시 디렉터리 (None이면 임시 디렉터리 생성)

        Returns:
            체크아웃된 저장소의 로컬 경로(str)
        """
        if checkout_dir is None:
            checkout_dir = tempfile.mkdtemp(prefix="Svn_analyzer_checkout_")
        client = Client()
        try:
            client.checkout(remote_url, checkout_dir)
            logger.info(f"Checked out remote Svn repo {remote_url} to {checkout_dir}")
            return checkout_dir
        except Exception as e:
            logger.error(f"Failed to checkout remote Svn repo: {e}")
            if os.path.exists(checkout_dir):
                shutil.rmtree(checkout_dir)
            raise

    @classmethod
    def from_remote(cls, remote_url: str):
        """
        원격 저장소를 체크아웃하여 SvnAnalyzer 인스턴스 생성

        Args:
            remote_url: 원격 저장소 URL

        Returns:
            SvnAnalyzer 인스턴스
        """
        checkout_dir = cls.checkout_remote_repo(remote_url)
        return cls(remote_url, local_path=checkout_dir)

    def get_log_entries(
        self,
        start_rev: Optional[int] = None,
        end_rev: Optional[int] = None,
        max_count: int = 50
    ) -> List[Client.log]:
        """
        리비전 범위의 로그 엔트리 반환

        Args:
            start_rev: 시작 리비전 번호 (None이면 1)
            end_rev: 종료 리비전 번호 (None이면 HEAD)
            max_count: 최대 분석할 리비전 수

        Returns:
            로그 엔트리 목록
        """
        try:
            start = pysvn.Revision(pysvn.opt_revision_kind.number, start_rev) if start_rev else pysvn.Revision(pysvn.opt_revision_kind.number, 1)
            end = pysvn.Revision(pysvn.opt_revision_kind.number, end_rev) if end_rev else pysvn.Revision(pysvn.opt_revision_kind.head)
            logs = self.client.log(
                str(self.local_path),
                revision_start=end,
                revision_end=start,
                discover_changed_paths=True,
                limit=max_count
            )
            logger.info(f"Found {len(logs)} log entries to analyze")
            return logs
        except Exception as e:
            logger.error(f"Svn log error: {e}")
            raise

    def analyze_log_entry(self, log_entry: Client.log) -> CommitAnalysis:
        """
        단일 로그 엔트리 분석

        Args:
            log_entry: 분석할 로그 엔트리

        Returns:
            커밋 분석 결과
        """
        logger.debug(f"Analyzing revision {log_entry.revision.number}")

        analysis = CommitAnalysis(
            commit_hash=str(log_entry.revision.number),
            author=log_entry.author or "",
            author_email="",  # Svn은 이메일 정보가 없음
            commit_date=datetime.fromtimestamp(log_entry.date),
            message=log_entry.message.strip() if log_entry.message else "",
            files_changed=[],
            tags=[]
        )

        for changed_path in log_entry.changed_paths:
            file_change = self._analyze_changed_path(changed_path, log_entry.revision.number)
            if file_change:
                analysis.files_changed.append(file_change)
                analysis.total_additions += file_change.additions
                analysis.total_deletions += file_change.deletions

        return analysis

    def _analyze_changed_path(self, changed_path, revision_number: int) -> Optional[FileChange]:
        """
        변경된 파일/디렉터리 분석

        Args:
            changed_path: pysvn.ChangedPath 객체
            revision_number: 해당 리비전 번호

        Returns:
            파일 변경사항 또는 None
        """
        try:
            # 변경 유형 결정
            action_map = {'A': 'added', 'D': 'deleted', 'M': 'modified', 'R': 'renamed'}
            change_type = action_map.get(changed_path.action, 'modified')
            file_path = changed_path.path
            old_path = changed_path.copyfrom_path if change_type == 'renamed' else None

            ext = Path(file_path).suffix.lower()
            language = self.SUPPORTED_LANGUAGES.get(ext)

            diff_content = ""
            additions = 0
            deletions = 0

            # diff 내용 분석 (삭제된 파일 제외)
            if change_type != 'deleted':
                try:
                    prev_rev = revision_number - 1 if revision_number > 1 else 1
                    diff = self.client.diff(
                        tmpfile=None,
                        url_or_path=str(self.local_path / file_path),
                        revision1=pysvn.Revision(pysvn.opt_revision_kind.number, prev_rev),
                        revision2=pysvn.Revision(pysvn.opt_revision_kind.number, revision_number)
                    )
                    diff_content = diff.decode('utf-8', errors='ignore')
                    for line in diff_content.split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            additions += 1
                        elif line.startswith('-') and not line.startswith('---'):
                            deletions += 1
                except Exception as e:
                    logger.warning(f"Failed to get diff for {file_path}: {e}")

            file_change = FileChange(
                file_path=file_path,
                change_type=change_type,
                old_path=old_path,
                additions=additions,
                deletions=deletions,
                diff_content=diff_content,
                language=language
            )

            # 언어별 함수/클래스 변경사항 추출
            if language and diff_content:
                file_change.functions_changed = self._extract_changed_functions(diff_content, language)
                file_change.classes_changed = self._extract_changed_classes(diff_content, language)

            return file_change

        except Exception as e:
            logger.warning(f"Failed to analyze changed path: {e}")
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

    def analyze_revision_range(
        self,
        start_rev: Optional[int] = None,
        end_rev: Optional[int] = None,
        max_count: int = 50
    ) -> List[CommitAnalysis]:
        """
        리비전 범위 분석

        Args:
            start_rev: 시작 리비전
            end_rev: 종료 리비전
            max_count: 최대 분석할 리비전 수

        Returns:
            커밋 분석 결과 목록
        """
        logs = self.get_log_entries(start_rev, end_rev, max_count)
        analyses = []

        for i, log_entry in enumerate(logs):
            logger.info(f"Analyzing revision {i+1}/{len(logs)}: {log_entry.revision.number}")
            try:
                analysis = self.analyze_log_entry(log_entry)
                analyses.append(analysis)
            except Exception as e:
                logger.error(f"Failed to analyze revision {log_entry.revision.number}: {e}")
                continue

        return analyses

    def get_file_history(self, file_path: str, max_count: int = 10) -> List[CommitAnalysis]:
        """
        특정 파일의 변경 이력 분석

        Args:
            file_path: 파일 경로
            max_count: 최대 분석할 리비전 수

        Returns:
            파일과 관련된 커밋 분석 결과 목록
        """
        try:
            logs = self.client.log(
                str(self.local_path / file_path),
                discover_changed_paths=True,
                limit=max_count
            )
            analyses = []

            for log_entry in logs:
                analysis = self.analyze_log_entry(log_entry)
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

    def get_branch_diff(self, source_url: str, target_url: str) -> List[FileChange]:
        """
        두 브랜치(또는 경로) 간 차이 분석

        Args:
            source_url: 소스 브랜치(경로) URL
            target_url: 타겟 브랜치(경로) URL

        Returns:
            파일 변경사항 목록
        """
        try:
            diff = self.client.diff(
                tmpfile=None,
                url_or_path=target_url,
                url_or_path2=source_url
            )
            diff_content = diff.decode('utf-8', errors='ignore')
            # 간단히 파일별로 분리
            changes = []
            current_file = None
            file_diff = []
            for line in diff_content.split('\n'):
                if line.startswith('Index: '):
                    if current_file and file_diff:
                        changes.append(self._parse_diff_block(current_file, '\n'.join(file_diff)))
                    current_file = line[len('Index: '):].strip()
                    file_diff = []
                else:
                    file_diff.append(line)
            if current_file and file_diff:
                changes.append(self._parse_diff_block(current_file, '\n'.join(file_diff)))
            return [c for c in changes if c]
        except Exception as e:
            logger.error(f"Failed to get branch diff: {e}")
            return []

    def _parse_diff_block(self, file_path: str, diff_content: str) -> Optional[FileChange]:
        """
        diff 블록을 FileChange로 변환

        Args:
            file_path: 파일 경로
            diff_content: diff 내용

        Returns:
            FileChange 또는 None
        """
        try:
            additions = 0
            deletions = 0
            for line in diff_content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    additions += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deletions += 1
            ext = Path(file_path).suffix.lower()
            language = self.SUPPORTED_LANGUAGES.get(ext)
            file_change = FileChange(
                file_path=file_path,
                change_type='modified',
                additions=additions,
                deletions=deletions,
                diff_content=diff_content,
                language=language
            )
            if language:
                file_change.functions_changed = self._extract_changed_functions(diff_content, language)
                file_change.classes_changed = self._extract_changed_classes(diff_content, language)
            return file_change
        except Exception as e:
            logger.warning(f"Failed to parse diff block for {file_path}: {e}")
            return None

    def find_related_files(self, file_path: str) -> List[str]:
        """
        특정 파일과 관련된 파일 찾기 (같이 자주 변경되는 파일)

        Args:
            file_path: 기준 파일 경로

        Returns:
            관련 파일 경로 목록
        """
        try:
            logs = self.client.log(
                str(self.local_path / file_path),
                discover_changed_paths=True,
                limit=50
            )
            related_files = {}
            for log_entry in logs:
                for changed_path in log_entry.changed_paths:
                    if changed_path.path != file_path:
                        related_files[changed_path.path] = related_files.get(changed_path.path, 0) + 1
            sorted_files = sorted(
                related_files.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return [f[0] for f in sorted_files[:10]]
        except Exception as e:
            logger.error(f"Failed to find related files for {file_path}: {e}")
            return []

    def close(self) -> None:
        """리소스 정리"""
        try:
            if self.local_path and self.local_path.exists():
                logger.info(f"Cleaning up local path {self.local_path}")
                import shutil
                shutil.rmtree(str(self.local_path))
        except Exception as e:
            logger.warning(f"Failed to clean up local path: {e}")