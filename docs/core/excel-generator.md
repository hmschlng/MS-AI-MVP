# Excel Generator 모듈 문서

> 테스트 시나리오 문서화 및 엑셀 출력 시스템

## 📌 개요

Excel Generator 모듈은 **AI가 생성한 테스트 시나리오를 구조화된 엑셀 문서로 변환**하는 시스템입니다. 테스트 팀이 쉽게 이해하고 활용할 수 있는 표준화된 문서를 자동으로 생성하며, Streamlit UI에서 직접 편집 가능한 형태로 제공됩니다.

## 🎯 주요 기능

### 1. 자동 문서 생성
- AI 생성 시나리오를 엑셀 형식으로 변환
- 다중 시트 구성 (요약, 시나리오, 템플릿, 검증)
- 표준 테스트 문서 템플릿 적용

### 2. 데이터 검증
- 입력 데이터 유효성 검사
- 필수 필드 확인
- 데이터 타입 및 형식 검증

### 3. 스타일링 및 포매팅
- 전문적인 문서 스타일 자동 적용
- 조건부 서식 및 색상 코딩
- 데이터 유효성 검사 규칙

## 🏗️ 아키텍처

```
ExcelGenerator
├── Core Components
│   ├── ExcelGenerator (메인 생성기)
│   ├── ExcelTemplates (템플릿 관리)
│   └── ExcelValidator (검증 로직)
├── Data Models
│   ├── ExcelTestScenario
│   ├── TestPriority
│   ├── TestType
│   └── TestStatus
└── Styling
    ├── ExcelStyles
    ├── CellFormatting
    └── DataValidation
```

## 📊 엑셀 문서 구조

### 1. Summary Sheet (요약)
**목적**: 프로젝트 개요 및 테스트 통계 제공

| 섹션 | 내용 |
|------|------|
| 프로젝트 정보 | 프로젝트명, 버전, 생성일 |
| 통계 | 총 시나리오 수, 우선순위별 분포 |
| 커버리지 | 기능별 테스트 커버리지 |
| 진행 상태 | 작성/검토/승인 상태 |

### 2. Test Scenarios Sheet (테스트 시나리오)
**목적**: 상세 테스트 시나리오 목록

| 컬럼 | 설명 | 데이터 타입 |
|------|------|------------|
| Scenario ID | 고유 식별자 | TC001, TC002... |
| Feature | 테스트 대상 기능 | Text |
| Description | 시나리오 설명 | Text |
| Priority | 우선순위 | High/Medium/Low |
| Type | 테스트 유형 | Functional/Performance/Security |
| Preconditions | 전제조건 | JSON Array |
| Test Steps | 테스트 단계 | JSON Array |
| Expected Results | 예상 결과 | JSON Array |
| Status | 실행 상태 | Not Started/In Progress/Passed/Failed |

### 3. Template Sheet (템플릿)
**목적**: 새 시나리오 추가를 위한 빈 템플릿

- 데이터 유효성 검사 규칙 포함
- 드롭다운 목록 제공
- 입력 가이드 및 예시

### 4. Validation Sheet (검증 결과)
**목적**: 데이터 품질 검증 결과

- 검증 규칙 목록
- 검증 결과 (Pass/Fail)
- 오류 상세 및 권장사항

## 💻 주요 클래스 및 데이터 모델

### ExcelTestScenario (Dataclass)
```python
@dataclass
class ExcelTestScenario:
    scenario_id: str           # 시나리오 ID
    feature: str              # 기능명
    description: str          # 설명
    priority: TestPriority    # 우선순위
    test_type: TestType       # 테스트 유형
    preconditions: str        # 전제조건 (JSON)
    test_steps: str          # 테스트 단계 (JSON)
    expected_results: str    # 예상 결과 (JSON)
    test_data: Optional[str] # 테스트 데이터
    status: TestStatus       # 상태
    assigned_to: str         # 담당자
    created_date: datetime   # 생성일
    
    @classmethod
    def from_test_scenario(cls, scenario: TestScenario):
        """LLM TestScenario를 Excel 형식으로 변환"""
```

