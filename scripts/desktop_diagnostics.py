from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import win32gui

from desktop_auto_reply_listener import (
    ListenerConfig,
    active_window_handle,
    capture_window,
    detect_target,
    find_tesseract_cmd,
    foreground_window_title,
    read_chat_text,
    read_clipboard,
    read_ocr_text,
    read_uia_text,
    looks_like_chat_text,
    normalize_chat_candidate,
    window_title,
)


def visible_windows(limit: int = 80) -> list[str]:
    titles: list[str] = []

    def callback(hwnd: int, _: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                titles.append(title)

    win32gui.EnumWindows(callback, None)
    return titles[:limit]


def tesseract_languages() -> list[str]:
    cmd = find_tesseract_cmd()
    if not cmd:
        return []
    completed = subprocess.run(
        [cmd, "--list-langs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    return [line.strip() for line in completed.stdout.splitlines()[1:] if line.strip()]


def build_config(args: argparse.Namespace) -> ListenerConfig:
    return ListenerConfig(
        api_base=args.api_base,
        platform=args.platform,
        source=args.source,
        merchant_profile="diagnostics",
        knowledge_file=args.knowledge_file,
        reply_goal="diagnostics",
        target_title=args.target_title,
        window_allowlist=args.window_allowlist or [],
        poll_seconds=1,
        min_send_gap_seconds=20,
        once=True,
        paste=False,
        auto_send=False,
        dry_run=True,
        max_chars=args.max_chars,
        min_text_chars=args.min_text_chars,
        min_chat_chars=args.min_chat_chars,
        allow_non_chat_text=False,
        allow_clipboard_fallback=args.allow_clipboard_fallback,
        ocr_lang=args.ocr_lang,
        debug_screenshot=args.debug_screenshot,
        history_file="data/desktop-listener/history.jsonl",
        history_limit=8,
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Diagnose desktop customer-service window reading.")
    parser.add_argument("--api-base", default="https://wjhai.cn/merchant-admin/api")
    parser.add_argument("--platform", choices=["auto", "wechat", "douyin", "douyin_dm", "taobao", "pdd", "xianyu"], default="auto")
    parser.add_argument("--source", choices=["auto", "uia", "ocr", "clipboard"], default="auto")
    parser.add_argument("--target-title", default="")
    parser.add_argument("--window-allowlist", action="append", default=[])
    parser.add_argument("--knowledge-file", default="docs/examples/merchant_knowledge.example.txt")
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--min-text-chars", type=int, default=30)
    parser.add_argument("--min-chat-chars", type=int, default=12)
    parser.add_argument("--allow-clipboard-fallback", action="store_true")
    parser.add_argument("--ocr-lang", default="chi_sim+eng")
    parser.add_argument("--debug-screenshot", default="data/desktop-listener/diagnostics-window.png")
    args = parser.parse_args()

    config = build_config(args)
    target = detect_target(config)
    active_hwnd = active_window_handle(config)
    result: dict[str, object] = {
        "foreground_title": foreground_window_title(),
        "active_title": window_title(active_hwnd) if active_hwnd else "",
        "target": target.__dict__ if target else None,
        "tesseract_cmd": find_tesseract_cmd(),
        "tesseract_languages": tesseract_languages(),
        "debug_screenshot": args.debug_screenshot,
        "visible_platform_windows": [
            title
            for title in visible_windows()
            if any(word in title.lower() for word in ["微信", "wechat", "抖音", "douyin", "千牛", "淘宝", "拼多多", "pdd", "闲鱼", "咸鱼", "xianyu", "goofish"])
        ],
        "checks": {},
    }
    checks: dict[str, object] = {}
    result["checks"] = checks

    try:
        if not active_hwnd:
            raise RuntimeError("no_active_window")
        uia = read_uia_text(args.max_chars, hwnd=active_hwnd)
        checks["uia"] = {
            "ok": bool(uia.strip()),
            "chat_like": looks_like_chat_text(uia, args.min_chat_chars),
            "candidate": normalize_chat_candidate(uia)[:500],
            "length": len(uia),
            "sample": uia[:500],
        }
    except Exception as exc:
        checks["uia"] = {"ok": False, "error": str(exc)}

    try:
        if not active_hwnd:
            raise RuntimeError("no_active_window")
        capture_window(active_hwnd, args.debug_screenshot)
        checks["screenshot"] = {"ok": Path(args.debug_screenshot).exists(), "path": args.debug_screenshot}
    except Exception as exc:
        checks["screenshot"] = {"ok": False, "error": str(exc)}

    try:
        if not active_hwnd:
            raise RuntimeError("no_active_window")
        ocr = read_ocr_text(config)
        checks["ocr"] = {
            "ok": bool(ocr.strip()),
            "chat_like": looks_like_chat_text(ocr, args.min_chat_chars),
            "candidate": normalize_chat_candidate(ocr)[:500],
            "length": len(ocr),
            "sample": ocr[:500],
        }
    except Exception as exc:
        checks["ocr"] = {"ok": False, "error": str(exc)}

    try:
        clip = read_clipboard()
        checks["clipboard"] = {
            "ok": bool(clip.strip()),
            "chat_like": looks_like_chat_text(clip, args.min_chat_chars),
            "candidate": normalize_chat_candidate(clip)[:500],
            "length": len(clip),
            "sample": clip[:500],
        }
    except Exception as exc:
        checks["clipboard"] = {"ok": False, "error": str(exc)}

    try:
        if not target:
            raise RuntimeError("no_target_window")
        auto = read_chat_text(config, target)
        checks["auto"] = {
            "ok": bool(auto.strip()),
            "chat_like": looks_like_chat_text(auto, args.min_chat_chars),
            "candidate": normalize_chat_candidate(auto)[:500],
            "length": len(auto),
            "sample": auto[:500],
        }
    except Exception as exc:
        checks["auto"] = {"ok": False, "error": str(exc)}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if target and (checks.get("auto") or {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
