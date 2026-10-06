#!/bin/bash
# ============================================================
#  네이버 카페 마케팅 프로그램 — 맥용 설치 페이로드 빌드
#
#  build_cafe_payload.ps1(윈도우판)을 맥으로 옮긴 것이다. 제외 규칙·화이트리스트·
#  유출 방지 검사는 원본과 같은 내용을 유지한다. 한쪽만 고치면 어긋나므로
#  둘 중 하나를 고치면 반대쪽도 같이 고칠 것.
#
#  ⚠ 반드시 맥에서 실행해야 한다. 맥용 Python·Node·Chromium 을 받아
#    설치해야 하고, 이어지는 make_cafe_app_mac.sh 의 서명도 맥 전용이다.
#
#  사용:
#    cd ".../01 마케팅 연구소/installer"
#    chmod +x build_cafe_payload_mac.sh
#    ./build_cafe_payload_mac.sh --version 1.1.4
#
#  필요: 인터넷 연결, 빌드 맥에 Node/npm 설치(프론트 빌드용), Xcode Command Line Tools
# ============================================================
set -euo pipefail

# ── 파라미터 (윈도우판 param 블록과 같은 기본값) ──────────────
PYTHON_VERSION="3.12.8"
PBS_TAG="20241219"          # python-build-standalone 릴리스 태그
NODE_VERSION="20.18.1"
LICENSE_SERVER="https://license.blocklab.co.kr"
BACKEND_PORT="8010"         # cafe_launcher.py 의 BACKEND_PORT 와 반드시 동일
VERSION="1.0.0"             # 설치본 버전. make_cafe_app_mac.sh 와 같은 값을 쓸 것
SKIP_RUNTIME=0              # 코드만 고쳤을 때 쓰는 증분 빌드

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)        VERSION="$2"; shift 2 ;;
    --python-version) PYTHON_VERSION="$2"; shift 2 ;;
    --pbs-tag)        PBS_TAG="$2"; shift 2 ;;
    --node-version)   NODE_VERSION="$2"; shift 2 ;;
    --license-server) LICENSE_SERVER="$2"; shift 2 ;;
    --backend-port)   BACKEND_PORT="$2"; shift 2 ;;
    --skip-runtime)   SKIP_RUNTIME=1; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -25; exit 0 ;;
    *) echo "모르는 옵션: $1"; exit 1 ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "이 스크립트는 맥에서만 동작합니다. 윈도우에서는 build_cafe_payload.ps1 을 쓰세요." >&2
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(dirname "$HERE")"                       # 앱 루트(01 마케팅 연구소)
PAYLOAD="$HERE/payload_cafe_mac"
CACHE="$HERE/.cache"
RUNTIME="$PAYLOAD/runtime"
WEB_STAGE="$CACHE/cafe_web_stage_mac"          # 프론트 빌드용 임시 사본

# 애플 실리콘 / 인텔 자동 판별. 두 아키텍처의 바이너리는 섞을 수 없다.
case "$(uname -m)" in
  arm64)  PY_ARCH="aarch64-apple-darwin"; NODE_ARCH="darwin-arm64" ;;
  x86_64) PY_ARCH="x86_64-apple-darwin";  NODE_ARCH="darwin-x64"   ;;
  *) echo "지원하지 않는 아키텍처: $(uname -m)" >&2; exit 1 ;;
esac

echo "== 카페 전용판 맥 페이로드 빌드 =="
echo "Src     = $SRC"
echo "Payload = $PAYLOAD"
echo "아키텍처 = $(uname -m)  ($PY_ARCH / $NODE_ARCH)"
echo "버전     = $VERSION"

# ── 0. 초기화 ──────────────────────────────────────────────
# 기본은 전체 재빌드. --skip-runtime 이면 코드로 바뀌지 않는 runtime/ 과
# mbam-web/node_modules 만 남기고 갈아끼울 것은 전부 지운다.
# (덮어쓰기만 하면 이번 빌드에서 '빠진' 파일이 이전 것 그대로 남아 설치본에 실린다)
if [[ $SKIP_RUNTIME -eq 1 ]]; then
  [[ -d "$RUNTIME" ]] || { echo "--skip-runtime 은 이전 빌드의 runtime/ 이 있어야 합니다. 처음 한 번은 옵션 없이 실행하세요." >&2; exit 1; }
  echo "== 증분 빌드: runtime·node_modules 재사용 =="
  find "$PAYLOAD" -mindepth 1 -maxdepth 1 ! -name runtime ! -name mbam-web -exec rm -rf {} +
  if [[ -d "$PAYLOAD/mbam-web" ]]; then
    find "$PAYLOAD/mbam-web" -mindepth 1 -maxdepth 1 ! -name node_modules -exec rm -rf {} +
  fi
