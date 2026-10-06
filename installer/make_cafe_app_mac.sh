#!/bin/bash
# ============================================================
#  네이버 카페 마케팅 프로그램 — .app 번들 + .dmg 설치 이미지 생성
#
#  cafe.iss(Inno Setup)가 하던 일의 맥 버전이다.
#  반드시 build_cafe_payload_mac.sh 를 먼저 실행해 payload_cafe_mac/ 을 만들 것.
#
#  사용:
#    ./make_cafe_app_mac.sh --version 1.1.4
#
#  결과: output/카페마케팅_1.1.4.dmg
# ============================================================
set -euo pipefail

VERSION="1.0.0"
ICON_VARIANT="D"        # cafe.ico 와 같은 시안(윈도우판이 D 를 쓰고 있다)
SKIP_DMG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)      VERSION="$2"; shift 2 ;;
    --icon-variant) ICON_VARIANT="$2"; shift 2 ;;
    --skip-dmg)     SKIP_DMG=1; shift ;;      # .app 만 만들어 바로 실행해 볼 때
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -14; exit 0 ;;
    *) echo "모르는 옵션: $1"; exit 1 ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || { echo "맥에서만 동작합니다." >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="$HERE/payload_cafe_mac"
OUTPUT="$HERE/output"
STAGE="$HERE/.cache/dmg_stage"
APP_NAME="카페 마케팅"
BUNDLE="$STAGE/$APP_NAME.app"
EXEC_NAME="cafe-marketing"        # 번들 실행 파일 이름(공백·한글 없이 — 셸에서 다루기 쉽게)

[[ -d "$PAYLOAD" ]] || { echo "payload_cafe_mac 이 없습니다. build_cafe_payload_mac.sh 를 먼저 실행하세요." >&2; exit 1; }
[[ -f "$PAYLOAD/cafe_launcher.py" ]] || { echo "페이로드가 불완전합니다(cafe_launcher.py 없음)." >&2; exit 1; }

# 페이로드 버전과 어긋나면 설치 직후 고객에게 업데이트 안내가 뜬다. 미리 막는다.
PAYLOAD_VER="$(/usr/bin/python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$PAYLOAD/version.json" 2>/dev/null || echo "?")"
if [[ "$PAYLOAD_VER" != "$VERSION" ]]; then
  echo "버전이 어긋납니다 — payload=$PAYLOAD_VER, 이번 실행=$VERSION" >&2
  echo "  build_cafe_payload_mac.sh --version $VERSION 로 페이로드를 다시 만드세요." >&2
  exit 1
fi

echo "== 카페 마케팅 맥 앱 번들 생성 (v$VERSION) =="
rm -rf "$STAGE"; mkdir -p "$STAGE" "$OUTPUT"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources"

# ── 1. 아이콘 (.icns) ──────────────────────────────────────
echo "[1/5] 아이콘 생성..."
if [[ ! -d "$HERE/cafe.iconset" ]]; then
  # Pillow 가 있는 파이썬으로 만든다 — 동봉 파이썬에 이미 들어 있다.
  "$PAYLOAD/runtime/python/bin/python3" "$HERE/make_cafe_icon.py" --iconset "$ICON_VARIANT"
fi
iconutil -c icns "$HERE/cafe.iconset" -o "$BUNDLE/Contents/Resources/cafe.icns"

# ── 2. 앱 소스 배치 ────────────────────────────────────────
# 페이로드 전체를 Contents/Resources/app 에 넣는다.
# ⚠ 이 프로그램은 실행 중에 자기 폴더 안에 파일을 만든다(SQLite DB, 네이버 로그인
#   프로필, 임시 이미지). 그래서 번들을 '응용 프로그램' 폴더처럼 쓸 수 있는 곳에
#   두어야 하고, 코드 서명은 하지 않는다 — 서명하면 프로그램이 자기 번들을 고치는
#   순간 봉인이 깨져 다음 실행 때 '손상되었기 때문에 열 수 없습니다' 가 뜬다.
#   (윈도우판이 Program Files 대신 사용자 폴더에 설치하는 것과 같은 이유다)
echo "[2/5] 앱 소스 배치... ($(du -sh "$PAYLOAD" | cut -f1))"
rsync -a "$PAYLOAD/" "$BUNDLE/Contents/Resources/app/"

# ── 3. 번들 실행 파일 ──────────────────────────────────────
echo "[3/5] 실행 스크립트 작성..."
cat > "$BUNDLE/Contents/MacOS/$EXEC_NAME" <<'LAUNCHER'
#!/bin/bash
# 카페 마케팅 — .app 번들 진입점.
# 동봉 파이썬으로 cafe_launcher.py 를 띄운다. 나머지는 전부 파이썬 쪽에서 한다.
BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$BUNDLE/Contents/Resources/app"
PYBIN="$APP/runtime/python/bin/python3"

