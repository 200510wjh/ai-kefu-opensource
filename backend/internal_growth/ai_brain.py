from __future__ import annotations

import os
import re
import time
from typing import Any

from backend.customer_service_saas import knowledge_rows
from backend.internal_growth.models import (
    AIBrainChatRequest,
    AIBrainChatResponse,
    AIBrainProviderStatus,
)
from backend.platform.ai_engine import AIEngineConfig, default_ai_engine
from backend.platform.workflow import workflow_engine


CUSTOMER_FACING_CHANNELS = {"wechat_group", "douyin_group", "website_chat"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def ai_brain_providers() -> list[AIBrainProviderStatus]:
    default_base = _env("AI_BASE_URL", "https://api.openai.com/v1")
    default_model = _env("AI_MODEL")
    return [
        AIBrainProviderStatus(
            id="default",
            name="默认 AI Engine",
            kind="official",
            base_url=default_base,
            model=default_model,
            configured=bool((_env("AI_API_KEY") or _env("OPENAI_API_KEY")) and default_model),
            env_key="AI_API_KEY / OPENAI_API_KEY",
            cost_note="跟随当前后端 AI_ENGINE 配置，适合生产默认路由。",
            safety_note="密钥仅放后端环境变量，不进入前端页面。",
        ),
        AIBrainProviderStatus(
            id="deepseek",
            name="DeepSeek 官方兼容接口",
            kind="official",
            base_url=_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=_env("DEEPSEEK_MODEL", "deepseek-chat"),
            configured=bool(_env("DEEPSEEK_API_KEY")),
            env_key="DEEPSEEK_API_KEY",
            cost_note="适合优先做低成本文本客服与群聊问答。",
            safety_note="建议只在后端配置专用低权限 Key，并设置用量上限。",
        ),
        AIBrainProviderStatus(
            id="relay",
            name="OpenAI-compatible 中转站",
            kind="relay",
            base_url=_env("AI_RELAY_BASE_URL"),
            model=_env("AI_RELAY_MODEL"),
            configured=bool(_env("AI_RELAY_BASE_URL") and _env("AI_RELAY_API_KEY") and _env("AI_RELAY_MODEL")),
            env_key="AI_RELAY_API_KEY",
            cost_note="适合接入第三方聚合/中转；价格和稳定性由供应商决定。",
            safety_note="不要把主业务 Key 交给不可信中转，优先使用限额 Key。",
        ),
        AIBrainProviderStatus(
            id="openrouter",
            name="OpenRouter 兼容路由",
            kind="relay",
            base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=_env("OPENROUTER_MODEL"),
            configured=bool(_env("OPENROUTER_API_KEY") and _env("OPENROUTER_MODEL")),
            env_key="OPENROUTER_API_KEY",
            cost_note="适合统一试用多模型，实际成本按所选模型计费。",
            safety_note="生产前需要验证数据合规、可用性和账单上限。",
        ),
        AIBrainProviderStatus(
            id="siliconflow",
            name="硅基流动兼容路由",
            kind="relay",
            base_url=_env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            model=_env("SILICONFLOW_MODEL"),
            configured=bool(_env("SILICONFLOW_API_KEY") and _env("SILICONFLOW_MODEL")),
            env_key="SILICONFLOW_API_KEY",
            cost_note="适合国内网络环境下评估多模型成本。",
            safety_note="上线前单独做延迟、失败率、内容安全和合同审查。",
        ),
        AIBrainProviderStatus(
            id="self_hosted",
            name="自建 AI 中转网关",
            kind="self_hosted",
            base_url=_env("SELF_HOSTED_AI_BASE_URL"),
            model=_env("SELF_HOSTED_AI_MODEL"),
            configured=bool(_env("SELF_HOSTED_AI_BASE_URL") and _env("SELF_HOSTED_AI_API_KEY") and _env("SELF_HOSTED_AI_MODEL")),
            env_key="SELF_HOSTED_AI_API_KEY",
            cost_note="适合后期统一缓存、限流、审计、模型路由和成本控制。",
            safety_note="自建网关必须做密钥隔离、请求审计、限流和熔断。",
        ),
    ]


def provider_config(provider_id: str, temperature: float | None) -> tuple[AIBrainProviderStatus, AIEngineConfig]:
    providers = {provider.id: provider for provider in ai_brain_providers()}
    provider = providers.get(provider_id) or providers["default"]
    engine = default_ai_engine()
    if provider.id == "default":
        return provider, engine.chat_config(temperature=temperature, timeout=35)
    if provider.id == "deepseek":
        return provider, AIEngineConfig(
            provider="deepseek",
            api_key=_env("DEEPSEEK_API_KEY"),
            model=_env("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url=engine.normalize_base_url(_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")),
            temperature=temperature if temperature is not None else 0.45,
            timeout=float(_env("DEEPSEEK_TIMEOUT", "35")),
        )
    if provider.id == "openrouter":
        return provider, AIEngineConfig(
            provider="openrouter",
            api_key=_env("OPENROUTER_API_KEY"),
            model=_env("OPENROUTER_MODEL"),
            base_url=engine.normalize_base_url(_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")),
            temperature=temperature if temperature is not None else 0.45,
            timeout=float(_env("OPENROUTER_TIMEOUT", "35")),
        )
    if provider.id == "siliconflow":
        return provider, AIEngineConfig(
            provider="siliconflow",
            api_key=_env("SILICONFLOW_API_KEY"),
            model=_env("SILICONFLOW_MODEL"),
            base_url=engine.normalize_base_url(_env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")),
            temperature=temperature if temperature is not None else 0.45,
            timeout=float(_env("SILICONFLOW_TIMEOUT", "35")),
        )
    if provider.id == "self_hosted":
        return provider, AIEngineConfig(
            provider="self_hosted",
            api_key=_env("SELF_HOSTED_AI_API_KEY"),
            model=_env("SELF_HOSTED_AI_MODEL"),
            base_url=engine.normalize_base_url(_env("SELF_HOSTED_AI_BASE_URL")),
            temperature=temperature if temperature is not None else 0.45,
            timeout=float(_env("SELF_HOSTED_AI_TIMEOUT", "35")),
        )
    return provider, AIEngineConfig(
        provider="relay",
        api_key=_env("AI_RELAY_API_KEY"),
        model=_env("AI_RELAY_MODEL"),
        base_url=engine.normalize_base_url(_env("AI_RELAY_BASE_URL")),
        temperature=temperature if temperature is not None else 0.45,
        timeout=float(_env("AI_RELAY_TIMEOUT", "35")),
    )


def citation_terms(text: str) -> set[str]:
    lowered = text.lower()
    terms = set(re.findall(r"[a-zA-Z0-9_+\-.]{3,}", lowered))
    for token in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        terms.add(token)
        for index in range(0, max(0, len(token) - 1)):
            terms.add(token[index : index + 2])
    return {term for term in terms if len(term.strip()) >= 2}


def knowledge_citations(merchant_id: int | None, query: str, limit: int = 4) -> list[dict[str, Any]]:
    if not merchant_id:
        return []
    query_terms = citation_terms(query)
    if not query_terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in knowledge_rows(merchant_id, limit=100):
        title = str(row.get("title") or "")
        content = str(row.get("content") or "")
        row_terms = citation_terms(f"{title}\n{content}")
        score = len(query_terms.intersection(row_terms))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], int(item[1].get("id") or 0)), reverse=True)
    return [
        {
            "id": int(row.get("id") or 0),
            "title": str(row.get("title") or ""),
            "source_type": str(row.get("source_type") or ""),
            "snippet": str(row.get("content") or "")[:360],
            "match_score": score,
        }
        for score, row in scored[:limit]
    ]


