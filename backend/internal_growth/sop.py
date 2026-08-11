from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.internal_growth.models import (
    CustomerInteraction,
    FollowUpTask,
    Lead,
    SOPMetrics,
    SOPRun,
    SOPStepRun,
    SOPStepTemplate,
    SOPTemplate,
)
from backend.platform.workflow import WorkflowDefinition, WorkflowEngine, WorkflowRun


ACTION_DESCRIPTIONS = {
    "read_message": "读取桌面 Connector 上报的客户消息、会话和窗口上下文。",
    "dedupe_message": "用 event_id 或 message_hash 判断同一条消息是否已经处理。",
    "retrieve_knowledge": "检索企业知识库，提取可引用资料，避免无依据回答。",
    "generate_ai_reply": "基于客户问题、企业话术和知识库引用生成回复建议。",
    "risk_check": "识别投诉、退款、付款、承诺、隐私等需要人工确认的风险。",
    "decide_reply_action": "根据风控、置信度、暂停状态和白名单判断自动发送或转人工。",
    "record_automation_log": "把会话、AI回复、发送结果和运行证据写入日志。",
    "score_intent": "根据咨询内容、价格意向、预约意愿等信号计算客户意向。",
    "update_lead_stage": "把客户阶段写回 CRM，沉淀为销售可跟进对象。",
    "create_task": "为人工客服、销售或运营生成下一步任务。",
    "notify_human": "触发人工接管或负责人提醒。",
    "generate_report": "汇总客服和经营数据，生成老板复盘建议。",
    "run_local_script": "运行被允许的本地脚本动作，并记录执行结果。",
}

DEFAULT_GUARDRAILS = [
    "无知识库引用或低置信度时转人工",
    "退款、投诉、付款、承诺、隐私信息必须转人工",
    "自动发送受全局暂停、会话暂停、白名单和人工接管控制",
    "同一 message_hash 只允许处理和回复一次",
    "窗口识别、OCR 或焦点异常时禁止盲目点击发送",
]

DEFAULT_LIMITS = [
    "连续消息合并后再生成一次回复",
    "单会话发送间隔不低于 3 秒",
    "异常回复、空回复或超长回复禁止自动发送",
    "每日自动回复上限由企业设置控制",
]


