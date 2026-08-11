from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.internal_growth.store import InternalGrowthStore, store as default_store
from backend.internal_growth.tool_registry import ToolDefinition


def normalized_input_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, str]:
    required = schema.get("required") or []
    properties = schema.get("properties") or {}
    if not isinstance(payload, dict):
        return False, "参数必须是 JSON object。"
    for key in required:
        if key not in payload or payload[key] in {"", None}:
            return False, f"缺少必填参数：{key}"
    if schema.get("additionalProperties") is False:
        extra = sorted(set(payload) - set(properties))
        if extra:
            return False, f"存在未声明参数：{', '.join(extra)}"
    for key, rule in properties.items():
        if key not in payload:
            continue
        value = payload[key]
        expected = rule.get("type")
        if expected == "string" and not isinstance(value, str):
            return False, f"参数 {key} 必须是字符串。"
        if expected == "array" and not isinstance(value, list):
            return False, f"参数 {key} 必须是数组。"
        if expected == "object" and not isinstance(value, dict):
            return False, f"参数 {key} 必须是对象。"
        if "enum" in rule and value not in rule["enum"]:
            return False, f"参数 {key} 不在合法取值范围。"
        if isinstance(value, str):
            if "minLength" in rule and len(value) < int(rule["minLength"]):
                return False, f"参数 {key} 过短。"
            if "maxLength" in rule and len(value) > int(rule["maxLength"]):
                return False, f"参数 {key} 过长。"
    return True, ""


def check_tool_call(
    task_id: str,
    tool: ToolDefinition,
    payload: dict[str, Any],
    growth_store: InternalGrowthStore | None = None,
) -> tuple[bool, str, str]:
    active_store = growth_store or default_store
    ok, reason = validate_against_schema(payload, tool.input_schema)
    input_hash = normalized_input_hash(payload)
    if not ok:
        return False, reason, input_hash
    if tool.requires_human_confirmation:
        return False, "高风险工具需要人工确认，已拦截自动执行。", input_hash
    previous = [
        item
        for item in active_store.list_tool_runs(task_id)
        if item.tool_name == tool.name and item.input_hash == input_hash and item.status in {"success", "failed", "blocked"}
    ]
    if previous:
        return False, "检测到相同工具和相同参数的重复调用，已拦截。", input_hash
    failures = [item for item in active_store.list_tool_runs(task_id) if item.tool_name == tool.name and item.status == "failed"]
    if len(failures) >= tool.max_retries + 1:
        return False, "工具连续失败，已触发熔断。", input_hash
    return True, "", input_hash
