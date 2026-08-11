from __future__ import annotations

import uuid
from typing import Any

from backend.internal_growth.models import (
    ContentTask,
    DemandSignal,
    PublishingRecord,
)
from backend.internal_growth.scoring import score_demand
from backend.internal_growth.store import InternalGrowthStore, store as default_store


OPEN_SOURCE_STACK: list[dict[str, Any]] = [
    {
        "name": "social-auto-upload",
        "repo": "dreammis/social-auto-upload",
        "url": "https://github.com/dreammis/social-auto-upload",
        "use_for": "抖音、小红书、视频号、Bilibili 等多平台视频上传",
        "adoption": "P0",
        "risk": "平台登录、验证码和最终发布必须人工确认；先接草稿/半自动上传。",
        "fit": "补齐当前抖音发布自动化最明显的短板。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "Automa",
        "repo": "AutomaApp/automa",
        "url": "https://github.com/AutomaApp/automa",
        "use_for": "浏览器可视化自动化，把重复网页操作沉淀成可审计流程",
        "adoption": "P0",
        "risk": "只用于打开页面、填草稿、导出证据，不用于无人值守外发。",
        "fit": "适合把抖音/闲鱼/后台操作做成 Record/Replay 辅助流程。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "LangGraph",
        "repo": "langchain-ai/langgraph",
        "url": "https://github.com/langchain-ai/langgraph",
        "use_for": "代码级 Agent 状态机、可恢复流程、工具调用编排",
        "adoption": "P1",
        "risk": "引入前先稳定现有工具边界，避免一开始重构过大。",
        "fit": "适合把 Market/Content/Publish/Lead/Sales/Review 串成真正 Agent。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "n8n",
        "repo": "n8n-io/n8n",
        "url": "https://github.com/n8n-io/n8n",
        "use_for": "外部 SaaS、表单、通知、报表等工作流编排",
        "adoption": "P1",
        "risk": "不要一开始替换现有 Python 主流程；先做外围通知和数据同步。",
        "fit": "适合把每天发布回填、飞书/企微提醒、表单同步自动化。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "Dify",
        "repo": "langgenius/dify",
        "url": "https://github.com/langgenius/dify",
        "use_for": "低代码 Agent、RAG、工具编排和企业 demo",
        "adoption": "P1",
        "risk": "生产主链路先不迁移；可用来给客户演示企业 AI 工作流。",
        "fit": "适合快速做企业客户 demo 和知识库问答。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "RAGFlow",
        "repo": "infiniflow/ragflow",
        "url": "https://github.com/infiniflow/ragflow",
        "use_for": "企业知识库、峰会资料库、客户案例库",
        "adoption": "P2",
        "risk": "先用轻量文档库验证需求，再接完整 RAG 引擎。",
        "fit": "适合把峰会资料、客户 SOP 和案例变成 Agent 可检索知识。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "Chatwoot",
        "repo": "chatwoot/chatwoot",
        "url": "https://github.com/chatwoot/chatwoot",
        "use_for": "统一客服收件箱、多渠道客户支持",
        "adoption": "P2",
        "risk": "咨询量没起来前不必引入完整客服台。",
        "fit": "后续私信、表单、网页客服增多后可作为统一收件箱参考。",
        "last_checked": "2026-07-31",
    },
    {
        "name": "XianyuAutoAgent",
        "repo": "shaxiu/XianyuAutoAgent",
        "url": "https://github.com/shaxiu/XianyuAutoAgent",
        "use_for": "闲鱼 AI 客服 Agent 架构参考",
        "adoption": "P2-reference",
        "risk": "不直接开启 7x24 自动值守；只参考会话记忆、后台和候选回复。",
        "fit": "可参考闲鱼服务咨询承接，但外发必须人工确认。",
        "last_checked": "2026-07-31",
    },
]


def _clean_list(values: list[Any], fallback: list[str]) -> list[str]:
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    return cleaned or fallback


