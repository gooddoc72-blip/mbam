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
#    powershell -ExecutionPolicy Bypass -File build_blog_payload.ps1              (기본판)
#    powershell -ExecutionPolicy Bypass -File build_blog_payload.ps1 -Tier pro    (프로판 = 병원 블로그 포함)
#
#  기본판/프로판 차이
#    - 프로판만 병원 블로그(/hospital-blog) 화면·메뉴·'병원' 지시문이 들어간다
#    - 인증 제품 코드: 기본=blog, 프로=blog_pro (승인을 따로 받는다 — 기본판 승인으로는 프로판이 안 열림)
#    - 설치 폴더·포트·AppId 는 같다 → 프로판을 깔면 기본판이 프로판으로 교체(업그레이드)된다
#
#  필요: 인터넷 연결(런타임 다운로드), 빌드 PC 에 Node/npm 설치(프론트 빌드용)
# ============================================================
param(
  # 제품 등급: basic(블로그 마케팅 기본) | pro(블로그 마케팅 프로 — 병원 블로그 포함)
  [ValidateSet("basic","pro")]
  [string]$Tier          = "basic",
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
  Write-Host "== 증분 빌드: runtime 재사용 ==" -ForegroundColor Cyan
  # mbam-web 은 독립 실행형(standalone) 산출물로 매번 새로 채운다(약 1,500개·20MB 라 재사용할 이유가 없다)
  Get-ChildItem $Payload -Force | Where-Object { $_.Name -ne "runtime" } |
    Remove-Item -Recurse -Force
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
               "build","dist","_startup_backup","_보관")
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
$stageNm = Join-Path $WebStage "node_modules"
# 예전 빌드가 남긴 node_modules '정션'은 반드시 rmdir 로 연결만 끊는다.
# (그대로 두고 아래 robocopy /MIR 를 돌리면 원본 mbam-web\node_modules 에 직접 쓰고 지운다)
if ((Test-Path $stageNm) -and ((Get-Item $stageNm -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  cmd /c rmdir "$stageNm" | Out-Null
}
# node_modules 는 남겨 두고(다음 빌드에서 /MIR 로 바뀐 것만 갱신) 나머지만 새로 뜬다.
if (Test-Path $WebStage) {
  Get-ChildItem $WebStage -Force | Where-Object { $_.Name -ne "node_modules" } | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $WebStage | Out-Null
& robocopy $webSrc $WebStage /E /NFL /NDL /NJH /NJS /NP /XD ".next" "node_modules" ".claude" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "프론트 스테이징 복사 실패(code $LASTEXITCODE)" }

# node_modules 는 정션이 아니라 '실제 사본'이어야 한다.
# 독립 실행형(standalone) 빌드는 파일의 실제 경로로 추적하므로, 정션이면 산출물이
# 저장소 경로 구조째(standalone\installer\.cache\...\server.js + standalone\mbam-web\node_modules)
# 로 나와 server.js 가 next 를 찾지 못한다. 처음 한 번만 1~2분 걸리고 이후엔 바뀐 것만 복사한다.
if (-not (Test-Path (Join-Path $webSrc "node_modules"))) {
  Push-Location $webSrc; npm ci; Pop-Location
}
& robocopy (Join-Path $webSrc "node_modules") $stageNm /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "node_modules 복사 실패(code $LASTEXITCODE)" }

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
# 프로판은 병원 블로그를 남긴다 (blog-posting 화면을 재export 하므로 별도 의존성 없음)
if ($Tier -eq "pro") { $dropPages = $dropPages | Where-Object { $_ -ne "hospital-blog" } }
foreach ($d in $dropPages) {
  $p = Join-Path $WebStage "app\$d"
  if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "  - 제외: app\$d" }
}

# ── 3. 프론트엔드 빌드 (블로그 프로파일) ──────────────────────
Write-Host "[3/7] 프론트엔드(Next.js) 블로그 빌드..." -ForegroundColor Yellow
# NEXT_PUBLIC_PRODUCT 는 번들에 인라인되고, BACKEND_URL 은 rewrites 로
# routes-manifest.json 에 구워진다 → 둘 다 반드시 빌드 시점에 설정해야 한다.
$env:NEXT_PUBLIC_PRODUCT = "blog"
$env:NEXT_PUBLIC_BLOG_TIER = $Tier   # basic | pro — 메뉴·탭·제품명이 여기서 갈린다
$env:BACKEND_URL = "http://127.0.0.1:$BackendPort"
# 독립 실행형 — next.config.mjs 가 이 값을 보고 output:'standalone' 을 켠다.
$env:NEXT_OUTPUT_STANDALONE = "1"
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

