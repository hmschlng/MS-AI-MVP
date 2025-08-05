#!/usr/bin/env python
"""
소스 파일 자동 생성 스크립트

이전에 생성한 artifact의 내용을 실제 파일로 생성합니다.
"""
import os
from pathlib import Path


def create_file(file_path: str, content: str):
    """파일 생성 헬퍼 함수"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    print(f"✓ Created: {file_path}")


def create_git_analyzer():
    """git_analyzer.py 생성"""
    content = '''"""
Git Analyzer Module - VCS 변경사항 분석

이 모듈은 Git 저장소에서 커밋 간 변경사항을 분석하고,
테스트 생성에 필요한 정보를 추출합니다.
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

import git
from git import Repo, Commit, Diff
from tenacity import retry, stop_after_attempt, wait_exponential

# 로깅 설정
logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """파일 변경 정보를 담는 데이터 클래스"""
    file_path: str
    change_type: str  # 'added', 'modified', 'deleted', 'renamed'
    old_path: Optional[str] = None  # renamed의 경우 이전 경로
    additions: int = 0
    deletions: int = 0
    diff_content: str = ""
    language: Optional[str] = None
    functions_changed: List[str] = field(default_factory=list)
    classes_changed: List[str] = field(default_factory=list)


@dataclass
class CommitAnalysis:
    """커밋 분석 결과를 담는 데이터 클래스"""
    commit_hash: str
    author: str
    author_email: str
    commit_date: datetime
    message: str
    files_changed: List[FileChange]
    total_additions: int = 0
    total_deletions: int = 0
    branch: Optional[str] = None
    tags: List[str] = field(default_factory=list)


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
                for line in diff_content.split('\\n'):
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
        lines = diff_content.split('\\n')
        
        # 언어별 함수 패턴 (간단한 버전)
        patterns = {
            'python': r'^\\s*def\\s+(\\w+)\\s*\\(',
            'java': r'^\\s*(?:public|private|protected)?\\s*\\w+\\s+(\\w+)\\s*\\(',
            'javascript': r'^\\s*(?:function\\s+(\\w+)|const\\s+(\\w+)\\s*=\\s*(?:async\\s*)?\\()',
            'typescript': r'^\\s*(?:function\\s+(\\w+)|const\\s+(\\w+)\\s*=\\s*(?:async\\s*)?\\()',
            'go': r'^\\s*func\\s+(?:\\(\\w+\\s+\\*?\\w+\\)\\s+)?(\\w+)\\s*\\(',
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
        lines = diff_content.split('\\n')
        
        # 언어별 클래스 패턴 (간단한 버전)
        patterns = {
            'python': r'^\\s*class\\s+(\\w+)',
            'java': r'^\\s*(?:public|private|protected)?\\s*class\\s+(\\w+)',
            'javascript': r'^\\s*class\\s+(\\w+)',
            'typescript': r'^\\s*(?:export\\s+)?class\\s+(\\w+)',
            'csharp': r'^\\s*(?:public|private|protected)?\\s*class\\s+(\\w+)',
            'cpp': r'^\\s*class\\s+(\\w+)',
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
'''
    create_file("src/ai_test_generator/core/git_analyzer.py", content)


def create_cli():
    """cli.py 생성"""
    # CLI 파일 내용이 너무 길어서 일부만 포함
    content = '''"""
AI Test Generator CLI Interface

테스트 코드 자동 생성 도구의 명령줄 인터페이스
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
import logging
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.logging import RichHandler
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai_test_generator.core.git_analyzer import GitAnalyzer, CommitAnalysis
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import setup_logger

# Rich console for pretty output
console = Console()

# 환경 변수 로드
load_dotenv()


@click.group()
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Set the logging level'
)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Path to configuration file'
)
@click.pass_context
def cli(ctx, log_level, config):
    """AI Test Generator - 테스트 코드 자동 생성 도구"""
    # 로깅 설정
    setup_logger(log_level)
    
    # 설정 로드
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config(config_file=config) if config else Config()
    
    console.print(
        "[bold blue]AI Test Generator[/bold blue] - 테스트 코드 자동 생성 도구",
        style="bold"
    )


@cli.command()
@click.pass_context
def check_config(ctx):
    """환경 설정 확인"""
    console.print("\\n[bold]환경 설정 확인[/bold]")
    
    # 필수 환경 변수 확인
    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'AZURE_SEARCH_ENDPOINT',
        'AZURE_SEARCH_API_KEY'
    ]
    
    table = Table(title="환경 변수 상태")
    table.add_column("변수명", style="cyan")
    table.add_column("상태", style="green")
    table.add_column("값", style="yellow")
    
    all_configured = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # API 키는 일부만 표시
            if 'KEY' in var or 'TOKEN' in var:
                display_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            else:
                display_value = value
            status = "[green]✓[/green]"
        else:
            display_value = "미설정"
            status = "[red]✗[/red]"
            all_configured = False
        
        table.add_row(var, status, display_value)
    
    console.print(table)
    
    if all_configured:
        console.print("\\n[green]✓[/green] 모든 환경 변수가 올바르게 설정되었습니다.")
    else:
        console.print("\\n[red]✗[/red] 일부 환경 변수가 설정되지 않았습니다.")
        console.print("   .env 파일을 확인하거나 환경 변수를 설정해주세요.")


def main():
    """메인 엔트리포인트"""
    cli()


if __name__ == "__main__":
    main()
'''
    create_file("src/ai_test_generator/cli.py", content)


def create_config():
    """config.py 생성 (일부 간소화)"""
    content = '''"""
Configuration Management Module

환경 변수 및 설정 파일을 관리하는 모듈
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI 서비스 설정"""
    endpoint: str
    api_key: str
    deployment_name_agent: str
    deployment_name_rag: str
    deployment_name_embedding: str
    api_version: str = "2024-12-01-preview"
    
    @classmethod
    def from_env(cls) -> 'AzureOpenAIConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            endpoint=os.getenv('AZURE_OPENAI_ENDPOINT', ''),
            api_key=os.getenv('AZURE_OPENAI_API_KEY', ''),
            deployment_name_agent=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_AGENT', 'gpt-4'),
            deployment_name_rag=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_RAG', 'gpt-4'),
            deployment_name_embedding=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME_FOR_TEXT_EMBEDDING', 'text-embedding-3-small'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
        )


@dataclass
class AzureSearchConfig:
    """Azure AI Search 설정"""
    endpoint: str
    api_key: str
    index_name: str
    
    @classmethod
    def from_env(cls) -> 'AzureSearchConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            endpoint=os.getenv('AZURE_SEARCH_ENDPOINT', ''),
            api_key=os.getenv('AZURE_SEARCH_API_KEY', ''),
            index_name=os.getenv('AZURE_SEARCH_INDEX_NAME', 'test-conventions-index')
        )


@dataclass
class AppConfig:
    """애플리케이션 전체 설정"""
    output_directory: Path
    temp_directory: Path
    log_level: str
    max_concurrent_requests: int
    request_timeout: int
    retry_attempts: int
    cache_ttl: int
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """환경 변수에서 설정 로드"""
        return cls(
            output_directory=Path(os.getenv('OUTPUT_DIRECTORY', './output')),
            temp_directory=Path(os.getenv('TEMP_DIRECTORY', './temp')),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            max_concurrent_requests=int(os.getenv('MAX_CONCURRENT_REQUESTS', '5')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '60')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            cache_ttl=int(os.getenv('CACHE_TTL', '3600'))
        )


class Config:
    """통합 설정 관리 클래스"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        설정 초기화
        
        Args:
            config_file: 설정 파일 경로 (선택사항)
        """
        # 기본 환경 변수에서 로드
        self.azure_openai = AzureOpenAIConfig.from_env()
        self.azure_search = AzureSearchConfig.from_env()
        self.app = AppConfig.from_env()
        
        # 설정 파일이 있으면 오버라이드
        if config_file:
            self.load_from_file(config_file)
        
        # 디렉토리 생성
        self.app.output_directory.mkdir(parents=True, exist_ok=True)
        self.app.temp_directory.mkdir(parents=True, exist_ok=True)
    
    def load_from_file(self, config_file: str):
        """설정 파일에서 설정 로드"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 설정 업데이트
        self._update_from_dict(data)
    
    def _update_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 설정 업데이트"""
        if 'azure_openai' in data:
            for key, value in data['azure_openai'].items():
                if hasattr(self.azure_openai, key):
                    setattr(self.azure_openai, key, value)
        
        if 'azure_search' in data:
            for key, value in data['azure_search'].items():
                if hasattr(self.azure_search, key):
                    setattr(self.azure_search, key, value)
        
        if 'app' in data:
            for key, value in data['app'].items():
                if hasattr(self.app, key):
                    if key.endswith('_directory'):
                        value = Path(value)
                    setattr(self.app, key, value)
    
    def validate(self) -> List[str]:
        """설정 유효성 검증"""
        errors = []
        
        # Azure OpenAI 설정 검증
        if not self.azure_openai.endpoint:
            errors.append("Azure OpenAI endpoint is not configured")
        if not self.azure_openai.api_key:
            errors.append("Azure OpenAI API key is not configured")
        
        # Azure Search 설정 검증
        if not self.azure_search.endpoint:
            errors.append("Azure Search endpoint is not configured")
        if not self.azure_search.api_key:
            errors.append("Azure Search API key is not configured")
        
        return errors
'''
    create_file("src/ai_test_generator/utils/config.py", content)


def create_logger():
    """logger.py 생성"""
    content = '''"""
Logging Utility Module

애플리케이션 전체에서 사용할 로깅 설정 및 유틸리티
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console


# 전역 콘솔 객체
console = Console()

# 로거 이름
LOGGER_NAME = "ai_test_generator"


def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    use_rich: bool = True
) -> logging.Logger:
    """
    로거 설정
    
    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (선택사항)
        use_rich: Rich 핸들러 사용 여부
        
    Returns:
        설정된 로거 객체
    """
    # 로거 가져오기
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 기존 핸들러 제거
    logger.handlers.clear()
    
    # 포맷 설정
    if use_rich:
        # Rich 핸들러 (콘솔 출력)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True
        )
        rich_handler.setLevel(getattr(logging, log_level.upper()))
        logger.addHandler(rich_handler)
    else:
        # 기본 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러 (선택사항)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 파일에는 모든 로그 저장
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    로거 인스턴스 가져오기
    
    Args:
        name: 하위 로거 이름 (선택사항)
        
    Returns:
        로거 객체
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)


