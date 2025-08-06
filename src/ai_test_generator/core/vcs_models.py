from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class FileChange:
    file_path: str
    change_type: str  # 'added', 'modified', 'deleted', 'renamed'
    old_path: Optional[str] = None
    additions: int = 0
    deletions: int = 0
    diff_content: str = ""
    language: Optional[str] = None
    functions_changed: List[str] = field(default_factory=list)
    classes_changed: List[str] = field(default_factory=list)

@dataclass
class CommitAnalysis:
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