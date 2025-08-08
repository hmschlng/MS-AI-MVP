"""
Test module for excel_templates.py

Tests for Excel template data models and enums
"""
import pytest
import pandas as pd
from ai_test_generator.excel.excel_templates import (
    ExcelTestScenario,
    ExcelStyles,
    ExcelTemplate,
    TestPriority,
    TestType,
    TestStatus
)
from ai_test_generator.core.llm_agent import TestScenario


class TestEnums:
    """Test enum classes"""
    
    def test_test_priority_values(self):
        """Test TestPriority enum values"""
        assert TestPriority.HIGH.value == "High"
        assert TestPriority.MEDIUM.value == "Medium"
        assert TestPriority.LOW.value == "Low"
    
    def test_test_type_values(self):
        """Test TestType enum values"""
        assert TestType.FUNCTIONAL.value == "Functional"
        assert TestType.INTEGRATION.value == "Integration"
        assert TestType.PERFORMANCE.value == "Performance"
        assert TestType.SECURITY.value == "Security"
        assert TestType.REGRESSION.value == "Regression"
    
    def test_test_status_values(self):
        """Test TestStatus enum values"""
        assert TestStatus.NOT_EXECUTED.value == "Not Executed"
        assert TestStatus.PASS.value == "Pass"
        assert TestStatus.FAIL.value == "Fail"
        assert TestStatus.BLOCKED.value == "Blocked"
        assert TestStatus.SKIP.value == "Skip"


class TestExcelTestScenario:
    """Test ExcelTestScenario data class"""
    
    @pytest.fixture
    def sample_scenario(self):
        """Sample test scenario fixture"""
        return ExcelTestScenario(
            scenario_id="TC001",
            feature="User Login",
            description="Test user authentication",
            preconditions="User has valid credentials\nApplication is running",
            test_steps="1. Navigate to login page\n2. Enter credentials\n3. Click login",
            expected_results="User is logged in\nRedirected to dashboard",
            test_data="username: test@example.com",
            priority=TestPriority.HIGH.value,
            test_type=TestType.FUNCTIONAL.value,
            status=TestStatus.NOT_EXECUTED.value,
            assigned_to="Test Engineer",
            estimated_time="10",
            actual_time="8",
            notes="Test case created by AI"
        )
    
    def test_excel_test_scenario_creation(self, sample_scenario):
        """Test ExcelTestScenario object creation"""
        assert sample_scenario.scenario_id == "TC001"
        assert sample_scenario.feature == "User Login"
        assert sample_scenario.priority == TestPriority.HIGH.value
        assert sample_scenario.test_type == TestType.FUNCTIONAL.value
        assert sample_scenario.status == TestStatus.NOT_EXECUTED.value
    
    def test_to_dict_conversion(self, sample_scenario):
        """Test to_dict method"""
        result = sample_scenario.to_dict()
        
        # Check all required keys exist
        expected_keys = [
            "Scenario ID", "Feature", "Description", "Preconditions",
            "Test Steps", "Expected Results", "Test Data", "Priority",
            "Test Type", "Status", "Assigned To", "Estimated Time (min)",
            "Actual Time (min)", "Notes"
        ]
        
        for key in expected_keys:
            assert key in result
        
        # Check specific values
        assert result["Scenario ID"] == "TC001"
        assert result["Feature"] == "User Login"
        assert result["Priority"] == TestPriority.HIGH.value
    
    def test_from_dict_conversion(self):
        """Test from_dict class method"""
        data = {
            "Scenario ID": "TC002",
            "Feature": "User Logout",
            "Description": "Test user logout",
            "Preconditions": "User is logged in",
            "Test Steps": "1. Click logout button",
            "Expected Results": "User is logged out",
            "Test Data": "",
            "Priority": TestPriority.MEDIUM.value,
            "Test Type": TestType.FUNCTIONAL.value,
            "Status": TestStatus.NOT_EXECUTED.value,
            "Assigned To": "",
            "Estimated Time (min)": "5",
            "Actual Time (min)": "",
            "Notes": ""
        }
        
        scenario = ExcelTestScenario.from_dict(data)
        
        assert scenario.scenario_id == "TC002"
        assert scenario.feature == "User Logout"
        assert scenario.priority == TestPriority.MEDIUM.value
    
    def test_from_test_scenario_conversion(self):
        """Test from_test_scenario class method"""
        # Create a mock TestScenario object
        test_scenario = TestScenario(
            scenario_id="TS001",
            feature="Data Validation",
            description="Validate input data",
            preconditions=["Valid data exists", "System is ready"],
            test_steps=[
                {"action": "Enter data", "data": "test input"},
                {"action": "Click validate", "data": ""}
            ],
            expected_results=["Data is validated", "Success message shown"],
            test_data={"input": "test data"},
            priority="High",
            test_type="Functional"
        )
        
        excel_scenario = ExcelTestScenario.from_test_scenario(test_scenario)
        
        assert excel_scenario.scenario_id == "TS001"
        assert excel_scenario.feature == "Data Validation"
        assert excel_scenario.preconditions == "Valid data exists\nSystem is ready"
        assert "1. Enter data: test input" in excel_scenario.test_steps
        assert "2. Click validate:" in excel_scenario.test_steps
        assert excel_scenario.expected_results == "Data is validated\nSuccess message shown"
        assert excel_scenario.priority == "High"
    
    def test_from_test_scenario_with_custom_id(self):
        """Test from_test_scenario with custom scenario ID"""
        test_scenario = TestScenario(
            scenario_id="OLD001",
            feature="Test Feature",
            description="Test description",
            preconditions=[],
            test_steps=[],
            expected_results=[],
            priority="Medium"
        )
        
        excel_scenario = ExcelTestScenario.from_test_scenario(test_scenario, "NEW001")
        
        assert excel_scenario.scenario_id == "NEW001"
        assert excel_scenario.feature == "Test Feature"


