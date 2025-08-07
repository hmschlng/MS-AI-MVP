#!/usr/bin/env python3
"""
AI Test Generator - Project Runner

프로젝트의 다양한 실행 옵션을 제공하는 통합 실행 스크립트
"""
import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ai_test_generator.main import generate_tests_from_git, generate_tests_from_remote_git
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import setup_logger, get_logger


def setup_argument_parser() -> argparse.ArgumentParser:
    """명령행 인자 파서 설정"""
    parser = argparse.ArgumentParser(
        description="AI Test Generator - Automated test generation from VCS changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local Git repository
  python run.py git ./my-repo --max-commits 5

  # Remote Git repository  
  python run.py remote https://github.com/user/repo.git --max-commits 3

  # With custom output directory
  python run.py git ./my-repo --output ./test-results --project-name "My Project"

  # Run examples
  python run.py example local

  # Run tests
  python run.py test unit
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Git 분석 명령
    git_parser = subparsers.add_parser('git', help='Analyze local Git repository')
    git_parser.add_argument('repo_path', help='Path to Git repository')
    git_parser.add_argument('--branch', help='Branch to analyze (default: current branch)')
    git_parser.add_argument('--start-commit', help='Start commit hash')
    git_parser.add_argument('--end-commit', help='End commit hash') 
    git_parser.add_argument('--max-commits', type=int, default=10, help='Maximum commits to analyze (default: 10)')
    
    # 원격 Git 분석 명령
    remote_parser = subparsers.add_parser('remote', help='Analyze remote Git repository')
    remote_parser.add_argument('remote_url', help='Remote repository URL')
    remote_parser.add_argument('--branch', help='Branch to analyze')
    remote_parser.add_argument('--max-commits', type=int, default=10, help='Maximum commits to analyze (default: 10)')
    
    # 예제 실행 명령
    example_parser = subparsers.add_parser('example', help='Run example scenarios')
    example_parser.add_argument('example_type', 
                               choices=['local', 'remote', 'advanced', 'error', 'config', 'perf', 'all'],
                               help='Type of example to run')
    
    # 테스트 실행 명령
    test_parser = subparsers.add_parser('test', help='Run project tests')
    test_parser.add_argument('test_type', 
                            choices=['unit', 'integration', 'performance', 'error', 'all'],
                            nargs='?', default='all',
                            help='Type of tests to run (default: all)')
    
    # 공통 인자
    for p in [git_parser, remote_parser]:
        p.add_argument('--output', help='Output directory (default: ./output)')
        p.add_argument('--project-name', help='Project name for reports')
        p.add_argument('--project-version', help='Project version')
        p.add_argument('--tester', help='Tester name')
        p.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                      default='INFO', help='Logging level (default: INFO)')
        p.add_argument('--log-file', help='Log file path')
        p.add_argument('--quiet', '-q', action='store_true', help='Quiet mode (minimal output)')
        p.add_argument('--verbose', '-v', action='store_true', help='Verbose mode (detailed output)')
    
    return parser


async def run_git_analysis(args) -> None:
    """Git 분석 실행"""
    logger = get_logger()
    
    if not Path(args.repo_path).exists():
        print(f"❌ Error: Repository path does not exist: {args.repo_path}")
        return
    
    # 프로젝트 정보 구성
    project_info = {}
    if args.project_name:
        project_info['project_name'] = args.project_name
    if args.project_version:
        project_info['version'] = args.project_version
    if args.tester:
        project_info['tester'] = args.tester
    
    # 출력 디렉토리 설정
    if args.output:
        import os
        os.environ['OUTPUT_DIRECTORY'] = args.output
    
    try:
        if not args.quiet:
            print(f"🔍 Analyzing Git repository: {args.repo_path}")
            print(f"   Branch: {args.branch or 'current'}")
            print(f"   Max commits: {args.max_commits}")
            if project_info:
                print(f"   Project: {project_info.get('project_name', 'N/A')}")
        
        # 분석 실행
        result = await generate_tests_from_git(
            repo_path=args.repo_path,
            start_commit=args.start_commit,
            end_commit=args.end_commit,
            branch=args.branch,
            max_commits=args.max_commits,
            project_info=project_info or None
        )
        
        # 결과 출력
        await print_results(result, args.quiet, args.verbose)
        
    except Exception as e:
        logger.error(f"Git analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")


async def run_remote_analysis(args) -> None:
    """원격 저장소 분석 실행"""
    logger = get_logger()
    
    # 프로젝트 정보 구성
    project_info = {}
    if args.project_name:
        project_info['project_name'] = args.project_name
    if args.project_version:
        project_info['version'] = args.project_version
    if args.tester:
        project_info['tester'] = args.tester
    
    # 출력 디렉토리 설정
    if args.output:
        import os
        os.environ['OUTPUT_DIRECTORY'] = args.output
    
    try:
        if not args.quiet:
            print(f"🌐 Analyzing remote repository: {args.remote_url}")
            print(f"   Branch: {args.branch or 'default'}")
            print(f"   Max commits: {args.max_commits}")
            if project_info:
                print(f"   Project: {project_info.get('project_name', 'N/A')}")
        
        # 분석 실행
        result = await generate_tests_from_remote_git(
            remote_url=args.remote_url,
            branch=args.branch,
            max_commits=args.max_commits,
            project_info=project_info or None
        )
        
        # 결과 출력
        await print_results(result, args.quiet, args.verbose)
        
    except Exception as e:
        logger.error(f"Remote analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")


async def run_examples(args) -> None:
    """예제 실행"""
    try:
        from example import main as example_main
        
        # example.py의 sys.argv를 설정
        original_argv = sys.argv
        sys.argv = ['example.py', args.example_type]
        
        await example_main()
        
        sys.argv = original_argv
        
    except ImportError:
        print("❌ Error: example.py not found")
    except Exception as e:
        print(f"❌ Example execution failed: {e}")


