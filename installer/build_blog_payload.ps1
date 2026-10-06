# ============================================================
#  블로그 마케팅 프로그램 — 설치 페이로드 빌드 (Windows PowerShell)
#
#  풀버전(build_payload.ps1)과 다른 점
#    - 프론트를 NEXT_PUBLIC_PRODUCT=blog / BACKEND_URL=127.0.0.1:8020 으로 빌드
#    - 블로그와 무관한 page 폴더를 스테이징 사본에서 삭제하고 빌드 → 설치본에 아예 없음
#    - 런처가 blog_launcher.py (포트 8020/3020, 크롤러와 같은 기기 승인 인증)
#    - 웹 관제 에이전트(agent.py) 미동봉 — 단독 로컬 사용 제품
#
#  사용:
#    cd "...\01 마케팅 연구소\installer"
#    powershell -ExecutionPolicy Bypass -File build_blog_payload.ps1
#
#  필요: 인터넷 연결(런타임 다운로드), 빌드 PC 에 Node/npm 설치(프론트 빌드용)
# ============================================================
param(
  [string]$PythonVersion = "3.12.8",
  [string]$PbsTag        = "20241219",   # python-build-standalone 릴리스 태그
  [string]$NodeVersion   = "20.18.1",
  [string]$LicenseServer = "https://license.blocklab.co.kr",
  [int]   $BackendPort   = 8020,         # blog_launcher.py 의 BACKEND_PORT 와 반드시 동일
  # 설치본/업데이트 버전. blog.iss 의 MyAppVersion 과 같은 값을 쓴다.
  # 이 값이 version.json 으로 설치본에 들어가고, 런처가 서버 버전과 비교한다.
  [string]$Version       = "1.0.0",
  # 코드만 고쳤을 때 쓰는 증분 빌드. 페이로드 2.4GB 중 약 2.35GB(동봉 Python·Chromium·
  # Node·node_modules)는 코드를 고쳐도 한 바이트도 바뀌지 않는데, 기본 동작은 매번
  # 페이로드를 통째로 지우고 이걸 다시 받아 설치한다. 이 스위치는 그걸 재사용해
  # 20분대 → 4분대로 줄인다.
  # ⚠ requirements.txt / package.json 을 바꿨거나 고객 배포본을 만들 때는 쓰지 말 것.
  [switch]$SkipRuntime
)

$ErrorActionPreference = "Stop"
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src     = Split-Path -Parent $Here                 # 앱 루트(01 마케팅 연구소)
$Payload = Join-Path $Here "payload_blog"
$Cache   = Join-Path $Here ".cache"
$Runtime = Join-Path $Payload "runtime"
$WebStage = Join-Path $Cache "blog_web_stage"       # 프론트 빌드용 임시 사본

Write-Host "== 블로그 전용판 페이로드 빌드 ==" -ForegroundColor Cyan
Write-Host "Src     = $Src"
Write-Host "Payload = $Payload"

