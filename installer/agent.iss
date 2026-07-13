; ============================================================
;  MBAM 웹 관제 에이전트 - Inno Setup 설치 스크립트 (에이전트 전용)
;  빌드 전 반드시 build_agent_payload.ps1 을 먼저 실행해 payload_agent\ 를 생성하세요.
;  컴파일: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" agent.iss
;
;  이 설치본은 marketlabs.kr(클라우드) 웹 사용자가 자기 PC에서 자기 계정으로
;  에이전트만 상주시키기 위한 것입니다. (프론트/로컬 백엔드/라이선스 없음)
;  최초 실행 시 agent.py 가 로그인 창을 띄워 계정을 받아 agent_config.json 을 만듭니다.
; ============================================================

#define MyAppName "MBAM 웹 관제 에이전트"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MBAM"
; 콘솔 없이 백그라운드 실행하는 동봉 pythonw 로 agent.py 를 구동 (agent_startup.vbs 경유)
#define AgentPyw "runtime\python\pythonw.exe"

[Setup]
AppId={{B7A3E2C1-9F4D-4A8E-8C21-MBAMAGENT0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; 관리자 권한 없이 사용자별 설치 (HKCU 자동시작과 궁합)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\MBAM-Agent
DefaultGroupName=MBAM 에이전트
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=MBAM_Agent_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
; SetupIconFile=mbam.ico

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "agentautostart"; Description: "Windows 시작 시 에이전트 자동 실행 (권장 — 웹에서 분석·발행하려면 켜져 있어야 함)"; GroupDescription: "자동 실행:"; Flags: checkedonce
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"; Flags: unchecked

[Registry]
; 로그인(부팅) 시 에이전트를 콘솔 없이 백그라운드로 자동 실행
; 동봉 pythonw 를 직접 실행(vbs 인코딩/시스템 python 탐색 변수 제거). agent.py 가 cwd 를 스스로 고정.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MarketLabsAgent"; ValueData: """{app}\{#AgentPyw}"" ""{app}\agent.py"""; Flags: uninsdeletevalue; Tasks: agentautostart

[Files]
; build_agent_payload.ps1 이 생성한 payload_agent 전체를 설치 폴더로 복사
Source: "payload_agent\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName} 시작";  Filename: "{app}\{#AgentPyw}"; Parameters: """{app}\agent.py"""; WorkingDir: "{app}"; Comment: "에이전트 시작(최초 실행 시 로그인 창)"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#AgentPyw}"; Parameters: """{app}\agent.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 설치 직후 에이전트 시작 → 최초 1회 로그인 창이 떠서 계정 입력 (이후 자동)
; 동봉 pythonw 를 직접 실행(WorkingDir={app}). agent.py 가 sys.path[0]=앱폴더라 mbam_nextgen import 정상.
Filename: "{app}\{#AgentPyw}"; Parameters: """{app}\agent.py"""; WorkingDir: "{app}"; Description: "지금 로그인하고 에이전트 시작"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\agent.log"
; 사용자가 입력한 로그인 정보 정리
Type: files; Name: "{app}\agent_config.json"
