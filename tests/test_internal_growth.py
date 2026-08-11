from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["INTERNAL_GROWTH_DATA_DIR"] = tempfile.mkdtemp(prefix="internal-growth-test-")
os.environ.pop("INTERNAL_GROWTH_ENABLE_DAILY_SCHEDULE", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app


class InternalGrowthFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_full_growth_loop_stops_at_human_review(self) -> None:
        demand = self.client.post(
            "/api/internal-growth/demands",
            json={
                "name": "本地门店短视频获客没人咨询",
                "source_type": "manual",
                "source_detail": "unit-test",
                "industry": "本地生活",
                "keywords": ["获客", "短视频", "CRM"],
                "pain_points": "老板每天发内容但没有咨询，不知道哪个需求值得继续做。",
                "raw_text": "今天要先测试一个方向，需要脚本和跟进动作。",
            },
        )
        self.assertEqual(demand.status_code, 200, demand.text)
        demand_id = demand.json()["id"]

        score = self.client.post(f"/api/internal-growth/demands/{demand_id}/score")
        self.assertEqual(score.status_code, 200, score.text)
        self.assertGreaterEqual(score.json()["total_score"], 0)

        content = self.client.post(
            "/api/internal-growth/content/generate",
            json={"demand_id": demand_id, "platforms": ["douyin", "xianyu", "wechat_moments"]},
        )
        self.assertEqual(content.status_code, 200, content.text)
        self.assertEqual(len(content.json()), 3)

        first_task = content.json()[0]
        publishing = self.client.post(
            "/api/internal-growth/publishing-records",
            json={
                "content_task_id": first_task["id"],
                "platform": first_task["platform"],
                "status": "review",
                "views": 0,
                "favorites": 0,
                "consultations": 0,
                "deals": 0,
                "revenue": 0,
                "notes": "人工确认后发布",
            },
        )
        self.assertEqual(publishing.status_code, 200, publishing.text)

        lead = self.client.post(
            "/api/internal-growth/leads",
            json={
                "customer_name": "王老板",
                "source_platform": "douyin",
                "industry": "本地生活",
                "demand": "想知道怎么做短视频获客，有没有报价和案例。",
                "contact": "wechat pending",
                "intent_level": "high",
                "stage": "contacted",
                "next_followup_at": "2026-07-22 18:00",
                "next_action": "发送低成本内容测试方案",
            },
        )
        self.assertEqual(lead.status_code, 200, lead.text)
        lead_id = lead.json()["id"]

        analysis = self.client.post(
            "/api/internal-growth/sales/analyze-chat",
            json={
                "lead_id": lead_id,
                "customer_name": "王老板",
                "industry": "本地生活",
                "product_solution": "内部获客运营系统",
                "conversation": "你这个怎么收费？能不能今天给我报价和方案？",
            },
        )
        self.assertEqual(analysis.status_code, 200, analysis.text)
        self.assertGreaterEqual(analysis.json()["purchase_probability"], 72)

        workflow = self.client.post("/api/internal-growth/workflows/daily/run")
        self.assertEqual(workflow.status_code, 200, workflow.text)
        self.assertEqual(workflow.json()["status"], "needs_human")
        self.assertTrue(workflow.json()["needs_human_confirmation"])
        self.assertIn("does not auto-publish", "\n".join(workflow.json()["logs"]))

        report = self.client.post("/api/internal-growth/analytics/weekly")
        self.assertEqual(report.status_code, 200, report.text)
        self.assertIn("线索1条", report.json()["summary"])

        dashboard = self.client.get("/api/internal-growth/dashboard")
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertGreaterEqual(dashboard.json()["high_intent_leads"], 1)
        self.assertIsNotNone(dashboard.json()["latest_workflow_run"])


if __name__ == "__main__":
    unittest.main()
