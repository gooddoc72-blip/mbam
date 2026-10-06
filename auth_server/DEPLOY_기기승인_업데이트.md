# 라이선스 서버 배포 가이드 — 기기 승인(product) 기능 반영

카페 전용판이 쓰는 **제품별 기기 승인**을 서버에 반영하는 절차입니다.

> ⚠ **순서가 중요합니다.** 서버를 먼저 올리지 않고 카페 설치본을 배포하면,
> 크롤러로 이미 승인된 PC 가 카페판까지 그냥 열립니다.
> (구버전 서버는 `product` 필드를 무시하고 기존 `devices` 테이블만 보기 때문입니다.
> 실제로 현재 운영 서버에 확인한 동작입니다.)
>
> **올바른 순서: ① 서버 배포 → ② 관리자_승인도구 재빌드 → ③ 카페 설치본 배포**

---

## 0. 현재 운영 환경

| 항목 | 값 |
|---|---|
| 서버 | AWS EC2 `18.209.162.250` (ubuntu) |
| 공개 주소 | `https://license.blocklab.co.kr` (HTTPS 정상 동작 확인됨) |
| 구동 방식 | Docker Compose (`auth_server/docker-compose.yml`) |
| DB | SQLite `license.db` (컨테이너에 볼륨 마운트) |
| 배포 스크립트 | [deploy_aws_update.bat](../deploy_aws_update.bat) |
| SSH 키 | `my-key.pem` (저장소 루트) |

---

## 1. 서버 접속

터미널은 **Git Bash** 를 쓰세요 (저장소 폴더에서 마우스 우클릭 → "Open Git Bash here").
PowerShell 의 기본 `ssh.exe` 는 키 파일 권한을 더 깐깐하게 봐서 거부할 수 있습니다.

```bash
cd "F:/02 마케팅 프로그램/01 마케팅 연구소"
ssh -i my-key.pem ubuntu@18.209.162.250
```

처음 접속하면 호스트 지문을 신뢰할지 묻습니다 → `yes` 입력.

접속되면 프롬프트가 `ubuntu@ip-...:~$` 로 바뀝니다. 확인해 볼 것:

```bash
ls ~/auth_server                                   # 서버에 올라간 소스
sudo docker ps                                     # 컨테이너 상태
sudo docker compose -f ~/auth_server/docker-compose.yml logs --tail 30
exit                                               # 나가기
```

**현재 상태(2026-08-12 확인)**
- 컨테이너 `mbam_license_server` — 5주째 가동 중, `0.0.0.0:8005` 노출
- Docker Compose v2.40.3, 소스는 `~/auth_server/`
- 운영 DB `~/auth_server/license.db` — 승인 기기 1건, 계정 1건

> ⚠ **PowerShell 에서 `Permission denied` 또는 `UNPROTECTED PRIVATE KEY FILE` 이 나오면**
> 키 파일 권한이 너무 열려 있어서입니다(현재 `Everyone: Full control`). 이렇게 좁히세요:
> ```powershell
> icacls my-key.pem /inheritance:r
> icacls my-key.pem /grant:r "$env:USERNAME:(R)"
> ```

---

## 2. 배포

저장소 루트에서 실행하면 끝입니다.

```
deploy_aws_update.bat
```

하는 일: ① 서버의 운영 DB 백업 → ② **소스 파일만** 업로드 → ③ `docker compose up -d --build` → ④ 헬스체크

> ⚠ **이 스크립트는 2026-08-12 에 고쳤습니다.** 이전 버전은
> `scp -r auth_server ubuntu@서버:~/` 로 폴더를 통째로 올려서, 로컬의 `license.db`(사실상 빈 개발용 DB)가
> **서버의 운영 DB를 덮어썼습니다.** 그대로 실행했다면 발급된 인증코드와 승인된 고객 기기가 전부 사라졌을 겁니다.
> 지금은 소스 파일만 지정해 올리고 `license.db` 는 건드리지 않습니다.

수동으로 하려면 (폴더째 올리지 마세요):

