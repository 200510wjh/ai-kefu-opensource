from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "public" / "downloads"
RELEASE_DIR = ROOT / "release" / "desktop"
WINDOWS_INSTALLER_NAME = "AI-Customer-Agent-Windows.exe"
WINDOWS_DEV_ZIP_NAME = "desktop-agent-windows-dev.zip"
MANIFEST_NAME = "desktop-agent-downloads.json"


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

Douyin DM safety:

- Set platform=douyin_dm.
- Set authorized_account to the merchant-owned or explicitly authorized Douyin account label.
- Set contact_allowlist to the first-round test contacts only.
- Unsupported media, unknown message direction, non-whitelisted contacts, and unmatched knowledge will be handed off instead of auto-sent.
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version() -> str:
    try:
        data = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    except Exception:
        return ""


def remove_stale_customer_downloads() -> None:
    stale_names = [
        "desktop-agent-windows.zip",
        "desktop-agent-macos.zip",
        "desktop-agent-macos.dmg",
        "AI-Customer-Agent-Mac.dmg",
    ]
    for name in stale_names:
        target = OUT_DIR / name
        if target.exists():
            target.unlink()


def copy_windows_installer() -> dict[str, object]:
    source = RELEASE_DIR / WINDOWS_INSTALLER_NAME
    target = OUT_DIR / WINDOWS_INSTALLER_NAME
    if not source.exists():
        if target.exists():
            target.unlink()
        return {
            "available": False,
            "url": "",
            "package_type": "missing",
            "reason": "Run npm run desktop:win on Windows and rerun npm run desktop:downloads.",
        }
    shutil.copy2(source, target)
    return {
        "available": True,
        "url": f"/downloads/{WINDOWS_INSTALLER_NAME}",
        "filename": WINDOWS_INSTALLER_NAME,
        "package_type": "nsis_installer_exe",
        "size": target.stat().st_size,
        "sha256": sha256_file(target),
    }


def file_entry(path: Path, package_type: str) -> dict[str, object]:
    return {
        "available": path.exists(),
        "url": f"/downloads/{path.name}" if path.exists() else "",
        "filename": path.name,
        "package_type": package_type if path.exists() else "missing",
        "size": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else "",
    }


def write_manifest(windows_installer: dict[str, object], dev_zip: Path) -> Path:
    manifest = {
        "version": package_version(),
        "build_time": datetime.now(timezone.utc).isoformat(),
        "windows": windows_installer,
        "windows_dev_zip": file_entry(dev_zip, "developer_source_zip"),
        "macos": {
            "available": False,
            "url": "",
            "package_type": "disabled",
            "reason": "macOS client download is hidden until a real macOS DMG build and end-to-end validation pass.",
        },
    }
    target = OUT_DIR / MANIFEST_NAME
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    remove_stale_customer_downloads()
    dev_zip = build_zip(WINDOWS_DEV_ZIP_NAME, "desktop-agent-windows-dev", WINDOWS_README, "run-windows.ps1", WINDOWS_RUNNER)
    windows_installer = copy_windows_installer()
    manifest = write_manifest(windows_installer, dev_zip)
    print(f"built developer validation package {dev_zip.relative_to(ROOT)}")
    if windows_installer["available"]:
        print(f"published Windows installer public/downloads/{WINDOWS_INSTALLER_NAME}")
    else:
        print(f"Windows installer not published: {windows_installer['reason']}")
    print(f"wrote {manifest.relative_to(ROOT)}")
    print("macOS package disabled: real macOS end-to-end validation has not passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