def _save_tasks_with_review_records(
    growth_store: InternalGrowthStore,
    tasks: list[ContentTask],
    note: str,
) -> tuple[list[ContentTask], list[PublishingRecord]]:
    saved_tasks = growth_store.save_content_tasks(tasks)
    records: list[PublishingRecord] = []
    existing = {(item.content_task_id, item.platform) for item in growth_store.list_publishing_records()}
    for task in saved_tasks:
        if (task.id, task.platform) in existing:
            continue
        records.append(
            growth_store.save_publishing_record(
                PublishingRecord(
                    id=str(uuid.uuid4()),
                    content_task_id=task.id,
                    platform=task.platform,
                    status="review",
                    notes=note,
                )
            )
        )
    return saved_tasks, records


def generate_summit_content_pack(
    payload: dict[str, Any],
    growth_store: InternalGrowthStore | None = None,
) -> dict[str, Any]:
    active_store = growth_store or default_store
    topic = str(payload.get("topic") or "AI企业SOP").strip()
    angle = str(payload.get("angle") or "企业不是缺AI工具，而是缺能跑起来的AI SOP。").strip()
    source_files = _clean_list(payload.get("source_files") if isinstance(payload.get("source_files"), list) else [], ["峰会内容/_contact_sheet.jpg"])
    target_customer = str(payload.get("target_customer") or "想用AI降低人工成本、提升客服和销售效率的中小企业老板").strip()

    demand = active_store.save_demand(
        DemandSignal(
            id=str(uuid.uuid4()),
            name=f"峰会观察：{topic}",
            source_type="public",
            source_detail="峰会内容照片与本地项目 SOP 复盘",
            industry="企业AI / 中小企业服务",
            keywords=["AI企业应用", "Agent", "SOP", "CRM", "知识库", "自动化工作流"],
            pain_points=f"{target_customer}需要把AI从单点工具变成可落地流程：客服、知识库、CRM、内容获客和自动化跟进必须串起来。",
            raw_text=f"峰会观点：{angle}\n素材：{'; '.join(source_files)}",
            buying_possibility=72,
            recommended_action="先生成抖音内容和闲鱼服务草稿，发布后回填咨询数据。",
        )
    )
    opportunity = active_store.save_opportunity(score_demand(demand))

    douyin_payload = {
        "title": f"参加完AI峰会，我更确定：{topic}",
        "script_15s": (
            "参加完这场AI企业峰会，我更确定一件事：企业不是缺AI工具，"
            "企业缺的是能跑起来的AI SOP。客服、知识库、CRM和跟进流程必须连在一起。"
        ),
        "script_30s": (
            f"我参加完这场AI企业峰会，最大的感受是：{angle}"
            "老板真正关心的不是模型有多强，而是能不能少招人、能不能更快接住客户咨询、能不能把成交流程复制。"
            "所以我现在做的不是一个单点工具，而是一套企业AI运营Agent：AI客服、知识库、CRM、自动化工作流和内容获客放在同一个流程里。"
            "如果你也想先从一个业务流程试点，可以私信我发Agent。"
        ),
        "script_60s": (
            "这次峰会给我一个很强的信号：AI创业不能只讲工具，要讲企业结果。"
            f"围绕「{topic}」，中小企业最需要的是把分散经验变成SOP，再让Agent按流程执行。"
            "第一步，整理常见咨询、产品资料和成交话术，做成知识库。"
            "第二步，把AI客服、CRM线索、跟进任务和日报复盘接起来。"
            "第三步，用抖音、闲鱼和朋友圈测试真实咨询，再根据数据调整交付。"
            "这才是一个人做企业AI服务的现实路径：先做试点，再做可复制系统。"
        ),
        "storyboard": [
            "峰会PPT照片：AI企业应用、Agent+SOP关键词",
            "电脑前展示本地 Internal Growth OS / CRM / 内容草稿",
            "黑色玻璃UI展示 AI客服、知识库、CRM、自动化工作流",
            "结尾城市/办公桌镜头，引导私信 Agent",
        ],
        "subtitles": ["企业不是缺AI工具", "企业缺能跑起来的AI SOP", "先试点，再复制"],
        "cover_copy": "企业真正愿意为AI付费的地方",
        "source_files": source_files,
        "cta": "私信：Agent",
    }
    xianyu_payload = {
        "product_title": "企业AI客服/知识库/CRM流程诊断 可做试点方案",
        "product_description": (
            "适合：客服咨询多、回复慢、客户跟进容易断、想先低成本测试AI降本提效的中小企业。\n"
            f"核心观点：{angle}\n"
            "交付：业务流程诊断、知识库整理、AI客服候选回复、CRM跟进流程、自动化工作流建议。\n"
            "说明：先人工沟通需求，不承诺无人值守全自动成交。"
        ),
        "main_image_copy": "不是卖AI工具，是帮你把客服和销售流程做成AI SOP",
        "detail_image_copy": [
            "1. 梳理客服/销售重复问题",
            "2. 整理知识库和标准回复",
            "3. 接CRM跟进和复盘指标",
            "4. 先试点，再决定是否系统化",
        ],
        "source_files": source_files,
    }
    moments_payload = {
        "case_post": (
            f"参加完峰会后，我对「{topic}」更确定了。\n\n"
            "企业AI落地不是买一个工具，而是把客服、销售、内容、跟进和复盘做成能执行的SOP。"
            "我准备先用抖音和闲鱼测试这个需求，有咨询就进入CRM跟进，没有数据就换角度。"
        ),
        "sales_copy": "如果你也想把企业重复流程交给AI，可以先发一个业务场景，我帮你判断适不适合做试点。",
    }
    tasks = [
        ContentTask(
            id=str(uuid.uuid4()),
            demand_id=demand.id,
            opportunity_id=opportunity.id,
            platform="douyin",
            status="review",
            title=str(douyin_payload["title"]),
            payload=douyin_payload,
            review_note="峰会内容包自动生成；发布前人工审核事实和承诺边界。",
        ),
        ContentTask(
            id=str(uuid.uuid4()),
            demand_id=demand.id,
            opportunity_id=opportunity.id,
            platform="xianyu",
            status="review",
            title=str(xianyu_payload["product_title"]),
            payload=xianyu_payload,
            review_note="闲鱼服务草稿；发布、改价、交易动作必须人工确认。",
        ),
        ContentTask(
            id=str(uuid.uuid4()),
            demand_id=demand.id,
            opportunity_id=opportunity.id,
            platform="wechat_moments",
            status="review",
            title=f"峰会复盘：{topic}",
            payload=moments_payload,
            review_note="朋友圈内容草稿；发布前人工确认。",
        ),
    ]
    saved_tasks, records = _save_tasks_with_review_records(
        active_store,
        tasks,
        "Created by summit content pack. Human confirmation required before publishing.",
    )
    return {
        "demand_id": demand.id,
        "opportunity_id": opportunity.id,
        "content_task_ids": [item.id for item in saved_tasks],
        "publishing_record_ids": [item.id for item in records],
        "douyin_title": douyin_payload["title"],
        "douyin_script_30s": douyin_payload["script_30s"],
        "xianyu_product_title": xianyu_payload["product_title"],
        "guardrail": "只生成内容和发布审核记录；不会自动发布、私信或交易。",
    }


