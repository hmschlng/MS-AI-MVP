# AI Test Generator 배포 가이드

> Azure Web App 및 다양한 환경에서의 배포 방법

## 📌 개요

이 문서는 AI Test Generator를 다양한 환경에 배포하는 방법을 설명합니다. 주요 배포 환경으로는 Azure Web App, Docker 컨테이너, 온프레미스 서버 등을 다룹니다.

## 🚀 Azure Web App 배포

### 사전 요구사항

- Azure 구독
- Azure CLI 설치
- Git 설치
- Python 3.12 런타임

### 1. Azure 리소스 생성

```bash
# 리소스 그룹 생성
az group create --name rg-ai-test-generator --location koreacentral

# App Service Plan 생성 (Linux, B2 tier)
az appservice plan create \
  --name asp-ai-test-generator \
  --resource-group rg-ai-test-generator \
  --sku B2 \
  --is-linux

# Web App 생성 (Python 3.12)
az webapp create \
  --name ai-test-generator-app \
  --resource-group rg-ai-test-generator \
  --plan asp-ai-test-generator \
  --runtime "PYTHON:3.12"
```

### 2. 환경 변수 설정

```bash
# 필수 환경 변수 설정
az webapp config appsettings set \
  --name ai-test-generator-app \
  --resource-group rg-ai-test-generator \
  --settings \
    GIT_PYTHON_GIT_EXECUTABLE="/usr/bin/git" \
    GIT_PYTHON_REFRESH="quiet" \
    AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="your-api-key" \
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4" \
    AZURE_OPENAI_API_VERSION="2024-02-15-preview" \
    LANGFUSE_PUBLIC_KEY="your-public-key" \
    LANGFUSE_SECRET_KEY="your-secret-key" \
    LANGFUSE_HOST="https://cloud.langfuse.com"
```

### 3. 시작 명령 설정

```bash
# startup.sh를 시작 명령으로 설정
az webapp config set \
  --name ai-test-generator-app \
  --resource-group rg-ai-test-generator \
  --startup-file "bash /home/site/wwwroot/startup.sh"
```

### 4. 배포 설정

#### Git 배포 설정
```bash
# 로컬 Git 배포 사용자 설정
az webapp deployment user set \
  --user-name <username> \
  --password <password>

# Git URL 가져오기
az webapp deployment source config-local-git \
  --name ai-test-generator-app \
  --resource-group rg-ai-test-generator

# Git remote 추가 및 푸시
git remote add azure <git-url-from-above>
git push azure main:master
```

#### GitHub Actions 배포 (권장)
```yaml
# .github/workflows/azure-deploy.yml
name: Deploy to Azure Web App

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Deploy to Azure Web App
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'ai-test-generator-app'
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
        package: .
```

### 5. 스케일링 설정

```bash
# 자동 스케일링 규칙 설정
az monitor autoscale create \
  --resource-group rg-ai-test-generator \
  --resource /subscriptions/{subscription-id}/resourceGroups/rg-ai-test-generator/providers/Microsoft.Web/serverfarms/asp-ai-test-generator \
  --name autoscale-ai-test \
  --min-count 1 \
  --max-count 5 \
  --count 2

# CPU 기반 스케일링 규칙 추가
az monitor autoscale rule create \
  --resource-group rg-ai-test-generator \
  --autoscale-name autoscale-ai-test \
  --condition "Percentage CPU > 70 avg 5m" \
  --scale out 1

az monitor autoscale rule create \
  --resource-group rg-ai-test-generator \
  --autoscale-name autoscale-ai-test \
  --condition "Percentage CPU < 30 avg 5m" \
  --scale in 1
```

## 🐳 Docker 배포

### 1. Docker 이미지 빌드

```dockerfile
# Dockerfile
FROM python:3.12-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 환경 변수 설정
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
ENV GIT_PYTHON_REFRESH=quiet
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 포트 노출
EXPOSE 8501

# 시작 명령
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
```

### 2. 이미지 빌드 및 실행

```bash
# 이미지 빌드
docker build -t ai-test-generator:latest .

# 컨테이너 실행
docker run -d \
  --name ai-test-generator \
  -p 8501:8501 \
  -e AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/" \
  -e AZURE_OPENAI_API_KEY="your-api-key" \
  -e AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4" \
  ai-test-generator:latest
```

### 3. Docker Compose 설정

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
      - GIT_PYTHON_REFRESH=quiet
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      - AZURE_OPENAI_DEPLOYMENT_NAME=${AZURE_OPENAI_DEPLOYMENT_NAME}
      - AZURE_OPENAI_API_VERSION=2024-02-15-preview
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
      - LANGFUSE_HOST=${LANGFUSE_HOST}
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## ☸️ Kubernetes 배포

### 1. Kubernetes 매니페스트

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-test-generator
  labels:
    app: ai-test-generator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-test-generator
  template:
    metadata:
      labels:
        app: ai-test-generator
    spec:
      containers:
      - name: ai-test-generator
        image: ai-test-generator:latest
        ports:
        - containerPort: 8501
        env:
        - name: GIT_PYTHON_GIT_EXECUTABLE
          value: "/usr/bin/git"
        - name: GIT_PYTHON_REFRESH
          value: "quiet"
        - name: AZURE_OPENAI_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: ai-test-secrets
              key: azure-openai-endpoint
        - name: AZURE_OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: ai-test-secrets
              key: azure-openai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: ai-test-generator-service
spec:
  selector:
    app: ai-test-generator
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8501
  type: LoadBalancer
```

### 2. Secrets 설정

```bash
# Secrets 생성
kubectl create secret generic ai-test-secrets \
  --from-literal=azure-openai-endpoint=https://your-endpoint.openai.azure.com/ \
  --from-literal=azure-openai-api-key=your-api-key \
  --from-literal=azure-openai-deployment=gpt-4
