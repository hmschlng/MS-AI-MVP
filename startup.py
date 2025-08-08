#!/usr/bin/env python3
"""
Azure App Service용 Python 시작 스크립트
"""
import os
import sys
import subprocess
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """메인 실행 함수"""
    try:
        # 환경변수에서 포트 번호 가져오기 (Azure App Service 기본값)
        port = os.environ.get('PORT', '8000')
        
        print(f"Starting Streamlit on port {port}")
        print(f"Working directory: {os.getcwd()}")
        print(f"Python path: {sys.path}")
        
        # Streamlit 실행 (Azure App Service 최적화)
        cmd = [
            sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.port", port,
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false"
        ]
        
        print(f"Executing command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()