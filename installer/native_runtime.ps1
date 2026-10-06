# ============================================================
#  동봉 Python 런타임의 네이티브(C/C++) 의존성 점검·보정 — 빌드 스크립트 공용
#
#  왜 필요한가
#    동봉 Python(python-build-standalone)은 C 런타임(vcruntime140.dll,
#    vcruntime140_1.dll)만 함께 배포하고, C++ 런타임(msvcp140.dll)은 넣어주지 않는다.
#    그런데 PyPI 휠 중 C++ 로 작성된 확장모듈은 msvcp140.dll 을 요구한다.
#      - greenlet(_greenlet.pyd)  ← playwright.async_api 가 import 한다
#      - numpy, pandas, pyarrow, jpype
#    빌드 PC 에는 다른 프로그램이 깔아둔 VC++ 재배포 패키지 덕에 System32 에
#    msvcp140.dll 이 있어서 아무 문제가 없다. 하지만 갓 설치한 깨끗한 Windows 에는
#    없어서 고객 PC 에서만 이렇게 죽는다:
#      ImportError: DLL load failed while importing _greenlet: 지정된 모듈을 찾을 수 없습니다
#    → seo.py → main.py import 실패 → 백엔드가 아예 안 뜨고 프론트는 ECONNREFUSED.
#
#  왜 이 폴더에 넣으면 해결되는가
#    확장모듈(.pyd)의 DLL 탐색 경로에는 '실행 파일이 있는 폴더'가 포함된다.
#    백엔드는 runtime\python\python.exe 로 뜨므로, 지금 vcruntime140.dll 이
#    해석되는 것과 똑같은 경로로 msvcp140.dll 도 해석된다.
#    (VC++ CRT 는 이렇게 앱 폴더에 함께 배포하는 것이 MS 재배포 조건상 허용된다.
#     설치 프로그램이 PrivilegesRequired=lowest 라 VC_redist.exe 설치는 끼워넣을 수 없다)
#
#  사용 (각 build_*_payload.ps1 에서):
#      . (Join-Path $Here "native_runtime.ps1")
#      Repair-BundledNativeRuntime (Join-Path $Runtime "python")
#
#  ⚠ -SkipRuntime(증분 빌드)에서도 반드시 호출할 것. 이전 빌드의 runtime\ 을 그대로
#    재사용하므로, 분기 안에 두면 예전 결함이 있는 런타임이 그대로 나간다.
# ============================================================

