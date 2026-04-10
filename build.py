#!/usr/bin/env python3
"""
Build RiverFlow binaries for Windows and/or Linux distributions.
Usage: uv run build.py [client-ndi|server-mocap|unity|client-mocap|all]
"""

import platform
import subprocess
import shutil
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> bool:
    print(f"→ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode == 0


ROOT = Path(__file__).parent
APPS = ROOT / "Apps"


def build_client_ndi() -> bool:
    print("\n=== Build: Client UDP (Linux + Windows) ===")

    dist_linux = ROOT / "Dist/linux/client"
    dist_win = ROOT / "Dist/windows/client"
    dist_linux.mkdir(parents=True, exist_ok=True)
    dist_win.mkdir(parents=True, exist_ok=True)

    ok = True

    print("\n[Linux]")
    result = subprocess.run(
        ["cargo", "build", "-p", "riverflow-client-ndi", "--release"],
        cwd=APPS
    )
    if result.returncode == 0:
        src = APPS / "target/release/riverflow-client-ndi"
        shutil.copy2(src, dist_linux / "riverflow-client-ndi")
        (dist_linux / "riverflow-client-ndi").chmod(0o755)
        yaml_src = APPS / "target/release/riverflow-client-ndi.yaml"
        if yaml_src.exists():
            shutil.copy2(yaml_src, dist_linux / "riverflow-client-ndi.yaml")
        run_sh = dist_linux / "run.sh"
        run_sh.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'exec "$SELF_DIR/riverflow-client-ndi" "$@"\n'
        )
        run_sh.chmod(0o755)
        print(f"  ✓ {dist_linux}/riverflow-client-ndi")
    else:
        print("  ✗ Build Linux client-ndi échoué")
        ok = False

    print("\n[Windows]")
    if run(["cargo", "build", "-p", "riverflow-client-ndi", "--release",
            "--target", "x86_64-pc-windows-gnu"], cwd=APPS):
        src = APPS / "target/x86_64-pc-windows-gnu/release/riverflow-client-ndi.exe"
        shutil.copy2(src, dist_win / "riverflow-client-ndi.exe")
        yaml_src = APPS / "target/release/riverflow-client-ndi.yaml"
        if yaml_src.exists():
            shutil.copy2(yaml_src, dist_win / "riverflow-client-ndi.yaml")
        print(f"  ✓ {dist_win}/riverflow-client-ndi.exe")
    else:
        print("  ✗ Build Windows client-ndi échoué")
        ok = False

    return ok


def build_server_mocap() -> bool:
    print("\n=== Build: Server Mocap (Linux + Windows) ===")

    dist_linux = ROOT / "Dist/linux/serveur"
    dist_win   = ROOT / "Dist/windows/serveur"
    dist_linux.mkdir(parents=True, exist_ok=True)
    dist_win.mkdir(parents=True, exist_ok=True)

    ok = True

    print("\n[Linux]")
    result = subprocess.run(
        ["cargo", "build", "-p", "riverflow-server", "--release"],
        cwd=APPS
    )
    if result.returncode == 0:
        src = APPS / "target/release/riverflow-server"
        shutil.copy2(src, dist_linux / "riverflow-server")
        (dist_linux / "riverflow-server").chmod(0o755)
        run_sh = dist_linux / "run.sh"
        run_sh.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'exec "$SELF_DIR/riverflow-server" "$@"\n'
        )
        run_sh.chmod(0o755)
        print(f"  ✓ {dist_linux}/riverflow-server")
    else:
        print("  ✗ Build Linux server-mocap échoué")
        ok = False

    print("\n[Windows]")
    if run(["cargo", "build", "-p", "riverflow-server", "--release",
            "--target", "x86_64-pc-windows-gnu"], cwd=APPS):
        src = APPS / "target/x86_64-pc-windows-gnu/release/riverflow-server.exe"
        shutil.copy2(src, dist_win / "riverflow-server.exe")
        print(f"  ✓ {dist_win}/riverflow-server.exe")
    else:
        print("  ✗ Build Windows server-mocap échoué")
        ok = False

    return ok


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


LAUNCH = {
    "client-ndi": {
        "Linux":   ROOT / "Dist/linux/client/run.sh",
        "Windows": ROOT / "Dist/windows/client/run-client-ndi.bat",
    },
}


def launch(target: str):
    import os
    os_name = platform.system()
    launchers = LAUNCH.get(target, {})
    launcher = launchers.get(os_name)
    if not launcher:
        return
    if not launcher.exists():
        print(f"\n⚠ Launcher introuvable : {launcher}")
        return

    print(f"\n→ Lancement : {launcher}")

    if os_name == "Linux":
        import os, glob

        uid = os.getuid()

        # Lire l'environnement depuis un process graphique actif du même user
        def get_display_env() -> dict:
            for pid_path in glob.glob("/proc/*/environ"):
                try:
                    pid = pid_path.split("/")[2]
                    if str(uid) != open(f"/proc/{pid}/status").read().split("Uid:")[1].split()[0]:
                        continue
                    raw = open(pid_path, "rb").read()
                    env = dict(
                        e.split("=", 1) for e in raw.decode(errors="replace").split("\0")
                        if "=" in e
                    )
                    if env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"):
                        return env
                except Exception:
                    continue
            return {}

        env = os.environ.copy()
        env.update(get_display_env())

        # Fallbacks
        if "XDG_RUNTIME_DIR" not in env:
            env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
        if "WAYLAND_DISPLAY" not in env:
            sockets = glob.glob(f"{env['XDG_RUNTIME_DIR']}/wayland-*")
            wayland = next((os.path.basename(s) for s in sockets if not s.endswith(".lock")), "wayland-0")
            env["WAYLAND_DISPLAY"] = wayland

        subprocess.Popen(["bash", str(launcher)], env=env, start_new_session=True)
    else:
        subprocess.Popen([str(launcher)], start_new_session=True)


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
