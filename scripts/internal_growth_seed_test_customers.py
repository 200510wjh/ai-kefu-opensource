from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.models import CustomerInteraction, DemandSignal, FollowUpTask, Lead
from backend.internal_growth.scoring import score_demand
from backend.internal_growth.store import store
from backend.internal_growth.workflows import run_daily_growth_workflow


SEEDS = [
    {
        "name": "本地生活商家需要稳定获取咨询客户",
        "source_type": "manual",
        "source_detail": "Internal Growth OS 测试种子",
        "industry": "本地生活 / 门店服务",
        "keywords": ["抖音获客", "闲鱼咨询", "门店引流", "客户跟进", "报价"],
        "pain_points": "很多本地商家每天不知道发什么内容，发了也没人咨询；有人问价后没有及时跟进，客户流失。希望今天就能测试一套低成本内容获客和CRM跟进流程。",
        "raw_text": "客户常说：我想要今天就有人咨询，但不会写脚本，也没时间整理客户。",
        "buying_possibility": 76,
    },
    {
        "name": "个人创业者想用AI减少找需求和发内容时间",
        "source_type": "manual",
        "source_detail": "Internal Growth OS 测试种子",
        "industry": "个人创业 / AI服务",
        "keywords": ["AI获客", "需求雷达", "内容工厂", "销售跟进", "预算"],
        "pain_points": "个人创业者每天花大量时间找需求、写内容、筛客户，缺少一个能把需求发现、内容生成、线索跟进串起来的内部系统。购买意愿强，但需要看到实际结果。",
        "raw_text": "客户常说：我不是不想做销售，是每天不知道该找谁、说什么、怎么跟进。",
        "buying_possibility": 72,
    },
    {
        "name": "咨询服务需要高意向客户筛选",
        "source_type": "manual",
        "source_detail": "Internal Growth OS 测试种子",
        "industry": "咨询 / 培训 / 知识付费",
        "keywords": ["高意向客户", "销售助手", "聊天分析", "成交概率", "咨询"],
        "pain_points": "咨询类服务收到很多私信，但无法快速判断谁是真需求、谁只是白嫖信息；缺少结合聊天记录的购买概率和下一步回复建议。",
        "raw_text": "客户常说：每天有人问，但我分不清哪个值得花时间聊。",
        "buying_possibility": 70,
    },
]


def reset_test_data() -> None:
    for path in [
        store.demands_path,
        store.opportunities_path,
        store.content_tasks_path,
        store.publishing_records_path,
        store.leads_path,
        store.interactions_path,
        store.follow_up_tasks_path,
        store.sales_analyses_path,
        store.analytics_reports_path,
    ]:
        path.write_text("[]\n", encoding="utf-8")


def seed_demands() -> list[tuple[DemandSignal, int, str]]:
    results = []
    for seed in SEEDS:
        payload = dict(seed)
        buying = int(payload.pop("buying_possibility"))
        demand = DemandSignal(
            id=str(uuid.uuid4()),
            **payload,
            buying_possibility=buying,
            recommended_action="先做机会评分，再生成一组低成本内容测试。",
        )
        store.save_demand(demand)
        score = store.save_opportunity(score_demand(demand))
        results.append((demand, score.total_score, score.recommended_decision))
    return results


def seed_test_lead() -> Lead:
    lead = Lead(
        id=str(uuid.uuid4()),
        customer_name="测试客户：王老板本地服务门店",
        source_platform="xianyu",
        industry="本地生活 / 门店服务",
        demand="想知道能不能今天先做一条抖音脚本和一个闲鱼商品页，看看有没有咨询。关心价格、交付周期和后续怎么跟进客户。",
        contact="待人工确认",
        intent_level="high",
        stage="need_confirmed",
        next_followup_at="",
        next_action="确认行业细分、现有获客渠道、预算区间，并给一版低成本测试方案。",
    )
    store.save_lead(lead)
    store.save_interaction(
        CustomerInteraction(
            id=str(uuid.uuid4()),
            lead_id=lead.id,
            channel="manual-test",
            direction="inbound",
            content="我有个本地门店，最近想试试抖音和闲鱼获客。你这边能不能今天给个方案？大概多少钱，能看到什么效果？",
            ai_summary="高意向咨询，关注方案、价格和效果验证。",
        )
    )
    store.save_follow_up_task(
        FollowUpTask(
            id=str(uuid.uuid4()),
            lead_id=lead.id,
            title=lead.next_action,
            due_at=lead.next_followup_at,
            priority="high",
        )
    )
    return lead


def main() -> int:
    reset_test_data()
    created = seed_demands()
    lead = seed_test_lead()
    run = run_daily_growth_workflow("manual")
    payload = {
        "demands": [{"name": demand.name, "score": score, "decision": decision} for demand, score, decision in created],
        "lead": {"customer_name": lead.customer_name, "intent_level": lead.intent_level, "stage": lead.stage},
        "workflow": run.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