# ── 0. 초기화 ──────────────────────────────────────────────
# 기본은 전체 재빌드(페이로드를 통째로 지움). -SkipRuntime 이면 코드로 바뀌지 않는
# runtime\ 과 mbam-web\node_modules 만 남기고, 갈아끼울 것은 전부 지운다.
# (robocopy 로 덮어쓰기만 하면 이번 빌드에서 '빠진' 파일이 이전 것 그대로 남는다.
#  글감수집처럼 화면을 제거한 경우 그 잔재가 설치본에 실리므로 반드시 지우고 채운다)
if ($SkipRuntime) {
  if (-not (Test-Path $Runtime)) {
    throw "-SkipRuntime 은 이전 빌드의 runtime\ 이 있어야 합니다. 처음 한 번은 스위치 없이 실행하세요."
  }
  Write-Host "== 증분 빌드: runtime·node_modules 재사용 ==" -ForegroundColor Cyan
  Get-ChildItem $Payload -Force | Where-Object { $_.Name -notin @("runtime", "mbam-web") } |
    Remove-Item -Recurse -Force
  $webKeep = Join-Path $Payload "mbam-web"
  if (Test-Path $webKeep) {
    Get-ChildItem $webKeep -Force | Where-Object { $_.Name -ne "node_modules" } |
      Remove-Item -Recurse -Force
  }
} else {
  if (Test-Path $Payload) { Remove-Item $Payload -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path $Payload, $Cache, $Runtime | Out-Null

function Get-File($url, $out) {
  if (Test-Path $out) { Write-Host "  (캐시) $out"; return }
  Write-Host "  다운로드: $url"
  Invoke-WebRequest -Uri $url -OutFile $out
}

# ── 1. 앱 소스 복사 (불필요한 것 제외) ─────────────────────
Write-Host "[1/7] 앱 소스 복사..." -ForegroundColor Yellow
# ⚠ robocopy /XD 에 '전체 경로'를 주면 그 경로 하나만 제외된다. 이름만 주면 트리 어디에 있든
#   같은 이름의 폴더가 전부 제외된다. profiles/sessions 같은 건 최상위가 아니라
#   mbam_nextgen\ 아래에 생기므로 반드시 '이름'으로 제외해야 한다.
#   (mbam_nextgen\profiles 에는 네이버 계정별 로그인 세션이 들어 있다 — 고객 설치본에
#    들어가면 빌드 PC 의 계정이 그대로 넘어간다. 절대 포함 금지)
$exDirsAnywhere = @(
    "profiles",              # 네이버 계정 로그인 프로필 (쿠키·세션) — 유출 금지
    "sessions",              # 세션 캐시
    "venv", ".git", "node_modules", "__pycache__", ".next",
    "logs", "scratch", "tests",
    "temp_images", "temp_clips", "temp_uploaded_images",
    "generated_images", "saved_images"
)
# 최상위에서만 제외할 것들(같은 이름이 하위에 또 있어도 지우면 안 되는 경우)
$exDirsTop = @("installer","auth_server","mbam-web","db_backup_20260621",
               "nodejs_qa_crawler","chrome_extension","naver_place_crawler",
               "build","dist","_startup_backup")
# 개발 산출물/덤프 제외 (prompts.json 등 *.json 은 유지해야 하므로 통째 제외 금지)
# agent_config.json / .env: 빌드 PC(운영자)의 로그인 계정·API 키가 고객 설치본에
# 들어가면 안 됨 — 반드시 제외 (고객 키는 각자 설치 후 [설정]에서 입력)
#
# ⚠ *.db 를 반드시 제외한다. 백엔드 DB(seo_history.db)에는 등록된 네이버 계정(암호화
#   비밀번호)·API 키(app_settings)·광고주 정보가 들어 있다. 이걸 동봉하면 모든 고객이
#   빌드 PC 의 계정과 API 키로 프로그램을 시작하게 된다.
#   DB 는 첫 실행 때 create_all + run_migrations 가 새로 만들므로 동봉할 필요가 없다.
# ⚠ user_settings.json 에도 빌드 PC 의 계정 목록이 들어 있다.
$exFiles = @("agent_config.json", ".env", "user_settings.json",
             "*.db",                                   # 백엔드/캐시 DB 전부 (계정·API키 유출 방지)
             "my-key.pem", "deploy_aws_update.bat",    # 서버 배포용 키/스크립트
             "*.log","*.pyc","crash*.txt","crash*.log","*.zip","*.exe","test_*.py",
             "*.html","*_dump.*","screenshot*.png","map_screenshot.png","naver_shopping.png",
             "cli_test.json","crawler_test_*.json","graphql_responses.json","debug_*.json")
$rcArgs = @($Src, (Join-Path $Payload "."), "/E", "/NFL","/NDL","/NJH","/NJS","/NP")
foreach ($d in $exDirsAnywhere) { $rcArgs += @("/XD", $d) }                    # 이름 → 어느 깊이든 제외
foreach ($d in $exDirsTop)      { $rcArgs += @("/XD", (Join-Path $Src $d)) }   # 최상위만 제외
foreach ($f in $exFiles) { $rcArgs += @("/XF", $f) }
& robocopy @rcArgs | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 실패(code $LASTEXITCODE)" }

# ── 1-b. 최상위 정리 — 블로그 전용판이 쓰지 않는 것은 전부 뺀다 ──────────
# 위 복사는 '블랙리스트' 방식이라, 저장소 루트에 새로 생긴 개발용 파일이 자동으로
# 고객 설치본까지 따라간다. fix_*.py·dump_*.py 같은 1회용 스크립트와
# update_keys.py(카카오 앱 키가 그대로 적혀 있음), 서버 배포용 bat, admin_tool.py 가
# 그대로 들어가면 안 된다. 최상위만 화이트리스트로 다시 걸러낸다.
#   ⚠ 하위 폴더(mbam_nextgen 등)는 건드리지 않는다. mbam-web·runtime 은 뒤 단계에서
#     만들어지므로 이 시점엔 없지만, 나중에 지워지지 않도록 keep 목록에 함께 둔다.
$keepFiles = @(
    "blog_launcher.py", "blog_auth_gate.py",   # 런처 (blog.iss 가 직접 실행)
    "run_backend.py",                           # 런처가 백엔드를 이걸로 띄운다 — 빠지면 실행 불가
    "blog.ico",                                 # 바로가기 아이콘
    "license_config.json", "version.json",      # 인증 서버 주소 / 버전
    "package.json", "package-lock.json",        # 프론트 폴백 실행 시 참조
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
#
# 검사 범위는 '앱 소스'로 한정한다. runtime\(python-build-standalone·PyPI·Chromium·Node)과
# node_modules\(npm)는 레지스트리에서 받아온 제3자 트리라 빌드 PC 의 데이터가 섞일 수 없다.
# 오히려 anthropic SDK 의 resources\beta\sessions 같은 정상 모듈이 'sessions' 로 오탐된다.
# (전체 빌드에서는 이 시점에 runtime\ 이 아직 비어 있어 우연히 드러나지 않았을 뿐이고,
#  -SkipRuntime 은 이걸 남겨두므로 반드시 걸러야 한다)
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

# 단독 로컬 제품이라 웹 관제 에이전트는 동봉하지 않는다.
# mbam_auth_gate.py 는 풀버전의 '인증코드' 창이라 블로그판(기기 승인 방식)에는 쓰이지 않고,
# cafe_launcher.py 는 다른 제품의 런처라 들어갈 이유가 없다.
# (화이트리스트에서 이미 걸러지지만, 목록이 바뀌어도 새지 않도록 여기서 한 번 더 지운다)
foreach ($f in @("agent.py","agent_startup.vbs","agent_config.example.json",
                 "mbam_launcher.py","mbam_auth_gate.py",
                 "cafe_launcher.py","cafe_auth_gate.py")) {
  $p = Join-Path $Payload $f
  if (Test-Path $p) { Remove-Item $p -Force }
}

# ── 2. 프론트 스테이징 — 블로그 외 화면 제거 ──────────────────
# 원본 mbam-web 은 건드리지 않는다(풀버전 개발에 그대로 쓰이므로).
# 사본을 떠서 거기서 블로그와 무관한 page 폴더를 지우고 빌드한다.
Write-Host "[2/7] 프론트 스테이징(블로그 화면만 남기기)..." -ForegroundColor Yellow
$webSrc = Join-Path $Src "mbam-web"
if (Test-Path $WebStage) { Remove-Item $WebStage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $WebStage | Out-Null
& robocopy $webSrc $WebStage /E /NFL /NDL /NJH /NJS /NP /XD ".next" "node_modules" ".claude" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "프론트 스테이징 복사 실패(code $LASTEXITCODE)" }

# node_modules 는 용량이 커서 복사 대신 디렉터리 정션(junction)으로 연결 — 관리자 권한 불필요.
# ⚠ 원본과 node_modules 를 공유하므로, 빌드 중에는 mbam-web 개발 서버(npm run dev)나
#   다른 next 빌드를 돌리지 말 것. 캐시가 겹쳐 빌드가 실패한다.
if (-not (Test-Path (Join-Path $webSrc "node_modules"))) {
  Push-Location $webSrc; npm ci; Pop-Location
}
cmd /c mklink /J "$(Join-Path $WebStage 'node_modules')" "$(Join-Path $webSrc 'node_modules')" | Out-Null
if (-not (Test-Path (Join-Path $WebStage "node_modules"))) { throw "node_modules 정션 생성 실패" }

# 블로그판에서 뺄 화면들 — 사이드바에도 없고 백엔드 라우터도 마운트되지 않는다.
#
# 아래 두 폴더는 메뉴에 없어도 반드시 남긴다 — 지우면 빌드가 깨진다.
#   cafe-analysis : /blog-analysis 가 이 페이지를 channel="blog" 로 재export 한다
#   blog-posting  : /place-blog 가 이 페이지를 그대로 재export 한다
$dropPages = @("dashboard","billing","cafe-auto","cafe-image-wash","content-image-wash",
               "coupang","guide","hospital-blog","place-news","place-seo","seo-analysis",
               "shopping","shopping-partners-blog",
               "login","signup",        # 설치형은 회원가입·로그인 없이 바로 사용
               "next_api")              # 아무 데서도 부르지 않는 옛 라우트. 백엔드 주소가
                                        # 8000 으로 박혀 있어 이 제품(8020)에는 맞지도 않는다.
foreach ($d in $dropPages) {
  $p = Join-Path $WebStage "app\$d"
  if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "  - 제외: app\$d" }
}

# ── 3. 프론트엔드 빌드 (블로그 프로파일) ──────────────────────
Write-Host "[3/7] 프론트엔드(Next.js) 블로그 빌드..." -ForegroundColor Yellow
# NEXT_PUBLIC_PRODUCT 는 번들에 인라인되고, BACKEND_URL 은 rewrites 로
# routes-manifest.json 에 구워진다 → 둘 다 반드시 빌드 시점에 설정해야 한다.
$env:NEXT_PUBLIC_PRODUCT = "blog"
$env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
# 이전 산출물을 지우고 빌드 → 성공 여부를 BUILD_ID 존재로 판정한다.
# ($LASTEXITCODE 는 이 스크립트의 출력을 파일로 리다이렉트하면 npm 의 경고(stderr)를
#  실패로 잡아 거짓 실패를 낸다. 산출물 확인이 확실하다.)
$stageNext = Join-Path $WebStage ".next"
if (Test-Path $stageNext) { Remove-Item $stageNext -Recurse -Force }
Push-Location $WebStage
try { npm run build } finally { Pop-Location }
if (-not (Test-Path (Join-Path $stageNext "BUILD_ID"))) {
    throw "프론트 빌드 실패 — .next\BUILD_ID 가 생성되지 않았습니다. 위 npm 로그를 확인하세요."
}

# 빌드 산출물 + 런타임 의존성 복사 (node_modules 는 정션이 아닌 실제 사본이어야 함)
$webDst = Join-Path $Payload "mbam-web"
New-Item -ItemType Directory -Force -Path $webDst | Out-Null
foreach ($item in @(".next","public","package.json","package-lock.json")) {
  $p = Join-Path $WebStage $item
  if (Test-Path $p) {
    if ((Get-Item $p).PSIsContainer) { & robocopy $p (Join-Path $webDst $item) /E /NFL /NDL /NJH /NJS /NP | Out-Null }
    else { Copy-Item $p $webDst }
  }
}
# node_modules 는 원본에서 직접 복사(스테이징의 정션을 따라가면 안 되므로 원본 경로 사용)
$nmDst = Join-Path $webDst "node_modules"
if ($SkipRuntime -and (Test-Path $nmDst)) {
  Write-Host "  (재사용) mbam-web\node_modules — 약 370MB 복사 생략"
} else {
  & robocopy (Join-Path $webSrc "node_modules") $nmDst /E /NFL /NDL /NJH /NJS /NP | Out-Null
}
foreach ($cfg in (Get-ChildItem $WebStage -Filter "next.config.*" -ErrorAction SilentlyContinue)) {
  Copy-Item $cfg.FullName $webDst
}

# ── 4~5. 동봉 런타임 (Python + Chromium + Node) ─────────────
# 전체 빌드 시간의 대부분이 여기다 — pip 로 1.2GB 설치 + Chromium 675MB + Node 78MB.
# 코드만 고쳤다면 이 산출물은 직전 빌드와 완전히 동일하므로 -SkipRuntime 으로 통째로 건너뛴다.
if ($SkipRuntime) {
Write-Host "[4/7] 동봉 Python — 재사용(건너뜀)" -ForegroundColor DarkGray
Write-Host "[5/7] 동봉 Node   — 재사용(건너뜀)" -ForegroundColor DarkGray
} else {

# ── 4. 동봉 Python (python-build-standalone, tkinter 포함, 재배치 가능) ──
Write-Host "[4/7] 동봉 Python 준비..." -ForegroundColor Yellow
$pyArchive = Join-Path $Cache "python-$PythonVersion-$PbsTag.tar.gz"
$pyUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/cpython-$PythonVersion+$PbsTag-x86_64-pc-windows-msvc-install_only.tar.gz"
Get-File $pyUrl $pyArchive
$pyTmp = Join-Path $Cache "py_extract_blog"
if (Test-Path $pyTmp) { Remove-Item $pyTmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyTmp | Out-Null
tar -xzf $pyArchive -C $pyTmp
Move-Item (Join-Path $pyTmp "python") (Join-Path $Runtime "python")
$PyExe = Join-Path $Runtime "python\python.exe"

Write-Host "  파이썬 패키지 설치..."
& $PyExe -m pip install --upgrade pip

# requirements.txt 는 개발 PC(Python 3.14)에서 뽑은 freeze 목록이라, 동봉 Python($PythonVersion)
# 에 설치할 수 없는 항목이 섞여 있다. 대표적으로 audioop-lts 는 3.13+ 전용이라
# 3.12 에서는 resolver 가 통째로 실패하고 '아무 패키지도 설치되지 않는다'.
# (3.12 에는 audioop 이 표준 라이브러리로 들어 있어서 애초에 필요 없다)
# 또 이 파일은 UTF-16 로 저장돼 있어 .NET 이 BOM 을 보고 읽게 한다.
Write-Host "  requirements 필터링(동봉 Python 과 호환되지 않는 항목 제거)..."
$reqSrc = Join-Path $Src "requirements.txt"
$skipPkgs = @("audioop-lts")     # 3.13+ 전용
$reqLines = [System.IO.File]::ReadAllLines($reqSrc)   # BOM 자동 감지(UTF-16 대응)
$reqKept = $reqLines | Where-Object {
    $name = ($_ -split '[=<>!~\[; ]')[0].Trim().ToLower()
    -not ($skipPkgs -contains $name)
}
$reqFiltered = Join-Path $Cache "requirements_blog_payload.txt"
Set-Content -Path $reqFiltered -Value $reqKept -Encoding utf8
Write-Host "    $($reqLines.Count) 줄 → $($reqKept.Count) 줄"

& $PyExe -m pip install -r $reqFiltered
# requirements.txt(freeze)에 빠져 있지만 실제로 쓰이는 패키지들.
# pyperclip: 네이버 로그인 시 아이디/비번을 클립보드로 붙여넣는 데 쓴다.
#   빠지면 기기 인증 창이 뜨자마자 닫혀 로그인을 못 한다.
& $PyExe -m pip install playwright pyperclip

# pip 는 출력이 리다이렉트되면 종료코드 판정이 어긋날 수 있으므로, 실제로 import 되는지로 확인한다.
# 여기서 실패하면 '설치는 됐는데 고객 PC 에서 안 뜨는' 설치본이 나가므로 반드시 중단한다.
Write-Host "  설치 검증(핵심 패키지 import)..."
# ⚠ 목록에 빠진 패키지는 '설치본에서만' 터진다. 실제로 두 번 당했다.
#   - pyperclip 누락 → 기기 인증 창이 뜨자마자 닫힘
#   - cryptography 가 반쯤 설치됨(RECORD 없음, _rust.pyd 없음) → import jwt 실패로 백엔드가 아예 안 뜸.
#     이 경우 pip 은 '이미 설치됨'으로 보고 건너뛰므로 재실행해도 낫지 않는다.
#     여기서 import 로 검증해야만 잡힌다. (복구: pip install --ignore-installed --no-deps <pkg>)
#   - playwright 만 import 하면 greenlet 이 로드되지 않아, msvcp140.dll 누락으로
#     고객 PC 에서 백엔드가 아예 안 뜨는 결함이 이 검증을 그대로 통과했다.
#     실제 백엔드가 타는 경로(playwright.async_api)까지 import 해야 잡힌다.
$probe = "import fastapi,uvicorn,sqlalchemy,pydantic,dotenv,bs4,aiohttp,apscheduler,requests,PIL,tkinter,jwt,cryptography,pyperclip;import playwright.async_api,greenlet,numpy,pandas;print('PKG_OK')"
$probeOut = & $PyExe -c $probe 2>&1
if ($probeOut -notmatch "PKG_OK") {
    throw "동봉 Python 패키지 설치가 불완전합니다. pip 로그를 확인하세요.`n$probeOut"
}
Write-Host "    핵심 패키지 정상" -ForegroundColor Green

Write-Host "  Chromium(Playwright) 설치..."
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path $Runtime "ms-playwright")
& $PyExe -m playwright install chromium

# ── 5. 동봉 Node (portable) ────────────────────────────────
Write-Host "[5/7] 동봉 Node 준비..." -ForegroundColor Yellow
$nodeZip = Join-Path $Cache "node-v$NodeVersion-win-x64.zip"
Get-File "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" $nodeZip
$nodeTmp = Join-Path $Cache "node_extract_blog"
if (Test-Path $nodeTmp) { Remove-Item $nodeTmp -Recurse -Force }
Expand-Archive $nodeZip -DestinationPath $nodeTmp -Force
Move-Item (Join-Path $nodeTmp "node-v$NodeVersion-win-x64") (Join-Path $Runtime "node")

}   # ← -SkipRuntime 분기 끝 (4~5단계)

# ── 5-b. 동봉 런타임 네이티브 의존성 보정 ───────────────────
# 동봉 Python 은 C 런타임(vcruntime140*)만 들어 있고 C++ 런타임(msvcp140.dll)이 없다.
# greenlet(=playwright.async_api 가 import)·numpy·pandas·pyarrow 가 이걸 요구하는데,
# 빌드 PC 에는 System32 에 있어서 문제가 드러나지 않고 VC++ 재배포 패키지가 없는
# 깨끗한 Windows(고객 PC)에서만 백엔드가 통째로 죽는다. 실제로 그렇게 나갔다.
#   ImportError: DLL load failed while importing _greenlet: 지정된 모듈을 찾을 수 없습니다
# ⚠ -SkipRuntime 분기 '밖'에 둔다 — 증분 빌드는 예전 runtime\ 을 그대로 재사용하므로
#   분기 안에 두면 결함이 있는 런타임이 그대로 설치본에 실린다.
Write-Host "[5-b/7] 동봉 런타임 네이티브 의존성 점검..." -ForegroundColor Yellow
. (Join-Path $Here "native_runtime.ps1")
$PyDir = Join-Path $Runtime "python"
$PyExe = Join-Path $PyDir "python.exe"          # -SkipRuntime 이면 위 분기에서 설정되지 않는다
Repair-BundledNativeRuntime $PyDir
Copy-NativeFixPayload $PyDir $Payload      # 예전 설치본을 업데이트로 고치기 위한 복구용 사본
# 보정 결과를 실제 import 로 확인한다. 이게 통과해야 고객 PC 에서 백엔드가 뜬다.
# (DLL 이 있어도 버전이 낮으면 '프로시저 진입점을 찾을 수 없습니다' 로 여기서 걸린다)
$nativeOut = & $PyExe -c "import playwright.async_api,greenlet,numpy,pandas;print('NATIVE_OK')" 2>&1
if ($nativeOut -notmatch "NATIVE_OK") {
    throw "네이티브 확장모듈 로드 실패 — 이대로 배포하면 고객 PC 에서 백엔드가 뜨지 않습니다.`n$nativeOut"
}
Write-Host "  네이티브 확장모듈 정상" -ForegroundColor Green

# ── 6. 라이선스 서버 설정 ──────────────────────────────────
Write-Host "[6/7] license_config.json 작성..." -ForegroundColor Yellow
@{ server = $LicenseServer } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "license_config.json")

# 설치본의 현재 버전 — 런처가 이 값을 서버 최신 버전과 비교해 업데이트 여부를 정한다.
@{
  product  = "blog"
  version  = $Version
  built_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "version.json")
Write-Host "  version.json = $Version"

if (Test-Path (Join-Path $Here "blog.ico")) { Copy-Item (Join-Path $Here "blog.ico") $Payload }
elseif (Test-Path (Join-Path $Here "mbam.ico")) { Copy-Item (Join-Path $Here "mbam.ico") (Join-Path $Payload "blog.ico") }

# ── 7. 마무리 ──────────────────────────────────────────────
Remove-Item (Join-Path $WebStage "node_modules") -Force -Recurse -ErrorAction SilentlyContinue  # 정션 해제
Write-Host "[7/7] 완료. payload_blog 준비됨." -ForegroundColor Green
Write-Host ""
Write-Host "다음 명령으로 설치파일을 컴파일하세요:" -ForegroundColor Cyan
# Inno Setup 은 '모든 사용자'(Program Files)로도, '나만'(LOCALAPPDATA)으로도 설치된다.
# 이 PC 는 사용자 폴더에 깔려 있어 Program Files 경로를 안내하면 '찾을 수 없음'이 난다.
$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { Write-Host "  & `"$iscc`" blog.iss" }
else {
    Write-Host "  (Inno Setup 6 을 찾지 못했습니다 — https://jrsoftware.org/isdl.php 에서 설치하세요)" -ForegroundColor Red
}
Write-Host ""
Write-Host "※ 인증은 기기 승인 방식입니다(인증코드 없음)." -ForegroundColor Yellow
Write-Host "   고객이 실행 → [승인 요청] → 관리자_승인도구.exe 에서 '블로그 마케팅' 행을 승인하면 열립니다."