### TestPriority (Enum)
```python
class TestPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    CRITICAL = "Critical"
```

### TestType (Enum)
```python
class TestType(str, Enum):
    FUNCTIONAL = "Functional"
    PERFORMANCE = "Performance"
    SECURITY = "Security"
    USABILITY = "Usability"
    COMPATIBILITY = "Compatibility"
    REGRESSION = "Regression"
```

### TestStatus (Enum)
```python
class TestStatus(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    PASSED = "Passed"
    FAILED = "Failed"
    BLOCKED = "Blocked"
    SKIPPED = "Skipped"
```

## 🎨 스타일링 시스템

### ExcelStyles 클래스
```python
class ExcelStyles:
    def __init__(self):
        # 헤더 스타일
        self.header_font = Font(bold=True, size=12, color="FFFFFF")
        self.header_fill = PatternFill("solid", fgColor="366092")
        self.header_alignment = Alignment(horizontal="center")
        
        # 우선순위별 색상
        self.priority_colors = {
            "Critical": "FF0000",  # 빨강
            "High": "FFA500",      # 주황
            "Medium": "FFFF00",    # 노랑
            "Low": "90EE90"        # 연두
        }
        
        # 상태별 색상
        self.status_colors = {
            "Passed": "90EE90",    # 녹색
            "Failed": "FF6B6B",    # 빨강
            "In Progress": "87CEEB", # 하늘색
            "Not Started": "D3D3D3"  # 회색
        }
```

### 조건부 서식
```python
def apply_conditional_formatting(ws: Worksheet):
    """우선순위와 상태에 따른 조건부 서식 적용"""
    
    # 우선순위 색상 코딩
    for row in ws.iter_rows(min_row=2):
        priority_cell = row[3]  # Priority 컬럼
        if priority_cell.value == "Critical":
            priority_cell.fill = PatternFill("solid", fgColor="FF0000")
        elif priority_cell.value == "High":
            priority_cell.fill = PatternFill("solid", fgColor="FFA500")
```

## 🔧 핵심 메서드

### ExcelGenerator 클래스

#### `generate_from_llm_scenarios()`
```python
def generate_from_llm_scenarios(
    self, 
    scenarios: List[TestScenario], 
    project_info: Optional[Dict[str, str]] = None
) -> Workbook:
    """LLM 생성 시나리오를 엑셀로 변환"""
```

#### `generate_workbook()`
```python
def generate_workbook(
    self, 
    scenarios: List[ExcelTestScenario], 
    project_info: Optional[Dict[str, str]] = None
) -> Workbook:
    """멀티 시트 엑셀 워크북 생성"""
```

#### `export_to_file()`
```python
def export_to_file(
    self, 
    workbook: Workbook, 
    file_path: Union[str, Path]
) -> Path:
    """엑셀 파일로 저장"""
```

### ExcelValidator 클래스

#### `validate_scenario()`
```python
def validate_scenario(self, scenario: ExcelTestScenario) -> ValidationResult:
    """개별 시나리오 검증"""
    
    checks = [
        self._check_required_fields(scenario),
        self._check_data_types(scenario),
        self._check_json_format(scenario),
        self._check_business_rules(scenario)
    ]
```

#### `validate_workbook()`
```python
def validate_workbook(self, workbook: Workbook) -> List[ValidationResult]:
    """전체 워크북 검증"""
```

## 📈 Streamlit 통합

### DataFrame 변환
```python
def excel_to_dataframe(workbook: Workbook) -> pd.DataFrame:
    """엑셀 워크북을 Pandas DataFrame으로 변환"""
    
    ws = workbook["Test Scenarios"]
    data = []
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        data.append(row)
    
    df = pd.DataFrame(data, columns=headers)
    return df
```

