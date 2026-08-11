from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.internal_growth.models import ToolRiskLevel


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]
ToolValidator = Callable[[dict[str, Any]], tuple[bool, str]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    allowed_scenarios: list[str]
    blocked_scenarios: list[str]
    input_schema: dict[str, Any]
    risk_level: ToolRiskLevel
    requires_human_confirmation: bool
    timeout_seconds: int = 20
    max_retries: int = 2
    result_validator: ToolValidator | None = None


def non_empty_result(result: dict[str, Any]) -> tuple[bool, str]:
    return (bool(result), "工具返回为空，请换一个低风险降级动作。")


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "generate_contact_suggestion": ToolDefinition(
        name="generate_contact_suggestion",
        description="为真实公开潜在客户生成触达理由、私信草稿、电话开场白、官网表单留言和跟进节奏。",
        allowed_scenarios=["真实客户人工触达准备", "CRM跟进建议", "销售助手"],
        blocked_scenarios=["自动发送私信", "自动提交表单", "自动外呼", "批量骚扰"],
        input_schema={
            "type": "object",
            "required": ["lead_id"],
            "properties": {"lead_id": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "create_followup_task": ToolDefinition(
        name="create_followup_task",
        description="为 CRM 线索创建人工跟进任务。",
        allowed_scenarios=["CRM跟进", "人工确认队列"],
        blocked_scenarios=["自动联系客户"],
        input_schema={
            "type": "object",
            "required": ["lead_id", "title"],
            "properties": {
                "lead_id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1, "maxLength": 180},
                "priority": {"type": "string", "enum": ["low", "normal", "high"]},
            },
            "additionalProperties": False,
        },
        risk_level="medium",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "create_public_prospect_search": ToolDefinition(
        name="create_public_prospect_search",
        description="创建一个目的明确的公开平台潜客搜索任务，返回人工打开的搜索链接和采集边界。",
        allowed_scenarios=["真实客户搜索", "公开信息采集", "需求雷达"],
        blocked_scenarios=["绕过登录抓取", "验证码绕过", "自动私信", "采集私密聊天"],
        input_schema={
            "type": "object",
            "required": ["platform", "industry"],
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["baidu", "douyin", "xianyu", "xiaohongshu", "kuaishou", "website", "manual_public"],
                },
                "intent_goal": {"type": "string", "maxLength": 300},
                "industry": {"type": "string", "minLength": 1, "maxLength": 120},
                "city": {"type": "string", "maxLength": 80},
                "keywords": {"type": "array"},
                "pain_keywords": {"type": "array"},
                "excluded_keywords": {"type": "array"},
                "notes": {"type": "string", "maxLength": 1000},
            },
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "import_public_prospect_candidate": ToolDefinition(
        name="import_public_prospect_candidate",
        description="导入人工核实过的公开候选客户证据，作为 CRM 转线索前的候选池。",
        allowed_scenarios=["人工粘贴公开候选客户", "线索入库前审核"],
        blocked_scenarios=["批量抓取个人资料", "导入私密聊天", "自动联系客户"],
        input_schema={
            "type": "object",
            "required": ["source_platform", "customer_name", "demand_signal", "public_evidence"],
            "properties": {
                "search_id": {"type": "string"},
                "source_platform": {
                    "type": "string",
                    "enum": ["baidu", "douyin", "xianyu", "xiaohongshu", "kuaishou", "website", "manual_public"],
                },
                "customer_name": {"type": "string", "minLength": 1, "maxLength": 160},
                "industry": {"type": "string", "maxLength": 120},
                "city": {"type": "string", "maxLength": 80},
                "demand_signal": {"type": "string", "minLength": 1, "maxLength": 4000},
                "source_url": {"type": "string", "maxLength": 1000},
                "public_evidence": {"type": "string", "minLength": 1, "maxLength": 4000},
                "contact": {"type": "string", "maxLength": 300},
                "fit_reason": {"type": "string", "maxLength": 1000},
                "intent_level": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "run_public_source_search": ToolDefinition(
        name="run_public_source_search",
        description="通过已配置的开源搜索 Provider 拉取公开搜索结果，用于人工筛选候选客户。",
        allowed_scenarios=["SearXNG公开搜索", "搜索任务结果拉取", "人工候选客户筛选"],
        blocked_scenarios=["绕过登录抓取", "自动导入大批个人信息", "自动联系客户"],
        input_schema={
            "type": "object",
            "required": ["search_id"],
            "properties": {
                "search_id": {"type": "string", "minLength": 1},
                "provider": {"type": "string", "enum": ["searxng", "firecrawl", "crawlee"]},
            },
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "convert_prospect_candidate_to_lead": ToolDefinition(
        name="convert_prospect_candidate_to_lead",
        description="把已核实的公开候选客户转入 CRM 线索，并创建人工跟进下一步。",
        allowed_scenarios=["公开候选客户转 CRM", "人工跟进准备"],
        blocked_scenarios=["自动联系客户", "未核实证据直接批量导入"],
        input_schema={
            "type": "object",
            "required": ["candidate_id"],
            "properties": {"candidate_id": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
        risk_level="medium",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "run_daily_growth_workflow": ToolDefinition(
        name="run_daily_growth_workflow",
        description="运行今日获客流程，只生成草稿、审核队列和跟进任务。",
        allowed_scenarios=["每日获客流程", "人工审核前准备"],
        blocked_scenarios=["无人值守自动发布", "自动发送客户回复"],
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        risk_level="medium",
        requires_human_confirmation=False,
        timeout_seconds=40,
        result_validator=non_empty_result,
    ),
    "generate_summit_content_pack": ToolDefinition(
        name="generate_summit_content_pack",
        description="基于峰会照片/观点生成抖音、闲鱼、朋友圈内容包，并创建发布审核记录。",
        allowed_scenarios=["峰会内容复盘", "个人IP内容生产", "发布前草稿准备", "企业AI获客内容测试"],
        blocked_scenarios=["无人值守自动发布", "虚假峰会背书", "夸大成交承诺"],
        input_schema={
            "type": "object",
            "required": ["topic"],
            "properties": {
                "topic": {"type": "string", "minLength": 1, "maxLength": 120},
                "angle": {"type": "string", "maxLength": 500},
                "target_customer": {"type": "string", "maxLength": 200},
                "source_files": {"type": "array"},
            },
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "create_xianyu_service_draft": ToolDefinition(
        name="create_xianyu_service_draft",
        description="生成闲鱼服务商品草稿和发布审核记录，用于测试企业AI服务咨询。",
        allowed_scenarios=["闲鱼服务草稿", "人工发布前准备", "低成本获客测试"],
        blocked_scenarios=["自动发布闲鱼商品", "自动改价", "自动发货", "自动评价", "自动私信"],
        input_schema={
            "type": "object",
            "required": ["service_name"],
            "properties": {
                "service_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "target_customer": {"type": "string", "maxLength": 200},
                "pain_points": {"type": "string", "maxLength": 1000},
                "deliverables": {"type": "array"},
                "price_anchor": {"type": "string", "maxLength": 200},
            },
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "recommend_open_source_stack": ToolDefinition(
        name="recommend_open_source_stack",
        description="根据当前获客Agent目标推荐可采用的GitHub开源项目和接入边界。",
        allowed_scenarios=["开源项目选型", "Agent工具链设计", "GitHub项目评估"],
        blocked_scenarios=["直接执行未知第三方脚本", "绕过平台风控", "未审计代码接入生产"],
        input_schema={
            "type": "object",
            "required": ["goal"],
            "properties": {"goal": {"type": "string", "minLength": 1, "maxLength": 300}},
            "additionalProperties": False,
        },
        risk_level="low",
        requires_human_confirmation=False,
        result_validator=non_empty_result,
    ),
    "auto_contact_customer": ToolDefinition(
        name="auto_contact_customer",
        description="外部联系客户动作。v1 只允许进入人工确认，不执行。",
        allowed_scenarios=["人工确认后的外部联系"],
        blocked_scenarios=["自动私信", "自动提交表单", "自动拨号", "批量联系"],
        input_schema={
            "type": "object",
            "required": ["lead_id", "message"],
            "properties": {
                "lead_id": {"type": "string", "minLength": 1},
                "message": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        },
        risk_level="high",
        requires_human_confirmation=True,
        max_retries=0,
    ),
}


def get_tool(name: str) -> ToolDefinition | None:
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[ToolDefinition]:
    return list(TOOL_REGISTRY.values())
