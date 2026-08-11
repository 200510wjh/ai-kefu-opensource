from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.internal_growth.analytics import build_weekly_report
from backend.internal_growth.content_factory import create_content_tasks
from backend.internal_growth.models import (
    AgentPlan,
    AgentPlanRequest,
    AgentRunRequest,
    AgentRunResponse,
    AIBrainChatRequest,
    AIBrainChatResponse,
    AIBrainProviderStatus,
    AnalyticsReport,
    ContentGenerateRequest,
    ContentTask,
    ContentTaskUpdate,
    CustomerInteraction,
    CustomerInteractionCreate,
    DashboardSummary,
    DailyWorkflowRun,
    DemandCreate,
    DemandSignal,
    FollowUpTask,
    FollowUpTaskCreate,
    Lead,
    LeadCreate,
    LeadUpdate,
    OpportunityScore,
    ProspectCandidate,
    ProspectCandidateCreate,
    ProspectCandidateUpdate,
    ProspectExternalSearchResponse,
    ProspectIntegrationProvider,
    ProspectIntegrationStatus,
    ProspectSearch,
    ProspectSearchCreate,
    PublishingRecord,
    PublishingRecordCreate,
    PublishingRecordUpdate,
    SalesAnalysis,
    SalesAnalyzeRequest,
    SOPMetrics,
    SOPRun,
    SOPTemplate,
    ToolRunRecord,
    now_iso,
)
from backend.internal_growth.agent_planner import plan_agent_task
from backend.internal_growth.ai_brain import ai_brain_providers, run_ai_brain_chat
from backend.internal_growth.prospecting import PLATFORM_LABELS, convert_candidate_to_lead, create_prospect_search
from backend.internal_growth.sales import analyze_sales_conversation
from backend.internal_growth.scoring import score_demand
from backend.internal_growth.source_integrations import list_source_integrations, run_external_search
from backend.internal_growth.sop import build_sop_metrics, list_sop_runs, list_sop_templates
from backend.internal_growth.store import store
from backend.internal_growth.tool_executor import execute_tool
from backend.internal_growth.tool_registry import list_tools
from backend.internal_growth.workflows import run_daily_growth_workflow
from backend.platform.workflow import workflow_engine


router = APIRouter(prefix="/api/internal-growth", tags=["internal-growth"])


def infer_prospect_platform(task: str, context: dict[str, object]) -> str:
    explicit = str(context.get("platform") or "")
    if explicit:
        return explicit
    if "闲鱼" in task:
        return "xianyu"
    if "小红书" in task:
        return "xiaohongshu"
    if "快手" in task:
        return "kuaishou"
    if "抖音" in task:
        return "douyin"
    if "官网" in task or "网页" in task:
        return "website"
    return "baidu"


def list_from_context(context: dict[str, object], key: str, fallback: list[str]) -> list[str]:
    value = context.get(key)
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return fallback


def is_today(iso_value: str) -> bool:
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.astimezone(timezone.utc).date() == datetime.now(timezone.utc).date()


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard() -> DashboardSummary:
    demands = store.list_demands()
    opportunities = store.list_opportunities()
    content_tasks = store.list_content_tasks()
    publishing_records = store.list_publishing_records()
    leads = store.list_leads()
    followups = [item for item in store.list_follow_up_tasks() if item.status == "open"]
    high_intent = [item for item in leads if item.intent_level == "high" and item.stage not in {"won", "lost"}]
    top = sorted(opportunities, key=lambda item: item.total_score, reverse=True)[:3]
    demand_map = {item.id: item for item in demands}
    top_directions = [
        {
            "demand_id": item.demand_id,
            "name": demand_map[item.demand_id].name if item.demand_id in demand_map else "未知需求",
            "industry": demand_map[item.demand_id].industry if item.demand_id in demand_map else "",
            "score": item.total_score,
            "decision": item.recommended_decision,
            "reasoning": item.reasoning,
        }
        for item in top
    ]
    return DashboardSummary(
        today_opportunities=sum(1 for item in opportunities if is_today(item.created_at)),
        today_content_tasks=sum(1 for item in content_tasks if is_today(item.created_at)),
        pending_followups=len(followups),
        high_intent_leads=len(high_intent),
        weekly={
            "published_count": sum(1 for item in content_tasks if item.status == "published"),
            "consultations": len(leads),
            "qualified_leads": sum(1 for item in leads if item.intent_level in {"medium", "high"}),
            "revenue": sum(1 for item in leads if item.stage == "won"),
        },
        top_directions=top_directions,
        review_queue=[item for item in content_tasks if item.status in {"draft", "review"}][:8],
        publishing_queue=[item for item in publishing_records if item.status in {"draft", "review"}][:8],
        today_followups=followups[:8],
        high_intent_lead_list=high_intent[:8],
        latest_workflow_run=store.list_workflow_runs()[0] if store.list_workflow_runs() else None,
    )


