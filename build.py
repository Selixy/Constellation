#!/usr/bin/env python3
"""
Build RiverFlow binaries for Windows and/or Linux distributions.
Usage: uv run build.py [windows|linux|all]
"""

import subprocess
import shutil
import sys
from pathlib import Path
from typing import Literal

def run_command(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Run a shell command and return exit code."""
    print(f"→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=check)
    return result.returncode

def build_windows() -> bool:
    """Build Windows binaries (cross-compile from Linux or native on Windows)."""
    print("\n" + "=" * 60)
    print("Building Windows binaries...")
    print("=" * 60)
    
    root = Path(__file__).parent
    apps_dir = root / "Apps"
    dist_client = root / "Dist" / "windows" / "client"
    dist_serveur = root / "Dist" / "windows" / "serveur"
    
    dist_client.mkdir(parents=True, exist_ok=True)
    dist_serveur.mkdir(parents=True, exist_ok=True)
    
    # Build server
    print("\n[1/3] Building server (Windows)...")
    if run_command(
        ["cargo", "build", "-p", "riverflow-server", "--release", "--target", "x86_64-pc-windows-gnu"],
        cwd=apps_dir,
        check=False
    ) != 0:
        print("⚠️  Server build failed (may be expected on non-Windows)")
        return False
    
    # Build client
    print("\n[2/3] Building client (Windows)...")
    if run_command(
        ["cargo", "build", "-p", "riverflow-client-ndi", "--release", "--target", "x86_64-pc-windows-gnu"],
        cwd=apps_dir,
        check=False
    ) != 0:
        print("⚠️  Client build failed (may be expected on non-Windows)")
        return False
    
    # Copy to Dist
    print("\n[3/3] Copying to Dist/windows/...")
    target_dir = apps_dir / "target" / "x86_64-pc-windows-gnu" / "release"
    
    server_src = target_dir / "riverflow-server.exe"
    client_src = target_dir / "riverflow-client-ndi.exe"
    client_yaml = apps_dir / "target" / "x86_64-pc-windows-gnu" / "release" / "riverflow-client-ndi.yaml"
    
    if server_src.exists():
        shutil.copy2(server_src, dist_serveur / "riverflow-server.exe")
        print(f"  ✓ Copied server to {dist_serveur / 'riverflow-server.exe'}")
    
    if client_src.exists():
        shutil.copy2(client_src, dist_client / "riverflow-client-ndi.exe")
        print(f"  ✓ Copied client to {dist_client / 'riverflow-client-ndi.exe'}")
    
    if client_yaml.exists():
        shutil.copy2(client_yaml, dist_client / "riverflow-client-ndi.yaml")
        print(f"  ✓ Copied YAML to {dist_client / 'riverflow-client-ndi.yaml'}")
    
    print("\n✅ Windows build completed!")
    return True

def build_linux() -> bool:
    """Build Linux binaries."""
    print("\n" + "=" * 60)
    print("Building Linux binaries...")
    print("=" * 60)
    
    root = Path(__file__).parent
    apps_dir = root / "Apps"
    dist_client = root / "Dist" / "linux" / "client"
    dist_serveur = root / "Dist" / "linux" / "serveur"
    
    dist_client.mkdir(parents=True, exist_ok=True)
    dist_serveur.mkdir(parents=True, exist_ok=True)
    
    # Build server
    print("\n[1/2] Building server (Linux)...")
    if run_command(
        ["cargo", "build", "-p", "riverflow-server", "--release"],
        cwd=apps_dir,
        check=False
    ) != 0:
        print("❌ Server build failed")
        return False
    
    # Build client
    print("\n[2/2] Building client (Linux)...")
    if run_command(
        ["cargo", "build", "-p", "riverflow-client-ndi", "--release"],
        cwd=apps_dir,
        check=False
    ) != 0:
        print("❌ Client build failed")
        return False
    
    # Copy to Dist
    print("\n[3/3] Copying to Dist/linux/...")
    target_dir = apps_dir / "target" / "release"
    
    server_src = target_dir / "riverflow-server"
    client_src = target_dir / "riverflow-client-ndi"
    client_yaml = target_dir / "riverflow-client-ndi.yaml"
    
    if server_src.exists():
        shutil.copy2(server_src, dist_serveur / "riverflow-server")
        (dist_serveur / "riverflow-server").chmod(0o755)
        print(f"  ✓ Copied server to {dist_serveur / 'riverflow-server'}")
    
    if client_src.exists():
        shutil.copy2(client_src, dist_client / "riverflow-client-ndi")
        (dist_client / "riverflow-client-ndi").chmod(0o755)
        print(f"  ✓ Copied client to {dist_client / 'riverflow-client-ndi'}")
    
    if client_yaml.exists():
        shutil.copy2(client_yaml, dist_client / "riverflow-client-ndi.yaml")
        print(f"  ✓ Copied YAML to {dist_client / 'riverflow-client-ndi.yaml'}")
    
    print("\n✅ Linux build completed!")
    return True

def main():
    """Main entry point."""
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    
    if target not in ("windows", "linux", "all"):
        print(f"Invalid target: {target}")
        print("Usage: uv run build.py [windows|linux|all]")
        sys.exit(1)
    
    success = True
    
    if target in ("windows", "all"):
        if not build_windows():
            success = False
    
    if target in ("linux", "all"):
        if not build_linux():
            success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All builds completed successfully!")
    else:
        print("⚠️  Some builds encountered issues. Check output above.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
