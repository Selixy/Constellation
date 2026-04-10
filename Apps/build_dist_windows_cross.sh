#!/usr/bin/env bash
set -euo pipefail

# Cross-compile Windows binaries depuis Linux et les place dans Dist/windows/
# Requiert : rustup target add x86_64-pc-windows-gnu  +  mingw-w64
#
# Usage :
#   ./build_dist_windows_cross.sh
#   ./build_dist_windows_cross.sh --ndi /path/to/Processing.NDI.Lib.x64.dll

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="x86_64-pc-windows-gnu"
TARGET_RELEASE="$SCRIPT_DIR/target/$TARGET/release"
CLIENT_OUT="$ROOT_DIR/Dist/windows/client"
SERVER_OUT="$ROOT_DIR/Dist/windows/serveur"

ENABLE_NDI=0
NDI_DLL_INPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ndi) ENABLE_NDI=1; NDI_DLL_INPUT="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

find_ndi_dll() {
  local candidates=(
    "$NDI_DLL_INPUT"
    "$CLIENT_OUT/Processing.NDI.Lib.x64.dll"
    "/mnt/c/Program Files/NDI/NDI 6 Runtime/v6/Processing.NDI.Lib.x64.dll"
    "/mnt/c/Program Files/NDI/NDI 5 Runtime/v5/Processing.NDI.Lib.x64.dll"
  )
  for c in "${candidates[@]}"; do
    if [[ -n "$c" && -f "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

echo "[1/4] Build server Windows (release, target=$TARGET)..."
cd "$SCRIPT_DIR"
cargo build -p riverflow-server --release --target "$TARGET"

echo "[2/4] Build client Windows (release, target=$TARGET)..."
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! cargo build -p riverflow-client-ndi --release --target "$TARGET" --features ndi; then
    echo "Warning: NDI-feature build failed, fallback sans NDI."
    cargo build -p riverflow-client-ndi --release --target "$TARGET"
  fi
else
  cargo build -p riverflow-client-ndi --release --target "$TARGET"
fi

echo "[3/4] Copy binaires dans Dist/windows/..."
mkdir -p "$CLIENT_OUT" "$SERVER_OUT"
cp "$TARGET_RELEASE/riverflow-server.exe"        "$SERVER_OUT/riverflow-server.exe"
cp "$TARGET_RELEASE/riverflow-client-ndi.exe"    "$CLIENT_OUT/riverflow-client-ndi.exe"

YAML_SOURCE="$SCRIPT_DIR/target/release/riverflow-client-ndi.yaml"
if [[ -f "$YAML_SOURCE" ]]; then
  cp "$YAML_SOURCE" "$CLIENT_OUT/riverflow-client-ndi.yaml"
fi

echo "[4/4] NDI runtime Windows..."
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! NDI_DLL="$(find_ndi_dll)"; then
    echo "NDI DLL non trouvee. Fournir avec --ndi /path/to/Processing.NDI.Lib.x64.dll"
    exit 1
  fi
  cp "$NDI_DLL" "$CLIENT_OUT/Processing.NDI.Lib.x64.dll"
  cat > "$CLIENT_OUT/run-client-ndi.bat" <<'EOF'
@echo off
setlocal
set "SELF_DIR=%~dp0"
set "PATH=%SELF_DIR%;%PATH%"
"%SELF_DIR%\riverflow-client-ndi.exe" %*
endlocal
EOF
  echo "NDI bundlee dans Dist/windows/client"
else
  echo "NDI feature desactivee (mode NO SIGNAL)"
fi

echo
echo "Done. Sorties :"
echo "- $SERVER_OUT/riverflow-server.exe"
echo "- $CLIENT_OUT/riverflow-client-ndi.exe"
