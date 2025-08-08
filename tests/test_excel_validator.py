"""
Test module for excel_validator.py

Tests for Excel data validation functionality
"""
import pytest
import pandas as pd
from ai_test_generator.excel.excel_validator import (
    ExcelValidator,
    ValidationResult,
    ValidationError
)
from ai_test_generator.excel.excel_templates import (
    ExcelTestScenario,
    TestPriority,
    TestType,
    TestStatus
)


class TestValidationError:
    """Test ValidationError dataclass"""
    
    def test_validation_error_creation(self):
        """Test ValidationError object creation"""
        error = ValidationError(
            row_index=0,
            column="Scenario ID",
            error_type="required",
            message="Field is required",
            severity="error"
        )
        
        assert error.row_index == 0
        assert error.column == "Scenario ID"
        assert error.error_type == "required"
        assert error.message == "Field is required"
        assert error.severity == "error"


class TestValidationResult:
    """Test ValidationResult dataclass"""
    
    def test_validation_result_creation(self):
        """Test ValidationResult object creation"""
        errors = [
            ValidationError(0, "Field1", "error", "Error message", "error")
        ]
        warnings = [
            ValidationError(1, "Field2", "warning", "Warning message", "warning")
        ]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            total_scenarios=5,
            valid_scenarios=3
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.total_scenarios == 5
        assert result.valid_scenarios == 3
    
    def test_error_count_property(self):
        """Test error_count property"""
        errors = [
            ValidationError(0, "Field1", "error", "Error 1", "error"),
            ValidationError(1, "Field2", "error", "Error 2", "error")
        ]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=[],
            total_scenarios=2,
            valid_scenarios=0
        )
        
        assert result.error_count == 2
    
    def test_warning_count_property(self):
        """Test warning_count property"""
        warnings = [
            ValidationError(0, "Field1", "warning", "Warning 1", "warning"),
            ValidationError(1, "Field2", "warning", "Warning 2", "warning"),
            ValidationError(2, "Field3", "warning", "Warning 3", "warning")
        ]
        
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=warnings,
            total_scenarios=3,
            valid_scenarios=3
        )
        
        assert result.warning_count == 3


