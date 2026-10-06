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
  [string]$LicenseServer = "https://license.blocklab.co.kr",  # 라이선스 서버(HTTPS). IP 직결(:8005)은 구버전 호환용으로만 남아 있다
  # 동봉 런타임(Python·Node·Chromium·node_modules)을 다시 만들지 않고 재사용한다.
  # 이 2.3GB 는 코드를 고쳐도 한 바이트도 안 바뀌는데 매번 다시 만드느라 40분이 들었다.
  # 업데이트 패치를 만들 때는 항상 이 스위치를 쓴다.
  [switch]$SkipRuntime,
  # 설치본에 찍을 버전. 업데이트 패키지 버전과 반드시 같아야 한다.
  [string]$Version = "1.0.0"
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
# 증분 빌드면 runtime\ 과 mbam-web\node_modules 는 남겨두고 나머지만 지운다.
$webNodeModules = Join-Path $Payload "mbam-web"
$webNodeModules = Join-Path $webNodeModules "node_modules"
if (Test-Path $Payload) {
  if ($SkipRuntime) {
    Write-Host "== 증분 빌드: runtime·node_modules 재사용 ==" -ForegroundColor Magenta
    if (-not (Test-Path $Runtime)) { throw "재사용할 runtime 이 없습니다. -SkipRuntime 없이 한 번 전체 빌드하세요." }
    Get-ChildItem $Payload -Force | Where-Object { $_.Name -ne "runtime" } | ForEach-Object {
      if ($_.Name -eq "mbam-web") {
        Get-ChildItem $_.FullName -Force | Where-Object { $_.Name -ne "node_modules" } |
          Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
      } else {
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      }
    }
  } else {
    Remove-Item $Payload -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $Payload, $Cache, $Runtime | Out-Null

function Get-File($url, $out) {
  if (Test-Path $out) { Write-Host "  (캐시) $out"; return }
  Write-Host "  다운로드: $url"
  Invoke-WebRequest -Uri $url -OutFile $out
}

# ── 1. 앱 소스 복사 (불필요한 것 제외) ─────────────────────
Write-Host "[1/6] 앱 소스 복사..." -ForegroundColor Yellow
# mbam-web 은 2단계에서 빌드 후 별도 복사하므로 여기선 제외
# ⚠ robocopy /XD 에 '전체 경로'를 주면 그 경로 하나만 제외된다(=최상위만). 이름만 주면
#   트리 어디에 있든 같은 이름의 폴더가 전부 제외된다. profiles/sessions 는 최상위가 아니라
#   mbam_nextgen\ 아래에 생기므로 반드시 '이름'으로 제외해야 한다.
#   (mbam_nextgen\profiles 에는 네이버 계정별 로그인 쿠키·세션이 들어 있다 — 고객 설치본에
#    들어가면 빌드 PC 의 계정이 그대로 넘어간다. 절대 포함 금지)
$exDirsAnywhere = @(
    "profiles",              # 네이버 계정 로그인 프로필(쿠키·세션) — 유출 금지
    "sessions",              # 세션 캐시
    "venv", ".git", ".claude", "node_modules", "__pycache__", ".next",
    "logs", "scratch", "tests", "cafe_dom_dumps",
    "temp_images", "temp_clips", "temp_uploaded_images",
    "generated_images", "saved_images"
)
# 최상위에서만 제외할 것들(같은 이름이 하위에 또 있어도 지우면 안 되는 경우)
# ⚠ naver_place_crawler 는 7GB 다. 어차피 아래 1-b 에서 지워지지만, 복사부터 하면
#   그것만으로 10분 넘게 걸린다(실측). 애초에 복사하지 않는다.
$exDirsTop = @("installer","auth_server","mbam-web","db_backup_20260621",
               "naver_place_crawler","nodejs_qa_crawler","chrome_extension",
               "docs","build","dist","_startup_backup")
# 개발 산출물/덤프 제외 (prompts.json 등 *.json 은 유지해야 하므로 통째 제외 금지)
#
# ⚠ *.db 를 반드시 제외한다. 백엔드 DB(seo_history.db)에는 등록된 네이버 계정(비밀번호)·
#   API 키(app_settings)·광고주 정보가 들어 있다. 이걸 동봉하면 모든 고객이 빌드 PC 의
#   계정과 API 키로 프로그램을 시작하게 된다. DB 는 첫 실행 때 새로 만들어지므로 넣을 필요가 없다.
# ⚠ user_settings.json 에도 빌드 PC 의 계정 목록이 들어 있다.
# ⚠ my-key.pem / deploy_aws_update.bat 은 운영 서버 배포용 키·스크립트다.
$exFiles = @("agent_config.json", ".env", "user_settings.json",
             "*.db",
             "my-key.pem", "deploy_aws_update.bat",
             "*.log","*.pyc","crash*.txt","crash*.log","*.zip","*.exe","test_*.py",
             "*.html","*_dump.*","screenshot*.png","map_screenshot.png","naver_shopping.png",
             "cli_test.json","crawler_test_*.json","graphql_responses.json","debug_*.json")
$rcArgs = @($Src, (Join-Path $Payload "."), "/E", "/NFL","/NDL","/NJH","/NJS","/NP")
foreach ($d in $exDirsAnywhere) { $rcArgs += @("/XD", $d) }                    # 이름 → 어느 깊이든 제외
foreach ($d in $exDirsTop)      { $rcArgs += @("/XD", (Join-Path $Src $d)) }   # 최상위만 제외
foreach ($f in $exFiles) { $rcArgs += @("/XF", $f) }
# robocopy 종료코드 0~7 은 정상
& robocopy @rcArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 실패(code $LASTEXITCODE)" }

# ── 1-b. 최상위 정리 — 실행에 쓰지 않는 것은 전부 뺀다 ──────────────
# 위 복사는 '블랙리스트' 방식이라, 저장소 루트에 새로 생긴 개발용 파일이 자동으로
# 고객 설치본까지 따라간다. 실제로 루트에 .py 만 137개가 있고 대부분 1회용 스크립트다
# (fix_*.py, dump_*.py, patch*.py …). update_keys.py 처럼 앱 키가 코드에 박혀 있는 것도 있고,
# docs\ 에는 개발일지·대화기록이, .claude\ 에는 작업 메모가 들어 있다.
# 최상위만 화이트리스트로 다시 걸러낸다. 하위 폴더(mbam_nextgen 등)는 건드리지 않는다.
#   ※ mbam-web·runtime 은 뒤 단계에서 만들어지므로 이 시점엔 없지만, keep 에 함께 둔다.
$keepFiles = @(
    "mbam_launcher.py", "mbam_auth_gate.py",   # 런처 (mbam.iss 가 직접 실행)
    "run_backend.py",                           # 런처가 백엔드를 이걸로 띄운다
    "agent.py", "agent_startup.vbs",            # 웹 관제 에이전트 (설치 시 자동시작 등록)
    "mbam.ico",
    "license_config.json", "version.json",      # 인증 서버 주소 / 버전
    "package.json", "package-lock.json",
    "requirements.txt"
)
$keepDirs = @("mbam_nextgen", "licensing", "mbam-web", "runtime")

$dropped = 0
Get-ChildItem $Payload -File -Force | Where-Object { $keepFiles -notcontains $_.Name } | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue; $dropped++
}
Get-ChildItem $Payload -Directory -Force | Where-Object { $keepDirs -notcontains $_.Name } | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue; $dropped++
}
Write-Host "  최상위 개발용 파일 $dropped 개 제외" -ForegroundColor DarkGray