else
  rm -rf "$PAYLOAD"
fi
mkdir -p "$PAYLOAD" "$CACHE" "$RUNTIME"

get_file() {   # get_file <url> <out>
  if [[ -f "$2" ]]; then echo "  (캐시) $2"; return; fi
  echo "  다운로드: $1"
  curl -fL --progress-bar -o "$2" "$1"
}

# ── 1. 앱 소스 복사 (불필요한 것 제외) ─────────────────────
echo "[1/7] 앱 소스 복사..."
# rsync 제외 규칙 — 이름만 쓰면(profiles/) 트리 어느 깊이든 제외되고,
# 앞에 / 를 붙이면(/installer) 최상위 하나만 제외된다. robocopy 의 /XD 두 형태와 같다.
# ⚠ profiles/ 에는 네이버 계정별 로그인 쿠키·세션이 들어 있다. 고객 설치본에
#   들어가면 빌드 맥의 계정이 그대로 넘어간다. 절대 포함 금지.
# ⚠ *.db 도 반드시 제외한다. seo_history.db 에 등록된 네이버 계정(암호화 비밀번호)·
#   API 키·광고주 정보가 들어 있다. DB 는 첫 실행 때 새로 만들어진다.
rsync -a \
  --exclude 'profiles/' --exclude 'sessions/' \
  --exclude 'venv/' --exclude '.git/' --exclude '.claude/' \
  --exclude 'node_modules/' --exclude '__pycache__/' --exclude '.next/' \
  --exclude 'logs/' --exclude 'scratch/' --exclude 'tests/' --exclude 'cafe_dom_dumps/' \
  --exclude 'temp_images/' --exclude 'temp_clips/' --exclude 'temp_uploaded_images/' \
  --exclude 'generated_images/' --exclude 'saved_images/' \
  --exclude '/installer' --exclude '/auth_server' --exclude '/mbam-web' \
  --exclude '/db_backup_20260621' --exclude '/nodejs_qa_crawler' \
  --exclude '/chrome_extension' --exclude '/naver_place_crawler' \
  --exclude '/docs' --exclude '/build' --exclude '/dist' --exclude '/_startup_backup' \
  --exclude 'agent_config.json' --exclude '.env' --exclude 'user_settings.json' \
  --exclude '*.db' --exclude 'my-key.pem' --exclude 'deploy_aws_update.bat' \
  --exclude '*.log' --exclude '*.pyc' --exclude 'crash*.txt' --exclude 'crash*.log' \
  --exclude '*.zip' --exclude '*.exe' --exclude 'test_*.py' \
  --exclude '*.html' --exclude '*_dump.*' --exclude 'screenshot*.png' \
  --exclude 'map_screenshot.png' --exclude 'naver_shopping.png' \
  --exclude 'cli_test.json' --exclude 'crawler_test_*.json' \
  --exclude 'graphql_responses.json' --exclude 'debug_*.json' \
  "$SRC/" "$PAYLOAD/"

# ── 1-b. 최상위 정리 — 카페 전용판이 쓰지 않는 것은 전부 뺀다 ──────────
# 위 복사는 '블랙리스트' 방식이라, 저장소 루트에 새로 생긴 개발용 파일이 자동으로
# 고객 설치본까지 따라간다(루트에 .py 만 130개가 넘고 대부분 1회용 스크립트다.
# update_keys.py 처럼 앱 키가 코드에 박혀 있는 것도 있다).
# 최상위만 화이트리스트로 다시 걸러낸다. 하위 폴더(mbam_nextgen 등)는 건드리지 않는다.
KEEP_FILES=(cafe_launcher.py cafe_auth_gate.py run_backend.py cafe.ico
            license_config.json version.json package.json package-lock.json requirements.txt)
KEEP_DIRS=(mbam_nextgen licensing mbam-web runtime)

dropped=0
while IFS= read -r -d '' entry; do
  name="$(basename "$entry")"
  keep=0
  if [[ -d "$entry" ]]; then
    for k in "${KEEP_DIRS[@]}";  do [[ "$name" == "$k" ]] && keep=1 && break; done
  else
    for k in "${KEEP_FILES[@]}"; do [[ "$name" == "$k" ]] && keep=1 && break; done
  fi
  if [[ $keep -eq 0 ]]; then rm -rf "$entry"; dropped=$((dropped+1)); fi
done < <(find "$PAYLOAD" -mindepth 1 -maxdepth 1 -print0)
echo "  최상위 개발용 파일 $dropped 개 제외"

