from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


DEFAULT_API_BASE = os.getenv("MERCHANT_DESKTOP_API_BASE", "https://wjhai.cn/merchant-admin/api")
CONFIRM_AUTO_SEND = "\u6211\u786e\u8ba4\u53d1\u9001"

SourceName = Literal["uia", "clipboard"]

ZH = {
    "wechat": "\u5fae\u4fe1",
    "wechat_work": "\u4f01\u4e1a\u5fae\u4fe1",
    "douyin": "\u6296\u97f3",
    "jul": "\u5de8\u91cf",
    "taobao": "\u6dd8\u5b9d",
    "qianniu": "\u5343\u725b",
    "wangwang": "\u65fa\u65fa",
    "pdd": "\u62fc\u591a\u591a",
    "merchant_backend": "\u5546\u5bb6\u540e\u53f0",
}

PLATFORMS: dict[str, dict[str, Any]] = {
    "wechat": {
        "backend": "wechat",
        "label": ZH["wechat"],
        "allowlist": [ZH["wechat"], "WeChat", ZH["wechat_work"]],
    },
    "douyin": {
        "backend": "douyin_dm",
        "label": f"{ZH['douyin']}\u79c1\u4fe1",
        "allowlist": [ZH["douyin"], ZH["jul"], "Douyin"],
    },
    "douyin_dm": {
        "backend": "douyin_dm",
        "label": f"{ZH['douyin']}\u79c1\u4fe1",
        "allowlist": [ZH["douyin"], ZH["jul"], "Douyin"],
    },
    "taobao": {
        "backend": "taobao",
        "label": f"{ZH['taobao']}/{ZH['qianniu']}",
        "allowlist": [ZH["qianniu"], ZH["taobao"], ZH["wangwang"], "Qianniu"],
    },
    "pdd": {
        "backend": "pdd",
        "label": ZH["pdd"],
        "allowlist": [ZH["pdd"], "PDD", ZH["merchant_backend"]],
    },
}


@dataclass
class ActiveTarget:
    title: str
    platform: str
    backend_channel: str
    label: str


@dataclass
class ListenerConfig:
    api_base: str
    platform: str
    source: SourceName
    merchant_profile: str
    knowledge_file: str
    reply_goal: str
    window_allowlist: list[str]
    poll_seconds: float
    min_send_gap_seconds: float
    once: bool
    paste: bool
    auto_send: bool
    dry_run: bool
    max_chars: int
    min_text_chars: int


def endpoint_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/api"):
        return f"{base}/customer-service/chat-reply-agent"
    return f"{base}/api/customer-service/chat-reply-agent"


def foreground_window_handle() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def foreground_window_title() -> str:
    hwnd = foreground_window_handle()
    if not hwnd:
        return ""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def detect_target(config: ListenerConfig) -> ActiveTarget | None:
    title = foreground_window_title()
    if not title:
        return None
    if config.window_allowlist and not match_any(title, config.window_allowlist):
        return None

    if config.platform != "auto":
        info = PLATFORMS[config.platform]
        custom_match = bool(config.window_allowlist) and match_any(title, config.window_allowlist)
        platform_match = match_any(title, list(info["allowlist"]))
        if not (custom_match or platform_match):
            return None
        return ActiveTarget(title, config.platform, str(info["backend"]), str(info["label"]))

    for platform, info in PLATFORMS.items():
        if platform == "douyin_dm":
            continue
        if match_any(title, list(info["allowlist"])):
            return ActiveTarget(title, platform, str(info["backend"]), str(info["label"]))
    return None


