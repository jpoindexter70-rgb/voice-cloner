param([Parameter(Mandatory=$true)][string]$Exe,
      [Parameter(Mandatory=$true)][string[]]$Arguments,
      [int]$TimeoutSeconds=900)
$ErrorActionPreference = 'Stop'
$p = Start-Process -FilePath $Exe -ArgumentList $Arguments -PassThru
if (!$p.WaitForExit($TimeoutSeconds * 1000)) {
    try { $p.Kill($true); $p.WaitForExit() } catch { }
    throw "Timed out after $TimeoutSeconds seconds: $([IO.Path]::GetFileName($Exe)). See the installer and application diagnostic logs."
}
if ($p.ExitCode -ne 0) {
    throw "Windows process failed with exit code $($p.ExitCode): $([IO.Path]::GetFileName($Exe)). See the installer and application diagnostic logs."
}
