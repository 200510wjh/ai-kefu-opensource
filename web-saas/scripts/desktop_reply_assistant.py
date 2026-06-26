from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = os.getenv("MERCHANT_DESKTOP_API_BASE", "https://wjhai.cn/merchant-admin/api")
SEND_CONFIRMATION = "我确认发送"

PLATFORMS: dict[str, dict[str, str]] = {
    "wechat": {"backend": "wechat", "label": "微信"},
    "douyin": {"backend": "douyin_dm", "label": "抖音私信"},
    "douyin_dm": {"backend": "douyin_dm", "label": "抖音私信"},
    "taobao": {"backend": "taobao", "label": "淘宝/千牛"},
    "pdd": {"backend": "pdd", "label": "拼多多"},
}


@dataclass
class ReplyResult:
    should_reply: bool
    automation_mode: str
    pending_messages: list[str]
    recommended_reply: str
    next_actions: list[str]
    raw: dict[str, Any]


def endpoint_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/api"):
        return f"{base}/customer-service/chat-reply-agent"
    return f"{base}/api/customer-service/chat-reply-agent"


def read_clipboard() -> str:
    try:
        return read_windows_clipboard()
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
    return completed.stdout


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


def call_reply_agent(api_base: str, payload: dict[str, Any]) -> ReplyResult:
    request = urllib.request.Request(
        endpoint_url(api_base),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"接口返回 {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连接接口失败：{exc}") from exc

    return ReplyResult(
        should_reply=bool(data.get("should_reply")),
        automation_mode=str(data.get("automation_mode", "copy_only")),
        pending_messages=list(data.get("pending_customer_messages") or []),
        recommended_reply=str(data.get("recommended_reply") or ""),
        next_actions=list(data.get("next_actions") or []),
        raw=data,
    )


def press_vk(vk: int, up: bool = False) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0x0002 if up else 0, 0)


def paste_clipboard_to_active_window(send: bool = False) -> None:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="桌面客服单次回复助手：复制聊天内容 -> 生成回复 -> 复制/粘贴到微信、抖音、淘宝、拼多多。"
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="后端 API 根地址，默认使用线上 wjhai.cn。")
    parser.add_argument("--platform", choices=sorted(PLATFORMS), help="目标平台：wechat/douyin/taobao/pdd。")
    parser.add_argument("--channel", choices=sorted(PLATFORMS), help="兼容旧参数；建议改用 --platform。")
    parser.add_argument("--text-file", help="从文本文件读取聊天记录；不传则读取剪贴板。")
    parser.add_argument("--merchant-profile", default="通用商家客服助手", help="商家资料、商品卖点、优惠、禁用承诺等。")
    parser.add_argument("--reply-goal", default="先接住客户问题，再推进到留资、下单、预约或人工跟进。")
    parser.add_argument("--paste", action="store_true", help="把回复粘贴到当前输入框。运行前请先点到目标聊天输入框。")
    parser.add_argument("--send", action="store_true", help="粘贴后按 Enter 发送。必须同时传确认短语。")
    parser.add_argument("--confirm-send", default="", help=f"自动发送确认短语：{SEND_CONFIRMATION}")
    parser.add_argument("--delay", type=float, default=3.0, help="执行粘贴前等待秒数，给你切换到聊天窗口。")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON，方便调试。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.send and (not args.paste or args.confirm_send != SEND_CONFIRMATION):
        print(
            f"已阻止自动发送。真要发送请同时传：--paste --send --confirm-send {SEND_CONFIRMATION!r}",
            file=sys.stderr,
        )
        return 2

    platform = platform_from_args(args)
    platform_info = PLATFORMS[platform]
    chat_text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else read_clipboard()
    if not chat_text.strip():
        print("剪贴板或文本文件为空。请先复制一段聊天记录，或者传 --text-file。", file=sys.stderr)
        return 2

    profile = f"{platform_info['label']}桌面客服助手。{args.merchant_profile}".strip()
    result = call_reply_agent(
        args.api_base,
        {
            "channel": platform_info["backend"],
            "ocr_text": chat_text,
            "merchant_profile": profile,
            "reply_goal": args.reply_goal,
            "auto_send": False,
        },
    )

    if args.json:
        print(json.dumps(result.raw, ensure_ascii=False, indent=2))
    else:
        print(f"平台：{platform_info['label']}")
        print(f"是否建议回复：{'是' if result.should_reply else '否'}")
        print("\n待回复消息：")
        for item in result.pending_messages or ["没有识别到最后一轮未回复客户消息"]:
            print(f"- {item}")
        print("\n推荐回复：")
        print(result.recommended_reply)
        if result.next_actions:
            print("\n下一步提醒：")
            for item in result.next_actions[:3]:
                print(f"- {item}")

    write_clipboard(result.recommended_reply)
    print("\n已把推荐回复复制到剪贴板。")

    if args.paste:
        print(f"{args.delay:g} 秒后粘贴到当前输入框，请把光标放在 {platform_info['label']} 聊天输入框里。")
        time.sleep(max(args.delay, 0))
        paste_clipboard_to_active_window(send=args.send)
        print("已粘贴。" + (" 已按 Enter 发送。" if args.send else " 未发送，请人工确认后再按 Enter。"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
