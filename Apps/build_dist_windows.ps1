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

# ── 1. Build Server Python (PyInstaller) ──────────────────────────────────────
Write-Host "[1/3] Build Server Python (PyInstaller)..."
Push-Location (Join-Path $ScriptDir "Server")
& uv sync --group dev
& uv run pyinstaller `
    --onedir `
    --name riverflow-server `
    --distpath $ServerOut `
    --workpath (Join-Path $env:TEMP "pyinstaller_build_server") `
    --specpath (Join-Path $env:TEMP "pyinstaller_spec_server") `
    src\riverflow_server\main.py
Pop-Location

# ── 2. Build + copie ClientNDI (Rust) ─────────────────────────────────────────
Write-Host "[2/3] Build ClientNDI (Rust, release, target=$Target)..."
Push-Location $ScriptDir
if ($EnableNdi) {
    & cargo build -p riverflow-client-ndi --release --target $Target --features ndi
} else {
    & cargo build -p riverflow-client-ndi --release --target $Target
}
Pop-Location

New-Item -ItemType Directory -Force -Path $ClientOut | Out-Null
$TargetRelease = Join-Path $ScriptDir "target/$Target/release"
Copy-Item -Force (Join-Path $TargetRelease $ClientExe) (Join-Path $ClientOut $ClientExe)

$YamlSource = Join-Path $ScriptDir "target/release/$YamlName"
if (Test-Path $YamlSource) {
    Copy-Item -Force $YamlSource (Join-Path $ClientOut $YamlName)
}

# ── 3. NDI runtime optionnel ──────────────────────────────────────────────────
Write-Host "[3/3] NDI runtime..."
if ($EnableNdi) {
    $dll = Get-NdiDll -Hint $NdiDllPath
    if ($null -eq $dll) {
        throw "NDI DLL non trouvee. Fournir -NdiDllPath ou installer NDI Runtime."
    }
    Copy-Item -Force $dll (Join-Path $ClientOut "Processing.NDI.Lib.x64.dll")
    @"
@echo off
setlocal
set "SELF_DIR=%~dp0"
set "PATH=%SELF_DIR%;%PATH%"
"%SELF_DIR%\riverflow-client-ndi.exe" %*
endlocal
"@ | Set-Content -Encoding ASCII (Join-Path $ClientOut "run-client-ndi.bat")
    Write-Host "NDI bundlee dans Dist\windows\client"
} else {
    Write-Host "NDI desactive (mode NO SIGNAL)"
}

Write-Host ""
Write-Host "Done. Sorties :"
Write-Host "- $(Join-Path $ClientOut $ClientExe)"
Write-Host "- $ServerOut\riverflow-server\"
