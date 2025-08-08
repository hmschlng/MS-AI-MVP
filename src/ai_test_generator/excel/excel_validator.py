"""
Excel Validator Module - 엑셀 데이터 검증

테스트 시나리오 데이터의 유효성을 검증하고,
Streamlit에서 실시간 검증 피드백을 제공합니다.
"""
from typing import List, Dict, Any, Tuple, Optional
import re
import pandas as pd
from dataclasses import dataclass
from .excel_templates import ExcelTestScenario, TestPriority, TestType, TestStatus


@dataclass
class ValidationError:
    """검증 오류 정보"""
    row_index: int
    column: str
    error_type: str
    message: str
    severity: str  # 'error', 'warning', 'info'


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    total_scenarios: int
    valid_scenarios: int
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class ExcelValidator:
    """엑셀 데이터 검증 클래스"""
    
    # 필수 필드 정의
    REQUIRED_FIELDS = [
        "Scenario ID",
        "Feature", 
        "Description",
        "Test Steps",
        "Expected Results"
    ]
    
    # 시나리오 ID 패턴 (예: TC001, TEST_001, TS-001)
    SCENARIO_ID_PATTERN = re.compile(r'^[A-Z]{1,4}[-_]?\d{3,4}$')
    
    def __init__(self):
        self.valid_priorities = {e.value for e in TestPriority}
        self.valid_test_types = {e.value for e in TestType}
        self.valid_statuses = {e.value for e in TestStatus}
    
    def validate_scenarios(self, scenarios: List[ExcelTestScenario]) -> ValidationResult:
        """시나리오 리스트 전체 검증"""
        errors = []
        warnings = []
        
        # 중복 ID 체크
        scenario_ids = [s.scenario_id for s in scenarios if s.scenario_id.strip()]
        duplicate_ids = self._find_duplicates(scenario_ids)
        
        for i, scenario in enumerate(scenarios):
            # 개별 시나리오 검증
            scenario_errors, scenario_warnings = self._validate_single_scenario(scenario, i)
            errors.extend(scenario_errors)
            warnings.extend(scenario_warnings)
            
            # 중복 ID 오류 추가
            if scenario.scenario_id in duplicate_ids:
                errors.append(ValidationError(
                    row_index=i,
                    column="Scenario ID",
                    error_type="duplicate",
                    message=f"Duplicate scenario ID: {scenario.scenario_id}",
                    severity="error"
                ))
        
        # Count unique scenarios that have errors
        scenarios_with_errors = set(e.row_index for e in errors if e.severity == "error")
        valid_scenarios = len(scenarios) - len(scenarios_with_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            total_scenarios=len(scenarios),
            valid_scenarios=valid_scenarios
        )
    
    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResult:
        """DataFrame 검증 (Streamlit용)"""
        scenarios = []
        
        for _, row in df.iterrows():
            try:
                scenario = ExcelTestScenario.from_dict(row.to_dict())
                scenarios.append(scenario)
            except Exception as e:
                # DataFrame 파싱 오류는 별도 처리
                pass
        
        return self.validate_scenarios(scenarios)
    
    def _validate_single_scenario(self, scenario: ExcelTestScenario, row_index: int) -> Tuple[List[ValidationError], List[ValidationError]]:
        """단일 시나리오 검증"""
        errors = []
        warnings = []
        
        # 필수 필드 검증
        for field in self.REQUIRED_FIELDS:
            value = getattr(scenario, self._field_to_attribute(field), "")
            if not value or not value.strip():
                errors.append(ValidationError(
                    row_index=row_index,
                    column=field,
                    error_type="required",
                    message=f"{field} is required",
                    severity="error"
                ))
        
        # Scenario ID 형식 검증
        if scenario.scenario_id.strip():
            if not self.SCENARIO_ID_PATTERN.match(scenario.scenario_id.strip().upper()):
                warnings.append(ValidationError(
                    row_index=row_index,
                    column="Scenario ID",
                    error_type="format",
                    message="Scenario ID format should be like TC001, TEST_001, or TS-001",
                    severity="warning"
                ))
        
        # Priority 검증
        if scenario.priority and scenario.priority not in self.valid_priorities:
            errors.append(ValidationError(
                row_index=row_index,
                column="Priority",
                error_type="invalid_value",
                message=f"Invalid priority: {scenario.priority}. Must be one of {list(self.valid_priorities)}",
                severity="error"
            ))
        
        # Test Type 검증
        if scenario.test_type and scenario.test_type not in self.valid_test_types:
            errors.append(ValidationError(
                row_index=row_index,
                column="Test Type",
                error_type="invalid_value",
                message=f"Invalid test type: {scenario.test_type}. Must be one of {list(self.valid_test_types)}",
                severity="error"
            ))
        
        # Status 검증
        if scenario.status and scenario.status not in self.valid_statuses:
            errors.append(ValidationError(
                row_index=row_index,
                column="Status",
                error_type="invalid_value",
                message=f"Invalid status: {scenario.status}. Must be one of {list(self.valid_statuses)}",
                severity="error"
            ))
        
        # 시간 필드 검증
        if scenario.estimated_time and not self._is_valid_time(scenario.estimated_time):
            warnings.append(ValidationError(
                row_index=row_index,
                column="Estimated Time (min)",
                error_type="format",
                message="Time should be a number (minutes)",
                severity="warning"
            ))
        
        if scenario.actual_time and not self._is_valid_time(scenario.actual_time):
            warnings.append(ValidationError(
                row_index=row_index,
                column="Actual Time (min)",
                error_type="format",
                message="Time should be a number (minutes)",
                severity="warning"
            ))
        
        # 내용 길이 검증
        if len(scenario.description) > 500:
            warnings.append(ValidationError(
                row_index=row_index,
                column="Description",
                error_type="length",
                message="Description is very long (>500 characters)",
                severity="warning"
            ))
        
        # Test Steps 구조 검증
        if scenario.test_steps and not self._has_numbered_steps(scenario.test_steps):
            warnings.append(ValidationError(
                row_index=row_index,
                column="Test Steps",
                error_type="format",
                message="Test steps should be numbered (1., 2., 3., ...)",
                severity="warning"
            ))
        
        return errors, warnings
    
    def _field_to_attribute(self, field: str) -> str:
        """필드명을 속성명으로 변환"""
        field_mapping = {
            "Scenario ID": "scenario_id",
            "Feature": "feature",
            "Description": "description",
            "Preconditions": "preconditions",
            "Test Steps": "test_steps",
            "Expected Results": "expected_results",
            "Test Data": "test_data",
            "Priority": "priority",
            "Test Type": "test_type",
            "Status": "status",
            "Assigned To": "assigned_to",
            "Estimated Time (min)": "estimated_time",
            "Actual Time (min)": "actual_time",
            "Notes": "notes"
        }
        return field_mapping.get(field, field.lower().replace(" ", "_"))
    
    def _find_duplicates(self, items: List[str]) -> set:
        """중복 항목 찾기"""
        seen = set()
        duplicates = set()
        for item in items:
            if item in seen:
                duplicates.add(item)
            seen.add(item)
        return duplicates
    
    def _is_valid_time(self, time_str: str) -> bool:
        """시간 형식 검증"""
        if not time_str.strip():
            return True
        try:
            float(time_str.strip())
            return True
        except ValueError:
            return False
    
    def _has_numbered_steps(self, steps: str) -> bool:
        """번호가 매겨진 단계인지 확인"""
        if not steps.strip():
            return True
        
        lines = [line.strip() for line in steps.split('\n') if line.strip()]
        if len(lines) <= 1:
            return True
        
        # 첫 번째 줄이 1. 또는 1) 로 시작하는지 확인
        first_line = lines[0]
        return bool(re.match(r'^\d+[.)]', first_line))
    
    def get_validation_summary(self, result: ValidationResult) -> str:
        """검증 결과 요약 텍스트"""
        if result.is_valid:
            return f"✅ All {result.total_scenarios} test scenarios are valid!"
        
        summary = f"📊 Validation Results:\n"
        summary += f"- Total scenarios: {result.total_scenarios}\n"
        summary += f"- Valid scenarios: {result.valid_scenarios}\n"
        summary += f"- Errors: {result.error_count}\n"
        summary += f"- Warnings: {result.warning_count}\n"
        
        if result.errors:
            summary += f"\n❌ Critical Errors:\n"
            for error in result.errors[:5]:  # 최대 5개만 표시
                summary += f"- Row {error.row_index + 1}, {error.column}: {error.message}\n"
            
            if len(result.errors) > 5:
                summary += f"... and {len(result.errors) - 5} more errors\n"
        
        if result.warnings:
            summary += f"\n⚠️ Warnings:\n"
            for warning in result.warnings[:3]:  # 최대 3개만 표시
                summary += f"- Row {warning.row_index + 1}, {warning.column}: {warning.message}\n"
            
            if len(result.warnings) > 3:
                summary += f"... and {len(result.warnings) - 3} more warnings\n"
        
        return summary
    
    def get_streamlit_validation_config(self) -> Dict[str, Any]:
        """Streamlit ag-grid 검증 설정"""
        return {
            "suppressRowClickSelection": True,
            "rowSelection": "multiple",
            "enableRangeSelection": True,
            "pagination": True,
            "paginationPageSize": 20,
            "gridOptions": {
                "domLayout": "autoHeight",
                "suppressColumnVirtualisation": True
            },
            "custom_css": {
                ".ag-row-level-0.validation-error": {
                    "background-color": "#ffebee !important"
                },
                ".ag-row-level-0.validation-warning": {
                    "background-color": "#fff3e0 !important"
                }
            }
        }
