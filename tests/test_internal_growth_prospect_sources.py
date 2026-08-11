from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["INTERNAL_GROWTH_DATA_DIR"] = tempfile.mkdtemp(prefix="internal-growth-prospects-")
os.environ.pop("INTERNAL_GROWTH_ENABLE_DAILY_SCHEDULE", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app


class InternalGrowthProspectSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_public_platform_search_candidate_and_crm_conversion(self) -> None:
        search = self.client.post(
            "/api/internal-growth/prospect-searches",
            json={
                "platform": "douyin",
                "intent_goal": "寻找本地生活商家获客痛点",
                "industry": "本地生活",
                "city": "广州",
                "keywords": ["获客", "短视频", "客户咨询"],
                "pain_keywords": ["没人咨询", "转化差"],
                "excluded_keywords": ["招聘", "课程"],
                "notes": "验证抖音公开内容里是否有获客服务需求",
            },
        )
        self.assertEqual(search.status_code, 200, search.text)
        search_body = search.json()
        self.assertEqual(search_body["status"], "needs_human_collection")
        self.assertIn("douyin.com/search", search_body["search_url"])
        self.assertIn("不要自动私信", search_body["guardrail_note"])

        candidate = self.client.post(
            "/api/internal-growth/prospect-candidates",
            json={
                "search_id": search_body["id"],
                "source_platform": "douyin",
                "customer_name": "广州本地生活代运营账号",
                "industry": "本地生活",
                "city": "广州",
                "demand_signal": "公开主页和作品强调帮商家做短视频获客，但评论区多次出现咨询承接慢的问题。",
                "source_url": "https://www.douyin.com/search/example",
                "public_evidence": "公开作品文案提到商家缺稳定咨询；评论区有咨询跟进慢的公开反馈。",
                "contact": "公开主页联系方式待人工核实",
                "fit_reason": "需求发现、内容工厂和 CRM 跟进都匹配。",
                "intent_level": "high",
            },
        )
        self.assertEqual(candidate.status_code, 200, candidate.text)
        candidate_body = candidate.json()

        lead = self.client.post(f"/api/internal-growth/prospect-candidates/{candidate_body['id']}/convert-lead")
        self.assertEqual(lead.status_code, 200, lead.text)
        lead_body = lead.json()
        self.assertEqual(lead_body["source_platform"], "douyin_public")
        self.assertIn("公开来源", lead_body["demand"])
        self.assertIn("不要自动发送", lead_body["next_action"])

        candidates = self.client.get("/api/internal-growth/prospect-candidates")
        self.assertEqual(candidates.status_code, 200, candidates.text)
        self.assertEqual(candidates.json()[0]["status"], "converted")

    def test_agent_can_create_purposeful_public_search(self) -> None:
        response = self.client.post(
            "/api/internal-growth/agent/run",
            json={
                "task": "去抖音搜索真实客户，找本地生活商家获客痛点",
                "context": {"industry": "本地生活", "city": "深圳", "keywords": ["获客", "短视频"]},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertIn("create_public_prospect_search", body["plan"]["needed_tools"])
        self.assertEqual(body["tool_results"][0]["status"], "success")
        self.assertIn("douyin.com/search", body["tool_results"][0]["output"]["search_url"])

    def test_open_source_provider_status_and_unconfigured_search(self) -> None:
        integrations = self.client.get("/api/internal-growth/source-integrations")
        self.assertEqual(integrations.status_code, 200, integrations.text)
        providers = {item["provider"]: item for item in integrations.json()}
        self.assertIn("searxng", providers)
        self.assertIn("github.com/searxng/searxng", providers["searxng"]["repository_url"])

        search = self.client.post(
            "/api/internal-growth/prospect-searches",
            json={
                "platform": "baidu",
                "intent_goal": "寻找公开官网潜在客户",
                "industry": "企业服务",
                "keywords": ["获客", "CRM"],
                "pain_keywords": ["销售跟进慢"],
                "excluded_keywords": [],
                "notes": "",
            },
        )
        self.assertEqual(search.status_code, 200, search.text)
        result = self.client.post(f"/api/internal-growth/prospect-searches/{search.json()['id']}/external-results?provider=searxng")
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body["provider"], "searxng")
        self.assertFalse(body["configured"])
        self.assertEqual(body["results"], [])
        self.assertIn("INTERNAL_GROWTH_SEARXNG_URL", body["message"])


if __name__ == "__main__":
    unittest.main()
