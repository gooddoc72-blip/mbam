# 블로그 마케팅 프로그램 — 설치본 빌드 가이드

풀버전(마케팅 연구소)에서 **블로그 부분만** 떼어낸 단독 설치형 제품입니다.
카페 전용판([README_CAFE_BUILD.md](README_CAFE_BUILD.md))과 완전히 같은 구조로,
코드베이스는 하나를 그대로 쓰고 **제품 프로파일(`blog`)** 로 기능 범위·메뉴·인증을
분리합니다. 블로그판을 따로 포크하지 않으므로 버그 수정이 세 제품에 동시에 반영됩니다.

---

## 1. 제품에 포함되는 것

| 화면 | 경로 | 비고 |
|---|---|---|
| 블로그 진단 | `/blog-check` | 블로그 지수·최적화 진단 |
| 형태소 분석 | `/blog-analysis` | 카페 분석 화면을 `channel="blog"` 로 재사용 |
| 블로그 발행 | `/blog-posting` | 다계정 순차 자동 발행 |
| 플레이스 블로그 | `/place-blog` | 블로그 발행 화면의 플레이스 모드 |
| 소통 & 이웃 | `/communication` | 서로이웃·댓글·공감 |
| 이미지 세탁소 | `/image-wash` | |
| 구글 블로그스팟 | `/blogspot` | |
| 티스토리 | `/blog-schedule?platform=tistory` | 매일 자동발행 · 1회 예약 포함 |
| 글감수집 | `/content-collect` | 매일 자동발행이 여기 카테고리를 고른다 |
| 원고관리 | `/manuscript` | 블로그 발행이 원고를 여기서 가져옴 |
| 블로그 순위추적 | `/cafe-rank?type=blog` | |
| 계정관리 | `/multi-task` | 네이버 계정 등록·기기인증 |
| 프록시 IP | `/proxy` | 댓글·공감 IP 변경용 |
| 설정 · 로그 | `/settings`, `/logs` | |

**제외**: 네이버 카페 전체, 플레이스 진단·자동화, 쇼핑/쿠팡, SEO 통검분석,
결제·플랜, 대시보드, 사용 가이드, **로그인·회원가입**(`/login`, `/signup`).

제외는 두 겹으로 막습니다.
- **프론트** — `build_blog_payload.ps1` 이 해당 `app/<page>` 폴더를 빌드 대상에서 아예 삭제 → 설치본에 파일 자체가 없음
- **백엔드** — `MBAM_PRODUCT=blog` 일 때 [main.py](../mbam_nextgen/backend/main.py) 가 블로그용 라우터만 마운트 → 주소를 직접 쳐도 404

> ⚠ `app/cafe-analysis` 폴더는 메뉴에 없어도 **지우면 안 됩니다.**
> `/blog-analysis` 가 이 페이지를 `channel="blog"` 로 재export 하기 때문에,
> 지우면 프론트 빌드가 그 자리에서 깨집니다. (`/place-blog` ↔ `blog-posting` 도 같은 관계)
> 그래서 설치본에서 `/cafe-analysis` 주소를 직접 치면 블로그판에서도 화면이 뜹니다.
> 백엔드 `seo` 라우터는 블로그판에도 마운트되므로 동작도 합니다 — 메뉴에 없을 뿐입니다.

---

## 2. 세 제품의 분리

| 항목 | 풀버전 | 카페 전용판 | 블로그 전용판 |
|---|---|---|---|
| 설치 폴더 | `%ProgramFiles%\MBAM` | `%LOCALAPPDATA%\Programs\MBAM-Cafe` | `%LOCALAPPDATA%\Programs\MBAM-Blog` |
| Inno AppId | `…MBAM00000001` | `…MBAMCAFE00001` | `…MBAMBLOG00001` |
| 백엔드 / 프론트 포트 | 8000 / 3000 | 8010 / 3010 | **8020 / 3020** |
| 런처 | `mbam_launcher.py` | `cafe_launcher.py` | `blog_launcher.py` |
| 인증 방식 | 인증코드 입력 | 기기 승인 | **기기 승인 (크롤러와 동일)** |
| 인증 제품 코드 | — | `cafe` | **`blog`** |
| 인증 캐시 | `%LOCALAPPDATA%\MBAM\license.json` | `…\MBAM\device_cafe.json` | `…\MBAM\device_blog.json` |
| 보안키·로그 | `…\MBAM` | `…\MBAM-Cafe` | `…\MBAM-Blog` |
| 아이콘 | `mbam.ico` | `cafe.ico` (녹색 커피잔) | `blog.ico` (파란 종이+펜) |

