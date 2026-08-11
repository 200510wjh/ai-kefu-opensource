export type SourceType = 'manual' | 'chat' | 'public' | 'authorized_data';
export type ContentPlatform = 'douyin' | 'xianyu' | 'wechat_moments';
export type ContentStatus = 'draft' | 'review' | 'published' | 'data_backfilled';
export type PublishingStatus = 'draft' | 'review' | 'published' | 'data_backfilled';
export type LeadStage = 'new' | 'contacted' | 'need_confirmed' | 'proposal' | 'quoted' | 'won' | 'lost';
export type IntentLevel = 'low' | 'medium' | 'high';
export type ProspectSourcePlatform = 'baidu' | 'douyin' | 'xianyu' | 'xiaohongshu' | 'kuaishou' | 'website' | 'manual_public';
export type ProspectSearchStatus = 'needs_human_collection' | 'imported' | 'closed';
export type ProspectCandidateStatus = 'new' | 'verified' | 'converted' | 'rejected';
export type ProspectIntegrationProvider = 'searxng' | 'firecrawl' | 'crawlee';

export type DemandSignal = {
  id: string;
  name: string;
  source_type: SourceType;
  source_detail: string;
  industry: string;
  keywords: string[];
  pain_points: string;
  raw_text: string;
  buying_possibility: number;
  recommended_action: string;
  created_at: string;
};

export type OpportunityScore = {
  id: string;
  demand_id: string;
  demand_strength: number;
  deal_probability: number;
  average_order_value: number;
  delivery_difficulty: number;
  fit_score: number;
  total_score: number;
  reasoning: string;
  recommended_decision: string;
  created_at: string;
};

export type ContentTask = {
  id: string;
  demand_id: string;
  opportunity_id: string;
  platform: ContentPlatform;
  status: ContentStatus;
  title: string;
  payload: Record<string, unknown>;
  review_note: string;
  created_at: string;
  updated_at: string;
};

