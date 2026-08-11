from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["INTERNAL_GROWTH_DATA_DIR"] = tempfile.mkdtemp(prefix="internal-growth-guardrails-")
os.environ.pop("INTERNAL_GROWTH_ENABLE_DAILY_SCHEDULE", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.internal_growth.models import Lead
from backend.internal_growth.store import store
from backend.internal_growth.tool_executor import execute_tool
from backend.main import app


class InternalGrowthToolGuardrailsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        for path in [
            store.demands_path,
            store.opportunities_path,
            store.content_tasks_path,
            store.publishing_records_path,
            store.leads_path,
            store.follow_up_tasks_path,
            store.tool_runs_path,
        ]:
            path.write_text("[]\n", encoding="utf-8")
        self.lead = store.save_lead(
            Lead(
                id="lead-guardrail-1",
                customer_name="真实客户：本地生活代运营公司",
                source_platform="public_web",
                industry="抖音本地生活代运营",
                demand="公开页面显示其服务本地商家，需要内容产出、客户跟进和复盘。",
                contact="官网公开页面",
                intent_level="medium",
                stage="new",
                next_action="人工核实官网后发送合作测试邀约。",
            )
        )

    def test_missing_required_parameter_is_blocked(self) -> None:
        result = execute_tool("task-missing-param", "generate_contact_suggestion", {})
        self.assertEqual(result.status, "blocked")
        self.assertIn("lead_id", result.blocked_reason)

    def test_high_risk_auto_contact_requires_human(self) -> None:
        result = execute_tool(
            "task-high-risk",
            "auto_contact_customer",
            {"lead_id": self.lead.id, "message": "自动发送测试"},
        )
        self.assertEqual(result.status, "needs_human")
        self.assertIn("人工确认", result.blocked_reason)

    def test_duplicate_tool_call_is_blocked(self) -> None:
        first = execute_tool("task-duplicate", "generate_contact_suggestion", {"lead_id": self.lead.id})
        second = execute_tool("task-duplicate", "generate_contact_suggestion", {"lead_id": self.lead.id})
        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "blocked")
        self.assertIn("重复调用", second.blocked_reason)

    def test_agent_run_generates_contact_suggestion_and_audit_log(self) -> None:
        response = self.client.post(
            "/api/internal-growth/agent/run",
            json={"task": "给这个真实客户生成联系建议，不要自动发送", "context": {"lead_id": self.lead.id}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["tool_results"][0]["status"], "success")
        self.assertIn("dm_draft", body["tool_results"][0]["output"])

        logs = self.client.get("/api/internal-growth/agent/tool-runs")
        self.assertEqual(logs.status_code, 200, logs.text)
        self.assertGreaterEqual(len(logs.json()), 1)

    def test_agent_plan_marks_auto_send_as_human_confirmation(self) -> None:
        response = self.client.post(
            "/api/internal-growth/agent/plan",
            json={"task": "自动私信这个客户并提交官网表单", "context": {"lead_id": self.lead.id}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["requires_human_confirmation"])
        self.assertIn("auto_contact_customer", body["needed_tools"])

    def test_summit_content_pack_creates_review_records(self) -> None:
        result = execute_tool(
            "task-summit-pack",
            "generate_summit_content_pack",
            {"topic": "AI企业SOP"},
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.output["content_task_ids"]), 3)
        self.assertEqual(len(store.list_content_tasks()), 3)
        self.assertEqual(len(store.list_publishing_records()), 3)
        self.assertIn("不会自动发布", result.output["guardrail"])

    def test_xianyu_service_draft_creates_one_review_record(self) -> None:
        result = execute_tool(
            "task-xianyu-draft",
            "create_xianyu_service_draft",
            {"service_name": "企业AI客服流程诊断"},
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.output["content_task_id"])
        self.assertEqual(len(store.list_content_tasks()), 1)
        self.assertEqual(store.list_content_tasks()[0].platform, "xianyu")

    def test_agent_run_recommends_open_source_stack(self) -> None:
        response = self.client.post(
            "/api/internal-growth/agent/run",
            json={"task": "找适合抖音发布和闲鱼获客Agent的GitHub开源项目", "context": {"goal": "抖音发布 闲鱼获客 Agent"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "success")
        tool_names = [item["tool_name"] for item in body["tool_results"]]
        self.assertIn("recommend_open_source_stack", tool_names)
        self.assertNotIn("create_xianyu_service_draft", tool_names)


if __name__ == "__main__":
    unittest.main()
