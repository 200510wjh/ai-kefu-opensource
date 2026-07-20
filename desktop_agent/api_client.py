from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class DesktopAgentApiClient:
    def __init__(self, api_base: str, auth_token: str) -> None:
        base = api_base.rstrip("/")
        if base.endswith("/api"):
            base = f"{base}/v1"
        self.api_base = base
        self.auth_token = auth_token

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base}/{path.lstrip('/')}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API returned {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot connect API: {exc}") from exc
        if isinstance(data, dict) and "data" in data and "ok" in data:
            if not data.get("ok"):
                raise RuntimeError(json.dumps(data.get("error") or data, ensure_ascii=False))
            return data.get("data") or {}
        return data if isinstance(data, dict) else {}

    def register_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/desktop-agent/sessions", payload)

    def send_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/desktop-agent/events", payload)

    def send_result(self, action_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/desktop-agent/actions/{action_id}/result", payload)
