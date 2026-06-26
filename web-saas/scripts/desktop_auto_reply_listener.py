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
CONFIRM_AUTO_SEND = "我确认发送"

PLATFORMS: dict[str, dict[str, Any]] = {
    "wechat": {
        "backend": "wechat",
        "label": "微信",
        "allowlist": [r"微信", r"WeChat", r"企业微信"],
    },
    "douyin": {
        "backend": "douyin_dm",
        "label": "抖音私信",
        "allowlist": [r"抖音", r"巨量", r"Douyin"],
    },
    "douyin_dm": {
        "backend": "douyin_dm",
        "label": "抖音私信",
        "allowlist": [r"抖音", r"巨量", r"Douyin"],
    },
    "taobao": {
        "backend": "taobao",
        "label": "淘宝/千牛",
        "allowlist": [r"千牛", r"淘宝", r"旺旺", r"Qianniu"],
    },
    "pdd": {
        "backend": "pdd",
        "label": "拼多多",
        "allowlist": [r"拼多多", r"PDD", r"商家后台"],
    },
}


@dataclass
class ListenerConfig:
    api_base: str
    platform: str
    backend_channel: str
    label: str
    source: Literal["clipboard", "uia"]
    merchant_profile: str
    reply_goal: str
    window_allowlist: list[str]
    poll_seconds: float
    min_send_gap_seconds: float
    once: bool
    paste: bool
    auto_send: bool
    dry_run: bool


def endpoint_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/api"):
        return f"{base}/customer-service/chat-reply-agent"
    return f"{base}/api/customer-service/chat-reply-agent"


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
        raise RuntimeError(completed.stderr.strip() or "无法读取剪贴板")
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
        raise RuntimeError(completed.stderr.strip() or "无法写入剪贴板")


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
        raise RuntimeError("剪贴板正被其他程序占用")
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

    cf_unicode_text = 13
    gmem_moveable = 0x0002
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    handle = kernel32.GlobalAlloc(gmem_moveable, size)
    if not handle:
        raise RuntimeError("无法分配剪贴板内存")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        raise RuntimeError("无法锁定剪贴板内存")
    ctypes.memmove(pointer, data, size)
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        raise RuntimeError("剪贴板正被其他程序占用")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(cf_unicode_text, handle):
            raise RuntimeError("写入剪贴板失败")
    finally:
        user32.CloseClipboard()


def foreground_window_title() -> str:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def window_allowed(title: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in allowlist)


def read_uia_text() -> str:
    try:
        import uiautomation as auto  # type: ignore
    except ImportError as exc:
        raise RuntimeError("未安装 uiautomation。请先运行 pip install uiautomation，或改用 --source clipboard。") from exc

    control = auto.GetForegroundControl()
    texts: list[str] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 6 or len(texts) >= 180:
            return
        try:
            name = (node.Name or "").strip()
            value = ""
            try:
                value = (node.GetValuePattern().Value or "").strip()
            except Exception:
                value = ""
            text = value or name
            if text and len(text) > 1:
                texts.append(text)
            for child in node.GetChildren() or []:
                walk(child, depth + 1)
        except Exception:
            return

    walk(control)
    return "\n".join(dict.fromkeys(texts))


def call_agent(config: ListenerConfig, chat_text: str) -> dict[str, Any]:
    payload = {
        "channel": config.backend_channel,
        "ocr_text": chat_text,
        "merchant_profile": f"{config.label}桌面客服助手。{config.merchant_profile}",
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
        raise RuntimeError(f"接口返回 {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连接接口失败：{exc}") from exc


def press_vk(vk: int, up: bool = False) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0x0002 if up else 0, 0)


def paste_and_optionally_send(reply: str, send: bool) -> None:
    write_clipboard(reply)
    vk_control = 0x11
    vk_v = 0x56
    vk_enter = 0x0D
    press_vk(vk_control)
    press_vk(vk_v)
    press_vk(vk_v, up=True)
    press_vk(vk_control, up=True)
    if send:
        time.sleep(0.25)
        press_vk(vk_enter)
        press_vk(vk_enter, up=True)


def platform_from_args(args: argparse.Namespace) -> str:
    platform = args.platform or args.channel or "wechat"
    if platform not in PLATFORMS:
        raise ValueError(f"不支持的平台：{platform}")
    return platform


