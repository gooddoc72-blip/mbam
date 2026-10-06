# 네이버 카페 마케팅 프로그램 — 설치본 빌드 가이드

풀버전(마케팅 연구소)에서 **네이버 카페 부분만** 떼어낸 단독 설치형 제품입니다.

> 같은 구조의 자매 제품이 있습니다 — 블로그 전용판은 [README_BLOG_BUILD.md](README_BLOG_BUILD.md) 를 보세요.
> 제품 프로파일(`cafe` / `blog`)만 다르고 빌드·인증·업데이트 방식은 동일합니다.
코드베이스는 하나를 그대로 쓰고, **제품 프로파일(`cafe`)** 로 기능 범위·메뉴·인증코드를
분리합니다. 카페판을 따로 포크하지 않으므로 버그 수정이 양쪽에 동시에 반영됩니다.

---

## 1. 제품에 포함되는 것

| 화면 | 경로 | 비고 |
|---|---|---|
| 카페 형태소 분석 | `/cafe-analysis` | URL 권위 분석 + 본문 해부 분석 |
| 카페 포스팅 | `/cafe-auto` | 발행 / 육성(댓글·공감) 탭 |
| 이미지 세탁소 | `/cafe-image-wash` | |
| 카페 순위추적 | `/cafe-rank?type=cafe` | |
| 원고관리 | `/manuscript` | 카페 포스팅이 원고를 여기서 가져옴 |
| 계정관리 | `/multi-task` | 네이버 계정 등록·기기인증 |
| 프록시 IP | `/proxy` | 댓글·공감 IP 변경용 |
| 설정 · 로그 | `/settings`, `/logs` | |

**제외**: 블로그 전체, 플레이스, 쇼핑/쿠팡, SEO 통검분석, 블로그스팟/티스토리, 결제·플랜, 대시보드,
**글감수집**(`/content-collect`), **로그인·회원가입**(`/login`, `/signup`), **사용 가이드**(`/guide`).

> 글감수집은 제거되었습니다. 카페 포스팅 화면 안에 있던 "글감에서 가져오기" 선택지도 함께 빠지고,
> 원고관리(`/manuscript`)만 남습니다.
>
> `/guide` 는 클라우드 에이전트 사용법을 설명하는 문서라 단독 설치판에는 맞지 않아 제외했습니다.

제외는 두 겹으로 막습니다.
- **프론트** — `build_cafe_payload.ps1` 이 해당 `app/<page>` 폴더를 빌드 대상에서 아예 삭제 → 설치본에 파일 자체가 없음
- **백엔드** — `MBAM_PRODUCT=cafe` 일 때 [main.py](../mbam_nextgen/backend/main.py) 가 카페용 라우터만 마운트 → 주소를 직접 쳐도 404

---

## 2. 풀버전과의 분리

| 항목 | 풀버전 | 카페 전용판 |
|---|---|---|
| 설치 폴더 | `%ProgramFiles%\MBAM` | `%ProgramFiles%\MBAM-Cafe` |
| Inno AppId | `…MBAM00000001` | `…MBAMCAFE00001` |
| 백엔드 / 프론트 포트 | 8000 / 3000 | **8010 / 3010** |
| 런처 | `mbam_launcher.py` | `cafe_launcher.py` |
| 인증 방식 | 인증코드 입력 | **기기 승인 (크롤러와 동일)** |
| 인증 제품 코드 | — | **`cafe`** |
| 인증 캐시 | `%LOCALAPPDATA%\MBAM\license.json` | `%LOCALAPPDATA%\MBAM\device_cafe.json` |
| 로그 | `%LOCALAPPDATA%\MBAM\logs` | `%LOCALAPPDATA%\MBAM-Cafe\logs` |

포트를 바꾸려면 [cafe_launcher.py](../cafe_launcher.py) 의 `BACKEND_PORT` 와
`build_cafe_payload.ps1 -BackendPort` 를 **함께** 바꿔야 합니다. 프론트의 `/api` 프록시 대상은
빌드 시점에 `routes-manifest.json` 으로 구워지기 때문입니다.

---

## 3. 빌드 순서