# PE 파일이 import 하는 DLL 이름 목록을 돌려준다.
# 파일 전체를 문자열로 훑어 찾는 방식은 데이터 영역의 문자열까지 잡아 오탐이 난다.
# 여기서는 PE import 테이블만 정확히 읽는다(수십 KB 만 읽으므로 빠르다).
function Get-PeImportedDll {
  param([Parameter(Mandatory)][string]$Path)

  $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
  try {
    $br = New-Object System.IO.BinaryReader($fs)

    # --- DOS 헤더 ---
    if ($br.ReadUInt16() -ne 0x5A4D) { return @() }          # 'MZ' 아니면 PE 가 아니다
    $fs.Position = 0x3C
    $peOff = $br.ReadUInt32()
    if ($peOff -le 0 -or $peOff -ge $fs.Length - 24) { return @() }

    # --- PE 시그니처 + 파일 헤더 ---
    $fs.Position = $peOff
    if ($br.ReadUInt32() -ne 0x00004550) { return @() }      # 'PE\0\0'
    $null = $br.ReadUInt16()                                  # Machine
    $numSections = $br.ReadUInt16()
    $fs.Position += 12                                        # TimeDateStamp, PointerToSymbolTable, NumberOfSymbols
    $sizeOfOptional = $br.ReadUInt16()
    $null = $br.ReadUInt16()                                  # Characteristics

    # --- 옵션 헤더: 데이터 디렉터리[1] = Import Table ---
    $optOff = $fs.Position
    $magic = $br.ReadUInt16()
    $ddOff = if ($magic -eq 0x20B) { 112 } elseif ($magic -eq 0x10B) { 96 } else { return @() }
    $fs.Position = $optOff + $ddOff + 8                        # +8 = 디렉터리 1번(Import)
    $importRva = $br.ReadUInt32()
    $null = $br.ReadUInt32()                                   # Size
    if ($importRva -eq 0) { return @() }

    # --- 섹션 테이블(RVA → 파일 오프셋 변환용) ---
    $fs.Position = $optOff + $sizeOfOptional
    $sections = @()
    for ($i = 0; $i -lt $numSections; $i++) {
      $null = $br.ReadBytes(8)                                 # Name
      $vsize = $br.ReadUInt32(); $vaddr = $br.ReadUInt32()
      $rsize = $br.ReadUInt32(); $raddr = $br.ReadUInt32()
      $null = $br.ReadBytes(16)                                # 나머지
      $sections += [pscustomobject]@{
        VAddr = $vaddr; VSize = [Math]::Max($vsize, $rsize); RAddr = $raddr
      }
    }
    $rva2off = {
      param($rva)
      foreach ($s in $sections) {
        if ($rva -ge $s.VAddr -and $rva -lt ($s.VAddr + $s.VSize)) { return $s.RAddr + ($rva - $s.VAddr) }
      }
      return 0
    }

    # --- IMAGE_IMPORT_DESCRIPTOR 순회 (20바이트, Name RVA 는 +12) ---
    $descOff = & $rva2off $importRva
    if ($descOff -le 0) { return @() }
    $names = @()
    for ($i = 0; $i -lt 4096; $i++) {
      $entry = $descOff + ($i * 20)
      if (($entry + 20) -gt $fs.Length) { break }
      $fs.Position = $entry + 12
      $nameRva = $br.ReadUInt32()
      if ($nameRva -eq 0) { break }                            # 종료(전부 0인 디스크립터)
      $nameOff = & $rva2off $nameRva
      if ($nameOff -le 0) { break }
      $fs.Position = $nameOff
      $sb = New-Object System.Text.StringBuilder
      while ($fs.Position -lt $fs.Length) {
        $b = $br.ReadByte()
        if ($b -eq 0) { break }
        [void]$sb.Append([char]$b)
      }
      if ($sb.Length -gt 0) { $names += $sb.ToString() }
    }
    return $names
  } catch {
    return @()          # 손상/특수 형식 파일은 조용히 건너뛴다(검사 대상이 수천 개다)
  } finally {
    $fs.Dispose()
  }
}

# 앱 폴더에 함께 배포해야 하는 MSVC 런타임 DLL 인지 판별.
# (api-ms-win-*, kernel32 등 OS 가 제공하는 것은 대상이 아니다)
$script:MsvcRedistPattern = '^(msvcp\d+(_\d+)?|vcruntime\d+(_\d+)?|vcomp\d+|concrt\d+)\.dll$'

# 재배포 DLL 원본을 찾는다. Visual Studio 재배포 폴더 → System32 순.
function Find-MsvcRedistSource {
  param([Parameter(Mandatory)][string]$Name)

  $globs = @(
    (Join-Path $env:ProgramFiles        "Microsoft Visual Studio\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT\$Name"),
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\*\*\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT\$Name"),
    (Join-Path $env:WINDIR "System32\$Name")
  )
  $cands = foreach ($g in $globs) {
    Get-ChildItem $g -ErrorAction SilentlyContinue | ForEach-Object {
      [pscustomobject]@{
        Path = $_.FullName
        Ver  = [version]("{0}.{1}.{2}.{3}" -f $_.VersionInfo.FileMajorPart, $_.VersionInfo.FileMinorPart,
                                              $_.VersionInfo.FileBuildPart, $_.VersionInfo.FilePrivatePart)
      }
    }
  }
  # 가장 높은 버전을 쓴다(하위 호환되므로 최신이 안전하다)
  $cands | Sort-Object Ver -Descending | Select-Object -First 1
}

