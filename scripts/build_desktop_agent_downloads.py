from __future__ import annotations

import os
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "downloads"


WINDOWS_README = """# Windows AI Customer Service Agent

This package is for MVP customer testing.

## Requirements

- Windows 10/11
- Python 3.11+
- Tesseract OCR, only needed when OCR mode is used
- A valid merchant backend login token

## Start

1. Edit scripts/desktop_listener.config.example.json.
2. Put your backend token into auth_token, or set MERCHANT_DESKTOP_AUTH_TOKEN.
3. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\\run-windows.ps1
```

Default mode is auto_paste. Guarded auto-send requires mode=auto_send, send=true, and confirm_send=CONFIRM_DESKTOP_AUTO_SEND.
"""


WINDOWS_RUNNER = """$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
& ".\\.venv\\Scripts\\python.exe" -m pip install --upgrade pip
& ".\\.venv\\Scripts\\python.exe" -m pip install -r requirements.txt
& ".\\.venv\\Scripts\\python.exe" scripts\\desktop_agent_runner.py --config scripts\\desktop_listener.config.example.json
"""


def add_tree(zf: zipfile.ZipFile, source: Path, target_prefix: str) -> None:
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        if "__pycache__" in path.parts:
            continue
        zf.write(path, f"{target_prefix}/{path.relative_to(source).as_posix()}")


def add_common_files(zf: zipfile.ZipFile, package_root: str) -> None:
    add_tree(zf, ROOT / "desktop_agent", f"{package_root}/desktop_agent")
    for script in [
        ROOT / "scripts" / "desktop_agent_runner.py",
        ROOT / "scripts" / "desktop_auto_reply_listener.py",
        ROOT / "scripts" / "desktop_listener.config.example.json",
    ]:
        zf.write(script, f"{package_root}/scripts/{script.name}")
    zf.write(ROOT / "requirements.txt", f"{package_root}/requirements.txt")


def build_zip(filename: str, package_root: str, readme: str, runner_name: str, runner_body: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / filename
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        add_common_files(zf, package_root)
        zf.writestr(f"{package_root}/README.md", readme)
        zf.writestr(f"{package_root}/{runner_name}", runner_body)
    return target


def main() -> int:
    windows = build_zip("desktop-agent-windows.zip", "desktop-agent-windows", WINDOWS_README, "run-windows.ps1", WINDOWS_RUNNER)
    macos = OUT_DIR / "desktop-agent-macos.zip"
    if macos.exists():
        macos.unlink()
    print(f"built {windows.relative_to(ROOT)}")
    print("macOS package disabled: real macOS end-to-end validation has not passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
