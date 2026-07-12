import os
import subprocess
import platform

def build_executable():
    system = platform.system()
    print(f"[{system}] 환경에서 단일 실행 파일 빌드를 시작합니다...")
    
    # OS별 빌드 설정
    if system == "Windows":
        name = "CrawlerPro"
    elif system == "Darwin":
        name = "CrawlerPro_Mac"
    else:
        name = "CrawlerPro_App"

    # PyInstaller 명령어 구성
    # --noconsole: 실행 시 시꺼먼 콘솔창(cmd/터미널)을 띄우지 않음 (GUI 전용)
    # --onefile: 하나의 파일로 모든 의존성을 압축함
    # --clean: 빌드 전 기존 캐시 정리
    command = [
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        f"--name={name}",
        "gui_main.py"
    ]
    
    try:
        subprocess.run(command, check=True)
        print("\n✅ 빌드가 성공적으로 완료되었습니다!")
        
        # 결과물 경로 표시
        if system == "Windows":
            result_file = f"{name}.exe"
        elif system == "Darwin":
            result_file = f"{name}.app (또는 유닉스 실행파일 {name})"
        else:
            result_file = name
            
        print(f"실행 파일 위치: {os.path.join(os.getcwd(), 'dist', result_file)}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 빌드 중 오류가 발생했습니다: {e}")
    except FileNotFoundError:
        print("\n❌ PyInstaller를 찾을 수 없습니다. 'pip install pyinstaller'를 먼저 실행해주세요.")

if __name__ == "__main__":
    build_executable()
