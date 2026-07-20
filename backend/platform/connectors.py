from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


ConnectorKey = Literal["website", "api", "wechat", "wechat_work", "douyin", "douyin_dm", "taobao", "pdd", "xianyu"]
ConnectorStatus = Literal["disabled", "not_configured", "pending_auth", "connected", "failed", "assist_only"]


class ConnectorMessage(BaseModel):
    connector: ConnectorKey
    external_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    text: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ConnectorLead(BaseModel):
    connector: ConnectorKey
    external_id: str = ""
    name: str = ""
    contact: str = ""
    need: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ConnectorResult(BaseModel):
    ok: bool
    status: ConnectorStatus
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class Connector(Protocol):
    key: ConnectorKey

    def status(self) -> ConnectorResult:
        ...

    def receive_messages(self) -> list[ConnectorMessage]:
        ...

    def send_message(self, message: ConnectorMessage) -> ConnectorResult:
        ...

    def sync_leads(self) -> list[ConnectorLead]:
        ...


class BaseConnector:
    def __init__(self, key: ConnectorKey, label: str, status: ConnectorStatus = "not_configured"):
        self.key = key
        self.label = label
        self._status = status

    def status(self) -> ConnectorResult:
        return ConnectorResult(ok=self._status in {"connected", "assist_only"}, status=self._status, message=self.label)

    def receive_messages(self) -> list[ConnectorMessage]:
        return []

    def send_message(self, message: ConnectorMessage) -> ConnectorResult:
        if self._status != "connected":
            return ConnectorResult(ok=False, status=self._status, message="Connector is not authorized for direct sending.")
        return ConnectorResult(ok=False, status="failed", message="Sending is not implemented for this connector.")

    def sync_leads(self) -> list[ConnectorLead]:
        return []


CONNECTOR_REGISTRY: dict[ConnectorKey, BaseConnector] = {
    "website": BaseConnector("website", "Website widget", "connected"),
    "api": BaseConnector("api", "Open API", "pending_auth"),
    "wechat": BaseConnector("wechat", "WeChat", "assist_only"),
    "wechat_work": BaseConnector("wechat_work", "WeCom", "pending_auth"),
    "douyin": BaseConnector("douyin", "Douyin", "pending_auth"),
    "douyin_dm": BaseConnector("douyin_dm", "Douyin DM", "pending_auth"),
    "taobao": BaseConnector("taobao", "Taobao/Qianniu", "pending_auth"),
    "pdd": BaseConnector("pdd", "Pinduoduo", "pending_auth"),
    "xianyu": BaseConnector("xianyu", "Xianyu", "assist_only"),
}


def get_connector(key: str) -> BaseConnector:
    normalized = "douyin_dm" if key == "douyin_private_message" else key
    if normalized not in CONNECTOR_REGISTRY:
        return BaseConnector("api", f"Unsupported connector: {key}", "failed")
    return CONNECTOR_REGISTRY[normalized]  # type: ignore[index]


def list_connectors() -> list[ConnectorResult]:
    return [connector.status() for connector in CONNECTOR_REGISTRY.values()]

