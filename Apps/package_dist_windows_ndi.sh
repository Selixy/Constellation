#!/usr/bin/env bash
set -euo pipefail

# Bundle NDI runtime for Windows dist output after cross-build.
# Usage:
#   ./package_dist_windows_ndi.sh /path/to/Processing.NDI.Lib.x64.dll

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_DIR="$ROOT_DIR/Dist/windows/client"
DLL_PATH="${1:-}"

if [[ -z "$DLL_PATH" ]]; then
  echo "Usage: ./package_dist_windows_ndi.sh /path/to/Processing.NDI.Lib.x64.dll"
  exit 1
fi

if [[ ! -f "$DLL_PATH" ]]; then
  echo "NDI DLL not found: $DLL_PATH"
  exit 1
fi

if [[ ! -f "$CLIENT_DIR/riverflow-client-ndi.exe" ]]; then
  echo "Missing client executable: $CLIENT_DIR/riverflow-client-ndi.exe"
  echo "Build first (cross-build):"
  echo "  cd Apps && cargo build -p riverflow-client-ndi --release --target x86_64-pc-windows-gnu"
  exit 1
fi

mkdir -p "$CLIENT_DIR"
cp "$DLL_PATH" "$CLIENT_DIR/Processing.NDI.Lib.x64.dll"

cat > "$CLIENT_DIR/run-client-ndi.bat" <<'EOF'
@echo off
setlocal
set "SELF_DIR=%~dp0"
set "PATH=%SELF_DIR%;%PATH%"
"%SELF_DIR%\\riverflow-client-ndi.exe" %*
endlocal
EOF

echo "NDI runtime bundled in: $CLIENT_DIR"
echo "Launcher created: $CLIENT_DIR/run-client-ndi.bat"
