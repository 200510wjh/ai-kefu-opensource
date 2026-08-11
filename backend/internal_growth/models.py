from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SourceType = Literal["manual", "chat", "public", "authorized_data"]
ContentPlatform = Literal["douyin", "xianyu", "wechat_moments"]
ContentStatus = Literal["draft", "review", "published", "data_backfilled"]
PublishingStatus = Literal["draft", "review", "published", "data_backfilled"]
LeadStage = Literal["new", "contacted", "need_confirmed", "proposal", "quoted", "won", "lost"]
IntentLevel = Literal["low", "medium", "high"]
TaskStatus = Literal["open", "done", "cancelled"]
InteractionDirection = Literal["inbound", "outbound", "note"]
WorkflowRunStatus = Literal["queued", "running", "needs_human", "success", "failed"]
ToolRiskLevel = Literal["low", "medium", "high"]
ToolRunStatus = Literal["success", "failed", "blocked", "needs_human"]
ProspectSourcePlatform = Literal["baidu", "douyin", "xianyu", "xiaohongshu", "kuaishou", "website", "manual_public"]
ProspectSearchStatus = Literal["needs_human_collection", "imported", "closed"]
ProspectCandidateStatus = Literal["new", "verified", "converted", "rejected"]
ProspectIntegrationProvider = Literal["searxng", "firecrawl", "crawlee"]


class DemandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: SourceType = "manual"
    source_detail: str = ""
    industry: str = ""
    keywords: list[str] = Field(default_factory=list)
    pain_points: str = Field(min_length=1, max_length=4000)
    raw_text: str = ""


class DemandSignal(DemandCreate):
    id: str
    buying_possibility: int = Field(default=50, ge=0, le=100)
    recommended_action: str = ""
    created_at: str = Field(default_factory=now_iso)


class OpportunityScore(BaseModel):
    id: str
    demand_id: str
    demand_strength: int = Field(ge=0, le=100)
    deal_probability: int = Field(ge=0, le=100)
    average_order_value: int = Field(ge=0, le=100)
    delivery_difficulty: int = Field(ge=0, le=100)
    fit_score: int = Field(ge=0, le=100)
    total_score: int = Field(ge=0, le=100)
    reasoning: str
    recommended_decision: str
    created_at: str = Field(default_factory=now_iso)


class ContentGenerateRequest(BaseModel):
    demand_id: str
    platforms: list[ContentPlatform] = Field(default_factory=lambda: ["douyin", "xianyu", "wechat_moments"])


class DouyinContent(BaseModel):
    title: str
    script_15s: str
    script_30s: str
    script_60s: str
    storyboard: list[str]
    subtitles: list[str]
    cover_copy: str


class XianyuContent(BaseModel):
    product_title: str
    product_description: str
    main_image_copy: str
    detail_image_copy: list[str]


class MomentsContent(BaseModel):
    case_post: str
    sales_copy: str


class ContentPayload(BaseModel):
    douyin: DouyinContent | None = None
    xianyu: XianyuContent | None = None
    wechat_moments: MomentsContent | None = None


class ContentTask(BaseModel):
    id: str
    demand_id: str
    opportunity_id: str = ""
    platform: ContentPlatform
    status: ContentStatus = "draft"
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    review_note: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ContentTaskUpdate(BaseModel):
    status: ContentStatus | None = None
    review_note: str | None = None


class PublishingRecordCreate(BaseModel):
    content_task_id: str
    platform: ContentPlatform
    status: PublishingStatus = "draft"
    scheduled_at: str = ""
    published_at: str = ""
    views: int = 0
    favorites: int = 0
    consultations: int = 0
    deals: int = 0
    revenue: float = 0
    notes: str = ""


class PublishingRecord(PublishingRecordCreate):
    id: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class PublishingRecordUpdate(BaseModel):
    status: PublishingStatus | None = None
    scheduled_at: str | None = None
    published_at: str | None = None
    views: int | None = None
    favorites: int | None = None
    consultations: int | None = None
    deals: int | None = None
    revenue: float | None = None
    notes: str | None = None


class LeadCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    source_platform: str = "manual"
    industry: str = ""
    demand: str = Field(min_length=1, max_length=4000)
    contact: str = ""
    intent_level: IntentLevel = "medium"
    stage: LeadStage = "new"
    next_followup_at: str = ""
    next_action: str = ""


class Lead(LeadCreate):
    id: str
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class LeadUpdate(BaseModel):
    customer_name: str | None = None
    source_platform: str | None = None
    industry: str | None = None
    demand: str | None = None
    contact: str | None = None
    intent_level: IntentLevel | None = None
    stage: LeadStage | None = None
    next_followup_at: str | None = None
    next_action: str | None = None


