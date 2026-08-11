from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.store import store


TEST_DEMAND_NAMES = {
    "本地生活商家需要稳定获取咨询客户",
    "个人创业者想用AI减少找需求和发内容时间",
    "咨询服务需要高意向客户筛选",
}


def classify_lead_source(source: str) -> str:
    if source == "public_web" or source.endswith("_public"):
        return "真实公开潜在客户，需人工核实和触达"
    if source in {"douyin", "xianyu", "wechat_moments"}:
        return "平台线索，但需确认是否真实入站咨询"
    return "人工或未知来源，需补充来源证据"


def main() -> int:
    demands = store.list_demands()
    leads = store.list_leads()
    content_tasks = store.list_content_tasks()
    publishing_records = store.list_publishing_records()
    followups = store.list_follow_up_tasks()
    reports = store.list_analytics_reports()
    tool_runs = store.list_tool_runs()
    prospect_searches = store.list_prospect_searches()
    prospect_candidates = store.list_prospect_candidates()

    test_demands = [item for item in demands if item.name in TEST_DEMAND_NAMES or "测试种子" in item.source_detail]
    public_leads = [item for item in leads if item.source_platform == "public_web" or item.source_platform.endswith("_public")]
    real_inbound_leads = [item for item in leads if item.source_platform in {"douyin", "xianyu", "wechat_moments"} and "测试" not in item.customer_name]

    payload = {
        "summary": {
            "demands": len(demands),
            "test_or_seed_demands": len(test_demands),
            "content_tasks": len(content_tasks),
            "publishing_records": len(publishing_records),
            "leads": len(leads),
            "public_prospect_leads": len(public_leads),
            "prospect_searches": len(prospect_searches),
            "prospect_candidates": len(prospect_candidates),
            "converted_public_candidates": sum(1 for item in prospect_candidates if item.status == "converted"),
            "confirmed_real_inbound_leads": len(real_inbound_leads),
            "followups": len(followups),
            "analytics_reports": len(reports),
            "tool_audit_logs": len(tool_runs),
        },
        "public_prospects": [
            {
                "customer_name": lead.customer_name,
                "industry": lead.industry,
                "source_platform": lead.source_platform,
                "contact": lead.contact,
                "classification": classify_lead_source(lead.source_platform),
            }
            for lead in public_leads
        ],
        "prospect_source_pipeline": [
            {
                "platform": item.platform,
                "query": item.query,
                "status": item.status,
                "search_url": item.search_url,
            }
            for item in prospect_searches
        ],
        "prospect_candidates": [
            {
                "customer_name": item.customer_name,
                "source_platform": item.source_platform,
                "industry": item.industry,
                "status": item.status,
                "converted_lead_id": item.converted_lead_id,
                "source_url": item.source_url,
            }
            for item in prospect_candidates
        ],
        "not_real_yet": [
            "Demand Radar 当前仍需要人工粘贴公开证据；系统不会绕过平台登录、验证码或风控自动抓取。",
            "Content Factory 当前内容是基于需求文本生成的草稿，不是已发布后验证过有咨询的数据。",
            "Publishing Center 当前大多是待审核/回填记录，没有真实浏览、收藏、咨询、成交回填。",
            "Analytics 周报缺少真实发布表现和成交数据，不能用于判断渠道优劣。",
            "Agent Tool Audit 只有实际运行 Agent 后才会出现日志。",
            "系统没有自动联系客户能力；外部触达必须人工确认和人工发送。",
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
