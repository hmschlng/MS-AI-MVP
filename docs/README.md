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