```bash
scp -i my-key.pem \
    auth_server/server.py auth_server/issue_codes.py auth_server/requirements.txt \
    auth_server/Dockerfile auth_server/docker-compose.yml auth_server/.dockerignore \
    ubuntu@18.209.162.250:~/auth_server/

ssh -i my-key.pem ubuntu@18.209.162.250
  cd auth_server
  sudo docker compose up -d --build
  sudo docker compose logs --tail 30      # 기동 확인
```

### DB 는 그대로 보존됩니다
`docker-compose.yml` 이 `./license.db` 를 컨테이너에 마운트하므로 재배포해도 기존
인증코드·기기 승인 기록이 유지됩니다. 신규 테이블 `product_devices` 는 서버가 뜰 때
SQLAlchemy 가 자동 생성합니다 — **수동 마이그레이션 불필요**.

기존 `devices` 테이블은 **건드리지 않습니다.** 크롤러는 재배포 없이 그대로 동작합니다.

> 💾 배포 전 DB 백업(선택이지만 권장):
> ```bash
> ssh -i my-key.pem ubuntu@18.209.162.250 "cp ~/auth_server/license.db ~/license.db.$(date +%Y%m%d)"
> ```

---

## 3. 배포 확인

```bash
# 1) 살아있는지
curl https://license.blocklab.co.kr/health
# → {"ok":true}

# 2) product 를 아는 새 서버인지 (핵심 확인)
curl -X POST https://license.blocklab.co.kr/request_approval \
     -H "Content-Type: application/json" \
     -d "{\"hwid\":\"DEPLOY-TEST-1\",\"name\":\"배포확인\",\"product\":\"cafe\"}"
# → {"success":true,...}

curl -X POST https://license.blocklab.co.kr/verify \
     -H "Content-Type: application/json" \
     -d "{\"hwid\":\"DEPLOY-TEST-1\",\"product\":\"cafe\"}"
# → {"authorized":false,...,"status":"pending"}   ← pending 이 나오면 성공
```

`status`가 `pending`이면 신규 테이블에 제품별로 들어간 것입니다.
구버전 서버라면 `unregistered`가 나옵니다(= 배포 안 됨).

확인용 테스트 행 삭제:
```bash
ssh -i my-key.pem ubuntu@18.209.162.250 \
  "sudo docker compose -f ~/auth_server/docker-compose.yml exec -T license_server \
   python -c \"import sqlite3;c=sqlite3.connect('/app/license.db');c.execute(\\\"DELETE FROM product_devices WHERE hwid='DEPLOY-TEST-1'\\\");c.commit()\""
```

---

## 4. 관리자 승인도구 재빌드 (필수)

서버만 올리고 이 단계를 건너뛰면 **카페 승인 요청이 관리자 화면에 보이지 않습니다.**
[admin_tool.py](../admin_tool.py) 에 제품 컬럼이 추가됐기 때문입니다.

```powershell
# 저장소 루트에서
python -m PyInstaller --onefile --windowed --name "관리자_승인도구" admin_tool.py
# → dist\관리자_승인도구.exe
```

기존 `관리자_승인도구.spec` 이 있으므로 이렇게 해도 됩니다:
```powershell
python -m PyInstaller 관리자_승인도구.spec
```

빌드 전에 [admin_tool.py](../admin_tool.py) 상단의 `ADMIN_TOKEN` 이 서버에 설정한 값과
같은지 확인하세요. 현재 소스에는 `change-this-admin-token` 이라는 자리표시자가 들어 있습니다.

---

## 5. ⚠ ADMIN_TOKEN 교체 (이번 배포에 같이 하세요)

**현재 운영 서버의 관리자 토큰이 기본 예시값 `change-this-admin-token` 그대로입니다.**
2026-08-12 에 실제로 확인했습니다 — 이 토큰으로 `GET /admin/devices` 가 `200` 을 반환합니다.

이 값은 [docker-compose.yml](docker-compose.yml) 과 [admin_tool.py](../admin_tool.py) 에
평문으로 들어 있고, 저장소에 그대로 커밋돼 있습니다. 서버가 공개 HTTPS 로 열려 있으므로
이 값을 아는 사람은 누구나 다음을 할 수 있습니다.

