#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
[Setup]
AppId={{E44B4B82-320A-4D43-A066-460309921068}
AppName=Family AI Voice Cloner Pro
AppVersion={#AppVersion}
AppPublisher=Family Voice Studio
DefaultDirName={localappdata}\Programs\Family AI Voice Cloner Pro
DefaultGroupName=Family AI Voice Cloner Pro
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=Family-AI-Voice-Cloner-Pro-{#AppVersion}-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FamilyVoiceCloner.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
[Files]
Source: "..\dist\FamilyVoiceCloner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Family AI Voice Cloner Pro"; Filename: "{app}\FamilyVoiceCloner.exe"
Name: "{autodesktop}\Family AI Voice Cloner Pro"; Filename: "{app}\FamilyVoiceCloner.exe"
[Run]
Filename: "{app}\FamilyVoiceCloner.exe"; Description: "Open Family AI Voice Cloner Pro"; Flags: nowait postinstall skipifsilent
; User recordings/models remain in LOCALAPPDATA\VoiceControlRoom. No uninstall-delete rule.
