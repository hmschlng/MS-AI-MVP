"""
Main Integration Logic - 전체 워크플로우 통합

Git 분석 → LLM Agent → Excel 생성의 전체 파이프라인을 관리합니다.
"""
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime

from ai_test_generator.core.git_analyzer import GitAnalyzer
from ai_test_generator.core.svn_analyzer import SvnAnalyzer
from ai_test_generator.core.llm_agent import LLMAgent, TestCase, TestScenario
from ai_test_generator.core.vcs_models import CommitAnalysis, FileChange
from ai_test_generator.excel.excel_generator import ExcelGenerator
from ai_test_generator.excel.excel_templates import ExcelTestScenario
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import get_logger, LogContext
from ai_test_generator.utils.prompt_loader import PromptLoader
from ai_test_generator.utils.test_output_formatter import TestOutputFormatter

logger = get_logger(__name__)


class TestGenerationResult:
    """테스트 생성 결과"""
    
    def __init__(self):
        self.commit_analyses: List[CommitAnalysis] = []
        self.generated_tests: List[TestCase] = []
        self.test_scenarios: List[TestScenario] = []
        self.excel_scenarios: List[ExcelTestScenario] = []
        self.output_files: Dict[str, str] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.execution_time: Optional[float] = None
        
    def add_error(self, error: str):
        """오류 추가"""
        self.errors.append(error)
        logger.error(error)
    
    def add_warning(self, warning: str):
        """경고 추가"""
        self.warnings.append(warning)
        logger.warning(warning)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """요약 딕셔너리 변환"""
        return {
            "total_commits_analyzed": len(self.commit_analyses),
            "total_files_changed": sum(len(ca.files_changed) for ca in self.commit_analyses),
            "total_tests_generated": len(self.generated_tests),
            "total_scenarios_generated": len(self.test_scenarios),
            "output_files": self.output_files,
            "execution_time_seconds": self.execution_time,
            "errors": self.errors,
            "warnings": self.warnings,
            "success": len(self.errors) == 0
        }


