from __future__ import annotations

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig


class MockAdapter:
    def capabilities(self) -> list[str]:
        return ["mock", "clipboard", "paste", "send"]

    def active_target(self, config: AgentConfig) -> ActiveTarget | None:
        return ActiveTarget(window_id="mock-window", title="Mock Customer Service Window", platform=config.platform, channel=config.platform, label="Mock")

    def read_chat_text(self, config: AgentConfig, target: ActiveTarget) -> str:
        return "客户：你好，请问这个可以今天发货吗？价格有没有优惠？"

    def paste_and_optionally_send(self, reply: str, send: bool, target: ActiveTarget) -> dict[str, object]:
        return {"copied": True, "pasted": True, "sent": bool(send), "reason": "", "target_title": target.title, "foreground_title": target.title}