class TestExcelStyles:
    """Test ExcelStyles class"""
    
    def test_excel_styles_creation(self):
        """Test ExcelStyles object creation"""
        styles = ExcelStyles()
        
        # Test fonts exist
        assert styles.header_font is not None
        assert styles.content_font is not None
        
        # Test fills exist
        assert styles.header_fill is not None
        assert styles.priority_high_fill is not None
        assert styles.priority_medium_fill is not None
        assert styles.priority_low_fill is not None
        
        # Test border exists
        assert styles.thin_border is not None
        
        # Test alignments exist
        assert styles.center_alignment is not None
        assert styles.wrap_alignment is not None
    
    def test_header_font_properties(self):
        """Test header font properties"""
        styles = ExcelStyles()
        
        assert styles.header_font.name == 'Arial'
        assert styles.header_font.size == 12
        assert styles.header_font.bold is True
        assert styles.header_font.color.rgb == '00FFFFFF'  # Color object has rgb property
    
    def test_content_font_properties(self):
        """Test content font properties"""
        styles = ExcelStyles()
        
        assert styles.content_font.name == 'Arial'
        assert styles.content_font.size == 10


class TestExcelTemplate:
    """Test ExcelTemplate class"""
    
    def test_get_column_definitions(self):
        """Test column definitions"""
        columns = ExcelTemplate.get_column_definitions()
        
        # Check it's a list
        assert isinstance(columns, list)
        assert len(columns) > 0
        
        # Check first column (Scenario ID)
        first_col = columns[0]
        assert first_col["headerName"] == "Scenario ID"
        assert first_col["field"] == "Scenario ID"
        assert first_col["pinned"] == "left"
        assert first_col["editable"] is True
        
        # Check that all expected columns exist
        expected_fields = [
            "Scenario ID", "Feature", "Description", "Preconditions",
            "Test Steps", "Expected Results", "Test Data", "Priority",
            "Test Type", "Status", "Assigned To", "Estimated Time (min)",
            "Actual Time (min)", "Notes"
        ]
        
        actual_fields = [col["field"] for col in columns]
        for field in expected_fields:
            assert field in actual_fields
    
    def test_priority_column_configuration(self):
        """Test Priority column has select editor"""
        columns = ExcelTemplate.get_column_definitions()
        
        priority_col = next(col for col in columns if col["field"] == "Priority")
        
        assert priority_col["cellEditor"] == "agSelectCellEditor"
        assert "cellEditorParams" in priority_col
        assert "values" in priority_col["cellEditorParams"]
        
        # Check that all priority values are included
        values = priority_col["cellEditorParams"]["values"]
        assert TestPriority.HIGH.value in values
        assert TestPriority.MEDIUM.value in values
        assert TestPriority.LOW.value in values
    
    def test_create_empty_dataframe(self):
        """Test empty dataframe creation"""
        df = ExcelTemplate.create_empty_dataframe()
        
        # Check it's a DataFrame
        assert isinstance(df, pd.DataFrame)
        
        # Check it has exactly one row (sample data)
        assert len(df) == 1
        
        # Check all required columns exist
        expected_columns = [
            "Scenario ID", "Feature", "Description", "Preconditions",
            "Test Steps", "Expected Results", "Test Data", "Priority",
            "Test Type", "Status", "Assigned To", "Estimated Time (min)",
            "Actual Time (min)", "Notes"
        ]
        
        for col in expected_columns:
            assert col in df.columns
        
        # Check sample data
        assert df.iloc[0]["Scenario ID"] == "TC001"
        assert df.iloc[0]["Feature"] == "User Authentication"
        assert df.iloc[0]["Priority"] == TestPriority.HIGH.value
    
    def test_get_summary_template(self):
        """Test summary template"""
        template = ExcelTemplate.get_summary_template()
        
        assert isinstance(template, dict)
        assert "title" in template
        assert "sections" in template
        
        assert template["title"] == "Test Execution Summary"
        
        # Check sections exist
        sections = template["sections"]
        section_names = [section["name"] for section in sections]
        
        assert "Project Information" in section_names
        assert "Test Statistics" in section_names
        assert "Priority Breakdown" in section_names
        
        # Check Project Information section
        project_info = next(s for s in sections if s["name"] == "Project Information")
        assert "fields" in project_info
        
        field_names = [field[0] for field in project_info["fields"]]
        assert "Project Name" in field_names
        assert "Version" in field_names
        assert "Test Environment" in field_names


