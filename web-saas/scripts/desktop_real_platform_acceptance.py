from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from desktop_auto_reply_listener import PLATFORMS, enum_visible_windows, looks_like_chat_text, normalize_chat_candidate


PYTHON = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
DEFAULT_PLATFORMS = ["wechat", "douyin", "taobao", "pdd", "xianyu"]


def platform_patterns(platform: str) -> list[str]:
    info = PLATFORMS["douyin" if platform == "douyin_dm" else platform]
    return [str(pattern) for pattern in info["allowlist"]]


def find_platform_window(platform: str, windows: list[tuple[int, str]]) -> tuple[int, str] | None:
    patterns = platform_patterns(platform)
    for hwnd, title in windows:
        if any(re.search(pattern, title, re.IGNORECASE) for pattern in patterns):
            return hwnd, title
    return None


def run_diagnostics(root: Path, python: Path, platform: str, title: str, timeout: int, min_read_chars: int) -> dict[str, Any]:
    escaped_title = re.escape(title)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm:
        cmd = [
            npm,
            "run",
            "desktop:diagnose",
            "--",
            "--platform",
            platform,
            "--target-title",
            escaped_title,
            "--window-allowlist",
            escaped_title,
            "--source",
            "auto",
            "--max-chars",
            "1200",
        ]
    else:
        cmd = [
            str(python),
            "scripts/desktop_diagnostics.py",
            "--platform",
            platform,
            "--target-title",
            escaped_title,
            "--window-allowlist",
            escaped_title,
            "--source",
            "auto",
            "--max-chars",
            "1200",
        ]
    completed = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    parsed: dict[str, Any] | None = None
    stdout = completed.stdout.strip()
    if stdout:
        start = stdout.find("{")
        if start >= 0:
            try:
                parsed = json.loads(stdout[start:])
            except Exception:
                parsed = None
    checks = ((parsed or {}).get("checks") or {})
    uia = checks.get("uia", {}) if isinstance(checks, dict) else {}
    ocr = checks.get("ocr", {}) if isinstance(checks, dict) else {}
    auto = checks.get("auto", {}) if isinstance(checks, dict) else {}
    clipboard = checks.get("clipboard", {}) if isinstance(checks, dict) else {}
    uia_sample = str(uia.get("sample") or "") if isinstance(uia, dict) else ""
    ocr_sample = str(ocr.get("sample") or "") if isinstance(ocr, dict) else ""
    clipboard_sample = str(clipboard.get("sample") or "") if isinstance(clipboard, dict) else ""
    auto_ok = bool(isinstance(auto, dict) and auto.get("ok"))
    uia_chat_ok = bool(isinstance(uia, dict) and uia.get("ok") and looks_like_chat_text(uia_sample, min_read_chars))
    ocr_chat_ok = bool(isinstance(ocr, dict) and ocr.get("ok") and looks_like_chat_text(ocr_sample, min_read_chars))
    clipboard_chat_ok = bool(isinstance(clipboard, dict) and clipboard.get("ok") and looks_like_chat_text(clipboard_sample, 12))
    real_read_ok = bool(uia_chat_ok or ocr_chat_ok)
    read_mode = "uia" if uia_chat_ok else "ocr" if ocr_chat_ok else "clipboard_fallback" if clipboard_chat_ok else "none"
    return {
        "ok": completed.returncode == 0 and real_read_ok,
        "returncode": completed.returncode,
        "title": title,
        "auto_ok": auto_ok,
        "real_read_ok": real_read_ok,
        "read_mode": read_mode,
        "uia_chat_candidate": normalize_chat_candidate(uia_sample)[:500],
        "ocr_chat_candidate": normalize_chat_candidate(ocr_sample)[:500],
        "clipboard_chat_candidate": normalize_chat_candidate(clipboard_sample)[:500],
        "min_read_chars": min_read_chars,
        "diagnostics": parsed,
        "stdout_tail": completed.stdout[-1500:],
        "stderr_tail": completed.stderr[-1500:],
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Verify real desktop customer-service windows are open and readable.")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS), help="Comma-separated platforms: wechat,douyin,taobao,pdd,xianyu")
    parser.add_argument("--soft", action="store_true", help="Report missing platforms without failing the command.")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--min-read-chars", type=int, default=80, help="Minimum UIA/OCR characters required to count as real window reading.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    python = PYTHON if PYTHON.exists() else Path(sys.executable)
    requested = [item.strip() for item in args.platforms.split(",") if item.strip()]
    windows = enum_visible_windows()
    results: dict[str, Any] = {}

    for platform in requested:
        match = find_platform_window(platform, windows)
        if not match:
            results[platform] = {
                "ok": False,
                "status": "missing_window",
                "message": f"没有找到 {platform} 的可见客服窗口，请先打开对应平台聊天窗口再验收。",
                "expected_title_patterns": platform_patterns(platform),
            }
            continue
        _, title = match
        results[platform] = {
            "ok": False,
            "status": "diagnosing",
            "window_title": title,
            **run_diagnostics(root, python, platform, title, args.timeout, args.min_read_chars),
        }
        if results[platform]["ok"]:
            results[platform]["status"] = "ok"
        elif results[platform].get("read_mode") == "clipboard_fallback":
            results[platform]["status"] = "clipboard_fallback_only"
            results[platform]["message"] = "找到了窗口，但窗口文字/OCR 没读到足够聊天内容，或只读到了窗口壳文字；这不算真正自动读取。"
        else:
            results[platform]["status"] = "read_failed"

    ok = all(item.get("ok") for item in results.values())
    output = {
        "ok": ok or args.soft,
        "strict_ok": ok,
        "soft": args.soft,
        "visible_platform_windows": [
            title
            for _, title in windows
            if any(word in title.lower() for word in ["微信", "wechat", "抖音", "douyin", "千牛", "淘宝", "拼多多", "pdd", "闲鱼", "咸鱼", "xianyu", "goofish"])
        ],
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
