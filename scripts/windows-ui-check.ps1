param([Parameter(Mandatory=$true)][string]$Exe,
      [Parameter(Mandatory=$true)][string]$Report,
      [Parameter(Mandatory=$true)][string]$Screenshot)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class FamilyWindowCapture {
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct Point { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out Rect r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref Point p);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int hgt, uint flags);
}
'@
$p = Start-Process $Exe -PassThru
$ready = $false
try {
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $p.Refresh()
        if ($p.HasExited) { throw "Native application exited: $($p.ExitCode)" }
        $handle = $p.MainWindowHandle
        if ($handle -eq [IntPtr]::Zero) { continue }
        if ($p.MainWindowTitle -ne 'Family AI Voice Cloner Pro') { throw "Unexpected native window: $($p.MainWindowTitle)" }
        [FamilyWindowCapture]::ShowWindow($handle, 9) | Out-Null
        [FamilyWindowCapture]::SetWindowPos($handle, [IntPtr]::Zero, 10, 10, 1000, 700, 0x0040) | Out-Null
        [FamilyWindowCapture]::SetForegroundWindow($handle) | Out-Null
        $rect = New-Object FamilyWindowCapture+Rect
        $origin = New-Object FamilyWindowCapture+Point
        if (![FamilyWindowCapture]::GetClientRect($handle, [ref]$rect) -or ![FamilyWindowCapture]::ClientToScreen($handle, [ref]$origin)) { continue }
        $width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
        if ($width -lt 500 -or $height -lt 400) { continue }
        $bitmap = New-Object System.Drawing.Bitmap($width, $height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.CopyFromScreen($origin.X, $origin.Y, 0, 0, $bitmap.Size)
            $colors = New-Object 'System.Collections.Generic.HashSet[int]'
            $bluePixels = 0; $brightPixels = 0
            for ($y=0; $y -lt $height; $y+=8) {
                for ($x=0; $x -lt $width; $x+=8) {
                    $color = $bitmap.GetPixel($x,$y)
                    $colors.Add(([int]($color.R/32) -shl 10) -bor ([int]($color.G/32) -shl 5) -bor [int]($color.B/32)) | Out-Null
                    if ($color.B -gt 140 -and $color.B -gt ($color.R+25) -and $color.B -gt ($color.G+10)) { $bluePixels++ }
                    if ($color.R -gt 180 -and $color.G -gt 180 -and $color.B -gt 180) { $brightPixels++ }
                }
            }
            $bitmap.Save([IO.Path]::GetFullPath($Screenshot), [System.Drawing.Imaging.ImageFormat]::Png)
            if ($colors.Count -ge 8 -and $bluePixels -ge 25 -and $brightPixels -ge 20) {
                $ready = $true
                @{native_window=$true; real_desktop_pixels=$true; screenshot_method='Windows client-area screen capture'; colors=$colors.Count; blue_pixels=$bluePixels; bright_pixels=$brightPixels; window_title=$p.MainWindowTitle; physical_microphone='unrun'} | ConvertTo-Json | Set-Content $Report
                break
            }
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
    }
    if (!$ready) { throw "Native window remained visually blank (colors=$($colors.Count), blue=$bluePixels, text=$brightPixels)." }
} finally {
    $p.Refresh()
    if (!$p.HasExited) {
        $p.CloseMainWindow() | Out-Null
        if (!$p.WaitForExit(20000)) { $p.Kill(); throw 'Native application failed to close gracefully.' }
    }
}
