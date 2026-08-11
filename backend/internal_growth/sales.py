from __future__ import annotations

import uuid

from backend.internal_growth.models import SalesAnalysis, SalesAnalyzeRequest
from backend.platform.ai_engine import default_ai_engine


RISK_TERMS = {
    "price_commitment": ["保证", "包成交", "最低价", "一定赚钱"],
    "privacy": ["手机号", "微信号", "身份证", "隐私", "通讯录"],
    "platform_risk": ["自动私信", "自动发布", "批量采集", "刷量"],
}


def detect_risks(text: str) -> list[str]:
    lowered = text.lower()
    return [label for label, terms in RISK_TERMS.items() if any(term.lower() in lowered for term in terms)]


def fallback_sales_analysis(payload: SalesAnalyzeRequest) -> SalesAnalysis:
    text = payload.conversation
    probability = 42
    if any(term in text for term in ["价格", "报价", "多少钱", "合作", "方案"]):
        probability += 18
    if any(term in text for term in ["今天", "马上", "本周", "急"]):
        probability += 12
    if any(term in text for term in ["案例", "效果", "怎么做", "能不能"]):
        probability += 10
    probability = min(probability, 92)
    industry = payload.industry or "客户所在行业待确认"
    name = payload.customer_name or "客户"
    return SalesAnalysis(
        id=str(uuid.uuid4()),
        lead_id=payload.lead_id or "",
        customer_profile=f"{name}，行业：{industry}。当前更关注能否解决获客、内容测试和后续跟进效率问题。",
        real_need="客户需要看到具体痛点、可执行方案和实际结果，而不是泛泛了解AI能力。",
        purchase_probability=probability,
        next_strategy="先确认行业、现有获客方式、最近咨询量和预算区间，再给一个低成本测试方案。",
        reply_suggestion=(
            "我先不直接给你推大方案。你把行业、现在主要获客渠道、最近一周有没有咨询发我，"
            "我先判断这个需求值不值得做一轮内容测试，再给你具体脚本和跟进动作。"
        ),
        risk_flags=detect_risks(text),
    )


def analyze_sales_conversation(payload: SalesAnalyzeRequest) -> SalesAnalysis:
    engine = default_ai_engine()
    if not engine.is_chat_configured():
        return fallback_sales_analysis(payload)
    try:
        parsed = engine.complete_json(
            system_prompt=(
                "你是内部销售助手，只输出JSON。回复建议必须结合客户行业、历史聊天和产品方案。"
                "不能像普通机器人，不能承诺保证成交，不能建议无人值守自动发布。"
            ),
            user_prompt=(
                "输出字段：customer_profile, real_need, purchase_probability(0-100), "
                "next_strategy, reply_suggestion, risk_flags。\n"
                f"{payload.model_dump_json()}"
            ),
            temperature=0.45,
            timeout=45,
        )
        return SalesAnalysis(
            id=str(uuid.uuid4()),
            lead_id=payload.lead_id or "",
            customer_profile=str(parsed.get("customer_profile") or ""),
            real_need=str(parsed.get("real_need") or ""),
            purchase_probability=max(0, min(100, int(parsed.get("purchase_probability") or 50))),
            next_strategy=str(parsed.get("next_strategy") or ""),
            reply_suggestion=str(parsed.get("reply_suggestion") or ""),
            risk_flags=[str(item) for item in parsed.get("risk_flags") or []],
        )
    except Exception:
        return fallback_sales_analysis(payload)