export type PublishingRecord = {
  id: string;
  content_task_id: string;
  platform: ContentPlatform;
  status: PublishingStatus;
  scheduled_at: string;
  published_at: string;
  views: number;
  favorites: number;
  consultations: number;
  deals: number;
  revenue: number;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type DailyWorkflowRun = {
  id: string;
  status: 'queued' | 'running' | 'needs_human' | 'success' | 'failed';
  trigger: 'manual' | 'schedule';
  started_at: string;
  finished_at: string;
  demand_count: number;
  opportunity_count: number;
  generated_content_tasks: number;
  publishing_records_created: number;
  followup_tasks_created: number;
  needs_human_confirmation: boolean;
  logs: string[];
};

export type DashboardSummary = {
  today_opportunities: number;
  today_content_tasks: number;
  pending_followups: number;
  high_intent_leads: number;
  weekly: Record<string, number>;
  top_directions: Array<{
    demand_id: string;
    name: string;
    industry: string;
    score: number;
    decision: string;
    reasoning: string;
  }>;
  review_queue: ContentTask[];
  publishing_queue: PublishingRecord[];
  today_followups: FollowUpTask[];
  high_intent_lead_list: Lead[];
  latest_workflow_run: DailyWorkflowRun | null;
};

export type Lead = {
  id: string;
  customer_name: string;
  source_platform: string;
  industry: string;
  demand: string;
  contact: string;
  intent_level: IntentLevel;
  stage: LeadStage;
  next_followup_at: string;
  next_action: string;
  created_at: string;
  updated_at: string;
};

export type ProspectSearch = {
  id: string;
  platform: ProspectSourcePlatform;
  intent_goal: string;
  industry: string;
  city: string;
  keywords: string[];
  pain_keywords: string[];
  excluded_keywords: string[];
  notes: string;
  query: string;
  search_url: string;
  status: ProspectSearchStatus;
  guardrail_note: string;
  collection_steps: string[];
  created_at: string;
  updated_at: string;
};

export type ProspectCandidate = {
  id: string;
  search_id: string;
  source_platform: ProspectSourcePlatform;
  customer_name: string;
  industry: string;
  city: string;
  demand_signal: string;
  source_url: string;
  public_evidence: string;
  contact: string;
  fit_reason: string;
  intent_level: IntentLevel;
  status: ProspectCandidateStatus;
  converted_lead_id: string;
  created_at: string;
  updated_at: string;
};

export type ProspectIntegrationStatus = {
  provider: ProspectIntegrationProvider;
  name: string;
  license: string;
  repository_url: string;
  configured: boolean;
  mode: 'search_api' | 'scrape_api' | 'crawler_framework';
  status: 'ready' | 'needs_config' | 'planned';
  env_keys: string[];
  best_for: string;
  guardrail: string;
  next_action: string;
};

export type ProspectExternalResult = {
  search_id: string;
  provider: ProspectIntegrationProvider;
  title: string;
  url: string;
  snippet: string;
  engine: string;
  score: number;
};

export type ProspectExternalSearchResponse = {
  search_id: string;
  provider: ProspectIntegrationProvider;
  configured: boolean;
  query: string;
  results: ProspectExternalResult[];
  message: string;
  guardrail_note: string;
};

export type CustomerInteraction = {
  id: string;
  lead_id: string;
  channel: string;
  direction: 'inbound' | 'outbound' | 'note';
  content: string;
  ai_summary: string;
  created_at: string;
};

export type FollowUpTask = {
  id: string;
  lead_id: string;
  title: string;
  due_at: string;
  priority: 'low' | 'normal' | 'high';
  status: 'open' | 'done' | 'cancelled';
  created_at: string;
  updated_at: string;
};

export type SalesAnalysis = {
  id: string;
  lead_id: string;
  customer_profile: string;
  real_need: string;
  purchase_probability: number;
  next_strategy: string;
  reply_suggestion: string;
  risk_flags: string[];
  created_at: string;
};

export type AnalyticsReport = {
  id: string;
  report_type: 'weekly' | 'daily';
  period_start: string;
  period_end: string;
  summary: string;
  best_platforms: string[];
  best_content: string[];
  best_services: string[];
  stop_list: string[];
  next_actions: string[];
  created_at: string;
};

export type AgentPlan = {
  id: string;
  task_goal: string;
  needed_tools: string[];
  execution_steps: string[];
  risk_assessment: string;
  requires_human_confirmation: boolean;
  expected_outputs: string[];
  created_at: string;
};

export type ToolExecutionResult = {
  status: 'success' | 'failed' | 'blocked' | 'needs_human';
  tool_name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string;
  blocked_reason: string;
  retry_count: number;
  risk_level: 'low' | 'medium' | 'high';
};

export type AgentRunResponse = {
  task_id: string;
  plan: AgentPlan;
  tool_results: ToolExecutionResult[];
  status: 'success' | 'failed' | 'blocked' | 'needs_human';
  summary: string;
};

export type ToolRunRecord = {
  id: string;
  task_id: string;
  tool_name: string;
  input_hash: string;
  risk_level: 'low' | 'medium' | 'high';
  status: 'success' | 'failed' | 'blocked' | 'needs_human';
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string;
  blocked_reason: string;
  retry_count: number;
  duration_ms: number;
  created_at: string;
};

export type SOPStepTemplate = {
  id: string;
  name: string;
  action_type: string;
  description: string;
  requires_human_confirmation: boolean;
};

export type SOPTemplate = {
  id: string;
  name: string;
  module: string;
  description: string;
  trigger: string;
  enabled: boolean;
  steps: SOPStepTemplate[];
  guardrails: string[];
  frequency_limits: string[];
  updated_at: string;
};

export type SOPStepRun = {
  id: string;
  name: string;
  action_type: string;
  status: 'success' | 'failed' | 'needs_human' | 'skipped' | 'running';
  duration_ms: number;
  evidence: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error: string;
  created_at: string;
};

export type SOPRun = {
  id: string;
  template_id: string;
  template_name: string;
  status: 'queued' | 'pending' | 'running' | 'success' | 'completed' | 'failed' | 'needs_human';
  source: string;
  platform: string;
  session_id: string;
  customer_name: string;
  message_hash: string;
  action: string;
  intent_score: number;
  risk_flags: string[];
  knowledge_citations: string[];
  reply_text: string;
  reason: string;
  steps: SOPStepRun[];
  started_at: string;
  updated_at: string;
};

export type SOPMetrics = {
  today_consultations: number;
  ai_auto_replies: number;
  saved_minutes: number;
  high_intent_customers: number;
  pending_followups: number;
  handoff_count: number;
  auto_reply_rate: number;
  avg_response_ms: number;
  conversion_customers: number;
  sop_runs_today: number;
  advice: string[];
  recent_runs: SOPRun[];
};

export type AIBrainChannel = 'direct' | 'wechat_group' | 'douyin_group' | 'website_chat' | 'internal';

export type AIBrainMessage = {
  role: 'system' | 'user' | 'assistant';
  content: string;
  sender_name: string;
  created_at: string;
};

export type AIBrainProviderStatus = {
  id: string;
  name: string;
  kind: 'official' | 'relay' | 'self_hosted';
  base_url: string;
  model: string;
  configured: boolean;
  env_key: string;
  cost_note: string;
  safety_note: string;
};

export type AIBrainChatRequest = {
  question: string;
  messages: AIBrainMessage[];
  channel: AIBrainChannel;
  provider_id: string;
  group_name: string;
  member_name: string;
  merchant_id?: number | null;
  use_knowledge: boolean;
  allow_auto_answer: boolean;
  temperature?: number | null;
};

export type AIBrainChatResponse = {
  answer: string;
  provider_id: string;
  provider_name: string;
  model: string;
  mode: 'ai' | 'rule';
  channel: AIBrainChannel;
  risk_flags: string[];
  need_human: boolean;
  citations: Array<Record<string, unknown>>;
  latency_ms: number;
  sop_run_ids: string[];
  suggested_action: 'send' | 'review' | 'handoff';
};
