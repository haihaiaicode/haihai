#pragma codepage 65001
#define AppName "会议记录工具"
#define AppVersion "1.0.3"
#define AppPublisher "haihaiaicode"
#define AppExeName "MeetingRecorder.exe"

[Setup]
AppId={{8A0E1C7E-89E3-4A20-A4C0-5E4D72D87110}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\MeetingRecorder
DefaultGroupName={#AppName}
OutputDir=installer
OutputBaseFilename=MeetingRecorder-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\MeetingRecorder.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动{#AppName}"; Flags: nowait postinstall skipifsilent
