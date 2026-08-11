from __future__ import annotations

from desktop_agent.connectors.base import PreparedMessage, PlatformConnector
from desktop_agent.connectors.douyin_dm import DouyinDMConnector
from desktop_agent.connectors.generic import GenericConnector


def connector_for_platform(platform: str) -> PlatformConnector:
    normalized = (platform or "auto").lower()
    if normalized in {"douyin", "douyin_dm", "douyin_private_message"}:
        return DouyinDMConnector()
    return GenericConnector(normalized)


__all__ = ["DouyinDMConnector", "GenericConnector", "PlatformConnector", "PreparedMessage", "connector_for_platform"]
