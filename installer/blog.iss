; ============================================================
;  블로그 마케팅 프로그램 - Inno Setup 설치 스크립트 (블로그 자동화 전용판)
;  빌드 전 반드시 build_blog_payload.ps1 을 먼저 실행해 payload_blog\ 를 생성하세요.
;  컴파일: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" blog.iss
;
;  풀버전(mbam.iss)·카페 전용판(cafe.iss)과 AppId·설치폴더·시작메뉴·포트가 모두 달라서
;  한 PC 에 셋 다 설치돼 있어도 서로를 덮어쓰거나 충돌하지 않습니다.
;  실행 시 크롤링 프로그램과 같은 '기기 승인' 인증을 거칩니다(인증코드 없음).
; ============================================================

#define MyAppName "블로그 마케팅"
; ⚠ build_blog_payload.ps1 의 -Version 과 반드시 같아야 한다.
;   이 값이 version.json 으로 설치본에 들어가고, 런처가 서버의 최신 버전과 비교한다.
;   어긋나면 방금 설치한 고객에게도 업데이트 안내가 뜬다.
#define MyAppVersion "1.0.0"
#define MyAppPublisher "마케팅연구소"
; 런처는 동봉된 pythonw.exe 로 blog_launcher.py 를 실행 (별도 exe 빌드 불필요)
#define LauncherExe "runtime\python\pythonw.exe"
; (LauncherArgs 정의는 쓰지 않는다 — #define 을 거치면 Inno 가 따옴표를 벗겨
;  공백 있는 경로가 깨진다. 아래 [Icons]/[Run] 에 직접 적는다)

[Setup]
; 풀버전·카페판과 반드시 다른 AppId — 같으면 서로를 업그레이드/제거해 버린다
AppId={{B7A3E2C1-9F4D-4A8E-8C21-MBAMBLOG00001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; ⚠ Program Files 에 설치하면 안 된다.
;   이 프로그램은 실행 중에 설치 폴더 안에 파일을 만든다
;   (saas_data.db 같은 SQLite DB, 네이버 로그인 프로필, 임시 이미지 등).
;   Program Files 는 일반 사용자 권한으로 쓸 수 없어서 백엔드가
;   'sqlite3.OperationalError: unable to open database file' 로 죽는다.
;   그래서 카페 전용판(cafe.iss)과 같이 사용자 폴더에 설치한다.
DefaultDirName={localappdata}\Programs\MBAM-Blog
DefaultGroupName=블로그 마케팅
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=BlogMarketing_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 사용자 폴더에 설치하므로 관리자 권한이 필요 없다.
; (관리자로 설치하면 오히려 바로가기·설정이 다른 사용자 계정에 만들어져 꼬인다)
PrivilegesRequired=lowest
UninstallDisplayName={#MyAppName}
; 설치 마법사 exe 자체의 아이콘
SetupIconFile=blog.ico
; [프로그램 추가/제거] 목록에 표시될 아이콘
UninstallDisplayIcon={app}\blog.ico

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"; Flags: checkedonce

[Files]
; build_blog_payload.ps1 이 생성한 payload_blog 전체를 설치 폴더로 복사
Source: "payload_blog\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; 아이콘은 make_blog_icon.py 가 만든 installer\blog.ico (16~256px 7종 포함).
; 페이로드 빌드 스크립트가 {app}\blog.ico 로 함께 복사한다.
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#LauncherExe}"; Parameters: """{app}\blog_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\blog.ico"
Name: "{group}\제거";                Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#LauncherExe}"; Parameters: """{app}\blog_launcher.py"""; WorkingDir: "{app}"; IconFilename: "{app}\blog.ico"; Tasks: desktopicon

[Run]
; 설치 직후 실행 (최초 1회 기기 승인 요청 창이 뜸)
Filename: "{app}\{#LauncherExe}"; Parameters: """{app}\blog_launcher.py"""; WorkingDir: "{app}"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 실행 중 생성되는 캐시/로그 정리
; (인증 캐시는 LOCALAPPDATA\MBAM\device_blog.json, 로그는 LOCALAPPDATA\MBAM-Blog\logs 에 별도 보관)
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\mbam_nextgen\__pycache__"
Type: filesandordirs; Name: "{app}\sessions"
Type: filesandordirs; Name: "{app}\profiles"