def read_windows_clipboard() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    cf_unicode_text = 13
    if not user32.OpenClipboard(None):
        raise RuntimeError("Clipboard is busy")
    try:
        handle = user32.GetClipboardData(cf_unicode_text)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def write_windows_clipboard(text: str) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    data = ctypes.create_unicode_buffer(text)
    handle = kernel32.GlobalAlloc(0x0002, ctypes.sizeof(data))
    if not handle:
        raise RuntimeError("Cannot allocate clipboard memory")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        raise RuntimeError("Cannot lock clipboard memory")
    ctypes.memmove(pointer, data, ctypes.sizeof(data))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        raise RuntimeError("Clipboard is busy")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(13, handle):
            raise RuntimeError("Cannot write clipboard")
    finally:
        user32.CloseClipboard()


def read_clipboard() -> str:
    try:
        return read_windows_clipboard().strip()
    except Exception:
        pass
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Cannot read clipboard")
    return completed.stdout.strip()


def write_clipboard(text: str) -> None:
    try:
        write_windows_clipboard(text)
        return
    except Exception:
        pass
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Set-Clipboard"],
        input=text,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Cannot write clipboard")


def read_uia_text(max_chars: int) -> str:
    try:
        import uiautomation as auto  # type: ignore
    except ImportError as exc:
        raise RuntimeError("uiautomation is not installed. Run: python -m pip install uiautomation") from exc

    hwnd = foreground_window_handle()
    if not hwnd:
        return ""
    try:
        control = auto.ControlFromHandle(hwnd)
    except Exception:
        control = auto.GetForegroundControl()

    texts: list[str] = []

    def push(value: str) -> None:
        text = " ".join(value.replace("\r", "\n").split())
        if len(text) < 2 or text in texts:
            return
        texts.append(text)

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 8 or len("\n".join(texts)) > max_chars:
            return
        try:
            push(str(getattr(node, "Name", "") or ""))
            try:
                push(str(node.GetValuePattern().Value or ""))
            except Exception:
                pass
            for child in node.GetChildren() or []:
                walk(child, depth + 1)
        except Exception:
            return

    walk(control)
    return "\n".join(texts)[-max_chars:]


def read_knowledge_file(path: str, max_chars: int = 6000) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.exists():
        raise RuntimeError(f"Knowledge file not found: {file_path}")
    raw = file_path.read_bytes()
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)[-max_chars:]
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")[-max_chars:]


def build_merchant_profile(config: ListenerConfig, target: ActiveTarget) -> str:
    pieces = [f"{target.label} desktop customer-service assistant.", config.merchant_profile]
    knowledge = read_knowledge_file(config.knowledge_file)
    if knowledge:
        pieces.append("Imported local knowledge base:\n" + knowledge)
    return "\n\n".join(piece for piece in pieces if piece)


def read_chat_text(config: ListenerConfig) -> str:
    if config.source == "clipboard":
        return read_clipboard()
    text = read_uia_text(config.max_chars)
    if len(text.strip()) >= config.min_text_chars:
        return text
    fallback = read_clipboard()
    if fallback:
        print("UIA text was too short; used clipboard fallback.")
        return fallback
    return text


def call_agent(config: ListenerConfig, target: ActiveTarget, chat_text: str) -> dict[str, Any]:
    payload = {
        "channel": target.backend_channel,
        "ocr_text": chat_text,
        "merchant_profile": build_merchant_profile(config, target),
        "reply_goal": config.reply_goal,
        "auto_send": False,
    }
    request = urllib.request.Request(
        endpoint_url(config.api_base),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect API: {exc}") from exc


def press_vk(vk: int, up: bool = False) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0x0002 if up else 0, 0)


def paste_and_optionally_send(reply: str, send: bool) -> None:
    write_clipboard(reply)
    press_vk(0x11)
    press_vk(0x56)
    press_vk(0x56, up=True)
    press_vk(0x11, up=True)
    if send:
        time.sleep(0.25)
        press_vk(0x0D)
        press_vk(0x0D, up=True)


