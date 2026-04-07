#!/usr/bin/env bash
set -euo pipefail

# If launched from a GUI file manager without an interactive terminal,
# relaunch inside a terminal emulator so the prompt is visible.
if [[ ! -t 0 ]]; then
  if command -v konsole >/dev/null 2>&1; then
    exec konsole --noclose -e bash "$0"
  elif command -v x-terminal-emulator >/dev/null 2>&1; then
    exec x-terminal-emulator -e bash "$0"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

read -r -p "Nom de l'asset: " ASSET_NAME

if [[ -z "${ASSET_NAME// }" ]]; then
  echo "Nom invalide."
  exit 1
fi

ASSET_DIR="$SCRIPT_DIR/$ASSET_NAME"

if [[ -e "$ASSET_DIR" ]]; then
  echo "Le dossier existe deja: $ASSET_DIR"
  exit 1
fi

mkdir -p "$ASSET_DIR/output/textures"
touch "$ASSET_DIR/.gitkeep"
touch "$ASSET_DIR/output/.gitkeep"
touch "$ASSET_DIR/output/textures/.gitkeep"

echo "Structure creee:"
echo "- $ASSET_DIR"
echo "- $ASSET_DIR/output"
echo "- $ASSET_DIR/output/textures"
echo "- fichiers .gitkeep crees"
