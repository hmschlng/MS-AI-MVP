#!/usr/bin/env python3
"""
AI Test Generator - Project Runner

프로젝트의 다양한 실행 옵션을 제공하는 통합 실행 스크립트
"""
import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Legacy imports removed - now using Pipeline system only
from ai_test_generator.core.commit_selector import CommitSelector
from ai_test_generator.core.pipeline_stages import PipelineOrchestrator, PipelineContext, PipelineStage
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import setup_logger, get_logger


def setup_argument_parser() -> argparse.ArgumentParser:
    """명령행 인자 파서 설정"""
    parser = argparse.ArgumentParser(
        description="AI Test Generator - Automated test generation from VCS changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive commit selection (recommended)
  python run.py interactive ./my-repo --max-commits 20
  python run.py interactive https://github.com/user/repo.git --max-commits 20

  # Pipeline execution with specific commits
  python run.py pipeline ./my-repo --commits abc123 def456 789ghi
  python run.py pipeline https://github.com/user/repo.git --commits abc123 def456

  # Launch Streamlit web interface
  python run.py ui --port 8501

  # Quick Git analysis (auto-selects recent commits)
  python run.py git ./my-repo --max-commits 10

  # Quick remote Git analysis
  python run.py remote https://github.com/user/repo.git --max-commits 10

  # Run examples
  python run.py example local

  # Run tests
  python run.py test unit
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Simple Git analysis command (Pipeline-based)
    git_parser = subparsers.add_parser('git', help='Quick Git repository analysis (uses latest commits)')
    git_parser.add_argument('repo_path', help='Path to Git repository')
    git_parser.add_argument('--branch', help='Branch to analyze (default: current branch)')
    git_parser.add_argument('--max-commits', type=int, default=10, help='Maximum commits to analyze (default: 10)')
    
    # 새로운 대화형 Git 분석 명령
    interactive_parser = subparsers.add_parser('interactive', help='Interactive Git repository analysis')
    interactive_parser.add_argument('repo_source', help='Path to local Git repository or remote URL')
    interactive_parser.add_argument('--branch', help='Branch to analyze (default: current branch)')
    interactive_parser.add_argument('--max-commits', type=int, default=50, help='Maximum commits to show (default: 50)')
    interactive_parser.add_argument('--exclude-test-commits', action='store_true', default=True, help='Exclude test commits')
    
    # 파이프라인 실행 명령
    pipeline_parser = subparsers.add_parser('pipeline', help='Execute pipeline with selected commits')
    pipeline_parser.add_argument('repo_source', help='Path to local Git repository or remote URL')
    pipeline_parser.add_argument('--commits', nargs='+', required=True, help='Commit hashes to analyze')
    pipeline_parser.add_argument('--branch', help='Branch to analyze (default: current branch)')
    pipeline_parser.add_argument('--stages', nargs='+', choices=['vcs_analysis', 'test_strategy', 'test_code_generation', 'test_scenario_generation', 'review_generation'], help='Pipeline stages to run')
    
    # Streamlit UI 시작 명령
    ui_parser = subparsers.add_parser('ui', help='Launch Streamlit web interface')
    ui_parser.add_argument('--port', type=int, default=8501, help='Port for Streamlit app (default: 8501)')
    
    # Simple remote Git analysis command (Pipeline-based)  
    remote_parser = subparsers.add_parser('remote', help='Quick remote Git repository analysis')
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
    
    # 공통 인자 - git과 remote도 포함하여 Pipeline 기반으로 통일
    for p in [git_parser, remote_parser, interactive_parser, pipeline_parser]:
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
    """Git 분석 실행 (Pipeline 기반)"""
    logger = get_logger()
    
    if not Path(args.repo_path).exists():
        print(f"❌ Error: Repository path does not exist: {args.repo_path}")
        return
    
    try:
        if not args.quiet:
            print(f"🔍 Quick Git repository analysis: {args.repo_path}")
            print(f"   Branch: {args.branch or 'current'}")
            print(f"   Max commits: {args.max_commits}")
        
        # CommitSelector를 통한 최신 커밋 자동 선택
        commit_selector = CommitSelector(args.repo_path, args.branch or "main")
        recent_commits = commit_selector.get_commit_list(
            max_commits=args.max_commits,
            exclude_test_commits=True
        )
        
        if not recent_commits:
            print("❌ No commits found to analyze")
            return
        
        # 최신 커밋들을 자동 선택
        selected_commit_hashes = [commit.hash for commit in recent_commits[:min(5, len(recent_commits))]]
        
        if not args.quiet:
            print(f"📝 Auto-selected {len(selected_commit_hashes)} recent commits for analysis")
        
        # Pipeline으로 처리
        await run_pipeline_for_commits(args, selected_commit_hashes)
        
    except Exception as e:
        logger.error(f"Git analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")


async def run_remote_analysis(args) -> None:
    """원격 저장소 분석 실행 (Pipeline 기반)"""
    logger = get_logger()
    temp_path = None
    
    try:
        if not args.quiet:
            print(f"🌐 Quick remote repository analysis: {args.remote_url}")
            print(f"   Branch: {args.branch or 'default'}")
            print(f"   Max commits: {args.max_commits}")
        
        # 원격 저장소 클론
        from ai_test_generator.core.git_analyzer import GitAnalyzer
        temp_path = GitAnalyzer.clone_remote_repo(args.remote_url, branch=args.branch)
        
        if not args.quiet:
            print(f"📁 Repository cloned to: {temp_path}")
        
        # CommitSelector를 통한 최신 커밋 자동 선택
        commit_selector = CommitSelector(temp_path, args.branch or "main")
        recent_commits = commit_selector.get_commit_list(
            max_commits=args.max_commits,
            exclude_test_commits=True
        )
        
        if not recent_commits:
            print("❌ No commits found to analyze")
            return
        
        # 최신 커밋들을 자동 선택
        selected_commit_hashes = [commit.hash for commit in recent_commits[:min(5, len(recent_commits))]]
        
        if not args.quiet:
            print(f"📝 Auto-selected {len(selected_commit_hashes)} recent commits for analysis")
        
        # repo_path를 임시 경로로 설정하여 Pipeline 처리
        args.repo_path = temp_path
        await run_pipeline_for_commits(args, selected_commit_hashes)
        
    except Exception as e:
        logger.error(f"Remote analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
    
    finally:
        # 임시 디렉토리 정리
        if temp_path:
            try:
                import shutil
                if Path(temp_path).exists():
                    shutil.rmtree(temp_path)
                    if not args.quiet:
                        print(f"🧹 Cleaned up temporary directory")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


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


def is_remote_url(repo_source: str) -> bool:
    """저장소 경로가 원격 URL인지 확인"""
    return repo_source.startswith(('http://', 'https://', 'git@', 'ssh://'))


async def setup_repository_access(repo_source: str, branch: str = None) -> tuple[CommitSelector, str, bool]:
    """저장소 접근 설정 (로컬/원격 자동 판별)"""
    is_remote = is_remote_url(repo_source)
    temp_path = None
    
    if is_remote:
        print(f"🌐 Cloning remote repository: {repo_source}")
        print("   This may take a few moments...")
        
        from ai_test_generator.core.git_analyzer import GitAnalyzer
        temp_path = GitAnalyzer.clone_remote_repo(repo_source, branch=branch)
        repo_path = temp_path
        print(f"✅ Repository cloned to: {temp_path}")
    else:
        if not Path(repo_source).exists():
            raise ValueError(f"Repository path does not exist: {repo_source}")
        repo_path = repo_source
    
    commit_selector = CommitSelector(repo_path, branch or "main")
    return commit_selector, repo_path, is_remote


async def run_interactive_analysis(args) -> None:
    """대화형 Git 분석 실행"""
    logger = get_logger()
    
    try:
        # 저장소 설정 (로컬/원격 자동 판별)
        commit_selector, repo_path, is_remote = await setup_repository_access(
            args.repo_source, args.branch
        )
        
        repo_display = args.repo_source if is_remote else repo_path
        print(f"🔍 Interactive analysis for: {repo_display}")
        print(f"   Type: {'Remote' if is_remote else 'Local'}")
        print(f"   Branch: {args.branch or 'current'}")
        print(f"   Max commits: {args.max_commits}")
        print()
        
        # 커밋 리스트 조회
        commits = commit_selector.get_commit_list(
            max_commits=args.max_commits,
            exclude_test_commits=args.exclude_test_commits
        )
        
        if not commits:
            print("❌ No commits found")
            return
        
        # 커밋 리스트 표시
        print("📋 Available commits:")
        print("-" * 100)
        print(f"{'No.':<4} {'Hash':<10} {'Message':<50} {'Author':<15} {'Date':<12} {'Files':<6}")
        print("-" * 100)
        
        for i, commit in enumerate(commits):
            message = commit.message[:47] + "..." if len(commit.message) > 50 else commit.message
            author = commit.author.split()[0] if commit.author else "Unknown"
            date_str = commit.date.strftime("%m-%d %H:%M")
            test_indicator = " 🧪" if commit.is_test_commit else ""
            
            print(f"{i+1:<4} {commit.short_hash:<10} {message:<50} {author:<15} {date_str:<12} {len(commit.files_changed):<6}{test_indicator}")
        
        print("-" * 100)
        print()
        
        # 사용자 입력 받기
        while True:
            selection = input("Select commits (e.g., 1,3,5 or 1-5 or 'all' or 'q' to quit): ").strip()
            
            if selection.lower() in ['q', 'quit', 'exit']:
                print("👋 Goodbye!")
                return
            
            try:
                selected_indices = parse_selection(selection, len(commits))
                if not selected_indices:
                    print("❌ Invalid selection. Please try again.")
                    continue
                
                selected_commits = [commits[i] for i in selected_indices]
                
                # 선택된 커밋들 표시
                print(f"\n✅ Selected {len(selected_commits)} commits:")
                for commit in selected_commits:
                    print(f"   • {commit.short_hash}: {commit.message[:50]}")
                
                # 확인 받기
                confirm = input("\nProceed with analysis? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    # 파이프라인 실행 (repo_path를 실제 경로로 업데이트)
                    args.repo_path = repo_path
                    await run_pipeline_for_commits(args, [c.hash for c in selected_commits])
                    break
                else:
                    print("Operation cancelled.")
                    continue
                
            except ValueError as e:
                print(f"❌ Invalid input: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Interactive analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
    
    finally:
        # 임시 디렉토리 정리 (원격 저장소인 경우)
        if 'is_remote' in locals() and is_remote and 'repo_path' in locals():
            try:
                import shutil
                if Path(repo_path).exists():
                    shutil.rmtree(repo_path)
                    print(f"🧹 Cleaned up temporary directory: {repo_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


def parse_selection(selection: str, max_count: int) -> List[int]:
    """사용자 선택 입력 파싱"""
    if selection.lower() == 'all':
        return list(range(max_count))
    
    indices = []
    parts = selection.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # 범위 선택 (예: 1-5)
            try:
                start, end = map(int, part.split('-'))
                start = max(1, start)
                end = min(max_count, end)
                indices.extend(range(start-1, end))
            except ValueError:
                raise ValueError(f"Invalid range: {part}")
        else:
            # 단일 선택
            try:
                idx = int(part)
                if 1 <= idx <= max_count:
                    indices.append(idx - 1)
                else:
                    raise ValueError(f"Index {idx} out of range (1-{max_count})")
            except ValueError:
                raise ValueError(f"Invalid number: {part}")
    
    return sorted(list(set(indices)))


async def run_pipeline_for_commits(args, commit_hashes: List[str]) -> None:
    """선택된 커밋들에 대한 파이프라인 실행"""
    try:
        config = Config()
        
        # 출력 디렉토리 설정
        if args.output:
            import os
            os.environ['OUTPUT_DIRECTORY'] = args.output
        
        # 프로젝트 정보 구성
        project_info = {}
        if args.project_name:
            project_info['project_name'] = args.project_name
        if args.project_version:
            project_info['version'] = args.project_version
        if args.tester:
            project_info['tester'] = args.tester
        
        # CommitSelector로 통합 변경사항 계산
        commit_selector = CommitSelector(args.repo_path, args.branch or "main")
        combined_changes = commit_selector.calculate_combined_changes(commit_hashes)
        
        # 파이프라인 컨텍스트 생성
        context = PipelineContext(
            config=config,
            repo_path=args.repo_path,
            selected_commits=commit_hashes,
            combined_changes=combined_changes,
            project_info=project_info or None,
            progress_callback=print_progress,
            user_confirmation_callback=lambda title, data: True
        )
        
        # 파이프라인 오케스트레이터 초기화
        orchestrator = PipelineOrchestrator(config)
        
        print(f"\n🚀 Starting pipeline for {len(commit_hashes)} commits...")
        print(f"   Combined changes: {combined_changes['summary']['total_files']} files, +{combined_changes['summary']['total_additions']}/-{combined_changes['summary']['total_deletions']}")
        print()
        
        # 파이프라인 실행
        results = await orchestrator.execute_pipeline(context)
        
        # 결과 출력
        await print_pipeline_results(results, args.quiet, args.verbose)
        
    except Exception as e:
        print(f"❌ Pipeline execution failed: {e}")


def print_progress(stage: str, progress: float, message: str):
    """진행상황 출력"""
    print(f"[{stage.upper()}] {progress:.1%}: {message}")


async def run_pipeline_command(args) -> None:
    """파이프라인 명령 실행"""
    logger = get_logger()
    
    try:
        # 저장소 설정 (로컬/원격 자동 판별)
        commit_selector, repo_path, is_remote = await setup_repository_access(
            args.repo_source, args.branch
        )
        
        # 단계 선택
        if args.stages:
            stages = [PipelineStage(stage) for stage in args.stages]
        else:
            stages = None  # 모든 단계 실행
        
        repo_display = args.repo_source if is_remote else repo_path
        print(f"🔄 Running pipeline for: {repo_display}")
        print(f"   Type: {'Remote' if is_remote else 'Local'}")
        print(f"   Selected commits: {args.commits}")
        if stages:
            print(f"   Stages: {[stage.value for stage in stages]}")
        else:
            print("   Stages: All stages")
        
        # repo_path를 실제 경로로 업데이트
        args.repo_path = repo_path
        await run_pipeline_for_commits(args, args.commits)
        
    except Exception as e:
        logger.error(f"Pipeline command failed: {e}")
        print(f"❌ Command failed: {e}")
    
    finally:
        # 임시 디렉토리 정리 (원격 저장소인 경우)
        if 'is_remote' in locals() and is_remote and 'repo_path' in locals():
            try:
                import shutil
                if Path(repo_path).exists():
                    shutil.rmtree(repo_path)
                    print(f"🧹 Cleaned up temporary directory: {repo_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")


async def run_ui_command(args) -> None:
    """Streamlit UI 시작"""
    try:
        import subprocess
        import os
        
        # streamlit_app.py 경로 확인
        app_path = Path(__file__).parent / "streamlit_app.py"
        
        if not app_path.exists():
            print(f"❌ Error: Streamlit app not found at {app_path}")
            return
        
        print(f"🌐 Starting Streamlit UI on port {args.port}...")
        print(f"   App will be available at: http://localhost:{args.port}")
        print("   Press Ctrl+C to stop the server")
        
        # Streamlit 실행
        cmd = [
            "streamlit", "run", str(app_path),
            "--server.port", str(args.port),
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ]
        
        # UTF-8 환경변수 설정
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        subprocess.run(cmd, env=env, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Streamlit: {e}")
        print("Make sure Streamlit is installed: pip install streamlit")
    except KeyboardInterrupt:
        print("\n👋 UI stopped by user")
    except Exception as e:
        print(f"❌ UI command failed: {e}")


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


async def print_pipeline_results(results: Dict, quiet: bool = False, verbose: bool = False) -> None:
    """파이프라인 결과 출력"""
    if not results:
        print("❌ No results to display")
        return
    
    # 통계 계산
    completed_stages = sum(1 for r in results.values() if r.status.value == 'completed')
    failed_stages = sum(1 for r in results.values() if r.status.value == 'failed')
    total_stages = len(results)
    
    total_tests = 0
    total_scenarios = 0
    total_execution_time = 0
    all_errors = []
    all_warnings = []
    
    for result in results.values():
        if hasattr(result, 'execution_time') and result.execution_time:
            total_execution_time += result.execution_time
        if hasattr(result, 'errors'):
            all_errors.extend(result.errors)
        if hasattr(result, 'warnings'):
            all_warnings.extend(result.warnings)
        if hasattr(result, 'data') and result.data:
            if 'generated_tests' in result.data:
                total_tests += len(result.data['generated_tests'])
            if 'test_scenarios' in result.data:
                total_scenarios += len(result.data['test_scenarios'])
    
    if quiet:
        status = "✅ Success" if failed_stages == 0 else f"⚠️ Partial ({failed_stages} failed)"
        print(f"{status} | Stages: {completed_stages}/{total_stages} | Tests: {total_tests} | Scenarios: {total_scenarios} | Time: {total_execution_time:.1f}s")
        return
    
    print("\n" + "="*60)
    print("📊 PIPELINE EXECUTION RESULTS")
    print("="*60)
    
    # 전체 통계
    print(f"🔄 Pipeline Stages: {completed_stages}/{total_stages} completed")
    print(f"🧪 Generated Tests: {total_tests}")
    print(f"📋 Test Scenarios: {total_scenarios}")
    print(f"⏱️ Total Execution Time: {total_execution_time:.2f} seconds")
    
    if failed_stages == 0:
        print("✅ Status: All stages completed successfully")
    else:
        print(f"⚠️ Status: {failed_stages} stage(s) failed")
    
    # 단계별 상세 결과
    print(f"\n📝 Stage Details:")
    print("-" * 60)
    
    stage_order = ['vcs_analysis', 'test_strategy', 'test_code_generation', 'test_scenario_generation', 'review_generation']
    
    for stage_name in stage_order:
        stage_enum = None
        for stage_key in results.keys():
            if stage_key.value == stage_name:
                stage_enum = stage_key
                break
        
        if stage_enum and stage_enum in results:
            result = results[stage_enum]
            status_icon = "✅" if result.status.value == 'completed' else "❌" if result.status.value == 'failed' else "⏸️"
            stage_display = stage_name.replace('_', ' ').title()
            exec_time = f"{result.execution_time:.2f}s" if hasattr(result, 'execution_time') and result.execution_time else "N/A"
            
            print(f"{status_icon} {stage_display:<25} | Time: {exec_time:<8} | Status: {result.status.value}")
            
            if verbose and hasattr(result, 'data') and result.data:
                for key, value in result.data.items():
                    if isinstance(value, list):
                        print(f"     └─ {key}: {len(value)} items")
                    elif isinstance(value, dict):
                        print(f"     └─ {key}: {len(value)} keys")
        else:
            print(f"⏸️ {stage_name.replace('_', ' ').title():<25} | Time: N/A      | Status: not executed")
    
    # 에러 및 경고 표시
    if all_errors:
        print(f"\n❌ Errors ({len(all_errors)}):")
        for i, error in enumerate(all_errors[:5 if not verbose else None]):
            print(f"   {i+1}. {error}")
        if len(all_errors) > 5 and not verbose:
            print(f"   ... and {len(all_errors) - 5} more errors (use --verbose for full list)")
    
    if all_warnings:
        print(f"\n⚠️ Warnings ({len(all_warnings)}):")
        for i, warning in enumerate(all_warnings[:3 if not verbose else None]):
            print(f"   {i+1}. {warning}")
        if len(all_warnings) > 3 and not verbose:
            print(f"   ... and {len(all_warnings) - 3} more warnings (use --verbose for full list)")
    
    # 성능 지표
    if total_stages > 0 and total_execution_time > 0:
        avg_time_per_stage = total_execution_time / completed_stages if completed_stages > 0 else 0
        print(f"\n📈 Performance:")
        print(f"   Average time per stage: {avg_time_per_stage:.2f}s")
        if total_tests > 0:
            avg_time_per_test = total_execution_time / total_tests
            print(f"   Average time per test: {avg_time_per_test:.2f}s")
    
    print("\n" + "="*60)


# Legacy print_results function removed - now using Pipeline system with print_pipeline_results


def print_usage_help():
    """사용법 도움말"""
    print("""
🤖 AI Test Generator

A tool for generating automated tests from VCS (Version Control System) changes.
Supports both local repositories and remote Git repositories.

Quick Start:
  1. 🌐 Launch Web UI (Recommended):    python run.py ui
  2. 💬 Interactive analysis:           python run.py interactive ./my-repo
                                        python run.py interactive https://github.com/user/repo.git
  3. ⚡ Direct pipeline execution:       python run.py pipeline ./my-repo --commits abc123 def456
  4. 📊 Quick Git analysis:             python run.py git ./my-repo

🌐 Web Interface:
  - Full-featured web UI with commit selection
  - Real-time progress monitoring
  - Visual results and export options

💬 Interactive CLI:
  - Browse commits in terminal
  - Select specific commits for analysis
  - Step-by-step guidance

⚡ Direct Pipeline:
  - Execute with specific commit hashes
  - Scriptable for automation
  - Customizable pipeline stages

For detailed help:
  python run.py --help
  python run.py interactive --help
  python run.py pipeline --help

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
    log_level = getattr(args, 'log_level', 'DEBUG')
    log_file = getattr(args, 'log_file', None)
    setup_logger(log_level, log_file)
    
    try:
        if args.command == 'git':
            await run_git_analysis(args)
        elif args.command == 'remote':
            await run_remote_analysis(args)
        elif args.command == 'interactive':
            await run_interactive_analysis(args)
        elif args.command == 'pipeline':
            await run_pipeline_command(args)
        elif args.command == 'ui':
            await run_ui_command(args)
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