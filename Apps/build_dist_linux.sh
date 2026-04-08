#!/usr/bin/env bash
set -euo pipefail

# Build Rust apps and place outputs in Dist/linux/{client,serveur}
#
# Usage:
#   ./build_dist_linux.sh
#   ./build_dist_linux.sh --ndi /path/to/libndi.so.6.3.1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_OUT="$ROOT_DIR/Dist/linux/client"
SERVER_OUT="$ROOT_DIR/Dist/linux/serveur"

ENABLE_NDI=0
NDI_LIB_INPUT=""

if [[ "${1:-}" == "--ndi" ]]; then
  ENABLE_NDI=1
  NDI_LIB_INPUT="${2:-}"
fi

find_ndi_lib() {
  local candidates=(
    "$NDI_LIB_INPUT"
    "/usr/lib/x86_64-linux-gnu/libndi.so.6"
    "/usr/local/lib/libndi.so.6"
    "/usr/local/lib/libndi.so"
    "/opt/ndi/lib/x86_64-linux-gnu/libndi.so.6"
    "/usr/share/NDI SDK for Linux/lib/x86_64-linux-gnu/libndi.so.6"
    "/usr/share/NDI SDK for Linux/lib/x86_64-linux-gnu/libndi.so.6.3.1"
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

echo "[1/4] Build server (release)..."
cd "$SCRIPT_DIR"
cargo build -p riverflow-server --release

echo "[2/4] Build client (release)..."
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! cargo build -p riverflow-client-ndi --release --features ndi; then
    echo "Warning: NDI-feature build failed, falling back to standard build (NO SIGNAL mode)."
    cargo build -p riverflow-client-ndi --release
  fi
else
  cargo build -p riverflow-client-ndi --release
fi

echo "[3/4] Copy binaries to Dist/linux/..."
mkdir -p "$CLIENT_OUT" "$SERVER_OUT"
cp "$SCRIPT_DIR/target/release/riverflow-server" "$SERVER_OUT/riverflow-server"
cp "$SCRIPT_DIR/target/release/riverflow-client-ndi" "$CLIENT_OUT/riverflow-client-ndi"
chmod +x "$SERVER_OUT/riverflow-server" "$CLIENT_OUT/riverflow-client-ndi"

if [[ -f "$SCRIPT_DIR/target/release/riverflow-client-ndi.yaml" ]]; then
  cp "$SCRIPT_DIR/target/release/riverflow-client-ndi.yaml" "$CLIENT_OUT/riverflow-client-ndi.yaml"
fi

echo "[4/4] Optional NDI runtime copy..."
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! NDI_LIB_PATH="$(find_ndi_lib)"; then
    echo "NDI runtime lib not found."
    echo "Provide path as second argument:"
    echo "  ./build_dist_linux.sh --ndi /path/to/libndi.so.6.3.1"
    exit 1
  fi

  # NDI Linux runtime is expected as libndi.so.6 at runtime.
  if [[ "$(basename "$NDI_LIB_PATH")" == libndi.so* ]]; then
    local_ndi_file="$(basename "$NDI_LIB_PATH")"
    cp "$NDI_LIB_PATH" "$CLIENT_OUT/$local_ndi_file"
    ln -sfn "$local_ndi_file" "$CLIENT_OUT/libndi.so.6"
    ln -sfn "$local_ndi_file" "$CLIENT_OUT/libndi.so"
  else
    cp "$NDI_LIB_PATH" "$CLIENT_OUT/Processing.NDI.Lib.x86_64.so"
  fi
  cat > "$CLIENT_OUT/run.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$SELF_DIR:${LD_LIBRARY_PATH:-}"
exec "$SELF_DIR/riverflow-client-ndi" "$@"
EOF
  chmod +x "$CLIENT_OUT/run.sh"
  echo "NDI runtime bundled in Dist/linux/client"
else
  echo "NDI feature disabled (client will run in NO SIGNAL mode only)"
fi

echo
echo "Done. Outputs:"
echo "- $SERVER_OUT/riverflow-server"
echo "- $CLIENT_OUT/riverflow-client-ndi"
if [[ -f "$CLIENT_OUT/riverflow-client-ndi.yaml" ]]; then
  echo "- $CLIENT_OUT/riverflow-client-ndi.yaml"
fi
