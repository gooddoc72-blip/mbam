# ============================================================
#  업데이트 패키지 만들기 — 바뀌는 부분만 묶는다 (약 15MB)
#
#  왜 부분 패키지인가
#    설치본 2.4GB 중 실제로 바뀌는 건 파이썬 소스(3.4MB)와 프론트 빌드(10.8MB)뿐이다.
#    나머지(동봉 Python·Chromium·Node·node_modules 2.35GB)는 코드를 고쳐도 그대로다.
#    고객에게 637MB 설치본을 다시 받게 할 이유가 없다.
#
#  사용
#    1) 먼저 페이로드를 최신으로 만든다 (프론트 빌드가 여기 들어간다)
#         powershell -File build_cafe_payload.ps1 -SkipRuntime -Version 1.0.1
#    2) 이 스크립트로 패키지를 만든다
#         powershell -File 업데이트_패키지_만들기.ps1 -Version 1.0.1 -Notes "댓글 중복 수정"
#
#    블로그 전용판이면 -Product blog 를 붙인다(페이로드도 build_blog_payload.ps1 로 만든 것).
#         powershell -File build_blog_payload.ps1 -SkipRuntime -Version 1.0.1
#         powershell -File 업데이트_패키지_만들기.ps1 -Product blog -Version 1.0.1
#    3) 나오는 두 파일을 서버에 올린다 (배포 안내는 실행 끝에 출력된다)
#
#  ⚠ -Version 은 반드시 페이로드를 만들 때 준 값과 같아야 한다.
#     다르면 고객이 업데이트해도 버전이 안 올라가 매번 다시 물어보게 된다.
# ============================================================
param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$Notes = "",
  [ValidateSet("cafe", "blog", "mbam")]
  [string]$Product = "cafe"
)

$ErrorActionPreference = "Stop"
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
# 제품별 페이로드 폴더 — cafe=payload_cafe, blog=payload_blog, mbam(마케팅연구소)=payload
$PayloadName = switch ($Product) {
  "cafe"  { "payload_cafe" }
  "blog"  { "payload_blog" }
  default { "payload" }
}
$BuildScript = switch ($Product) {
  "cafe"  { "build_cafe_payload.ps1" }
  "blog"  { "build_blog_payload.ps1" }
  default { "build_payload.ps1" }
}
$Payload = Join-Path $Here $PayloadName
$OutDir  = Join-Path $Here "output\updates"

if (-not (Test-Path $Payload)) { throw "$PayloadName 가 없습니다. $BuildScript 을 먼저 실행하세요." }

# 페이로드의 버전이 요청한 버전과 같은지 확인 — 이게 어긋나면 업데이트가 무한 반복된다.
$verFile = Join-Path $Payload "version.json"
if (-not (Test-Path $verFile)) {
  throw "$PayloadName\version.json 이 없습니다. $BuildScript -Version $Version 으로 다시 만드세요."
}
$payloadVer = (Get-Content $verFile -Raw | ConvertFrom-Json).version
if ($payloadVer -ne $Version) {
  throw "버전 불일치 — 페이로드=$payloadVer, 요청=$Version`n  $BuildScript -SkipRuntime -Version $Version 으로 페이로드를 다시 만드세요."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stage = Join-Path $Here ".cache\update_stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Write-Host "== 업데이트 패키지 만들기 (v$Version) ==" -ForegroundColor Cyan

# licensing/updater.py 의 UPDATE_TARGETS 와 반드시 같아야 한다.
# (여기에만 넣고 저쪽에 안 넣으면 받아놓고 교체하지 않는다)
$targets = @(
  @{ rel = "mbam_nextgen";       kind = "dir"  },
  @{ rel = "licensing";          kind = "dir"  },
  @{ rel = "mbam-web\.next";     kind = "dir"  },
  @{ rel = "cafe_launcher.py";   kind = "file" },
  @{ rel = "cafe_auth_gate.py";  kind = "file" },
  @{ rel = "blog_launcher.py";   kind = "file" },
  @{ rel = "blog_auth_gate.py";  kind = "file" },
  @{ rel = "mbam_launcher.py";   kind = "file" },
  @{ rel = "mbam_auth_gate.py";  kind = "file" },
  @{ rel = "run_backend.py";     kind = "file" },
  @{ rel = "version.json";       kind = "file" },
  # 예외적으로 runtime 안의 파일 하나(약 0.6MB). 1.1.5 까지의 설치본에는 C++ 런타임이
  # 빠져 있어, VC++ 재배포 패키지가 없는 깨끗한 Windows 에서 백엔드가 아예 뜨지 않는다.
  # 이미 설치된 고객을 재설치 없이 고치려면 업데이트 패키지에 함께 실어야 한다.
  @{ rel = "runtime\python\msvcp140.dll"; kind = "file" }
)

foreach ($t in $targets) {
  $src = Join-Path $Payload $t.rel
  $dst = Join-Path $stage $t.rel
  if (-not (Test-Path $src)) { Write-Host "  (없음, 건너뜀) $($t.rel)" -ForegroundColor DarkGray; continue }
  if ($t.kind -eq "dir") {
    # 사용자 데이터(profiles/sessions)와 캐시는 패키지에 넣지 않는다.
    # 넣으면 고객 PC 의 네이버 로그인 세션을 빌드 PC 것으로 덮어쓴다.
    & robocopy $src $dst /E /NFL /NDL /NJH /NJS /NP /XD "profiles" "sessions" "__pycache__" | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "복사 실패: $($t.rel)" }
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item $src $dst -Force
  }
  Write-Host "  담음: $($t.rel)"
}

