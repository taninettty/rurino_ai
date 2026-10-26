# Creates the desktop / Start Menu shortcut (and optionally autostart).
param([switch]$Autostart)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$launcher = Join-Path $root 'launcher.py'
$icon = Join-Path $root 'assets\rurino.ico'
if (-not (Test-Path $pythonw)) { throw 'Install-Windows.cmd must run first (.venv missing).' }

$shell = New-Object -ComObject WScript.Shell
function New-Link([string]$path) {
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + $launcher + '"'
    $shortcut.WorkingDirectory = $root
    if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
    $shortcut.Description = '瑠璃乃桌宠'
    $shortcut.Save()
    Write-Host "created $path"
}

New-Link (Join-Path ([Environment]::GetFolderPath('Desktop')) '瑠璃乃.lnk')
New-Link (Join-Path ([Environment]::GetFolderPath('Programs')) '瑠璃乃.lnk')
if ($Autostart) {
    New-Link (Join-Path ([Environment]::GetFolderPath('Startup')) '瑠璃乃.lnk')
} else {
    $startupLink = Join-Path ([Environment]::GetFolderPath('Startup')) '瑠璃乃.lnk'
    if (Test-Path $startupLink) { Write-Host "autostart already enabled: $startupLink" }
}
