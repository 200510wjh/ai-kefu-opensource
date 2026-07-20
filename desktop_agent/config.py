from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


AgentMode = Literal["assist", "auto_paste", "auto_send", "paused"]
AgentSource = Literal["auto", "uia", "ocr", "clipboard", "mock"]

DEFAULT_API_BASE = os.getenv("MERCHANT_DESKTOP_API_BASE", "https://wjhai.cn/merchant-admin/api/v1")
CONFIRM_DESKTOP_AUTO_SEND = "CONFIRM_DESKTOP_AUTO_SEND"


@dataclass
class AgentConfig:
    api_base: str = DEFAULT_API_BASE
    auth_token: str = field(default_factory=lambda: os.getenv("MERCHANT_DESKTOP_AUTH_TOKEN", ""))
    session_id: str = ""
    device_name: str = ""
    platform: str = "auto"
    source: AgentSource = "auto"
    mode: AgentMode = "assist"
    paste: bool = False
    send: bool = False
    confirm_send: str = ""
    merchant_profile: str = "General merchant customer-service assistant."
    knowledge_file: str = ""
    reply_goal: str = "Reply naturally, answer the customer, and move toward lead capture, order, appointment, or human follow-up."
    target_title: str = ""
    window_allowlist: list[str] = field(default_factory=list)
    poll_seconds: float = 2.0
    min_send_gap_seconds: float = 20.0
    once: bool = False
    dry_run: bool = False
    max_chars: int = 6000
    min_text_chars: int = 30
    min_chat_chars: int = 12
    allow_non_chat_text: bool = False
    allow_clipboard_fallback: bool = False
    ocr_lang: str = field(default_factory=lambda: os.getenv("DESKTOP_OCR_LANG", "chi_sim+eng"))
    debug_screenshot: str = "data/desktop-agent/latest-window.png"
    history_file: str = "data/desktop-agent/history.jsonl"
    error_file: str = "data/desktop-agent/errors.jsonl"
    pause_file: str = "data/desktop-agent/PAUSED"
    app_version: str = "desktop-agent-v1"

    @property
    def auto_send_confirmed(self) -> bool:
        return bool(self.send and self.confirm_send == CONFIRM_DESKTOP_AUTO_SEND)


def normalize_config_data(data: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    aliases = {
        "api-base": "api_base",
        "auth-token": "auth_token",
        "confirm-send": "confirm_send",
        "merchant-profile": "merchant_profile",
        "knowledge-file": "knowledge_file",
        "reply-goal": "reply_goal",
        "target-title": "target_title",
        "window-allowlist": "window_allowlist",
        "poll-seconds": "poll_seconds",
        "min-send-gap-seconds": "min_send_gap_seconds",
        "max-chars": "max_chars",
        "min-text-chars": "min_text_chars",
        "min-chat-chars": "min_chat_chars",
        "allow-non-chat-text": "allow_non_chat_text",
        "allow-clipboard-fallback": "allow_clipboard_fallback",
        "ocr-lang": "ocr_lang",
        "debug-screenshot": "debug_screenshot",
        "history-file": "history_file",
        "error-file": "error_file",
        "pause-file": "pause_file",
        "app-version": "app_version",
    }
    for key, value in data.items():
        normalized[aliases.get(key, key)] = value
    if "send" in normalized and "mode" not in normalized:
        normalized["mode"] = "auto_send" if normalized["send"] else "auto_paste" if normalized.get("paste") else "assist"
    return normalized


def load_config_from_args(args: argparse.Namespace) -> AgentConfig:
    raw = vars(args).copy()
    config_path = raw.pop("config", "") or ""
    if config_path:
        file_data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(file_data, dict):
            raise ValueError("Config file must be a JSON object")
        cli_data = {k: v for k, v in raw.items() if v not in (None, "", [], False, 0)}
        raw = {**normalize_config_data(file_data), **cli_data}
    raw = normalize_config_data(raw)
    raw = {k: v for k, v in raw.items() if v not in (None, "", [], False, 0)}
    allowed = set(AgentConfig.__dataclass_fields__.keys())
    data = {key: value for key, value in raw.items() if key in allowed}
    if isinstance(data.get("window_allowlist"), str):
        data["window_allowlist"] = [str(data["window_allowlist"])]
    return AgentConfig(**data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-platform desktop AI customer-service agent.")
    parser.add_argument("--config", default="", help="JSON config file.")
    parser.add_argument("--api-base", default="")
    parser.add_argument("--auth-token", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--device-name", default="")
    parser.add_argument("--platform", default="auto")
    parser.add_argument("--source", choices=["auto", "uia", "ocr", "clipboard", "mock"], default=None)
    parser.add_argument("--mode", choices=["assist", "auto_paste", "auto_send", "paused"], default=None)
    parser.add_argument("--merchant-profile", default="")
    parser.add_argument("--knowledge-file", default="")
    parser.add_argument("--reply-goal", default="")
    parser.add_argument("--target-title", default="")
    parser.add_argument("--window-allowlist", action="append", default=[])
    parser.add_argument("--poll-seconds", type=float, default=0)
    parser.add_argument("--min-send-gap-seconds", type=float, default=0)
    parser.add_argument("--max-chars", type=int, default=0)
    parser.add_argument("--min-text-chars", type=int, default=0)
    parser.add_argument("--min-chat-chars", type=int, default=0)
    parser.add_argument("--ocr-lang", default="")
    parser.add_argument("--debug-screenshot", default="")
    parser.add_argument("--history-file", default="")
    parser.add_argument("--error-file", default="")
    parser.add_argument("--pause-file", default="")
    parser.add_argument("--once", action="store_true", default=None)
    parser.add_argument("--paste", action="store_true", default=None)
    parser.add_argument("--send", action="store_true", default=None)
    parser.add_argument("--confirm-send", default="")
    parser.add_argument("--dry-run", action="store_true", default=None)
    parser.add_argument("--allow-non-chat-text", action="store_true", default=None)
    parser.add_argument("--allow-clipboard-fallback", action="store_true", default=None)
    return parser