# 안전장치 — 계정 정보가 페이로드에 섞여 들어갔으면 즉시 중단한다.
# (제외 규칙이 나중에 잘못 수정돼도 고객 설치본에 로그인 정보가 나가는 일은 막는다)
# 검사 범위는 '앱 소스'로 한정한다. runtime\ 과 node_modules\ 는 레지스트리에서 받아온
# 제3자 트리라 빌드 PC 의 데이터가 섞일 수 없고, anthropic SDK 의 resources\beta\sessions
# 같은 정상 모듈이 'sessions' 로 오탐된다.
$notVendor = { $_.FullName -notmatch '\\(runtime|node_modules)\\' }
foreach ($leak in @("profiles", "sessions")) {
    $found = Get-ChildItem $Payload -Directory -Recurse -Filter $leak -ErrorAction SilentlyContinue |
             Where-Object $notVendor
    if ($found) { throw "페이로드에 '$leak' 폴더가 포함됐습니다($($found[0].FullName)). 계정 로그인 정보가 유출될 수 있어 빌드를 중단합니다." }
}
foreach ($pat in @("*.db", ".env", "agent_config.json", "user_settings.json", "my-key.pem")) {
    $found = Get-ChildItem $Payload -File -Recurse -Filter $pat -Force -ErrorAction SilentlyContinue |
             Where-Object $notVendor
    if ($found) { throw "페이로드에 '$pat' 가 포함됐습니다($($found[0].FullName)). 계정·API키가 유출될 수 있어 빌드를 중단합니다." }
}

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
$webItems = @(".next","public","package.json","package-lock.json")
if ($SkipRuntime -and (Test-Path $webNodeModules)) {
  Write-Host "  (재사용) mbam-web node_modules — 복사 생략" -ForegroundColor DarkGray
} else {
  $webItems += "node_modules"
}
foreach ($item in $webItems) {
  $p = Join-Path $webSrc $item
  if (Test-Path $p) { & robocopy $p (Join-Path $webDst $item) /E /NFL /NDL /NJH /NJS /NP | Out-Null }
}
foreach ($cfg in (Get-ChildItem $webSrc -Filter "next.config.*" -ErrorAction SilentlyContinue)) {
  Copy-Item $cfg.FullName $webDst
}

