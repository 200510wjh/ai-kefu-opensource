from __future__ import annotations

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig
from desktop_agent.connectors.base import PreparedMessage


class GenericConnector:
    def __init__(self, platform: str = "auto") -> None:
        self.key = platform or "auto"
        self.channel = self.key

    def capabilities(self) -> list[str]:
        return ["generic_connector"]

    def matches_title(self, title: str, config: AgentConfig) -> bool:
        return bool(title)

    def target_from_window(self, window_id: str, title: str, config: AgentConfig) -> ActiveTarget:
        platform = config.platform if config.platform != "auto" else self.key
        return ActiveTarget(window_id=window_id, title=title, platform=platform, channel=platform, label=platform)

    def prepare_message(self, raw_text: str, target: ActiveTarget, config: AgentConfig) -> PreparedMessage:
        text = raw_text.strip()
        return PreparedMessage(
            should_upload=bool(text),
            message_text=text,
            hash_basis=f"{target.platform}:{target.title}:{text}",
            metadata={
                "connector": self.key,
                "connector_safety": {"block_auto_send": False, "risk_flags": []},
                "parse_confidence": 0.55,
            },
            reason="" if text else "empty text",
        )