class AITestGenerator:
    """AI 테스트 생성기 메인 클래스"""
    
    def __init__(self, config: Config):
        """
        초기화
        
        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self.llm_agent = LLMAgent(config)
        self.excel_generator = ExcelGenerator()
        self.prompt_loader = PromptLoader()
        
        # 출력 디렉토리 확인
        self.config.app.output_directory.mkdir(parents=True, exist_ok=True)
        self.config.app.temp_directory.mkdir(parents=True, exist_ok=True)
        
        # 출력 포매터 초기화
        self.output_formatter = TestOutputFormatter(self.config.app.output_directory)
        
        logger.info("AITestGenerator initialized successfully")
    
    async def generate_from_git_repo(
        self,
        repo_path: str,
        start_commit: Optional[str] = None,
        end_commit: Optional[str] = None,
        branch: Optional[str] = None,
        max_commits: int = 10,
        project_info: Optional[Dict[str, str]] = None
    ) -> TestGenerationResult:
        """
        Git 저장소에서 테스트 생성
        
        Args:
            repo_path: Git 저장소 경로
            start_commit: 시작 커밋 (None이면 최근 커밋들)
            end_commit: 종료 커밋 (None이면 HEAD)
            branch: 분석할 브랜치
            max_commits: 최대 분석할 커밋 수
            project_info: 프로젝트 정보
            
        Returns:
            테스트 생성 결과
        """
        start_time = datetime.now()
        result = TestGenerationResult()
        
        with LogContext(f"Generating tests from Git repo: {repo_path}"):
            try:
                # 1. Git 분석
                git_analyzer = GitAnalyzer(repo_path, branch or "main")
                commits = git_analyzer.get_commits_between(
                    start_commit, end_commit, branch, max_commits
                )
                
                if not commits:
                    result.add_error("No commits found to analyze")
                    return result
                
                logger.info(f"Found {len(commits)} commits to analyze")
                
                # 2. 커밋별 분석 및 테스트 생성
                for i, commit in enumerate(commits):
                    logger.info(f"Processing commit {i+1}/{len(commits)}: {commit.hexsha[:8]}")
                    
                    try:
                        # 커밋 분석
                        commit_analysis = git_analyzer.analyze_commit(commit)
                        result.commit_analyses.append(commit_analysis)
                        
                        # 변경사항이 있는 경우에만 테스트 생성
                        if commit_analysis.files_changed:
                            test_result = await self.llm_agent.generate_tests(commit_analysis)
                            
                            if test_result.get("error"):
                                result.add_error(f"Commit {commit.hexsha[:8]}: {test_result['error']}")
                            else:
                                result.generated_tests.extend(test_result.get("tests", []))
                                result.test_scenarios.extend(test_result.get("scenarios", []))
                        else:
                            result.add_warning(f"Commit {commit.hexsha[:8]}: No relevant file changes")
                    
                    except Exception as e:
                        result.add_error(f"Failed to process commit {commit.hexsha[:8]}: {str(e)}")
                        continue
                
                # 3. Excel 문서 생성
                if result.test_scenarios:
                    try:
                        excel_path = await self._generate_excel_output(
                            result.test_scenarios, 
                            project_info,
                            f"git_tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        )
                        result.output_files["excel"] = excel_path
                        logger.info(f"Excel file generated: {excel_path}")
                    except Exception as e:
                        result.add_error(f"Failed to generate Excel file: {str(e)}")
                
                # 4. 테스트 코드 파일 생성
                if result.generated_tests:
                    try:
                        test_files = await self._generate_test_code_files(result.generated_tests)
                        result.output_files.update(test_files)
                        logger.info(f"Test code files generated: {len(test_files)}")
                    except Exception as e:
                        result.add_error(f"Failed to generate test code files: {str(e)}")
                
                # 5. 요약 리포트 생성
                try:
                    summary_path = await self._generate_summary_report(result)
                    result.output_files["summary"] = summary_path
                except Exception as e:
                    result.add_error(f"Failed to generate summary report: {str(e)}")
            
            except Exception as e:
                result.add_error(f"Critical error in Git analysis: {str(e)}")
            
            finally:
                result.execution_time = (datetime.now() - start_time).total_seconds()
        
        return result
    
    async def generate_from_remote_git(
        self,
        remote_url: str,
        branch: Optional[str] = None,
        max_commits: int = 10,
        project_info: Optional[Dict[str, str]] = None
    ) -> TestGenerationResult:
        """
        원격 Git 저장소에서 테스트 생성
        
        Args:
            remote_url: 원격 저장소 URL
            branch: 분석할 브랜치
            max_commits: 최대 분석할 커밋 수
            project_info: 프로젝트 정보
            
        Returns:
            테스트 생성 결과
        """
        result = TestGenerationResult()
        temp_path = None
        
        try:
            # 임시 경로에 클론
            temp_path = GitAnalyzer.clone_remote_repo(remote_url, branch=branch)
            logger.info(f"Cloned remote repository to: {temp_path}")
            
            # 로컬 저장소처럼 처리
            result = await self.generate_from_git_repo(
                temp_path, None, None, branch, max_commits, project_info
            )
            
        except Exception as e:
            result.add_error(f"Failed to clone remote repository: {str(e)}")
        
        finally:
            # 임시 디렉토리 정리
            if temp_path:
                try:
                    import shutil
                    shutil.rmtree(temp_path)
                    logger.info(f"Cleaned up temporary directory: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
        
        return result
    
    async def generate_from_svn_repo(
        self,
        repo_url: str,
        start_rev: Optional[int] = None,
        end_rev: Optional[int] = None,
        max_revisions: int = 10,
        project_info: Optional[Dict[str, str]] = None
    ) -> TestGenerationResult:
        """
        SVN 저장소에서 테스트 생성
        
        Args:
            repo_url: SVN 저장소 URL
            start_rev: 시작 리비전
            end_rev: 종료 리비전
            max_revisions: 최대 분석할 리비전 수
            project_info: 프로젝트 정보
            
        Returns:
            테스트 생성 결과
        """
        start_time = datetime.now()
        result = TestGenerationResult()
        svn_analyzer = None
        
        with LogContext(f"Generating tests from SVN repo: {repo_url}"):
            try:
                # 1. SVN 분석
                svn_analyzer = SvnAnalyzer.from_remote(repo_url)
                log_entries = svn_analyzer.get_log_entries(start_rev, end_rev, max_revisions)
                
                if not log_entries:
                    result.add_error("No revisions found to analyze")
                    return result
                
                logger.info(f"Found {len(log_entries)} revisions to analyze")
                
                # 2. 리비전별 분석 및 테스트 생성
                for i, log_entry in enumerate(log_entries):
                    logger.info(f"Processing revision {i+1}/{len(log_entries)}: {log_entry.revision.number}")
                    
                    try:
                        # 리비전 분석
                        commit_analysis = svn_analyzer.analyze_log_entry(log_entry)
                        result.commit_analyses.append(commit_analysis)
                        
                        # 변경사항이 있는 경우에만 테스트 생성
                        if commit_analysis.files_changed:
                            test_result = await self.llm_agent.generate_tests(commit_analysis)
                            
                            if test_result.get("error"):
                                result.add_error(f"Revision {log_entry.revision.number}: {test_result['error']}")
                            else:
                                result.generated_tests.extend(test_result.get("tests", []))
                                result.test_scenarios.extend(test_result.get("scenarios", []))
                        else:
                            result.add_warning(f"Revision {log_entry.revision.number}: No relevant file changes")
                    
                    except Exception as e:
                        result.add_error(f"Failed to process revision {log_entry.revision.number}: {str(e)}")
                        continue
                
                # 3. 출력 파일 생성 (Git과 동일한 로직)
                if result.test_scenarios:
                    try:
                        excel_path = await self._generate_excel_output(
                            result.test_scenarios, 
                            project_info,
                            f"svn_tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        )
                        result.output_files["excel"] = excel_path
                    except Exception as e:
                        result.add_error(f"Failed to generate Excel file: {str(e)}")
                
                if result.generated_tests:
                    try:
                        test_files = await self._generate_test_code_files(result.generated_tests)
                        result.output_files.update(test_files)
                    except Exception as e:
                        result.add_error(f"Failed to generate test code files: {str(e)}")
                
                try:
                    summary_path = await self._generate_summary_report(result)
                    result.output_files["summary"] = summary_path
                except Exception as e:
                    result.add_error(f"Failed to generate summary report: {str(e)}")
            
            except Exception as e:
                result.add_error(f"Critical error in SVN analysis: {str(e)}")
            
            finally:
                result.execution_time = (datetime.now() - start_time).total_seconds()
                
                # SVN 리소스 정리
                if svn_analyzer:
                    try:
                        svn_analyzer.close()
                    except Exception as e:
                        logger.warning(f"Failed to close SVN analyzer: {e}")
        
        return result
    
    async def _generate_excel_output(
        self,
        test_scenarios: List[TestScenario],
        project_info: Optional[Dict[str, str]],
        filename_prefix: str
    ) -> str:
        """Excel 파일 생성"""
        # 기본 프로젝트 정보 설정
        if not project_info:
            project_info = self.excel_generator.get_default_project_info()
        
        # 워크북 생성
        workbook = self.excel_generator.generate_from_llm_scenarios(
            test_scenarios, project_info
        )
        
        # 파일 저장
        excel_filename = f"{filename_prefix}.xlsx"
        excel_path = self.config.app.output_directory / excel_filename
        
        return self.excel_generator.save_workbook(workbook, excel_path)
    
    async def _generate_test_code_files(self, tests: List[TestCase]) -> Dict[str, str]:
        """테스트 코드 파일 생성"""
        test_files = {}
        
        # 언어별로 테스트 그룹화
        tests_by_language = {}
        for test in tests:
            # 테스트의 언어 추정 (간단한 휴리스틱)
            language = self._detect_test_language(test.code)
            if language not in tests_by_language:
                tests_by_language[language] = []
            tests_by_language[language].append(test)
        
        # 언어별 파일 생성
        for language, language_tests in tests_by_language.items():
            try:
                file_path = await self._create_test_file(language, language_tests)
                test_files[f"test_code_{language}"] = file_path
                logger.info(f"Generated {language} test file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to create {language} test file: {e}")
        
        return test_files
    
    def _detect_test_language(self, test_code: str) -> str:
        """테스트 코드에서 언어 추정"""
        code_lower = test_code.lower()
        
        if "def test_" in code_lower or "import pytest" in code_lower:
            return "python"
        elif "@test" in code_lower or "import org.junit" in code_lower:
            return "java"
        elif "describe(" in code_lower or "it(" in code_lower or "jest" in code_lower:
            return "javascript"
        elif "func test" in code_lower or "import testing" in code_lower:
            return "go"
        else:
            return "unknown"
    
    async def _create_test_file(self, language: str, tests: List[TestCase]) -> str:
        """언어별 테스트 파일 생성"""
        # 파일 확장자 매핑
        extensions = {
            "python": ".py",
            "java": ".java",
            "javascript": ".js",
            "typescript": ".ts",
            "go": ".go",
            "unknown": ".txt"
        }
        
        extension = extensions.get(language, ".txt")
        filename = f"generated_tests_{language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"
        file_path = self.config.app.output_directory / filename
        
        # 파일 내용 생성
        content = self._build_test_file_content(language, tests)
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
    
    def _build_test_file_content(self, language: str, tests: List[TestCase]) -> str:
        """테스트 파일 내용 구성"""
        if language == "python":
            return self._build_python_test_file(tests)
        elif language == "java":
            return self._build_java_test_file(tests)
        elif language == "javascript":
            return self._build_javascript_test_file(tests)
        else:
            # 기본 형태
            content = f"# Generated Tests - {language.upper()}\n"
            content += f"# Generated at: {datetime.now().isoformat()}\n\n"
            
            for i, test in enumerate(tests):
                content += f"# Test {i+1}: {test.name}\n"
                content += f"# Description: {test.description}\n"
                content += f"# Priority: {test.priority}\n"
                content += test.code + "\n\n"
            
            return content
    
    def _build_python_test_file(self, tests: List[TestCase]) -> str:
        """Python 테스트 파일 구성"""
        content = '''"""