def create_xianyu_service_draft(
    payload: dict[str, Any],
    growth_store: InternalGrowthStore | None = None,
) -> dict[str, Any]:
    active_store = growth_store or default_store
    service_name = str(payload.get("service_name") or "企业AI客服/知识库/CRM流程诊断").strip()
    target_customer = str(payload.get("target_customer") or "中小企业老板、本地生活商家、电商卖家").strip()
    pain_points = str(payload.get("pain_points") or "客服回复慢、客户跟进断、内容获客不稳定、重复流程靠人工").strip()
    deliverables = _clean_list(
        payload.get("deliverables") if isinstance(payload.get("deliverables"), list) else [],
        ["业务流程诊断", "知识库整理", "AI客服候选回复", "CRM跟进流程", "自动化工作流建议"],
    )
    price_anchor = str(payload.get("price_anchor") or "先做低成本诊断，确认需求后再报价试点").strip()

    demand = active_store.save_demand(
        DemandSignal(
            id=str(uuid.uuid4()),
            name=f"闲鱼服务草稿：{service_name}",
            source_type="manual",
            source_detail="Agent 生成闲鱼服务商品草稿",
            industry="企业AI服务 / 获客自动化",
            keywords=["闲鱼服务", "AI客服", "知识库", "CRM", "企业AI试点"],
            pain_points=pain_points,
            raw_text=f"目标客户：{target_customer}\n交付：{'; '.join(deliverables)}\n价格锚点：{price_anchor}",
            buying_possibility=66,
            recommended_action="生成服务商品草稿后，人工审核再发布到闲鱼。",
        )
    )
    opportunity = active_store.save_opportunity(score_demand(demand))
    detail_lines = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(deliverables))
    xianyu_payload = {
        "product_title": service_name[:60],
        "product_description": (
            f"适合对象：{target_customer}\n"
            f"常见问题：{pain_points}\n\n"
            f"交付内容：\n{detail_lines}\n\n"
            f"费用说明：{price_anchor}\n"
            "服务边界：先人工沟通需求，不承诺无人值守全自动成交；发布、付款、交易动作都由你本人确认。"
        ),
        "main_image_copy": "把重复客服和客户跟进流程，整理成一套AI SOP",
        "detail_image_copy": [
            "先诊断业务流程",
            "再整理知识库和话术",
            "最后接CRM跟进与复盘",
        ],
        "target_customer": target_customer,
        "price_anchor": price_anchor,
    }
    task = ContentTask(
        id=str(uuid.uuid4()),
        demand_id=demand.id,
        opportunity_id=opportunity.id,
        platform="xianyu",
        status="review",
        title=str(xianyu_payload["product_title"]),
        payload=xianyu_payload,
        review_note="闲鱼服务商品草稿；最终发布、交易和客服外发都需要人工确认。",
    )
    saved_tasks, records = _save_tasks_with_review_records(
        active_store,
        [task],
        "Created by Xianyu service draft tool. Human confirmation required before publishing.",
    )
    return {
        "demand_id": demand.id,
        "content_task_id": saved_tasks[0].id,
        "publishing_record_id": records[0].id if records else "",
        "product_title": xianyu_payload["product_title"],
        "product_description": xianyu_payload["product_description"],
        "guardrail": "只生成闲鱼服务草稿和审核记录；不会自动发布、自动回复或自动交易。",
    }