def load_config(args: argparse.Namespace) -> ListenerConfig:
    platform = platform_from_args(args)
    platform_info = PLATFORMS[platform]
    allowlist = list(platform_info["allowlist"])
    if args.window_allowlist:
        allowlist = args.window_allowlist
    if args.config:
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        allowlist = data.get("window_allowlist", allowlist)
    return ListenerConfig(
        api_base=args.api_base,
        platform=platform,
        backend_channel=str(platform_info["backend"]),
        label=str(platform_info["label"]),
        source=args.source,
        merchant_profile=args.merchant_profile,
        reply_goal=args.reply_goal,
        window_allowlist=allowlist,
        poll_seconds=args.poll_seconds,
        min_send_gap_seconds=args.min_send_gap_seconds,
        once=args.once,
        paste=args.paste,
        auto_send=args.send,
        dry_run=args.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="桌面客服监听助手：监听剪贴板或当前窗口文本，自动生成客服回复。")
    parser.add_argument("--config", help="JSON 配置文件，可覆盖窗口白名单。")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), help="目标平台：wechat/douyin/taobao/pdd。")
    parser.add_argument("--channel", choices=sorted(PLATFORMS), help="兼容旧参数；建议改用 --platform。")
    parser.add_argument("--source", choices=["clipboard", "uia"], default="clipboard", help="clipboard 稳定；uia 尝试读取当前窗口控件文本。")
    parser.add_argument("--merchant-profile", default="通用商家客服助手")
    parser.add_argument("--reply-goal", default="自然回复客户，并推进到留资、下单、预约或人工跟进。")
    parser.add_argument("--window-allowlist", action="append", default=[], help="窗口标题正则白名单。传了以后会覆盖平台默认白名单。")
    parser.add_argument("--poll-seconds", type=float, default=3)
    parser.add_argument("--min-send-gap-seconds", type=float, default=20)
    parser.add_argument("--once", action="store_true", help="只跑一轮。")
    parser.add_argument("--paste", action="store_true", help="检测到新消息后粘贴到当前输入框；默认只复制到剪贴板。")
    parser.add_argument("--send", action="store_true", help="粘贴后按 Enter 发送；必须同时传确认短语。")
    parser.add_argument("--confirm-send", default="", help=f"自动发送确认短语：{CONFIRM_AUTO_SEND}")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不复制、不粘贴、不发送。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.send and (not args.paste or args.confirm_send != CONFIRM_AUTO_SEND):
        print(f"已阻止自动发送。必须传 --paste --send --confirm-send {CONFIRM_AUTO_SEND!r}", file=sys.stderr)
        return 2

    config = load_config(args)
    print(f"桌面客服监听已启动：{config.label}，来源={config.source}，粘贴={'开' if config.paste else '关'}，发送={'开' if config.auto_send else '关'}")
    print("提示：clipboard 模式需要你复制聊天内容；uia 模式会尝试读取当前窗口，但不同客户端兼容性不一样。按 Ctrl+C 停止。")

    last_fingerprint = ""
    last_send_at = 0.0

    while True:
        title = foreground_window_title()
        if not window_allowed(title, config.window_allowlist):
            if config.once:
                print(f"当前窗口不在白名单：{title or '未知'}")
                return 3
            time.sleep(config.poll_seconds)
            continue

        try:
            chat_text = read_clipboard() if config.source == "clipboard" else read_uia_text()
        except Exception as exc:
            print(f"读取聊天失败：{exc}", file=sys.stderr)
            if config.once:
                return 4
            time.sleep(config.poll_seconds)
            continue

        fingerprint = f"{title}\n{chat_text[-2500:]}"
        if not chat_text or fingerprint == last_fingerprint:
            if config.once:
                return 0
            time.sleep(config.poll_seconds)
            continue
        last_fingerprint = fingerprint

        data = call_agent(config, chat_text)
        reply = str(data.get("recommended_reply") or "")
        pending = data.get("pending_customer_messages") or []
        should_reply = bool(data.get("should_reply"))
        print(
            json.dumps(
                {"window": title, "platform": config.label, "should_reply": should_reply, "pending": pending, "reply": reply},
                ensure_ascii=False,
                indent=2,
            )
        )

        if should_reply and reply:
            now = time.time()
            if config.dry_run:
                print("dry-run：不复制、不粘贴、不发送。")
            elif now - last_send_at < config.min_send_gap_seconds:
                print("频率限制：距离上次处理太近，本轮只复制回复到剪贴板。")
                write_clipboard(reply)
            elif config.paste:
                paste_and_optionally_send(reply, send=config.auto_send)
                last_send_at = now
                print("已粘贴。" + (" 已按 Enter 发送。" if config.auto_send else " 未发送，请人工确认。"))
            else:
                write_clipboard(reply)
                print("已复制到剪贴板。")

        if config.once:
            return 0
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