def build_messages(payload: AIBrainChatRequest, citations: list[dict[str, Any]]) -> list[dict[str, str]]:
    citation_block = "\n".join(
        f"[{index}] {item.get('title')}: {item.get('snippet')}"
        for index, item in enumerate(citations, start=1)
    )
    channel_note = {
        "wechat_group": "当前场景是微信群。回答要短、自然、像企业客服，不要刷屏。",
        "douyin_group": "当前场景是抖音群/私域群。回答要克制，不诱导违规交易。",
        "website_chat": "当前场景是网页客服。回答要专业，并引导客户留下可跟进信息。",
        "direct": "当前场景是内部对话框。可以帮助老板、客服或运营分析问题。",
        "internal": "当前场景是内部运营。可以给出策略、SOP和排查建议。",
    }.get(payload.channel, "")
    system_prompt = (
        "你是企业AI大脑，负责客服问答、群聊答疑和运营建议。"
        "客户可见场景必须基于企业知识库回答，不确定时明确转人工，不能编造价格、政策、承诺和售后规则。"
        "遇到退款、投诉、付款、合同、隐私、承诺、违法敏感内容，必须建议人工确认。"
        f"\n{channel_note}\n"
        f"群名称：{payload.group_name or '无'}；提问人：{payload.member_name or '未知'}。\n"
        f"知识库引用：\n{citation_block or '未命中可引用知识库。'}"
    )
    history = [
        {"role": item.role, "content": f"{item.sender_name}: {item.content}" if item.sender_name else item.content}
        for item in payload.messages[-12:]
    ]
    return [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": payload.question}]


def fallback_answer(payload: AIBrainChatRequest, reason: str) -> str:
    if payload.channel in CUSTOMER_FACING_CHANNELS:
        return "这个问题需要人工客服确认，我帮您转接。"
    return f"AI接口暂时不可用：{reason}。你可以先配置后端环境变量里的 API Key、模型和 Base URL。"


def run_ai_brain_chat(payload: AIBrainChatRequest) -> AIBrainChatResponse:
    started = time.perf_counter()
    provider, config = provider_config(payload.provider_id, payload.temperature)
    engine = default_ai_engine()
    risk = engine.assess_risk(payload.question)
    citations = knowledge_citations(payload.merchant_id, payload.question) if payload.use_knowledge else []
    customer_facing = payload.channel in CUSTOMER_FACING_CHANNELS
    must_handoff = bool(risk.risk_flags) or (customer_facing and payload.use_knowledge and not citations)
    mode = "rule"
    answer = fallback_answer(payload, "未配置可用模型")

    if config.api_key and config.model and not must_handoff:
        try:
            result = engine.complete_chat_with_config(config, build_messages(payload, citations))
            answer = result.content
            mode = "ai"
        except Exception as exc:
            answer = fallback_answer(payload, str(exc))
    elif must_handoff:
        answer = fallback_answer(payload, "需要人工确认")

    suggested_action = "handoff" if must_handoff else "send" if payload.allow_auto_answer and customer_facing else "review"
    latency_ms = int((time.perf_counter() - started) * 1000)
    workflow_payload = {
        "message": payload.question,
        "source": "ai_brain",
        "platform": payload.channel,
        "group_name": payload.group_name,
        "customer_name": payload.member_name,
        "reply_text": answer,
        "action": suggested_action,
        "should_reply": suggested_action == "send",
        "reason": "risk_or_no_knowledge" if must_handoff else "ai_brain_reply",
        "risk_flags": risk.risk_flags,
        "knowledge_citations": citations,
        "knowledge_chars": sum(len(str(item.get("snippet") or "")) for item in citations),
        "model": config.model,
        "confidence": 0.86 if mode == "ai" and citations else 0.52 if mode == "ai" else 0.35,
    }
    runs = workflow_engine.trigger("message", "ai_brain_chat", workflow_payload)
    return AIBrainChatResponse(
        answer=answer,
        provider_id=provider.id,
        provider_name=provider.name,
        model=config.model,
        mode=mode,  # type: ignore[arg-type]
        channel=payload.channel,
        risk_flags=risk.risk_flags,
        need_human=must_handoff,
        citations=citations,
        latency_ms=latency_ms,
        sop_run_ids=[run.id for run in runs],
        suggested_action=suggested_action,  # type: ignore[arg-type]
    )
