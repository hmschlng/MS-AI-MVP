# Azure App Service 배포 가이드

## 준비된 파일들
- ✅ `pyproject.toml` - 의존성 관리
- ✅ `startup.py` - Azure App Service Python 시작 스크립트 (주 사용)
- ✅ `startup.sh` - Linux Bash 시작 스크립트 (백업용)
- ✅ `.deployment` - 배포 설정

## 배포 방법 (선택)

### 방법 1: Azure CLI (추천)
```bash
# 리소스 그룹 및 App Service 생성
az group create --name rg-ai-test-gen --location "Korea Central"
az appservice plan create --name plan-ai-test-gen --resource-group rg-ai-test-gen --sku B1 --is-linux
az webapp create --resource-group rg-ai-test-gen --plan plan-ai-test-gen --name [your-unique-app-name] --runtime "PYTHON|3.12"

# 환경변수 설정
az webapp config appsettings set --name [your-app-name] --resource-group rg-ai-test-gen --settings \
  AZURE_OPENAI_API_KEY="[your-api-key]" \
  AZURE_OPENAI_ENDPOINT="https://[your-resource].openai.azure.com/" \
  AZURE_OPENAI_API_VERSION="2024-02-01" \
  AZURE_OPENAI_DEPLOYMENT_NAME="[your-deployment]" \
  LOG_LEVEL="INFO" \
  WEBSITES_PORT="8000"

# 코드 배포
az webapp up --name [your-app-name] --resource-group rg-ai-test-gen --runtime "PYTHON|3.12"
```

### 방법 2: GitHub Actions
1. GitHub에 코드 푸시
2. Azure Portal에서 Deployment Center 설정
3. GitHub 연결 및 자동 배포 활성화

### 방법 3: VS Code Extension
1. Azure App Service 확장 설치
2. 리소스 생성 및 배포

## 필수 환경변수 설정

Azure Portal > App Service > Configuration > Application settings에서 다음 값들을 설정:

```
AZURE_OPENAI_API_KEY: [Azure OpenAI API 키]
AZURE_OPENAI_ENDPOINT: https://[리소스명].openai.azure.com/
AZURE_OPENAI_API_VERSION: 2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME: [배포된 모델명]
AZURE_SEARCH_ENDPOINT: https://[검색서비스명].search.windows.net (선택사항)
AZURE_SEARCH_KEY: [검색 서비스 키] (선택사항)
LOG_LEVEL: INFO
WEBSITES_PORT: 8000
```

## 배포 후 확인사항

1. **앱 상태 확인**: https://[your-app-name].azurewebsites.net
2. **로그 확인**: Portal > App Service > Log stream
3. **환경변수 확인**: 앱이 제대로 환경변수를 읽어오는지 확인

## 문제 해결

### 시작 오류
- Log stream에서 오류 메시지 확인
- startup.py의 print 문으로 디버깅

### 의존성 문제
- pyproject.toml의 버전 호환성 확인
- 특정 패키지가 Linux에서 문제되는 경우 제거

### 포트 문제
- WEBSITES_PORT 환경변수가 올바르게 설정되었는지 확인
- Streamlit이 올바른 포트로 실행되는지 로그 확인

## 성능 최적화

- **App Service Plan**: 프로덕션에서는 S1 이상 권장
- **Always On**: 콜드 스타트 방지를 위해 활성화
- **Application Insights**: 모니터링을 위해 활성화 권장