LOG_DIR="$HOME/Library/Application Support/MBAM-Cafe/logs"
mkdir -p "$LOG_DIR"

alert() {   # 파이썬이 뜨기도 전에 실패하면 보여줄 것이 이것뿐이다
  /usr/bin/osascript -e "display alert \"카페 마케팅\" message \"$1\" as critical" >/dev/null 2>&1
}

# 서명·공증이 없어서 내려받은 파일에 '격리(quarantine)' 딱지가 붙는다. 그대로 두면
# 동봉 파이썬·노드·크로미움을 실행할 때마다 macOS 가 차단한다. 딱지가 있을 때만 뗀다
# (2.4GB 를 매번 훑으면 시작이 느려진다).
if xattr -p com.apple.quarantine "$BUNDLE" >/dev/null 2>&1 \
   || xattr -p com.apple.quarantine "$PYBIN" >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$BUNDLE" >/dev/null 2>&1 || true
fi

if [ ! -x "$PYBIN" ]; then
  alert "동봉된 파이썬을 찾을 수 없습니다.\n설치가 덜 됐을 수 있습니다. 프로그램을 다시 설치해 주세요."
  exit 1
fi

cd "$APP" || exit 1
# exec 로 바꿔치기해야 Dock 아이콘과 메뉴 이름이 이 앱 것으로 나온다
# (그냥 실행하면 파이썬이 별개 프로그램으로 잡혀 이름 없는 아이콘이 하나 더 뜬다).
exec "$PYBIN" "$APP/cafe_launcher.py" >>"$LOG_DIR/launcher.log" 2>&1
LAUNCHER
chmod +x "$BUNDLE/Contents/MacOS/$EXEC_NAME"

# ── 4. Info.plist ─────────────────────────────────────────
echo "[4/5] Info.plist 작성..."
cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>              <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>       <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>        <string>kr.marketlabs.cafe</string>
    <key>CFBundleExecutable</key>        <string>$EXEC_NAME</string>
    <key>CFBundleIconFile</key>          <string>cafe</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>CFBundleVersion</key>           <string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>    <string>11.0</string>
    <key>LSApplicationCategoryType</key> <string>public.app-category.business</string>
    <key>NSHighResolutionCapable</key>   <true/>
    <!-- 이 앱은 창을 띄우는 정식 앱이다(백그라운드 전용 아님) -->
    <key>LSUIElement</key>               <false/>
</dict>
</plist>
PLIST
plutil -lint "$BUNDLE/Contents/Info.plist" >/dev/null

# 번들을 방금 만들었으므로 Finder 가 예전 아이콘을 기억하지 않도록 갱신 시각을 올린다
touch "$BUNDLE"

if [[ $SKIP_DMG -eq 1 ]]; then
  echo "[5/5] --skip-dmg — 앱 번들만 만들었습니다:"
  echo "  $BUNDLE"
  exit 0
fi

# ── 5. DMG 설치 이미지 ─────────────────────────────────────
echo "[5/5] DMG 생성... (2GB 대를 압축하므로 10분 이상 걸릴 수 있습니다)"
ln -s /Applications "$STAGE/응용 프로그램"
cat > "$STAGE/설치 방법.txt" <<'GUIDE'
카페 마케팅 — 맥 설치 방법
================================

1. 왼쪽의 [카페 마케팅] 아이콘을 오른쪽 [응용 프로그램] 폴더로 끌어다 놓으세요.

2. '응용 프로그램' 폴더를 열고, [카페 마케팅] 아이콘을
   >> 마우스 오른쪽 버튼 << 으로 눌러 [열기] 를 선택하세요.
   (그냥 두 번 눌러서 여는 것과 다릅니다. 처음 한 번만 이렇게 하면 됩니다)

3. "확인되지 않은 개발자..." 경고가 뜨면 [열기] 를 누르세요.
   애플 개발자 등록을 하지 않은 프로그램에 뜨는 안내로, 이상이 있는 것이 아닙니다.

4. 처음 실행하면 '기기번호'가 적힌 창이 뜹니다.
   그 번호를 관리자에게 알려주시면 승인해 드립니다.

문제가 생기면
--------------
프로그램 창의 [진단 파일 저장] 을 누르면 바탕화면에
'카페마케팅_진단.txt' 가 만들어집니다. 그 파일을 보내주세요.
GUIDE

DMG_OUT="$OUTPUT/카페마케팅_$VERSION.dmg"
rm -f "$DMG_OUT"
hdiutil create \
  -volname "$APP_NAME $VERSION" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$DMG_OUT"

echo
echo "완료: $DMG_OUT  ($(du -sh "$DMG_OUT" | cut -f1))"
echo
echo "※ 이 DMG 는 애플 서명·공증이 없습니다. 고객은 첫 실행 때 반드시"
echo "  오른쪽 클릭 > 열기 로 열어야 합니다(DMG 안 '설치 방법.txt' 에 안내됨)."