# 유출 방지 — 설치본 빌드와 같은 기준으로 한 번 더 검사한다.
foreach ($leak in @("profiles", "sessions")) {
  $found = Get-ChildItem $stage -Directory -Recurse -Filter $leak -ErrorAction SilentlyContinue
  if ($found) { throw "패키지에 '$leak' 가 들어갔습니다($($found[0].FullName)). 계정 로그인 정보가 유출됩니다." }
}
foreach ($pat in @("*.db", ".env", "user_settings.json", "agent_config.json", "my-key.pem")) {
  $found = Get-ChildItem $stage -File -Recurse -Force -Filter $pat -ErrorAction SilentlyContinue
  if ($found) { throw "패키지에 '$pat' 가 들어갔습니다($($found[0].FullName))." }
}

# 예전 설치본(1.1.5 이하) 복구용 DLL 이 실렸는지 확인.
# 이게 빠지면 그 고객들은 업데이트를 받아도 백엔드가 여전히 뜨지 않는다.
# (고객 PC 의 구버전 updater 는 runtime\ 을 교체하지 않으므로 licensing\ 경유가 유일한 통로다)
$fixDll = Join-Path $stage "licensing\runtime_fix\msvcp140.dll"
if (-not (Test-Path $fixDll)) {
  throw "licensing\runtime_fix\msvcp140.dll 이 패키지에 없습니다.`n  $BuildScript 을 다시 실행해 페이로드를 최신으로 만드세요(네이티브 의존성 보정 단계가 이 파일을 만듭니다)."
}

$zipName = "$Product-$Version.zip"
$zipPath = Join-Path $OutDir $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -CompressionLevel Optimal
$sha = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)

# 서버가 그대로 돌려줄 최신버전 정보
$manifest = [ordered]@{
  product     = $Product
  version     = $Version
  url         = "https://license.blocklab.co.kr/update/$Product/download/$zipName"
  sha256      = $sha
  size        = (Get-Item $zipPath).Length
  notes       = $Notes
  released_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}
$manifestPath = Join-Path $OutDir "$Product-latest.json"
# ⚠ BOM 없이 저장한다. Set-Content -Encoding UTF8 은 BOM 을 붙이는데,
#   그러면 서버(파이썬)가 json 을 읽다 터져 고객이 업데이트를 못 받는다.
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json),
                              (New-Object System.Text.UTF8Encoding($false)))

Remove-Item $stage -Recurse -Force

Write-Host ""
Write-Host "완료 — $zipName ($sizeMB MB)" -ForegroundColor Green
Write-Host "  $zipPath"
Write-Host "  $manifestPath"
Write-Host ""
Write-Host "서버에 올리기 — 저장소 루트에서 '업데이트_서버에올리기.bat' 을 더블클릭하세요." -ForegroundColor Cyan
Write-Host "  (직접 올리려면 Git Bash 에서:)"
Write-Host "  scp -i my-key.pem `"$zipPath`" ubuntu@18.209.162.250:~/auth_server/updates/"
Write-Host "  scp -i my-key.pem `"$manifestPath`" ubuntu@18.209.162.250:~/auth_server/updates/"
Write-Host ""
Write-Host "고객은 프로그램을 다시 켤 때 업데이트 안내를 받습니다." -ForegroundColor Cyan
