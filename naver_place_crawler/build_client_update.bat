@echo off
chcp 65001 >nul
echo [클라이언트 업데이트 진행] 크롤러 실행 파일 빌드를 시작합니다...
echo.

cd /d "%~dp0"
python -m PyInstaller -y "Crawler Pro.spec"

if %errorlevel% neq 0 (
    echo.
    echo [오류] PyInstaller 빌드에 실패했습니다.
    exit /b %errorlevel%
)

echo.
echo [설치파일 생성] 배포용 Setup 파일을 생성합니다...
"C:\Users\blocklabs02\AppData\Local\Programs\Inno Setup 6\ISCC.exe" setup_script.iss

if %errorlevel% neq 0 (
    echo.
    echo [오류] 설치파일(Setup) 생성에 실패했습니다.
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo 완료! Output 폴더에 새로운 CrawlerPro_Setup.exe 가 생성되었습니다!
echo ========================================================
