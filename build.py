#!/usr/bin/env python3
"""
Build RiverFlow binaries for Windows and/or Linux distributions.
Usage: uv run build.py [client-ndi|server-mocap|unity|client-mocap|all]
"""

import subprocess
import shutil
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> bool:
    print(f"→ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode == 0


ROOT = Path(__file__).parent
APPS = ROOT / "Apps"
NDI_SDK = APPS / "ndi-sdk"


def build_client_ndi() -> bool:
    print("\n=== Build: Client NDI (Linux + Windows) ===")

    dist_linux = ROOT / "Dist/linux/client"
    dist_win = ROOT / "Dist/windows/client"
    dist_linux.mkdir(parents=True, exist_ok=True)
    dist_win.mkdir(parents=True, exist_ok=True)

    ok = True

    # Linux (avec NDI — link sur stub, runtime charge le vrai .so via LD_LIBRARY_PATH)
    print("\n[Linux]")
    env_ndi = {
        **__import__("os").environ,
        "NDI_SDK_DIR": str(NDI_SDK),
        "RUSTFLAGS": "-C linker=gcc",
    }
    result = subprocess.run(
        ["cargo", "build", "-p", "riverflow-client-ndi", "--release", "--features", "ndi"],
        cwd=APPS, env=env_ndi
    )
    if result.returncode == 0:
        src = APPS / "target/release/riverflow-client-ndi"
        shutil.copy2(src, dist_linux / "riverflow-client-ndi")
        (dist_linux / "riverflow-client-ndi").chmod(0o755)
        yaml_src = APPS / "target/release/riverflow-client-ndi.yaml"
        if yaml_src.exists():
            shutil.copy2(yaml_src, dist_linux / "riverflow-client-ndi.yaml")
        # Copier le vrai .so NDI + symlinks dans Dist si pas déjà présents
        real_so = dist_linux / "libndi.so.6.3.1"
        if not real_so.exists():
            print("  ⚠ libndi.so.6.3.1 absent de Dist/linux/client — à copier manuellement depuis le NDI runtime")
        # Écrire run.sh avec LD_LIBRARY_PATH
        run_sh = dist_linux / "run.sh"
        run_sh.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'export LD_LIBRARY_PATH="$SELF_DIR:${LD_LIBRARY_PATH:-}"\n'
            'exec "$SELF_DIR/riverflow-client-ndi" "$@"\n'
        )
        run_sh.chmod(0o755)
        print(f"  ✓ {dist_linux}/riverflow-client-ndi")
    else:
        print("  ✗ Build Linux client-ndi échoué")
        ok = False

    # Windows (cross-compile sans NDI — grafton-ndi ne supporte pas le cross-compile Linux→Windows)
    # Pour un build Windows avec NDI, builder nativement sur Windows avec build_dist_windows.ps1
    print("\n[Windows] (sans NDI — NO SIGNAL mode)")
    if run(["cargo", "build", "-p", "riverflow-client-ndi", "--release",
            "--target", "x86_64-pc-windows-gnu"], cwd=APPS):
        src = APPS / "target/x86_64-pc-windows-gnu/release/riverflow-client-ndi.exe"
        shutil.copy2(src, dist_win / "riverflow-client-ndi.exe")
        yaml_src = APPS / "target/release/riverflow-client-ndi.yaml"
        if yaml_src.exists():
            shutil.copy2(yaml_src, dist_win / "riverflow-client-ndi.yaml")
        print(f"  ✓ {dist_win}/riverflow-client-ndi.exe (NO SIGNAL — NDI nécessite un build natif Windows)")
    else:
        print("  ✗ Build Windows client-ndi échoué")
        ok = False

    return ok


def build_server_mocap() -> bool:
    print("\n=== Build: Server Mocap (non encore implémenté) ===")
    print("  ⚠ Projet Python — packaging (PyInstaller ou autre) à définir")
    return True


def build_unity() -> bool:
    print("\n=== Build: Projet Unity (non encore implémenté) ===")
    print("  ⚠ Build Unity à configurer (Unity CLI headless)")
    return True


def build_client_mocap() -> bool:
    print("\n=== Build: Client Mocap (non encore implémenté) ===")
    print("  ⚠ Client Mocap à créer")
    return True


TARGETS = {
    "client-ndi":    build_client_ndi,
    "server-mocap":  build_server_mocap,
    "unity":         build_unity,
    "client-mocap":  build_client_mocap,
    "all":           None,
}


def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if target not in TARGETS:
        print(f"Target inconnu : {target}")
        print(f"Usage: uv run build.py [{' | '.join(TARGETS)}]")
        sys.exit(1)

    if target == "all":
        results = {name: fn() for name, fn in TARGETS.items() if fn is not None}
    else:
        results = {target: TARGETS[target]()}

    print("\n" + "=" * 50)
    ok = all(results.values())
    for name, success in results.items():
        print(f"  {'✓' if success else '✗'} {name}")
    print("=" * 50)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
