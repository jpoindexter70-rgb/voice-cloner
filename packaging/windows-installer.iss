#ifndef AppVersion
  #define AppVersion "0.3.0"
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

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  ReportPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Verifying bundled Python, local backend and audio processing...';
    ReportPath := ExpandConstant('{tmp}\FamilyVoice-runtime-check.json');
    DeleteFile(ReportPath);
    Log('Starting installed runtime verification. Models are not downloaded by this check.');
    if not Exec(ExpandConstant('{app}\FamilyVoiceCloner.exe'),
      '--self-test "' + ReportPath + '"', ExpandConstant('{app}'),
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Unable to start the installed application: ' + SysErrorMessage(ResultCode) +
        '. Your recordings are preserved. Retry the installer to repair the runtime.');
    if (ResultCode <> 0) or not FileExists(ReportPath) then
      RaiseException('Installed runtime verification failed. Exit code: ' + IntToStr(ResultCode) +
        '. Your recordings are preserved. Check the installer log and local application diagnostics, then retry installation to repair the runtime.');
    Log('Installed Python/backend/reference upload/WAV/MP3 verification passed.');
    DeleteFile(ReportPath);
  end;
end;
