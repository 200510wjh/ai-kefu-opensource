from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowTriggerType = Literal["message", "lead", "schedule", "manual"]
WorkflowActionType = Literal[
    "create_task",
    "score_intent",
    "risk_check",
    "notify_human",
    "generate_report",
    "run_local_script",
    "update_lead_stage",
]
WorkflowRunStatus = Literal["queued", "running", "success", "failed", "needs_human"]


class WorkflowTrigger(BaseModel):
    type: WorkflowTriggerType
    source: str = ""
    payload_schema: dict[str, Any] = Field(default_factory=dict)


class WorkflowCondition(BaseModel):
    field: str
    operator: Literal["exists", "equals", "contains", "gte", "lte"] = "exists"
    value: Any = None


class WorkflowAction(BaseModel):
    type: WorkflowActionType
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    requires_human_confirmation: bool = False


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    module: str
    description: str = ""
    trigger: WorkflowTrigger
    conditions: list[WorkflowCondition] = Field(default_factory=list)
    actions: list[WorkflowAction] = Field(default_factory=list)
    enabled: bool = True


class WorkflowRun(BaseModel):
    id: str
    workflow_id: str
    status: WorkflowRunStatus = "queued"
    trigger_type: WorkflowTriggerType | None = None
    trigger_source: str = ""
    trigger_payload: dict[str, Any] = Field(default_factory=dict)
    action_logs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowEngine:
    """Single execution boundary for automation.

    Workflow is the shared automation layer for manual runs, message events,
    lead events, schedules, and existing local scripts. It is intentionally
    deterministic here; risky platform writes still stay behind existing
    guarded script endpoints or human confirmation.
    """

    def __init__(self) -> None:
        self.definitions: dict[str, WorkflowDefinition] = default_workflow_definitions()
        self.runs: dict[str, WorkflowRun] = {}

    def list_definitions(self) -> list[WorkflowDefinition]:
        return sorted(self.definitions.values(), key=lambda item: (item.module, item.id))

    def get_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.definitions.get(workflow_id)

    def upsert_definition(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        self.definitions[definition.id] = definition
        return definition

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
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self.runs[run.id] = run
        return run

    def append_log(self, run_id: str, message: str, data: dict[str, Any] | None = None, status: WorkflowRunStatus | None = None) -> WorkflowRun:
        run = self.runs[run_id]
        logs = [*run.action_logs, {"time": now_iso(), "message": message, "data": data or {}}]
        update = {"action_logs": logs, "updated_at": now_iso()}
        if status:
            update["status"] = status
        run = run.model_copy(update=update)
        self.runs[run_id] = run
        return run

    def list_runs(self) -> list[WorkflowRun]:
        return sorted(self.runs.values(), key=lambda item: item.created_at, reverse=True)

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self.runs.get(run_id)

    def match_definitions(self, trigger_type: WorkflowTriggerType, source: str, payload: dict[str, Any]) -> list[WorkflowDefinition]:
        matches: list[WorkflowDefinition] = []
        for definition in self.definitions.values():
            if not definition.enabled or definition.trigger.type != trigger_type:
                continue
            if definition.trigger.source and definition.trigger.source not in {"*", source}:
                continue
            if all(evaluate_condition(condition, payload) for condition in definition.conditions):
                matches.append(definition)
        return matches

    def trigger(self, trigger_type: WorkflowTriggerType, source: str, payload: dict[str, Any]) -> list[WorkflowRun]:
        runs: list[WorkflowRun] = []
        for definition in self.match_definitions(trigger_type, source, payload):
            runs.append(self.execute_definition(definition, payload, trigger_type, source))
        return runs

    def run_manual(self, workflow_id: str, payload: dict[str, Any] | None = None) -> WorkflowRun:
        definition = self.definitions.get(workflow_id)
        if not definition:
            raise KeyError(workflow_id)
        return self.execute_definition(definition, payload or {}, "manual", "operator")

    def execute_definition(
        self,
        definition: WorkflowDefinition,
        payload: dict[str, Any],
        trigger_type: WorkflowTriggerType,
        source: str,
    ) -> WorkflowRun:
        run = self.create_run(
            workflow_id=definition.id,
            payload=payload,
            status="running",
            trigger_type=trigger_type,
            trigger_source=source,
        )
        self.append_log(
            run.id,
            "Workflow started",
            {"workflow": definition.name, "trigger_type": trigger_type, "source": source},
        )
        status: WorkflowRunStatus = "success"
        context = dict(payload)
        try:
            for action in definition.actions:
                result = execute_action(action, context)
                context[f"action:{action.name}"] = result
                if result.get("needs_human"):
                    status = "needs_human"
                self.append_log(run.id, f"Action {action.name} completed", {"type": action.type, **result})
        except Exception as exc:
            self.append_log(run.id, "Workflow failed", {"error": str(exc)}, status="failed")
            return self.runs[run.id]
        self.append_log(run.id, "Workflow completed", {"action_count": len(definition.actions)}, status=status)
        return self.runs[run.id]


def payload_value(payload: dict[str, Any], field: str) -> Any:
    current: Any = payload
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def evaluate_condition(condition: WorkflowCondition, payload: dict[str, Any]) -> bool:
    actual = payload_value(payload, condition.field)
    if condition.operator == "exists":
        return actual not in {None, ""}
    if condition.operator == "equals":
        return actual == condition.value
    if condition.operator == "contains":
        return str(condition.value) in str(actual or "")
    if condition.operator in {"gte", "lte"}:
        try:
            left = float(actual)
            right = float(condition.value)
        except (TypeError, ValueError):
            return False
        return left >= right if condition.operator == "gte" else left <= right
    return False


def text_from_context(context: dict[str, Any]) -> str:
    for key in ["message", "text", "need", "need_text", "conversation"]:
        value = context.get(key)
        if value:
            return str(value)
    customer = context.get("customer")
    if isinstance(customer, dict):
        return str(customer.get("message") or customer.get("need") or "")
    return ""


def keyword_intent_score(text: str) -> dict[str, Any]:
    score = 35
    tags: list[str] = []
    if any(word in text for word in ["价格", "多少钱", "报价", "套餐", "费用"]):
        score += 18
        tags.append("price")
    if any(word in text for word in ["案例", "演示", "试用", "效果", "怎么做"]):
        score += 18
        tags.append("solution")
    if any(word in text for word in ["微信", "电话", "联系", "预约", "加你"]):
        score += 22
        tags.append("contact")
    if any(word in text for word in ["今天", "马上", "尽快", "本周", "急"]):
        score += 12
        tags.append("urgent")
    score = max(0, min(100, score))
    return {"intent_score": score, "tags": tags, "hot": score >= 70}


def keyword_risk_check(text: str) -> dict[str, Any]:
    risks = []
    for label, words in {
        "after_sale": ["退款", "退货", "售后", "不满意"],
        "complaint": ["投诉", "差评", "骗子"],
        "payment": ["付款", "打款", "转账", "押金"],
        "privacy": ["身份证", "银行卡", "密码"],
    }.items():
        if any(word in text for word in words):
            risks.append(label)
    return {"risk_flags": risks, "needs_human": bool(risks)}


def execute_action(action: WorkflowAction, context: dict[str, Any]) -> dict[str, Any]:
    text = text_from_context(context)
    if action.type == "score_intent":
        return keyword_intent_score(text)
    if action.type == "risk_check":
        return keyword_risk_check(text)
    if action.type == "notify_human":
        return {
            "needs_human": action.requires_human_confirmation or bool(action.config.get("always", True)),
            "reason": action.config.get("reason", "需要人工确认"),
        }
    if action.type == "create_task":
        return {
            "task_id": str(uuid.uuid4()),
            "title": action.config.get("title") or "跟进客户",
            "target": action.config.get("target") or context.get("lead_id") or context.get("session_id") or "manual",
        }
    if action.type == "update_lead_stage":
        return {"stage": action.config.get("stage", "follow_up"), "target": context.get("lead_id") or context.get("session_id")}
    if action.type == "generate_report":
        return {"report": {"summary": text[:120] or "暂无触发内容", "next_action": action.config.get("next_action", "继续跟进")}}
    if action.type == "run_local_script":
        return {
            "needs_human": True,
            "script_id": action.config.get("script_id"),
            "reason": "本机脚本必须通过受保护的 /api/local-scripts/{id}/run 接口从本机启动",
        }
    return {}


def default_workflow_definitions() -> dict[str, WorkflowDefinition]:
    definitions = [
        WorkflowDefinition(
            id="message_high_intent_handoff",
            name="高意向消息转人工跟进",
            module="AI 客服",
            description="客户消息包含留资、报价、试用等信号时，评分并创建人工跟进任务。",
            trigger=WorkflowTrigger(type="message", source="*"),
            conditions=[WorkflowCondition(field="message", operator="exists")],
            actions=[
                WorkflowAction(type="score_intent", name="意向评分"),
                WorkflowAction(type="risk_check", name="风险识别"),
                WorkflowAction(type="create_task", name="创建跟进任务", config={"title": "高意向客户跟进"}),
                WorkflowAction(type="notify_human", name="提醒人工确认", config={"reason": "高意向或风险消息需要人工确认"}),
            ],
        ),
        WorkflowDefinition(
            id="lead_intake_next_step",
            name="新线索首轮跟进",
            module="获客中心",
            description="新线索进入后生成跟进任务，并标记为待跟进阶段。",
            trigger=WorkflowTrigger(type="lead", source="*"),
            conditions=[WorkflowCondition(field="need", operator="exists")],
            actions=[
                WorkflowAction(type="score_intent", name="线索意向评分"),
                WorkflowAction(type="update_lead_stage", name="标记待跟进", config={"stage": "follow_up"}),
                WorkflowAction(type="create_task", name="创建线索跟进任务", config={"title": "新线索 24 小时内跟进"}),
            ],
        ),
        WorkflowDefinition(
            id="daily_ops_report",
            name="每日运营检查",
            module="自动化中心",
            description="为每日检查保留统一 Workflow 入口；真实脚本启动仍走本机受保护接口。",
            trigger=WorkflowTrigger(type="schedule", source="daily"),
            actions=[
                WorkflowAction(type="generate_report", name="生成运营摘要", config={"next_action": "运行今日脚本验收和需求扫描"}),
                WorkflowAction(type="run_local_script", name="等待本机脚本确认", config={"script_id": "today_check"}, requires_human_confirmation=True),
            ],
        ),
        WorkflowDefinition(
            id="daily_business_report",
            name="每日经营日报",
            module="经营分析",
            description="生成可复盘的经营日报；真实报表由 /api/v1/reports/daily/run 触发并保存。",
            trigger=WorkflowTrigger(type="schedule", source="daily"),
            actions=[
                WorkflowAction(type="generate_report", name="生成日报摘要", config={"next_action": "保存日报并发送给老板/运营负责人"}),
                WorkflowAction(type="notify_human", name="提醒负责人查看", config={"reason": "日报生成后需要负责人确认重点动作"}),
            ],
        ),
    ]
    return {item.id: item for item in definitions}


workflow_engine = WorkflowEngine()
