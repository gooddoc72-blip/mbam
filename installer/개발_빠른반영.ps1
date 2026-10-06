# ============================================================
#  수정한 코드를 '설치된 프로그램'에 바로 반영 — 설치파일을 만들지 않는다.
#
#  왜 필요한가
#    설치파일(exe)을 다시 만들려면 페이로드 20분 + LZMA2 압축 25분 = 45분이 든다.
#    그런데 그 2.4GB 중 2.35GB(동봉 Python·Chromium·Node·node_modules)는
#    코드를 고쳐도 한 바이트도 안 바뀐다. 고친 걸 '확인'하는 데 45분을 쓸 이유가 없다.
#
#    확인은 이 스크립트로 하고, 설치파일은 고객에게 내보내기 직전에 한 번만 만든다.
#
#  사용
#    powershell -ExecutionPolicy Bypass -File 개발_빠른반영.ps1          # 파이썬만 (수초)
#    powershell -ExecutionPolicy Bypass -File 개발_빠른반영.ps1 -Web     # 프론트 포함 (약 5분)
#
#  ⚠ 이건 '내 PC 의 설치본'만 갱신한다. 고객에게 나가는 설치파일은 바뀌지 않는다.
#     배포용은 반드시 build_cafe_payload.ps1 (스위치 없이) + ISCC 로 다시 만들 것.
# ============================================================
param(
  [switch]$Web,       # 프론트(mbam-web) 수정도 반영. 붙이지 않으면 파이썬 소스만 복사.
  [switch]$NoStart,   # 반영 후 프로그램을 다시 켜지 않음
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\MBAM-Cafe")
)

$ErrorActionPreference = "Stop"
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src     = Split-Path -Parent $Here
$Payload = Join-Path $Here "payload_cafe"

if (-not (Test-Path $InstallDir)) { throw "설치 폴더가 없습니다: $InstallDir`n먼저 설치파일로 한 번 설치하세요." }
Write-Host "== 설치본에 바로 반영 ==" -ForegroundColor Cyan
Write-Host "  대상: $InstallDir"

# ── 1. 실행 중이면 종료 ────────────────────────────────────
# 파일을 잡고 있으면 복사가 실패한다(설치파일도 같은 이유로 종료코드 5 로 죽는다).
$running = Get-Process python, pythonw, node -ErrorAction SilentlyContinue |
           Where-Object { $_.Path -and $_.Path.StartsWith($InstallDir, "OrdinalIgnoreCase") }
if ($running) {
  Write-Host "  실행 중인 프로그램 종료 ($($running.Count)개)..." -ForegroundColor Yellow
  $running | Stop-Process -Force
  Start-Sleep -Seconds 3
}

# ── 2. 프론트 — 요청 시에만 ────────────────────────────────
# 프론트는 '카페 화면만 남기고 빌드'하는 스테이징을 거쳐야 해서 직접 빌드하면 안 된다.
# 실제 배포와 똑같은 경로를 타도록 페이로드 빌드를 증분(-SkipRuntime)으로 부른다.
if ($Web) {
  Write-Host "`n[1/2] 프론트 재빌드 (증분)..." -ForegroundColor Yellow
  & powershell -ExecutionPolicy Bypass -File (Join-Path $Here "build_cafe_payload.ps1") -SkipRuntime
  if (-not (Test-Path (Join-Path $Payload "mbam-web\.next\BUILD_ID"))) {
    throw "프론트 빌드 실패 — 위 로그를 확인하세요."
  }
  # .next 는 이전 빌드의 잔재가 섞이면 안 되므로 통째로 갈아끼운다(/MIR).
  # node_modules 는 payload 쪽과 동일하므로 건드리지 않는다.
  Write-Host "  .next 반영..."
  & robocopy (Join-Path $Payload "mbam-web\.next") (Join-Path $InstallDir "mbam-web\.next") /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw ".next 복사 실패(code $LASTEXITCODE)" }
} else {
  Write-Host "`n[1/2] 프론트 — 건너뜀 (-Web 을 붙이면 반영)" -ForegroundColor DarkGray
}