```

### 3. 배포 및 확인

```bash
# 배포
kubectl apply -f k8s-deployment.yaml

# 상태 확인
kubectl get pods -l app=ai-test-generator
kubectl get service ai-test-generator-service

# 로그 확인
kubectl logs -f deployment/ai-test-generator
```

## 🖥️ 온프레미스 배포

### 1. 시스템 요구사항

- **OS**: Ubuntu 20.04+ / CentOS 8+ / Windows Server 2019+
- **Python**: 3.12+
- **메모리**: 최소 4GB, 권장 8GB
- **디스크**: 최소 20GB
- **CPU**: 최소 2 코어, 권장 4 코어

### 2. 설치 스크립트

```bash
#!/bin/bash
# install.sh

# 시스템 업데이트
sudo apt-get update && sudo apt-get upgrade -y

# 필수 패키지 설치
sudo apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    git \
    nginx \
    supervisor

# 애플리케이션 디렉토리 생성
sudo mkdir -p /opt/ai-test-generator
sudo chown $USER:$USER /opt/ai-test-generator

# 코드 클론
git clone https://github.com/your-org/ai-test-generator.git /opt/ai-test-generator
cd /opt/ai-test-generator

# 가상환경 생성 및 활성화
python3.12 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip
pip install -r requirements.txt

# 환경 변수 파일 생성
cat > .env << EOL
GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
GIT_PYTHON_REFRESH=quiet
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
EOL
```

### 3. Systemd 서비스 설정

```ini
# /etc/systemd/system/ai-test-generator.service
[Unit]
Description=AI Test Generator
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-test-generator
Environment="PATH=/opt/ai-test-generator/venv/bin:/usr/bin"
Environment="GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git"
Environment="GIT_PYTHON_REFRESH=quiet"
ExecStart=/opt/ai-test-generator/venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Nginx 리버스 프록시 설정

```nginx
# /etc/nginx/sites-available/ai-test-generator
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    
    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 5. 서비스 시작

```bash
# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable ai-test-generator
sudo systemctl start ai-test-generator

# Nginx 설정 활성화
sudo ln -s /etc/nginx/sites-available/ai-test-generator /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 상태 확인
sudo systemctl status ai-test-generator
sudo journalctl -u ai-test-generator -f
```

## 📊 모니터링 및 로깅

### 1. Application Insights 설정 (Azure)

```python
# config.py에 추가
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string="InstrumentationKey=your-key;IngestionEndpoint=https://your-region.in.applicationinsights.azure.com/"
)
```

### 2. 로그 수집 설정

```yaml
# filebeat.yml (ELK Stack 연동)
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /opt/ai-test-generator/logs/*.log
  fields:
    service: ai-test-generator
    environment: production

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "ai-test-generator-%{+yyyy.MM.dd}"
```

### 3. 헬스체크 엔드포인트

```python
# health_check.py
import streamlit as st
from datetime import datetime

@st.cache_data(ttl=60)
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {
            "azure_openai": check_azure_openai(),
            "git": check_git_availability(),
            "langfuse": check_langfuse_connection()
        }
    }
```

## 🔐 보안 고려사항

### 1. SSL/TLS 설정

```bash
# Let's Encrypt SSL 인증서 설치
sudo certbot --nginx -d your-domain.com
```

### 2. 방화벽 설정

```bash
# UFW 방화벽 설정
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable
```

### 3. 환경 변수 보안

```bash
# Azure Key Vault 사용
az keyvault secret set \
  --vault-name ai-test-kv \
  --name azure-openai-key \
  --value "your-api-key"

# 애플리케이션에서 사용
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://ai-test-kv.vault.azure.net/", credential=credential)
api_key = client.get_secret("azure-openai-key").value
```

## 🔧 트러블슈팅

### 일반적인 문제 해결

#### 1. Git 실행 파일을 찾을 수 없음
```bash
# 해결책
export GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git
export GIT_PYTHON_REFRESH=quiet
```

#### 2. 메모리 부족
```bash
# Azure Web App 스케일 업
az webapp plan update \
  --name asp-ai-test-generator \
  --resource-group rg-ai-test-generator \
  --sku P1V2
```

#### 3. 포트 충돌
```bash
# 다른 포트 사용
export STREAMLIT_SERVER_PORT=8502
streamlit run streamlit_app.py --server.port 8502
```

#### 4. 권한 문제
```bash
# 권한 수정
sudo chown -R www-data:www-data /opt/ai-test-generator
sudo chmod -R 755 /opt/ai-test-generator
```

## 📈 성능 최적화

### 1. 캐싱 설정

```python
# Streamlit 캐싱
@st.cache_data(ttl=3600)
def load_data():
    return expensive_operation()

@st.cache_resource
def init_connection():
    return create_connection()
```

### 2. 동시성 설정

```toml
# .streamlit/config.toml
[server]
maxUploadSize = 200
maxMessageSize = 200
enableCORS = false
enableXsrfProtection = true

[runner]
magicEnabled = true
installTracer = false
fixMatplotlib = true
```

### 3. 리소스 제한

```bash
# Docker 리소스 제한
docker run -d \
  --memory="2g" \
  --memory-swap="2g" \
  --cpus="2.0" \
  ai-test-generator:latest
```

## 🔄 CI/CD 파이프라인

### GitHub Actions 전체 워크플로우

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Azure
      uses: azure/webapps-deploy@v2
      with:
        app-name: 'ai-test-generator-app'
        publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

## 📚 참고 자료

- [Azure Web App Documentation](https://docs.microsoft.com/azure/app-service/)
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Streamlit Deployment Guide](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app)
- [Nginx Configuration](https://nginx.org/en/docs/)
