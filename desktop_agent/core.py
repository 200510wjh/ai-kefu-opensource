from __future__ import annotations

import platform as py_platform
import time
from pathlib import Path
from typing import Any

from desktop_agent.adapters.base import ActiveTarget, WindowAdapter
from desktop_agent.adapters.mock import MockAdapter
from desktop_agent.api_client import DesktopAgentApiClient
from desktop_agent.config import AgentConfig, CONFIRM_DESKTOP_AUTO_SEND
from desktop_agent.connectors import PreparedMessage, connector_for_platform
from desktop_agent.local_logging import append_jsonl
from desktop_agent.normalizer import looks_like_chat_text, message_hash, normalize_chat_candidate
from desktop_agent.safety import LocalSendGate, is_locally_paused


def select_adapter(config: AgentConfig) -> WindowAdapter:
    if config.source == "mock":
        return MockAdapter()
    system = py_platform.system()
    if system == "Windows":
        from desktop_agent.adapters.windows import WindowsAdapter

        return WindowsAdapter()
    if system == "Darwin":
        from desktop_agent.adapters.macos import MacOSAdapter

        return MacOSAdapter()
    return MockAdapter()


class DesktopAgent:
    def __init__(self, config: AgentConfig, adapter: WindowAdapter | None = None) -> None:
        self.config = config
        self.adapter = adapter or select_adapter(config)
        self.connector = connector_for_platform(config.platform)
        self.api = DesktopAgentApiClient(config.api_base, config.auth_token)
        self.send_gate = LocalSendGate(config.min_send_gap_seconds, config.daily_send_limit, config.send_state_file)
        self.last_fingerprint = ""
        self.last_candidate_fingerprint = ""
        self.candidate_first_seen_at = 0.0
        self.session_id = config.session_id

    def register_session(self) -> dict[str, Any]:
        response = self.api.register_session(
            {
                "session_id": self.session_id,
                "device_name": self.config.device_name,
                "os_name": py_platform.system(),
                "platform": self.config.platform,
                "app_version": self.config.app_version,
                "mode": self.config.mode,
                "paused": self.config.mode == "paused",
                "auto_send_confirmed": self.config.auto_send_confirmed,
                "window_allowlist": self.config.window_allowlist,
                "capabilities": [*self.adapter.capabilities(), *self.connector.capabilities()],
                "metadata": {
                    "connector": self.connector.key,
                    "authorized_account_configured": bool(self.config.authorized_account),
                    "contact_allowlist_count": len(self.config.contact_allowlist),
                    "daily_send_limit": self.config.daily_send_limit,
                    "message_stability_seconds": self.config.message_stability_seconds,
                },
            }
        )
        session = response.get("session") or {}
        self.session_id = str(session.get("session_id") or self.session_id)
        append_jsonl(self.config.history_file, {"event": "session_registered", "session_id": self.session_id, "response": response})
        return response

    def read_once(self) -> tuple[ActiveTarget | None, str]:
        target = self.adapter.active_target(self.config)
        if not target:
            return None, ""
        text = self.adapter.read_chat_text(self.config, target).strip()
        return target, text

    def send_event(self, target: ActiveTarget, prepared: PreparedMessage, local_paused: bool) -> dict[str, Any]:
        message_text = prepared.message_text
        return self.api.send_event(
            {
                "session_id": self.session_id,
                "platform": target.platform,
                "channel": target.channel,
                "window_title": target.title,
                "window_id": target.window_id,
                "source": "mock" if self.config.source == "mock" else self.config.source if self.config.source != "auto" else "uia",
                "message_text": message_text,
                "message_hash": message_hash(prepared.hash_basis or message_text),
                "mode": self.config.mode,
                "auto_send_enabled": bool(self.config.send),
                "auto_send_confirm_phrase": self.config.confirm_send if self.config.send else "",
                "local_paused": local_paused,
                "reply_goal": self.config.reply_goal,
                "merchant_profile": self.config.merchant_profile,
                "metadata": prepared.metadata,
            }
        )

    def execute_decision(self, target: ActiveTarget, decision: dict[str, Any]) -> dict[str, Any]:
        action = str(decision.get("action") or "none")
        action_id = str(decision.get("action_id") or "")
        reply = str(decision.get("reply_text") or "")
        if self.config.dry_run or action in {"none", "draft_only", "handoff"}:
            result = {
                "status": "skipped" if self.config.dry_run else "blocked" if action == "handoff" else "copied",
                "copied": False,
                "pasted": False,
                "sent": False,
                "reason": "dry-run" if self.config.dry_run else str(decision.get("reason") or action),
            }
        elif action == "send_reply":
            if not self.send_gate.can_send():
                result = {
                    "status": "blocked",
                    "copied": False,
                    "pasted": False,
                    "sent": False,
                    "reason": self.send_gate.last_block_reason or "local send gate",
                }
            else:
                paste_result = self.adapter.paste_and_optionally_send(reply, send=True, target=target)
                if paste_result.get("sent"):
                    self.send_gate.mark_sent()
                result = {"status": "sent" if paste_result.get("sent") else "failed", **paste_result}
        elif action == "paste_reply":
            if not self.config.paste:
                result = {"status": "copied", "copied": False, "pasted": False, "sent": False, "reason": "paste disabled locally"}
            else:
                paste_result = self.adapter.paste_and_optionally_send(reply, send=False, target=target)
                result = {"status": "pasted" if paste_result.get("pasted") else "failed", **paste_result}
        else:
            result = {"status": "skipped", "copied": False, "pasted": False, "sent": False, "reason": f"unknown action {action}"}
        if action_id:
            try:
                self.api.send_result(action_id, result)
            except Exception as exc:
                append_jsonl(self.config.error_file, {"event": "result_upload_failed", "action_id": action_id, "error": str(exc), "result": result})
        return result

    def tick(self) -> bool:
        local_paused = is_locally_paused(self.config.pause_file)
        if local_paused and self.config.once:
            append_jsonl(self.config.history_file, {"event": "paused", "pause_file": self.config.pause_file})
            return False
        target, chat_text = self.read_once()
        if not target:
            return False
        prepared = self.connector.prepare_message(chat_text[-self.config.max_chars :], target, self.config)
        if not prepared.should_upload:
            append_jsonl(
                self.config.history_file,
                {
                    "event": "connector_skipped",
                    "session_id": self.session_id,
                    "window": target.title,
                    "platform": target.platform,
                    "reason": prepared.reason,
                    "metadata": prepared.metadata,
                },
            )
            return False
        fingerprint = f"{target.platform}:{target.title}:{message_hash(prepared.hash_basis or prepared.message_text)}"
        if not prepared.message_text or fingerprint == self.last_fingerprint:
            return False
        if not self.config.once and self.config.message_stability_seconds > 0:
            now = time.time()
            if fingerprint != self.last_candidate_fingerprint:
                self.last_candidate_fingerprint = fingerprint
                self.candidate_first_seen_at = now
                append_jsonl(
                    self.config.history_file,
                    {
                        "event": "message_waiting_for_stability",
                        "session_id": self.session_id,
                        "window": target.title,
                        "platform": target.platform,
                        "wait_seconds": self.config.message_stability_seconds,
                    },
                )
                return False
            if now - self.candidate_first_seen_at < self.config.message_stability_seconds:
                return False
        self.last_fingerprint = fingerprint
        if not self.config.allow_non_chat_text and not looks_like_chat_text(prepared.message_text, self.config.min_chat_chars):
            append_jsonl(
                self.config.history_file,
                {
                    "event": "not_chat_like",
                    "window": target.title,
                    "candidate": normalize_chat_candidate(prepared.message_text)[:500],
                    "metadata": prepared.metadata,
                },
            )
            return False
        decision = self.send_event(target, prepared, local_paused)
        result = self.execute_decision(target, decision)
        append_jsonl(
            self.config.history_file,
            {
                "event": "decision",
                "session_id": self.session_id,
                "window": target.title,
                "platform": target.platform,
                "action": decision.get("action"),
                "action_id": decision.get("action_id"),
                "message_hash": decision.get("message_hash"),
                "risk_flags": decision.get("risk_flags"),
                "reply_meta": decision.get("reply_meta"),
                "result": result,
            },
        )
        return True

    def run(self) -> int:
        if self.config.send and self.config.confirm_send != CONFIRM_DESKTOP_AUTO_SEND:
            raise RuntimeError(f"Auto-send requires --confirm-send {CONFIRM_DESKTOP_AUTO_SEND!r}")
        Path(self.config.history_file).parent.mkdir(parents=True, exist_ok=True)
        self.register_session()
        while True:
            try:
                handled = self.tick()
            except KeyboardInterrupt:
                return 130
            except Exception as exc:
                append_jsonl(self.config.error_file, {"event": "tick_failed", "error": str(exc)})
                if self.config.once:
                    raise
            if self.config.once:
                return 0 if handled else 3
            time.sleep(self.config.poll_seconds)
