#define AppVer "1.4"

[Setup]
AppName=Crawler Pro
AppVersion={#AppVer}
DefaultDirName={autopf}\CrawlerPro
DefaultGroupName=Crawler Pro
OutputBaseFilename=CrawlerPro_Setup_v{#AppVer}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=compiler:SetupClassicIcon.ico

[Files]
Source: "dist\Crawler Pro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Crawler Pro"; Filename: "{app}\Crawler Pro.exe"
Name: "{autodesktop}\Crawler Pro"; Filename: "{app}\Crawler Pro.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"

[Run]
Filename: "{app}\Crawler Pro.exe"; Description: "Crawler Pro 실행"; Flags: nowait postinstall skipifsilent