# ── 3. 파이썬 소스 ─────────────────────────────────────────
# 여기가 대부분의 수정이 일어나는 곳이고, 복사는 수 초면 끝난다.
# ⚠ 설치 폴더에는 사용자 데이터(seo_history.db, profiles\)가 함께 있으므로
#   /MIR 를 쓰면 안 된다. 덮어쓰기만 한다.
Write-Host "`n[2/2] 파이썬 소스 반영..." -ForegroundColor Yellow
# ⚠ /IS /IT 가 반드시 필요하다.
#   설치본 파일은 설치·이전 복사 때 '현재 시각'으로 찍혀 원본보다 최신인 경우가 많다.
#   그러면 robocopy 가 '원본이 더 오래됨'으로 보고 조용히 건너뛴다.
#   실제로 이것 때문에 고친 코드가 반영되지 않은 채 '반영 완료'만 뜬 적이 두 번 있었다.
#   /IS(같아 보여도 복사) /IT(속성만 달라도 복사) 로 항상 덮어쓴다.
$rcOpts = @("/E", "/IS", "/IT", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
& robocopy (Join-Path $Src "mbam_nextgen") (Join-Path $InstallDir "mbam_nextgen") @rcOpts `
    /XD "profiles" "sessions" "__pycache__" "temp_clips" "scratch" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "mbam_nextgen 복사 실패(code $LASTEXITCODE)" }
& robocopy (Join-Path $Src "licensing") (Join-Path $InstallDir "licensing") @rcOpts /XD "__pycache__" | Out-Null
foreach ($f in @("cafe_launcher.py", "cafe_auth_gate.py")) {
  if (Test-Path (Join-Path $Src $f)) { Copy-Item (Join-Path $Src $f) $InstallDir -Force; Write-Host "  $f" }
}
# 이전에 복사돼 남은 .pyc 가 새 소스를 가리는 일이 없도록 정리
Get-ChildItem $InstallDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ── 4. 반영한 코드가 실제로 임포트되는지 확인 ─────────────────────────
# 문법 오류나 미정의 이름(import 누락 등)이 있으면 백엔드가 아예 안 뜬다.
# 그걸 모르고 '반영 완료'만 보고 넘어가면, 프로그램을 켰을 때야 알게 된다.
Write-Host "`n[검사] 설치본 코드가 정상 임포트되는지 확인..." -ForegroundColor Yellow
$probe = @"
import sys, os
sys.path.insert(0, r'$InstallDir')
os.environ.setdefault('MBAM_PRODUCT', 'cafe')
os.environ.setdefault('JWT_SECRET', 'probe')
os.environ.setdefault('ENV_CIPHER_KEY', 'probe')
try:
    from mbam_nextgen.backend.main import app
    print('IMPORT_OK routes=%d' % len(app.routes))
except Exception as e:
    print('IMPORT_FAIL %s: %s' % (type(e).__name__, e))
    raise SystemExit(1)
"@
$probeFile = Join-Path $env:TEMP "mbam_import_probe.py"
Set-Content -Path $probeFile -Value $probe -Encoding UTF8
Push-Location $InstallDir
# ⚠ 네이티브 명령에 2>&1 을 쓰면 안 된다. $ErrorActionPreference='Stop' 이라
#   파이썬이 경고 한 줄만 stderr 로 내보내도 PowerShell 이 '실패'로 보고 스크립트를 끊는다.
#   (실제로 여기서 끊겨 검사 결과를 못 봤다) 그래서 각각 파일로 받는다.
$probeOutFile = Join-Path $env:TEMP "mbam_import_probe.out"
$probeErrFile = Join-Path $env:TEMP "mbam_import_probe.err"
Start-Process -FilePath (Join-Path $InstallDir "runtime\python\python.exe") -ArgumentList "`"$probeFile`"" `
    -NoNewWindow -Wait -RedirectStandardOutput $probeOutFile -RedirectStandardError $probeErrFile
$probeOut = @()
if (Test-Path $probeOutFile) { $probeOut += Get-Content $probeOutFile }
if (Test-Path $probeErrFile) { $probeOut += Get-Content $probeErrFile }
Remove-Item $probeOutFile, $probeErrFile -Force -ErrorAction SilentlyContinue
Pop-Location
Remove-Item $probeFile -Force -ErrorAction SilentlyContinue
if ($probeOut -match "IMPORT_OK") {
    Write-Host "  $(($probeOut | Select-String 'IMPORT_OK').Line.Trim())" -ForegroundColor Green
} else {
    Write-Host "  ❌ 설치본이 기동할 수 없는 상태입니다:" -ForegroundColor Red
    ($probeOut | Select-String "IMPORT_FAIL|Error|error" | Select-Object -Last 5) | ForEach-Object { Write-Host "     $_" }
    throw "코드 반영은 됐지만 임포트에 실패했습니다. 위 오류를 고친 뒤 다시 실행하세요."
}

Write-Host "`n반영 완료." -ForegroundColor Green

# ── 4. 재시작 ──────────────────────────────────────────────
if (-not $NoStart) {
  Write-Host "프로그램을 다시 시작합니다..." -ForegroundColor Cyan
  Start-Process -FilePath (Join-Path $InstallDir "runtime\python\pythonw.exe") `
                -ArgumentList (Join-Path $InstallDir "cafe_launcher.py") -WorkingDirectory $InstallDir
  Write-Host "  (백엔드 기동까지 20~30초 걸립니다)"
}