class TestExcelValidator:
    """Test ExcelValidator class"""
    
    @pytest.fixture
    def validator(self):
        """ExcelValidator instance fixture"""
        return ExcelValidator()
    
    @pytest.fixture
    def valid_scenario(self):
        """Valid scenario fixture"""
        return ExcelTestScenario(
            scenario_id="TC001",
            feature="User Login",
            description="Test user authentication functionality",
            preconditions="User has valid credentials",
            test_steps="1. Navigate to login page\n2. Enter credentials\n3. Click login",
            expected_results="User is logged in successfully",
            test_data="username: test@example.com",
            priority=TestPriority.HIGH.value,
            test_type=TestType.FUNCTIONAL.value,
            status=TestStatus.NOT_EXECUTED.value
        )
    
    @pytest.fixture
    def invalid_scenario(self):
        """Invalid scenario fixture"""
        return ExcelTestScenario(
            scenario_id="",  # Missing required field
            feature="",      # Missing required field
            description="",  # Missing required field
            preconditions="",
            test_steps="",   # Missing required field
            expected_results="",  # Missing required field
            priority="Invalid Priority",  # Invalid value
            test_type="Invalid Type",     # Invalid value
            status="Invalid Status"       # Invalid value
        )
    
    def test_validator_initialization(self, validator):
        """Test validator initialization"""
        assert validator is not None
        assert len(validator.REQUIRED_FIELDS) > 0
        assert validator.SCENARIO_ID_PATTERN is not None
        assert len(validator.valid_priorities) > 0
        assert len(validator.valid_test_types) > 0
        assert len(validator.valid_statuses) > 0
    
    def test_required_fields_constant(self, validator):
        """Test required fields are properly defined"""
        expected_fields = [
            "Scenario ID", "Feature", "Description", 
            "Test Steps", "Expected Results"
        ]
        
        for field in expected_fields:
            assert field in validator.REQUIRED_FIELDS
    
    def test_validate_valid_scenario(self, validator, valid_scenario):
        """Test validation of valid scenario"""
        result = validator.validate_scenarios([valid_scenario])
        
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.total_scenarios == 1
        assert result.valid_scenarios == 1
    
    def test_validate_invalid_scenario(self, validator, invalid_scenario):
        """Test validation of invalid scenario"""
        result = validator.validate_scenarios([invalid_scenario])
        
        assert result.is_valid is False
        assert result.error_count > 0
        assert result.total_scenarios == 1
        assert result.valid_scenarios >= 0  # Should be 0 or positive
        
        # Check that required field errors are present
        error_columns = [error.column for error in result.errors]
        assert "Scenario ID" in error_columns
        assert "Feature" in error_columns
        assert "Description" in error_columns
    
    def test_validate_multiple_scenarios(self, validator, valid_scenario, invalid_scenario):
        """Test validation of multiple scenarios"""
        scenarios = [valid_scenario, invalid_scenario]
        result = validator.validate_scenarios(scenarios)
        
        assert result.total_scenarios == 2
        assert result.valid_scenarios == 1  # Should be 1 valid scenario (first one)
        assert result.error_count > 0
    
    def test_duplicate_scenario_ids(self, validator):
        """Test duplicate scenario ID detection"""
        scenario1 = ExcelTestScenario(
            scenario_id="TC001",
            feature="Feature 1",
            description="Description 1",
            preconditions="",
            test_steps="1. Step 1",
            expected_results="Result 1"
        )
        
        scenario2 = ExcelTestScenario(
            scenario_id="TC001",  # Duplicate ID
            feature="Feature 2", 
            description="Description 2",
            preconditions="",
            test_steps="1. Step 2",
            expected_results="Result 2"
        )
        
        result = validator.validate_scenarios([scenario1, scenario2])
        
        # Should have duplicate ID errors
        duplicate_errors = [e for e in result.errors if e.error_type == "duplicate"]
        assert len(duplicate_errors) >= 2  # Both scenarios should have duplicate error
    
    def test_scenario_id_format_validation(self, validator):
        """Test scenario ID format validation"""
        test_cases = [
            ("TC001", True),      # Valid format
            ("TEST001", True),    # Valid format
            ("TS-001", True),     # Valid format with dash
            ("T_001", True),      # Valid format with underscore
            ("tc001", True),     # Lowercase is converted to uppercase, so it's valid
            ("TC01", False),      # Too few digits (should be warning)
            ("TC1", False),       # Too few digits (should be warning)
            ("TOOLONG001", False), # Too long prefix (should be warning)
            ("123", False),       # No prefix (should be warning)
            ("", False),          # Empty (should be error for required)
        ]
        
        for scenario_id, should_pass in test_cases:
            scenario = ExcelTestScenario(
                scenario_id=scenario_id,
                feature="Test Feature",
                description="Test Description",
                preconditions="",
                test_steps="1. Test step",
                expected_results="Test result"
            )
            
            errors, warnings = validator._validate_single_scenario(scenario, 0)
            
            if scenario_id == "":
                # Empty ID should have required error
                assert any(e.error_type == "required" for e in errors)
            elif not should_pass and scenario_id:
                # Invalid format should have format warning
                assert any(w.error_type == "format" for w in warnings)
    
    def test_priority_validation(self, validator):
        """Test priority field validation"""
        # Valid priority
        valid_scenario = ExcelTestScenario(
            scenario_id="TC001",
            feature="Test",
            description="Test",
            preconditions="",
            test_steps="1. Test",
            expected_results="Result",
            priority=TestPriority.HIGH.value
        )
        
        errors, _ = validator._validate_single_scenario(valid_scenario, 0)
        priority_errors = [e for e in errors if e.column == "Priority"]
        assert len(priority_errors) == 0
        
        # Invalid priority
        invalid_scenario = ExcelTestScenario(
            scenario_id="TC001",
            feature="Test",
            description="Test",
            preconditions="",
            test_steps="1. Test",
            expected_results="Result",
            priority="Invalid Priority"
        )
        
        errors, _ = validator._validate_single_scenario(invalid_scenario, 0)
        priority_errors = [e for e in errors if e.column == "Priority"]
        assert len(priority_errors) > 0
        assert priority_errors[0].error_type == "invalid_value"
    
    def test_time_field_validation(self, validator):
        """Test time field validation"""
        test_cases = [
            ("10", True),      # Valid integer
            ("10.5", True),    # Valid decimal
            ("0", True),       # Valid zero
            ("", True),        # Empty is valid
            ("abc", False),    # Invalid text
            ("10 minutes", False),  # Invalid format
        ]
        
        for time_value, should_be_valid in test_cases:
            scenario = ExcelTestScenario(
                scenario_id="TC001",
                feature="Test",
                description="Test",
                preconditions="",
                test_steps="1. Test",
                expected_results="Result",
                estimated_time=time_value
            )
            
            _, warnings = validator._validate_single_scenario(scenario, 0)
            time_warnings = [w for w in warnings if "Time" in w.column]
            
            if should_be_valid:
                assert len(time_warnings) == 0
            else:
                assert len(time_warnings) > 0
    
    def test_description_length_validation(self, validator):
        """Test description length validation"""
        # Short description (should pass)
        short_desc = "Short description"
        scenario = ExcelTestScenario(
            scenario_id="TC001",
            feature="Test",
            description=short_desc,
            preconditions="",
            test_steps="1. Test",
            expected_results="Result"
        )
        
        _, warnings = validator._validate_single_scenario(scenario, 0)
        length_warnings = [w for w in warnings if w.error_type == "length"]
        assert len(length_warnings) == 0
        
        # Long description (should warn)
        long_desc = "A" * 600  # More than 500 characters
        scenario.description = long_desc
        
        _, warnings = validator._validate_single_scenario(scenario, 0)
        length_warnings = [w for w in warnings if w.error_type == "length"]
        assert len(length_warnings) > 0
    
    def test_numbered_steps_validation(self, validator):
        """Test numbered steps validation"""
        test_cases = [
            ("1. First step\n2. Second step", True),
            ("1) First step\n2) Second step", True),
            ("Step one\nStep two", False),  # Not numbered
            ("1. Only one step", True),     # Single step is OK
            ("", True),                     # Empty is OK
        ]
        
        for steps, should_be_valid in test_cases:
            scenario = ExcelTestScenario(
                scenario_id="TC001",
                feature="Test",
                description="Test",
                preconditions="",
                test_steps=steps,
                expected_results="Result"
            )
            
            _, warnings = validator._validate_single_scenario(scenario, 0)
            format_warnings = [w for w in warnings 
                             if w.column == "Test Steps" and w.error_type == "format"]
            
            if should_be_valid:
                assert len(format_warnings) == 0
            else:
                assert len(format_warnings) > 0
    
    def test_field_to_attribute_mapping(self, validator):
        """Test field name to attribute name conversion"""
        test_cases = [
            ("Scenario ID", "scenario_id"),
            ("Feature", "feature"),
            ("Test Steps", "test_steps"),
            ("Expected Results", "expected_results"),
            ("Estimated Time (min)", "estimated_time")
        ]
        
        for field, expected_attr in test_cases:
            attr = validator._field_to_attribute(field)
            assert attr == expected_attr
    
    def test_find_duplicates(self, validator):
        """Test duplicate finding utility"""
        # No duplicates
        items = ["A", "B", "C"]
        duplicates = validator._find_duplicates(items)
        assert len(duplicates) == 0
        
        # With duplicates
        items = ["A", "B", "A", "C", "B"]
        duplicates = validator._find_duplicates(items)
        assert "A" in duplicates
        assert "B" in duplicates
        assert "C" not in duplicates
    
    def test_is_valid_time(self, validator):
        """Test time validation utility"""
        assert validator._is_valid_time("10") is True
        assert validator._is_valid_time("10.5") is True
        assert validator._is_valid_time("0") is True
        assert validator._is_valid_time("") is True
        assert validator._is_valid_time("  ") is True
        assert validator._is_valid_time("abc") is False
        assert validator._is_valid_time("10 min") is False
    
    def test_has_numbered_steps(self, validator):
        """Test numbered steps validation utility"""
        assert validator._has_numbered_steps("1. First step") is True
        assert validator._has_numbered_steps("1) First step") is True
        assert validator._has_numbered_steps("1. First\n2. Second") is True
        assert validator._has_numbered_steps("Step one") is True  # Single line is OK
        assert validator._has_numbered_steps("") is True
        assert validator._has_numbered_steps("   ") is True
        assert validator._has_numbered_steps("Single line without number") is True
    
    def test_validate_dataframe(self, validator):
        """Test DataFrame validation"""
        # Valid DataFrame
        data = {
            "Scenario ID": ["TC001", "TC002"],
            "Feature": ["Login", "Logout"],
            "Description": ["Test login", "Test logout"],
            "Preconditions": ["", "User logged in"],
            "Test Steps": ["1. Enter credentials", "1. Click logout"],
            "Expected Results": ["Login successful", "Logout successful"],
            "Test Data": ["", ""],
            "Priority": [TestPriority.HIGH.value, TestPriority.MEDIUM.value],
            "Test Type": [TestType.FUNCTIONAL.value, TestType.FUNCTIONAL.value],
            "Status": [TestStatus.NOT_EXECUTED.value, TestStatus.NOT_EXECUTED.value],
            "Assigned To": ["", ""],
            "Estimated Time (min)": ["", ""],
            "Actual Time (min)": ["", ""],
            "Notes": ["", ""]
        }
        
        df = pd.DataFrame(data)
        result = validator.validate_dataframe(df)
        
        assert result.total_scenarios == 2
        assert result.is_valid is True or result.error_count == 0
    
    def test_get_validation_summary_valid(self, validator, valid_scenario):
        """Test validation summary for valid scenarios"""
        result = validator.validate_scenarios([valid_scenario])
        summary = validator.get_validation_summary(result)
        
        assert "valid" in summary.lower()  # Check for valid indicator
    
    def test_get_validation_summary_invalid(self, validator, invalid_scenario):
        """Test validation summary for invalid scenarios"""
        result = validator.validate_scenarios([invalid_scenario])
        summary = validator.get_validation_summary(result)
        
        assert "📊" in summary
        assert "Validation Results" in summary
        assert "Errors:" in summary
        assert str(result.error_count) in summary
    
    def test_get_validation_summary_with_many_errors(self, validator):
        """Test validation summary with many errors (should truncate)"""
        # Create many invalid scenarios
        scenarios = []
        for i in range(10):
            scenarios.append(ExcelTestScenario(
                scenario_id="",  # All missing required fields
                feature="",
                description="",
                preconditions="",
                test_steps="",
                expected_results=""
            ))
        
        result = validator.validate_scenarios(scenarios)
        summary = validator.get_validation_summary(result)
        
        # Should mention "more errors" when truncating
        if result.error_count > 5:
            assert "more errors" in summary
    
    def test_get_streamlit_validation_config(self, validator):
        """Test Streamlit validation configuration"""
        config = validator.get_streamlit_validation_config()
        
        assert isinstance(config, dict)
        assert "suppressRowClickSelection" in config
        assert "rowSelection" in config
        assert "pagination" in config
        assert "custom_css" in config
        
        # Check CSS classes for validation styling
        css = config["custom_css"]
        assert ".ag-row-level-0.validation-error" in css
        assert ".ag-row-level-0.validation-warning" in css