AppId·설치폴더·포트가 전부 다르므로 **한 PC 에 셋 다 설치해도 서로 간섭하지 않습니다.**

포트를 바꾸려면 [blog_launcher.py](../blog_launcher.py) 의 `BACKEND_PORT` 와
`build_blog_payload.ps1 -BackendPort` 를 **함께** 바꿔야 합니다. 프론트의 `/api` 프록시 대상은
빌드 시점에 `routes-manifest.json` 으로 구워지기 때문입니다.

---

## 3. 빌드 순서

```powershell
cd "F:\02 마케팅 프로그램\01 마케팅 연구소\installer"

# 1) 페이로드 (동봉 Python + Node + Chromium + 블로그 전용 프론트 빌드)
powershell -ExecutionPolicy Bypass -File build_blog_payload.ps1 -Version 1.0.0

# 2) 설치파일 컴파일 → output\BlogMarketing_Setup_1.0.0.exe
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" blog.iss
```

> `-Version` 은 `blog.iss` 의 `MyAppVersion` 과 **반드시 같아야** 합니다.
> 어긋나면 방금 설치한 고객에게도 업데이트 안내가 뜹니다.
>
> 코드만 고쳤다면 `-SkipRuntime` 으로 20분대 → 4분대로 줄일 수 있습니다.
> (requirements.txt / package.json 을 바꿨거나 고객 배포본을 만들 때는 쓰지 마세요)
>
> 압축(LZMA2/max)에 시간이 걸립니다 — 페이로드가 2GB 대라 10~30분 정도 봅니다.

### 아이콘

전용 아이콘 `blog.ico` 는 [make_blog_icon.py](make_blog_icon.py) 가 생성합니다
(둥근 사각형 + 종이·펜, 브랜드 파랑 · 16/24/32/48/64/128/256px 7종 포함).

```powershell
python make_blog_icon.py --preview      # 시안 비교 PNG (파일 안 건드림)
python make_blog_icon.py --variant A    # 골라서 blog.ico 생성
```

작은 크기에서 뭉개지지 않도록 크기별로 디테일을 다르게 그립니다:
48px 이상은 종이+글줄+펜, 32px 는 종이+펜, 24px 이하는 펜만 크게.

카페판(녹색 커피잔)과 **작업표시줄에서 한눈에 구분되도록** 색과 형태를 모두 다르게 했습니다.

빌드 PC 요구사항: 인터넷 연결, Node/npm 설치(프론트 빌드용), Inno Setup 6.

> 스크립트는 원본 `mbam-web` 을 건드리지 않습니다. `.cache\blog_web_stage` 에 사본을 뜨고
> (node_modules 는 정션으로 연결) 거기서 페이지를 지운 뒤 빌드합니다.
>
> ⚠ **빌드 중에는 `mbam-web` 개발 서버(`npm run dev`)와 카페판 빌드를 동시에 돌리지 마세요.**
> 스테이징 사본이 원본 `node_modules` 를 공유하기 때문에 Turbopack 캐시가 겹쳐 빌드가 실패합니다.

### 페이로드에 절대 들어가면 안 되는 것

카페판과 동일합니다. `mbam_nextgen\profiles\` 에는 **네이버 계정별 로그인 세션(쿠키)** 이,
`*.db` 에는 **암호화된 계정 비밀번호와 API 키** 가 들어 있습니다. 소스 복사 단계에서
이름 기준으로 제외하고, 복사 직후 한 번 더 검사해 발견되면 **빌드를 중단**합니다.
(`.env`, `agent_config.json`, `user_settings.json`, `my-key.pem` 도 제외)

---

## 4. 인증 — 기기 승인 방식 (크롤링 프로그램·카페판과 동일)

**인증코드를 발급하지 않습니다.** 고객이 실행하면 PC 기기번호가 자동으로 잡히고,
관리자가 승인해 주면 열립니다.

```
[고객] 프로그램 실행
   → 미등록 PC 면 인증창이 뜸 (기기번호 표시 + 이름/소속 입력)
   → [승인 요청하기] 클릭
[관리자] 관리자_승인도구.exe 실행 → 목록 새로고침
   → 제품이 "블로그 마케팅" 인 행 선택 → [✅ 선택 기기 승인]
