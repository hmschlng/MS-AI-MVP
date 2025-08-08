"""
Output Module - 엑셀 문서 생성 모듈

테스트 시나리오를 엑셀 문서로 출력하고,
Streamlit에서 편집 가능한 형태로 제공합니다.
"""

from .excel_generator import ExcelGenerator
from .excel_templates import (
    ExcelTestScenario, 
    ExcelStyles, 
    ExcelTemplate,
    TestPriority,
    TestType, 
    TestStatus
)
from .excel_validator import (
    ExcelValidator, 
    ValidationResult, 
    ValidationError
)

__all__ = [
    'ExcelGenerator',
    'ExcelTestScenario',
    'ExcelStyles',
    'ExcelTemplate', 
    'ExcelValidator',
    'ValidationResult',
    'ValidationError',
    'TestPriority',
    'TestType',
    'TestStatus'
]

# 버전 정보
__version__ = "1.0.0"

# 기본 설정
DEFAULT_EXCEL_CONFIG = {
    "file_extension": ".xlsx",
    "default_sheet_name": "Test Scenarios",
    "max_scenarios_per_sheet": 1000,
    "auto_save_interval": 300,  # 5분
    "backup_enabled": True
}

# 지원되는 엑셀 포맷
SUPPORTED_FORMATS = {
    "xlsx": "Excel 2007+ Workbook",
    "xls": "Excel 97-2003 Workbook", 
    "csv": "Comma Separated Values",
    "ods": "OpenDocument Spreadsheet"
}

def get_excel_generator() -> ExcelGenerator:
    """기본 설정으로 ExcelGenerator 인스턴스 반환"""
    return ExcelGenerator()

def get_validator() -> ExcelValidator:
    """기본 설정으로 ExcelValidator 인스턴스 반환"""
    return ExcelValidator()

def create_sample_scenarios(count: int = 3) -> list:
    """샘플 테스트 시나리오 생성 (데모/테스트용)"""
    from .excel_templates import ExcelTestScenario, TestPriority, TestType
    
    samples = []
    for i in range(count):
        scenario = ExcelTestScenario(
            scenario_id=f"TC{i+1:03d}",
            feature=f"Sample Feature {i+1}",
            description=f"This is a sample test scenario {i+1} for demonstration purposes.",
            preconditions=f"1. System is running\n2. User has access\n3. Test data is prepared",
            test_steps=f"1. Open the application\n2. Navigate to feature {i+1}\n3. Execute test action\n4. Verify results",
            expected_results=f"1. Feature {i+1} works correctly\n2. No errors are displayed\n3. Expected output is shown",
            test_data=f"sample_data_{i+1}.json",
            priority=TestPriority.MEDIUM.value,
            test_type=TestType.FUNCTIONAL.value
        )
        samples.append(scenario)
    
    return samples
