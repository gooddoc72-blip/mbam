# MBAM 설치파일(.exe) 빌드 가이드

PC 1대당 인증코드로 동작하는 **설치형 MBAM** 을 만드는 절차입니다.
결과물: `installer/output/MBAM_Setup_1.0.0.exe` (더블클릭 한 번으로 설치)

---

## 0. 구성 요약

```
[고객 PC]  MBAM_Setup.exe 설치 → 실행 시 인증창(코드 입력) → 백엔드+프론트 자동 기동
              │ 인증코드 + HWID
              ▼
[내 서버]  라이선스 서버(auth_server) — 코드 발급/검증/PC이전/차단
```

- **인증코드 1개 = PC 1대**. 최초 실행 시 코드를 그 PC(HWID)에 묶고, 이후엔 자동 검증.
- 다른 PC 에서 같은 코드 입력 → 거부. PC 교체는 관리자가 `reset` 으로 바인딩 해제.
- 인터넷이 잠깐 끊겨도 마지막 인증 후 **7일** 까지는 오프라인 사용 가능(설정값).

---

## 1. 사전 준비 (빌드 PC)

- Windows 10/11 (x64)
- **Node.js + npm** (프론트 빌드용)
- **Inno Setup 6** — https://jrsoftware.org/isdl.php
- 인터넷 연결 (동봉용 Python/Node/Chromium 자동 다운로드)
- `tar` (Windows 10 1803+ 기본 포함)

> 동봉 Python 은 [python-build-standalone](https://github.com/astral-sh/python-build-standalone) 의
> `install_only` 빌드라 **tkinter 포함 + 재배치 가능** 합니다. (python.org 임베디드 배포판은 tkinter 가 없어 인증창이 안 떠서 사용하지 않습니다.)

---

## 2. 빌드 절차

### (1) 라이선스 서버 주소 정하기
배포된 프로그램이 인증을 물어볼 주소입니다. 아래 둘 중 하나:
- 빌드 시 인자로 전달: `-LicenseServer "http://내도메인:8005"`
- 또는 빌드 후 `payload/license_config.json` 의 `server` 값을 직접 수정

### (2) 페이로드 빌드
```powershell
cd "...\마케팅 프로그램\installer"
powershell -ExecutionPolicy Bypass -File build_payload.ps1 -LicenseServer "http://내도메인:8005"
```
→ 동봉 Python+Node+Chromium 다운로드, 프론트 빌드, `installer/payload/` 생성 (수백 MB ~ 1GB)

### (3) 설치파일 컴파일
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" mbam.iss
```
→ `installer/output/MBAM_Setup_1.0.0.exe` 완성. 이 파일 하나만 배포하면 됩니다.

---

## 3. 설치 폴더 구조(고객 PC)

```
C:\Program Files\MBAM\
  mbam_launcher.py        ← 인증창 + 서버 기동
  mbam_auth_gate.py
  licensing\              ← HWID/검증 모듈
  license_config.json     ← 라이선스 서버 주소
  run_backend.py, mbam_nextgen\ ...   ← 백엔드
  mbam-web\ (.next, node_modules)     ← 빌드된 프론트
  runtime\python\         ← 동봉 Python (pythonw.exe 가 런처 실행)
  runtime\node\           ← 동봉 Node
  runtime\ms-playwright\  ← 동봉 Chromium
```

- 바탕화면/시작메뉴 바로가기 → `runtime\python\pythonw.exe "...\mbam_launcher.py"`
- 사용자별 인증 캐시: `%LOCALAPPDATA%\MBAM\license.json`, 로그: `%LOCALAPPDATA%\MBAM\logs\`

---

## 4. 자주 막히는 곳

| 증상 | 해결 |
|------|------|
| 빌드 중 Python 다운로드 실패 | `build_payload.ps1` 의 `$PbsTag`/`$PythonVersion` 을 최신 릴리스로 수정 |
| 프론트 빌드 실패 | 빌드 PC 에서 `cd mbam-web && npm run build` 가 되는지 먼저 확인 |
| 설치 후 인증창만 뜨고 진행 안 됨 | 고객 PC 가 라이선스 서버에 접속 가능한지(방화벽/주소) 확인 |
| Chromium 관련 오류 | 런처가 `PLAYWRIGHT_BROWSERS_PATH` 를 `runtime\ms-playwright` 로 지정함 — 폴더 동봉 여부 확인 |

서버 운영은 [auth_server/README_DEPLOY.md](../auth_server/README_DEPLOY.md) 참고.
