from __future__ import annotations

import uuid
from urllib.parse import quote, quote_plus

from backend.internal_growth.models import Lead, ProspectCandidate, ProspectSearch, ProspectSearchCreate, now_iso


PLATFORM_LABELS = {
    "baidu": "百度",
    "douyin": "抖音",
    "xianyu": "闲鱼",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
    "website": "官网/公开网页",
    "manual_public": "手动公开来源",
}


def clean_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        term = value.strip()
        if term and term not in seen:
            cleaned.append(term)
            seen.add(term)
    return cleaned


def build_query(payload: ProspectSearchCreate) -> str:
    base_terms = clean_terms(
        [
            payload.city,
            payload.industry,
            *payload.keywords,
            *payload.pain_keywords,
        ]
    )
    if not base_terms:
        base_terms = ["获客", "客户咨询", "内容运营", "CRM跟进"]
    query = " ".join(base_terms)
    exclusions = clean_terms(payload.excluded_keywords)
    if exclusions and payload.platform in {"baidu", "website"}:
        query = f"{query} " + " ".join(f"-{item}" for item in exclusions)
    return query


def build_search_url(platform: str, query: str) -> str:
    if platform == "baidu":
        return f"https://www.baidu.com/s?wd={quote_plus(query)}"
    if platform == "douyin":
        return f"https://www.douyin.com/search/{quote(query)}?type=general"
    if platform == "xianyu":
        return f"https://www.goofish.com/search?q={quote_plus(query)}"
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={quote_plus(query)}"
    if platform == "kuaishou":
        return f"https://www.kuaishou.com/search/video?searchKey={quote_plus(query)}"
    if platform == "website":
        return f"https://www.baidu.com/s?wd={quote_plus(query + ' 官网 联系方式')}"
    return ""


def build_collection_steps(platform: str) -> list[str]:
    label = PLATFORM_LABELS.get(platform, "公开平台")
    return [
        f"打开{label}搜索链接，优先看公开主页、作品、商品、评论区里的业务需求信号。",
        "只记录公开可见的公司/店铺/账号名、公开链接、需求证据和人工可验证的联系方式。",
        "不要绕过登录、验证码、反爬或平台风控，不采集私密聊天和个人敏感信息。",
        "把候选客户粘贴到系统后，再由人确认是否转入 CRM 并人工触达。",
    ]


def create_prospect_search(payload: ProspectSearchCreate) -> ProspectSearch:
    query = build_query(payload)
    return ProspectSearch(
        id=str(uuid.uuid4()),
        **payload.model_dump(),
        query=query,
        search_url=build_search_url(payload.platform, query),
        collection_steps=build_collection_steps(payload.platform),
    )


def convert_candidate_to_lead(candidate: ProspectCandidate) -> Lead:
    platform_label = PLATFORM_LABELS.get(candidate.source_platform, candidate.source_platform)
    evidence = candidate.public_evidence.strip()
    source_line = f"公开来源：{platform_label}"
    if candidate.source_url:
        source_line = f"{source_line} {candidate.source_url}"
    fit = f"\n匹配原因：{candidate.fit_reason}" if candidate.fit_reason else ""
    demand = f"{candidate.demand_signal}\n{source_line}\n证据：{evidence}{fit}"
    return Lead(
        id=str(uuid.uuid4()),
        customer_name=candidate.customer_name,
        source_platform=f"{candidate.source_platform}_public",
        industry=candidate.industry,
        demand=demand,
        contact=candidate.contact or "待人工核实公开联系方式",
        intent_level=candidate.intent_level,
        stage="new",
        next_action="人工核实公开来源后，准备一条定制触达建议；不要自动发送。",
        updated_at=now_iso(),
    )
