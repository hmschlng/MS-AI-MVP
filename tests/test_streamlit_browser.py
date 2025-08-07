"""
Streamlit 앱 브라우저 자동화 테스트
"""
import time
import asyncio
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_streamlit_app_manually():
    """수동 테스트를 위한 인터페이스"""
    print("🌐 Streamlit 앱 브라우저 테스트")
    print("=" * 50)
    
    print("📍 앱 주소: http://localhost:8521")
    print("")
    
    print("🧪 테스트 시나리오:")
    print("1. 메인 페이지 접근")
    print("2. 저장소 설정 (로컬 저장소)")
    print("3. 커밋 선택")
    print("4. 파이프라인 실행")
    print("5. 결과 확인")
    print("")
    
    # 사용자 입력을 받아가며 단계별 테스트
    input("Enter를 눌러 테스트를 시작하세요...")
    
    # 1단계: 메인 페이지 접근
    print("\n=== 1단계: 메인 페이지 접근 ===")
    print("브라우저에서 http://localhost:8521 을 열어주세요")
    print("다음을 확인해주세요:")
    print("- 페이지 제목: 'AI 테스트 생성기'")
    print("- 사이드바 메뉴: 저장소 설정, 커밋 선택, 파이프라인 실행, 결과 및 내보내기")
    print("- 현재 페이지: '저장소 설정'")
    
    result = input("메인 페이지가 정상적으로 표시되나요? (y/n): ").lower()
    if result != 'y':
        print("❌ 메인 페이지 테스트 실패")
        return False
    print("✅ 메인 페이지 테스트 통과")
    
    # 2단계: 저장소 설정
    print("\n=== 2단계: 저장소 설정 ===")
    print("'로컬 저장소' 옵션이 선택되어 있는지 확인")
    current_path = Path.cwd()
    print(f"저장소 경로에 다음을 입력: {current_path}")
    print("브랜치: main (또는 현재 브랜치)")
    print("'로컬 저장소 연결' 버튼 클릭")
    
    print("예상 결과:")
    print("- Git 설정 최적화 알림 (이미 설정되어 있으면 바로 연결)")
    print("- '로컬 저장소 연결 성공!' 메시지")
    print("- 저장소 정보 표시 (브랜치 수, 최근 커밋 등)")
    
    result = input("저장소 연결이 성공했나요? (y/n): ").lower()
    if result != 'y':
        print("❌ 저장소 설정 테스트 실패")
        return False
    print("✅ 저장소 설정 테스트 통과")
    
    # 3단계: 커밋 선택
    print("\n=== 3단계: 커밋 선택 ===")
    print("사이드바에서 '커밋 선택' 메뉴 클릭")
    print("다음을 확인해주세요:")
    print("- 커밋 리스트가 표시됨")
    print("- 필터 옵션들 (Max Commits, Exclude Test Commits 등)")
    print("- 각 커밋의 해시, 메시지, 작성자, 날짜 표시")
    
    print("테스트 작업:")
    print("1. 하나 이상의 커밋을 선택 (체크박스)")
    print("2. Action을 'Analyze Selected'로 선택")
    print("3. 'Execute Action' 버튼 클릭")
    
    print("예상 결과:")
    print("- 선택된 커밋 분석 완료 메시지")
    print("- 'Combined Changes Preview' 섹션 표시")
    print("- '파이프라인 실행으로 이동' 안내 메시지")
    
    result = input("커밋 선택 및 분석이 성공했나요? (y/n): ").lower()
    if result != 'y':
        print("❌ 커밋 선택 테스트 실패")
        return False
    print("✅ 커밋 선택 테스트 통과")
    
    # 4단계: 파이프라인 실행 (가장 중요)
    print("\n=== 4단계: 파이프라인 실행 ===")
    print("사이드바에서 '파이프라인 실행' 메뉴 클릭")
    print("다음을 확인해주세요:")
    print("- Pipeline Configuration 섹션")
    print("- 선택된 커밋 수 표시")
    print("- Stages to Execute: 모든 단계가 선택된 상태")
    print("- Execution Mode: 'Full Pipeline' 또는 'Stage by Stage'")
    
    mode = input("어떤 실행 모드를 테스트하시겠습니까? (full/stage): ").lower()
    
    if mode == "full":
        print("\n--- Full Pipeline 테스트 ---")
        print("'Full Pipeline' 선택 후 'Start Pipeline Execution' 클릭")
        print("예상 동작:")
        print("- '파이프라인 실행 중...' 메시지")
        print("- 진행상황 모니터링 섹션 표시")
        print("- 각 스테이지별 실행 결과")
        print("- 완료시 성공/실패 메시지")
        
        # Azure OpenAI 설정이 필요할 수 있음
        print("\n⚠️  주의사항:")
        print("- Azure OpenAI API 키가 필요합니다")
        print("- 실제 LLM 호출이 발생하므로 비용이 발생할 수 있습니다")
        
        proceed = input("실제로 파이프라인을 실행하시겠습니까? (y/n): ").lower()
        if proceed == 'y':
            result = input("파이프라인 실행이 완료되었나요? (y/n/error): ").lower()
            if result == 'error':
                error_msg = input("어떤 오류가 발생했나요? ")
                print(f"❌ 파이프라인 실행 오류: {error_msg}")
                return False
            elif result != 'y':
                print("❌ 파이프라인 실행 실패")
                return False
            print("✅ Full Pipeline 테스트 통과")
        else:
            print("⏭️  Full Pipeline 테스트 건너뜀")
    
    else:
        print("\n--- Stage by Stage 테스트 ---")
        print("'Stage by Stage' 선택 후 'Start Pipeline Execution' 클릭")
        print("각 스테이지를 하나씩 실행:")
        print("1. VCS Analysis")
        print("2. Test Strategy") 
        print("3. Test Code Generation")
        print("4. Test Scenario Generation")
        print("5. Review Generation")
        
        for i, stage in enumerate(['VCS Analysis', 'Test Strategy', 'Test Code Generation', 'Test Scenario Generation', 'Review Generation'], 1):
            print(f"\n--- Stage {i}: {stage} ---")
            result = input(f"{stage} 실행이 성공했나요? (y/n/skip): ").lower()
            if result == 'n':
                error_msg = input("어떤 오류가 발생했나요? ")
                print(f"❌ {stage} 실행 오류: {error_msg}")
                return False
            elif result == 'skip':
                print(f"⏭️  {stage} 테스트 건너뜀")
                break
            else:
                print(f"✅ {stage} 테스트 통과")
    
    # 5단계: 결과 확인
    print("\n=== 5단계: 결과 및 내보내기 ===")
    print("사이드바에서 '결과 및 내보내기' 메뉴 클릭")
    print("다음을 확인해주세요:")
    print("- Results Summary (통계 카드들)")
    print("- Detailed Results 탭들:")
    print("  - Test Code: 생성된 테스트 코드")
    print("  - Test Scenarios: 생성된 테스트 시나리오")
    print("  - Analysis Results: 분석 결과")
    print("  - Export Options: 내보내기 옵션")
    
    result = input("결과 페이지가 정상적으로 표시되나요? (y/n): ").lower()
    if result != 'y':
        print("❌ 결과 페이지 테스트 실패")
        return False
    print("✅ 결과 페이지 테스트 통과")
    
    # 내보내기 테스트
    export_test = input("내보내기 기능을 테스트하시겠습니까? (y/n): ").lower()
    if export_test == 'y':
        print("Export Options 탭에서:")
        print("- JSON, Excel 형식 선택")
        print("- 'Export Results' 버튼 클릭")
        print("- 다운로드 링크 확인")
        
        result = input("내보내기가 성공했나요? (y/n): ").lower()
        if result != 'y':
            print("❌ 내보내기 테스트 실패")
            return False
        print("✅ 내보내기 테스트 통과")
    
    print("\n" + "=" * 50)
    print("🎉 모든 브라우저 테스트가 완료되었습니다!")
    print("=" * 50)
    
    return True

def main():
    """메인 함수"""
    try:
        success = test_streamlit_app_manually()
        if success:
            print("\n✅ 전체 테스트 성공!")
        else:
            print("\n❌ 일부 테스트 실패")
    except KeyboardInterrupt:
        print("\n\n⚠️  테스트가 중단되었습니다")
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    main()