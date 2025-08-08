#!/usr/bin/env python3
"""
Pipeline Stages Integration Test

실제 LLM과 통신하여 파이프라인 단계별 동작을 테스트합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from ai_test_generator.core.pipeline_stages import (
    PipelineOrchestrator, PipelineContext, PipelineStage,
    StageStatus, VCSAnalysisStage, TestStrategyStage
)
from ai_test_generator.utils.config import Config
from ai_test_generator.utils.logger import get_logger

logger = get_logger(__name__)


def progress_callback(stage: str, progress: float, message: str):
    """진행상황 콜백"""
    print(f"[{stage}] {progress:.1%} - {message}")


def user_confirmation_callback(prompt: str, data: dict) -> bool:
    """사용자 확인 콜백"""
    print(f"\n{prompt}")
    print(f"데이터: {data}")
    response = input("계속 진행하시겠습니까? (y/n): ").lower().strip()
    return response in ['y', 'yes', '예']


async def test_vcs_analysis_stage():
    """VCS 분석 단계 테스트"""
    print("\n" + "="*60)
    print("VCS Analysis Stage 테스트")
    print("="*60)
    
    try:
        config = Config()
        
        # 현재 프로젝트 저장소를 사용
        context = PipelineContext(
            repo_path=str(project_root),
            progress_callback=progress_callback
        )
        
        # VCS 분석 단계 실행
        vcs_stage = VCSAnalysisStage()
        result = await vcs_stage.execute(context)
        
        print(f"상태: {result.status}")
        print(f"실행 시간: {result.execution_time:.2f}초")
        print(f"데이터 키: {list(result.data.keys())}")
        
        if result.errors:
            print(f"오류: {result.errors}")
        if result.warnings:
            print(f"경고: {result.warnings}")
        
        if result.status == StageStatus.COMPLETED:
            # 분석된 커밋 정보 출력
            if 'commit_analyses' in result.data:
                analyses = result.data['commit_analyses']
                print(f"분석된 커밋 수: {len(analyses)}")
                for i, analysis in enumerate(analyses[:3]):  # 처음 3개만 출력
                    print(f"  {i+1}. {analysis.commit_hash[:8]} - {analysis.message[:50]}...")
        
        return result
        
    except Exception as e:
        print(f"VCS 분석 테스트 실패: {e}")
        return None


async def test_strategy_stage(vcs_result):
    """전략 결정 단계 테스트"""
    print("\n" + "="*60)
    print("Test Strategy Stage 테스트")
    print("="*60)
    
    try:
        config = Config()
        
        # 설정 유효성 검증
        validation_errors = config.validate()
        if validation_errors:
            print(f"설정 오류: {validation_errors}")
            return None
        
        context = PipelineContext(
            repo_path=str(project_root),
            progress_callback=progress_callback,
            user_confirmation_callback=user_confirmation_callback
        )
        context.vcs_analysis_result = vcs_result
        
        # 전략 결정 단계 실행
        strategy_stage = TestStrategyStage(config)
        result = await strategy_stage.execute(context)
        
        print(f"상태: {result.status}")
        print(f"실행 시간: {result.execution_time:.2f}초")
        print(f"데이터 키: {list(result.data.keys())}")
        
        if result.errors:
            print(f"오류: {result.errors}")
        if result.warnings:
            print(f"경고: {result.warnings}")
        
        if result.status == StageStatus.COMPLETED:
            # 결정된 전략 출력
            strategies = result.data.get('test_strategies', [])
            print(f"결정된 전략: {strategies}")
            
            if result.test_strategies:
                print(f"TestStrategy 객체들: {[str(ts) for ts in result.test_strategies]}")
        
        return result
        
    except Exception as e:
        print(f"전략 결정 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_single_stage(stage_name: PipelineStage, config: Config, context: PipelineContext):
    """단일 스테이지 테스트"""
    print(f"\n테스트 중: {stage_name.value}")
    
    orchestrator = PipelineOrchestrator(config)
    result = await orchestrator.execute_single_stage(stage_name, context)
    
    print(f"  상태: {result.status}")
    print(f"  실행 시간: {result.execution_time:.2f}초")
    print(f"  오류 수: {len(result.errors)}")
    print(f"  경고 수: {len(result.warnings)}")
    
    if result.errors:
        print(f"  오류: {result.errors}")
    
    return result


async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    print("\n" + "="*60)
    print("Full Pipeline 테스트")
    print("="*60)
    
    try:
        config = Config()
        
        # 설정 유효성 검증
        validation_errors = config.validate()
        if validation_errors:
            print(f"설정 오류가 있어 일부 단계는 실행되지 않을 수 있습니다: {validation_errors}")
        
        context = PipelineContext(
            repo_path=str(project_root),
            progress_callback=progress_callback,
            user_confirmation_callback=user_confirmation_callback
        )
        
        orchestrator = PipelineOrchestrator(config)
        
        # 첫 번째 단계(VCS 분석)만 실행
        print("VCS 분석 단계만 실행...")
        vcs_stages = [PipelineStage.VCS_ANALYSIS]
        results = await orchestrator.execute_pipeline(context, vcs_stages)
        
        # 결과 출력
        for stage, result in results.items():
            print(f"\n{stage.value}: {result.status}")
            if result.execution_time:
                print(f"  실행 시간: {result.execution_time:.2f}초")
            if result.errors:
                print(f"  오류: {result.errors}")
            if result.warnings:
                print(f"  경고: {result.warnings}")
        
        # LLM 설정이 올바른 경우 전략 단계도 실행
        if not validation_errors:
            print("\n전략 결정 단계 추가 실행...")
            strategy_stages = [PipelineStage.TEST_STRATEGY]
            strategy_results = await orchestrator.execute_pipeline(context, strategy_stages)
            
            for stage, result in strategy_results.items():
                print(f"\n{stage.value}: {result.status}")
                if result.execution_time:
                    print(f"  실행 시간: {result.execution_time:.2f}초")
                if result.errors:
                    print(f"  오류: {result.errors}")
                if result.warnings:
                    print(f"  경고: {result.warnings}")
        
        # 진행상황 확인
        all_results = {**results, **(strategy_results if not validation_errors else {})}
        progress = orchestrator.get_pipeline_progress(all_results)
        print(f"\n전체 진행상황: {progress}")
        
        return all_results
        
    except Exception as e:
        print(f"전체 파이프라인 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """메인 테스트 함수"""
    print("Pipeline Stages Integration Test 시작")
    print(f"프로젝트 경로: {project_root}")
    
    # 1. VCS 분석 단계만 먼저 테스트
    vcs_result = await test_vcs_analysis_stage()
    
    if vcs_result and vcs_result.status == StageStatus.COMPLETED:
        # 2. 전략 결정 단계 테스트 (LLM 통신 필요)
        strategy_result = await test_strategy_stage(vcs_result)
        
        if strategy_result:
            print("\n개별 단계 테스트 완료!")
    
    # 3. 전체 파이프라인 테스트
    await test_full_pipeline()
    
    print("\n" + "="*60)
    print("모든 테스트 완료!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())