param(
    [string]$Target = "x86_64-pc-windows-msvc",
    [switch]$EnableNdi,
    [string]$NdiDllPath = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$ClientOut = Join-Path $RootDir "Dist/windows/client"
$ServerOut = Join-Path $RootDir "Dist/windows/serveur"

$ClientExe = "riverflow-client-ndi.exe"
$ServerExe = "riverflow-server.exe"
$YamlName = "riverflow-client-ndi.yaml"

function Get-NdiDll {
    param([string]$Hint)

    $candidates = @()
    if ($Hint -ne "") { $candidates += $Hint }
    $candidates += @(
        "C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll",
        "C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll",
        "C:\Program Files\NDI\NDI Runtime\Processing.NDI.Lib.x64.dll"
    )

    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }

    return $null
}

Write-Host "[1/4] Build server (release, target=$Target)..."
& cargo build -p riverflow-server --release --target $Target

Write-Host "[2/4] Build client (release, target=$Target)..."
if ($EnableNdi) {
    & cargo build -p riverflow-client-ndi --release --target $Target --features ndi
} else {
    & cargo build -p riverflow-client-ndi --release --target $Target
}

Write-Host "[3/4] Copy binaries to Dist/windows/..."
New-Item -ItemType Directory -Force -Path $ClientOut | Out-Null
New-Item -ItemType Directory -Force -Path $ServerOut | Out-Null

$TargetRelease = Join-Path $ScriptDir "target/$Target/release"
Copy-Item -Force (Join-Path $TargetRelease $ServerExe) (Join-Path $ServerOut $ServerExe)
Copy-Item -Force (Join-Path $TargetRelease $ClientExe) (Join-Path $ClientOut $ClientExe)

$YamlSource = Join-Path $ScriptDir "target/release/$YamlName"
$YamlDest = Join-Path $ClientOut $YamlName
if (Test-Path $YamlSource) {
    Copy-Item -Force $YamlSource $YamlDest
} else {
    @"
streams:
  - id: camera_1
    ip: 127.0.0.1
  - id: camera_2
    ip: 127.0.0.2
  - id: camera_3
    ip: 127.0.0.3
  - id: camera_4
    ip: 127.0.0.4
"@ | Set-Content -Encoding UTF8 $YamlDest
}

Write-Host "[4/4] Optional NDI runtime copy..."
if ($EnableNdi) {
    $dll = Get-NdiDll -Hint $NdiDllPath
    if ($null -eq $dll) {
        throw "NDI DLL not found. Provide -NdiDllPath or install NDI Runtime."
    }

    Copy-Item -Force $dll (Join-Path $ClientOut "Processing.NDI.Lib.x64.dll")
    @"
@echo off
setlocal
set "SELF_DIR=%~dp0"
set "PATH=%SELF_DIR%;%PATH%"
"%SELF_DIR%\\riverflow-client-ndi.exe" %*
endlocal
"@ | Set-Content -Encoding ASCII (Join-Path $ClientOut "run-client-ndi.bat")
    Write-Host "NDI runtime bundled in Dist/windows/client"
} else {
    Write-Host "NDI feature disabled (client runs in NO SIGNAL mode only)"
}

Write-Host ""
Write-Host "Done. Outputs:"
Write-Host "- $(Join-Path $ServerOut $ServerExe)"
Write-Host "- $(Join-Path $ClientOut $ClientExe)"
Write-Host "- $YamlDest"