```powershell
cd "F:\02 마케팅 프로그램\01 마케팅 연구소\installer"

# 1) 페이로드 (동봉 Python + Node + Chromium + 카페 전용 프론트 빌드)
powershell -ExecutionPolicy Bypass -File build_cafe_payload.ps1

# 2) 설치파일 컴파일 → output\CafeMarketing_Setup_1.0.0.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" cafe.iss
```

> Inno Setup 이 사용자 폴더(`%LOCALAPPDATA%\Programs\Inno Setup 6`)에 설치돼 있습니다.
> `C:\Program Files (x86)\Inno Setup 6` 에 있는 PC 라면 그 경로를 쓰세요.
> 없으면 `winget install JRSoftware.InnoSetup` 으로 설치합니다.
>
> 압축(LZMA2/max)에 시간이 걸립니다 — 페이로드가 2GB 대라 10~30분 정도 봅니다.

### 아이콘

전용 아이콘 `cafe.ico` 는 [make_cafe_icon.py](make_cafe_icon.py) 가 생성합니다
(둥근 사각형 + 커피잔, 브랜드 녹색 · 16/24/32/48/64/128/256px 7종 포함).

```powershell
python make_cafe_icon.py --preview      # 시안 비교 PNG (파일 안 건드림)
python make_cafe_icon.py --variant D    # 골라서 cafe.ico 생성
```

색·형태를 바꾸려면 스크립트 안의 `VARIANTS` 값을 고치고 `--preview` 로 확인한 뒤 다시 생성하세요.
아이콘은 세 곳에 쓰입니다 — 설치 마법사 exe(`SetupIconFile`), 바로가기(`IconFilename`),
[프로그램 추가/제거] 목록(`UninstallDisplayIcon`).

작은 크기에서 뭉개지지 않도록 크기별로 디테일을 다르게 그립니다:
48px 이상은 김+받침, 32px 는 받침만, 24px 이하는 잔만 크게.

빌드 PC 요구사항: 인터넷 연결, Node/npm 설치(프론트 빌드용), Inno Setup 6.

> 스크립트는 원본 `mbam-web` 을 건드리지 않습니다. `.cache\cafe_web_stage` 에 사본을 뜨고
> (node_modules 는 정션으로 연결) 거기서 페이지를 지운 뒤 빌드합니다.
>
> ⚠ **빌드 중에는 `mbam-web` 개발 서버(`npm run dev`)를 꺼 두세요.** 스테이징 사본이
> 원본 `node_modules` 를 공유하기 때문에, 동시에 돌리면 Turbopack 캐시가 겹쳐 빌드가 실패합니다.

### 페이로드에 절대 들어가면 안 되는 것

`mbam_nextgen\profiles\` 에는 **네이버 계정별 로그인 세션(쿠키)** 이 들어 있습니다.
빌드 PC 에서 기기인증한 계정들이 그대로 고객 설치본에 실릴 수 있어, 소스 복사 단계에서
`profiles`·`sessions` 를 이름 기준으로 제외하고, 복사 직후 한 번 더 검사해
발견되면 **빌드를 중단**합니다. (`.env`, `agent_config.json`, `license.db`, `my-key.pem` 도 제외)

robocopy 의 `/XD` 는 **전체 경로를 주면 그 경로 하나만** 제외합니다. `profiles` 는 최상위가
아니라 `mbam_nextgen\` 아래에 있으므로 반드시 **이름으로** 제외해야 합니다.

---

## 4. 인증 — 기기 승인 방식 (크롤링 프로그램과 동일)

**인증코드를 발급하지 않습니다.** 고객이 실행하면 PC 기기번호가 자동으로 잡히고,
관리자가 승인해 주면 열립니다.

```
[고객] 프로그램 실행
   → 미등록 PC 면 인증창이 뜸 (기기번호 표시 + 이름/소속 입력)
   → [승인 요청하기] 클릭
[관리자] 관리자_승인도구.exe 실행 → 목록 새로고침
   → 제품이 "카페 마케팅" 인 행 선택 → [✅ 선택 기기 승인]