def recommend_open_source_stack(payload: dict[str, Any]) -> dict[str, Any]:
    goal = str(payload.get("goal") or "一人AI获客运营Agent").strip()
    matched = OPEN_SOURCE_STACK
    if "闲鱼" in goal or "咸鱼" in goal:
        matched = [item for item in OPEN_SOURCE_STACK if item["adoption"].startswith("P0") or "Xianyu" in item["name"] or "闲鱼" in item["use_for"]]
    elif "发布" in goal or "抖音" in goal or "视频" in goal:
        matched = [item for item in OPEN_SOURCE_STACK if item["name"] in {"social-auto-upload", "Automa", "LangGraph", "n8n"}]
    elif "知识库" in goal or "客服" in goal:
        matched = [item for item in OPEN_SOURCE_STACK if item["name"] in {"Dify", "RAGFlow", "Chatwoot", "LangGraph", "n8n"}]

    return {
        "goal": goal,
        "recommendation": [
            {
                "name": item["name"],
                "repo": item["repo"],
                "url": item["url"],
                "adoption": item["adoption"],
                "use_for": item["use_for"],
                "risk": item["risk"],
                "fit": item["fit"],
            }
            for item in matched
        ],
        "adoption_order": ["social-auto-upload", "Automa", "LangGraph", "n8n/Dify", "RAGFlow/Chatwoot"],
        "guardrail": "核心流程留在本项目；开源项目优先作为执行器、知识库或后台参考接入，所有外发和发布动作人工确认。",
    }