Generated Test File
Auto-generated by AI Test Generator
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Generated at: ''' + datetime.now().isoformat() + '''

'''
        
        for test in tests:
            content += f"\n# {test.description}\n"
            if test.dependencies:
                content += f"# Dependencies: {', '.join(test.dependencies)}\n"
            content += test.code + "\n"
        
        return content
    
    def _build_java_test_file(self, tests: List[TestCase]) -> str:
        """Java 테스트 파일 구성"""
        content = '''/**
 * Generated Test File
 * Auto-generated by AI Test Generator
 * Generated at: ''' + datetime.now().isoformat() + '''
 */
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import static org.junit.jupiter.api.Assertions.*;

public class GeneratedTests {
    
'''
        
        for test in tests:
            content += f"\n    /**\n     * {test.description}\n"
            if test.dependencies:
                content += f"     * Dependencies: {', '.join(test.dependencies)}\n"
            content += "     */\n"
            content += "    " + test.code.replace('\n', '\n    ') + "\n"
        
        content += "}\n"
        return content
    
    def _build_javascript_test_file(self, tests: List[TestCase]) -> str:
        """JavaScript 테스트 파일 구성"""
        content = '''/**
 * Generated Test File
 * Auto-generated by AI Test Generator
 * Generated at: ''' + datetime.now().isoformat() + '''
 */

'''
        
        for test in tests:
            content += f"\n// {test.description}\n"
            if test.dependencies:
                content += f"// Dependencies: {', '.join(test.dependencies)}\n"
            content += test.code + "\n"
        
        return content
    
    async def _generate_summary_report(self, result: TestGenerationResult) -> str:
        """요약 리포트 생성 (TestOutputFormatter 활용)"""
        try:
            # 모든 형식으로 리포트 생성
            output_files = self.output_formatter.export_all_formats(
                result.commit_analyses,
                result.generated_tests,
                result.test_scenarios,
                result.to_summary_dict()
            )
            
            # 생성된 파일들을 결과에 추가
            result.output_files.update(output_files)
            
            logger.info(f"Rich reports generated: {len(output_files)} files")
            
            # 메인 마크다운 리포트 경로 반환
            return output_files.get('markdown_report', '')
            
        except Exception as e:
            logger.error(f"Failed to generate rich reports: {e}")
            
            # 폴백: 기본 JSON 요약만 생성
            summary = result.to_summary_dict()
            json_filename = f"test_generation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_path = self.config.app.output_directory / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Fallback summary generated: {json_path}")
            return str(json_path)
    


# 편의 함수들
async def generate_tests_from_git(
    repo_path: str,
    config: Optional[Config] = None,
    **kwargs
) -> TestGenerationResult:
    """Git 저장소에서 테스트 생성 (편의 함수)"""
    if config is None:
        config = Config()
    
    generator = AITestGenerator(config)
    return await generator.generate_from_git_repo(repo_path, **kwargs)


async def generate_tests_from_remote_git(
    remote_url: str,
    config: Optional[Config] = None,
    **kwargs
) -> TestGenerationResult:
    """원격 Git 저장소에서 테스트 생성 (편의 함수)"""
    if config is None:
        config = Config()
    
    generator = AITestGenerator(config)
    return await generator.generate_from_remote_git(remote_url, **kwargs)


async def generate_tests_from_svn(
    repo_url: str,
    config: Optional[Config] = None,
    **kwargs
) -> TestGenerationResult:
    """SVN 저장소에서 테스트 생성 (편의 함수)"""
    if config is None:
        config = Config()
    
    generator = AITestGenerator(config)
    return await generator.generate_from_svn_repo(repo_url, **kwargs)


if __name__ == "__main__":
    # 간단한 테스트 실행
    import sys
    
    async def main():
        config = Config()
        
        if len(sys.argv) < 2:
            print("Usage: python main.py <git_repo_path>")
            return
        
        repo_path = sys.argv[1]
        generator = AITestGenerator(config)
        
        print(f"Analyzing Git repository: {repo_path}")
        result = await generator.generate_from_git_repo(repo_path, max_commits=5)
        
        print("\n=== Test Generation Results ===")
        summary = result.to_summary_dict()
        print(f"Commits analyzed: {summary['total_commits_analyzed']}")
        print(f"Tests generated: {summary['total_tests_generated']}")
        print(f"Scenarios generated: {summary['total_scenarios_generated']}")
        print(f"Execution time: {summary['execution_time_seconds']:.2f}s")
        
        if summary['output_files']:
            print("\nOutput files:")
            for file_type, path in summary['output_files'].items():
                print(f"  {file_type}: {path}")
        
        if summary['errors']:
            print(f"\nErrors: {len(summary['errors'])}")
            for error in summary['errors'][:3]:
                print(f"  - {error}")
        
        if summary['warnings']:
            print(f"\nWarnings: {len(summary['warnings'])}")
            for warning in summary['warnings'][:3]:
                print(f"  - {warning}")
    
    asyncio.run(main())