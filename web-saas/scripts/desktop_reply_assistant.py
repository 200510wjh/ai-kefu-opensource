from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_API_BASE = os.getenv("MERCHANT_DESKTOP_API_BASE", "https://wjhai.cn/merchant-admin/api")
SEND_CONFIRMATION = "我确认发送"


@dataclass
class ReplyResult:
    should_reply: bool
    automation_mode: str
    pending_messages: list[str]
    recommended_reply: str
    raw: dict[str, Any]


def read_clipboard() -> str:
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception:
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
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return
    except Exception:
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


def call_reply_agent(api_base: str, payload: dict[str, Any]) -> ReplyResult:
    url = f"{api_base.rstrip('/')}/customer-service/chat-reply-agent"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
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
        raw=data,
    )


def press_vk(vk: int, up: bool = False) -> None:
    user32 = ctypes.windll.user32
    keyeventf_keyup = 0x0002
    user32.keybd_event(vk, 0, keyeventf_keyup if up else 0, 0)


def paste_clipboard_to_active_window(send: bool = False) -> None:
    # Ctrl+V into the currently focused chat input. Enter is only used after explicit confirmation.
    vk_control = 0x11
    vk_v = 0x56
    vk_enter = 0x0D
    press_vk(vk_control)
    press_vk(vk_v)
    press_vk(vk_v, up=True)
    press_vk(vk_control, up=True)
    if send:
        time.sleep(0.2)
        press_vk(vk_enter)
        press_vk(vk_enter, up=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="读取剪贴板聊天记录，生成微信/抖音客服候选回复。")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="后端 API 根地址，默认使用 MERCHANT_DESKTOP_API_BASE 或线上 wjhai.cn。")
    parser.add_argument("--text-file", help="从文本文件读取聊天记录；不传则读取剪贴板。")
    parser.add_argument("--channel", choices=["wechat", "douyin_dm", "customer_service"], default="wechat")
    parser.add_argument("--merchant-profile", default="微信风格回复助手")
    parser.add_argument("--reply-goal", default="先确认需求，再引导留下联系方式")
    parser.add_argument("--paste", action="store_true", help="把推荐回复粘贴到当前输入框；运行前请先点到微信/客服输入框。")
    parser.add_argument("--send", action="store_true", help="粘贴后按 Enter 发送。必须同时传 --confirm-send。")
    parser.add_argument("--confirm-send", default="", help=f"若要自动发送，必须填：{SEND_CONFIRMATION}")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON，方便调试。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.send and (not args.paste or args.confirm_send != SEND_CONFIRMATION):
        print(f"已阻止自动发送。若确实要发送，必须同时传 --paste --send --confirm-send {SEND_CONFIRMATION!r}", file=sys.stderr)
        return 2

    chat_text = open(args.text_file, encoding="utf-8").read() if args.text_file else read_clipboard()
    if not chat_text.strip():
        print("剪贴板或文本文件为空。请先复制聊天记录。", file=sys.stderr)
        return 2

    result = call_reply_agent(
        args.api_base,
        {
            "channel": args.channel,
            "ocr_text": chat_text,
            "merchant_profile": args.merchant_profile,
            "reply_goal": args.reply_goal,
            "auto_send": args.send,
        },
    )
    if args.json:
        print(json.dumps(result.raw, ensure_ascii=False, indent=2))
    else:
        print("待回复消息：")
        for item in result.pending_messages or ["没有检测到未回复客户消息"]:
            print(f"- {item}")
        print(f"\n模式：{result.automation_mode}")
        print("\n推荐回复：")
        print(result.recommended_reply)

    write_clipboard(result.recommended_reply)
    print("\n已把推荐回复复制到剪贴板。")

    if args.paste:
        print("3 秒后粘贴到当前输入框，请确认光标已经在聊天输入框里。")
        time.sleep(3)
        paste_clipboard_to_active_window(send=args.send)
        print("已粘贴。" + (" 已发送。" if args.send else " 未按 Enter 发送。"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