@router.get("/demands", response_model=list[DemandSignal])
async def list_demands() -> list[DemandSignal]:
    return store.list_demands()


@router.post("/demands", response_model=DemandSignal)
async def create_demand(payload: DemandCreate) -> DemandSignal:
    text = " ".join([payload.name, payload.pain_points, payload.raw_text, " ".join(payload.keywords)])
    buying = 62 if any(term in text for term in ["报价", "价格", "马上", "今天", "客户", "成交", "咨询", "预算"]) else 48
    demand = DemandSignal(
        id=str(uuid.uuid4()),
        **payload.model_dump(),
        buying_possibility=buying,
        recommended_action="先做机会评分，再生成一组低成本内容测试。",
    )
    return store.save_demand(demand)


@router.post("/demands/{demand_id}/score", response_model=OpportunityScore)
async def score(demand_id: str) -> OpportunityScore:
    demand = store.get_demand(demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    return store.save_opportunity(score_demand(demand))


@router.get("/opportunities", response_model=list[OpportunityScore])
async def list_opportunities() -> list[OpportunityScore]:
    return store.list_opportunities()


@router.post("/content/generate", response_model=list[ContentTask])
async def generate_content(payload: ContentGenerateRequest) -> list[ContentTask]:
    demand = store.get_demand(payload.demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    opportunity = store.get_opportunity_for_demand(demand.id) or store.save_opportunity(score_demand(demand))
    tasks = create_content_tasks(demand, opportunity, payload.platforms)
    return store.save_content_tasks(tasks)


@router.get("/content-tasks", response_model=list[ContentTask])
async def list_content_tasks() -> list[ContentTask]:
    return store.list_content_tasks()


@router.patch("/content-tasks/{task_id}", response_model=ContentTask)
async def update_content_task(task_id: str, payload: ContentTaskUpdate) -> ContentTask:
    task = store.get_content_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Content task not found")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    return store.save_content_task(task.model_copy(update={**updates, "updated_at": now_iso()}))


@router.get("/publishing-records", response_model=list[PublishingRecord])
async def list_publishing_records() -> list[PublishingRecord]:
    return store.list_publishing_records()


@router.post("/publishing-records", response_model=PublishingRecord)
async def create_publishing_record(payload: PublishingRecordCreate) -> PublishingRecord:
    task = store.get_content_task(payload.content_task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Content task not found")
    record = PublishingRecord(id=str(uuid.uuid4()), **payload.model_dump())
    saved = store.save_publishing_record(record)
    store.save_content_task(task.model_copy(update={"status": saved.status, "updated_at": now_iso()}))
    return saved


@router.patch("/publishing-records/{record_id}", response_model=PublishingRecord)
async def update_publishing_record(record_id: str, payload: PublishingRecordUpdate) -> PublishingRecord:
    record = store.get_publishing_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Publishing record not found")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    saved = store.save_publishing_record(record.model_copy(update={**updates, "updated_at": now_iso()}))
    task = store.get_content_task(saved.content_task_id)
    if task:
        store.save_content_task(task.model_copy(update={"status": saved.status, "updated_at": now_iso()}))
    return saved


@router.get("/leads", response_model=list[Lead])
async def list_leads() -> list[Lead]:
    return store.list_leads()


@router.post("/leads", response_model=Lead)
async def create_lead(payload: LeadCreate) -> Lead:
    lead = Lead(id=str(uuid.uuid4()), **payload.model_dump())
    saved = store.save_lead(lead)
    if saved.next_action:
        store.save_follow_up_task(
            FollowUpTask(
                id=str(uuid.uuid4()),
                lead_id=saved.id,
                title=saved.next_action,
                due_at=saved.next_followup_at,
                priority="high" if saved.intent_level == "high" else "normal",
            )
        )
    return saved


@router.patch("/leads/{lead_id}", response_model=Lead)
async def update_lead(lead_id: str, payload: LeadUpdate) -> Lead:
    lead = store.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    return store.save_lead(lead.model_copy(update={**updates, "updated_at": now_iso()}))


@router.get("/prospect-source-templates")
async def prospect_source_templates() -> list[dict[str, str]]:
    return [
        {
            "platform": platform,
            "label": label,
            "mode": "manual_public_collection",
            "guardrail": "只打开公开搜索结果并人工粘贴证据；不登录抓取、不绕过验证码、不自动联系。",
        }
        for platform, label in PLATFORM_LABELS.items()
    ]


@router.get("/source-integrations", response_model=list[ProspectIntegrationStatus])
async def source_integrations() -> list[ProspectIntegrationStatus]:
    return list_source_integrations()


@router.get("/prospect-searches", response_model=list[ProspectSearch])
async def list_prospect_searches() -> list[ProspectSearch]:
    return store.list_prospect_searches()


@router.post("/prospect-searches", response_model=ProspectSearch)
async def create_public_prospect_search(payload: ProspectSearchCreate) -> ProspectSearch:
    search = create_prospect_search(payload)
    return store.save_prospect_search(search)


@router.post("/prospect-searches/{search_id}/external-results", response_model=ProspectExternalSearchResponse)
async def prospect_external_results(
    search_id: str,
    provider: ProspectIntegrationProvider = "searxng",
) -> ProspectExternalSearchResponse:
    search = store.get_prospect_search(search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Prospect search not found")
    return run_external_search(search, provider)


@router.get("/prospect-candidates", response_model=list[ProspectCandidate])
async def list_prospect_candidates() -> list[ProspectCandidate]:
    return store.list_prospect_candidates()


@router.post("/prospect-candidates", response_model=ProspectCandidate)
async def create_prospect_candidate(payload: ProspectCandidateCreate) -> ProspectCandidate:
    if payload.search_id and not store.get_prospect_search(payload.search_id):
        raise HTTPException(status_code=404, detail="Prospect search not found")
    candidate = ProspectCandidate(id=str(uuid.uuid4()), **payload.model_dump())
    saved = store.save_prospect_candidate(candidate)
    if saved.search_id:
        search = store.get_prospect_search(saved.search_id)
        if search:
            store.save_prospect_search(search.model_copy(update={"status": "imported", "updated_at": now_iso()}))
    return saved


@router.patch("/prospect-candidates/{candidate_id}", response_model=ProspectCandidate)
async def update_prospect_candidate(candidate_id: str, payload: ProspectCandidateUpdate) -> ProspectCandidate:
    candidate = store.get_prospect_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Prospect candidate not found")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    return store.save_prospect_candidate(candidate.model_copy(update={**updates, "updated_at": now_iso()}))


@router.post("/prospect-candidates/{candidate_id}/convert-lead", response_model=Lead)
async def convert_prospect_candidate(candidate_id: str) -> Lead:
    candidate = store.get_prospect_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Prospect candidate not found")
    if candidate.converted_lead_id:
        lead = store.get_lead(candidate.converted_lead_id)
        if lead:
            return lead
    lead = store.save_lead(convert_candidate_to_lead(candidate))
    store.save_prospect_candidate(
        candidate.model_copy(update={"status": "converted", "converted_lead_id": lead.id, "updated_at": now_iso()})
    )
    return lead


@router.get("/leads/{lead_id}/interactions", response_model=list[CustomerInteraction])
async def list_interactions(lead_id: str) -> list[CustomerInteraction]:
    if not store.get_lead(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return store.list_interactions(lead_id)


@router.post("/interactions", response_model=CustomerInteraction)
async def create_interaction(payload: CustomerInteractionCreate) -> CustomerInteraction:
    if not store.get_lead(payload.lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    summary = payload.content[:120]
    return store.save_interaction(CustomerInteraction(id=str(uuid.uuid4()), **payload.model_dump(), ai_summary=summary))


@router.get("/follow-up-tasks", response_model=list[FollowUpTask])
async def list_follow_up_tasks() -> list[FollowUpTask]:
    return store.list_follow_up_tasks()


@router.post("/follow-up-tasks", response_model=FollowUpTask)
async def create_follow_up_task(payload: FollowUpTaskCreate) -> FollowUpTask:
    if not store.get_lead(payload.lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return store.save_follow_up_task(FollowUpTask(id=str(uuid.uuid4()), **payload.model_dump()))


@router.post("/sales/analyze-chat", response_model=SalesAnalysis)
async def analyze_chat(payload: SalesAnalyzeRequest) -> SalesAnalysis:
    if payload.lead_id and not store.get_lead(payload.lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    analysis = analyze_sales_conversation(payload)
    saved = store.save_sales_analysis(analysis)
    if saved.lead_id:
        lead = store.get_lead(saved.lead_id)
        if lead:
            intent_level = "high" if saved.purchase_probability >= 72 else "medium" if saved.purchase_probability >= 45 else "low"
            store.save_lead(
                lead.model_copy(
                    update={
                        "intent_level": intent_level,
                        "next_action": saved.next_strategy,
                        "updated_at": now_iso(),
                    }
                )
            )
    return saved


@router.get("/sales/analyses", response_model=list[SalesAnalysis])
async def list_sales_analyses() -> list[SalesAnalysis]:
    return store.list_sales_analyses()


@router.post("/analytics/weekly", response_model=AnalyticsReport)
async def weekly_report() -> AnalyticsReport:
    report = build_weekly_report(store.list_leads(), store.list_content_tasks())
    return store.save_analytics_report(report)


@router.get("/analytics/reports", response_model=list[AnalyticsReport])
async def list_reports() -> list[AnalyticsReport]:
    return store.list_analytics_reports()


@router.post("/workflows/daily/run", response_model=DailyWorkflowRun)
async def run_daily_workflow() -> DailyWorkflowRun:
    return run_daily_growth_workflow("manual")


@router.get("/workflows/runs", response_model=list[DailyWorkflowRun])
async def list_workflow_runs() -> list[DailyWorkflowRun]:
    return store.list_workflow_runs()


@router.get("/sop/templates", response_model=list[SOPTemplate])
async def sop_templates() -> list[SOPTemplate]:
    return list_sop_templates(workflow_engine)


@router.get("/sop/runs", response_model=list[SOPRun])
async def sop_runs(workflow_id: str | None = None) -> list[SOPRun]:
    return list_sop_runs(workflow_engine, workflow_id)


@router.get("/sop/metrics", response_model=SOPMetrics)
async def sop_metrics() -> SOPMetrics:
    runs = list_sop_runs(workflow_engine)
    return build_sop_metrics(
        runs=runs,
        leads=store.list_leads(),
        followups=store.list_follow_up_tasks(),
        interactions=store.list_interactions(),
    )


@router.get("/ai-brain/providers", response_model=list[AIBrainProviderStatus])
async def ai_brain_provider_status() -> list[AIBrainProviderStatus]:
    return ai_brain_providers()


@router.post("/ai-brain/chat", response_model=AIBrainChatResponse)
async def ai_brain_chat(payload: AIBrainChatRequest) -> AIBrainChatResponse:
    return run_ai_brain_chat(payload)


@router.get("/agent/tools")
async def agent_tools() -> list[dict[str, object]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "risk_level": tool.risk_level,
            "requires_human_confirmation": tool.requires_human_confirmation,
            "allowed_scenarios": tool.allowed_scenarios,
            "blocked_scenarios": tool.blocked_scenarios,
            "input_schema": tool.input_schema,
        }
        for tool in list_tools()
    ]


@router.post("/agent/plan", response_model=AgentPlan)
async def agent_plan(payload: AgentPlanRequest) -> AgentPlan:
    return plan_agent_task(payload)


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(payload: AgentRunRequest) -> AgentRunResponse:
    plan = plan_agent_task(payload)
    task_id = payload.task_id or plan.id
    results = []
    context = payload.context
    for tool_name in plan.needed_tools:
        if tool_name == "generate_contact_suggestion":
            lead_id = str(context.get("lead_id") or "")
            if not lead_id:
                leads = store.list_leads()
                lead_id = leads[0].id if leads else ""
            results.append(execute_tool(task_id, tool_name, {"lead_id": lead_id}))
        elif tool_name == "create_followup_task":
            results.append(
                execute_tool(
                    task_id,
                    tool_name,
                    {
                        "lead_id": str(context.get("lead_id") or ""),
                        "title": str(context.get("title") or "人工跟进真实潜在客户"),
                        "priority": str(context.get("priority") or "normal"),
                    },
                )
            )
        elif tool_name == "create_public_prospect_search":
            results.append(
                execute_tool(
                    task_id,
                    tool_name,
                    {
                        "platform": infer_prospect_platform(payload.task, context),
                        "intent_goal": str(context.get("intent_goal") or "寻找有获客、内容生产、客户跟进痛点的真实公开客户"),
                        "industry": str(context.get("industry") or "本地生活/中小企业服务"),
                        "city": str(context.get("city") or ""),
                        "keywords": list_from_context(context, "keywords", ["获客", "客户咨询", "内容运营", "CRM"]),
                        "pain_keywords": list_from_context(context, "pain_keywords", ["没人咨询", "转化差", "客户跟进慢"]),
                        "excluded_keywords": list_from_context(context, "excluded_keywords", ["招聘", "课程", "论文"]),
                        "notes": f"Agent 任务：{payload.task}",
                    },
                )
            )
        elif tool_name == "run_daily_growth_workflow":
            results.append(execute_tool(task_id, tool_name, {}))
        elif tool_name == "generate_summit_content_pack":
            results.append(
                execute_tool(
                    task_id,
                    tool_name,
                    {
                        "topic": str(context.get("topic") or "AI企业SOP与一人AI获客Agent"),
                        "angle": str(context.get("angle") or "企业不是缺AI工具，而是缺能跑起来的AI SOP。"),
                        "target_customer": str(context.get("target_customer") or "想用AI降低人工成本、提升客服和销售效率的中小企业老板"),
                        "source_files": list_from_context(context, "source_files", ["峰会内容/_contact_sheet.jpg"]),
                    },
                )
            )
        elif tool_name == "create_xianyu_service_draft":
            results.append(
                execute_tool(
                    task_id,
                    tool_name,
                    {
                        "service_name": str(context.get("service_name") or "企业AI客服/知识库/CRM流程诊断 可做试点方案"),
                        "target_customer": str(context.get("target_customer") or "中小企业老板、本地生活商家、电商卖家"),
                        "pain_points": str(context.get("pain_points") or "客服回复慢、客户跟进断、内容获客不稳定、重复流程靠人工"),
                        "deliverables": list_from_context(
                            context,
                            "deliverables",
                            ["业务流程诊断", "知识库整理", "AI客服候选回复", "CRM跟进流程", "自动化工作流建议"],
                        ),
                        "price_anchor": str(context.get("price_anchor") or "先做低成本诊断，确认需求后再报价试点"),
                    },
                )
            )
        elif tool_name == "recommend_open_source_stack":
            results.append(
                execute_tool(
                    task_id,
                    tool_name,
                    {"goal": str(context.get("goal") or payload.task)},
                )
            )
        else:
            results.append(execute_tool(task_id, tool_name, context))
    status = "success"
    if any(item.status == "needs_human" for item in results):
        status = "needs_human"
    elif any(item.status in {"failed", "blocked"} for item in results):
        status = "blocked"
    return AgentRunResponse(
        task_id=task_id,
        plan=plan,
        tool_results=results,
        status=status,  # type: ignore[arg-type]
        summary="Agent 工具调用已通过 Guardrail 执行；外部联系动作不会自动发送。",
    )


@router.get("/agent/tool-runs", response_model=list[ToolRunRecord])
async def agent_tool_runs(task_id: str | None = None) -> list[ToolRunRecord]:
    return store.list_tool_runs(task_id)
