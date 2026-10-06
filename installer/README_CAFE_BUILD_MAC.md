# 카페 마케팅 — 맥용 설치본 만들기

윈도우판(`build_cafe_payload.ps1` + `cafe.iss` → `.exe`)에 대응하는 맥 빌드다.
결과물은 `output/카페마케팅_<버전>.dmg` 하나다.

> **맥에서만 빌드된다.** 맥용 Python·Node·Chromium 을 내려받아 설치해야 하고,
> `iconutil`·`hdiutil` 도 macOS 전용이다. 윈도우 PC 에서는 만들 수 없다.

---

## 준비 (빌드용 맥에서 한 번만)

```bash
xcode-select --install                    # iconutil, git 등
brew install node@20                      # 프론트 빌드용 (또는 nodejs.org 설치본)
node -v && npm -v
```

### 소스를 맥으로 옮기기

⚠ **카페 제품 파일은 아직 git 에 커밋돼 있지 않다.** `cafe_launcher.py`,
`cafe_auth_gate.py`, `licensing/ui_font.py`, `licensing/device_auth.py`,
`licensing/update_prompt.py`, `installer/` 의 빌드 스크립트가 전부 untracked 라
지금 `git clone` 하면 빈손으로 받는다. 먼저 커밋하거나, 폴더째 복사해야 한다.

**커밋해서 받는 경우** — `.gitattributes` 가 `.sh` 를 LF 로 보장하므로 그대로 쓰면 된다.

**폴더째 복사하는 경우**(USB·네트워크 공유) — 윈도우 작업트리는 `core.autocrlf=true`
때문에 `.sh` 가 CRLF 다. 그대로 두면 `/bin/bash^M: bad interpreter` 로 죽는다.
복사한 뒤 맥에서 한 번 돌린다:

```bash
sed -i '' 's/\r$//' installer/*.sh
chmod +x installer/*.sh
```

---

## 빌드

```bash
cd "01 마케팅 연구소/installer"
chmod +x build_cafe_payload_mac.sh make_cafe_app_mac.sh

./build_cafe_payload_mac.sh --version 1.1.4     # 페이로드 (30~50분, 약 2.4GB)
./make_cafe_app_mac.sh      --version 1.1.4     # .app + .dmg (10~20분)
```

**두 명령의 `--version` 은 반드시 같아야 한다.** 어긋나면 `make_cafe_app_mac.sh` 가
빌드를 거부한다. 이 값이 `version.json` 으로 설치본에 들어가고 런처가 서버의 최신
버전과 비교하므로, 어긋난 채 배포하면 방금 설치한 고객에게도 업데이트 안내가 뜬다.

### 코드만 고쳤을 때 (증분)

```bash
./build_cafe_payload_mac.sh --version 1.1.5 --skip-runtime
```

동봉 Python·Chromium·Node·node_modules(약 2.35GB)를 재사용한다.
**`requirements.txt` 나 `package.json` 을 고쳤거나 고객 배포본을 만들 때는 쓰지 말 것.**

### .app 만 만들어 바로 실행해 보기

```bash
./make_cafe_app_mac.sh --version 1.1.4 --skip-dmg
open ".cache/dmg_stage/카페 마케팅.app"
```

---

## 윈도우판과 다른 점

| | 윈도우 | 맥 |
|---|---|---|
| 패키징 | Inno Setup → `.exe` | `.app` 번들 → `.dmg` |
| 설치 위치 | `%LOCALAPPDATA%\Programs\MBAM-Cafe` | `/응용 프로그램/카페 마케팅.app` |
| 사용자 데이터 | `%LOCALAPPDATA%\MBAM-Cafe` | `~/Library/Application Support/MBAM-Cafe` |
| 동봉 파이썬 | `runtime\python\python.exe` | `runtime/python/bin/python3` |
| 동봉 노드 | `runtime\node\node.exe` | `runtime/node/bin/node` |
| 기기번호(HWID) | 레지스트리 MachineGuid | `IOPlatformUUID` (`ioreg`) |
| 자동 업데이트 | 있음 | **없음** (아래 참고) |