class TestIntegration:
    """Integration tests"""
    
    def test_scenario_roundtrip_conversion(self):
        """Test scenario -> dict -> scenario conversion"""
        original = ExcelTestScenario(
            scenario_id="TC999",
            feature="Integration Test",
            description="Test roundtrip conversion",
            preconditions="Setup complete",
            test_steps="1. Test conversion",
            expected_results="Successful conversion",
            priority=TestPriority.LOW.value
        )
        
        # Convert to dict and back
        data_dict = original.to_dict()
        converted = ExcelTestScenario.from_dict(data_dict)
        
        # Check all fields match
        assert original.scenario_id == converted.scenario_id
        assert original.feature == converted.feature
        assert original.description == converted.description
        assert original.preconditions == converted.preconditions
        assert original.test_steps == converted.test_steps
        assert original.expected_results == converted.expected_results
        assert original.priority == converted.priority
    
    def test_template_dataframe_integration(self):
        """Test template and dataframe integration"""
        # Create empty dataframe
        df = ExcelTemplate.create_empty_dataframe()
        
        # Convert to scenarios
        scenarios = []
        for _, row in df.iterrows():
            scenario = ExcelTestScenario.from_dict(row.to_dict())
            scenarios.append(scenario)
        
        assert len(scenarios) == 1
        assert scenarios[0].scenario_id == "TC001"
        
        # Convert back to dataframe-like structure
        data = [scenario.to_dict() for scenario in scenarios]
        new_df = pd.DataFrame(data)
        
        # Check structure is preserved
        assert len(new_df.columns) == len(df.columns)
        for col in df.columns:
            assert col in new_df.columns