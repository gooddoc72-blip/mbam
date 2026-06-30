# 라이선스 서버 클라우드 배포 (Fly.io)

사무실이 여러 곳이어도, PC 가 몇 대든 **이 서버 한 곳**으로 모두 인증됩니다.
SQLite DB 는 영구 볼륨에 저장되어 재배포해도 발급한 인증코드가 유지됩니다.

---

## 1. 준비 (한 번만)

1) Fly CLI 설치 (Windows PowerShell):
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```
2) 가입 + 로그인 (카드 등록 필요, 소액):
```powershell
fly auth signup    # 또는 이미 계정 있으면  fly auth login
```

---

## 2. 배포 (auth_server 폴더에서)

```powershell
cd "...\마케팅 프로그램\auth_server"

# (1) fly.toml 의 app 이름을 고유하게 변경
#     예: app = "mbam-license-mycompany"   ← 본인 회사명 등으로

# (2) 앱 생성 (배포는 아직 안 함)
fly launch --no-deploy --copy-config --name mbam-license-mycompany --region nrt

# (3) SQLite 보존용 영구 볼륨 생성 (1GB면 충분)
fly volumes create mbam_data --region nrt --size 1 --yes

# (4) 비밀값 등록 (둘 다 길고 안전한 임의 문자열로)
fly secrets set ADMIN_TOKEN="아주-긴-관리자-비번" AUTH_SECRET="아주-긴-토큰서명키"
#   ADMIN_TOKEN : 코드/계정 관리에 쓰는 관리자 비번
#   AUTH_SECRET : 로그인 토큰 위조 방지 서명키 (바뀌면 기존 로그인 토큰 무효화됨)
#   (선택) 체험 기간 변경: fly secrets set TRIAL_DAYS=5

# (5) 배포
fly deploy
```

배포가 끝나면 주소가 나옵니다:  `https://mbam-license-mycompany.fly.dev`

확인:
```powershell
curl https://mbam-license-mycompany.fly.dev/health     # {"ok":true}
```
브라우저로 `https://mbam-license-mycompany.fly.dev/` 접속 → **회원가입/로그인 페이지**가 뜹니다.
가입하면 자동으로 **5일 무료 체험**이 시작됩니다.

---

## 3. 프로그램이 이 서버를 보게 하기

설치파일 빌드 시 라이선스 서버 주소를 위 주소로 지정하세요:

```powershell
cd ..\installer
powershell -ExecutionPolicy Bypass -File build_payload.ps1 `
  -LicenseServer "https://mbam-license-mycompany.fly.dev"
```
(또는 빌드 후 `payload\license_config.json` 의 `server` 값을 직접 수정)

---

## 4. 인증코드 발급/관리 (내 PC 에서 원격으로)

```powershell
$env:LICENSE_SERVER = "https://mbam-license-mycompany.fly.dev"
$env:ADMIN_TOKEN    = "위에서 secrets 로 넣은 그 값"

# [계정/체험 관리]  ← 회원가입+5일 체험 방식
python issue_codes.py users                                  # 가입 계정 목록(체험/유료/남은일수)
python issue_codes.py upgrade --email a@b.com --days 365     # 유료 전환(365일)
python issue_codes.py extend  --email a@b.com --days 5       # 체험 5일 연장
python issue_codes.py block   --email a@b.com               # 계정 차단

# [PC별 인증코드 방식]  ← 설치형에서 쓰던 방식(병행 가능)
python issue_codes.py issue --count 10 --memo "1차 배포"
python issue_codes.py list
python issue_codes.py reset --code XXXX-XXXX-XXXX-XXXX
python issue_codes.py revoke --code XXXX-XXXX-XXXX-XXXX
```

- **계정 방식(권장, 웹용)**: 고객이 `/` 에서 회원가입 → 5일 무료 체험 → 만료 후 결제하면 `upgrade` 로 유료 전환.
- **코드 방식**: 발급한 코드를 고객에게 전달, 설치형 프로그램 첫 실행 시 입력 (PC 1대당 1코드).

---

## 5. 운영 메모

- **항상 켜짐**: `fly.toml` 에 `auto_stop_machines=false`, `min_machines_running=1` 로 설정되어
  잠들지 않습니다(인증이 즉시 응답). 비용 아끼려 끄면 첫 인증이 몇 초 지연될 수 있습니다.
- **백업**: `fly ssh console` 후 `/data/license.db` 를 받아두면 코드 DB 백업.
- **로그**: `fly logs`
- **재배포**: 코드 수정 후 `fly deploy` (DB 는 볼륨이라 유지됨).
- 비용: shared-cpu-1x / 256MB + 볼륨 1GB → 보통 월 소액(무료 크레딧 내에서 충당되는 경우도 많음).

> 다른 플랫폼을 쓰려면: Railway 도 이 Dockerfile 그대로 + Volume 을 `/data` 에 붙이고
> 환경변수 `LICENSE_DB_URL=sqlite:////data/license.db`, `ADMIN_TOKEN` 만 주면 동일하게 동작합니다.
