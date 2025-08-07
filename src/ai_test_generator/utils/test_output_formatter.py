"""
Test Output Formatter Module - 테스트 결과 출력 포맷팅

다양한 형태로 테스트 결과를 포맷팅하고 출력하는 유틸리티
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import asdict

from ai_test_generator.core.llm_agent import TestCase, TestScenario
from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange
from ai_test_generator.utils.logger import get_logger

logger = get_logger(__name__)


class TestOutputFormatter:
    """테스트 결과 출력 포맷터"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def format_commit_analysis_json(
        self, 
        analyses: List[CommitAnalysis], 
        filename: Optional[str] = None
    ) -> str:
        """커밋 분석 결과를 JSON으로 저장"""
        if not filename:
            filename = f"commit_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        file_path = self.output_dir / filename
        
        # 데이터 직렬화 가능한 형태로 변환
        data = []
        for analysis in analyses:
            analysis_dict = {
                "commit_hash": analysis.commit_hash,
                "author": analysis.author,
                "author_email": analysis.author_email,
                "commit_date": analysis.commit_date.isoformat(),
                "message": analysis.message,
                "total_additions": analysis.total_additions,
                "total_deletions": analysis.total_deletions,
                "branch": analysis.branch,
                "tags": analysis.tags,
                "files_changed": [
                    {
                        "file_path": fc.file_path,
                        "change_type": fc.change_type,
                        "old_path": fc.old_path,
                        "additions": fc.additions,
                        "deletions": fc.deletions,
                        "language": fc.language,
                        "functions_changed": fc.functions_changed,
                        "classes_changed": fc.classes_changed,
                        "diff_content_preview": fc.diff_content[:500] if fc.diff_content else ""
                    }
                    for fc in analysis.files_changed
                ]
            }
            data.append(analysis_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Commit analysis saved to: {file_path}")
        return str(file_path)
    
    def format_test_cases_json(
        self, 
        test_cases: List[TestCase], 
        filename: Optional[str] = None
    ) -> str:
        """테스트 케이스를 JSON으로 저장"""
        if not filename:
            filename = f"test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        file_path = self.output_dir / filename
        
        # TestCase 객체를 딕셔너리로 변환
        data = []
        for test_case in test_cases:
            test_dict = {
                "name": test_case.name,
                "description": test_case.description,
                "test_type": test_case.test_type.value if hasattr(test_case.test_type, 'value') else str(test_case.test_type),
                "code": test_case.code,
                "assertions": test_case.assertions,
                "dependencies": test_case.dependencies,
                "priority": test_case.priority
            }
            data.append(test_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Test cases saved to: {file_path}")
        return str(file_path)
    
    def format_test_scenarios_json(
        self, 
        scenarios: List[TestScenario], 
        filename: Optional[str] = None
    ) -> str:
        """테스트 시나리오를 JSON으로 저장"""
        if not filename:
            filename = f"test_scenarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        file_path = self.output_dir / filename
        
        # TestScenario 객체를 딕셔너리로 변환
        data = []
        for scenario in scenarios:
            scenario_dict = {
                "scenario_id": scenario.scenario_id,
                "feature": scenario.feature,
                "description": scenario.description,
                "preconditions": scenario.preconditions,
                "test_steps": scenario.test_steps,
                "expected_results": scenario.expected_results,
                "test_data": scenario.test_data,
                "priority": scenario.priority,
                "test_type": scenario.test_type
            }
            data.append(scenario_dict)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Test scenarios saved to: {file_path}")
        return str(file_path)
    
    def format_markdown_report(
        self,
        analyses: List[CommitAnalysis],
        test_cases: List[TestCase],
        scenarios: List[TestScenario],
        execution_summary: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """마크다운 리포트 생성"""
        if not filename:
            filename = f"test_generation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        file_path = self.output_dir / filename
        
        # 마크다운 내용 구성
        content = self._build_markdown_content(analyses, test_cases, scenarios, execution_summary)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Markdown report saved to: {file_path}")
        return str(file_path)
    
    def _build_markdown_content(
        self,
        analyses: List[CommitAnalysis],
        test_cases: List[TestCase],
        scenarios: List[TestScenario],
        execution_summary: Dict[str, Any]
    ) -> str:
        """마크다운 내용 구성"""
        content = f"""# AI Test Generation Report

Generated at: {datetime.now().isoformat()}

## Executive Summary

- **Total Commits Analyzed**: {len(analyses)}
- **Total Test Cases Generated**: {len(test_cases)}
- **Total Test Scenarios Generated**: {len(scenarios)}
- **Execution Time**: {execution_summary.get('execution_time_seconds', 0):.2f} seconds
- **Success Rate**: {execution_summary.get('success', False)}

## Commit Analysis Overview

"""
        
        # 커밋별 요약
        for i, analysis in enumerate(analyses[:10]):  # 최대 10개만 표시
            content += f"""### Commit {i+1}: {analysis.commit_hash[:8]}

- **Author**: {analysis.author} ({analysis.author_email})
- **Date**: {analysis.commit_date.strftime('%Y-%m-%d %H:%M:%S')}
- **Message**: {analysis.message}
- **Files Changed**: {len(analysis.files_changed)}
- **Additions**: +{analysis.total_additions} lines
- **Deletions**: -{analysis.total_deletions} lines

#### Changed Files:
"""
            
            for fc in analysis.files_changed[:5]:  # 파일 최대 5개만 표시
                content += f"- `{fc.file_path}` ({fc.change_type}) - {fc.language or 'unknown'}\n"
                if fc.functions_changed:
                    content += f"  - Functions: {', '.join(fc.functions_changed[:3])}\n"
                if fc.classes_changed:
                    content += f"  - Classes: {', '.join(fc.classes_changed[:3])}\n"
            
            content += "\n"
        
        # 테스트 케이스 요약
        if test_cases:
            content += f"""## Generated Test Cases ({len(test_cases)})

"""
            # 타입별 집계
            test_by_type = {}
            for test in test_cases:
                test_type = str(test.test_type)
                test_by_type[test_type] = test_by_type.get(test_type, 0) + 1
            
            content += "### Test Distribution by Type\n\n"
            for test_type, count in test_by_type.items():
                content += f"- **{test_type}**: {count} tests\n"
            
            content += "\n### Sample Test Cases\n\n"
            
            for i, test in enumerate(test_cases[:3]):  # 샘플 3개만 표시
                content += f"""#### {i+1}. {test.name}

- **Description**: {test.description}
- **Type**: {test.test_type}
- **Priority**: {test.priority}
- **Dependencies**: {', '.join(test.dependencies) if test.dependencies else 'None'}

```python
{test.code[:500]}{"..." if len(test.code) > 500 else ""}
```

"""
        
        # 테스트 시나리오 요약
        if scenarios:
            content += f"""## Generated Test Scenarios ({len(scenarios)})

"""
            
            # 우선순위별 집계
            priority_counts = {}
            type_counts = {}
            
            for scenario in scenarios:
                priority_counts[scenario.priority] = priority_counts.get(scenario.priority, 0) + 1
                type_counts[scenario.test_type] = type_counts.get(scenario.test_type, 0) + 1
            
            content += "### Scenario Distribution\n\n"
            content += "**By Priority:**\n"
            for priority, count in priority_counts.items():
                content += f"- {priority}: {count} scenarios\n"
            
            content += "\n**By Type:**\n"
            for test_type, count in type_counts.items():
                content += f"- {test_type}: {count} scenarios\n"
            
            content += "\n### Sample Test Scenarios\n\n"
            
            for i, scenario in enumerate(scenarios[:2]):  # 샘플 2개만 표시
                content += f"""#### {i+1}. {scenario.scenario_id}: {scenario.feature}

**Description**: {scenario.description}

**Preconditions**:
"""
                if isinstance(scenario.preconditions, list):
                    for precond in scenario.preconditions:
                        content += f"- {precond}\n"
                else:
                    content += f"- {scenario.preconditions}\n"
                
                content += f"""
**Test Steps**:
"""
                if isinstance(scenario.test_steps, list):
                    for j, step in enumerate(scenario.test_steps[:3], 1):
                        if isinstance(step, dict):
                            action = step.get('action', '')
                            data = step.get('data', '')
                            content += f"{j}. {action}: {data}\n"
                        else:
                            content += f"{j}. {step}\n"
                else:
                    content += f"1. {scenario.test_steps}\n"
                
                content += f"""
**Expected Results**:
"""
                if isinstance(scenario.expected_results, list):
                    for result in scenario.expected_results:
                        content += f"- {result}\n"
                else:
                    content += f"- {scenario.expected_results}\n"
                
                content += f"""
**Priority**: {scenario.priority}  
**Type**: {scenario.test_type}

---

"""
        
        # 에러 및 경고
        if execution_summary.get('errors'):
            content += f"""## Errors ({len(execution_summary['errors'])})

"""
            for error in execution_summary['errors']:
                content += f"- ❌ {error}\n"
            content += "\n"
        
        if execution_summary.get('warnings'):
            content += f"""## Warnings ({len(execution_summary['warnings'])})

"""
            for warning in execution_summary['warnings']:
                content += f"- ⚠️ {warning}\n"
            content += "\n"
        
        # 출력 파일 목록
        if execution_summary.get('output_files'):
            content += """## Generated Files

"""
            for file_type, file_path in execution_summary['output_files'].items():
                content += f"- **{file_type.title()}**: `{file_path}`\n"
        
        content += f"""

## Technical Details

- **Analysis Engine**: AI Test Generator v1.0
- **LLM Provider**: Azure OpenAI Service
- **VCS Integration**: GitPython + PyGitHub
- **Document Generation**: openpyxl + pandas
- **Report Generation**: Automated Markdown

---

*This report was automatically generated by AI Test Generator*
"""
        
        return content
    
    def format_html_report(
        self,
        analyses: List[CommitAnalysis],
        test_cases: List[TestCase],
        scenarios: List[TestScenario],
        execution_summary: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """HTML 리포트 생성"""
        if not filename:
            filename = f"test_generation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        file_path = self.output_dir / filename
        
        # HTML 내용 구성
        html_content = self._build_html_content(analyses, test_cases, scenarios, execution_summary)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved to: {file_path}")
        return str(file_path)
    
    def _build_html_content(
        self,
        analyses: List[CommitAnalysis],
        test_cases: List[TestCase],
        scenarios: List[TestScenario],
        execution_summary: Dict[str, Any]
    ) -> str:
        """HTML 내용 구성"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Test Generation Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; border-left: 4px solid #3498db; padding-left: 15px; }}
        h3 {{ color: #2c3e50; }}
        .summary {{ background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .summary-item {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .summary-value {{ font-weight: bold; color: #2980b9; font-size: 1.2em; }}
        .commit-box {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; background: #fafafa; }}
        .test-case {{ border-left: 4px solid #27ae60; padding: 15px; margin: 10px 0; background: #f8f9fa; }}
        .scenario {{ border-left: 4px solid #e74c3c; padding: 15px; margin: 10px 0; background: #f8f9fa; }}
        .code {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', monospace; }}
        .error {{ color: #e74c3c; background: #fdf2f2; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        .warning {{ color: #f39c12; background: #fef9e7; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        .file-list {{ background: #f8f9fa; padding: 10px; border-radius: 5px; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }}
        .badge-primary {{ background: #3498db; color: white; }}
        .badge-success {{ background: #27ae60; color: white; }}
        .badge-warning {{ background: #f39c12; color: white; }}
        .badge-danger {{ background: #e74c3c; color: white; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI Test Generation Report</h1>
        <p><strong>Generated at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="summary">
            <h2>📊 Executive Summary</h2>
            <div class="summary-item">
                <div>Commits Analyzed</div>
                <div class="summary-value">{len(analyses)}</div>
            </div>
            <div class="summary-item">
                <div>Test Cases Generated</div>
                <div class="summary-value">{len(test_cases)}</div>
            </div>
            <div class="summary-item">
                <div>Test Scenarios Generated</div>
                <div class="summary-value">{len(scenarios)}</div>
            </div>
            <div class="summary-item">
                <div>Execution Time</div>
                <div class="summary-value">{execution_summary.get('execution_time_seconds', 0):.2f}s</div>
            </div>
            <div class="summary-item">
                <div>Success</div>
                <div class="summary-value">{'✅ Yes' if execution_summary.get('success', False) else '❌ No'}</div>
            </div>
        </div>
        
        <h2>📝 Commit Analysis</h2>
        {self._build_commits_html_section(analyses[:10])}
        
        {self._build_test_cases_html_section(test_cases) if test_cases else ''}
        
        {self._build_scenarios_html_section(scenarios) if scenarios else ''}
        
        {self._build_errors_html_section(execution_summary) if execution_summary.get('errors') or execution_summary.get('warnings') else ''}
        
        {self._build_files_html_section(execution_summary) if execution_summary.get('output_files') else ''}
        
        <hr>
        <footer>
            <p><em>This report was automatically generated by AI Test Generator</em></p>
        </footer>
    </div>
</body>
</html>"""
    
    def _build_commits_html_section(self, analyses: List[CommitAnalysis]) -> str:
        """커밋 분석 HTML 섹션 구성"""
        html = ""
        for i, analysis in enumerate(analyses):
            html += f"""
        <div class="commit-box">
            <h3>Commit {i+1}: <code>{analysis.commit_hash[:8]}</code></h3>
            <p><strong>Author:</strong> {analysis.author} ({analysis.author_email})</p>
            <p><strong>Date:</strong> {analysis.commit_date.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Message:</strong> {analysis.message}</p>
            <p>
                <span class="badge badge-success">+{analysis.total_additions}</span>
                <span class="badge badge-danger">-{analysis.total_deletions}</span>
                <span class="badge badge-primary">{len(analysis.files_changed)} files</span>
            </p>
            
            <div class="file-list">
                <strong>Changed Files:</strong>
                <ul>
"""
            for fc in analysis.files_changed[:5]:
                html += f'<li><code>{fc.file_path}</code> ({fc.change_type}) - {fc.language or "unknown"}</li>'
            
            html += """
                </ul>
            </div>
        </div>
"""
        return html
    
    def _build_test_cases_html_section(self, test_cases: List[TestCase]) -> str:
        """테스트 케이스 HTML 섹션 구성"""
        html = f"""
        <h2>🧪 Generated Test Cases ({len(test_cases)})</h2>
"""
        
        for i, test in enumerate(test_cases[:5]):  # 최대 5개만 표시
            html += f"""
        <div class="test-case">
            <h3>{i+1}. {test.name}</h3>
            <p><strong>Description:</strong> {test.description}</p>
            <p>
                <span class="badge badge-primary">{test.test_type}</span>
                <span class="badge badge-warning">Priority: {test.priority}</span>
            </p>
            <div class="code">{test.code[:300]}{"..." if len(test.code) > 300 else ""}</div>
        </div>
"""
        
        return html
    
    def _build_scenarios_html_section(self, scenarios: List[TestScenario]) -> str:
        """테스트 시나리오 HTML 섹션 구성"""
        html = f"""
        <h2>📋 Generated Test Scenarios ({len(scenarios)})</h2>
"""
        
        for i, scenario in enumerate(scenarios[:3]):  # 최대 3개만 표시
            html += f"""
        <div class="scenario">
            <h3>{i+1}. {scenario.scenario_id}: {scenario.feature}</h3>
            <p><strong>Description:</strong> {scenario.description}</p>
            <p>
                <span class="badge badge-primary">{scenario.test_type}</span>
                <span class="badge badge-warning">{scenario.priority}</span>
            </p>
"""
            
            if isinstance(scenario.preconditions, list) and scenario.preconditions:
                html += "<p><strong>Preconditions:</strong></p><ul>"
                for precond in scenario.preconditions[:3]:
                    html += f"<li>{precond}</li>"
                html += "</ul>"
            
            html += "</div>"
        
        return html
    
    def _build_errors_html_section(self, execution_summary: Dict[str, Any]) -> str:
        """에러/경고 HTML 섹션 구성"""
        html = "<h2>⚠️ Issues</h2>"
        
        if execution_summary.get('errors'):
            html += "<h3>Errors</h3>"
            for error in execution_summary['errors']:
                html += f'<div class="error">❌ {error}</div>'
        
        if execution_summary.get('warnings'):
            html += "<h3>Warnings</h3>"
            for warning in execution_summary['warnings']:
                html += f'<div class="warning">⚠️ {warning}</div>'
        
        return html
    
    def _build_files_html_section(self, execution_summary: Dict[str, Any]) -> str:
        """출력 파일 HTML 섹션 구성"""
        html = """
        <h2>📁 Generated Files</h2>
        <table>
            <thead>
                <tr>
                    <th>File Type</th>
                    <th>Path</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for file_type, file_path in execution_summary['output_files'].items():
            html += f"""
                <tr>
                    <td><span class="badge badge-primary">{file_type.title()}</span></td>
                    <td><code>{file_path}</code></td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
"""
        
        return html
    
    def export_all_formats(
        self,
        analyses: List[CommitAnalysis],
        test_cases: List[TestCase],
        scenarios: List[TestScenario],
        execution_summary: Dict[str, Any],
        base_filename: Optional[str] = None
    ) -> Dict[str, str]:
        """모든 포맷으로 내보내기"""
        if not base_filename:
            base_filename = f"test_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_files = {}
        
        # JSON 파일들
        output_files['commit_analysis_json'] = self.format_commit_analysis_json(
            analyses, f"{base_filename}_commits.json"
        )
        
        if test_cases:
            output_files['test_cases_json'] = self.format_test_cases_json(
                test_cases, f"{base_filename}_tests.json"
            )
        
        if scenarios:
            output_files['scenarios_json'] = self.format_test_scenarios_json(
                scenarios, f"{base_filename}_scenarios.json"
            )
        
        # 리포트 파일들
        output_files['markdown_report'] = self.format_markdown_report(
            analyses, test_cases, scenarios, execution_summary, f"{base_filename}_report.md"
        )
        
        output_files['html_report'] = self.format_html_report(
            analyses, test_cases, scenarios, execution_summary, f"{base_filename}_report.html"
        )
        
        logger.info(f"All formats exported: {len(output_files)} files")
        return output_files