# 동봉 Python 폴더를 검사해 부족한 MSVC 런타임 DLL 을 채워 넣고, 그래도 부족하면 빌드를 중단한다.
function Repair-BundledNativeRuntime {
  param([Parameter(Mandatory)][string]$PythonDir)

  if (-not (Test-Path $PythonDir)) { throw "동봉 Python 폴더가 없습니다: $PythonDir" }

  Write-Host "  네이티브 의존성 검사(확장모듈이 요구하는 MSVC 런타임)..." -ForegroundColor DarkGray
  $needBy = @{}      # DLL 이름(소문자) → 그걸 요구하는 모듈 경로 하나
  $files = Get-ChildItem $PythonDir -Recurse -Include *.pyd, *.dll -File -ErrorAction SilentlyContinue
  foreach ($f in $files) {
    foreach ($dep in (Get-PeImportedDll $f.FullName)) {
      $lower = $dep.ToLower()
      if ($lower -match $script:MsvcRedistPattern -and -not $needBy.ContainsKey($lower)) {
        $needBy[$lower] = $f.FullName.Substring($PythonDir.Length).TrimStart('\')
      }
    }
  }
  Write-Host "    모듈 $($files.Count) 개 검사 → 요구 런타임 $($needBy.Count) 종" -ForegroundColor DarkGray

  $copied = @(); $failed = @()
  foreach ($name in ($needBy.Keys | Sort-Object)) {
    if (Test-Path (Join-Path $PythonDir $name)) { continue }   # 이미 동봉돼 있음
    $src = Find-MsvcRedistSource $name
    if ($src) {
      Copy-Item $src.Path (Join-Path $PythonDir $name) -Force
      $copied += "$name (v$($src.Ver), $($needBy[$name]) 가 요구)"
    } else {
      $failed += "$name  ← $($needBy[$name])"
    }
  }

  if ($copied) {
    Write-Host "    동봉 추가:" -ForegroundColor Green
    $copied | ForEach-Object { Write-Host "      + $_" -ForegroundColor Green }
  }
  # 오래된 CRT 를 동봉하면, 나중에 최신 툴셋으로 빌드된 휠로 갈아탈 때
  # '프로시저 진입점을 찾을 수 없습니다'(에러 127)가 난다. 다만 그 경우 빌드 PC 에서도
  # 똑같이 재현되므로(아래 import 검증에서 걸린다) 여기서는 중단하지 않고 알리기만 한다.
  $mp = Join-Path $PythonDir "msvcp140.dll"
  if (Test-Path $mp) {
    $vi = (Get-Item $mp).VersionInfo
    $mv = [version]("{0}.{1}.{2}.{3}" -f $vi.FileMajorPart, $vi.FileMinorPart, $vi.FileBuildPart, $vi.FilePrivatePart)
    if ($mv -lt [version]"14.30") {
      Write-Host "    ※ 동봉된 msvcp140.dll 이 v$mv 로 오래됐습니다. 빌드 PC 에 최신 VC++ 재배포 패키지를" -ForegroundColor Yellow
      Write-Host "       설치해 두면 더 안전합니다: https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
    }
  }
  if ($failed) {
    throw @"
동봉 Python 이 요구하는 MSVC 런타임 DLL 을 빌드 PC 에서 찾지 못했습니다:
$($failed -join "`n")

이대로 배포하면 VC++ 재배포 패키지가 없는 고객 PC(갓 설치한 Windows)에서
'ImportError: DLL load failed ... 지정된 모듈을 찾을 수 없습니다' 로 백엔드가 뜨지 않습니다.
빌드 PC 에 'Microsoft Visual C++ 2015-2022 재배포 가능 패키지(x64)' 를 설치한 뒤 다시 빌드하세요.
  https://aka.ms/vs/17/release/vc_redist.x64.exe
"@
  }
  if (-not $copied) { Write-Host "    이미 모두 동봉됨" -ForegroundColor DarkGray }
}

# 업데이트로 예전 설치본을 고치기 위한 복구용 사본을 licensing\runtime_fix\ 에 함께 싣는다.
#
# 업데이트는 고객 PC 에 '이미 깔려 있는' updater.py 가 수행하는데, 1.1.5 까지의 그 목록에는
# runtime\ 이 없다. 그래서 새 목록에 runtime\python\msvcp140.dll 을 넣어도 기존 고객에게는
# 닿지 않는다. 반면 licensing\ 은 예전부터 교체 대상이라 이 경로로는 확실히 전달된다.
# 런처(licensing\native_fix.py)가 백엔드를 띄우기 전에 이걸 runtime\python\ 으로 옮긴다.
function Copy-NativeFixPayload {
  param(
    [Parameter(Mandatory)][string]$PythonDir,     # payload\runtime\python
    [Parameter(Mandatory)][string]$PayloadDir     # payload 루트
  )
  $src = Join-Path $PythonDir "msvcp140.dll"
  if (-not (Test-Path $src)) { throw "msvcp140.dll 이 동봉되지 않았습니다: $PythonDir" }
  $dstDir = Join-Path $PayloadDir "licensing\runtime_fix"
  New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  Copy-Item $src (Join-Path $dstDir "msvcp140.dll") -Force
  Write-Host "    업데이트 복구용 사본: licensing\runtime_fix\msvcp140.dll" -ForegroundColor DarkGray
}
