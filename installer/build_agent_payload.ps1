# ============================================================
#  MBAM "웹 관제 에이전트" 전용 설치 페이로드 빌드 (Windows PowerShell)
#  - 동봉 Python(tkinter 포함) + mbam_nextgen 코드 + agent.py + Chromium 만 모읍니다.
#  - 프론트엔드/Node/로컬 백엔드/라이선스는 제외 (에이전트는 클라우드 로그인으로 동작).
#
#  사용:
#    cd "...\마케팅 프로그램\installer"
#    powershell -ExecutionPolicy Bypass -File build_agent_payload.ps1
#
#  이후:  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" agent.iss
#
#  필요: 인터넷 연결(동봉 Python/Chromium 다운로드). Node/프론트 빌드 불필요.
# ============================================================
param(
  [string]$PythonVersion = "3.12.8",
  [string]$PbsTag        = "20241219"    # python-build-standalone 릴리스 태그
)

$ErrorActionPreference = "Stop"
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src     = Split-Path -Parent $Here                 # 앱 루트(마케팅 프로그램)
$Payload = Join-Path $Here "payload_agent"
$Cache   = Join-Path $Here ".cache"
$Runtime = Join-Path $Payload "runtime"

Write-Host "== MBAM 에이전트 페이로드 빌드 ==" -ForegroundColor Cyan
Write-Host "Src     = $Src"
Write-Host "Payload = $Payload"

# ── 0. 초기화 ──────────────────────────────────────────────
if (Test-Path $Payload) { Remove-Item $Payload -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Payload, $Cache, $Runtime | Out-Null

function Get-File($url, $out) {
  if (Test-Path $out) { Write-Host "  (캐시) $out"; return }
  Write-Host "  다운로드: $url"
  Invoke-WebRequest -Uri $url -OutFile $out
}

# ── 1. 앱 소스 복사 (에이전트에 필요한 것만; 프론트/무거운 산출물 제외) ─────
Write-Host "[1/4] 앱 소스 복사..." -ForegroundColor Yellow
# mbam-web(프론트), node, venv, git, 개발 산출물 등은 에이전트에 불필요 → 제외
# 어느 깊이에서든 '이름'으로 제외 — mbam_nextgen 내부의 profiles(운영자 로그인 세션!)·임시·생성물까지 확실히 배제
$exDirsAny = @("__pycache__",".git","node_modules",".next",
               "profiles","sessions","logs","scratch",
               "saved_images","generated_images","temp_images","temp_uploaded_images","temp_clips",
               "db_backup_20260621")
# 루트 특정 폴더만 제외
$exDirsRoot = @("venv","installer","auth_server","mbam-web","tests",
                "nodejs_qa_crawler","chrome_extension","naver_place_crawler",
                "build","dist","docs","output","payload","payload_agent")
# 운영자 계정/키/DB/무관 산출물(크롤러 설치본 등)은 고객 설치본에 절대 포함 금지
$exFiles = @("agent_config.json", ".env",
             "*.db","*.zip","*.log","*.pyc","*.spec",
             "CrawlerPro*.exe","*_Setup*.exe","관리자_승인도구.exe",
             "crash*.txt","crash*.log","test_*.py","test_image.*","editor_fail*.png",
             "analysis_pattern_output.txt","*.html","*_dump.*",
             "screenshot*.png","map_screenshot.png","naver_shopping.png",
             "cli_test.json","crawler_test_*.json","graphql_responses.json","debug_*.json")
$rcArgs = @($Src, (Join-Path $Payload "."), "/E", "/NFL","/NDL","/NJH","/NJS","/NP")
foreach ($d in $exDirsAny)  { $rcArgs += @("/XD", $d) }                    # 이름 매칭(모든 깊이)
foreach ($d in $exDirsRoot) { $rcArgs += @("/XD", (Join-Path $Src $d)) }   # 루트 경로 매칭
foreach ($f in $exFiles)    { $rcArgs += @("/XF", $f) }
& robocopy @rcArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 실패(code $LASTEXITCODE)" }

# 에이전트 실행에 꼭 필요한 진입 파일 존재 확인
foreach ($f in @("agent.py","agent_startup.vbs","requirements.txt")) {
  if (-not (Test-Path (Join-Path $Payload $f))) { throw "필수 파일 누락: $f (Src 에서 복사 실패)" }
}

# ── 2. 동봉 Python (python-build-standalone, tkinter 포함, 재배치 가능) ──
Write-Host "[2/4] 동봉 Python 준비..." -ForegroundColor Yellow
$pyArchive = Join-Path $Cache "python-$PythonVersion-$PbsTag.tar.gz"
$pyUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/cpython-$PythonVersion+$PbsTag-x86_64-pc-windows-msvc-install_only.tar.gz"
Get-File $pyUrl $pyArchive
$pyTmp = Join-Path $Cache "py_extract_agent"
if (Test-Path $pyTmp) { Remove-Item $pyTmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyTmp | Out-Null
tar -xzf $pyArchive -C $pyTmp
Move-Item (Join-Path $pyTmp "python") (Join-Path $Runtime "python")
$PyExe = Join-Path $Runtime "python\python.exe"

Write-Host "  파이썬 패키지 설치(requirements.txt)..."
& $PyExe -m pip install --upgrade pip
& $PyExe -m pip install -r (Join-Path $Src "requirements.txt")
& $PyExe -m pip install playwright

# ── 3. Chromium(Playwright) 동봉 ───────────────────────────
Write-Host "[3/4] Chromium(Playwright) 설치..." -ForegroundColor Yellow
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $Runtime "ms-playwright")
& $PyExe -m playwright install chromium

# 선택: 아이콘 동봉
if (Test-Path (Join-Path $Here "mbam.ico")) { Copy-Item (Join-Path $Here "mbam.ico") $Payload }

# ── 4. 마무리 ──────────────────────────────────────────────
Write-Host "[4/4] 완료. payload_agent 준비됨." -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령으로 에이전트 설치파일을 컴파일하세요:" -ForegroundColor Cyan
Write-Host '  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" agent.iss'
