"""Lightweight workflow runtime used by the merchant growth backend.

The workflow layer stays generic on purpose. Product surfaces such as SOP
templates can wrap these definitions without changing CRM, desktop-agent, or
knowledge-base contracts.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowTriggerType = Literal["message", "lead", "schedule", "manual"]
WorkflowActionType = Literal[
    "read_message",
    "dedupe_message",
    "retrieve_knowledge",
    "generate_ai_reply",
    "decide_reply_action",
    "record_automation_log",
    "create_task",
    "score_intent",
    "risk_check",
    "notify_human",
    "generate_report",
    "run_local_script",
    "update_lead_stage",
]
WorkflowRunStatus = Literal["queued", "pending", "running", "success", "completed", "failed", "needs_human"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowCondition(BaseModel):
    field: str
    operator: Literal["eq", "contains", "gte", "lte", "exists"]
    value: Any | None = None


class WorkflowTrigger(BaseModel):
    type: WorkflowTriggerType
    source: str | None = None
    conditions: list[WorkflowCondition] = Field(default_factory=list)


class WorkflowAction(BaseModel):
    type: WorkflowActionType
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    requires_human_confirmation: bool = False


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    module: str
    description: str
    trigger: WorkflowTrigger
    actions: list[WorkflowAction]
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowRun(BaseModel):
    id: str
    workflow_id: str
    status: WorkflowRunStatus = "queued"
    trigger_type: WorkflowTriggerType | None = None
    trigger_source: str = ""
    trigger_payload: dict[str, Any] = Field(default_factory=dict)
    action_logs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class WorkflowEngine:
    def __init__(self) -> None:
        self.definitions: dict[str, WorkflowDefinition] = {}
        self.runs: dict[str, WorkflowRun] = {}

    def register(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        self.definitions[definition.id] = definition
        return definition

    def upsert_definition(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        return self.register(definition)

    def list_definitions(self) -> list[WorkflowDefinition]:
        return list(self.definitions.values())

    def get_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.definitions.get(workflow_id)

    def list_runs(self, workflow_id: str | None = None) -> list[WorkflowRun]:
        runs = list(self.runs.values())
        if workflow_id:
            runs = [run for run in runs if run.workflow_id == workflow_id]
        return sorted(runs, key=lambda run: run.created_at, reverse=True)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.runs.get(run_id)

    def create_run(
        self,
        workflow_id: str,
        payload: dict[str, Any] | None = None,
        status: WorkflowRunStatus = "queued",
        trigger_type: WorkflowTriggerType | None = None,
        trigger_source: str = "",
    ) -> WorkflowRun:
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=status,
            trigger_type=trigger_type,
            trigger_source=trigger_source,
            trigger_payload=payload or {},
        )
        self.runs[run.id] = run
        return run

    def trigger(
        self,
        trigger_type: WorkflowTriggerType,
        source: str,
        payload: dict[str, Any],
    ) -> list[WorkflowRun]:
        matched: list[WorkflowRun] = []
        for definition in self.definitions.values():
            if not definition.enabled or definition.trigger.type != trigger_type:
                continue
            if definition.trigger.source and definition.trigger.source != source:
                continue
            if not self.conditions_match(definition.trigger.conditions, payload):
                continue
            matched.append(self.start_run(definition, source, payload))
        return matched

    def start_run(
        self,
        definition: WorkflowDefinition,
        source: str,
        payload: dict[str, Any],
    ) -> WorkflowRun:
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=definition.id,
            trigger_type=definition.trigger.type,
            trigger_source=source,
            trigger_payload=payload,
            status="running",
        )
        self.runs[run.id] = run
        self.execute_definition(definition, run)
        return run

    def run_manual(self, workflow_id: str, payload: dict[str, Any] | None = None) -> WorkflowRun:
        definition = self.definitions.get(workflow_id)
        if not definition:
            raise KeyError(workflow_id)
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=definition.id,
            trigger_type="manual",
            trigger_source="operator",
            trigger_payload=payload or {},
            status="running",
        )
        self.runs[run.id] = run
        self.execute_definition(definition, run)
        return run

    def conditions_match(self, conditions: list[WorkflowCondition], payload: dict[str, Any]) -> bool:
        for condition in conditions:
            value = payload.get(condition.field)
            if condition.operator == "exists" and value is None:
                return False
            if condition.operator == "eq" and value != condition.value:
                return False
            if condition.operator == "contains" and str(condition.value) not in str(value):
                return False
            if condition.operator == "gte":
                try:
                    if float(value) < float(condition.value):
                        return False
                except (TypeError, ValueError):
                    return False
            if condition.operator == "lte":
                try:
                    if float(value) > float(condition.value):
                        return False
                except (TypeError, ValueError):
                    return False
        return True

    def execute_definition(self, definition: WorkflowDefinition, run: WorkflowRun) -> None:
        try:
            for action in definition.actions:
                started = time.perf_counter()
                try:
                    result = self.execute_action(action, run.trigger_payload)
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    status = "needs_human" if result.get("needs_human") else "success"
                    if result.get("decision") == "skip_duplicate":
                        status = "skipped"
                    self.append_log(
                        run,
                        f"Action {action.name} completed",
                        {
                            "type": action.type,
                            "step_name": action.name,
                            "duration_ms": duration_ms,
                            "status": status,
                            **result,
                        },
                    )
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    self.append_log(
                        run,
                        f"Action {action.name} failed",
                        {
                            "type": action.type,
                            "step_name": action.name,
                            "duration_ms": duration_ms,
                            "status": "failed",
                            "error": str(exc),
                        },
                        status="failed",
                    )
                    return
            if run.status == "running":
                run.status = "success"
            run.updated_at = utc_now()
        except Exception as exc:  # defensive fallback for unknown runtime errors
            self.append_log(run, "Workflow failed", {"error": str(exc)}, status="failed")

    def execute_action(self, action: WorkflowAction, payload: dict[str, Any]) -> dict[str, Any]:
        if action.type == "read_message":
            return {
                "message": payload.get("message") or payload.get("content"),
                "session_id": payload.get("session_id"),
            }
        if action.type == "dedupe_message":
            return {
                "message_hash": payload.get("message_hash"),
                "dedupe_key": payload.get("event_id") or payload.get("message_hash"),
                "decision": "accepted",
            }
        if action.type == "retrieve_knowledge":
            references = payload.get("knowledge_citations") or payload.get("citations") or []
            knowledge_chars = int(payload.get("knowledge_chars") or 0)
            return {
                "references": references,
                "knowledge_chars": knowledge_chars,
                "has_reference": bool(references) or knowledge_chars > 0,
            }
        if action.type == "generate_ai_reply":
            return {
                "reply": payload.get("reply_text") or payload.get("recommended_reply"),
                "model": payload.get("model") or payload.get("ai_model"),
                "confidence": payload.get("confidence") or payload.get("reply_confidence"),
            }
        if action.type == "decide_reply_action":
            action_value = payload.get("action") or payload.get("next_action") or "review"
            return {
                "decision": action_value,
                "should_reply": bool(payload.get("should_reply", action_value == "send")),
                "needs_human": action_value in {"handoff", "manual", "review"},
                "reason": payload.get("reason"),
            }
        if action.type == "risk_check":
            flags = payload.get("risk_flags") or detect_risk_flags(str(payload.get("message") or ""))
            return {"risk_flags": flags, "needs_human": bool(flags)}
        if action.type == "score_intent":
            return score_intent(str(payload.get("message") or ""), payload)
        if action.type == "notify_human":
            return {"notified": True, "reason": payload.get("reason") or "需要人工确认"}
        if action.type == "create_task":
            return {
                "task_title": payload.get("task_title") or "跟进高意向客户",
                "lead_id": payload.get("lead_id"),
                "due_at": payload.get("due_at"),
            }
        if action.type == "record_automation_log":
            return {
                "action_id": payload.get("action_id"),
                "session_id": payload.get("session_id"),
                "result": payload.get("send_result") or payload.get("result") or "recorded",
            }
        if action.type == "generate_report":
            return {
                "report_type": action.config.get("report_type", "daily"),
                "summary": payload.get("summary") or "待生成经营复盘",
            }
        if action.type == "run_local_script":
            return {
                "script": action.config.get("script"),
                "allowed": action.config.get("allowed", False),
            }
        if action.type == "update_lead_stage":
            return {
                "lead_id": payload.get("lead_id"),
                "stage": payload.get("stage") or action.config.get("stage"),
            }
        return {}

    def append_log(
        self,
        run: WorkflowRun | str,
        message: str,
        data: dict[str, Any] | None = None,
        status: WorkflowRunStatus | None = None,
    ) -> WorkflowRun:
        if isinstance(run, str):
            active_run = self.runs[run]
        else:
            active_run = run
        active_run.action_logs.append(
            {
                "time": utc_now().isoformat(),
                "message": message,
                "data": data or {},
            }
        )
        if status:
            active_run.status = status
        elif data and data.get("needs_human"):
            active_run.status = "needs_human"
        active_run.updated_at = utc_now()
        self.runs[active_run.id] = active_run
        return active_run


def detect_risk_flags(message: str) -> list[str]:
    categories = {
        "售后退款": ["退款", "退货", "售后", "换货", "不满意"],
        "投诉风险": ["投诉", "差评", "曝光", "骗子", "举报"],
        "付款承诺": ["付款", "打款", "转账", "保证", "承诺", "押金"],
        "隐私信息": ["身份证", "银行卡", "密码", "验证码"],
    }
    return [label for label, keywords in categories.items() if any(keyword in message for keyword in keywords)]


def score_intent(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    score = int(payload.get("intent_score") or 0)
    if score:
        return {"intent_score": score, "need_followup": score >= 70}

    keyword_groups = {
        "price": ["价格", "多少钱", "报价", "套餐", "费用", "预算"],
        "solution": ["案例", "演示", "试用", "效果", "怎么做", "方案"],
        "contact": ["微信", "电话", "联系", "预约", "加你", "咨询"],
        "urgent": ["今天", "马上", "尽快", "本周", "急"],
    }
    weights = {"price": 20, "solution": 25, "contact": 25, "urgent": 20}
    reasons: list[str] = []
    for group, keywords in keyword_groups.items():
        if any(keyword in message for keyword in keywords):
            score += weights[group]
            reasons.append(group)
    score = min(score, 100)
    return {"intent_score": score, "need_followup": score >= 70, "reasons": reasons}


workflow_engine = WorkflowEngine()


def default_workflow_definitions() -> list[WorkflowDefinition]:
    return [
        WorkflowDefinition(
            id="ai_customer_service_desktop_mvp",
            name="AI客服接待 SOP",
            module="AI客服",
            description="桌面客户端收到客户消息后，完成去重、知识库检索、AI回复、风控、发送决策和日志落库。",
            trigger=WorkflowTrigger(type="message", source="desktop_auto_reply"),
            actions=[
                WorkflowAction(type="read_message", name="读取客户消息"),
                WorkflowAction(type="dedupe_message", name="消息去重"),
                WorkflowAction(type="retrieve_knowledge", name="检索企业知识库"),
                WorkflowAction(type="generate_ai_reply", name="生成AI回复建议"),
                WorkflowAction(type="risk_check", name="风险与敏感内容检查"),
                WorkflowAction(type="decide_reply_action", name="判断自动发送或转人工"),
                WorkflowAction(type="record_automation_log", name="记录会话与发送日志"),
            ],
        ),
        WorkflowDefinition(
            id="message_high_intent_handoff",
            name="高意向客户跟进 SOP",
            module="CRM",
            description="客户出现价格、试用、预约、联系方式等高意向信号后，评分并创建跟进任务。",
            trigger=WorkflowTrigger(
                type="message",
                conditions=[WorkflowCondition(field="message", operator="exists")],
            ),
            actions=[
                WorkflowAction(type="score_intent", name="计算客户意向评分"),
                WorkflowAction(type="update_lead_stage", name="更新客户阶段", config={"stage": "高意向"}),
                WorkflowAction(type="create_task", name="创建销售跟进任务"),
                WorkflowAction(type="notify_human", name="通知人工客服"),
            ],
        ),
        WorkflowDefinition(
            id="lead_intake_next_step",
            name="新线索分配 SOP",
            module="CRM",
            description="新客户进入CRM后，补齐阶段、来源和下一步动作。",
            trigger=WorkflowTrigger(type="lead", source="lead_intake"),
            actions=[
                WorkflowAction(type="score_intent", name="计算线索意向"),
                WorkflowAction(type="create_task", name="生成首访任务"),
                WorkflowAction(type="record_automation_log", name="记录线索流转"),
            ],
        ),
        WorkflowDefinition(
            id="ai_brain_group_qa",
            name="AI大脑群聊问答 SOP",
            module="AI大脑",
            description="群聊或内部对话框提问后，完成知识库检索、AI生成、风控判断、回复建议和审计记录。",
            trigger=WorkflowTrigger(type="message", source="ai_brain_chat"),
            actions=[
                WorkflowAction(type="read_message", name="读取群聊问题"),
                WorkflowAction(type="retrieve_knowledge", name="检索知识库引用"),
                WorkflowAction(type="generate_ai_reply", name="生成AI大脑回复"),
                WorkflowAction(type="risk_check", name="识别敏感问题"),
                WorkflowAction(type="decide_reply_action", name="判断发送或人工确认"),
                WorkflowAction(type="record_automation_log", name="记录AI大脑审计日志"),
            ],
        ),
        WorkflowDefinition(
            id="daily_ops_report",
            name="客服每日复盘 SOP",
            module="数据分析",
            description="汇总当日咨询、AI回复、转人工和知识库无答案问题，给老板输出经营建议。",
            trigger=WorkflowTrigger(type="schedule", source="daily"),
            actions=[
                WorkflowAction(type="generate_report", name="生成日报", config={"report_type": "daily_ops"}),
                WorkflowAction(type="notify_human", name="推送给负责人"),
            ],
        ),
        WorkflowDefinition(
            id="knowledge_gap_maintenance",
            name="知识库维护 SOP",
            module="知识库",
            description="客户问题无引用或低置信度时，沉淀为知识库补充任务。",
            trigger=WorkflowTrigger(
                type="message",
                conditions=[WorkflowCondition(field="reason", operator="contains", value="知识库")],
            ),
            actions=[
                WorkflowAction(type="retrieve_knowledge", name="确认无命中引用"),
                WorkflowAction(type="create_task", name="创建知识库补充任务"),
                WorkflowAction(type="notify_human", name="提醒运营维护"),
            ],
        ),
    ]


for workflow_definition in default_workflow_definitions():
    workflow_engine.register(workflow_definition)
