from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def assert_ok(response, label: str) -> dict:
    if response.status_code >= 400:
        raise AssertionError(f"{label} failed: {response.status_code} {response.text}")
    body = response.json()
    if isinstance(body, dict) and body.get("ok") is False:
        raise AssertionError(f"{label} returned error: {body}")
    return body.get("data", body)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="desktop-agent-acceptance-", ignore_cleanup_errors=True) as temp_dir:
        data_dir = Path(temp_dir)
        os.environ["MERCHANT_AUTO_CUT_DATA_DIR"] = str(data_dir)
        os.environ["CS_SQLITE_PATH"] = str(data_dir / "customer_service.sqlite3")
        os.environ.setdefault("AUTH_SECRET", "desktop-agent-acceptance-secret")

        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        login = assert_ok(client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}), "login")
        token = login["token"]
        headers = {"Authorization": f"Bearer {token}"}

        session = assert_ok(
            client.post(
                "/api/v1/desktop-agent/sessions",
                headers=headers,
                json={
                    "session_id": "acceptance-session",
                    "device_name": "acceptance-machine",
                    "os_name": "Windows",
                    "platform": "douyin",
                    "mode": "auto_send",
                    "auto_send_confirmed": True,
                    "capabilities": ["mock", "ocr", "uia", "paste", "send"],
                },
            ),
            "register session",
        )
        if session["session"]["session_id"] != "acceptance-session":
            raise AssertionError("session id mismatch")

        decision = assert_ok(
            client.post(
                "/api/v1/desktop-agent/events",
                headers=headers,
                json={
                    "session_id": "acceptance-session",
                    "platform": "douyin",
                    "channel": "douyin_dm",
                    "window_title": "Mock Douyin Customer Window",
                    "window_id": "mock-window",
                    "source": "mock",
                    "message_text": "客户：你好，这个套餐多少钱？今天能安排演示吗？",
                    "mode": "auto_send",
                    "auto_send_enabled": True,
                    "auto_send_confirm_phrase": "CONFIRM_DESKTOP_AUTO_SEND",
                },
            ),
            "ingest event",
        )
        if decision["action"] not in {"send_reply", "paste_reply", "draft_only"}:
            raise AssertionError(f"unexpected action: {decision}")
        if not decision["reply_text"]:
            raise AssertionError("reply text is empty")
        if not decision["action_id"]:
            raise AssertionError("action id is empty")

        result = assert_ok(
            client.post(
                f"/api/v1/desktop-agent/actions/{decision['action_id']}/result",
                headers=headers,
                json={"status": "sent", "copied": True, "pasted": True, "sent": True, "target_title": "Mock Douyin Customer Window"},
            ),
            "record result",
        )
        if not result["recorded"]:
            raise AssertionError("result was not recorded")

        duplicate = assert_ok(
            client.post(
                "/api/v1/desktop-agent/events",
                headers=headers,
                json={
                    "session_id": "acceptance-session",
                    "platform": "douyin",
                    "channel": "douyin_dm",
                    "window_title": "Mock Douyin Customer Window",
                    "source": "mock",
                    "message_text": "客户：你好，这个套餐多少钱？今天能安排演示吗？",
                    "mode": "auto_send",
                    "auto_send_enabled": True,
                    "auto_send_confirm_phrase": "CONFIRM_DESKTOP_AUTO_SEND",
                },
            ),
            "idempotent duplicate",
        )
        if not duplicate["idempotent"]:
            raise AssertionError("duplicate message was not idempotent")

        pause = assert_ok(
            client.post(
                "/api/v1/desktop-agent/pause",
                headers=headers,
                json={"paused": True, "platform": "", "window_title": "", "reason": "acceptance pause"},
            ),
            "pause",
        )
        if not pause["paused"]:
            raise AssertionError("pause state did not persist")

        paused_decision = assert_ok(
            client.post(
                "/api/v1/desktop-agent/events",
                headers=headers,
                json={
                    "session_id": "acceptance-session",
                    "platform": "douyin",
                    "channel": "douyin_dm",
                    "window_title": "Mock Douyin Customer Window",
                    "source": "mock",
                    "message_text": "客户：我想换一个问题，能开发票吗？",
                    "mode": "auto_send",
                    "auto_send_enabled": True,
                    "auto_send_confirm_phrase": "CONFIRM_DESKTOP_AUTO_SEND",
                },
            ),
            "paused event",
        )
        if paused_decision["action"] != "none" or not paused_decision["paused"]:
            raise AssertionError(f"paused event was not blocked: {paused_decision}")

        state = assert_ok(client.get("/api/v1/desktop-agent/state", headers=headers), "state")
        logs = assert_ok(client.get("/api/v1/desktop-agent/logs?limit=10", headers=headers), "logs")
        if not state["sessions"] or not logs:
            raise AssertionError("state/logs are empty")

        client.close()
        print("desktop_agent_acceptance: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
