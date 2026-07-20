from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


DEFAULT_API_BASE = os.getenv("MERCHANT_DESKTOP_API_BASE", "https://wjhai.cn/merchant-admin/api")
CONFIRM_AUTO_SEND = "\u6211\u786e\u8ba4\u53d1\u9001"

SourceName = Literal["auto", "uia", "ocr", "clipboard"]

ZH = {
    "wechat": "\u5fae\u4fe1",
    "wechat_work": "\u4f01\u4e1a\u5fae\u4fe1",
    "douyin": "\u6296\u97f3",
    "jul": "\u5de8\u91cf",
    "taobao": "\u6dd8\u5b9d",
    "qianniu": "\u5343\u725b",
    "wangwang": "\u65fa\u65fa",
    "pdd": "\u62fc\u591a\u591a",
    "xianyu": "\u95f2\u9c7c",
    "salted_fish": "\u54b8\u9c7c",
    "merchant_backend": "\u5546\u5bb6\u540e\u53f0",
}

PLATFORMS: dict[str, dict[str, Any]] = {
    "wechat": {
        "backend": "wechat",
        "label": ZH["wechat"],
        "allowlist": [ZH["wechat"], "WeChat"],
    },
    "wechat_work": {
        "backend": "wechat_work",
        "label": ZH["wechat_work"],
        "allowlist": [ZH["wechat_work"], "WeCom", "WXWork", "WeChat Work"],
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
    "xianyu": {
        "backend": "xianyu",
        "label": ZH["xianyu"],
        "allowlist": [ZH["xianyu"], ZH["salted_fish"], "Xianyu", "Idle Fish", "Goofish"],
    },
}

SHELL_TEXT_PATTERNS = [
    r"^CefView$",
    r"^FLUTTERVIEW$",
    r"^Chrome Legacy Window$",
    r".*Google Chrome.*",
    r".*Chrome.*",
    r".*可以访问此网站.*",
    r"^Acrobat 扩展程序.*",
    r"^Codex .*",
    r"^AI客服助手 .*",
    r"^JustTab.*",
    r"^PulseNew Tab.*",
    r"^扩展程序$",
    r"^关闭侧边栏$",
    r"^Chrome 实验室.*",
    r"^标签页搜索.*",
    r"^书签$",
    r"^所有书签$",
    r"^应用$",
    r"^受管理的书签$",
    r"^已保存的标签页分组$",
    r"^标签页分组$",
    r"^分隔符$",
    r"^地址和搜索栏$",
    r"^查看网站信息$",
    r"^清除输入的内容$",
    r"^返回$",
    r"^前进$",
    r"^重新加载$",
    r"^首页$",
    r"^在拆分视图中打开标签页$",
    r"^拆分视图下大小调整手柄.*",
    r"^侧边栏大小调整手柄.*",
    r"^信息栏容器$",
    r"^隐藏的工具栏按钮$",
    r"^有新版 Chrome 可用$",
    r"^查看您的任务$",
    r"^打开 Chrome 中的 Gemini$",
    r"^性能问题提醒$",
    r"^节能模式已开启$",
    r".*内存用量.*",
    r".*taobao\.com.*",
    r"^系统$",
    r"^还原$",
    r"^最大化$",
    r"^最小化$",
    r"^关闭$",
    r"^zip://",
    r"^app://",
    r"^http://",
    r"^https://",
]

CHAT_SIGNAL_PATTERN = (
    r"(客户|买家|卖家|亲您好|亲亲|价格|多少钱|多少|下单|拍下|付款|发货|退款|退货|换货|地址|"
    r"客服|你好|您好|在吗|还有|优惠|订单|物流|能不能|可以吗|有吗|到吗|多久|什么时候|"
    r"包邮|库存|现货|售后|投诉|发票|尺码|颜色|配送|送到|能送|能发|怎么拍|怎么下单)"
)


@dataclass
class ActiveTarget:
    hwnd: int
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
    target_title: str
    window_allowlist: list[str]
    poll_seconds: float
    min_send_gap_seconds: float
    once: bool
    paste: bool
    auto_send: bool
    dry_run: bool
    max_chars: int
    min_text_chars: int
    min_chat_chars: int
    allow_non_chat_text: bool
    allow_clipboard_fallback: bool
    ocr_lang: str
    debug_screenshot: str
    history_file: str
    history_limit: int


def endpoint_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/api"):
        return f"{base}/customer-service/chat-reply-agent"
    return f"{base}/api/customer-service/chat-reply-agent"


def foreground_window_handle() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def foreground_window_title() -> str:
    return window_title(foreground_window_handle())


def enum_visible_windows() -> list[tuple[int, str]]:
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    windows: list[tuple[int, str]] = []

    def callback(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            title = window_title(hwnd)
            if title:
                windows.append((int(hwnd), title))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return windows


def find_window_handle(title_pattern: str) -> int:
    if not title_pattern:
        return foreground_window_handle()
    for hwnd, title in enum_visible_windows():
        if re.search(title_pattern, title, re.IGNORECASE):
            return hwnd
    return 0


def active_window_handle(config: ListenerConfig) -> int:
    return find_window_handle(config.target_title) if config.target_title else foreground_window_handle()


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    if not hwnd:
        raise RuntimeError("No foreground window")
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("Cannot read foreground window rectangle")
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def normalize_chat_candidate(text: str) -> str:
    useful_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in SHELL_TEXT_PATTERNS):
            continue
        useful_lines.append(line)
    return "\n".join(useful_lines).strip()


def looks_like_chat_text(text: str, min_chat_chars: int = 12) -> bool:
    candidate = normalize_chat_candidate(text)
    if len(candidate) < min_chat_chars:
        return False
    return bool(re.search(CHAT_SIGNAL_PATTERN, candidate, re.IGNORECASE))


def detect_target(config: ListenerConfig) -> ActiveTarget | None:
    hwnd = active_window_handle(config)
    title = window_title(hwnd)
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
        return ActiveTarget(hwnd, title, config.platform, str(info["backend"]), str(info["label"]))

    platform_order = ["wechat_work", *[name for name in PLATFORMS if name != "wechat_work"]]
    for platform in platform_order:
        info = PLATFORMS[platform]
        if platform == "douyin_dm":
            continue
        if match_any(title, list(info["allowlist"])):
            return ActiveTarget(hwnd, title, platform, str(info["backend"]), str(info["label"]))
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


def read_uia_text(max_chars: int, hwnd: int | None = None) -> str:
    try:
        import uiautomation as auto  # type: ignore
    except ImportError as exc:
        raise RuntimeError("uiautomation is not installed. Run: python -m pip install uiautomation") from exc

    hwnd = hwnd or foreground_window_handle()
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


def capture_window(hwnd: int, debug_path: str = "") -> Any:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed; cannot capture foreground window") from exc

    left, top, right, bottom = window_rect(hwnd)
    image = ImageGrab.grab(bbox=(left, top, right, bottom))
    if debug_path:
        path = Path(debug_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    return image


def read_ocr_text(config: ListenerConfig) -> str:
    try:
        import pytesseract  # type: ignore
        from PIL import ImageOps
    except ImportError as exc:
        raise RuntimeError("pytesseract/Pillow is not installed; run pip install pytesseract pillow") from exc

    image = capture_window(active_window_handle(config), config.debug_screenshot)
    tesseract_cmd = find_tesseract_cmd()
    if not tesseract_cmd:
        raise RuntimeError("Tesseract OCR executable not found. Install Tesseract, or set TESSERACT_CMD.")
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    gray = ImageOps.grayscale(image)
    # A light contrast pass helps small chat text without making screenshots unreadable.
    text = pytesseract.image_to_string(gray, lang=config.ocr_lang)
    return text.strip()[-config.max_chars:]


def find_tesseract_cmd() -> str:
    candidates = [
        os.getenv("TESSERACT_CMD", ""),
        shutil.which("tesseract") or "",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


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


def load_history(path: str, limit: int) -> list[dict[str, Any]]:
    if not path or limit <= 0:
        return []
    file_path = Path(path)
    if not file_path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(limit * 3, limit):]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items[-limit:]


def append_history(path: str, item: dict[str, Any]) -> None:
    if not path:
        return
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def history_context(config: ListenerConfig, target: ActiveTarget) -> str:
    rows = [
        row
        for row in load_history(config.history_file, config.history_limit)
        if row.get("platform") in {target.platform, target.backend_channel, target.label}
    ]
    if not rows:
        return ""
    lines = ["Previous desktop assistant context:"]
    for row in rows:
        pending = " / ".join(str(item) for item in row.get("pending", []) if item)
        reply = str(row.get("reply") or "")
        if pending or reply:
            lines.append(f"- customer: {pending[:400]}\n  assistant: {reply[:500]}")
    return "\n".join(lines)


def build_merchant_profile(config: ListenerConfig, target: ActiveTarget) -> str:
    pieces = [f"{target.label} desktop customer-service assistant.", config.merchant_profile]
    knowledge = read_knowledge_file(config.knowledge_file)
    if knowledge:
        pieces.append("Imported local knowledge base:\n" + knowledge)
    return "\n\n".join(piece for piece in pieces if piece)


def build_chat_payload(config: ListenerConfig, target: ActiveTarget, chat_text: str) -> str:
    context = history_context(config, target)
    if not context:
        return chat_text
    return f"{context}\n\nCurrent visible chat:\n{chat_text}"


def read_chat_text(config: ListenerConfig, target: ActiveTarget | None = None) -> str:
    if config.source == "clipboard":
        return read_clipboard()
    hwnd = target.hwnd if target else active_window_handle(config)
    if config.source in {"auto", "uia"}:
        text = read_uia_text(config.max_chars, hwnd=hwnd)
        if len(text.strip()) >= config.min_text_chars and (config.allow_non_chat_text or looks_like_chat_text(text, config.min_chat_chars)):
            return text
        if config.source == "uia":
            if config.allow_clipboard_fallback:
                fallback = read_clipboard()
                if fallback:
                    print("UIA text was not chat-like; used clipboard fallback.")
                    return fallback
            if text:
                print("UIA text was not chat-like; returning it for diagnostics.")
                return text
            if config.allow_clipboard_fallback:
                fallback = read_clipboard()
                if fallback:
                    print("UIA text was too short; used clipboard fallback.")
                    return fallback
            return text
        if text:
            print("UIA text was not chat-like; trying OCR fallback.")
        else:
            print("UIA text was too short; trying OCR fallback.")
    if config.source in {"auto", "ocr"}:
        try:
            text = read_ocr_text(config)
            if len(text.strip()) >= config.min_text_chars and (config.allow_non_chat_text or looks_like_chat_text(text, config.min_chat_chars)):
                return text
            if config.source == "ocr":
                if text:
                    print("OCR text was not chat-like; returning it for diagnostics.")
                    return text
                if config.allow_clipboard_fallback:
                    fallback = read_clipboard()
                    if fallback:
                        print("OCR text was too short; used clipboard fallback.")
                        return fallback
                return text
            if text:
                print("OCR text was not chat-like.")
        except Exception as exc:
            if config.source == "ocr":
                raise
            print(f"OCR fallback unavailable: {exc}")
    if config.allow_clipboard_fallback:
        fallback = read_clipboard()
        if fallback:
            print("Used clipboard fallback.")
            return fallback
    return ""


def call_agent(config: ListenerConfig, target: ActiveTarget, chat_text: str) -> dict[str, Any]:
    payload = {
        "channel": target.backend_channel,
        "ocr_text": build_chat_payload(config, target, chat_text),
        "window_title": target.title,
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


def focus_window(hwnd: int) -> bool:
    if not hwnd:
        return True
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    return foreground_window_handle() == int(hwnd)


def paste_and_optionally_send(reply: str, send: bool, hwnd: int = 0) -> dict[str, Any]:
    write_clipboard(reply)
    if hwnd and not focus_window(hwnd):
        return {
            "pasted": False,
            "sent": False,
            "copied": True,
            "reason": "target_window_not_focused",
            "target_title": window_title(hwnd),
            "foreground_title": foreground_window_title(),
        }
    press_vk(0x11)
    press_vk(0x56)
    press_vk(0x56, up=True)
    press_vk(0x11, up=True)
    if send:
        time.sleep(0.25)
        press_vk(0x0D)
        press_vk(0x0D, up=True)
    return {
        "pasted": True,
        "sent": bool(send),
        "copied": True,
        "reason": "",
        "target_title": window_title(hwnd) if hwnd else "",
        "foreground_title": foreground_window_title(),
    }


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
        target_title=args.target_title,
        window_allowlist=args.window_allowlist or [],
        poll_seconds=args.poll_seconds,
        min_send_gap_seconds=args.min_send_gap_seconds,
        once=args.once,
        paste=args.paste,
        auto_send=args.send,
        dry_run=args.dry_run,
        max_chars=args.max_chars,
        min_text_chars=args.min_text_chars,
        min_chat_chars=args.min_chat_chars,
        allow_non_chat_text=args.allow_non_chat_text,
        allow_clipboard_fallback=args.allow_clipboard_fallback,
        ocr_lang=args.ocr_lang,
        debug_screenshot=args.debug_screenshot,
        history_file=args.history_file,
        history_limit=args.history_limit,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Desktop auto listener for WeChat, Douyin, Taobao/Qianniu, and PDD customer service windows.")
    parser.add_argument("--config", help="JSON config file.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--platform", choices=["auto", *sorted(PLATFORMS)], default="auto")
    parser.add_argument("--channel", choices=["auto", *sorted(PLATFORMS)], help="Backward-compatible alias for --platform.")
    parser.add_argument("--source", choices=["auto", "uia", "ocr", "clipboard"], default="auto")
    parser.add_argument("--merchant-profile", default="General merchant customer-service assistant.")
    parser.add_argument("--knowledge-file", default="", help="Local txt/md/json/csv knowledge file appended to the reply prompt.")
    parser.add_argument("--reply-goal", default="Reply naturally, answer the customer, and move toward lead capture, order, appointment, or human follow-up.")
    parser.add_argument("--target-title", default="", help="Regex title of a specific customer-service window to read, instead of the foreground window.")
    parser.add_argument("--window-allowlist", action="append", default=[], help="Extra window-title regex allowlist.")
    parser.add_argument("--poll-seconds", type=float, default=2)
    parser.add_argument("--min-send-gap-seconds", type=float, default=20)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--min-text-chars", type=int, default=30)
    parser.add_argument("--min-chat-chars", type=int, default=12, help="Minimum filtered chat-like characters required before calling AI.")
    parser.add_argument("--allow-non-chat-text", action="store_true", help="Allow replying even when the visible text looks like window chrome instead of chat.")
    parser.add_argument("--allow-clipboard-fallback", action="store_true", help="Allow auto/uia/ocr modes to use clipboard when window reading fails.")
    parser.add_argument("--ocr-lang", default=os.getenv("DESKTOP_OCR_LANG", "chi_sim+eng"))
    parser.add_argument("--debug-screenshot", default="", help="Optional path to save the latest foreground-window screenshot for OCR debugging.")
    parser.add_argument("--history-file", default="data/desktop-listener/history.jsonl")
    parser.add_argument("--history-limit", type=int, default=8)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--paste", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirm-send", default="", help=f"Required phrase for auto-send: {CONFIRM_AUTO_SEND}")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_parser().parse_args()
    if args.send and (not args.paste or args.confirm_send != CONFIRM_AUTO_SEND):
        print(f"Auto-send blocked. Pass --paste --send --confirm-send {CONFIRM_AUTO_SEND!r}.", file=sys.stderr)
        return 2

    config = load_config(args)
    print(f"Desktop listener started: platform={config.platform}, source={config.source}, paste={config.paste}, send={config.auto_send}")
    print("Open or lock a supported customer-service chat window. If the target cannot be focused, the reply is copied only. Press Ctrl+C to stop.")

    last_fingerprint = ""
    last_send_at = 0.0

    while True:
        if not config.once and last_send_at and time.time() - last_send_at < config.min_send_gap_seconds:
            time.sleep(config.poll_seconds)
            continue

        target = detect_target(config)
        if not target:
            if config.once:
                print("Current window is not a supported customer-service window.")
                return 3
            time.sleep(config.poll_seconds)
            continue

        try:
            chat_text = read_chat_text(config, target)
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

        if not config.allow_non_chat_text and not looks_like_chat_text(chat_text, config.min_chat_chars):
            print(
                json.dumps(
                    {
                        "window": target.title,
                        "platform": target.label,
                        "should_reply": False,
                        "reason": "not_chat_like",
                        "candidate": normalize_chat_candidate(chat_text)[:500],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if config.once:
                return 5
            time.sleep(config.poll_seconds)
            continue

        data = call_agent(config, target, chat_text)
        reply = str(data.get("recommended_reply") or "")
        pending = data.get("pending_customer_messages") or []
        should_reply = bool(data.get("should_reply"))
        print(json.dumps({"window": target.title, "platform": target.label, "should_reply": should_reply, "pending": pending, "reply": reply}, ensure_ascii=False, indent=2))

        if should_reply and reply:
            append_history(
                config.history_file,
                {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "window": target.title,
                    "platform": target.platform,
                    "backend_channel": target.backend_channel,
                    "pending": pending,
                    "reply": reply,
                    "source": config.source,
                    "sent": bool(config.auto_send and config.paste and not config.dry_run),
                },
            )
            now = time.time()
            if config.dry_run:
                print("dry-run: not copied, pasted, or sent.")
            elif now - last_send_at < config.min_send_gap_seconds:
                write_clipboard(reply)
                print("Rate limited: reply copied only.")
            elif config.paste:
                paste_result = paste_and_optionally_send(reply, send=config.auto_send, hwnd=target.hwnd)
                last_send_at = now
                if paste_result.get("pasted"):
                    print("Pasted." + (" Sent." if config.auto_send else " Not sent; confirm manually."))
                else:
                    print(json.dumps({"paste_blocked": paste_result}, ensure_ascii=False, indent=2))
            else:
                write_clipboard(reply)
                print("Copied to clipboard.")

        if config.once:
            return 0
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