- 등록된 모든 고객 기기 목록 조회
- 임의의 기기를 **승인**(무단 사용) 하거나 기존 고객을 **차단**
- 인증코드 무제한 발급 (`/admin/issue`)

### 교체 방법

1. 새 토큰 생성 (아무 방법이나):
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. `docker-compose.yml` 수정:
   ```yaml
   environment:
     - ADMIN_TOKEN=새로_생성한_값
     - PORT=8005
   ```
3. [admin_tool.py](../admin_tool.py) 9번째 줄 `ADMIN_TOKEN` 상수도 같은 값으로 수정
4. 배포(2항) → 관리자 도구 재빌드(4항)
5. `issue_codes.py` 를 쓸 때는 환경변수 `ADMIN_TOKEN` 에 같은 값을 넣습니다.

> 토큰을 저장소에 커밋하지 않으려면 `docker-compose.yml` 에서 `${ADMIN_TOKEN}` 으로 참조하고
> 서버의 `~/auth_server/.env` 에 실제 값을 두는 방식이 낫습니다. 다만 `admin_tool.py` 는
> exe 로 배포되므로 어차피 값이 안에 들어갑니다 — 관리자 PC 밖으로 나가지 않게 하세요.

---

## 6. 승인 운영 흐름

```
[고객] 카페 프로그램 실행 → 미등록이면 창이 뜸
       → 기기번호 자동 표시 + 이름/소속 입력 → [승인 요청하기]
[관리자] 관리자_승인도구.exe → [목록 새로고침]
       → 제품 열이 "카페 마케팅" 인 행 선택 → [✅ 선택 기기 승인]
[고객] 인증창의 [다시 확인] 클릭 → 바로 실행
```

- 승인 후에는 실행할 때마다 조용히 확인만 하고 열립니다.
- 인터넷이 끊겨도 마지막 확인 후 **7일**까지는 실행됩니다
  (`licensing/device_auth.py` 의 `OFFLINE_GRACE_DAYS`).
- 해지/사용중지는 같은 도구에서 **[❌ 선택 기기 차단]** — 다음 실행부터 막히고
  차단된 기기는 재요청도 안 됩니다.
- PC 교체는 새 PC 에서 다시 승인 요청을 받으면 됩니다(기존 행은 차단 처리).

---

## 7. 서버 API 변경 요약

기존 클라이언트(크롤러 등)는 `product` 를 안 보내므로 **동작이 전혀 바뀌지 않습니다.**

| 엔드포인트 | 변경 |
|---|---|
| `POST /verify` | `product` 필드 추가(선택). 있으면 `product_devices`, 없으면 기존 `devices` 조회 |
| `POST /request_approval` | 동일하게 `product` 추가(선택) |
| `GET /admin/devices` | 두 테이블을 합쳐 반환, 각 행에 `product` 포함(기존 기기는 `""`) |
| `POST /admin/device/status` | `product` 추가(선택) — 어느 테이블을 고칠지 결정 |
| 신규 테이블 | `product_devices` (`hwid` + `product` 조합, 자동 생성) |

---

## 8. 문제가 생기면

```bash
ssh -i my-key.pem ubuntu@18.209.162.250
sudo docker compose -f ~/auth_server/docker-compose.yml logs --tail 100   # 로그
sudo docker compose -f ~/auth_server/docker-compose.yml restart           # 재시작
sudo docker compose -f ~/auth_server/docker-compose.yml down              # 정지
```

되돌리려면 이전 버전의 **소스 파일만** 다시 올려 `up -d --build` 하면 됩니다
(폴더째 `scp -r` 하지 마세요 — 운영 DB 를 덮어씁니다).
`product_devices` 테이블이 남아 있어도 구버전 서버는 그 테이블을 보지 않으므로 무해합니다.

DB 를 되살려야 하면 배포 스크립트가 남긴 백업을 쓰면 됩니다:

```bash
ssh -i my-key.pem ubuntu@18.209.162.250
ls ~/auth_server/license.db.bak.*                       # 백업 목록
cd ~/auth_server
sudo docker compose down
cp license.db.bak.20260812_120000 license.db            # 되돌릴 시점 선택
sudo docker compose up -d
```
