from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_NAME = "AI-Customer-Agent-Windows.exe"
LOCAL_RELEASE_DIR = ROOT / "release" / "desktop"


def default_build_dir() -> Path:
    configured = os.getenv("MERCHANT_DESKTOP_BUILD_DIR", "").strip()
    if configured:
        return Path(configured)
    if sys.platform.startswith("win"):
        return Path(r"C:\codex_ai_agent_release")
    return ROOT / "release" / "desktop"


def clean_dir(path: Path) -> None:
    resolved = path.resolve()
    if resolved == Path(resolved.anchor):
        raise RuntimeError(f"Refusing to clean drive root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def electron_builder_command(output_dir: Path) -> list[str]:
    executable = ROOT / "node_modules" / ".bin" / ("electron-builder.cmd" if sys.platform.startswith("win") else "electron-builder")
    if not executable.exists():
        raise RuntimeError("electron-builder is not installed. Run npm install first.")
    return [
        str(executable),
        "--win",
        "nsis",
        f"--config.directories.output={output_dir}",
        "--config.win.signAndEditExecutable=false",
    ]


def main() -> int:
    if not sys.platform.startswith("win"):
        raise RuntimeError("Windows installer must be built on Windows.")
    output_dir = default_build_dir()
    clean_dir(output_dir)
    env = os.environ.copy()
    env.setdefault("ELECTRON_MIRROR", "https://npmmirror.com/mirrors/electron/")
    env.setdefault("ELECTRON_BUILDER_BINARIES_MIRROR", "https://npmmirror.com/mirrors/electron-builder-binaries/")
    subprocess.run(electron_builder_command(output_dir), cwd=ROOT, env=env, check=True)
    built_installer = output_dir / INSTALLER_NAME
    if not built_installer.exists():
        raise RuntimeError(f"Installer was not produced: {built_installer}")
    LOCAL_RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    target = LOCAL_RELEASE_DIR / INSTALLER_NAME
    shutil.copy2(built_installer, target)
    print(f"built {target.relative_to(ROOT)} size={target.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
