# MBAM 웹 관제 에이전트 설치파일 빌드 가이드

marketlabs.kr(클라우드) 웹 사용자가 **자기 PC에서 자기 계정으로 에이전트만** 상주시키는
경량 설치본(`MBAM_Agent_Setup_1.0.0.exe`)을 만드는 절차입니다.

> 왜 필요한가: 네이버 스크래핑(플레이스 리뷰·블로그·발행)은 데이터센터 IP(클라우드)에서
> 막히므로, 각 사용자의 집 PC 에이전트가 그 사용자의 잡을 대신 실행합니다.
> 백엔드는 **로그인한 계정(user_id)의 잡만** 에이전트에 넘기므로, 에이전트도 **같은 계정**으로
> 로그인해야 합니다. → 사용자별 설치본이 필요.

---

## 0. 풀 설치본(mbam.iss)과의 차이

| | 풀 설치(`mbam.iss`) | 에이전트 설치(`agent.iss`) |
|---|---|---|
| 포함 | 백엔드+프론트+에이전트+Node+Chromium | 에이전트+Python+Chromium 만 |
| 인증 | 라이선스 코드(PC당) | **웹 계정 로그인**(라이선스 없음) |
| 권한 | 관리자 | **사용자 권한**(UAC 불필요) |
| 용량 | ~1GB | ~300MB (Chromium 위주) |
| 계정 입력 | - | 최초 실행 시 `agent.py` 로그인 창 |

---

## 1. 사전 준비 (빌드 PC, 1회)

- Windows 10/11 (x64), 인터넷 연결
- **Inno Setup 6** — https://jrsoftware.org/isdl.php
  (또는 `winget install -e --id JRSoftware.InnoSetup`)
- `tar` (Windows 10 1803+ 기본 포함)

> 동봉 Python 은 python-build-standalone `install_only` 빌드(tkinter 포함 → 로그인 창 표시 가능).

---

## 2. 빌드 절차 (2단계)

```powershell
cd "...\마케팅 프로그램\installer"

# (1) 페이로드 빌드 — 동봉 Python + requirements + Chromium 다운로드/구성 (수백 MB, 수 분)
powershell -ExecutionPolicy Bypass -File build_agent_payload.ps1

# (2) 설치파일 컴파일
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" agent.iss
```

→ `installer/output/MBAM_Agent_Setup_1.0.0.exe` 완성. 이 파일 하나만 배포하면 됩니다.

---

## 3. 고객 사용 흐름

1. `MBAM_Agent_Setup_1.0.0.exe` 더블클릭 → 설치(관리자 권한 불필요)
2. 설치 끝 → 에이전트 시작 → **로그인 창**에 marketlabs 계정(이메일/비번) 입력
   - 서버에 실제 로그인해 검증 후 `agent_config.json` 저장 (오타 방지)
3. 이후 **Windows 시작 시 자동 실행**(백그라운드, 콘솔 없음)
4. 웹에서 **같은 계정**으로 로그인해 맛집 수집·발행 등 실행 → 이 PC 에이전트가 처리

> 재로그인(비번 변경 등): 저장된 계정으로 로그인 실패 시 다음 시작 때 로그인 창이 다시 뜹니다.

---

## 4. 설치 폴더 구조 (고객 PC)

```
%LOCALAPPDATA%\Programs\MBAM-Agent\
  agent.py                ← 에이전트 본체 (최초 로그인 창 + 폴링)
  agent_startup.vbs       ← 콘솔 없이 실행 + PYTHONPATH/브라우저 경로 설정
  agent_config.json       ← (최초 로그인 후 생성) 계정/서버 주소
  mbam_nextgen\ ...        ← 잡 실행 코드(스크래핑/발행/분석)
  requirements 로 설치된 site-packages
  runtime\python\          ← 동봉 Python (pythonw)
  runtime\ms-playwright\   ← 동봉 Chromium
```

- 자동시작 레지스트리: `HKCU\...\Run\MarketLabsAgent = wscript.exe "...\agent_startup.vbs"`
- 로그: `%LOCALAPPDATA%\Programs\MBAM-Agent\agent.log`

---

## 5. 자주 막히는 곳

| 증상 | 해결 |
|------|------|
| 빌드 중 Python 다운로드 실패 | `build_agent_payload.ps1` 의 `$PbsTag`/`$PythonVersion` 을 최신 릴리스로 |
| 잡이 실행되는데 "import mbam_nextgen" 오류 | `agent_startup.vbs` 가 PYTHONPATH=설치폴더 로 실행하는지 확인 |
| Playwright/Chromium 오류 | `runtime\ms-playwright` 동봉 여부 + agent.py 가 `PLAYWRIGHT_BROWSERS_PATH` 설정하는지 |
| 로그인해도 잡이 안 옴 | 웹 로그인 계정과 에이전트 로그인 계정이 **동일**한지 확인(핵심) |
