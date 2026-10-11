Unicode true
Target amd64-unicode
!include "MUI2.nsh"
!include "x64.nsh"
Name "VoiceCraft Studio"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\VoiceCraft Studio"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=1033 "ProductName" "VoiceCraft Studio"
VIAddVersionKey /LANG=1033 "FileDescription" "VoiceCraft Studio Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "1.0.0"
VIAddVersionKey /LANG=1033 "LegalCopyright" "VoiceCraft Studio contributors"
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
 FindWindow $0 "VoiceCraftDesktop"
 ${If} $0 != 0
  MessageBox MB_ICONINFORMATION "Exit VoiceCraft using its tray icon before installing an update."
  Abort
 ${EndIf}
FunctionEnd
Section "VoiceCraft Studio"
 IfFileExists "$INSTDIR\*.*" 0 safe_directory
 IfFileExists "$INSTDIR\VoiceCraft.exe" safe_directory 0
 MessageBox MB_ICONSTOP "This folder contains another application or files. Choose a new VoiceCraft folder; existing files will not be overwritten."
 Abort
 safe_directory:
 SetOutPath "$INSTDIR"
 File /r "${STAGE}\*"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 CreateDirectory "$SMPROGRAMS\VoiceCraft Studio"
 CreateShortcut "$SMPROGRAMS\VoiceCraft Studio\VoiceCraft Studio.lnk" "$INSTDIR\VoiceCraft.exe"
 CreateShortcut "$DESKTOP\VoiceCraft Studio.lnk" "$INSTDIR\VoiceCraft.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceCraftStudio" "DisplayName" "VoiceCraft Studio"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceCraftStudio" "DisplayVersion" "1.0.0"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceCraftStudio" "UninstallString" '"$INSTDIR\Uninstall.exe"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceCraftStudio" "DisplayIcon" "$INSTDIR\VoiceCraft.exe"
SectionEnd
Section "Uninstall"
 FindWindow $0 "VoiceCraftDesktop"
 ${If} $0 != 0
  MessageBox MB_ICONINFORMATION "Exit VoiceCraft from its tray icon before uninstalling."
  Abort
 ${EndIf}
 Delete "$DESKTOP\VoiceCraft Studio.lnk"
 Delete "$SMPROGRAMS\VoiceCraft Studio\VoiceCraft Studio.lnk"
 RMDir "$SMPROGRAMS\VoiceCraft Studio"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceCraftStudio"
 ; Only this product's installation payload is removed. Data and other applications are untouched.
 RMDir /r "$INSTDIR\app"
 RMDir /r "$INSTDIR\runtime"
 Delete "$INSTDIR\VoiceCraft.exe"
 Delete "$INSTDIR\Uninstall.exe"
 RMDir "$INSTDIR"
SectionEnd