# 독립 실행형 산출물 조립 → payload\mbam-web
#   .next\standalone\  = server.js + 실행에 필요한 node_modules(추려진 것) + .next(서버 번들)
#   여기에 .next\static(브라우저용 JS/CSS)과 public 을 직접 넣어야 server.js 가 서빙한다.
# 결과 구조(설치 폴더\mbam-web):
#   server.js, package.json, node_modules\(약 1,500개), .next\(BUILD_ID·server·static), public\
# ⚠ .next 위치는 예전과 같아야 한다 — 업데이트(licensing\updater.py)가 mbam-web\.next 를
#   통째로 교체하므로, 1.0.3 이하(next start) 설치본도 같은 .next 로 뜬다.
$saDir = Join-Path $stageNext "standalone"
if (-not (Test-Path (Join-Path $saDir "server.js"))) {
  throw "독립 실행형 산출물이 없습니다 → $saDir\server.js`n  next.config.mjs 의 NEXT_OUTPUT_STANDALONE 처리와 npm 로그를 확인하세요."
}
$webDst = Join-Path $Payload "mbam-web"
New-Item -ItemType Directory -Force -Path $webDst | Out-Null
& robocopy $saDir $webDst /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "standalone 복사 실패(code $LASTEXITCODE)" }
& robocopy (Join-Path $stageNext "static") (Join-Path $webDst ".next\static") /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw ".next\static 복사 실패(code $LASTEXITCODE)" }
$pub = Join-Path $WebStage "public"
if (Test-Path $pub) { & robocopy $pub (Join-Path $webDst "public") /E /NFL /NDL /NJH /NJS /NP | Out-Null }
# 경로 구조째 나왔다면(정션 등으로 추적 루트가 어긋남) server.js 가 next 를 못 찾는다 — 여기서 잡는다.
if (-not (Test-Path (Join-Path $webDst "node_modules\next\package.json"))) {
  throw "standalone 산출물에 node_modules\next 가 없습니다. 추적 루트가 어긋났습니다(정션 여부 확인)."
}
$webFiles = (Get-ChildItem $webDst -Recurse -File -Force).Count
Write-Host "  mbam-web 파일 수: $webFiles (예전 통째 동봉 약 19,000)" -ForegroundColor DarkGray

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
# Windows 내장 tar(bsdtar)를 직접 지정 — Git Bash 에서 실행하면 PATH 의 GNU tar 가 잡혀
# 'F:' 를 원격 호스트로 해석해 'Cannot connect to F: resolve failed' 로 실패한다.
& (Join-Path $env:SystemRoot "System32\tar.exe") -xzf $pyArchive -C $pyTmp
Move-Item (Join-Path $pyTmp "python") (Join-Path $Runtime "python")
$PyExe = Join-Path $Runtime "python\python.exe"

Write-Host "  파이썬 패키지 설치..."
& $PyExe -m pip install --upgrade pip

# 저장소 루트 requirements.txt(개발 PC 의 pip freeze, 180여 개)가 아니라
# installer\requirements_local.txt(고객용 코드가 실제로 import 하는 것만, 버전 고정)를 쓴다.
# freeze 를 그대로 넣던 1.0.3 까지는 gradio·streamlit·pandas·pyarrow 등 안 쓰는 패키지가
# 파일 2만 3천 개·675MB 를 차지해 고객 PC 설치가 오래 걸렸다.
# 빠진 패키지는 맨 끝 check_imports.py 가 잡아 빌드를 중단한다.
$reqLocal = Join-Path $Here "requirements_local.txt"
& $PyExe -m pip install --no-warn-script-location -r $reqLocal
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
$probe = "import fastapi,uvicorn,sqlalchemy,pydantic,dotenv,bs4,aiohttp,apscheduler,requests,PIL,tkinter,jwt,cryptography,pyperclip;import playwright.async_api,greenlet,numpy,multipart,docx,kiwipiepy;print('PKG_OK')"
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
$nativeOut = & $PyExe -c "import playwright.async_api,greenlet,numpy,lxml.etree;print('NATIVE_OK')" 2>&1
if ($nativeOut -notmatch "NATIVE_OK") {
    throw "네이티브 확장모듈 로드 실패 — 이대로 배포하면 고객 PC 에서 백엔드가 뜨지 않습니다.`n$nativeOut"
}
Write-Host "  네이티브 확장모듈 정상" -ForegroundColor Green

# 고객용 코드가 import 하는 패키지가 동봉 Python 에 전부 있는지(코드는 실행하지 않고 이름만 확인)
$impOut = & $PyExe -I (Join-Path $Here "check_imports.py") $Payload 2>&1
if ($impOut -notmatch "IMPORTS_OK") {
    throw "동봉 Python 에 빠진 패키지가 있습니다 — 이대로 배포하면 고객 PC 에서 해당 기능이 죽습니다.`n$impOut"
}
Write-Host "  고객용 코드 import 점검 정상" -ForegroundColor Green

# ── 6. 라이선스 서버 설정 ──────────────────────────────────
Write-Host "[6/7] license_config.json 작성..." -ForegroundColor Yellow
@{ server = $LicenseServer } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "license_config.json")

# 설치본의 현재 버전 — 런처가 이 값을 서버 최신 버전과 비교해 업데이트 여부를 정한다.
# product 는 인증·업데이트 채널 코드다 (기본=blog, 프로=blog_pro). 런처가 이 값을 읽는다.
$productCode = if ($Tier -eq "pro") { "blog_pro" } else { "blog" }
@{
  product  = $productCode
  tier     = $Tier
  version  = $Version
  built_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Payload "version.json")
Write-Host "  version.json = $Version ($productCode)"

if (Test-Path (Join-Path $Here "blog.ico")) { Copy-Item (Join-Path $Here "blog.ico") $Payload }
elseif (Test-Path (Join-Path $Here "mbam.ico")) { Copy-Item (Join-Path $Here "mbam.ico") (Join-Path $Payload "blog.ico") }

# ── 7. 마무리 ──────────────────────────────────────────────
# (스테이징의 node_modules 는 실제 사본이라 남겨 둔다 — 다음 빌드에서 바뀐 것만 복사)
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
if ($iscc) { Write-Host "  & `"$iscc`" /DTier=$Tier blog.iss" }
else {
    Write-Host "  (Inno Setup 6 을 찾지 못했습니다 — https://jrsoftware.org/isdl.php 에서 설치하세요)" -ForegroundColor Red
}
Write-Host ""
Write-Host "※ 인증은 기기 승인 방식입니다(인증코드 없음)." -ForegroundColor Yellow
Write-Host "   고객이 실행 → [승인 요청] → 관리자_승인도구.exe 에서 '$productCode' 제품 행을 승인하면 열립니다."
