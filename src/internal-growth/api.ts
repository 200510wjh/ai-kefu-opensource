import type {
  AgentPlan,
  AgentRunResponse,
  AIBrainChatRequest,
  AIBrainChatResponse,
  AIBrainProviderStatus,
  AnalyticsReport,
  ContentPlatform,
  ContentTask,
  CustomerInteraction,
  DailyWorkflowRun,
  DashboardSummary,
  DemandSignal,
  FollowUpTask,
  IntentLevel,
  Lead,
  LeadStage,
  OpportunityScore,
  ProspectCandidate,
  ProspectExternalSearchResponse,
  ProspectIntegrationProvider,
  ProspectIntegrationStatus,
  ProspectSourcePlatform,
  ProspectSearch,
  PublishingRecord,
  PublishingStatus,
  SalesAnalysis,
  SourceType,
  SOPMetrics,
  SOPRun,
  SOPTemplate,
  ToolRunRecord
} from './types';

const request = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(path, {
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
    ...options
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
};

export type DemandDraft = {
  name: string;
  source_type: SourceType;
  source_detail: string;
  industry: string;
  keywords: string[];
  pain_points: string;
  raw_text: string;
};

export type LeadDraft = {
  customer_name: string;
  source_platform: string;
  industry: string;
  demand: string;
  contact: string;
  intent_level: IntentLevel;
  stage: LeadStage;
  next_followup_at: string;
  next_action: string;
};

export type SalesAnalyzeDraft = {
  lead_id?: string;
  customer_name: string;
  industry: string;
  product_solution: string;
  conversation: string;
};

export type PublishingRecordDraft = {
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
};

export type ProspectSearchDraft = {
  platform: ProspectSourcePlatform;
  intent_goal: string;
  industry: string;
  city: string;
  keywords: string[];
  pain_keywords: string[];
  excluded_keywords: string[];
  notes: string;
};

export type ProspectCandidateDraft = {
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
};

export const internalGrowthApi = {
  dashboard: () => request<DashboardSummary>('/api/internal-growth/dashboard'),
  demands: () => request<DemandSignal[]>('/api/internal-growth/demands'),
  opportunities: () => request<OpportunityScore[]>('/api/internal-growth/opportunities'),
  contentTasks: () => request<ContentTask[]>('/api/internal-growth/content-tasks'),
  publishingRecords: () => request<PublishingRecord[]>('/api/internal-growth/publishing-records'),
  leads: () => request<Lead[]>('/api/internal-growth/leads'),
  prospectSearches: () => request<ProspectSearch[]>('/api/internal-growth/prospect-searches'),
  prospectCandidates: () => request<ProspectCandidate[]>('/api/internal-growth/prospect-candidates'),
  sourceIntegrations: () => request<ProspectIntegrationStatus[]>('/api/internal-growth/source-integrations'),
  followUpTasks: () => request<FollowUpTask[]>('/api/internal-growth/follow-up-tasks'),
  salesAnalyses: () => request<SalesAnalysis[]>('/api/internal-growth/sales/analyses'),
  reports: () => request<AnalyticsReport[]>('/api/internal-growth/analytics/reports'),
  createDemand: (payload: DemandDraft) =>
    request<DemandSignal>('/api/internal-growth/demands', {method: 'POST', body: JSON.stringify(payload)}),
  scoreDemand: (demandId: string) =>
    request<OpportunityScore>(`/api/internal-growth/demands/${demandId}/score`, {method: 'POST'}),
  generateContent: (demandId: string, platforms: ContentPlatform[]) =>
    request<ContentTask[]>('/api/internal-growth/content/generate', {
      method: 'POST',
      body: JSON.stringify({demand_id: demandId, platforms})
    }),
  createLead: (payload: LeadDraft) =>
    request<Lead>('/api/internal-growth/leads', {method: 'POST', body: JSON.stringify(payload)}),
  createProspectSearch: (payload: ProspectSearchDraft) =>
    request<ProspectSearch>('/api/internal-growth/prospect-searches', {method: 'POST', body: JSON.stringify(payload)}),
  createProspectCandidate: (payload: ProspectCandidateDraft) =>
    request<ProspectCandidate>('/api/internal-growth/prospect-candidates', {method: 'POST', body: JSON.stringify(payload)}),
  convertProspectCandidate: (candidateId: string) =>
    request<Lead>(`/api/internal-growth/prospect-candidates/${candidateId}/convert-lead`, {method: 'POST'}),
  prospectExternalResults: (searchId: string, provider: ProspectIntegrationProvider = 'searxng') =>
    request<ProspectExternalSearchResponse>(`/api/internal-growth/prospect-searches/${searchId}/external-results?provider=${provider}`, {method: 'POST'}),
  updateLead: (leadId: string, payload: Partial<LeadDraft>) =>
    request<Lead>(`/api/internal-growth/leads/${leadId}`, {method: 'PATCH', body: JSON.stringify(payload)}),
  updateContentTask: (taskId: string, payload: {status?: 'draft' | 'review' | 'published' | 'data_backfilled'; review_note?: string}) =>
    request<ContentTask>(`/api/internal-growth/content-tasks/${taskId}`, {method: 'PATCH', body: JSON.stringify(payload)}),
  createPublishingRecord: (payload: PublishingRecordDraft) =>
    request<PublishingRecord>('/api/internal-growth/publishing-records', {method: 'POST', body: JSON.stringify(payload)}),
  updatePublishingRecord: (recordId: string, payload: Partial<PublishingRecordDraft>) =>
    request<PublishingRecord>(`/api/internal-growth/publishing-records/${recordId}`, {method: 'PATCH', body: JSON.stringify(payload)}),
  interactions: (leadId: string) => request<CustomerInteraction[]>(`/api/internal-growth/leads/${leadId}/interactions`),
  createInteraction: (payload: {lead_id: string; channel: string; direction: 'inbound' | 'outbound' | 'note'; content: string}) =>
    request<CustomerInteraction>('/api/internal-growth/interactions', {method: 'POST', body: JSON.stringify(payload)}),
  analyzeChat: (payload: SalesAnalyzeDraft) =>
    request<SalesAnalysis>('/api/internal-growth/sales/analyze-chat', {method: 'POST', body: JSON.stringify(payload)}),
  weeklyReport: () => request<AnalyticsReport>('/api/internal-growth/analytics/weekly', {method: 'POST'}),
  runDailyWorkflow: () => request<DailyWorkflowRun>('/api/internal-growth/workflows/daily/run', {method: 'POST'}),
  workflowRuns: () => request<DailyWorkflowRun[]>('/api/internal-growth/workflows/runs'),
  sopTemplates: () => request<SOPTemplate[]>('/api/internal-growth/sop/templates'),
  sopRuns: () => request<SOPRun[]>('/api/internal-growth/sop/runs'),
  sopMetrics: () => request<SOPMetrics>('/api/internal-growth/sop/metrics'),
  aiBrainProviders: () => request<AIBrainProviderStatus[]>('/api/internal-growth/ai-brain/providers'),
  aiBrainChat: (payload: AIBrainChatRequest) =>
    request<AIBrainChatResponse>('/api/internal-growth/ai-brain/chat', {method: 'POST', body: JSON.stringify(payload)}),
  agentPlan: (payload: {task: string; context?: Record<string, unknown>}) =>
    request<AgentPlan>('/api/internal-growth/agent/plan', {method: 'POST', body: JSON.stringify(payload)}),
  agentRun: (payload: {task: string; context?: Record<string, unknown>; task_id?: string}) =>
    request<AgentRunResponse>('/api/internal-growth/agent/run', {method: 'POST', body: JSON.stringify(payload)}),
  toolRuns: () => request<ToolRunRecord[]>('/api/internal-growth/agent/tool-runs')
};