def log_execution_time(func):
    """함수 실행 시간을 로깅하는 데코레이터"""
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        try:
            logger.debug(f"Starting {func.__name__}")
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"{func.__name__} completed in {elapsed_time:.2f} seconds")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed after {elapsed_time:.2f} seconds: {str(e)}"
            )
            raise
    
    return wrapper


class LogContext:
    """로깅 컨텍스트 관리자"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        """
        로깅 컨텍스트 초기화
        
        Args:
            operation: 작업 이름
            logger: 사용할 로거 (선택사항)
        """
        self.operation = operation
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        """컨텍스트 진입"""
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation} in {elapsed_time:.2f} seconds"
            )
        else:
            self.logger.error(
                f"Failed {self.operation} after {elapsed_time:.2f} seconds: {exc_val}"
            )
        
        return False  # 예외를 다시 발생시킴


# 기본 로거 설정
_default_logger = None


def initialize_default_logger(log_level: str = "INFO", log_file: Optional[str] = None):
    """기본 로거 초기화"""
    global _default_logger
    _default_logger = setup_logger(log_level, log_file)
    return _default_logger


# 모듈 임포트 시 기본 로거 설정
initialize_default_logger()
'''
    create_file("src/ai_test_generator/utils/logger.py", content)


def create_test_file():
    """테스트 파일 생성"""
    content = '''"""