[고객] 인증창의 [다시 확인] 클릭 (또는 프로그램 재실행) → 바로 열림
```

승인은 **제품별로 분리**됩니다. 같은 PC 가 크롤러·카페판으로 이미 승인돼 있어도
블로그판은 따로 승인받아야 하고, 서로 영향을 주지 않습니다.

**라이선스 서버는 손댈 필요가 없습니다.** `product_devices` 테이블이 `(hwid, product)`
조합을 그대로 받으므로 `blog` 도 추가 작업 없이 동작합니다. 다만
[admin_tool.py](../admin_tool.py) 에 제품 이름(`blog` → "블로그 마케팅")을 추가했으니
**관리자_승인도구는 다시 빌드·배포**해야 목록에 "블로그 마케팅" 으로 표시됩니다.
(재빌드 전에도 승인 자체는 가능하지만 제품 칸에 `blog` 라고만 나옵니다)

---

## 4-1. 보안키 (JWT_SECRET / ENV_CIPHER_KEY)

개발용 `.env` 는 운영자의 API 키가 들어 있어 설치본에 넣지 않습니다. 대신
[blog_launcher.py](../blog_launcher.py) 가 최초 실행 때 이 PC 전용 키를 만들어
`%LOCALAPPDATA%\MBAM-Blog\secrets.env` 에 저장하고, 이후 계속 재사용합니다.

| 키 | 용도 | 없어지면 |
|---|---|---|
| `JWT_SECRET` | 로그인 토큰 서명 | 백엔드가 기동 자체를 거부 |
| `ENV_CIPHER_KEY` | 저장된 네이버 계정 비밀번호 암호화 | **기존에 저장한 비밀번호를 복호화 못 함** |

설치 폴더가 아니라 사용자 폴더에 두므로 **프로그램을 다시 설치해도 유지**됩니다.

---

## 5. 고객 최초 실행 흐름

1. 바탕화면 아이콘 실행 → **기기 승인 요청 창** (기기번호 + 이름/소속)
2. `[승인 요청하기]` → 관리자 승인 → `[다시 확인]`
3. 백엔드(8020)·프론트(3020) 자동 기동 → 브라우저 자동 열림 (`/blog-posting`)
4. `[설정]` 에서 AI API 키 입력, `[계정관리]` 에서 네이버 계정 등록·기기인증
5. 댓글·공감에 IP 변경을 쓰려면 `[프록시 IP]` 에 프록시 서버 등록

한 번 승인된 뒤에는 실행할 때마다 조용히 확인만 하고 바로 열립니다.
인터넷이 끊긴 상태에서는 마지막 확인 후 7일까지 실행됩니다.

---

## 6. 업데이트 배포 (부분 패키지)

설치본 2.4GB 중 실제로 바뀌는 건 파이썬 소스와 프론트 빌드뿐이라 전체를 다시 받게 하지 않습니다.

```powershell
# 1) 페이로드를 새 버전으로 다시 만든다 (런타임은 재사용)
powershell -File build_blog_payload.ps1 -SkipRuntime -Version 1.0.1

# 2) 바뀐 부분만 zip 으로 묶는다  ← -Product blog 를 반드시 붙인다
powershell -File 업데이트_패키지_만들기.ps1 -Product blog -Version 1.0.1 -Notes "발행 오류 수정"

# 3) 나오는 blog-1.0.1.zip · blog-latest.json 을 서버에 올린다
#    (저장소 루트의 '업데이트_서버에올리기.bat')
```

`-Product blog` 를 빠뜨리면 카페 페이로드(`payload_cafe`)를 묶어 **카페 고객에게
블로그 빌드가 배포됩니다.** 버전 불일치 검사가 대부분 걸러주지만, 두 제품의 버전이
우연히 같으면 통과하므로 항상 명시하세요.

---

## 7. 스케줄러 — 블로그판이 거는 잡

설치형은 고객 PC 에서 새벽에 브라우저를 띄워 네이버를 긁습니다. 화면조차 없는 기능의
일괄분석을 걸어두면 고객 PC 만 축냅니다. `MBAM_PRODUCT=blog` 일 때 등록되는 잡은 아래뿐입니다.

| 잡 | 블로그판 | 카페판 | 풀버전 |
|---|---|---|---|
| 블로그 매일 자동발행 · 1회 예약 | ✅ | ❌ | ✅ |
| 글감 자동수집 | ✅ | ❌ | ✅ |
| 블로그스팟 일괄분석 | ✅ | ❌ | ✅ |
| 카페 예약 육성 | ✅(비어 있음) | ✅ | ✅ |
| 플레이스 · 쇼핑 일괄분석 | ❌ | ❌ | ✅ |
