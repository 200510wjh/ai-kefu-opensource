from __future__ import annotations

from typing import Any

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig
from desktop_agent.connectors import connector_for_platform


class WindowsAdapter:
    def capabilities(self) -> list[str]:
        return ["uia", "ocr", "clipboard", "paste", "send", "window_title"]

    def _legacy_config(self, config: AgentConfig) -> Any:
        from scripts.desktop_auto_reply_listener import ListenerConfig

        source = "auto" if config.source == "mock" else config.source
        return ListenerConfig(
            api_base=config.api_base,
            platform=config.platform,
            source=source,  # type: ignore[arg-type]
            merchant_profile=config.merchant_profile,
            knowledge_file=config.knowledge_file,
            reply_goal=config.reply_goal,
            target_title=config.target_title,
            window_allowlist=config.window_allowlist,
            poll_seconds=config.poll_seconds,
            min_send_gap_seconds=config.min_send_gap_seconds,
            once=config.once,
            paste=config.paste,
            auto_send=config.send,
            dry_run=config.dry_run,
            max_chars=config.max_chars,
            min_text_chars=config.min_text_chars,
            min_chat_chars=config.min_chat_chars,
            allow_non_chat_text=config.allow_non_chat_text,
            allow_clipboard_fallback=config.allow_clipboard_fallback,
            ocr_lang=config.ocr_lang,
            debug_screenshot=config.debug_screenshot,
            history_file=config.history_file,
            history_limit=8,
        )

    def active_target(self, config: AgentConfig) -> ActiveTarget | None:
        if config.platform in {"douyin", "douyin_dm", "douyin_private_message"}:
            from scripts.desktop_auto_reply_listener import (
                find_window_handle,
                foreground_window_handle,
                window_title,
            )

            connector = connector_for_platform(config.platform)
            hwnd = find_window_handle(config.target_title) if config.target_title else foreground_window_handle()
            title = window_title(hwnd)
            if not connector.matches_title(title, config):
                return None
            return connector.target_from_window(str(hwnd), title, config)

        from scripts.desktop_auto_reply_listener import detect_target

        legacy_target = detect_target(self._legacy_config(config))
        if not legacy_target:
            return None
        return ActiveTarget(
            window_id=str(legacy_target.hwnd),
            title=legacy_target.title,
            platform=legacy_target.platform,
            channel=legacy_target.backend_channel,
            label=legacy_target.label,
        )

    def read_chat_text(self, config: AgentConfig, target: ActiveTarget) -> str:
        from scripts.desktop_auto_reply_listener import ActiveTarget as LegacyTarget
        from scripts.desktop_auto_reply_listener import read_chat_text

        legacy_target = LegacyTarget(
            hwnd=int(target.window_id or 0),
            title=target.title,
            platform=target.platform,
            backend_channel=target.channel,
            label=target.label,
        )
        return read_chat_text(self._legacy_config(config), legacy_target)

    def paste_and_optionally_send(self, reply: str, send: bool, target: ActiveTarget) -> dict[str, object]:
        from scripts.desktop_auto_reply_listener import paste_and_optionally_send

        return paste_and_optionally_send(reply, send=send, hwnd=int(target.window_id or 0))
