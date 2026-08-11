from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig


@dataclass
class PreparedMessage:
    should_upload: bool
    message_text: str = ""
    hash_basis: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    reason: str = ""


class PlatformConnector(Protocol):
    key: str
    channel: str

    def capabilities(self) -> list[str]:
        ...

    def matches_title(self, title: str, config: AgentConfig) -> bool:
        ...

    def target_from_window(self, window_id: str, title: str, config: AgentConfig) -> ActiveTarget:
        ...

    def prepare_message(self, raw_text: str, target: ActiveTarget, config: AgentConfig) -> PreparedMessage:
        ...
