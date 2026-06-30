# 웹 배포 가이드 (Railway 백엔드 + Vercel 프론트)

분석/계정/관리 부분을 웹에 올립니다. **자동화(네이버 발행·댓글·IP변경)는 클라우드에서 돌리지 않습니다** — 설치형 몫.

```
[브라우저] → Vercel(mbam-web, Next.js) ──/api/* rewrite 프록시──▶ Railway(FastAPI) ──▶ Railway Postgres
```
rewrite 프록시 덕분에 프론트·백엔드가 같은 출처처럼 보여 **쿠키/CORS 문제가 없습니다.**

---

## 준비물
- GitHub 저장소(이 코드) push
- Railway 계정 (railway.app) — 백엔드 + Postgres
- Vercel 계정 (vercel.com) — 프론트

---

## A. 백엔드 + DB → Railway

### 1) 프로젝트 생성
1. Railway → **New Project → Deploy from GitHub repo** → 이 저장소 선택
2. 루트의 `Dockerfile` 을 자동 인식해 빌드합니다. (Playwright 포함 이미지)

### 2) Postgres 추가
- 같은 프로젝트에서 **New → Database → PostgreSQL** 추가
- 백엔드 서비스 Variables 에 `DATABASE_URL` 을 Postgres 의 값으로 연결
  (Railway: `${{Postgres.DATABASE_URL}}` 참조 변수 사용)

### 3) 환경변수(Variables) 설정
| 변수 | 필수 | 설명 |
|---|---|---|
| `DATABASE_URL` | ✅ | Postgres 연결 (위에서 연결). `postgresql://...` |
| `JWT_SECRET` | ✅ | 로그인 토큰 서명키 (길게). 없으면 백엔드가 안 뜸 |
| `ENV_CIPHER_KEY` | ✅ | 자격증명 암호화키 (Fernet 키 권장) |
| `SUPER_ADMIN_ID` | ✅ | 관리자 로그인 ID |
| `SUPER_ADMIN_PW` | ✅ | 관리자 로그인 PW |
| `ALLOWED_ORIGINS` | ✅ | Vercel 프론트 주소 (예: `https://mbam.vercel.app`) |
| `FRONTEND_URL` | ⭕ | 소셜로그인 리다이렉트용 (Vercel 주소) |
| `BASE_URL` | ⭕ | 백엔드 공개주소 (소셜 콜백용) |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` | ⭕ | AI 분석/생성용 |
| `NAVER_CLIENT_ID` 등 | ⭕ | 네이버 검색량/소셜로그인용 |
| `PORT` | 자동 | Railway 가 주입 → run_backend.py 가 읽음 |

> `JWT_SECRET`/`ENV_CIPHER_KEY` 는 로컬 `.env` 값을 재사용하거나 새로 생성. (클라우드는 새 DB 라 새 키도 무방)
> 새 Fernet 키 생성: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`

### 4) 배포 & 확인
- 배포 후 도메인 생성 (Settings → Networking → Generate Domain) → 예: `https://mbam-backend.up.railway.app`
- 확인: `https://mbam-backend.up.railway.app/docs` 가 열리면 OK

---

## B. 프론트 → Vercel

### 1) 프로젝트 임포트
1. Vercel → **Add New → Project** → 같은 GitHub 저장소 선택
2. **Root Directory = `mbam-web`** 로 지정 (중요)
3. Framework: Next.js 자동 감지

### 2) 환경변수
| 변수 | 값 |
|---|---|
| `BACKEND_URL` | Railway 백엔드 주소 (예: `https://mbam-backend.up.railway.app`) |

→ `next.config.mjs` 의 rewrite 가 `/api/*` 를 이 주소로 프록시합니다.

### 3) 배포
- Deploy → 도메인 생성 (예: `https://mbam.vercel.app`)
- 이 주소를 Railway 의 `ALLOWED_ORIGINS`(및 `FRONTEND_URL`)에 넣었는지 확인

---

## C. 첫 동작 확인
1. `https://mbam.vercel.app/signup` → 회원가입 → 5일 체험 시작
2. 로그인 → "마케팅 연구소" 화면 진입
3. 관리자: `SUPER_ADMIN_ID/PW` 로 로그인 → `/admin` → **요금제 관리에서 계정수·일일한도 설정** 확인
4. 분석 기능(SEO/플레이스 등) 시도

> ⚠️ 네이버 스크래핑(분석)은 클라우드 데이터센터 IP 라 일부 차단/캡차가 날 수 있습니다.
> 분석까지 안정적으로 하려면 백엔드에도 프록시를 물리거나, 분석을 설치형에서 돌리는 방안을 검토하세요.

---

## D. 개발 루프 (권장)
- **코드 수정·테스트는 로컬에서** (localhost:3000 / 8000) 빠르게
- 확인되면 `git push` → Railway/Vercel 자동 재배포
- 배포본에서 직접 개발하지 말 것 (느리고 디버깅 어려움)

---

## 안 올라가는 것 (의도된 제외)
- 자동화 실행부(블로그/카페 발행·댓글, IP변경) = 설치형에서. `.dockerignore` 가 installer/launcher/auth_server 등 제외.
- 클라우드 백엔드는 **분석·계정·관리·한도** 담당. 자동화 트리거 엔드포인트는 존재하나 클라우드에서 실행 의도 아님.
