"""
AI Test Generator CLI Interface

테스트 코드 자동 생성 도구의 명령줄 인터페이스
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
import logging
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.logging import RichHandler
from dotenv import load_dotenv

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai_test_generator.core.git_analyzer import GitAnalyzer, CommitAnalysis
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import setup_logger

# Rich console for pretty output
console = Console()

# 환경 변수 로드
load_dotenv()


@click.group()
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Set the logging level'
)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Path to configuration file'
)
@click.pass_context
def cli(ctx, log_level, config):
    """AI Test Generator - 테스트 코드 자동 생성 도구"""
    # 로깅 설정
    setup_logger(log_level)
    
    # 설정 로드
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config(config_file=config) if config else Config()
    
    console.print(
        "[bold blue]AI Test Generator[/bold blue] - 테스트 코드 자동 생성 도구",
        style="bold"
    )


@cli.command()
@click.pass_context
def check_config(ctx):
    """환경 설정 확인"""
    console.print("\n[bold]환경 설정 확인[/bold]")
    
    # 필수 환경 변수 확인
    required_vars = [
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_API_KEY',
        'AZURE_SEARCH_ENDPOINT',
        'AZURE_SEARCH_API_KEY'
    ]
    
    table = Table(title="환경 변수 상태")
    table.add_column("변수명", style="cyan")
    table.add_column("상태", style="green")
    table.add_column("값", style="yellow")
    
    all_configured = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # API 키는 일부만 표시
            if 'KEY' in var or 'TOKEN' in var:
                display_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            else:
                display_value = value
            status = "[green]✓[/green]"
        else:
            display_value = "미설정"
            status = "[red]✗[/red]"
            all_configured = False
        
        table.add_row(var, status, display_value)
    
    console.print(table)
    
    if all_configured:
        console.print("\n[green]✓[/green] 모든 환경 변수가 올바르게 설정되었습니다.")
    else:
        console.print("\n[red]✗[/red] 일부 환경 변수가 설정되지 않았습니다.")
        console.print("   .env 파일을 확인하거나 환경 변수를 설정해주세요.")


def main():
    """메인 엔트리포인트"""
    cli()


if __name__ == "__main__":
    main()
