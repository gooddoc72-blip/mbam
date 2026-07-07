# ============================================================
#  MBAM 설치 페이로드 빌드 스크립트 (Windows PowerShell)
#  - 동봉 Python(tkinter 포함, 재배치 가능) + 동봉 Node + 빌드된 프론트 + Chromium 을
#    installer\payload\ 에 모읍니다. 이후 ISCC 로 mbam.iss 를 컴파일하면 설치파일 완성.
#
#  사용:
#    cd "...\마케팅 프로그램\installer"
#    powershell -ExecutionPolicy Bypass -File build_payload.ps1
#
#  필요: 인터넷 연결(런타임 다운로드), Node/npm 은 빌드 PC 에 설치돼 있어야 함(프론트 빌드용)
# ============================================================
param(
  [string]$PythonVersion = "3.12.8",
  [string]$PbsTag        = "20241219",   # python-build-standalone 릴리스 태그
  [string]$NodeVersion   = "20.18.1",
  [string]$LicenseServer = "http://CHANGE-ME.example.com:8005"  # 실제 라이선스 서버 주소로 교체
)

$ErrorActionPreference = "Stop"
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src     = Split-Path -Parent $Here                 # 앱 루트(마케팅 프로그램)
$Payload = Join-Path $Here "payload"
$Cache   = Join-Path $Here ".cache"
$Runtime = Join-Path $Payload "runtime"

Write-Host "== MBAM 페이로드 빌드 ==" -ForegroundColor Cyan
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

# ── 1. 앱 소스 복사 (불필요한 것 제외) ─────────────────────
Write-Host "[1/6] 앱 소스 복사..." -ForegroundColor Yellow
# mbam-web 은 2단계에서 빌드 후 별도 복사하므로 여기선 제외
$exDirs = @("venv",".git","installer","auth_server","mbam-web","node_modules","__pycache__",
            ".next","db_backup_20260621","saved_images","temp_uploaded_images",
            "temp_images","temp_clips","sessions","logs","generated_images","scratch","tests",
            "node_modules","nodejs_qa_crawler","chrome_extension")
# 개발 산출물/덤프 제외 (prompts.json 등 *.json 은 유지해야 하므로 통째 제외 금지)
# agent_config.json: 빌드 PC(운영자)의 로그인 계정이 고객 설치본에 들어가면 안 됨 — 반드시 제외
$exFiles = @("agent_config.json",
             "*.log","*.pyc","crash*.txt","crash*.log","*.zip","test_*.py",
             "*.html","*_dump.*","screenshot*.png","map_screenshot.png","naver_shopping.png",
             "cli_test.json","crawler_test_*.json","graphql_responses.json","debug_*.json")
$rcArgs = @($Src, (Join-Path $Payload "."), "/E", "/NFL","/NDL","/NJH","/NJS","/NP")
foreach ($d in $exDirs)  { $rcArgs += @("/XD", (Join-Path $Src $d)) }
foreach ($f in $exFiles) { $rcArgs += @("/XF", $f) }
# robocopy 종료코드 0~7 은 정상
& robocopy @rcArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 실패(code $LASTEXITCODE)" }

# mbam-web 의 node_modules 는 별도 빌드 후 production 만 가져오므로 여기선 제외됨(위 /XD node_modules)

# ── 2. 프론트엔드 빌드 ─────────────────────────────────────
Write-Host "[2/6] 프론트엔드(Next.js) 빌드..." -ForegroundColor Yellow
$webSrc = Join-Path $Src "mbam-web"
Push-Location $webSrc
if (-not (Test-Path (Join-Path $webSrc "node_modules"))) { npm ci }
npm run build
Pop-Location
# 빌드 산출물 + 런타임 의존성 복사
$webDst = Join-Path $Payload "mbam-web"
New-Item -ItemType Directory -Force -Path $webDst | Out-Null
foreach ($item in @(".next","public","package.json","package-lock.json","node_modules")) {
  $p = Join-Path $webSrc $item
  if (Test-Path $p) { & robocopy $p (Join-Path $webDst $item) /E /NFL /NDL /NJH /NJS /NP | Out-Null }
}
foreach ($cfg in (Get-ChildItem $webSrc -Filter "next.config.*" -ErrorAction SilentlyContinue)) {
  Copy-Item $cfg.FullName $webDst
}

# ── 3. 동봉 Python (python-build-standalone, tkinter 포함, 재배치 가능) ──
Write-Host "[3/6] 동봉 Python 준비..." -ForegroundColor Yellow
$pyArchive = Join-Path $Cache "python-$PythonVersion-$PbsTag.tar.gz"
$pyUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/cpython-$PythonVersion+$PbsTag-x86_64-pc-windows-msvc-install_only.tar.gz"
Get-File $pyUrl $pyArchive
$pyTmp = Join-Path $Cache "py_extract"
if (Test-Path $pyTmp) { Remove-Item $pyTmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyTmp | Out-Null
tar -xzf $pyArchive -C $pyTmp
# 압축은 python\ 폴더로 풀림 → runtime\python 으로 이동
Move-Item (Join-Path $pyTmp "python") (Join-Path $Runtime "python")
$PyExe = Join-Path $Runtime "python\python.exe"

Write-Host "  파이썬 패키지 설치..."
& $PyExe -m pip install --upgrade pip
& $PyExe -m pip install -r (Join-Path $Src "requirements.txt")
& $PyExe -m pip install playwright

Write-Host "  Chromium(Playwright) 설치..."
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $Runtime "ms-playwright")
& $PyExe -m playwright install chromium

# ── 4. 동봉 Node (portable) ────────────────────────────────
Write-Host "[4/6] 동봉 Node 준비..." -ForegroundColor Yellow
$nodeZip = Join-Path $Cache "node-v$NodeVersion-win-x64.zip"
Get-File "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" $nodeZip
$nodeTmp = Join-Path $Cache "node_extract"
if (Test-Path $nodeTmp) { Remove-Item $nodeTmp -Recurse -Force }
Expand-Archive $nodeZip -DestinationPath $nodeTmp -Force
Move-Item (Join-Path $nodeTmp "node-v$NodeVersion-win-x64") (Join-Path $Runtime "node")

# ── 5. 라이선스 서버 설정 파일 ─────────────────────────────
Write-Host "[5/6] license_config.json 작성..." -ForegroundColor Yellow
@{ server = $LicenseServer } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "license_config.json")

# 선택: 아이콘 동봉
if (Test-Path (Join-Path $Here "mbam.ico")) { Copy-Item (Join-Path $Here "mbam.ico") $Payload }

# ── 6. 마무리 ──────────────────────────────────────────────
Write-Host "[6/6] 완료. payload 준비됨." -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령으로 설치파일을 컴파일하세요:" -ForegroundColor Cyan
Write-Host '  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" mbam.iss'
Write-Host ""
Write-Host "※ 배포 전 license_config.json 의 server 주소가 실제 라이선스 서버인지 확인하세요." -ForegroundColor Yellow