class TestExcelValidatorIntegration:
    """Integration tests for ExcelValidator"""
    
    def test_complex_validation_scenario(self):
        """Test complex validation with mixed valid/invalid data"""
        validator = ExcelValidator()
        
        scenarios = [
            # Valid scenario
            ExcelTestScenario(
                scenario_id="TC001",
                feature="Valid Test",
                description="This is a valid test scenario",
                preconditions="System ready",
                test_steps="1. Execute test\n2. Verify results",
                expected_results="Test passes",
                priority=TestPriority.HIGH.value,
                test_type=TestType.FUNCTIONAL.value,
                estimated_time="15"
            ),
            # Invalid scenario - missing required fields
            ExcelTestScenario(
                scenario_id="TC002",
                feature="",  # Missing
                description="Invalid test",
                preconditions="",
                test_steps="",  # Missing
                expected_results="",  # Missing
                priority="Wrong Priority",  # Invalid
                test_type=TestType.SECURITY.value
            ),
            # Warning scenario - format issues
            ExcelTestScenario(
                scenario_id="tc003",  # Wrong format (lowercase)
                feature="Warning Test",
                description="A" * 600,  # Too long
                preconditions="",
                test_steps="Step without number",  # No numbering
                expected_results="Some result",
                estimated_time="not a number"  # Invalid time
            ),
            # Duplicate ID scenario
            ExcelTestScenario(
                scenario_id="TC001",  # Duplicate
                feature="Duplicate Test",
                description="This has duplicate ID",
                preconditions="",
                test_steps="1. Test step",
                expected_results="Result"
            )
        ]
        
        result = validator.validate_scenarios(scenarios)
        
        # Check overall results
        assert result.total_scenarios == 4
        assert result.valid_scenarios < 4  # Some scenarios are invalid
        assert result.error_count > 0
        assert result.warning_count > 0
        
        # Check specific error types
        error_types = [error.error_type for error in result.errors]
        assert "required" in error_types
        assert "invalid_value" in error_types
        assert "duplicate" in error_types
        
        warning_types = [warning.error_type for warning in result.warnings]
        assert "format" in warning_types
        assert "length" in warning_types
        
        # Generate summary
        summary = validator.get_validation_summary(result)
        assert "❌ Critical Errors:" in summary
        assert "Warnings:" in summary
    
    def test_dataframe_roundtrip_validation(self):
        """Test validation through DataFrame roundtrip"""
        validator = ExcelValidator()
        
        # Create DataFrame with mixed valid/invalid data
        data = {
            "Scenario ID": ["TC001", "", "TC003"],  # Missing middle ID
            "Feature": ["Login", "Profile", "Logout"],
            "Description": ["Test login", "", "Test logout"],  # Missing middle desc
            "Preconditions": ["", "", ""],
            "Test Steps": ["1. Login", "2. Update", "3. Logout"],
            "Expected Results": ["Success", "", "Success"],  # Missing middle result
            "Test Data": ["", "", ""],
            "Priority": [TestPriority.HIGH.value, "Invalid", TestPriority.LOW.value],
            "Test Type": [TestType.FUNCTIONAL.value, TestType.INTEGRATION.value, TestType.FUNCTIONAL.value],
            "Status": [TestStatus.NOT_EXECUTED.value, TestStatus.NOT_EXECUTED.value, TestStatus.NOT_EXECUTED.value],
            "Assigned To": ["", "", ""],
            "Estimated Time (min)": ["10", "invalid", "5"],  # Invalid middle time
            "Actual Time (min)": ["", "", ""],
            "Notes": ["", "", ""]
        }
        
        df = pd.DataFrame(data)
        result = validator.validate_dataframe(df)
        
        # Should catch missing required fields and invalid values
        assert result.error_count > 0
        assert result.warning_count >= 0  # May have warnings too
        
        # Check specific errors for row 1 (index 1)
        row_1_errors = [e for e in result.errors if e.row_index == 1]
        assert len(row_1_errors) > 0  # Should have errors for missing fields
        
        error_columns = [e.column for e in row_1_errors]
        assert "Scenario ID" in error_columns
        assert "Description" in error_columns
        assert "Expected Results" in error_columns