포트(8010/3010), 라이선스 서버, 기기 승인 방식은 양쪽이 같다.
기기번호는 **OS 별로 다른 값**이 나오므로, 같은 사람이 윈도우와 맥을 다 쓰면
기기를 두 개 승인해 줘야 한다.

---

## 서명·공증이 없다는 것의 의미

애플 개발자 계정(연 $99)이 없으므로 서명·공증을 못 한다. 그래서:

- 고객은 **첫 실행 때 반드시 오른쪽 클릭 → [열기]** 로 열어야 한다.
  그냥 두 번 누르면 "확인되지 않은 개발자" 라며 열리지 않는다.
  → DMG 안 `설치 방법.txt` 에 그림 없이 글로 안내해 두었다.
- 번들 안 파이썬·노드·크로미움에도 격리 딱지가 붙는다.
  → 번들 실행 스크립트가 첫 실행 때 `xattr -dr com.apple.quarantine` 로 뗀다.
- **DMG 에서 바로 실행하면 안 된다.** macOS 가 앱을 읽기 전용 임시 경로에 복사해
  띄우는데(App Translocation), 그 상태에서는 DB 도 로그인 프로필도 못 만든다.
  → `cafe_launcher.py` 의 `preflight()` 가 이 상태를 감지해 한국어로 안내한다.

개발자 계정을 나중에 등록하면 `make_cafe_app_mac.sh` 끝에 아래를 붙이면 된다.
지금은 **일부러 서명하지 않는다** — 이 앱은 실행 중에 자기 번들 안에 파일을 만들기
때문에, 서명하면 그 순간 봉인이 깨져 다음 실행 때 "손상되었기 때문에 열 수 없습니다"
가 뜬다. 서명을 도입할 거라면 먼저 데이터를 번들 밖으로 빼야 한다.

---

## 자동 업데이트

**맥에서는 꺼져 있다** (`cafe_launcher.py` 의 `_check_update()` 가 `IS_WIN` 이 아니면
바로 돌아온다). 업데이트 서버에는 윈도우 페이로드만 올라가 있어서, 맥이 그걸 받아
덮어쓰면 `runtime\python\python.exe` 같은 윈도 전용 파일로 갈아끼워져 앱이 죽는다.

맥도 자동 업데이트를 하려면:
1. 업데이트 서버에 `cafe-mac` 채널을 따로 만들고
2. `licensing/update_prompt.py` 가 제품 키에 OS 를 섞어 조회하게 고친 뒤
3. `_check_update()` 의 `if not IS_WIN: return` 를 지운다.

그전까지는 새 버전이 나오면 DMG 를 다시 내려받아 덮어 설치하도록 안내한다.
사용자 데이터는 `~/Library/Application Support/MBAM-Cafe` 에 따로 있어서
앱을 지우고 다시 깔아도 저장된 계정과 보안키는 유지된다.

---

## 막힐 만한 곳

**`pip install -r requirements.txt` 가 실패한다**
`requirements.txt` 는 윈도우 개발 PC 의 `pip freeze` 라 핀이 촘촘하다. 그 버전에
맥 arm64 휠이 없으면 소스 빌드로 넘어가 실패할 수 있다. 실패한 패키지만 핀을 풀어
(`==1.2.3` → `>=1.2`) 다시 돌린다. 끝의 import 검증이 통과하면 정상이다.

**`import tkinter` 검증에서 멈춘다**
python-build-standalone 의 맥 빌드에는 Tcl/Tk 가 들어 있다. 그래도 실패하면
`--pbs-tag` 를 최신 릴리스로 올려 다시 시도한다.

**Chromium 이 안 뜬다**
`runtime/ms-playwright` 안의 Chromium 에 격리 딱지가 남아 있을 수 있다.
`xattr -dr com.apple.quarantine "/Applications/카페 마케팅.app"` 를 직접 한 번 돌려본다.

**서버가 '준비 중' 에서 안 넘어간다**
프로그램 창의 [진단 파일 저장] → 바탕화면 `카페마케팅_진단.txt` 를 본다.
`~/Library/Application Support/MBAM-Cafe/logs/` 에 `backend.log`,
`frontend.log`, `launcher.log` 가 쌓인다.
