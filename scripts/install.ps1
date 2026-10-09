param([string]$Target = 'C:\VoiceCloner')
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $PSScriptRoot
function Run-Python([string[]]$Arguments) {
    & $script:Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed. Read the error above. Existing voice data has not been deleted." }
}
Write-Host 'VOICE CONTROL ROOM ADVANCED - backup-first installation / repair'
& py -3.11 -c "import sys; assert sys.version_info[:2] == (3,11)"
if ($LASTEXITCODE -ne 0) { throw 'Install 64-bit Python 3.11 from python.org, including the Python launcher, then run this file again.' }
$Target = [System.IO.Path]::GetFullPath($Target)
$Source = [System.IO.Path]::GetFullPath($Source)
$Data = Join-Path $env:LOCALAPPDATA 'VoiceControlRoom'
$PortCheck = New-Object System.Net.Sockets.TcpClient
try {
    $Connection = $PortCheck.ConnectAsync('127.0.0.1', 8765)
    if ($Connection.Wait(1000) -and $PortCheck.Connected) { throw 'A server is using port 8765. Close the existing application before backup and repair.' }
} catch [System.AggregateException] {
    # Connection refused is expected when no local server is running.
} finally { $PortCheck.Dispose() }
# Preserve every existing file before deployment. A failed archive/verification stops installation.
$script:Python = 'py'
function Backup-Folder([string]$Folder) {
    if (-not (Test-Path $Folder)) { return }
    $BackupRoot = Join-Path $env:LOCALAPPDATA 'VoiceControlRoom-Backups'
    & py -3.11 (Join-Path $Source 'scripts\backup_existing.py') $Folder $BackupRoot
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed. No installation files will be overwritten.' }
}
# Refuse repair while the server or its retained lock is active.
if (Test-Path (Join-Path $Data 'server.lock')) {
    $LockCheck = $null
    try { $LockCheck = [System.IO.File]::Open((Join-Path $Data 'server.lock'), 'Open', 'ReadWrite', 'None') }
    catch { throw 'Close Voice Control Room before installation, backup, or repair.' }
    finally { if ($LockCheck) { $LockCheck.Dispose() } }
}
Backup-Folder $Target
Backup-Folder $Data
# Deploy into a new version directory; never overwrite unknown legacy source files.
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$Target = Join-Path $Target ('VoiceControlRoomAdvanced-' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff'))
New-Item -ItemType Directory -Path $Target | Out-Null
if ($Source -ne $Target) {
    foreach ($Name in @('studio','scripts','docs','tests','requirements.txt','requirements-engine.txt','requirements-dev.txt','constraints-engine.txt','README.md','Start Voice Control Room.cmd','Install or Repair.cmd','Download Models.cmd','Backup Data.cmd','Diagnostics.cmd')) {
        $Item = Join-Path $Source $Name
        if (Test-Path $Item) { Copy-Item $Item -Destination $Target -Recurse -Force }
    }
}
New-Item -ItemType Directory -Force -Path $Data | Out-Null
# Set explicit user-only ACLs, including removal of pre-existing broad explicit grants.
function Protect-Folder([string]$Folder) {
    if (-not (Test-Path $Folder)) { return }
    $UserSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $Allowed = @($UserSid, (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')), (New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    $Items = @((Get-Item $Folder)) + @(Get-ChildItem $Folder -Recurse -Force)
    foreach ($Item in $Items) {
        if ($Item.PSIsContainer) {
            $Acl = New-Object System.Security.AccessControl.DirectorySecurity
            $Flags = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
        } else {
            $Acl = New-Object System.Security.AccessControl.FileSecurity
            $Flags = [System.Security.AccessControl.InheritanceFlags]::None
        }
        $Acl.SetAccessRuleProtection($true, $false)
        $Acl.SetOwner($UserSid)
        foreach ($Sid in $Allowed) {
            $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule($Sid, 'FullControl', $Flags, 'None', 'Allow')
            $Acl.AddAccessRule($Rule)
        }
        Set-Acl -LiteralPath $Item.FullName -AclObject $Acl
    }
}
Protect-Folder $Data
Protect-Folder (Join-Path $env:LOCALAPPDATA 'VoiceControlRoom-Backups')
# A fresh side-by-side environment keeps a broken/previous environment recoverable.
$EnvName = '.venv-vcr-' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff')
$EnvPath = Join-Path $Target $EnvName
& py -3.11 -m venv $EnvPath
if ($LASTEXITCODE -ne 0) { throw 'Could not create a Python environment.' }
$script:Python = Join-Path $EnvPath 'Scripts\python.exe'
Push-Location $Target
try {
    Run-Python -Arguments @('-m','pip','install','--upgrade','pip==25.1.1')
    # cu124 PyTorch 2.6 supports the RTX 2060. Requires a compatible NVIDIA driver.
    Run-Python -Arguments @('-m','pip','install','torch==2.6.0','torchaudio==2.6.0','--index-url','https://download.pytorch.org/whl/cu124')
    Run-Python -Arguments @('-m','pip','install','-r','requirements-engine.txt')
    Run-Python -Arguments @('-m','pip','check')
    Run-Python -Arguments @('-m','studio.cli','doctor')
    $Relative = $EnvName + '\Scripts\python.exe'
    [System.IO.File]::WriteAllText((Join-Path $Target 'python-path.txt'), $Relative, [System.Text.Encoding]::ASCII)
    Write-Host 'Packages installed. Downloading and verifying both voice models (several GB)...'
    Run-Python -Arguments @('-m','studio.cli','download-models','--engine','all')
    Run-Python -Arguments @('-m','studio.cli','verify-models','--engine','all')
    # Use a unique shortcut; do not replace an existing user shortcut.
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $ShortcutPath = Join-Path $Desktop ('Voice Control Room Advanced ' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff') + '.lnk')
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Join-Path $Target 'Start Voice Control Room.cmd'
    $Shortcut.WorkingDirectory = $Target
    $Shortcut.Description = 'Private local voice cloning studio'
    $Shortcut.Save()
    Write-Host ('Installation finished. Double-click the new desktop shortcut, or ' + (Join-Path $Target 'Start Voice Control Room.cmd'))
    Write-Host 'Previous installation files were backed up. Existing voice files need explicit import; unknown profile formats are not migrated automatically.'
} finally { Pop-Location }
