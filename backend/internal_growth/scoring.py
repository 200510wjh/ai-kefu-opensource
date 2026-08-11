from __future__ import annotations

import uuid

from backend.internal_growth.models import DemandSignal, OpportunityScore


HIGH_INTENT_TERMS = [
    "价格",
    "报价",
    "预算",
    "成交",
    "马上",
    "今天",
    "本周",
    "方案",
    "案例",
    "能不能",
    "怎么做",
    "省时间",
    "获客",
    "咨询",
    "客户",
]
HIGH_VALUE_TERMS = [
    "企业",
    "团队",
    "老板",
    "门店",
    "批量",
    "私域",
    "CRM",
    "自动化",
    "代运营",
    "交付",
    "培训",
    "咨询",
]
DIFFICULT_TERMS = ["无人值守", "自动发布", "破解", "采集联系方式", "保证成交", "刷量", "违规"]


def clamp(value: int) -> int:
    return max(0, min(100, value))


def score_demand(demand: DemandSignal) -> OpportunityScore:
    text = " ".join([demand.name, demand.industry, demand.pain_points, demand.raw_text, " ".join(demand.keywords)])
    lowered = text.lower()

    strength = 44 + min(36, sum(6 for term in HIGH_INTENT_TERMS if term.lower() in lowered))
    deal_probability = 36 + min(36, demand.buying_possibility // 2) + (10 if demand.source_type in {"chat", "authorized_data"} else 0)
    average_order_value = 38 + min(36, sum(7 for term in HIGH_VALUE_TERMS if term.lower() in lowered))
    delivery_difficulty = 30 + min(42, sum(12 for term in DIFFICULT_TERMS if term.lower() in lowered))
    fit_score = 78 if any(term in text for term in ["获客", "内容", "线索", "CRM", "跟进", "成交", "销售"]) else 58
    total = round(strength * 0.28 + deal_probability * 0.24 + average_order_value * 0.18 + fit_score * 0.22 + (100 - delivery_difficulty) * 0.08)

    if total >= 78:
        decision = "优先测试：今天生成内容并进入人工审核。"
    elif total >= 62:
        decision = "小样本测试：先发一条低成本内容验证咨询量。"
    else:
        decision = "暂缓：先补充客户证据或降低交付复杂度。"

    reasoning = (
        f"需求强度{clamp(strength)}，成交概率{clamp(deal_probability)}，客单价潜力{clamp(average_order_value)}，"
        f"交付难度{clamp(delivery_difficulty)}，与内部获客系统匹配度{clamp(fit_score)}。"
    )
    return OpportunityScore(
        id=str(uuid.uuid4()),
        demand_id=demand.id,
        demand_strength=clamp(strength),
        deal_probability=clamp(deal_probability),
        average_order_value=clamp(average_order_value),
        delivery_difficulty=clamp(delivery_difficulty),
        fit_score=clamp(fit_score),
        total_score=clamp(total),
        reasoning=reasoning,
        recommended_decision=decision,
    )