async def run_tests(args) -> None:
    """테스트 실행"""
    try:
        import pytest
        
        # pytest 인자 구성
        pytest_args = [
            "tests/",
            "-v",
            "--tb=short"
        ]
        
        if args.test_type != 'all':
            pytest_args.extend(["-m", args.test_type])
        
        # pytest 실행
        exit_code = pytest.main(pytest_args)
        
        if exit_code == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ Some tests failed (exit code: {exit_code})")
            
    except ImportError:
        print("❌ Error: pytest not installed")
        print("Install with: pip install pytest")
    except Exception as e:
        print(f"❌ Test execution failed: {e}")


async def print_results(result, quiet: bool = False, verbose: bool = False) -> None:
    """분석 결과 출력"""
    summary = result.to_summary_dict()
    
    if quiet:
        # 간단한 요약만
        status = "✅ Success" if summary['success'] else "❌ Failed"
        print(f"{status} | Tests: {summary['total_tests_generated']} | Scenarios: {summary['total_scenarios_generated']} | Time: {summary['execution_time_seconds']:.1f}s")
        return
    
    print("\n" + "="*50)
    print("📊 ANALYSIS RESULTS")
    print("="*50)
    
    # 기본 통계
    print(f"🔍 Commits Analyzed: {summary['total_commits_analyzed']}")
    print(f"📁 Files Changed: {summary['total_files_changed']}")
    print(f"🧪 Tests Generated: {summary['total_tests_generated']}")
    print(f"📋 Scenarios Generated: {summary['total_scenarios_generated']}")
    print(f"⏱️ Execution Time: {summary['execution_time_seconds']:.2f} seconds")
    print(f"✅ Status: {'Success' if summary['success'] else 'Failed'}")
    
    # 출력 파일
    if summary['output_files']:
        print(f"\n📁 Generated Files:")
        for file_type, file_path in summary['output_files'].items():
            file_size = ""
            if Path(file_path).exists():
                size_bytes = Path(file_path).stat().st_size
                if size_bytes > 1024*1024:
                    file_size = f" ({size_bytes/(1024*1024):.1f} MB)"
                elif size_bytes > 1024:
                    file_size = f" ({size_bytes/1024:.1f} KB)"
                else:
                    file_size = f" ({size_bytes} bytes)"
            
            print(f"   📄 {file_type.title()}: {Path(file_path).name}{file_size}")
    
    # 에러 및 경고
    if summary['errors']:
        print(f"\n❌ Errors ({len(summary['errors'])}):")
        for error in summary['errors'][:5 if not verbose else None]:
            print(f"   • {error}")
        if len(summary['errors']) > 5 and not verbose:
            print(f"   • ... and {len(summary['errors']) - 5} more errors")
    
    if summary['warnings']:
        print(f"\n⚠️ Warnings ({len(summary['warnings'])}):")
        for warning in summary['warnings'][:3 if not verbose else None]:
            print(f"   • {warning}")
        if len(summary['warnings']) > 3 and not verbose:
            print(f"   • ... and {len(summary['warnings']) - 3} more warnings")
    
    # 상세 정보 (verbose 모드)
    if verbose and result.commit_analyses:
        print(f"\n🔍 Detailed Commit Analysis:")
        for i, analysis in enumerate(result.commit_analyses[:5], 1):
            print(f"\n   Commit {i}: {analysis.commit_hash[:8]}")
            print(f"   Author: {analysis.author}")
            print(f"   Date: {analysis.commit_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Message: {analysis.message[:50]}{'...' if len(analysis.message) > 50 else ''}")
            print(f"   Files: {len(analysis.files_changed)} changed (+{analysis.total_additions}/-{analysis.total_deletions})")
    
    # 성능 지표
    if summary['total_commits_analyzed'] > 0:
        avg_time = summary['execution_time_seconds'] / summary['total_commits_analyzed']
        print(f"\n📈 Performance Metrics:")
        print(f"   Average time per commit: {avg_time:.2f}s")
        
        if summary['total_tests_generated'] > 0:
            avg_test_time = summary['execution_time_seconds'] / summary['total_tests_generated']
            print(f"   Average time per test: {avg_test_time:.2f}s")
    
    print("\n" + "="*50)


def print_usage_help():
    """사용법 도움말"""
    print("""
🤖 AI Test Generator

A tool for generating automated tests from VCS (Version Control System) changes.

Quick Start:
  1. Analyze local Git repo:     python run.py git ./my-repo
  2. Analyze remote Git repo:    python run.py remote https://github.com/user/repo.git
  3. Run examples:               python run.py example local
  4. Run tests:                  python run.py test unit

For detailed help:
  python run.py --help
  python run.py git --help
  python run.py remote --help

Configuration:
  - Set environment variables in .env file
  - Required: Azure OpenAI credentials
  - Optional: Azure AI Search credentials for RAG
    """)


async def main():
    """메인 함수"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    if not args.command:
        print_usage_help()
        return
    
    # 로그 설정
    log_level = getattr(args, 'log_level', 'INFO')
    log_file = getattr(args, 'log_file', None)
    setup_logger(log_level, log_file)
    
    try:
        if args.command == 'git':
            await run_git_analysis(args)
        elif args.command == 'remote':
            await run_remote_analysis(args)
        elif args.command == 'example':
            await run_examples(args)
        elif args.command == 'test':
            await run_tests(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        logger = get_logger()
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        
        # 디버그 정보 (verbose 모드에서만)
        if getattr(args, 'verbose', False):
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())