Git Analyzer Unit Tests

GitAnalyzer 클래스의 단위 테스트
"""
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest
import git
from git import Repo

# 프로젝트 루트를 Python 경로에 추가
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_test_generator.core.git_analyzer import GitAnalyzer, CommitAnalysis, FileChange


class TestGitAnalyzer:
    """GitAnalyzer 테스트 클래스"""
    
    @pytest.fixture
    def temp_repo(self):
        """테스트용 임시 Git 저장소 생성"""
        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp()
        repo = Repo.init(temp_dir)
        
        # 초기 설정
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()
        
        yield repo, temp_dir
        
        # 정리
        shutil.rmtree(temp_dir)
    
    def test_init_valid_repo(self, temp_repo):
        """유효한 저장소로 GitAnalyzer 초기화 테스트"""
        repo, temp_dir = temp_repo
        analyzer = GitAnalyzer(temp_dir)
        
        assert analyzer.repo_path == Path(temp_dir).resolve()
        assert analyzer.default_branch == "main"
        assert analyzer.repo is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
    create_file("tests/test_git_analyzer.py", content)


def create_all_files():
    """모든 소스 파일 생성"""
    print("🚀 AI Test Generator 소스 파일 생성을 시작합니다...\n")
    
    try:
        # 각 파일 생성
        create_git_analyzer()
        create_cli()
        create_config()
        create_logger()
        create_test_file()
        
        print("\n✅ 모든 소스 파일이 성공적으로 생성되었습니다!")
        print("\n다음 단계:")
        print("1. Python 환경 설정: uv venv --python 3.12.10")
        print("2. 가상환경 활성화: source .venv/bin/activate")
        print("3. 의존성 설치: uv pip install -e .")
        print("4. 환경 변수 설정: cp .env.example .env && nano .env")
        print("5. 설정 확인: ai-test-gen check-config")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        raise


if __name__ == "__main__":
    create_all_files()
