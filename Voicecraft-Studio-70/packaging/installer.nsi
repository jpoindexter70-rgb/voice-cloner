Unicode true
Target amd64-unicode
!include "MUI2.nsh"
!include "x64.nsh"
Name "Voicecraft Studio 70"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\Voicecraft Studio 70"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "70.1.1.0"
VIAddVersionKey /LANG=1033 "ProductName" "Voicecraft Studio 70"
VIAddVersionKey /LANG=1033 "FileDescription" "Voicecraft Studio 70 Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "70.1.1"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Voicecraft Studio 70 contributors"
!define MUI_ICON "voicecraft.ico"
!define MUI_UNICON "voicecraft.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\VoiceCraft.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open VoiceCraft (first setup downloads engine packages and models)"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "VoiceCraft requires 64-bit Windows."
  Abort
 ${EndIf}
 FindWindow $0 "Voicecraft70Desktop"
 ${If} $0 != 0
  MessageBox MB_ICONINFORMATION "Exit VoiceCraft using its tray icon before installing an update."
  Abort
 ${EndIf}
FunctionEnd
Section "Voicecraft Studio 70"
 IfFileExists "$INSTDIR\*.*" 0 safe_directory
 IfFileExists "$INSTDIR\VoiceCraft.exe" safe_directory 0
 MessageBox MB_ICONSTOP "This folder contains another application or files. Choose a new VoiceCraft folder; existing files will not be overwritten."
 Abort
 safe_directory:
 SetOutPath "$INSTDIR"
 File /r "${STAGE}\*"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 CreateDirectory "$SMPROGRAMS\Voicecraft Studio 70"
 CreateShortcut "$SMPROGRAMS\Voicecraft Studio 70\Voicecraft Studio 70.lnk" "$INSTDIR\VoiceCraft.exe"
 CreateShortcut "$DESKTOP\Voicecraft Studio 70.lnk" "$INSTDIR\VoiceCraft.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoicecraftStudio70" "DisplayName" "Voicecraft Studio 70"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoicecraftStudio70" "DisplayVersion" "70.1.1"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoicecraftStudio70" "UninstallString" '"$INSTDIR\Uninstall.exe"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoicecraftStudio70" "DisplayIcon" "$INSTDIR\VoiceCraft.exe"
SectionEnd
Section "Uninstall"
 FindWindow $0 "Voicecraft70Desktop"
 ${If} $0 != 0
  MessageBox MB_ICONINFORMATION "Exit VoiceCraft from its tray icon before uninstalling."
  Abort
 ${EndIf}
 Delete "$DESKTOP\Voicecraft Studio 70.lnk"
 Delete "$SMPROGRAMS\Voicecraft Studio 70\Voicecraft Studio 70.lnk"
 RMDir "$SMPROGRAMS\Voicecraft Studio 70"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoicecraftStudio70"
 ; Only this product's installation payload is removed. Data and other applications are untouched.
 RMDir /r "$INSTDIR\app"
 RMDir /r "$INSTDIR\runtime"
 RMDir /r "$INSTDIR\desktop-window"
 Delete "$INSTDIR\VoiceCraft.exe"
 Delete "$INSTDIR\Uninstall.exe"
 RMDir "$INSTDIR"
SectionEnd