# 안전장치 — 계정 정보가 페이로드에 섞여 들어갔으면 즉시 중단한다.
# (제외 규칙이 나중에 잘못 수정돼도 고객 설치본에 로그인 정보가 나가는 일은 막는다)
# 검사 범위는 '앱 소스'로 한정한다. runtime/ 과 node_modules/ 는 레지스트리에서 받아온
# 제3자 트리라 빌드 맥의 데이터가 섞일 수 없고, anthropic SDK 의 resources/beta/sessions
# 같은 정상 모듈이 'sessions' 로 오탐된다.
leak_check() {   # leak_check <find 타입> <이름 패턴> <설명>
  local found
  found="$(find "$PAYLOAD" -type "$1" -name "$2" \
             -not -path "*/runtime/*" -not -path "*/node_modules/*" -print -quit)"
  if [[ -n "$found" ]]; then
    echo "페이로드에 '$2' 가 포함됐습니다($found). $3 빌드를 중단합니다." >&2
    exit 1
  fi
}
leak_check d 'profiles' '계정 로그인 정보가 유출될 수 있어'
leak_check d 'sessions' '계정 로그인 정보가 유출될 수 있어'
for pat in '*.db' '.env' 'agent_config.json' 'user_settings.json' 'my-key.pem'; do
  leak_check f "$pat" '계정·API 키가 유출될 수 있어'
done

# 단독 로컬 제품이라 웹 관제 에이전트는 동봉하지 않는다.
# mbam_auth_gate.py 는 풀버전의 '인증코드' 창이라 카페판(기기 승인 방식)에는 쓰이지 않는다.
# (위 화이트리스트에서 이미 걸러지지만, 규칙이 바뀌어도 남지 않도록 명시적으로 지운다)
rm -f "$PAYLOAD/agent.py" "$PAYLOAD/agent_startup.vbs" \
      "$PAYLOAD/agent_config.example.json" \
      "$PAYLOAD/mbam_launcher.py" "$PAYLOAD/mbam_auth_gate.py"

# ── 2. 프론트 스테이징 — 카페 외 화면 제거 ──────────────────
# 원본 mbam-web 은 건드리지 않는다(풀버전 개발에 그대로 쓰이므로).
# 사본을 떠서 거기서 카페와 무관한 page 폴더를 지우고 빌드한다.
echo "[2/7] 프론트 스테이징(카페 화면만 남기기)..."
WEB_SRC="$SRC/mbam-web"
# 스테이징을 비우되 node_modules 는 남겨 재사용한다(370MB 를 매번 복사하면 느리다).
if [[ -d "$WEB_STAGE" ]]; then
  find "$WEB_STAGE" -mindepth 1 -maxdepth 1 ! -name node_modules -exec rm -rf {} +
else
  mkdir -p "$WEB_STAGE"
fi
rsync -a --exclude '.next/' --exclude 'node_modules/' --exclude '.claude/'       "$WEB_SRC/" "$WEB_STAGE/"

# node_modules 는 '진짜 복사' 여야 한다. 심볼릭 링크로 걸면 Next.js(Turbopack)가
#   Symlink ... is invalid, it points out of the filesystem root
# 로 죽는다. 프로젝트 루트 밖을 가리키는 링크는 따라가지 않기 때문이다.
# (윈도우판은 디렉터리 정션이라 이 문제가 없어서 그대로 옮겼다가 여기서 터졌다)
# 이전 빌드가 남긴 심볼릭 링크는 반드시 먼저 지운다.
# [[ -d ]] 는 링크를 따라가서 '폴더가 이미 있다'고 판정하므로, 이 줄이 없으면
# 낡은 링크가 그대로 살아남아 아래 복사가 통째로 건너뛰어진다(실제로 그랬다).
if [[ -L "$WEB_STAGE/node_modules" ]]; then
  rm -f "$WEB_STAGE/node_modules"
  echo "  이전 빌드의 심볼릭 링크 제거"
fi
if [[ ! -d "$WEB_STAGE/node_modules" ]]; then
  if [[ ! -d "$WEB_SRC/node_modules" ]]; then
    ( cd "$WEB_SRC" && npm ci )
  fi
  echo "  node_modules 복사(첫 빌드만, 1~2분)..."
  rsync -a "$WEB_SRC/node_modules/" "$WEB_STAGE/node_modules/"
fi

# 카페판에서 뺄 화면들 — 사이드바에도 없고 백엔드 라우터도 마운트되지 않는다.
# (image-wash 는 cafe-image-wash 가 재export 하므로 반드시 남긴다)
DROP_PAGES=(dashboard billing blog-analysis blog-check blog-posting blog-schedule
            blogspot communication content-image-wash coupang guide hospital-blog
            place-blog place-news place-seo seo-analysis shopping
            shopping-partners-blog
            login signup            # 설치형은 회원가입·로그인 없이 바로 사용
            content-collect         # 글감수집(정부·공공 데이터) 미포함
            manuscript)             # 원고 업로드는 '카페 포스팅 > 원고 업로드'로 통합
for d in "${DROP_PAGES[@]}"; do
  if [[ -d "$WEB_STAGE/app/$d" ]]; then rm -rf "$WEB_STAGE/app/$d"; echo "  - 제외: app/$d"; fi
done

# ── 3. 프론트엔드 빌드 (카페 프로파일) ──────────────────────
echo "[3/7] 프론트엔드(Next.js) 카페 빌드..."
# NEXT_PUBLIC_PRODUCT 는 번들에 인라인되고, BACKEND_URL 은 rewrites 로
# routes-manifest.json 에 구워진다 → 둘 다 반드시 빌드 시점에 설정해야 한다.
rm -rf "$WEB_STAGE/.next"
( cd "$WEB_STAGE" && NEXT_PUBLIC_PRODUCT=cafe BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" npm run build )
# 성공 여부는 종료코드가 아니라 산출물로 판정한다(npm 은 경고를 stderr 로 내보낸다).
[[ -f "$WEB_STAGE/.next/BUILD_ID" ]] || { echo "프론트 빌드 실패 — .next/BUILD_ID 가 없습니다. 위 npm 로그를 확인하세요." >&2; exit 1; }

WEB_DST="$PAYLOAD/mbam-web"
mkdir -p "$WEB_DST"
for item in .next public package.json package-lock.json; do
  [[ -e "$WEB_STAGE/$item" ]] && rsync -a "$WEB_STAGE/$item" "$WEB_DST/"
done
# node_modules 는 원본에서 직접 복사한다(스테이징의 심볼릭 링크를 따라가면 안 되므로 원본 경로 사용)
if [[ $SKIP_RUNTIME -eq 1 && -d "$WEB_DST/node_modules" ]]; then
  echo "  (재사용) mbam-web/node_modules — 복사 생략"
else
  rsync -a "$WEB_SRC/node_modules/" "$WEB_DST/node_modules/"
fi
for cfg in "$WEB_STAGE"/next.config.*; do
  [[ -e "$cfg" ]] && cp "$cfg" "$WEB_DST/"
done

# ── 4~5. 동봉 런타임 (Python + Chromium + Node) ─────────────
# 전체 빌드 시간의 대부분이 여기다. 코드만 고쳤다면 산출물이 직전 빌드와
# 완전히 같으므로 --skip-runtime 으로 통째로 건너뛴다.
PY_EXE="$RUNTIME/python/bin/python3"

if [[ $SKIP_RUNTIME -eq 1 ]]; then
  echo "[4/7] 동봉 Python — 재사용(건너뜀)"
  echo "[5/7] 동봉 Node   — 재사용(건너뜀)"
else

  # ── 4. 동봉 Python (python-build-standalone, tkinter 포함, 재배치 가능) ──
  echo "[4/7] 동봉 Python 준비..."
  PY_ARCHIVE="$CACHE/python-$PYTHON_VERSION-$PBS_TAG-$PY_ARCH.tar.gz"
  get_file "https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG/cpython-$PYTHON_VERSION+$PBS_TAG-$PY_ARCH-install_only.tar.gz" "$PY_ARCHIVE"
  PY_TMP="$CACHE/py_extract_cafe_mac"
  rm -rf "$PY_TMP"; mkdir -p "$PY_TMP"
  tar -xzf "$PY_ARCHIVE" -C "$PY_TMP"
  rm -rf "$RUNTIME/python"
  mv "$PY_TMP/python" "$RUNTIME/python"

  echo "  파이썬 패키지 설치..."
  "$PY_EXE" -m pip install --upgrade pip

  # requirements.txt 는 개발 PC(Python 3.14)에서 뽑은 freeze 목록이라, 동봉 Python
  # ($PYTHON_VERSION)에 설치할 수 없는 항목이 섞여 있다. audioop-lts 는 3.13+ 전용이라
  # 3.12 에서는 resolver 가 통째로 실패하고 '아무 패키지도 설치되지 않는다'.
  # 게다가 이 파일은 UTF-16 으로 저장돼 있어 그냥 읽으면 깨진다 — 파이썬으로 거른다.
  echo "  requirements 필터링(동봉 Python 과 호환되지 않는 항목 제거)..."
  REQ_FILTERED="$CACHE/requirements_cafe_payload_mac.txt"
  "$PY_EXE" - "$SRC/requirements.txt" "$REQ_FILTERED" <<'PYFILTER'
import sys
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, "rb").read()
enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
lines = raw.decode(enc).splitlines()
skip = {"audioop-lts"}          # 3.13+ 전용 (3.12 에는 audioop 이 표준 라이브러리)
kept = [l for l in lines
        if l.split("=")[0].split("<")[0].split(">")[0].split("[")[0].split(";")[0].strip().lower() not in skip]
open(dst, "w", encoding="utf-8").write("\n".join(kept) + "\n")
print(f"    {len(lines)} 줄 -> {len(kept)} 줄")
PYFILTER

  "$PY_EXE" -m pip install -r "$REQ_FILTERED"
  # requirements.txt(freeze)에 빠져 있지만 실제로 쓰이는 패키지들.
  # pyperclip: 네이버 로그인 시 아이디/비번을 클립보드로 붙여넣는 데 쓴다.
  #   빠지면 기기 인증 창이 뜨자마자 닫혀 로그인을 못 한다.
  "$PY_EXE" -m pip install playwright pyperclip

  # pip 의 종료코드만 믿으면 '설치는 됐는데 고객 맥에서 안 뜨는' 설치본이 나간다.
  # 실제로 import 되는지로 확인하고, 실패하면 여기서 중단한다.
  #   - pyperclip 누락 → 기기 인증 창이 뜨자마자 닫힘
  #   - cryptography 반쯤 설치 → import jwt 실패로 백엔드가 아예 안 뜸
  #   - tkinter 누락 → 인증창·제어창이 없어 프로그램이 시작조차 못 함
  echo "  설치 검증(핵심 패키지 import)..."
  if ! "$PY_EXE" -c "import fastapi,uvicorn,sqlalchemy,pydantic,dotenv,bs4,aiohttp,apscheduler,requests,PIL,playwright,tkinter,jwt,cryptography,pyperclip;print('PKG_OK')" | grep -q PKG_OK; then
    echo "동봉 Python 패키지 설치가 불완전합니다. 위 pip 로그를 확인하세요." >&2
    echo "  (복구: \"$PY_EXE\" -m pip install --ignore-installed --no-deps <패키지>)" >&2
    exit 1
  fi
  echo "    핵심 패키지 정상"

  echo "  Chromium(Playwright) 설치..."
  PLAYWRIGHT_BROWSERS_PATH="$RUNTIME/ms-playwright" "$PY_EXE" -m playwright install chromium

  # ── 5. 동봉 Node (portable) ────────────────────────────────
  echo "[5/7] 동봉 Node 준비..."
  NODE_TGZ="$CACHE/node-v$NODE_VERSION-$NODE_ARCH.tar.gz"
  get_file "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$NODE_ARCH.tar.gz" "$NODE_TGZ"
  NODE_TMP="$CACHE/node_extract_cafe_mac"
  rm -rf "$NODE_TMP"; mkdir -p "$NODE_TMP"
  tar -xzf "$NODE_TGZ" -C "$NODE_TMP"
  rm -rf "$RUNTIME/node"
  mv "$NODE_TMP/node-v$NODE_VERSION-$NODE_ARCH" "$RUNTIME/node"

fi   # ← --skip-runtime 분기 끝 (4~5단계)

# ── 6. 라이선스 서버 설정 / 버전 ───────────────────────────
echo "[6/7] license_config.json 작성..."
cat > "$PAYLOAD/license_config.json" <<JSON
{
  "server": "$LICENSE_SERVER"
}
JSON

# 설치본의 현재 버전 — 런처가 이 값을 서버 최신 버전과 비교해 업데이트 여부를 정한다.
cat > "$PAYLOAD/version.json" <<JSON
{
  "product": "cafe-mac",
  "version": "$VERSION",
  "built_at": "$(date '+%Y-%m-%d %H:%M:%S')"
}
JSON
echo "  version.json = $VERSION"

[[ -f "$HERE/cafe.ico" ]] && cp "$HERE/cafe.ico" "$PAYLOAD/"

# ── 7. 마무리 ──────────────────────────────────────────────
echo "[7/7] 완료. payload_cafe_mac 준비됨.  ($(du -sh "$PAYLOAD" | cut -f1))"
echo
echo "다음 명령으로 앱 번들과 설치 이미지를 만드세요:"
echo "  ./make_cafe_app_mac.sh --version $VERSION"
echo
echo "※ 배포 전 license_config.json 의 server 주소가 실제 라이선스 서버인지 확인하세요."
