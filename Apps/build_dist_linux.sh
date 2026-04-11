#!/usr/bin/env bash
set -euo pipefail

# Build et package les apps RiverFlow pour Linux
#   - ClientNDI  : Rust (cargo)
#   - Server     : Python UV + PyInstaller
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
  )
  for c in "${candidates[@]}"; do
    if [[ -n "$c" && -f "$c" ]]; then
      echo "$c"; return 0
    fi
  done
  return 1
}

# ── 1. Build ClientNDI (Rust) ──────────────────────────────────────────────────
echo "[1/4] Build ClientNDI (Rust, release)..."
cd "$SCRIPT_DIR"
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! cargo build -p riverflow-client-ndi --release --features ndi; then
    echo "Warning: NDI build failed, fallback sans feature NDI."
    cargo build -p riverflow-client-ndi --release
  fi
else
  cargo build -p riverflow-client-ndi --release
fi

# ── 2. Build Server (Python / PyInstaller) ─────────────────────────────────────
echo "[2/4] Build Server Python (PyInstaller)..."
cd "$SCRIPT_DIR/Server"
# Installe les deps + pyinstaller via uv si pas déjà fait
uv sync --group dev
uv run pyinstaller \
  --onedir \
  --name riverflow-server \
  --distpath "$SERVER_OUT" \
  --workpath /tmp/pyinstaller_build_server \
  --specpath /tmp/pyinstaller_spec_server \
  src/riverflow_server/main.py

# ── 3. Copie ClientNDI dans Dist ───────────────────────────────────────────────
echo "[3/4] Copie ClientNDI dans Dist/linux/client..."
mkdir -p "$CLIENT_OUT"
cp "$SCRIPT_DIR/target/release/riverflow-client-ndi" "$CLIENT_OUT/riverflow-client-ndi"
chmod +x "$CLIENT_OUT/riverflow-client-ndi"
if [[ -f "$SCRIPT_DIR/target/release/riverflow-client-ndi.yaml" ]]; then
  cp "$SCRIPT_DIR/target/release/riverflow-client-ndi.yaml" "$CLIENT_OUT/riverflow-client-ndi.yaml"
fi

# ── 4. NDI runtime optionnel ───────────────────────────────────────────────────
echo "[4/4] NDI runtime optionnel..."
if [[ "$ENABLE_NDI" -eq 1 ]]; then
  if ! NDI_LIB_PATH="$(find_ndi_lib)"; then
    echo "NDI runtime lib non trouvée."
    echo "Fournir le chemin : ./build_dist_linux.sh --ndi /path/to/libndi.so.6.3.1"
    exit 1
  fi
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
  echo "NDI runtime bundlé dans Dist/linux/client"
else
  echo "NDI désactivé (mode NO SIGNAL)"
fi

echo
echo "Done. Sorties :"
echo "- $CLIENT_OUT/riverflow-client-ndi"
echo "- $SERVER_OUT/riverflow-server/"
