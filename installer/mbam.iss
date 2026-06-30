; ============================================================
;  MBAM 마케팅 프로그램 - Inno Setup 설치 스크립트
;  빌드 전 반드시 build_payload.ps1 을 먼저 실행해 payload\ 를 생성하세요.
;  컴파일: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" mbam.iss
; ============================================================

#define MyAppName "MBAM 마케팅 프로그램"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MBAM"
; 런처는 동봉된 pythonw.exe 로 mbam_launcher.py 를 실행 (별도 exe 빌드 불필요)
#define LauncherExe "runtime\python\pythonw.exe"
#define LauncherArgs """{app}\mbam_launcher.py"""

[Setup]
AppId={{B7A3E2C1-9F4D-4A8E-8C21-MBAM00000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MBAM
DefaultGroupName=MBAM
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=MBAM_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; 아이콘 (있으면)
; SetupIconFile=mbam.ico
UninstallDisplayName={#MyAppName}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"; Flags: checkedonce

[Files]
; build_payload.ps1 이 생성한 payload 전체를 설치 폴더로 복사
Source: "payload\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; IconFilename: "{app}\mbam.ico"
Name: "{group}\제거";                Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; IconFilename: "{app}\mbam.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#LauncherExe}"; Parameters: "{#LauncherArgs}"; WorkingDir: "{app}"; Description: "지금 MBAM 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 실행 중 생성되는 캐시/로그 정리 (사용자 라이선스 캐시는 LOCALAPPDATA\MBAM 에 별도 보관)
Type: filesandordirs; Name: "{app}\__pycache__"
