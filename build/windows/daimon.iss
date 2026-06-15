; Inno Setup script for Daimon (Windows installer).
; Build:  iscc /DMyAppVersion=0.0.3 build\windows\daimon.iss
; Produces dist\Daimon-<version>-setup.exe from the PyInstaller one-dir bundle.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Daimon"
#define MyAppPublisher "Arborithm"
#define MyAppExeName "Daimon.exe"

[Setup]
AppId={{A7C0E2D6-7B4E-4E2A-9F3D-DA1MON000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user install needs no elevation (privileges lowest); fits the no-TCC model.
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist
OutputBaseFilename=Daimon-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 2004 (build 19041) — required for the overlay's WDA_EXCLUDEFROMCAPTURE.
MinVersion=10.0.19041

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startupicon"; Description: "Start Daimon (tray) when I sign in"; GroupDescription: "Startup"

[Files]
; The entire PyInstaller one-dir bundle.
Source: "..\..\dist\Daimon\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Launch the tray + onboarding right after install.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Daimon"; Flags: nowait postinstall skipifsilent