# ── 3. 동봉 Python (python-build-standalone, tkinter 포함, 재배치 가능) ──
if ($SkipRuntime) {
Write-Host "[3/6] 동봉 Python — 재사용(건너뜀)" -ForegroundColor DarkGray
} else {
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
}

# ── 3-b. 동봉 런타임 네이티브 의존성 보정 ───────────────────
# 동봉 Python 은 C 런타임(vcruntime140*)만 들어 있고 C++ 런타임(msvcp140.dll)이 없다.
# greenlet(=playwright.async_api 가 import)·numpy·pandas·pyarrow 가 이걸 요구하는데,
# 빌드 PC 에는 System32 에 있어서 문제가 드러나지 않고 VC++ 재배포 패키지가 없는
# 깨끗한 Windows(고객 PC)에서만 백엔드가 통째로 죽는다. 실제로 그렇게 나갔다.
#   ImportError: DLL load failed while importing _greenlet: 지정된 모듈을 찾을 수 없습니다
# ⚠ -SkipRuntime 분기 '밖'에 둔다 — 증분 빌드는 예전 runtime\ 을 그대로 재사용하므로
#   분기 안에 두면 결함이 있는 런타임이 그대로 설치본에 실린다.
Write-Host "[3-b/6] 동봉 런타임 네이티브 의존성 점검..." -ForegroundColor Yellow
. (Join-Path $Here "native_runtime.ps1")
$PyDir = Join-Path $Runtime "python"
$PyExe = Join-Path $PyDir "python.exe"          # -SkipRuntime 이면 위 분기에서 설정되지 않는다
Repair-BundledNativeRuntime $PyDir
Copy-NativeFixPayload $PyDir $Payload      # 예전 설치본을 업데이트로 고치기 위한 복구용 사본
# 보정 결과를 실제 import 로 확인한다. 이게 통과해야 고객 PC 에서 백엔드가 뜬다.
$nativeOut = & $PyExe -c "import playwright.async_api,greenlet;print('NATIVE_OK')" 2>&1
if ($nativeOut -notmatch "NATIVE_OK") {
    throw "네이티브 확장모듈 로드 실패 — 이대로 배포하면 고객 PC 에서 백엔드가 뜨지 않습니다.`n$nativeOut"
}
Write-Host "  네이티브 확장모듈 정상" -ForegroundColor Green

# ── 4. 동봉 Node (portable) ────────────────────────────────
if ($SkipRuntime) {
Write-Host "[4/6] 동봉 Node — 재사용(건너뜀)" -ForegroundColor DarkGray
} else {
Write-Host "[4/6] 동봉 Node 준비..." -ForegroundColor Yellow
$nodeZip = Join-Path $Cache "node-v$NodeVersion-win-x64.zip"
Get-File "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" $nodeZip
$nodeTmp = Join-Path $Cache "node_extract"
if (Test-Path $nodeTmp) { Remove-Item $nodeTmp -Recurse -Force }
Expand-Archive $nodeZip -DestinationPath $nodeTmp -Force
Move-Item (Join-Path $nodeTmp "node-v$NodeVersion-win-x64") (Join-Path $Runtime "node")
}

# ── 5. 라이선스 서버 설정 파일 ─────────────────────────────
Write-Host "[5/6] license_config.json 작성..." -ForegroundColor Yellow
@{ server = $LicenseServer } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "license_config.json")

# 설치본이 자기 버전을 알아야 업데이트 확인이 된다. 없으면 런처가 버전을 0 으로 보고 매번 다시 묻는다.
@{ version = $Version; product = "mbam"; built_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") } |
  ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "version.json")
Write-Host "  version.json = $Version" -ForegroundColor Green

# 선택: 아이콘 동봉
if (Test-Path (Join-Path $Here "mbam.ico")) { Copy-Item (Join-Path $Here "mbam.ico") $Payload }

# ── 6. 마무리 ──────────────────────────────────────────────
Write-Host "[6/6] 완료. payload 준비됨." -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령으로 설치파일을 컴파일하세요:" -ForegroundColor Cyan
Write-Host '  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" mbam.iss'
Write-Host ""
Write-Host "※ 배포 전 license_config.json 의 server 주소가 실제 라이선스 서버인지 확인하세요." -ForegroundColor Yellow
