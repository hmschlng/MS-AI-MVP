#!/bin/bash

# AI Test Generator Project Setup Script
# 프로젝트 구조 생성 및 초기 설정

set -e  # 에러 발생 시 중단

echo "🚀 AI Test Generator 프로젝트 설정을 시작합니다..."

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 현재 디렉토리 확인
PROJECT_ROOT=$(pwd)
echo -e "${BLUE}프로젝트 루트: ${PROJECT_ROOT}${NC}"

# 디렉토리 구조 생성
echo -e "\n${YELLOW}1. 디렉토리 구조 생성 중...${NC}"

directories=(
    "src/ai_test_generator"
    "src/ai_test_generator/core"
    "src/ai_test_generator/utils"
    "tests"
    "data/conventions/examples"
    "docs"
    "output"
    "temp"
    "logs"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    echo -e "  ✓ $dir"
done

# __init__.py 파일 생성
echo -e "\n${YELLOW}2. __init__.py 파일 생성 중...${NC}"

# src/ai_test_generator/__init__.py
cat > src/ai_test_generator/__init__.py << 'EOF'
"""
AI Test Generator

테스트코드 및 테스트 시나리오 자동 생성 도우미
"""

__version__ = "0.1.0"
__author__ = "AI Test Generator Team"

from .core.git_analyzer import GitAnalyzer
from .utils.config import Config
from .utils.logger import get_logger, setup_logger

__all__ = [
    "GitAnalyzer",
    "Config",
    "get_logger",
    "setup_logger",
]
EOF

# src/ai_test_generator/core/__init__.py
cat > src/ai_test_generator/core/__init__.py << 'EOF'
"""
Core modules for AI Test Generator
"""

from .git_analyzer import GitAnalyzer, CommitAnalysis, FileChange

__all__ = [
    "GitAnalyzer",
    "CommitAnalysis", 
    "FileChange",
]
EOF

# src/ai_test_generator/utils/__init__.py
cat > src/ai_test_generator/utils/__init__.py << 'EOF'
"""
Utility modules for AI Test Generator
"""

from .config import Config
from .logger import get_logger, setup_logger, LogContext

__all__ = [
    "Config",
    "get_logger",
    "setup_logger",
    "LogContext",
]
EOF

# tests/__init__.py
touch tests/__init__.py

echo -e "  ✓ __init__.py 파일 생성 완료"

# .gitignore 생성
echo -e "\n${YELLOW}3. .gitignore 파일 생성 중...${NC}"
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/
.venv/

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyCharm
.idea/

# VS Code
.vscode/

# Jupyter Notebook
.ipynb_checkpoints

# pytest
.pytest_cache/
.coverage
htmlcov/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Environments
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Output directories
output/
temp/
cache/

# OS
.DS_Store
Thumbs.db

# Azure
.azure/
EOF
echo -e "  ✓ .gitignore 생성 완료"

# .env.example 생성
echo -e "\n${YELLOW}4. .env.example 파일 생성 중...${NC}"
cat > .env.example << 'EOF'
# Azure OpenAI Service 설정
AZURE_OPENAI_ENDPOINT=https://your-openai-service.openai.azure.com/
AZURE_OPENAI_API_KEY=your_openai_api_key
AZURE_OPENAI_DEPLOYMENT_NAME_FOR_AGENT=gpt-4
AZURE_OPENAI_DEPLOYMENT_NAME_FOR_RAG=gpt-4
AZURE_OPENAI_DEPLOYMENT_NAME_FOR_TEXT_EMBEDDING=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Azure AI Search 설정
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_API_KEY=your_search_api_key
AZURE_SEARCH_INDEX_NAME=test-conventions-index

# LangFuse 모니터링 (선택사항)
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com

# Git 설정
DEFAULT_GIT_BRANCH=main
MAX_COMMIT_ANALYSIS=50
GITHUB_PAT_TOKEN=your_github_pat_token  # Optional, for private repos

# 앱 설정
OUTPUT_DIRECTORY=./output
TEMP_DIRECTORY=./temp
LOG_LEVEL=INFO

# 성능 설정
MAX_CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT=60
RETRY_ATTEMPTS=3
CACHE_TTL=3600

# 테스트 생성 설정
MAX_TESTS_PER_FILE=10
INCLUDE_INTEGRATION_TESTS=true
INCLUDE_PERFORMANCE_TESTS=false
EOF
echo -e "  ✓ .env.example 생성 완료"

# README 파일 생성
echo -e "\n${YELLOW}5. 문서 파일 생성 중...${NC}"

# data/conventions/README.md
cat > data/conventions/README.md << 'EOF'
# 테스트 컨벤션 문서

이 디렉토리에는 RAG 시스템에서 사용할 테스트 방법론 및 컨벤션 문서들을 저장합니다.

## 문서 구조

- `examples/`: 테스트 코드 예제
- `guidelines/`: 테스트 작성 가이드라인
- `templates/`: 테스트 시나리오 템플릿

## 문서 형식

지원하는 문서 형식:
- Markdown (.md)
- PDF (.pdf)
- Word (.docx)
- Text (.txt)

## 인덱싱

Azure AI Search에 자동으로 인덱싱되어 테스트 생성 시 참조됩니다.
EOF

# docs/README.md
cat > docs/README.md << 'EOF'
# AI Test Generator 문서

## 목차

1. [아키텍처](architecture.md) - 시스템 아키텍처 및 설계
2. [API 문서](api.md) - API 레퍼런스
3. [사용자 가이드](user-guide.md) - 사용 방법 및 예제
4. [개발자 가이드](developer-guide.md) - 개발 및 기여 가이드

## 빠른 시작

```bash
# 설치
uv pip install -e .

# 환경 설정 확인
ai-test-gen check-config

# 저장소 분석
ai-test-gen analyze /path/to/repo

# 테스트 생성
ai-test-gen generate /path/to/repo
```
EOF

echo -e "  ✓ 문서 파일 생성 완료"

# 소스 파일 복사 여부 확인
echo -e "\n${YELLOW}6. 소스 파일 설정${NC}"
echo "제공된 Python 소스 파일들을 프로젝트에 복사하시겠습니까?"
echo "파일 목록:"
echo "  - git_analyzer.py"
echo "  - cli.py (cli_interface.py)"
echo "  - config.py"
echo "  - logger.py"
echo ""
echo "이 파일들을 직접 생성하려면 다음 명령을 실행하세요:"
echo -e "${GREEN}python -c \"from create_source_files import create_all_files; create_all_files()\"${NC}"

# Python 환경 설정 안내
echo -e "\n${YELLOW}7. Python 환경 설정${NC}"
echo "다음 단계를 따라 Python 환경을 설정하세요:"
echo ""
echo "1. uv 설치 (아직 설치하지 않은 경우):"
echo -e "   ${GREEN}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
echo ""
echo "2. Python 3.12.10 가상환경 생성:"
echo -e "   ${GREEN}uv venv --python 3.12.10${NC}"
echo ""
echo "3. 가상환경 활성화:"
echo -e "   ${GREEN}source .venv/bin/activate${NC} (Linux/macOS)"
echo -e "   ${GREEN}.venv\\Scripts\\activate${NC} (Windows)"
echo ""
echo "4. 의존성 설치:"
echo -e "   ${GREEN}uv pip install -e .${NC}"
echo ""
echo "5. 개발 의존성 설치 (선택사항):"
echo -e "   ${GREEN}uv pip install -e \".[dev]\"${NC}"

# .env 파일 설정 안내
echo -e "\n${YELLOW}8. 환경 변수 설정${NC}"
echo ".env 파일을 생성하고 Azure 서비스 정보를 입력하세요:"
echo -e "   ${GREEN}cp .env.example .env${NC}"
echo -e "   ${GREEN}nano .env${NC} (또는 선호하는 편집기 사용)"

# 완료 메시지
echo -e "\n${GREEN}✅ 프로젝트 구조 생성이 완료되었습니다!${NC}"
echo ""
echo "다음 단계:"
echo "1. Python 소스 파일 생성 또는 복사"
echo "2. Python 환경 설정 및 의존성 설치"
echo "3. .env 파일 설정"
echo "4. 테스트 실행: pytest tests/"
echo ""
echo -e "${BLUE}행운을 빕니다! 🚀${NC}"