def load_config(args: argparse.Namespace) -> ListenerConfig:
    if args.channel:
        args.platform = args.channel
    if args.config:
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        for key, value in data.items():
            name = key.replace("-", "_")
            if hasattr(args, name):
                setattr(args, name, value)
    return ListenerConfig(
        api_base=args.api_base,
        platform=args.platform,
        source=args.source,
        merchant_profile=args.merchant_profile,
        knowledge_file=args.knowledge_file,
        reply_goal=args.reply_goal,
        window_allowlist=args.window_allowlist or [],
        poll_seconds=args.poll_seconds,
        min_send_gap_seconds=args.min_send_gap_seconds,
        once=args.once,
        paste=args.paste,
        auto_send=args.send,
        dry_run=args.dry_run,
        max_chars=args.max_chars,
        min_text_chars=args.min_text_chars,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Desktop auto listener for WeChat, Douyin, Taobao/Qianniu, and PDD customer service windows.")
    parser.add_argument("--config", help="JSON config file.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--platform", choices=["auto", *sorted(PLATFORMS)], default="auto")
    parser.add_argument("--channel", choices=["auto", *sorted(PLATFORMS)], help="Backward-compatible alias for --platform.")
    parser.add_argument("--source", choices=["uia", "clipboard"], default="uia")
    parser.add_argument("--merchant-profile", default="General merchant customer-service assistant.")
    parser.add_argument("--knowledge-file", default="", help="Local txt/md/json/csv knowledge file appended to the reply prompt.")
    parser.add_argument("--reply-goal", default="Reply naturally, answer the customer, and move toward lead capture, order, appointment, or human follow-up.")
    parser.add_argument("--window-allowlist", action="append", default=[], help="Extra window-title regex allowlist.")
    parser.add_argument("--poll-seconds", type=float, default=2)
    parser.add_argument("--min-send-gap-seconds", type=float, default=20)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--min-text-chars", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--paste", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirm-send", default="", help=f"Required phrase for auto-send: {CONFIRM_AUTO_SEND}")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.send and (not args.paste or args.confirm_send != CONFIRM_AUTO_SEND):
        print(f"Auto-send blocked. Pass --paste --send --confirm-send {CONFIRM_AUTO_SEND!r}.", file=sys.stderr)
        return 2

    config = load_config(args)
    print(f"Desktop listener started: platform={config.platform}, source={config.source}, paste={config.paste}, send={config.auto_send}")
    print("Open a supported customer-service chat window and keep it focused. Press Ctrl+C to stop.")

    last_fingerprint = ""
    last_send_at = 0.0

    while True:
        target = detect_target(config)
        if not target:
            if config.once:
                print("Current window is not a supported customer-service window.")
                return 3
            time.sleep(config.poll_seconds)
            continue

        try:
            chat_text = read_chat_text(config)
        except Exception as exc:
            print(f"Read chat failed: {exc}", file=sys.stderr)
            if config.once:
                return 4
            time.sleep(config.poll_seconds)
            continue

        fingerprint = f"{target.platform}:{target.title}\n{chat_text[-2500:]}"
        if not chat_text or fingerprint == last_fingerprint:
            if config.once:
                return 0
            time.sleep(config.poll_seconds)
            continue
        last_fingerprint = fingerprint

        data = call_agent(config, target, chat_text)
        reply = str(data.get("recommended_reply") or "")
        pending = data.get("pending_customer_messages") or []
        should_reply = bool(data.get("should_reply"))
        print(json.dumps({"window": target.title, "platform": target.label, "should_reply": should_reply, "pending": pending, "reply": reply}, ensure_ascii=False, indent=2))

        if should_reply and reply:
            now = time.time()
            if config.dry_run:
                print("dry-run: not copied, pasted, or sent.")
            elif now - last_send_at < config.min_send_gap_seconds:
                write_clipboard(reply)
                print("Rate limited: reply copied only.")
            elif config.paste:
                paste_and_optionally_send(reply, send=config.auto_send)
                last_send_at = now
                print("Pasted." + (" Sent." if config.auto_send else " Not sent; confirm manually."))
            else:
                write_clipboard(reply)
                print("Copied to clipboard.")

        if config.once:
            return 0
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
