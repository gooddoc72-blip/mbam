# MBAM 라이선스 서버 운영 가이드

인증코드를 **발급/검증/PC이전/차단** 하는 중앙 서버입니다. 항상 켜져 있어야 고객 PC 가 인증됩니다.
(작은 클라우드 VM, 또는 고정 IP/포트포워딩 된 사무실 PC 한 대면 충분)

---

## 1. 실행

> ☁️ **클라우드(추천)**: 사무실이 여러 곳이거나 외부에서도 인증이 되게 하려면
> [DEPLOY_FLY.md](DEPLOY_FLY.md) 의 Fly.io 배포를 따르세요. (HTTPS 자동 + SQLite 영구 보존 + 항상 켜짐)

### A. 직접 실행 (간단)
```bash
pip install -r requirements.txt
set ADMIN_TOKEN=원하는_관리자_비밀번호      # 안 정하면 실행 시 자동 생성되어 콘솔에 출력됨
set PORT=8005
python server.py
```

### B. Docker (권장 — 항상 켜둠)
```bash
# docker-compose.yml 에 ADMIN_TOKEN 환경변수만 추가하고
docker compose up -d --build
```
`docker-compose.yml` 의 `environment:` 에 `- ADMIN_TOKEN=...` 를 넣어 고정하세요.
DB(`license.db`)는 볼륨으로 보존됩니다.

> **중요:** 외부 공개 시 HTTPS(리버스 프록시: Caddy/Nginx) 뒤에 두는 것을 권장.
> 빌드한 프로그램의 `license_config.json` 주소를 이 서버 공인주소로 맞춰야 합니다.

---

## 2. 인증코드 관리 (CLI)

```bash
set ADMIN_TOKEN=서버에_설정한_토큰
set LICENSE_SERVER=http://내서버:8005     # 생략 시 127.0.0.1:8005

# 코드 5개 발급(무기한, PC 1대)
python issue_codes.py issue --count 5 --memo "A고객"

# 구독형: 365일 유효 코드 1개
python issue_codes.py issue --days 365 --memo "B고객"

# 전체 목록 (어느 코드가 어느 PC 에 묶였는지)
python issue_codes.py list

# 코드 차단 / 차단해제
python issue_codes.py revoke   --code XXXX-XXXX-XXXX-XXXX
python issue_codes.py unrevoke --code XXXX-XXXX-XXXX-XXXX

# PC 교체: 기존 바인딩 해제 → 고객이 새 PC 에서 같은 코드로 재인증 가능
python issue_codes.py reset    --code XXXX-XXXX-XXXX-XXXX
```

발급된 코드를 고객에게 전달 → 고객은 프로그램 첫 실행 시 인증창에 입력.

---

## 3. API

### 계정 방식 (회원가입 + 5일 무료 체험 — 웹용 권장)
| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET  | `/` | 회원가입/로그인 웹페이지 |
| POST | `/register` | `{email, password}` → 가입 + **5일 체험 시작**, 토큰 반환 |
| POST | `/login` | `{email, password}` → 토큰 + 상태 반환 |
| GET  | `/me` | `Authorization: Bearer <토큰>` → 사용 가능 여부 + 남은 기간 |
| POST | `/admin/upgrade`/`extend_trial`/`block_user` | 관리자(헤더 `x-admin-token`) |
| GET  | `/admin/users` | 가입 계정 목록 |

- `TRIAL_DAYS` 환경변수로 체험 일수 변경(기본 5).
- `AUTH_SECRET` 환경변수로 로그인 토큰 서명(없으면 ADMIN_TOKEN 기반 파생).

### PC별 인증코드 방식 (설치형)
| 메서드 | 경로 | 용도 |
|--------|------|------|
| POST | `/activate` | 최초 인증: `{code, hwid, machine_name}` → 코드를 그 PC 에 바인딩 |
| POST | `/verify`   | 실행 시 검증: `{code, hwid}` → 살아있고 이 PC 가 맞는지 |
| POST | `/admin/issue`/`revoke`/`unrevoke`/`reset` | 관리자(헤더 `x-admin-token`) |
| GET  | `/admin/list` | 코드 목록 |
| GET  | `/health` | 헬스체크 |

- **1코드=1PC**: 다른 PC 가 같은 코드로 `/activate` 하면 `409` 거부.
- **차단/만료** 코드는 `/verify` 가 거부 → 프로그램이 재인증 요구.
- 고객 PC 오프라인 시: 마지막 성공 인증 후 7일까지 사용 가능(클라이언트 설정 `OFFLINE_GRACE_DAYS`).
