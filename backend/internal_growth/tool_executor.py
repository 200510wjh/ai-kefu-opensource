from __future__ import annotations

import time
import uuid
from typing import Any

from backend.internal_growth.models import (
    FollowUpTask,
    ProspectCandidate,
    ProspectCandidateCreate,
    ProspectSearchCreate,
    ToolExecutionResult,
    ToolRunRecord,
    now_iso,
)
from backend.internal_growth.growth_agent_assets import (
    create_xianyu_service_draft,
    generate_summit_content_pack,
    recommend_open_source_stack,
)
from backend.internal_growth.prospecting import convert_candidate_to_lead, create_prospect_search
from backend.internal_growth.source_integrations import run_external_search
from backend.internal_growth.store import InternalGrowthStore, store as default_store
from backend.internal_growth.tool_guardrails import check_tool_call
from backend.internal_growth.tool_registry import get_tool
from backend.internal_growth.workflows import run_daily_growth_workflow


def generate_contact_suggestion(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    lead = growth_store.get_lead(str(payload["lead_id"]))
    if not lead:
        raise ValueError("Lead not found")
    reason = f"{lead.customer_name} 的公开业务与 Internal Growth OS 的需求发现、内容生产、CRM跟进能力匹配。"
    return {
        "lead_id": lead.id,
        "contact_reason": reason,
        "dm_draft": f"你好，我看到你们在做{lead.industry}。我这边在做一个内部获客运营系统，可以帮团队把需求发现、内容脚本、客户跟进和复盘串起来。想先给你看一个低成本测试案例，合适的话再聊。",
        "call_opening": f"你好，我想确认一下你们现在做{lead.industry}时，内容产出和客户跟进是不是主要靠人工？我这边有一个内部获客工作台，可以先用一个小样本方向测试。",
        "form_message": f"想咨询合作：我们有一套 Internal Growth OS，可辅助{lead.industry}团队做需求雷达、内容工厂、线索CRM和增长复盘。希望人工沟通一个试点场景。",
        "followup_cadence": ["第1天人工触达", "第3天补充一个案例", "第7天复盘是否继续跟进"],
        "risk_note": "仅生成建议，不自动发送。请人工核实公司和联系人后再触达。",
    }


def create_followup_task(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    if not growth_store.get_lead(str(payload["lead_id"])):
        raise ValueError("Lead not found")
    task = growth_store.save_follow_up_task(
        FollowUpTask(
            id=str(uuid.uuid4()),
            lead_id=str(payload["lead_id"]),
            title=str(payload["title"]),
            priority=str(payload.get("priority") or "normal"),  # type: ignore[arg-type]
        )
    )
    return task.model_dump(mode="json")


def create_public_prospect_search(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    search = create_prospect_search(ProspectSearchCreate.model_validate(payload))
    return growth_store.save_prospect_search(search).model_dump(mode="json")


def import_public_prospect_candidate(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    draft = ProspectCandidateCreate.model_validate(payload)
    if draft.search_id and not growth_store.get_prospect_search(draft.search_id):
        raise ValueError("Prospect search not found")
    candidate = growth_store.save_prospect_candidate(ProspectCandidate(id=str(uuid.uuid4()), **draft.model_dump()))
    return candidate.model_dump(mode="json")


def convert_prospect_candidate(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    candidate = growth_store.get_prospect_candidate(str(payload["candidate_id"]))
    if not candidate:
        raise ValueError("Prospect candidate not found")
    if candidate.converted_lead_id:
        lead = growth_store.get_lead(candidate.converted_lead_id)
        if lead:
            return lead.model_dump(mode="json")
    lead = growth_store.save_lead(convert_candidate_to_lead(candidate))
    growth_store.save_prospect_candidate(
        candidate.model_copy(update={"status": "converted", "converted_lead_id": lead.id, "updated_at": now_iso()})
    )
    return lead.model_dump(mode="json")


def run_public_source_search(payload: dict[str, Any], growth_store: InternalGrowthStore) -> dict[str, Any]:
    search = growth_store.get_prospect_search(str(payload["search_id"]))
    if not search:
        raise ValueError("Prospect search not found")
    provider = str(payload.get("provider") or "searxng")
    result = run_external_search(search, provider)  # type: ignore[arg-type]
    return result.model_dump(mode="json")


def execute_tool(
    task_id: str,
    tool_name: str,
    payload: dict[str, Any],
    growth_store: InternalGrowthStore | None = None,
) -> ToolExecutionResult:
    active_store = growth_store or default_store
    started = time.perf_counter()
    tool = get_tool(tool_name)
    if not tool:
        return ToolExecutionResult(status="blocked", tool_name=tool_name, input=payload, blocked_reason="工具未注册。")

    allowed, reason, input_hash = check_tool_call(task_id, tool, payload, active_store)
    if not allowed:
        result = ToolExecutionResult(
            status="needs_human" if tool.requires_human_confirmation else "blocked",
            tool_name=tool.name,
            input=payload,
            blocked_reason=reason,
            risk_level=tool.risk_level,
        )
        active_store.save_tool_run(
            ToolRunRecord(
                id=str(uuid.uuid4()),
                task_id=task_id,
                tool_name=tool.name,
                input_hash=input_hash,
                risk_level=tool.risk_level,
                status=result.status,
                input=payload,
                blocked_reason=reason,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )
        return result

    retry_count = 0
    error = ""
    output: dict[str, Any] = {}
    status = "failed"
    for attempt in range(tool.max_retries + 1):
        retry_count = attempt
        try:
            if tool.name == "generate_contact_suggestion":
                output = generate_contact_suggestion(payload, active_store)
            elif tool.name == "create_followup_task":
                output = create_followup_task(payload, active_store)
            elif tool.name == "create_public_prospect_search":
                output = create_public_prospect_search(payload, active_store)
            elif tool.name == "import_public_prospect_candidate":
                output = import_public_prospect_candidate(payload, active_store)
            elif tool.name == "run_public_source_search":
                output = run_public_source_search(payload, active_store)
            elif tool.name == "convert_prospect_candidate_to_lead":
                output = convert_prospect_candidate(payload, active_store)
            elif tool.name == "run_daily_growth_workflow":
                output = run_daily_growth_workflow("manual", active_store).model_dump(mode="json")
            elif tool.name == "generate_summit_content_pack":
                output = generate_summit_content_pack(payload, active_store)
            elif tool.name == "create_xianyu_service_draft":
                output = create_xianyu_service_draft(payload, active_store)
            elif tool.name == "recommend_open_source_stack":
                output = recommend_open_source_stack(payload)
            else:
                raise ValueError("工具暂未实现执行器。")
            if tool.result_validator:
                valid, validation_error = tool.result_validator(output)
                if not valid:
                    raise ValueError(validation_error)
            status = "success"
            error = ""
            break
        except Exception as exc:
            error = str(exc)
            status = "failed"

    result = ToolExecutionResult(
        status=status,  # type: ignore[arg-type]
        tool_name=tool.name,
        input=payload,
        output=output,
        error=error,
        retry_count=retry_count,
        risk_level=tool.risk_level,
    )
    active_store.save_tool_run(
        ToolRunRecord(
            id=str(uuid.uuid4()),
            task_id=task_id,
            tool_name=tool.name,
            input_hash=input_hash,
            risk_level=tool.risk_level,
            status=result.status,
            input=payload,
            output=output,
            error=error,
            retry_count=retry_count,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )
    return result
