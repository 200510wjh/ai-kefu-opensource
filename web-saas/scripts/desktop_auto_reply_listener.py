from __future__ import annotations

import argparse
import ctypes
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
CONFIRM_AUTO_SEND = "我确认自动发送"


@dataclass
class ListenerConfig:
    api_base: str
    source: Literal["clipboard", "uia"]
    channel: str
    merchant_profile: str
    reply_goal: str
    window_allowlist: list[str]
    poll_seconds: float
    min_send_gap_seconds: float
    once: bool
    auto_send: bool
    dry_run: bool


def read_clipboard() -> str:
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
        raise RuntimeError("未安装 uiautomation。先运行：pip install uiautomation，或改用 --source clipboard。") from exc

    control = auto.GetForegroundControl()
    texts: list[str] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 6 or len(texts) >= 160:
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


def call_agent(config: ListenerConfig, chat_text: str, auto_send_requested: bool) -> dict[str, Any]:
    payload = {
        "channel": config.channel,
        "ocr_text": chat_text,
        "merchant_profile": config.merchant_profile,
        "reply_goal": config.reply_goal,
        "auto_send": auto_send_requested,
    }
    request = urllib.request.Request(
        f"{config.api_base.rstrip('/')}/customer-service/chat-reply-agent",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"接口返回 {exc.code}: {detail}") from exc


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
        time.sleep(0.2)
        press_vk(vk_enter)
        press_vk(vk_enter, up=True)


def load_config(args: argparse.Namespace) -> ListenerConfig:
    allowlist = args.window_allowlist or []
    if args.config:
        data = json.loads(Path(args.config).read_text(encoding="utf-8"))
        allowlist = data.get("window_allowlist", allowlist)
    return ListenerConfig(
        api_base=args.api_base,
        source=args.source,
        channel=args.channel,
        merchant_profile=args.merchant_profile,
        reply_goal=args.reply_goal,
        window_allowlist=allowlist,
        poll_seconds=args.poll_seconds,
        min_send_gap_seconds=args.min_send_gap_seconds,
        once=args.once,
        auto_send=args.auto_send,
        dry_run=args.dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="监听当前客服窗口，生成并可选自动发送回复。")
    parser.add_argument("--config", help="JSON 配置文件，可放窗口白名单。")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--source", choices=["clipboard", "uia"], default="clipboard", help="clipboard 稳定；uia 可尝试直接读当前窗口控件文本。")
    parser.add_argument("--channel", choices=["wechat", "douyin_dm", "customer_service"], default="wechat")
    parser.add_argument("--merchant-profile", default="微信风格自动客服")
    parser.add_argument("--reply-goal", default="自然回复客户，并引导留下联系方式或下一步需求")
    parser.add_argument("--window-allowlist", action="append", default=[], help="只允许匹配这些窗口标题正则时运行，例如 微信|企业微信。可重复。")
    parser.add_argument("--poll-seconds", type=float, default=3)
    parser.add_argument("--min-send-gap-seconds", type=float, default=20)
    parser.add_argument("--once", action="store_true", help="只跑一轮。")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不粘贴，不发送。")
    parser.add_argument("--auto-send", action="store_true", help="真实按 Enter 发送，必须同时传确认短语。")
    parser.add_argument("--confirm-auto-send", default="", help=f"自动发送确认短语：{CONFIRM_AUTO_SEND}")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.auto_send and args.confirm_auto_send != CONFIRM_AUTO_SEND:
        print(f"已阻止自动发送。必须传 --confirm-auto-send {CONFIRM_AUTO_SEND!r}", file=sys.stderr)
        return 2

    config = load_config(args)
    last_fingerprint = ""
    last_send_at = 0.0

    while True:
        title = foreground_window_title()
        if not window_allowed(title, config.window_allowlist):
            print(f"跳过窗口：{title or '未知'}")
            if config.once:
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

        fingerprint = f"{title}\n{chat_text[-2000:]}"
        if not chat_text or fingerprint == last_fingerprint:
            if config.once:
                return 0
            time.sleep(config.poll_seconds)
            continue
        last_fingerprint = fingerprint

        data = call_agent(config, chat_text, auto_send_requested=config.auto_send)
        reply = str(data.get("recommended_reply") or "")
        pending = data.get("pending_customer_messages") or []
        should_reply = bool(data.get("should_reply"))
        mode = data.get("automation_mode")
        print(json.dumps({"window": title, "should_reply": should_reply, "mode": mode, "pending": pending, "reply": reply}, ensure_ascii=False, indent=2))

        if should_reply and reply:
            now = time.time()
            if now - last_send_at < config.min_send_gap_seconds:
                print("频率限制：距离上次发送太近，本轮只复制回复。")
                write_clipboard(reply)
            elif config.dry_run:
                print("dry-run：不粘贴、不发送。")
            else:
                paste_and_optionally_send(reply, send=config.auto_send)
                last_send_at = now
                print("已粘贴。" + (" 已发送。" if config.auto_send else " 未发送。"))

        if config.once:
            return 0
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
