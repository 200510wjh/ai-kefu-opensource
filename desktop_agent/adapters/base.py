from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from desktop_agent.config import AgentConfig


@dataclass
class ActiveTarget:
    window_id: str
    title: str
    platform: str
    channel: str
    label: str


class WindowAdapter(Protocol):
    def capabilities(self) -> list[str]:
        ...

    def active_target(self, config: AgentConfig) -> ActiveTarget | None:
        ...

    def read_chat_text(self, config: AgentConfig, target: ActiveTarget) -> str:
        ...

    def paste_and_optionally_send(self, reply: str, send: bool, target: ActiveTarget) -> dict[str, object]:
        ...
