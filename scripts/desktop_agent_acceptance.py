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

        assert_ok(
            client.post(
                "/api/v1/knowledge/import",
                headers=headers,
                json={
                    "title": "Desktop acceptance knowledge",
                    "source_type": "product",
                    "tags": "desktop,douyin,wechat",
                    "sync_to_faq": False,
                    "content": (
                        "Enterprise AI Customer Service Workspace V1 -> Supports website customer service, "
                        "knowledge-base grounded replies, human handoff, and conversation logging.\n"
                        "Desktop Agent -> Supports guarded auto paste/send only for explicitly authorized test contacts."
                    ),
                },
            ),
            "import knowledge",
        )

        session = assert_ok(
            client.post(
                "/api/v1/desktop-agent/sessions",
                headers=headers,
                json={
                    "session_id": "acceptance-douyin-session",
                    "device_name": "acceptance-machine",
                    "os_name": "Windows",
                    "platform": "douyin_dm",
                    "mode": "auto_send",
                    "auto_send_confirmed": True,
                    "capabilities": ["mock", "douyin_dm_connector", "direction_detection", "paste", "send"],
                    "metadata": {"authorized_account_configured": True, "contact_allowlist_count": 1},
                },
            ),
            "register session",
        )
        if session["session"]["session_id"] != "acceptance-douyin-session":
            raise AssertionError("session id mismatch")

        event_payload = {
            "session_id": "acceptance-douyin-session",
            "platform": "douyin_dm",
            "channel": "douyin_dm",
            "window_title": "TestBuyer - Douyin DM",
            "window_id": "mock-douyin-window",
            "source": "mock",
            "message_text": (
                "What is the price? I want to buy Enterprise AI Customer Service Workspace V1 "
                "for website customer service. Please contact me for a demo."
            ),
            "mode": "auto_send",
            "auto_send_enabled": True,
            "auto_send_confirm_phrase": "CONFIRM_DESKTOP_AUTO_SEND",
            "metadata": {
                "connector": "douyin_dm",
                "contact": "TestBuyer",
                "account": "TestShop",
                "last_message_direction": "customer",
                "merged_message_count": 1,
                "parse_confidence": 0.92,
                "connector_safety": {"block_auto_send": False, "risk_flags": []},
            },
        }
        decision = assert_ok(client.post("/api/v1/desktop-agent/events", headers=headers, json=event_payload), "ingest safe event")
        if decision["action"] != "send_reply":
            raise AssertionError(f"safe event did not auto-send: {decision}")
        if not decision["reply_text"]:
            raise AssertionError("reply text is empty")
        if not decision.get("reply_meta", {}).get("citations"):
            raise AssertionError(f"citations missing: {decision}")
        if decision.get("intent_score", 0) < 70:
            raise AssertionError(f"purchase/price intent did not become high intent: {decision}")

        result = assert_ok(
            client.post(
                f"/api/v1/desktop-agent/actions/{decision['action_id']}/result",
                headers=headers,
                json={"status": "sent", "copied": True, "pasted": True, "sent": True, "target_title": "TestBuyer - Douyin DM"},
            ),
            "record result",
        )
        if not result["recorded"]:
            raise AssertionError("result was not recorded")

        conversations = assert_ok(client.get("/api/v1/crm/conversations", headers=headers), "crm conversations")
        if not any(item.get("session_id") == "acceptance-douyin-session" and item.get("intent_score", 0) >= 70 for item in conversations):
            raise AssertionError(f"desktop event did not enter high-intent conversations: {conversations}")
        leads = assert_ok(client.get("/api/v1/crm/leads", headers=headers), "crm leads")
        if not any(item.get("last_session_id") == "acceptance-douyin-session" and item.get("intent_score", 0) >= 70 for item in leads):
            raise AssertionError(f"desktop event did not create/update CRM lead: {leads}")
        tasks = assert_ok(client.get("/api/v1/crm/tasks", headers=headers), "crm tasks")
        if not any(item.get("target_type") == "lead" and item.get("priority") == "high" for item in tasks):
            raise AssertionError(f"high-intent desktop event did not create follow-up task: {tasks}")
        overview = assert_ok(client.get("/api/v1/enterprise/dashboard", headers=headers), "overview")
        if overview.get("auto_replies", 0) < 1:
            raise AssertionError(f"sent desktop reply was not counted as an auto reply: {overview}")

        duplicate = assert_ok(client.post("/api/v1/desktop-agent/events", headers=headers, json=event_payload), "idempotent duplicate")
        if not duplicate["idempotent"] or duplicate["action_id"] != decision["action_id"]:
            raise AssertionError(f"duplicate message was not idempotent: {duplicate}")

        unsupported = dict(event_payload)
        unsupported["message_text"] = "[image] customer sent a product card"
        unsupported["metadata"] = {
            **event_payload["metadata"],
            "connector_safety": {"block_auto_send": True, "risk_flags": ["unsupported_image", "unsupported_product_card"]},
        }
        unsupported_decision = assert_ok(client.post("/api/v1/desktop-agent/events", headers=headers, json=unsupported), "unsupported event")
        if unsupported_decision["action"] != "handoff":
            raise AssertionError(f"unsupported content was not handed off: {unsupported_decision}")

        pause = assert_ok(
            client.post(
                "/api/v1/desktop-agent/pause",
                headers=headers,
                json={"paused": True, "platform": "douyin_dm", "window_title": "", "reason": "acceptance pause"},
            ),
            "pause",
        )
        if not pause["paused"]:
            raise AssertionError("pause state did not persist")

        paused_payload = {**event_payload, "message_text": "Another Enterprise AI Customer Service Workspace V1 question after pause."}
        paused_decision = assert_ok(client.post("/api/v1/desktop-agent/events", headers=headers, json=paused_payload), "paused event")
        if paused_decision["action"] != "none" or not paused_decision["paused"]:
            raise AssertionError(f"paused event was not blocked: {paused_decision}")

        state = assert_ok(client.get("/api/v1/desktop-agent/state", headers=headers), "state")
        logs = assert_ok(client.get("/api/v1/desktop-agent/logs?limit=10", headers=headers), "logs")
        if not state["sessions"] or not logs:
            raise AssertionError("state/logs are empty")
        if not any(item.get("reply_meta", {}).get("citations") for item in logs):
            raise AssertionError("logs do not include reply citations")

        client.close()
        print("desktop_agent_acceptance: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