def _iso(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return value.isoformat()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _string_list(value: Any) -> list[str]:
    items = []
    for item in _as_list(value):
        if isinstance(item, dict):
            label = item.get("title") or item.get("source") or item.get("name") or item.get("id")
            if label:
                items.append(str(label))
        elif item:
            items.append(str(item))
    return items


def definition_to_template(definition: WorkflowDefinition) -> SOPTemplate:
    trigger = definition.trigger.type
    if definition.trigger.source:
        trigger = f"{trigger}:{definition.trigger.source}"
    elif definition.trigger.conditions:
        trigger = f"{trigger}:条件触发"

    return SOPTemplate(
        id=definition.id,
        name=definition.name,
        module=definition.module,
        description=definition.description,
        trigger=trigger,
        enabled=definition.enabled,
        steps=[
            SOPStepTemplate(
                id=f"{definition.id}:{index}:{action.type}",
                name=action.name,
                action_type=action.type,
                description=ACTION_DESCRIPTIONS.get(action.type, ""),
                requires_human_confirmation=action.requires_human_confirmation,
            )
            for index, action in enumerate(definition.actions, start=1)
        ],
        guardrails=DEFAULT_GUARDRAILS,
        frequency_limits=DEFAULT_LIMITS,
        updated_at=_iso(definition.created_at),
    )


def _step_evidence(action_type: str, output: dict[str, Any]) -> str:
    if action_type == "read_message":
        message = str(output.get("message") or "")
        return message[:80] if message else "已读取客户消息"
    if action_type == "dedupe_message":
        return f"去重键：{output.get('dedupe_key') or output.get('message_hash') or '未提供'}"
    if action_type == "retrieve_knowledge":
        refs = _string_list(output.get("references"))
        if refs:
            return "引用：" + "、".join(refs[:3])
        if output.get("has_reference"):
            return f"知识库命中 {output.get('knowledge_chars', 0)} 字"
        return "未命中可引用知识库"
    if action_type == "generate_ai_reply":
        reply = str(output.get("reply") or "")
        model = output.get("model")
        return f"{model or 'AI'}：{reply[:80]}" if reply else "已生成回复建议"
    if action_type == "risk_check":
        flags = _string_list(output.get("risk_flags"))
        return "风险：" + "、".join(flags) if flags else "未发现强制转人工风险"
    if action_type == "decide_reply_action":
        decision = output.get("decision") or "review"
        reason = output.get("reason")
        return f"决策：{decision}" + (f"，原因：{reason}" if reason else "")
    if action_type == "score_intent":
        return f"意向评分：{output.get('intent_score', 0)}"
    if action_type == "notify_human":
        return str(output.get("reason") or "已通知人工")
    if action_type == "record_automation_log":
        return f"日志结果：{output.get('result') or 'recorded'}"
    if action_type == "create_task":
        return str(output.get("task_title") or "已创建任务")
    return "步骤已执行"


def run_to_sop_run(run: WorkflowRun, definition: WorkflowDefinition | None = None) -> SOPRun:
    payload = run.trigger_payload or {}
    steps: list[SOPStepRun] = []

    for index, log in enumerate(run.action_logs, start=1):
        output = dict(log.get("data") or {})
        action_type = str(output.get("type") or "")
        step_name = str(output.get("step_name") or log.get("message") or f"步骤 {index}")
        if not action_type:
            continue
        status = str(output.get("status") or "success")
        if status not in {"success", "failed", "needs_human", "skipped", "running"}:
            status = "success"
        error = str(output.get("error") or "")
        steps.append(
            SOPStepRun(
                id=f"{run.id}:{index}",
                name=step_name,
                action_type=action_type,
                status=status,  # type: ignore[arg-type]
                duration_ms=int(output.get("duration_ms") or 0),
                evidence=_step_evidence(action_type, output),
                output=output,
                error=error,
                created_at=str(log.get("time") or _iso(run.created_at)),
            )
        )

    reply_meta = payload.get("reply_meta") if isinstance(payload.get("reply_meta"), dict) else {}
    citations = (
        _string_list(payload.get("knowledge_citations"))
        or _string_list(payload.get("citations"))
        or _string_list(reply_meta.get("citations") if reply_meta else [])
    )

    return SOPRun(
        id=run.id,
        template_id=run.workflow_id,
        template_name=definition.name if definition else run.workflow_id,
        status=run.status,
        source=run.trigger_source,
        platform=str(payload.get("platform") or payload.get("channel") or ""),
        session_id=str(payload.get("session_id") or payload.get("lead_id") or ""),
        customer_name=str(payload.get("customer_name") or payload.get("contact") or payload.get("window_title") or ""),
        message_hash=str(payload.get("message_hash") or payload.get("event_id") or ""),
        action=str(payload.get("action") or payload.get("next_action") or ""),
        intent_score=int(payload.get("intent_score") or 0),
        risk_flags=_string_list(payload.get("risk_flags")),
        knowledge_citations=citations,
        reply_text=str(payload.get("reply_text") or payload.get("recommended_reply") or ""),
        reason=str(payload.get("reason") or ""),
        steps=steps,
        started_at=_iso(run.created_at),
        updated_at=_iso(run.updated_at),
    )


def list_sop_templates(engine: WorkflowEngine) -> list[SOPTemplate]:
    return [definition_to_template(definition) for definition in engine.list_definitions()]


def list_sop_runs(engine: WorkflowEngine, workflow_id: str | None = None) -> list[SOPRun]:
    definitions = {definition.id: definition for definition in engine.list_definitions()}
    return [
        run_to_sop_run(run, definitions.get(run.workflow_id))
        for run in engine.list_runs(workflow_id)
    ]


def _is_today(iso_value: str) -> bool:
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.astimezone(timezone.utc).date() == datetime.now(timezone.utc).date()


def build_sop_metrics(
    runs: list[SOPRun],
    leads: list[Lead],
    followups: list[FollowUpTask],
    interactions: list[CustomerInteraction],
) -> SOPMetrics:
    today_runs = [run for run in runs if _is_today(run.started_at)]
    today_inbound = [
        item
        for item in interactions
        if item.direction == "inbound" and _is_today(item.created_at)
    ]
    consultations = max(len(today_inbound), sum(1 for run in today_runs if "message" in run.source or run.template_id.startswith("ai_customer")))

    auto_replies = sum(
        1
        for run in today_runs
        if run.action in {"send", "auto_send", "reply"}
        or any(step.action_type == "decide_reply_action" and step.output.get("should_reply") for step in run.steps)
    )
    handoff_count = sum(1 for run in today_runs if run.status == "needs_human" or run.risk_flags)
    durations = [step.duration_ms for run in today_runs for step in run.steps if step.duration_ms > 0]
    avg_response_ms = int(sum(durations) / len(durations)) if durations else 0
    high_intent_customers = sum(1 for lead in leads if lead.intent_level == "high" and lead.stage not in {"won", "lost"})
    pending_followups = sum(1 for task in followups if task.status == "open")
    conversion_customers = sum(1 for lead in leads if lead.stage == "won")
    auto_reply_rate = int(auto_replies * 100 / consultations) if consultations else 0
    saved_minutes = auto_replies * 3

    advice: list[str] = []
    if consultations == 0:
        advice.append("今天还没有真实客户咨询进入，先用白名单联系人完成一轮端到端验收。")
    if handoff_count:
        advice.append(f"今天有 {handoff_count} 次转人工，优先查看风险原因和知识库缺口。")
    if high_intent_customers:
        advice.append(f"当前有 {high_intent_customers} 个高意向客户，建议销售在当天完成跟进。")
    if auto_replies and auto_reply_rate < 70:
        advice.append("自动回复率偏低，建议检查知识库引用命中率和风控规则。")
    if not advice:
        advice.append("SOP运行平稳，继续关注高意向客户和未命中知识库问题。")

    return SOPMetrics(
        today_consultations=consultations,
        ai_auto_replies=auto_replies,
        saved_minutes=saved_minutes,
        high_intent_customers=high_intent_customers,
        pending_followups=pending_followups,
        handoff_count=handoff_count,
        auto_reply_rate=auto_reply_rate,
        avg_response_ms=avg_response_ms,
        conversion_customers=conversion_customers,
        sop_runs_today=len(today_runs),
        advice=advice,
        recent_runs=runs[:8],
    )
