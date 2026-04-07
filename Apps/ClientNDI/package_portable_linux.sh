#!/usr/bin/env bash
set -euo pipefail

# Build and package a portable ClientNDI folder for Linux.
# Usage:
#   ./package_portable_linux.sh /path/to/Processing.NDI.Lib.x86_64.so
#
# If no path is provided, the script tries common locations.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$WORKSPACE_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/Dist/linux/client/riverflow-client-ndi"
BIN_PATH="$WORKSPACE_DIR/target/release/riverflow-client-ndi"
YAML_NAME="riverflow-client-ndi.yaml"

RUNTIME_LIB_INPUT="${1:-}"

find_ndi_lib() {
  local candidates=(
    "$RUNTIME_LIB_INPUT"
    "/usr/lib/Processing.NDI.Lib.x86_64.so"
    "/usr/local/lib/Processing.NDI.Lib.x86_64.so"
    "/opt/ndi/lib/x86_64-linux-gnu/Processing.NDI.Lib.x86_64.so"
    "/usr/share/NDI SDK for Linux/lib/x86_64-linux-gnu/Processing.NDI.Lib.x86_64.so"
  )

  for c in "${candidates[@]}"; do
    if [[ -n "$c" && -f "$c" ]]; then
      echo "$c"
      return 0
    fi
  done

  return 1
}

echo "[1/4] Building release binary with NDI feature..."
cd "$WORKSPACE_DIR"
cargo build -p riverflow-client-ndi --release --features ndi

if [[ ! -f "$BIN_PATH" ]]; then
  echo "Build succeeded but binary not found at: $BIN_PATH"
  exit 1
fi

echo "[2/4] Locating NDI runtime shared library..."
if ! NDI_LIB_PATH="$(find_ndi_lib)"; then
  echo "NDI runtime lib not found."
  echo "Provide it explicitly:"
  echo "  ./package_portable_linux.sh /path/to/Processing.NDI.Lib.x86_64.so"
  exit 1
fi

echo "Using NDI runtime: $NDI_LIB_PATH"

echo "[3/4] Creating portable folder..."
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

cp "$BIN_PATH" "$OUT_DIR/riverflow-client-ndi"
chmod +x "$OUT_DIR/riverflow-client-ndi"

cp "$WORKSPACE_DIR/target/release/$YAML_NAME" "$OUT_DIR/$YAML_NAME"
cp "$NDI_LIB_PATH" "$OUT_DIR/Processing.NDI.Lib.x86_64.so"

echo "[4/4] Writing launcher script with local library path..."
cat > "$OUT_DIR/run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$SELF_DIR:${LD_LIBRARY_PATH:-}"
exec "$SELF_DIR/riverflow-client-ndi" "$@"
EOF
chmod +x "$OUT_DIR/run.sh"

echo
echo "Portable package created: $OUT_DIR"
echo "Run with: $OUT_DIR/run.sh"