class ProspectSearchCreate(BaseModel):
    platform: ProspectSourcePlatform = "baidu"
    intent_goal: str = Field(default="寻找有明确获客、内容生产、CRM跟进痛点的真实公开客户", max_length=300)
    industry: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=80)
    keywords: list[str] = Field(default_factory=list)
    pain_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1000)


class ProspectSearch(ProspectSearchCreate):
    id: str
    query: str
    search_url: str
    status: ProspectSearchStatus = "needs_human_collection"
    guardrail_note: str = "只采集公开可见信息或你已获授权的数据；不要绕过登录、验证码或平台风控，不要自动私信。"
    collection_steps: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ProspectCandidateCreate(BaseModel):
    search_id: str = ""
    source_platform: ProspectSourcePlatform = "manual_public"
    customer_name: str = Field(min_length=1, max_length=160)
    industry: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=80)
    demand_signal: str = Field(min_length=1, max_length=4000)
    source_url: str = Field(default="", max_length=1000)
    public_evidence: str = Field(min_length=1, max_length=4000)
    contact: str = Field(default="", max_length=300)
    fit_reason: str = Field(default="", max_length=1000)
    intent_level: IntentLevel = "medium"


class ProspectCandidate(ProspectCandidateCreate):
    id: str
    status: ProspectCandidateStatus = "new"
    converted_lead_id: str = ""
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ProspectCandidateUpdate(BaseModel):
    status: ProspectCandidateStatus | None = None
    contact: str | None = None
    fit_reason: str | None = None
    intent_level: IntentLevel | None = None


class ProspectIntegrationStatus(BaseModel):
    provider: ProspectIntegrationProvider
    name: str
    license: str
    repository_url: str
    configured: bool = False
    mode: Literal["search_api", "scrape_api", "crawler_framework"]
    status: Literal["ready", "needs_config", "planned"] = "needs_config"
    env_keys: list[str] = Field(default_factory=list)
    best_for: str
    guardrail: str
    next_action: str


class ProspectExternalResult(BaseModel):
    search_id: str
    provider: ProspectIntegrationProvider
    title: str
    url: str = ""
    snippet: str = ""
    engine: str = ""
    score: float = 0


class ProspectExternalSearchResponse(BaseModel):
    search_id: str
    provider: ProspectIntegrationProvider
    configured: bool
    query: str
    results: list[ProspectExternalResult] = Field(default_factory=list)
    message: str = ""
    guardrail_note: str = "外部搜索结果只作为公开候选来源，转入 CRM 前必须人工核实。"


class CustomerInteractionCreate(BaseModel):
    lead_id: str
    channel: str = "manual"
    direction: InteractionDirection = "note"
    content: str = Field(min_length=1, max_length=8000)


class CustomerInteraction(CustomerInteractionCreate):
    id: str
    ai_summary: str = ""
    created_at: str = Field(default_factory=now_iso)


class FollowUpTaskCreate(BaseModel):
    lead_id: str
    title: str = Field(min_length=1, max_length=180)
    due_at: str = ""
    priority: Literal["low", "normal", "high"] = "normal"


class FollowUpTask(FollowUpTaskCreate):
    id: str
    status: TaskStatus = "open"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class SalesAnalyzeRequest(BaseModel):
    lead_id: str | None = None
    customer_name: str = ""
    industry: str = ""
    product_solution: str = "内部获客运营系统：需求发现、机会评分、内容生成、发布审核、CRM跟进和增长复盘。"
    conversation: str = Field(min_length=1, max_length=12000)


class SalesAnalysis(BaseModel):
    id: str
    lead_id: str = ""
    customer_profile: str
    real_need: str
    purchase_probability: int = Field(ge=0, le=100)
    next_strategy: str
    reply_suggestion: str
    risk_flags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class AnalyticsReport(BaseModel):
    id: str
    report_type: Literal["weekly", "daily"] = "weekly"
    period_start: str = ""
    period_end: str = ""
    summary: str
    best_platforms: list[str] = Field(default_factory=list)
    best_content: list[str] = Field(default_factory=list)
    best_services: list[str] = Field(default_factory=list)
    stop_list: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class DailyWorkflowRun(BaseModel):
    id: str
    status: WorkflowRunStatus = "queued"
    trigger: Literal["manual", "schedule"] = "manual"
    started_at: str = Field(default_factory=now_iso)
    finished_at: str = ""
    demand_count: int = 0
    opportunity_count: int = 0
    generated_content_tasks: int = 0
    publishing_records_created: int = 0
    followup_tasks_created: int = 0
    needs_human_confirmation: bool = True
    logs: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    today_opportunities: int
    today_content_tasks: int
    pending_followups: int
    high_intent_leads: int
    weekly: dict[str, int | float]
    top_directions: list[dict[str, Any]]
    review_queue: list[ContentTask]
    publishing_queue: list[PublishingRecord] = Field(default_factory=list)
    today_followups: list[FollowUpTask] = Field(default_factory=list)
    high_intent_lead_list: list[Lead] = Field(default_factory=list)
    latest_workflow_run: DailyWorkflowRun | None = None