### 인터랙티브 편집
```python
# Streamlit에서 편집 가능한 테이블 표시
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    column_config={
        "Priority": st.column_config.SelectboxColumn(
            options=["Critical", "High", "Medium", "Low"]
        ),
        "Status": st.column_config.SelectboxColumn(
            options=["Not Started", "In Progress", "Passed", "Failed"]
        )
    }
)
```

### 다운로드 기능
```python
def create_download_link(workbook: Workbook) -> bytes:
    """다운로드 가능한 바이트 스트림 생성"""
    
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    
    return output.getvalue()

# Streamlit 다운로드 버튼
st.download_button(
    label="📥 엑셀 다운로드",
    data=create_download_link(workbook),
    file_name=f"test_scenarios_{datetime.now():%Y%m%d}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
```

## 🔐 데이터 보안 및 프라이버시

### 민감 정보 처리
- 개인정보 자동 마스킹
- 보안 관련 데이터 암호화
- 접근 권한 관리

### 감사 추적
```python
@dataclass
class AuditLog:
    timestamp: datetime
    user: str
    action: str
    changes: Dict[str, Any]
```

## 📊 통계 및 리포팅

### 대시보드 메트릭
```python
def calculate_metrics(scenarios: List[ExcelTestScenario]) -> Dict:
    return {
        "total_scenarios": len(scenarios),
        "priority_distribution": count_by_priority(scenarios),
        "type_distribution": count_by_type(scenarios),
        "status_summary": count_by_status(scenarios),
        "coverage_percentage": calculate_coverage(scenarios)
    }
```

### 시각화
```python
import plotly.express as px

# 우선순위 분포 차트
fig = px.pie(
    values=priority_counts.values(),
    names=priority_counts.keys(),
    title="테스트 우선순위 분포"
)
```

## 🛠️ 커스터마이징

### 템플릿 커스터마이징
```python
class CustomTemplate(ExcelTemplate):
    def __init__(self):
        super().__init__()
        self.add_custom_fields({
            "environment": "테스트 환경",
            "automation_status": "자동화 상태",
            "execution_time": "예상 실행 시간"
        })
```

### 검증 규칙 추가
```python
def add_custom_validation(validator: ExcelValidator):
    validator.add_rule(
        name="scenario_id_format",
        check=lambda s: re.match(r"TC\d{3}", s.scenario_id),
        message="Scenario ID must be in format TCxxx"
    )
```

## 🔍 트러블슈팅

### 일반적인 문제

#### 1. 대용량 파일 처리
- **문제**: 1000개 이상 시나리오 시 성능 저하
- **해결**: 청크 단위 처리 및 스트리밍

#### 2. 인코딩 문제
- **문제**: 특수 문자 깨짐
- **해결**: UTF-8 인코딩 강제 적용

#### 3. 메모리 사용량
- **문제**: 대용량 워크북 생성 시 메모리 부족
- **해결**: openpyxl write_only 모드 사용

## 📈 성능 최적화

### 최적화 기법
- 지연 로딩 (Lazy Loading)
- 캐싱 전략
- 배치 처리
- 비동기 생성

### 벤치마크
| 시나리오 수 | 생성 시간 | 메모리 사용량 |
|------------|----------|--------------|
| 100 | 2초 | 50MB |
| 500 | 8초 | 150MB |
| 1000 | 15초 | 300MB |

## 🚀 향후 개선 계획

### 단기 목표
- [ ] 다국어 지원
- [ ] 추가 파일 형식 지원 (CSV, JSON)
- [ ] 실시간 협업 기능

### 장기 목표
- [ ] 클라우드 저장소 통합
- [ ] 버전 관리 시스템
- [ ] AI 기반 문서 품질 개선

## 📚 참고 자료

- [OpenPyXL Documentation](https://openpyxl.readthedocs.io/)
- [Pandas Excel Integration](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- [Excel File Format Specification](https://docs.microsoft.com/en-us/openspecs/office_standards/ms-xlsx/)