[고객] 인증창의 [다시 확인] 클릭 (또는 프로그램 재실행) → 바로 열림
```

승인은 **제품별로 분리**됩니다. 같은 PC 가 크롤러로 이미 승인돼 있어도 카페판은 따로
승인받아야 하고, 카페판 승인이 크롤러 쪽에 영향을 주지도 않습니다.

**서버 변경사항** — 라이선스 서버를 먼저 재배포해야 합니다.
- 신규 테이블 `product_devices` (`hwid` + `product` 조합으로 관리). 기존 `devices` 테이블은
  건드리지 않으므로 **크롤러는 지금 그대로 동작**합니다.
- `/verify`·`/request_approval` 에 `product` 필드가 추가됐습니다. 안 보내면 기존 동작 그대로라
  구버전 클라이언트도 문제없습니다.
- `/admin/devices` 가 두 테이블을 합쳐 돌려주고, 각 행에 `product` 가 붙습니다.
- `/admin/device/status` 는 `product` 를 같이 받아 올바른 쪽을 수정합니다.

관리자_승인도구([admin_tool.py](../admin_tool.py))에 **제품** 컬럼이 추가되었습니다.
서버를 올린 뒤 이 도구도 다시 배포(재빌드)해야 카페 승인 요청이 보입니다.

---

## 4-1. 보안키 (JWT_SECRET / ENV_CIPHER_KEY)

개발용 `.env` 는 운영자의 API 키가 들어 있어 설치본에 넣지 않습니다. 대신
[cafe_launcher.py](../cafe_launcher.py) 가 최초 실행 때 이 PC 전용 키를 만들어
`%LOCALAPPDATA%\MBAM-Cafe\secrets.env` 에 저장하고, 이후 계속 재사용합니다.

| 키 | 용도 | 없어지면 |
|---|---|---|
| `JWT_SECRET` | 로그인 토큰 서명 | 백엔드가 기동 자체를 거부 |
| `ENV_CIPHER_KEY` | 저장된 네이버 계정 비밀번호 암호화 | **기존에 저장한 비밀번호를 복호화 못 함** |

설치 폴더(Program Files)가 아니라 사용자 폴더에 두므로 **프로그램을 다시 설치해도 유지**됩니다.
고객에게 "이 파일은 지우지 마세요, PC 교체 시 옮기면 계정 재입력이 필요 없습니다" 라고 안내하면 됩니다.

---

## 5. 고객 최초 실행 흐름

1. 바탕화면 아이콘 실행 → **기기 승인 요청 창** (기기번호 + 이름/소속)
2. `[승인 요청하기]` → 관리자 승인 → `[다시 확인]`
3. 백엔드(8010)·프론트(3010) 자동 기동 → 브라우저 자동 열림
4. `[설정]` 에서 AI API 키 입력, `[계정관리]` 에서 네이버 계정 등록·기기인증
5. 댓글·공감에 IP 변경을 쓰려면 `[프록시 IP]` 에 프록시 서버 등록

한 번 승인된 뒤에는 실행할 때마다 조용히 확인만 하고 바로 열립니다.
인터넷이 끊긴 상태에서는 마지막 확인 후 7일까지 실행됩니다.

---

## 6. 프록시 IP 댓글·공감

`카페 포스팅 > 육성` 탭의 **🛡 프록시로 IP 변경** 옵션입니다.

- 계정마다 프록시가 배정되어 **각 계정이 서로 다른 IP** 로 댓글·공감을 남깁니다.
- 배정은 **계정 고정(sticky)** — 같은 계정은 항상 같은 IP 로 접속합니다.
  계정 IP 가 매번 튀면 네이버가 이상 접속으로 잡기 때문입니다.
- 등록된 프록시 수가 계정 수보다 적으면 일부 계정이 IP 를 공유합니다.
- 등록된 프록시가 없으면 경고를 남기고 현재 PC IP 로 진행합니다.
- 작업 로그에 계정별로 `🛡 프록시 적용: …` / `🌐 현재 IP: … (프록시 경유)` 가 찍혀
  실제 적용 여부를 눈으로 확인할 수 있습니다.