class AgentPlanRequest(BaseModel):
    task: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    id: str
    task_goal: str
    needed_tools: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    risk_assessment: str = ""
    requires_human_confirmation: bool = False
    expected_outputs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


class AgentRunRequest(AgentPlanRequest):
    task_id: str | None = None


class ToolRunRecord(BaseModel):
    id: str
    task_id: str
    tool_name: str
    input_hash: str
    risk_level: ToolRiskLevel
    status: ToolRunStatus
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    blocked_reason: str = ""
    retry_count: int = 0
    duration_ms: int = 0
    created_at: str = Field(default_factory=now_iso)


class ToolExecutionResult(BaseModel):
    status: ToolRunStatus
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    blocked_reason: str = ""
    retry_count: int = 0
    risk_level: ToolRiskLevel = "low"


class AgentRunResponse(BaseModel):
    task_id: str
    plan: AgentPlan
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    status: ToolRunStatus = "success"
    summary: str = ""


SOPStepRunStatus = Literal["success", "failed", "needs_human", "skipped", "running"]


class SOPStepTemplate(BaseModel):
    id: str
    name: str
    action_type: str
    description: str = ""
    requires_human_confirmation: bool = False


class SOPTemplate(BaseModel):
    id: str
    name: str
    module: str
    description: str
    trigger: str
    enabled: bool = True
    steps: list[SOPStepTemplate] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    frequency_limits: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=now_iso)


class SOPStepRun(BaseModel):
    id: str
    name: str
    action_type: str
    status: SOPStepRunStatus = "success"
    duration_ms: int = 0
    evidence: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    created_at: str = Field(default_factory=now_iso)


class SOPRun(BaseModel):
    id: str
    template_id: str
    template_name: str
    status: Literal["queued", "pending", "running", "success", "completed", "failed", "needs_human"] = "pending"
    source: str = ""
    platform: str = ""
    session_id: str = ""
    customer_name: str = ""
    message_hash: str = ""
    action: str = ""
    intent_score: int = 0
    risk_flags: list[str] = Field(default_factory=list)
    knowledge_citations: list[str] = Field(default_factory=list)
    reply_text: str = ""
    reason: str = ""
    steps: list[SOPStepRun] = Field(default_factory=list)
    started_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class SOPMetrics(BaseModel):
    today_consultations: int = 0
    ai_auto_replies: int = 0
    saved_minutes: int = 0
    high_intent_customers: int = 0
    pending_followups: int = 0
    handoff_count: int = 0
    auto_reply_rate: int = 0
    avg_response_ms: int = 0
    conversion_customers: int = 0
    sop_runs_today: int = 0
    advice: list[str] = Field(default_factory=list)
    recent_runs: list[SOPRun] = Field(default_factory=list)


AIBrainChannel = Literal["direct", "wechat_group", "douyin_group", "website_chat", "internal"]
AIBrainRole = Literal["system", "user", "assistant"]


class AIBrainMessage(BaseModel):
    role: AIBrainRole
    content: str = Field(min_length=1, max_length=12000)
    sender_name: str = ""
    created_at: str = Field(default_factory=now_iso)


class AIBrainProviderStatus(BaseModel):
    id: str
    name: str
    kind: Literal["official", "relay", "self_hosted"]
    base_url: str = ""
    model: str = ""
    configured: bool = False
    env_key: str = ""
    cost_note: str = ""
    safety_note: str = ""


class AIBrainChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    messages: list[AIBrainMessage] = Field(default_factory=list)
    channel: AIBrainChannel = "direct"
    provider_id: str = "default"
    group_name: str = ""
    member_name: str = ""
    merchant_id: int | None = None
    use_knowledge: bool = True
    allow_auto_answer: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)


class AIBrainChatResponse(BaseModel):
    answer: str
    provider_id: str
    provider_name: str
    model: str = ""
    mode: Literal["ai", "rule"] = "rule"
    channel: AIBrainChannel = "direct"
    risk_flags: list[str] = Field(default_factory=list)
    need_human: bool = False
    citations: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = 0
    sop_run_ids: list[str] = Field(default_factory=list)
    suggested_action: Literal["send", "review", "handoff"] = "review"
