import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  BarChart3,
  Bot,
  Brain,
  Clipboard,
  Code2,
  Database,
  Headphones,
  Inbox,
  Image as ImageIcon,
  ListChecks,
  LogIn,
  Package,
  PlugZap,
  RefreshCw,
  Save,
  Send,
  Settings,
  ShieldAlert,
  Sparkles,
  Target,
  Users,
  Workflow
} from 'lucide-react';
import InternalGrowthApp from './internal-growth/App';
import './styles.css';

const API_PREFIX = import.meta.env.BASE_URL === '/' ? '' : import.meta.env.BASE_URL.replace(/\/$/, '');
const apiUrl = (path: string) => `${API_PREFIX}${path.startsWith('/') ? path : `/${path}`}`;
document.documentElement.dataset.build = '20260720-cache-repair';

type Section =
  | 'enterprise'
  | 'acquisition'
  | 'aiService'
  | 'crm'
  | 'knowledge'
  | 'products'
  | 'automation'
  | 'aiDecision'
  | 'analytics'
  | 'settings';

type FAQItem = {
  question: string;
  answer: string;
};

type MerchantProfile = {
  id?: number | null;
  username: string;
  merchant_code: string;
  business_name: string;
  industry: string;
  business_intro: string;
  products_services: string;
  pricing: string;
  promotions: string;
  hours: string;
  contact: string;
  faq: FAQItem[];
  welcome_message: string;
};

type DashboardOverview = {
  today_conversations: number;
  auto_replies: number;
  leads: number;
  handoff_needed: number;
  ai_mode: string;
  knowledge_items: number;
  enabled_channels: number;
};

type ChannelConfig = {
  channel: string;
  display_name: string;
  mode: 'assist' | 'official_api' | 'manual';
  status: 'draft' | 'ready' | 'connected' | 'blocked';
  official_api_url: string;
  webhook_url: string;
  auto_reply_enabled: boolean;
  handoff_required: boolean;
  notes: string;
};

type ConnectorStatus = {
  ok: boolean;
  status: 'disabled' | 'not_configured' | 'pending_auth' | 'connected' | 'failed' | 'assist_only';
  message: string;
  data?: Record<string, unknown>;
};

type ConnectorAuth = {
  key: string;
  label: string;
  status: string;
  auth_mode: string;
  account_name: string;
  callback_url: string;
  read_only_enabled: boolean;
  send_enabled: boolean;
  safety_level: 'read_only' | 'draft_only' | 'requires_confirmation' | 'disabled';
  capabilities: string[];
  configured_fields: string[];
  missing_fields: string[];
  last_sync_at: string;
  notes: string;
};

type ConnectorOAuthDraft = {
  authorize_url: string;
  client_id: string;
  client_secret: string;
  token_url: string;
  messages_url: string;
  leads_url: string;
  send_url: string;
  scope: string;
};

const emptyConnectorOAuthDraft = (): ConnectorOAuthDraft => ({
  authorize_url: '',
  client_id: '',
  client_secret: '',
  token_url: '',
  messages_url: '',
  leads_url: '',
  send_url: '',
  scope: ''
});

const connectorOAuthDraftOrDefault = (draft?: ConnectorOAuthDraft): ConnectorOAuthDraft => ({
  ...emptyConnectorOAuthDraft(),
  ...(draft || {})
});

function oauthNonsecretConfig(draft: ConnectorOAuthDraft, redirectUri: string): Record<string, string> {
  const config: Record<string, string> = {redirect_uri: redirectUri};
  if (draft.authorize_url.trim()) config.authorize_url = draft.authorize_url.trim();
  if (draft.client_id.trim()) config.client_id = draft.client_id.trim();
  if (draft.token_url.trim()) config.token_url = draft.token_url.trim();
  if (draft.messages_url.trim()) config.messages_url = draft.messages_url.trim();
  if (draft.leads_url.trim()) config.leads_url = draft.leads_url.trim();
  if (draft.send_url.trim()) config.send_url = draft.send_url.trim();
  if (draft.scope.trim()) config.scope = draft.scope.trim();
  return config;
}

type ConnectorOAuthStart = {
  connector: string;
  status: 'ready' | 'setup_required';
  state: string;
  auth_url: string;
  callback_url: string;
  expires_at: string;
  next_action: string;
};

type ConnectorOAuthExchange = {
  connector: string;
  status: 'connected' | 'setup_required' | 'failed';
  configured_fields: string[];
  token_endpoint_host: string;
  expires_at: string;
  next_action: string;
};

type ConnectorOAuthRefresh = {
  connector: string;
  status: 'refreshed' | 'setup_required' | 'failed';
  configured_fields: string[];
  token_endpoint_host: string;
  expires_at: string;
  next_action: string;
};

type ConnectorReadPull = {
  connector: string;
  resource: 'messages' | 'leads';
  status: 'pulled' | 'setup_required' | 'failed';
  imported: number;
  duplicates: number;
  skipped: number;
  endpoint_host: string;
  workflow_run_ids: string[];
  next_action: string;
};

type ConnectorHealthItem = {
  connector: string;
  label: string;
  status: 'pass' | 'warning' | 'fail';
  auth_status: string;
  auth_mode: string;
  read_only_enabled: boolean;
  send_enabled: boolean;
  configured_fields: string[];
  alerts: string[];
  pending_dispatches: number;
  failed_dispatches: number;
  recent_failures: number;
  last_sync_at: string;
  token_expires_at: string;
  next_action: string;
};

type ConnectorHealthOverview = {
  status: 'pass' | 'warning' | 'fail';
  summary: string;
  items: ConnectorHealthItem[];
  alerts: string[];
  created_at: string;
};

type ConnectorSetupTask = {
  id: string;
  connector: string;
  label: string;
  category: string;
  severity: 'info' | 'warning' | 'blocker';
  status: 'done' | 'todo' | 'blocked';
  title: string;
  evidence: string;
  next_action: string;
  required_fields: string[];
  configured_fields: string[];
  endpoint_hint: string;
};

type ConnectorSetupGuide = {
  status: 'ready' | 'needs_setup' | 'blocked';
  summary: string;
  counts: Record<string, number>;
  tasks: ConnectorSetupTask[];
  created_at: string;
};

type ReplyDraftQueueItem = {
  id: number;
  connector: string;
  session_id: string;
  customer_id?: number | null;
  external_id: string;
  customer_name: string;
  source_text: string;
  draft_text: string;
  status: 'pending' | 'approved' | 'rejected';
  risk_flags: string[];
  intent_score: number;
  workflow_run_id: string;
  reviewer: string;
  reviewer_note: string;
  created_at: string;
  updated_at: string;
  reviewed_at: string;
};

type ReplyDispatchItem = {
  id: number;
  draft_id: number;
  connector: string;
  customer_id?: number | null;
  external_id: string;
  dispatch_mode: 'manual_copy' | 'api_send';
  status: 'manual_ready' | 'blocked' | 'sent' | 'send_failed' | 'revoked';
  draft_text: string;
  risk_flags: string[];
  operator: string;
  operator_note: string;
  revoke_note: string;
  created_at: string;
  updated_at: string;
  revoked_at: string;
  sent_at: string;
  send_request_id: string;
  send_error: string;
  next_action: string;
};

type TeamMember = {
  id: number;
  name: string;
  email: string;
  role: string;
  status: string;
  permissions: string[];
  created_at: string;
  updated_at: string;
};

type AuditLog = {
  id: number;
  actor: string;
  action: string;
  target_type: string;
  target_id: string;
  summary: string;
  metadata: Record<string, unknown>;
  ip: string;
  created_at: string;
};

type MerchantSubscription = {
  merchant_id: number;
  plan_id: string;
  status: string;
  ai_quota: number;
  workflow_quota: number;
  connector_quota: number;
  seats: number;
  updated_at: string;
};

type UsageRecord = {
  id: number;
  usage_type: string;
  quantity: number;
  source: string;
  target_id: string;
  created_at: string;
};

type UsageSummary = {
  period: string;
  subscription: MerchantSubscription;
  used: Record<string, number>;
  remaining: Record<string, number>;
  recent: UsageRecord[];
};

type BusinessReport = {
  id: number;
  report_type: string;
  title: string;
  summary: string;
  content: string;
  created_at: string;
};

type ReportExport = {
  report_id: number;
  format: 'markdown' | 'pdf' | 'docx';
  filename: string;
  artifact_url: string;
  content: string;
};

type DeliveryArtifact = {
  name: string;
  artifact_url: string;
  kind: 'markdown' | 'zip' | 'json';
};

type DeliveryPack = {
  id: string;
  customer_name: string;
  title: string;
  summary: string;
  artifacts: DeliveryArtifact[];
  zip_url: string;
  created_at: string;
};

type IntegrationWorkOrderItem = {
  connector: string;
  label: string;
  category: string;
  priority: 'low' | 'medium' | 'high';
  status: 'done' | 'todo' | 'blocked';
  required_fields: string[];
  configured_fields: string[];
  callback_url: string;
  endpoint_hint: string;
  owner: string;
  next_action: string;
  acceptance_check: string;
};

type IntegrationWorkOrder = {
  id: string;
  title: string;
  status: 'ready' | 'needs_setup' | 'blocked';
  summary: string;
  artifact_url: string;
  items: IntegrationWorkOrderItem[];
  created_at: string;
};

type IntegrationDryRunCheck = {
  connector: string;
  label: string;
  check: string;
  status: 'pass' | 'warning' | 'fail';
  evidence: string;
  next_action: string;
};

type IntegrationDryRun = {
  id: string;
  status: 'pass' | 'warning' | 'fail';
  summary: string;
  checks: IntegrationDryRunCheck[];
  artifact_url: string;
  created_at: string;
};

type IntegrationTaskSyncResult = {
  status: 'synced' | 'nothing_to_sync';
  created: number;
  skipped_existing: number;
  source_dry_run_status: 'pass' | 'warning' | 'fail';
  tasks: CRMTask[];
  summary: string;
};

type IntegrationTaskReconcileResult = {
  status: 'reconciled' | 'nothing_closed';
  closed: number;
  still_open: number;
  source_dry_run_status: 'pass' | 'warning' | 'fail';
  closed_tasks: CRMTask[];
  remaining_checks: IntegrationDryRunCheck[];
  summary: string;
};

type IntegrationTaskSLAItem = {
  task_id: number;
  connector: string;
  check: string;
  title: string;
  owner: string;
  priority: 'low' | 'normal' | 'high';
  due_at: string;
  sla_status: 'overdue' | 'due_today' | 'upcoming' | 'unscheduled';
  age_hours: number;
  created_at: string;
};

type IntegrationTaskSLABoard = {
  status: 'clear' | 'attention' | 'overdue';
  summary: string;
  total_open: number;
  overdue: number;
  due_today: number;
  upcoming: number;
  unscheduled: number;
  by_connector: Record<string, number>;
  by_owner: Record<string, number>;
  items: IntegrationTaskSLAItem[];
  created_at: string;
};

type IntegrationSLAEscalation = {
  id: string;
  status: 'clear' | 'attention' | 'overdue';
  summary: string;
  artifact_url: string;
  items: IntegrationTaskSLAItem[];
  created_at: string;
};

type IntegrationSLANotice = {
  id: string;
  status: 'clear' | 'attention' | 'overdue';
  channel: 'copy' | 'wecom' | 'dingtalk' | 'email';
  recipient: string;
  subject: string;
  draft_text: string;
  artifact_url: string;
  items: IntegrationTaskSLAItem[];
  created_at: string;
};

type IntegrationSLANoticeReceipt = {
  id: string;
  status: 'recorded' | 'partial' | 'closed';
  notice_id: string;
  recipient: string;
  outcome: 'acknowledged' | 'needs_help' | 'completed';
  summary: string;
  artifact_url: string;
  confirmed_task_ids: number[];
  ignored_task_ids: number[];
  closed_tasks: CRMTask[];
  remaining_open: number;
  created_at: string;
};

type IntegrationSLALoopReport = {
  id: string;
  status: 'clear' | 'attention' | 'overdue';
  summary: string;
  artifact_url: string;
  total_open: number;
  overdue: number;
  due_today: number;
  unscheduled: number;
  receipts_recent: number;
  closed_recent: number;
  audit_events: AuditLog[];
  created_at: string;
};

type PlatformAcceptanceScenario =
  | 'official_auth'
  | 'callback'
  | 'read_message'
  | 'read_lead'
  | 'draft_reply'
  | 'controlled_send'
  | 'ops_health'
  | 'customer_trial';

type PlatformAcceptanceEvidence = {
  id: string;
  connector: string;
  scenario: PlatformAcceptanceScenario;
  result: 'pass' | 'warning' | 'fail';
  account_label: string;
  operator: string;
  summary: string;
  evidence_url: string;
  artifact_url: string;
  occurred_at: string;
  created_at: string;
};

type PlatformAcceptanceReport = {
  id: string;
  status: 'ready' | 'partial' | 'blocked';
  summary: string;
  artifact_url: string;
  evidence_total: number;
  passed: number;
  warnings: number;
  failed: number;
  required_scenarios: PlatformAcceptanceScenario[];
  missing_scenarios: PlatformAcceptanceScenario[];
  evidence: PlatformAcceptanceEvidence[];
  created_at: string;
};

type PlatformAcceptanceGapSyncResult = {
  id: string;
  status: 'synced' | 'preview' | 'nothing_to_sync';
  summary: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  created: number;
  skipped_existing: number;
  tasks: CRMTask[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceGapReconcileResult = {
  id: string;
  status: 'reconciled' | 'preview' | 'nothing_closed';
  summary: string;
  passed_scenarios: PlatformAcceptanceScenario[];
  closed: number;
  still_open: number;
  closed_tasks: CRMTask[];
  open_tasks: CRMTask[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceChecklistItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_evidence' | 'needs_review';
  target_id: string;
  task_id?: number | null;
  task_status: string;
  owner: string;
  due_at: string;
  required_evidence: string[];
  capture_steps: string[];
  evidence_count: number;
  latest_evidence_result: string;
  latest_evidence_url: string;
  next_action: string;
};

type PlatformAcceptanceEvidenceChecklist = {
  id: string;
  status: 'complete' | 'collecting' | 'blocked';
  summary: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  items: PlatformAcceptanceEvidenceChecklistItem[];
  tasks: CRMTask[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceNotice = {
  id: string;
  status: 'ready' | 'empty';
  channel: 'copy' | 'wecom' | 'dingtalk' | 'email';
  recipient: string;
  subject: string;
  draft_text: string;
  artifact_url: string;
  items: PlatformAcceptanceEvidenceChecklistItem[];
  created_at: string;
};

type PlatformAcceptanceEvidenceReceiptScenario = {
  scenario: PlatformAcceptanceScenario;
  outcome: 'acknowledged' | 'needs_help' | 'submitted';
  note: string;
  evidence_url: string;
};

type PlatformAcceptanceEvidenceReceipt = {
  id: string;
  status: 'recorded' | 'needs_help' | 'submitted';
  notice_id: string;
  recipient: string;
  outcome: 'acknowledged' | 'needs_help' | 'submitted';
  summary: string;
  scenario_receipts: PlatformAcceptanceEvidenceReceiptScenario[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceReviewTaskItem = {
  receipt_id: string;
  scenario: PlatformAcceptanceScenario;
  outcome: 'needs_help' | 'submitted';
  target_id: string;
  task_id?: number | null;
  task_status: string;
  owner: string;
  due_at: string;
  note: string;
  evidence_url: string;
  next_action: string;
};

type PlatformAcceptanceEvidenceReviewTaskSync = {
  id: string;
  status: 'synced' | 'preview' | 'nothing_to_sync';
  summary: string;
  created: number;
  skipped_existing: number;
  submitted: number;
  needs_help: number;
  items: PlatformAcceptanceEvidenceReviewTaskItem[];
  tasks: CRMTask[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceReviewDecision = {
  id: string;
  status: 'recorded' | 'evidence_registered' | 'needs_redaction' | 'rejected';
  scenario: PlatformAcceptanceScenario;
  decision: 'approved' | 'needs_redaction' | 'rejected';
  summary: string;
  review_task_ids: number[];
  closed_review_tasks: CRMTask[];
  evidence?: PlatformAcceptanceEvidence | null;
  gap_reconcile?: PlatformAcceptanceGapReconcileResult | null;
  resubmission_link?: PlatformAcceptanceEvidenceSubmissionLink | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceReviewDeskScenario = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'ready_to_review' | 'needs_customer_help' | 'needs_evidence';
  outcome: 'acknowledged' | 'needs_help' | 'submitted' | 'none';
  receipt_id: string;
  task_id?: number | null;
  task_status: string;
  owner: string;
  due_at: string;
  evidence_url: string;
  note: string;
  can_register_pass: boolean;
  recommended_decision: 'approved' | 'needs_redaction' | 'rejected' | 'none';
  next_action: string;
};

type PlatformAcceptanceReviewDesk = {
  id: string;
  status: 'ready_for_review' | 'waiting_customer' | 'complete';
  summary: string;
  required_total: number;
  passed: number;
  ready_to_review: number;
  needs_customer_help: number;
  needs_evidence: number;
  scenarios: PlatformAcceptanceReviewDeskScenario[];
  review_sync: PlatformAcceptanceEvidenceReviewTaskSync;
  missing_scenarios: PlatformAcceptanceScenario[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceReviewExecutionRunItem = {
  scenario: PlatformAcceptanceScenario;
  decision: 'approved' | 'needs_redaction' | 'rejected';
  status: 'preview' | 'executed' | 'blocked';
  review_task_ids: number[];
  evidence_registered: boolean;
  closed_review_tasks: number;
  gap_closed: number;
  resubmission_url: string;
  artifact_url: string;
  error: string;
  next_action: string;
};

type PlatformAcceptanceReviewExecutionRun = {
  id: string;
  status: 'preview' | 'executed' | 'partial' | 'blocked';
  summary: string;
  requested: number;
  executed: number;
  blocked: number;
  evidence_registered: number;
  gap_closed: number;
  items: PlatformAcceptanceReviewExecutionRunItem[];
  decisions: PlatformAcceptanceEvidenceReviewDecision[];
  desk_before?: PlatformAcceptanceReviewDesk | null;
  desk_after?: PlatformAcceptanceReviewDesk | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceUrlPrecheckItem = {
  scenario: PlatformAcceptanceScenario;
  evidence_url: string;
  status: 'ok' | 'warning' | 'blocked';
  http_status: number;
  content_type: string;
  host: string;
  final_url: string;
  reason: string;
  next_action: string;
};

type PlatformAcceptanceEvidenceUrlPrecheckRun = {
  id: string;
  status: 'ok' | 'warning' | 'blocked';
  summary: string;
  checked: number;
  ok: number;
  warning: number;
  blocked: number;
  items: PlatformAcceptanceEvidenceUrlPrecheckItem[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceImportRequestItem = {
  scenario: PlatformAcceptanceScenario;
  connector: string;
  account_label: string;
  operator: string;
  evidence_note: string;
  evidence_url: string;
  occurred_at: string;
  review_task_ids: number[];
};

type PlatformAcceptanceEvidenceImportRunItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'ready' | 'imported' | 'missing' | 'blocked';
  evidence_url: string;
  url_precheck?: PlatformAcceptanceEvidenceUrlPrecheckItem | null;
  review_task_ids: number[];
  evidence_id: string;
  decision_id: string;
  gap_closed: number;
  error: string;
  next_action: string;
};

type PlatformAcceptanceEvidenceImportRun = {
  id: string;
  status: 'preview' | 'imported' | 'partial' | 'blocked';
  summary: string;
  required_total: number;
  supplied: number;
  ready: number;
  imported: number;
  blocked: number;
  evidence_registered: number;
  gap_closed: number;
  missing_scenarios: PlatformAcceptanceScenario[];
  items: PlatformAcceptanceEvidenceImportRunItem[];
  decisions: PlatformAcceptanceEvidenceReviewDecision[];
  report_before?: PlatformAcceptanceReport | null;
  report_after?: PlatformAcceptanceReport | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceManifestLink = {
  id: string;
  status: 'ready' | 'empty';
  customer_name: string;
  owner: string;
  recipient: string;
  scenarios: PlatformAcceptanceScenario[];
  manifest_url: string;
  token: string;
  expires_at: string;
  draft_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceManifestSubmission = {
  id: string;
  status: 'preview_ready' | 'needs_work' | 'empty';
  customer_name: string;
  recipient: string;
  submitter: string;
  scenarios: PlatformAcceptanceScenario[];
  import_preview: PlatformAcceptanceEvidenceImportRun;
  receipt: PlatformAcceptanceEvidenceReceipt;
  review_sync?: PlatformAcceptanceEvidenceReviewTaskSync | null;
  ready: number;
  blocked: number;
  missing_scenarios: PlatformAcceptanceScenario[];
  summary: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceManifestInboxItem = {
  submission_id: string;
  status: string;
  ready: number;
  blocked: number;
  scenarios: PlatformAcceptanceScenario[];
  missing_scenarios: PlatformAcceptanceScenario[];
  import_preview_id: string;
  import_preview_artifact_url: string;
  submission_artifact_url: string;
  receipt_id: string;
  review_sync_id: string;
  created_at: string;
  next_action: string;
};

type PlatformAcceptanceEvidenceManifestInbox = {
  id: string;
  status: 'empty' | 'ready_to_import' | 'needs_customer' | 'mixed';
  summary: string;
  total: number;
  ready: number;
  blocked: number;
  items: PlatformAcceptanceEvidenceManifestInboxItem[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestImportQueueItem = {
  submission_id: string;
  status: 'ready_to_import' | 'recovered_for_review' | 'needs_customer' | 'needs_manual_review';
  ready: number;
  blocked: number;
  scenarios: PlatformAcceptanceScenario[];
  missing_scenarios: PlatformAcceptanceScenario[];
  import_items: PlatformAcceptanceEvidenceImportRequestItem[];
  source: 'metadata' | 'artifact' | 'manual';
  recovered: boolean;
  recovery_review_id: string;
  recovery_review_status: string;
  recovery_review_decision: string;
  import_preview_artifact_url: string;
  submission_artifact_url: string;
  receipt_id: string;
  review_sync_id: string;
  created_at: string;
  next_action: string;
};

type PlatformAcceptanceManifestImportQueue = {
  id: string;
  status: 'empty' | 'ready' | 'recovered' | 'needs_customer' | 'needs_manual_review' | 'mixed';
  summary: string;
  total: number;
  ready: number;
  recovered: number;
  needs_customer: number;
  needs_manual_review: number;
  items: PlatformAcceptanceManifestImportQueueItem[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestRecoveryReview = {
  id: string;
  status: 'preview' | 'accepted_for_preview' | 'needs_customer_resubmission' | 'rejected';
  submission_id: string;
  decision: 'accepted_for_preview' | 'needs_customer_resubmission' | 'rejected';
  source: 'metadata' | 'artifact' | 'manual';
  recovered: boolean;
  import_items: PlatformAcceptanceEvidenceImportRequestItem[];
  scenarios: PlatformAcceptanceScenario[];
  resubmission_scenarios: PlatformAcceptanceScenario[];
  import_preview_artifact_url: string;
  submission_artifact_url: string;
  manifest_link?: PlatformAcceptanceEvidenceManifestLink | null;
  queue_item?: PlatformAcceptanceManifestImportQueueItem | null;
  review_note: string;
  summary: string;
  next_action: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestRecoveryResubmissionRunItem = {
  submission_id: string;
  status: 'would_request' | 'requested' | 'already_requested' | 'skipped' | 'blocked';
  source: 'metadata' | 'artifact' | 'manual';
  recovered: boolean;
  recovery_review_status: string;
  scenarios: PlatformAcceptanceScenario[];
  import_items: number;
  manifest_url: string;
  manifest_artifact_url: string;
  review_id: string;
  next_action: string;
};

type PlatformAcceptanceManifestRecoveryResubmissionRun = {
  id: string;
  status: 'preview' | 'executed' | 'partial' | 'empty';
  summary: string;
  total: number;
  would_request: number;
  requested: number;
  already_requested: number;
  skipped: number;
  blocked: number;
  items: PlatformAcceptanceManifestRecoveryResubmissionRunItem[];
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestResubmissionTrackerItem = {
  submission_id: string;
  status: 'waiting_customer' | 'ready_for_review' | 'needs_fix' | 'stale' | 'complete' | 'missing_link';
  manifest_link_id: string;
  recovery_review_id: string;
  scenarios: PlatformAcceptanceScenario[];
  missing_scenarios: PlatformAcceptanceScenario[];
  latest_submission_id: string;
  latest_submission_status: string;
  latest_submission_artifact_url: string;
  import_preview_artifact_url: string;
  wait_hours: number;
  escalation: 'none' | 'watch' | 'urgent';
  next_action: string;
};

type PlatformAcceptanceManifestResubmissionTracker = {
  id: string;
  status: 'ready_for_signoff' | 'ready_for_review' | 'waiting_customer' | 'stale' | 'needs_ops' | 'empty';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  evidence_status: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  total: number;
  waiting_customer: number;
  ready_for_review: number;
  needs_fix: number;
  stale: number;
  complete: number;
  missing_link: number;
  items: PlatformAcceptanceManifestResubmissionTrackerItem[];
  reminder_draft: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestResubmissionReminderRunItem = {
  submission_id: string;
  tracker_status: string;
  action_status: 'preview' | 'task_created' | 'task_existing' | 'skipped' | 'blocked';
  task?: CRMTask | null;
  priority: 'low' | 'normal' | 'high';
  due_at: string;
  title: string;
  next_action: string;
};

type PlatformAcceptanceManifestResubmissionReminderRun = {
  id: string;
  status: 'preview' | 'created' | 'clear' | 'partial' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  create_tasks: boolean;
  total: number;
  created: number;
  existing: number;
  skipped: number;
  blocked: number;
  tracker?: PlatformAcceptanceManifestResubmissionTracker | null;
  items: PlatformAcceptanceManifestResubmissionReminderRunItem[];
  reminder_draft: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceManifestFollowupRunItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'ready_to_import' | 'needs_resubmission' | 'awaiting_customer';
  latest_submission_id: string;
  latest_submission_status: string;
  import_preview_artifact_url: string;
  submission_artifact_url: string;
  requirement: string;
  next_action: string;
};

type PlatformAcceptanceManifestFollowupRun = {
  id: string;
  status: 'ready_for_signoff' | 'ready_for_review' | 'waiting_for_customer' | 'needs_ops';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  evidence_status: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  inbox_status: string;
  inbox_total: number;
  inbox_ready: number;
  inbox_blocked: number;
  manifest_url: string;
  manifest_artifact_url: string;
  items: PlatformAcceptanceManifestFollowupRunItem[];
  reminder_draft: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceSubmissionLink = {
  id: string;
  status: 'ready' | 'empty';
  recipient: string;
  owner: string;
  scenarios: PlatformAcceptanceScenario[];
  submit_url: string;
  token: string;
  expires_at: string;
  draft_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceEvidenceCustomerSubmission = {
  id: string;
  status: 'received' | 'needs_help' | 'submitted';
  recipient: string;
  submitter: string;
  scenarios: PlatformAcceptanceScenario[];
  receipt: PlatformAcceptanceEvidenceReceipt;
  review_sync: PlatformAcceptanceEvidenceReviewTaskSync;
  summary: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceSprintScenarioItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_evidence' | 'needs_review';
  task_id?: number | null;
  task_status: string;
  owner: string;
  due_at: string;
  evidence_count: number;
  latest_evidence_result: string;
  latest_evidence_url: string;
  required_evidence: string[];
  capture_steps: string[];
  next_action: string;
  submission_link?: PlatformAcceptanceEvidenceSubmissionLink | null;
};

type PlatformAcceptanceSprintPack = {
  id: string;
  status: 'complete' | 'collecting' | 'empty';
  summary: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  items: PlatformAcceptanceSprintScenarioItem[];
  tasks: CRMTask[];
  links: PlatformAcceptanceEvidenceSubmissionLink[];
  checklist?: PlatformAcceptanceEvidenceChecklist | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceLiveRunScenario = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_review' | 'needs_help' | 'needs_evidence';
  evidence_count: number;
  latest_evidence_result: string;
  latest_evidence_url: string;
  gap_task_id?: number | null;
  gap_task_status: string;
  review_task_count: number;
  customer_submission_count: number;
  receipt_count: number;
  submission_link_count: number;
  submission_link?: PlatformAcceptanceEvidenceSubmissionLink | null;
  next_action: string;
};

type PlatformAcceptanceLiveRun = {
  id: string;
  status: 'ready_for_signoff' | 'reviewing' | 'collecting' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  required_total: number;
  passed: number;
  missing: number;
  needs_review: number;
  needs_help: number;
  scenarios: PlatformAcceptanceLiveRunScenario[];
  sprint_pack?: PlatformAcceptanceSprintPack | null;
  signoff_draft: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceFinalSignoffLink = {
  id: string;
  status: 'ready' | 'blocked';
  customer_name: string;
  owner: string;
  recipient: string;
  signer_name: string;
  signer_role: string;
  live_run: PlatformAcceptanceLiveRun;
  missing_scenarios: PlatformAcceptanceScenario[];
  submit_url: string;
  token: string;
  expires_at: string;
  signoff_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceJointDebugScenario = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_setup' | 'failed' | 'skipped';
  connector: string;
  evidence_summary: string;
  next_action: string;
  registered_evidence?: PlatformAcceptanceEvidence | null;
  pull_result?: ConnectorReadPull | null;
};

type PlatformAcceptanceJointDebugRun = {
  id: string;
  status: 'ready_for_signoff' | 'partial' | 'blocked';
  summary: string;
  customer_name: string;
  operator: string;
  connectors: string[];
  passed: number;
  missing: number;
  scenarios: PlatformAcceptanceJointDebugScenario[];
  live_run?: PlatformAcceptanceLiveRun | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceGapClosureItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_config' | 'needs_customer' | 'failed' | 'ready';
  connector: string;
  missing_fields: string[];
  evidence_summary: string;
  next_action: string;
  registered_evidence?: PlatformAcceptanceEvidence | null;
  submission_link?: PlatformAcceptanceEvidenceSubmissionLink | null;
  exchange_result?: ConnectorOAuthExchange | null;
  pull_result?: ConnectorReadPull | null;
};

type PlatformAcceptanceGapClosureRun = {
  id: string;
  status: 'ready_for_signoff' | 'partial' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  missing_before: PlatformAcceptanceScenario[];
  missing_after: PlatformAcceptanceScenario[];
  items: PlatformAcceptanceGapClosureItem[];
  joint_debug?: PlatformAcceptanceJointDebugRun | null;
  gap_sync?: PlatformAcceptanceGapSyncResult | null;
  final_gate?: PlatformAcceptanceFinalSignoffLink | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceOwnerActionItem = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'needs_customer' | 'needs_ops' | 'ready';
  connector: string;
  required_fields: string[];
  configured_fields: string[];
  callback_url: string;
  action_text: string;
  secure_note: string;
  submission_link?: PlatformAcceptanceEvidenceSubmissionLink | null;
};

type PlatformAcceptanceOwnerActionPack = {
  id: string;
  status: 'complete' | 'ready_for_customer' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  items: PlatformAcceptanceOwnerActionItem[];
  draft_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceOwnerClosureConnectorResult = {
  connector: string;
  status: 'applied' | 'skipped' | 'failed';
  auth_status: string;
  auth_mode: string;
  configured_fields: string[];
  missing_fields: string[];
  applied_fields: string[];
  secret_field_names: string[];
  next_action: string;
};

type PlatformAcceptanceOwnerClosureRun = {
  id: string;
  status: 'ready_for_signoff' | 'partial' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  missing_before: PlatformAcceptanceScenario[];
  missing_after: PlatformAcceptanceScenario[];
  connector_results: PlatformAcceptanceOwnerClosureConnectorResult[];
  receipt?: PlatformAcceptanceEvidenceReceipt | null;
  review_sync?: PlatformAcceptanceEvidenceReviewTaskSync | null;
  gap_closure?: PlatformAcceptanceGapClosureRun | null;
  owner_action_pack?: PlatformAcceptanceOwnerActionPack | null;
  final_gate?: PlatformAcceptanceFinalSignoffLink | null;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceOwnerClosureLink = {
  id: string;
  status: 'ready' | 'empty';
  customer_name: string;
  owner: string;
  recipient: string;
  connectors: string[];
  submit_url: string;
  token: string;
  expires_at: string;
  draft_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceAutoWatchAction = {
  step: string;
  status: 'done' | 'waiting' | 'blocked' | 'skipped';
  summary: string;
  next_action: string;
  artifact_url: string;
};

type PlatformAcceptanceAutoWatchRun = {
  id: string;
  status: 'ready_for_signoff' | 'waiting_for_customer' | 'needs_ops' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  missing_before: PlatformAcceptanceScenario[];
  missing_after: PlatformAcceptanceScenario[];
  actions: PlatformAcceptanceAutoWatchAction[];
  review_sync?: PlatformAcceptanceEvidenceReviewTaskSync | null;
  joint_debug?: PlatformAcceptanceJointDebugRun | null;
  gap_closure?: PlatformAcceptanceGapClosureRun | null;
  owner_closure_link?: PlatformAcceptanceOwnerClosureLink | null;
  owner_action_pack?: PlatformAcceptanceOwnerActionPack | null;
  final_gate?: PlatformAcceptanceFinalSignoffLink | null;
  next_probe_at: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceWatchBoardScenario = {
  scenario: PlatformAcceptanceScenario;
  status: 'passed' | 'waiting_customer' | 'needs_ops' | 'overdue';
  owner: string;
  due_at: string;
  wait_hours: number;
  escalation: 'none' | 'watch' | 'urgent';
  task_id?: number | null;
  latest_action: string;
  latest_action_at: string;
  latest_artifact_url: string;
  next_action: string;
};

type PlatformAcceptanceWatchBoard = {
  id: string;
  status: 'ready_for_signoff' | 'waiting_for_customer' | 'needs_ops' | 'overdue';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  evidence_status: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  scenarios: PlatformAcceptanceWatchBoardScenario[];
  latest_auto_watch: Record<string, unknown>;
  open_gap_tasks: number;
  reminder_draft: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceCustomerRoomLink = {
  id: string;
  status: 'ready' | 'blocked';
  customer_name: string;
  owner: string;
  recipient: string;
  evidence_status: string;
  missing_scenarios: PlatformAcceptanceScenario[];
  room_url: string;
  token: string;
  expires_at: string;
  evidence_submission_url: string;
  owner_closure_url: string;
  final_signoff_url: string;
  watch_board_url: string;
  draft_text: string;
  artifact_url: string;
  created_at: string;
};

type PlatformAcceptanceFinalClosureRun = {
  id: string;
  status: 'ready_for_signoff' | 'waiting_customer' | 'needs_ops' | 'blocked';
  summary: string;
  customer_name: string;
  owner: string;
  recipient: string;
  missing_before: PlatformAcceptanceScenario[];
  missing_after: PlatformAcceptanceScenario[];
  report_before?: PlatformAcceptanceReport | null;
  report_after?: PlatformAcceptanceReport | null;
  tracker?: PlatformAcceptanceManifestResubmissionTracker | null;
  reminder_run?: PlatformAcceptanceManifestResubmissionReminderRun | null;
  auto_watch?: PlatformAcceptanceAutoWatchRun | null;
  customer_room?: PlatformAcceptanceCustomerRoomLink | null;
  final_gate?: PlatformAcceptanceFinalSignoffLink | null;
  created_tasks: number;
  existing_tasks: number;
  secure_links: number;
  artifact_url: string;
  created_at: string;
};

type AcceptanceAuditItem = {
  module: string;
  status: 'pass' | 'warning' | 'fail';
  evidence: string;
  next_action: string;
};

type AcceptanceAudit = {
  id: string;
  readiness_score: number;
  status: 'ready' | 'ready_with_boundaries' | 'needs_attention';
  summary: string;
  items: AcceptanceAuditItem[];
  blockers: string[];
  next_actions: string[];
  artifact_url: string;
  created_at: string;
};

type KnowledgeItem = {
  id?: number | null;
  title: string;
  content: string;
  source_type: string;
  tags: string;
  created_at: string;
};

type ServiceScriptStep = {
  title: string;
  message: string;
  goal: string;
};

type ServiceScriptResult = {
  title: string;
  channel: string;
  scenario: string;
  opening: string;
  steps: ServiceScriptStep[];
  objection_replies: ServiceScriptStep[];
  closing: string;
  knowledge_imported: number;
};

type ConversationSummary = {
  session_id: string;
  customer_id?: number | null;
  visitor_name: string;
  last_query: string;
  last_response: string;
  intent_score: number;
  need_followup: boolean;
  message_count: number;
  updated_at: string;
};

type ConversationDetail = {
  session_id: string;
  messages: Array<{
    role: 'visitor' | 'assistant';
    text: string;
    created_at: string;
    intent_score?: number;
    need_followup?: boolean;
  }>;
};

type Lead = {
  id: string;
  source: string;
  name: string;
  contact: string;
  need: string;
  status: string;
  created_at: string;
};

type CRMLead = {
  id: number;
  source: string;
  name: string;
  contact: string;
  need: string;
  status: string;
  sales_stage: string;
  owner: string;
  intent_score: number;
  tags: string[];
  last_session_id: string;
  next_followup_at: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

type CRMTask = {
  id: number;
  target_type: 'lead' | 'customer' | 'conversation';
  target_id: string;
  title: string;
  status: 'open' | 'done' | 'cancelled';
  priority: 'low' | 'normal' | 'high';
  owner: string;
  due_at: string;
  source: string;
  workflow_run_id: string;
  created_at: string;
  updated_at: string;
};

type CRMOverview = {
  leads: number;
  high_intent: number;
  needs_followup: number;
  open_tasks: number;
  won: number;
  lost: number;
  stage_counts: Record<string, number>;
};

type LocalScriptInfo = {
  id: string;
  name: string;
  description: string;
  risk: 'desktop' | 'long_running' | 'safe';
  enabled?: boolean;
  command_preview?: string;
};

type LocalScriptRun = {
  run_id: string;
  script_id: string;
  workflow_run_id?: string | null;
  status: 'queued' | 'running' | 'done' | 'failed';
  started_at?: string;
  finished_at?: string | null;
  returncode?: number | null;
  log?: string;
  log_path?: string;
};

type WorkflowRun = {
  id: string;
  workflow_id: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'needs_human';
  trigger_type?: 'message' | 'lead' | 'schedule' | 'manual' | null;
  trigger_source?: string;
  trigger_payload: Record<string, unknown>;
  action_logs: Array<{time?: string; message?: string; data?: Record<string, unknown>}>;
  created_at: string;
  updated_at: string;
};

type WorkflowDefinition = {
  id: string;
  name: string;
  module: string;
  description: string;
  trigger: {type: 'message' | 'lead' | 'schedule' | 'manual'; source: string; payload_schema?: Record<string, unknown>};
  conditions: Array<{field: string; operator: string; value?: unknown}>;
  actions: Array<{type: string; name: string; config?: Record<string, unknown>; requires_human_confirmation?: boolean}>;
  enabled: boolean;
};

type DesktopAgentMode = 'assist' | 'auto_paste' | 'auto_send' | 'paused';

type DesktopAgentSession = {
  session_id: string;
  merchant_id: number;
  device_name: string;
  os_name: string;
  platform: string;
  app_version: string;
  mode: DesktopAgentMode;
  paused: boolean;
  auto_send_confirmed: boolean;
  window_allowlist: string[];
  capabilities: string[];
  last_heartbeat_at: string;
  created_at: string;
  updated_at: string;
};

type DesktopAgentPauseState = {
  platform: string;
  window_title: string;
  paused: boolean;
  reason: string;
  updated_at: string;
};

type DesktopAgentActionLog = {
  action_id: string;
  action: string;
  mode: DesktopAgentMode;
  status: string;
  reason: string;
  intent_score?: number;
  platform?: string;
  channel?: string;
  window_title?: string;
  source?: string;
  message_hash?: string;
  message_excerpt?: string;
  reply_text?: string;
  risk_flags?: string[];
  workflow_run_ids?: string[];
  reply_meta?: {
    ai_model?: string;
    ai_mode?: string;
    confidence?: number;
    citations?: Array<{id?: number; title?: string; source_type?: string; snippet?: string; match_score?: number}>;
    knowledge_answered?: boolean;
    connector_safety?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
  result?: Record<string, unknown>;
};

type DesktopAgentState = {
  sessions: DesktopAgentSession[];
  pauses: DesktopAgentPauseState[];
  recent_actions: DesktopAgentActionLog[];
};

type ElectronAgentStatus = {
  running: boolean;
  pid?: number | null;
  logs?: Array<{time: string; type: string; text: string}>;
};

declare global {
  interface Window {
    merchantDesktop?: {
      platform: string;
      version: string;
      desktopAgent?: {
        start: (options?: Record<string, unknown>) => Promise<ElectronAgentStatus>;
        stop: () => Promise<ElectronAgentStatus>;
        status: () => Promise<ElectronAgentStatus>;
      };
    };
  }
}

type ApiEnvelope<T> = {
  ok: boolean;
  data: T;
  error?: {message?: string} | null;
};

type ProviderStatus = {
  mode?: string;
  provider?: string;
  model?: string;
  message?: string;
  [key: string]: unknown;
};

type ProductMediaPack = {
  pack_id: string;
  product_name: string;
  main_image_url: string;
  detail_image_url: string;
  video_preview_url: string;
  video_url?: string | null;
  video_status: 'rendered' | 'needs_ffmpeg' | 'failed';
  listing_draft: {
    platform: string;
    titles: string[];
    short_title: string;
    selling_points: string[];
    detail_sections: string[];
    customer_faq: Array<{question: string; answer: string}>;
    risk_checks: string[];
  };
  scenes: Array<{title: string; visual: string; asset_url: string}>;
  test_checklist: string[];
  next_action: string;
};

const emptyProfile: MerchantProfile = {
  username: '',
  merchant_code: '',
  business_name: '',
  industry: '企业电商运营',
  business_intro: '',
  products_services: '',
  pricing: '',
  promotions: '',
  hours: '',
  contact: '',
  faq: [
    {question: '你们能做什么？', answer: '我们提供 AI 客服、知识库、线索承接和企业运营自动化工作台。'},
    {question: '怎么接入？', answer: '官网可以放网页客服代码，平台渠道按授权或辅助模式接入。'}
  ],
  welcome_message: '您好，我是企业 AI 客服助手，请问现在想咨询哪一块？'
};

const sectionItems: Array<{id: Section; label: string; icon: React.ReactNode}> = [
  {id: 'enterprise', label: '首页', icon: <Brain size={18} />},
  {id: 'aiService', label: 'AI 客服', icon: <Bot size={18} />},
  {id: 'crm', label: '客户管理', icon: <Users size={18} />},
  {id: 'knowledge', label: '知识库', icon: <Database size={18} />},
  {id: 'automation', label: '自动化', icon: <Workflow size={18} />},
  {id: 'analytics', label: '数据分析', icon: <BarChart3 size={18} />},
  {id: 'settings', label: '设置', icon: <Settings size={18} />}
];

const channelNames: Record<string, string> = {
  web_widget: '官网客服',
  website: '官网客服',
  api: '开放 API',
  wechat: '微信',
  wechat_work: '企业微信',
  douyin: '抖音',
  douyin_dm: '抖音私信',
  taobao: '淘宝/千牛',
  pdd: '拼多多',
  xianyu: '闲鱼'
};

const statusNames: Record<string, string> = {
  draft: '未配置',
  ready: '待联调',
  connected: '已接入',
  blocked: '缺权限',
  disabled: '未启用',
  not_configured: '未配置',
  pending_auth: '待授权',
  failed: '异常',
  assist_only: '辅助模式',
  queued: '排队中',
  running: '运行中',
  success: '成功',
  done: '完成',
  needs_human: '需人工',
  pass: '通过',
  warning: '有边界',
  fail: '未通过',
  ready_with_boundaries: '可交付有边界',
  needs_attention: '需处理',
  needs_setup: '待配置',
  todo: '待处理',
  blocker: '阻塞',
  info: '信息',
  approved: '已通过',
  rejected: '已驳回'
};

const setupStatusNames: Record<string, string> = {
  ready: '已就绪',
  needs_setup: '待配置',
  blocked: '阻塞',
  done: '已完成',
  todo: '待处理',
  info: '信息',
  warning: '提醒',
  blocker: '阻塞',
  clear: '正常',
  attention: '需关注',
  overdue: '已逾期',
  recorded: '已记录',
  partial: '部分处理',
  closed: '已关闭',
  pass: '通过',
  fail: '失败',
  reconciled: '已复验',
  nothing_closed: '无关闭',
  complete: '已完成',
  collecting: '采集中',
  needs_evidence: '待证据',
  needs_review: '待复核',
  ready_to_review: '待审核',
  ready_for_review: '可处理',
  waiting_customer: '等待客户',
  needs_customer_help: '需客户协助',
  needs_help: '需协助',
  passed: '已通过',
  reviewing: '复核中',
  ready_for_signoff: '可签署',
  empty: '无事项',
  submitted: '已提交'
  ,
  synced: '已同步',
  nothing_to_sync: '无同步',
  preview: '预览',
  executed: '已执行',
  imported: '已导入',
  missing: '缺失',
  approved: '已通过',
  evidence_registered: '已登记证据'
};

function authHeaders(token: string): Record<string, string> {
  return token ? {Authorization: `Bearer ${token}`} : {};
}

function asDateText(value?: string) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('zh-CN');
  } catch {
    return value;
  }
}

function auditPillClass(status: AcceptanceAuditItem['status'] | AcceptanceAudit['status']) {
  if (status === 'pass' || status === 'ready') return 'connected';
  if (status === 'warning' || status === 'ready_with_boundaries') return 'ready';
  return 'blocked';
}

function auditStatusLabel(status: AcceptanceAuditItem['status'] | AcceptanceAudit['status']) {
  if (status === 'ready') return '可试运行';
  return statusNames[status] || status;
}

function setupPillClass(status: string) {
  if (status === 'done' || status === 'ready' || status === 'ok' || status === 'info' || status === 'complete' || status === 'passed' || status === 'ready_for_signoff' || status === 'ready_to_import' || status === 'accepted_for_preview' || status === 'executed' || status === 'imported' || status === 'requested' || status === 'created' || status === 'task_created' || status === 'task_existing' || status === 'clear') return 'connected';
  if (status === 'todo' || status === 'warning' || status === 'needs_setup' || status === 'collecting' || status === 'needs_evidence' || status === 'needs_review' || status === 'reviewing' || status === 'ready_to_review' || status === 'ready_for_review' || status === 'recovered' || status === 'recovered_for_review' || status === 'waiting_customer' || status === 'awaiting_customer' || status === 'needs_resubmission' || status === 'needs_customer_resubmission' || status === 'needs_customer' || status === 'needs_customer_help' || status === 'needs_fix' || status === 'mixed' || status === 'preview' || status === 'would_request' || status === 'already_requested') return 'ready';
  return 'blocked';
}

function setupStatusLabel(status: string) {
  return setupStatusNames[status] || statusNames[status] || status;
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('cs_token') || '');
  const [section, setSection] = useState<Section>('enterprise');
  const [profile, setProfile] = useState<MerchantProfile>(emptyProfile);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [channels, setChannels] = useState<ChannelConfig[]>([]);
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([]);
  const [connectorAuths, setConnectorAuths] = useState<ConnectorAuth[]>([]);
  const [connectorHealth, setConnectorHealth] = useState<ConnectorHealthOverview | null>(null);
  const [connectorSetupGuide, setConnectorSetupGuide] = useState<ConnectorSetupGuide | null>(null);
  const [connectorSecretDrafts, setConnectorSecretDrafts] = useState<Record<string, string>>({});
  const [connectorOAuthDrafts, setConnectorOAuthDrafts] = useState<Record<string, ConnectorOAuthDraft>>({});
  const [replyDraftQueue, setReplyDraftQueue] = useState<ReplyDraftQueueItem[]>([]);
  const [replyDispatches, setReplyDispatches] = useState<ReplyDispatchItem[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);
  const [businessReports, setBusinessReports] = useState<BusinessReport[]>([]);
  const [deliveryPacks, setDeliveryPacks] = useState<DeliveryPack[]>([]);
  const [integrationWorkOrder, setIntegrationWorkOrder] = useState<IntegrationWorkOrder | null>(null);
  const [integrationDryRun, setIntegrationDryRun] = useState<IntegrationDryRun | null>(null);
  const [integrationTaskSync, setIntegrationTaskSync] = useState<IntegrationTaskSyncResult | null>(null);
  const [integrationTaskReconcile, setIntegrationTaskReconcile] = useState<IntegrationTaskReconcileResult | null>(null);
  const [integrationSLA, setIntegrationSLA] = useState<IntegrationTaskSLABoard | null>(null);
  const [integrationSLAEscalation, setIntegrationSLAEscalation] = useState<IntegrationSLAEscalation | null>(null);
  const [integrationSLANotice, setIntegrationSLANotice] = useState<IntegrationSLANotice | null>(null);
  const [integrationSLANoticeReceipt, setIntegrationSLANoticeReceipt] = useState<IntegrationSLANoticeReceipt | null>(null);
  const [integrationSLALoopReport, setIntegrationSLALoopReport] = useState<IntegrationSLALoopReport | null>(null);
  const [platformAcceptanceEvidence, setPlatformAcceptanceEvidence] = useState<PlatformAcceptanceEvidence | null>(null);
  const [platformAcceptanceReport, setPlatformAcceptanceReport] = useState<PlatformAcceptanceReport | null>(null);
  const [platformAcceptanceGapSync, setPlatformAcceptanceGapSync] = useState<PlatformAcceptanceGapSyncResult | null>(null);
  const [platformAcceptanceGapReconcile, setPlatformAcceptanceGapReconcile] = useState<PlatformAcceptanceGapReconcileResult | null>(null);
  const [platformAcceptanceChecklist, setPlatformAcceptanceChecklist] = useState<PlatformAcceptanceEvidenceChecklist | null>(null);
  const [platformAcceptanceNotice, setPlatformAcceptanceNotice] = useState<PlatformAcceptanceEvidenceNotice | null>(null);
  const [platformAcceptanceReceipt, setPlatformAcceptanceReceipt] = useState<PlatformAcceptanceEvidenceReceipt | null>(null);
  const [platformAcceptanceReviewSync, setPlatformAcceptanceReviewSync] = useState<PlatformAcceptanceEvidenceReviewTaskSync | null>(null);
  const [platformAcceptanceReviewDesk, setPlatformAcceptanceReviewDesk] = useState<PlatformAcceptanceReviewDesk | null>(null);
  const [platformAcceptanceReviewExecution, setPlatformAcceptanceReviewExecution] = useState<PlatformAcceptanceReviewExecutionRun | null>(null);
  const [platformAcceptanceEvidenceUrlPrecheck, setPlatformAcceptanceEvidenceUrlPrecheck] = useState<PlatformAcceptanceEvidenceUrlPrecheckRun | null>(null);
  const [platformAcceptanceEvidenceImport, setPlatformAcceptanceEvidenceImport] = useState<PlatformAcceptanceEvidenceImportRun | null>(null);
  const [platformAcceptanceEvidenceManifestLink, setPlatformAcceptanceEvidenceManifestLink] = useState<PlatformAcceptanceEvidenceManifestLink | null>(null);
  const [platformAcceptanceEvidenceManifestInbox, setPlatformAcceptanceEvidenceManifestInbox] = useState<PlatformAcceptanceEvidenceManifestInbox | null>(null);
  const [platformAcceptanceManifestImportQueue, setPlatformAcceptanceManifestImportQueue] = useState<PlatformAcceptanceManifestImportQueue | null>(null);
  const [platformAcceptanceManifestRecoveryReview, setPlatformAcceptanceManifestRecoveryReview] = useState<PlatformAcceptanceManifestRecoveryReview | null>(null);
  const [platformAcceptanceManifestRecoveryResubmissionRun, setPlatformAcceptanceManifestRecoveryResubmissionRun] = useState<PlatformAcceptanceManifestRecoveryResubmissionRun | null>(null);
  const [platformAcceptanceManifestResubmissionTracker, setPlatformAcceptanceManifestResubmissionTracker] = useState<PlatformAcceptanceManifestResubmissionTracker | null>(null);
  const [platformAcceptanceManifestResubmissionReminderRun, setPlatformAcceptanceManifestResubmissionReminderRun] = useState<PlatformAcceptanceManifestResubmissionReminderRun | null>(null);
  const [platformAcceptanceManifestFollowupRun, setPlatformAcceptanceManifestFollowupRun] = useState<PlatformAcceptanceManifestFollowupRun | null>(null);
  const [platformAcceptanceEvidenceManifestSubmission, setPlatformAcceptanceEvidenceManifestSubmission] = useState<PlatformAcceptanceEvidenceManifestSubmission | null>(null);
  const [platformAcceptanceReviewDecision, setPlatformAcceptanceReviewDecision] = useState<PlatformAcceptanceEvidenceReviewDecision | null>(null);
  const [platformAcceptanceSubmissionLink, setPlatformAcceptanceSubmissionLink] = useState<PlatformAcceptanceEvidenceSubmissionLink | null>(null);
  const [platformAcceptanceCustomerSubmission, setPlatformAcceptanceCustomerSubmission] = useState<PlatformAcceptanceEvidenceCustomerSubmission | null>(null);
  const [platformAcceptanceSprintPack, setPlatformAcceptanceSprintPack] = useState<PlatformAcceptanceSprintPack | null>(null);
  const [platformAcceptanceLiveRun, setPlatformAcceptanceLiveRun] = useState<PlatformAcceptanceLiveRun | null>(null);
  const [platformAcceptanceJointDebugRun, setPlatformAcceptanceJointDebugRun] = useState<PlatformAcceptanceJointDebugRun | null>(null);
  const [platformAcceptanceGapClosureRun, setPlatformAcceptanceGapClosureRun] = useState<PlatformAcceptanceGapClosureRun | null>(null);
  const [platformAcceptanceOwnerActionPack, setPlatformAcceptanceOwnerActionPack] = useState<PlatformAcceptanceOwnerActionPack | null>(null);
  const [platformAcceptanceOwnerClosureLink, setPlatformAcceptanceOwnerClosureLink] = useState<PlatformAcceptanceOwnerClosureLink | null>(null);
  const [platformAcceptanceOwnerClosureRun, setPlatformAcceptanceOwnerClosureRun] = useState<PlatformAcceptanceOwnerClosureRun | null>(null);
  const [platformAcceptanceAutoWatchRun, setPlatformAcceptanceAutoWatchRun] = useState<PlatformAcceptanceAutoWatchRun | null>(null);
  const [platformAcceptanceWatchBoard, setPlatformAcceptanceWatchBoard] = useState<PlatformAcceptanceWatchBoard | null>(null);
  const [platformAcceptanceCustomerRoom, setPlatformAcceptanceCustomerRoom] = useState<PlatformAcceptanceCustomerRoomLink | null>(null);
  const [platformAcceptanceFinalSignoffLink, setPlatformAcceptanceFinalSignoffLink] = useState<PlatformAcceptanceFinalSignoffLink | null>(null);
  const [platformAcceptanceFinalClosureRun, setPlatformAcceptanceFinalClosureRun] = useState<PlatformAcceptanceFinalClosureRun | null>(null);
  const [acceptanceAudit, setAcceptanceAudit] = useState<AcceptanceAudit | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [crmLeads, setCrmLeads] = useState<CRMLead[]>([]);
  const [crmTasks, setCrmTasks] = useState<CRMTask[]>([]);
  const [crmOverview, setCrmOverview] = useState<CRMOverview | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition[]>([]);
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRun[]>([]);
  const [desktopAgentState, setDesktopAgentState] = useState<DesktopAgentState | null>(null);
  const [desktopAgentLogs, setDesktopAgentLogs] = useState<DesktopAgentActionLog[]>([]);
  const [electronAgentStatus, setElectronAgentStatus] = useState<ElectronAgentStatus | null>(null);
  const [desktopAgentMode, setDesktopAgentMode] = useState<DesktopAgentMode>('auto_paste');
  const [aiStatus, setAiStatus] = useState<ProviderStatus | null>(null);
  const [localScripts, setLocalScripts] = useState<LocalScriptInfo[]>([]);
  const [localRun, setLocalRun] = useState<LocalScriptRun | null>(null);
  const [localScriptStatus, setLocalScriptStatus] = useState('');
  const [loginDraft, setLoginDraft] = useState({username: '', password: ''});
  const [importDraft, setImportDraft] = useState({
    title: '企业客服知识库',
    source_type: 'faq',
    tags: '客服,成交,售后',
    content: 'Q: 你们怎么收费？\nA: 基础版适合官网客服和线索记录，Pro 适合加知识库、多渠道草稿和运营分析。\n\nQ: 可以接官网吗？\nA: 可以，把后台生成的 script 放到网站里即可出现客服气泡。'
  });
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [scriptDraft, setScriptDraft] = useState({
    channel: 'web_widget',
    scenario: 'full_pack',
    product_name: '',
    customer_pain: '',
    offer: '',
    tone: 'natural',
    save_to_knowledge: true
  });
  const [scriptResult, setScriptResult] = useState<ServiceScriptResult | null>(null);
  const [replyDraft, setReplyDraft] = useState({
    channel: 'web_widget',
    customer_name: '',
    message: '客户问：多少钱？怎么接到我网站？',
    reply: ''
  });
  const [replyPolicyDraft, setReplyPolicyDraft] = useState({
    tone: '成交型但克制，像真人客服，2-4句',
    goal: '先回答客户当前问题，再推进到留资、演示、下单或人工跟进',
    boundary: '只根据企业资料和知识库回答；资料没有就不要编造',
    handoff_rule: '退款、投诉、付款、账号、隐私、合同、发票、价格不确定时转人工',
    forbidden_terms: '保证准时,一定有效,无条件退款,私下付款,私下收款,绝对安全'
  });
  const [mediaDraft, setMediaDraft] = useState({
    product_name: '保湿精华液',
    category: '美妆护肤',
    platform: 'douyin',
    price: '129.00',
    selling_points: '深层补水,清爽不粘,敏感肌可用,熬夜急救',
    audience: '18-35 岁护肤用户',
    visual_style: '蓝紫霓虹科技风',
    call_to_action: '保存上架草稿'
  });
  const [mediaImageFile, setMediaImageFile] = useState<File | null>(null);
  const [mediaPack, setMediaPack] = useState<ProductMediaPack | null>(null);
  const [mediaStatus, setMediaStatus] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.session_id === selectedSessionId) ?? conversations[0],
    [conversations, selectedSessionId]
  );

  const widgetCode = useMemo(() => {
    const code = profile.merchant_code || 'WJAIKF001';
    return `<script src="${window.location.origin}${apiUrl(`/api/widget.js?merchant_code=${code}`)}"></script>`;
  }, [profile.merchant_code]);

  const widgetTestUrl = useMemo(() => {
    const code = profile.merchant_code || 'WJAIKF001';
    return `${window.location.origin}${apiUrl(`/api/widget-test?merchant_code=${code}`)}`;
  }, [profile.merchant_code]);

  const forbiddenReplyHits = useMemo(() => {
    const terms = replyPolicyDraft.forbidden_terms
      .split(/[,，、\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
    return terms.filter((term) => replyDraft.reply.includes(term));
  }, [replyDraft.reply, replyPolicyDraft.forbidden_terms]);

  function replyPolicyText() {
    return [
      `语气：${replyPolicyDraft.tone}`,
      `目标：${replyPolicyDraft.goal}`,
      `知识边界：${replyPolicyDraft.boundary}`,
      `转人工规则：${replyPolicyDraft.handoff_rule}`,
      `禁止承诺：${replyPolicyDraft.forbidden_terms}`,
      '不确定时固定回复：“这个问题需要人工客服确认，我帮您转接。”'
    ].join('\n');
  }

  function replyMessageWithPolicy() {
    return [`客户原话：${replyDraft.message.trim()}`, '', '客服策略：', replyPolicyText()].join('\n');
  }

  function displaySourceText(value: string) {
    return value
      .replace(/^客户原话：/, '')
      .split('\n\n客服策略：')[0]
      .trim();
  }

  useEffect(() => {
    if (!token) return;
    void refreshAll(token);
    void loadLocalScripts();
    void refreshElectronAgentStatus();
  }, [token]);

  useEffect(() => {
    if (!token || !selectedConversation?.session_id) {
      setDetail(null);
      return;
    }
    void loadConversation(selectedConversation.session_id);
  }, [token, selectedConversation?.session_id]);

  async function apiGet<T>(path: string, nextToken = token): Promise<T> {
    const response = await fetch(apiUrl(path), {headers: authHeaders(nextToken)});
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<T>;
  }

  async function apiGetData<T>(path: string, nextToken = token): Promise<T> {
    const response = await fetch(apiUrl(path), {headers: authHeaders(nextToken)});
    if (!response.ok) throw new Error(await response.text());
    const body = await response.json() as ApiEnvelope<T>;
    return body.data;
  }

  async function apiPostData<T>(path: string, payload: unknown, nextToken = token): Promise<T> {
    const response = await fetch(apiUrl(path), {
      method: 'POST',
      headers: {...authHeaders(nextToken), 'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(await response.text());
    const body = await response.json() as ApiEnvelope<T>;
    return body.data;
  }

  async function refreshDesktopAgentState() {
    const [state, logs] = await Promise.all([
      apiGetData<DesktopAgentState>('/api/v1/desktop-agent/state'),
      apiGetData<DesktopAgentActionLog[]>('/api/v1/desktop-agent/logs?limit=20')
    ]);
    setDesktopAgentState(state);
    setDesktopAgentLogs(Array.isArray(logs) ? logs : []);
  }

  async function setDesktopAgentPaused(paused: boolean) {
    setLoading(true);
    try {
      await apiPostData<DesktopAgentPauseState>('/api/v1/desktop-agent/pause', {
        paused,
        platform: '',
        window_title: '',
        reason: paused ? 'operator paused from web console' : 'operator resumed from web console'
      });
      await refreshDesktopAgentState();
      setStatus(paused ? '桌面自动客服已暂停。' : '桌面自动客服已恢复。');
    } finally {
      setLoading(false);
    }
  }

  async function refreshElectronAgentStatus() {
    if (!window.merchantDesktop?.desktopAgent) return;
    try {
      setElectronAgentStatus(await window.merchantDesktop.desktopAgent.status());
    } catch {
      setElectronAgentStatus(null);
    }
  }

  async function startLocalDesktopAgent() {
    if (!window.merchantDesktop?.desktopAgent) {
      setStatus('当前浏览器环境不能直接启动本地 Agent，请使用桌面客户端或命令行。');
      return;
    }
    setLoading(true);
    try {
      const nextStatus = await window.merchantDesktop.desktopAgent.start({
        authToken: token,
        apiBase: `${window.location.origin}${apiUrl('/api/v1')}`,
        mode: desktopAgentMode,
        paste: desktopAgentMode === 'auto_paste' || desktopAgentMode === 'auto_send',
        send: desktopAgentMode === 'auto_send',
        confirmSend: desktopAgentMode === 'auto_send' ? 'CONFIRM_DESKTOP_AUTO_SEND' : ''
      });
      setElectronAgentStatus(nextStatus);
      setStatus('本地桌面 Agent 已启动。');
    } finally {
      setLoading(false);
    }
  }

  async function stopLocalDesktopAgent() {
    if (!window.merchantDesktop?.desktopAgent) return;
    setElectronAgentStatus(await window.merchantDesktop.desktopAgent.stop());
    setStatus('本地桌面 Agent 已停止。');
  }

  function artifactUrl(path?: string | null) {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) return path;
    return apiUrl(path);
  }

  function fileToDataUrl(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function refreshAll(nextToken = token) {
    setLoading(true);
    setStatus('');
    try {
      const [
        profileData,
        overviewData,
        channelData,
        knowledgeData,
        conversationData,
        leadData,
        crmLeadData,
        crmTaskData,
        crmOverviewData,
        connectorData,
        connectorAuthData,
        connectorHealthData,
        connectorSetupGuideData,
        integrationSLAData,
        replyDraftData,
        replyDispatchData,
        teamMemberData,
        auditLogData,
        usageData,
        reportData,
        deliveryPackData,
        workflowData,
        workflowDefinitionData,
        desktopAgentStateData,
        desktopAgentLogData,
        aiData
      ] = await Promise.all([
        apiGet<MerchantProfile>('/api/merchant/profile', nextToken),
        apiGet<DashboardOverview>('/api/dashboard/overview', nextToken),
        apiGet<ChannelConfig[]>('/api/channels', nextToken),
        apiGet<KnowledgeItem[]>('/api/knowledge', nextToken),
        apiGet<ConversationSummary[]>('/api/conversations', nextToken),
        apiGet<Lead[]>('/api/leads', nextToken).catch(() => []),
        apiGetData<CRMLead[]>('/api/v1/crm/leads', nextToken).catch(() => []),
        apiGetData<CRMTask[]>('/api/v1/crm/tasks', nextToken).catch(() => []),
        apiGetData<CRMOverview>('/api/v1/crm/overview', nextToken).catch(() => null),
        apiGet<ConnectorStatus[]>('/api/connectors', nextToken).catch(() => []),
        apiGetData<ConnectorAuth[]>('/api/v1/connectors/auth', nextToken).catch(() => []),
        apiGetData<ConnectorHealthOverview>('/api/v1/ops/connector-health', nextToken).catch(() => null),
        apiGetData<ConnectorSetupGuide>('/api/v1/ops/setup-guide', nextToken).catch(() => null),
        apiGetData<IntegrationTaskSLABoard>('/api/v1/ops/integration-task-sla', nextToken).catch(() => null),
        apiGetData<ReplyDraftQueueItem[]>('/api/v1/reply-drafts?status=pending&limit=20', nextToken).catch(() => []),
        apiGetData<ReplyDispatchItem[]>('/api/v1/reply-dispatches?limit=20', nextToken).catch(() => []),
        apiGetData<TeamMember[]>('/api/v1/team/members', nextToken).catch(() => []),
        apiGetData<AuditLog[]>('/api/v1/audit/logs?limit=20', nextToken).catch(() => []),
        apiGetData<UsageSummary>('/api/v1/billing/usage', nextToken).catch(() => null),
        apiGetData<BusinessReport[]>('/api/v1/reports?limit=10', nextToken).catch(() => []),
        apiGetData<DeliveryPack[]>('/api/v1/delivery/packs?limit=5', nextToken).catch(() => []),
        apiGet<WorkflowRun[]>('/api/workflows/runs', nextToken).catch(() => []),
        apiGetData<WorkflowDefinition[]>('/api/v1/workflows/definitions', nextToken).catch(() => []),
        apiGetData<DesktopAgentState>('/api/v1/desktop-agent/state', nextToken).catch(() => null),
        apiGetData<DesktopAgentActionLog[]>('/api/v1/desktop-agent/logs?limit=20', nextToken).catch(() => []),
        apiGet<ProviderStatus>('/api/ai-engine/status', nextToken).catch(() => null)
      ]);
      setProfile({...emptyProfile, ...profileData});
      setOverview(overviewData);
      setChannels(Array.isArray(channelData) ? channelData : []);
      setKnowledge(Array.isArray(knowledgeData) ? knowledgeData : []);
      setConversations(Array.isArray(conversationData) ? conversationData : []);
      setLeads(Array.isArray(leadData) ? leadData : []);
      setCrmLeads(Array.isArray(crmLeadData) ? crmLeadData : []);
      setCrmTasks(Array.isArray(crmTaskData) ? crmTaskData : []);
      setCrmOverview(crmOverviewData);
      setConnectors(Array.isArray(connectorData) ? connectorData : []);
      setConnectorAuths(Array.isArray(connectorAuthData) ? connectorAuthData : []);
      setConnectorHealth(connectorHealthData);
      setConnectorSetupGuide(connectorSetupGuideData);
      setIntegrationSLA(integrationSLAData);
      setReplyDraftQueue(Array.isArray(replyDraftData) ? replyDraftData : []);
      setReplyDispatches(Array.isArray(replyDispatchData) ? replyDispatchData : []);
      setTeamMembers(Array.isArray(teamMemberData) ? teamMemberData : []);
      setAuditLogs(Array.isArray(auditLogData) ? auditLogData : []);
      setUsageSummary(usageData);
      setBusinessReports(Array.isArray(reportData) ? reportData : []);
      setDeliveryPacks(Array.isArray(deliveryPackData) ? deliveryPackData : []);
      setWorkflowRuns(Array.isArray(workflowData) ? workflowData : []);
      setWorkflowDefinitions(Array.isArray(workflowDefinitionData) ? workflowDefinitionData : []);
      setDesktopAgentState(desktopAgentStateData);
      setDesktopAgentLogs(Array.isArray(desktopAgentLogData) ? desktopAgentLogData : []);
      setAiStatus(aiData);
      if (Array.isArray(conversationData) && conversationData[0] && !selectedSessionId) {
        setSelectedSessionId(conversationData[0].session_id);
      }
    } catch {
      setStatus('登录已失效或服务暂不可用，请重新登录。');
      localStorage.removeItem('cs_token');
      setToken('');
    } finally {
      setLoading(false);
    }
  }

  async function login() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/auth/login'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(loginDraft)
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      localStorage.setItem('cs_token', data.token);
      setToken(data.token);
      setProfile({...emptyProfile, ...data.merchant});
      setStatus('登录成功，正在加载企业工作台。');
    } catch {
      setStatus('登录失败，请检查账号密码或后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function saveProfile() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/merchant/profile'), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(profile)
      });
      if (!response.ok) throw new Error(await response.text());
      setProfile(await response.json());
      setStatus('企业资料已保存，AI 客服会按新资料回复。');
      await refreshAll();
    } catch {
      setStatus('企业资料保存失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function saveChannel(channel: ChannelConfig) {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl(`/api/channels/${channel.channel}`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(channel)
      });
      if (!response.ok) throw new Error(await response.text());
      setStatus(`${channel.display_name || channelNames[channel.channel] || channel.channel} 配置已保存。`);
      await refreshAll();
    } catch {
      setStatus('渠道配置保存失败，请检查配置。');
    } finally {
      setLoading(false);
    }
  }

  async function saveConnectorWebhookSecret(connector: ConnectorAuth) {
    const signingKey = connectorSecretDrafts[connector.key]?.trim();
    if (!signingKey) {
      setStatus('请先填写 Webhook 签名密钥。');
      return;
    }
    setLoading(true);
    setStatus('正在保存 Webhook 签名密钥。');
    try {
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/auth`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          status: connector.status || 'pending_auth',
          auth_mode: connector.auth_mode || 'webhook',
          account_name: connector.account_name || '',
          callback_url: connector.callback_url || '',
          nonsecret_config: {},
          secret_fields: {webhook_token: signingKey},
          read_only_enabled: true,
          send_enabled: false,
          notes: connector.notes || ''
        })
      });
      if (!response.ok) throw new Error(await response.text());
      setConnectorSecretDrafts((current) => ({...current, [connector.key]: ''}));
      setStatus('Webhook 签名密钥已加密保存。');
      await refreshAll();
    } catch {
      setStatus('Webhook 签名密钥保存失败，请检查后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function startConnectorOAuth(connector: ConnectorAuth) {
    const draft = connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]);
    setLoading(true);
    setStatus('正在生成 OAuth 授权链接。');
    try {
      const redirectUri = `${window.location.origin}${apiUrl(`/api/v1/connectors/${connector.key}/oauth/callback`)}`;
      const saveResponse = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/auth`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          status: connector.status || 'pending_auth',
          auth_mode: 'oauth',
          account_name: connector.account_name || '',
          callback_url: redirectUri,
          nonsecret_config: oauthNonsecretConfig(draft, redirectUri),
          secret_fields: draft.client_secret.trim() ? {client_secret: draft.client_secret.trim()} : {},
          read_only_enabled: true,
          send_enabled: false,
          notes: connector.notes || ''
        })
      });
      if (!saveResponse.ok) throw new Error(await saveResponse.text());
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/oauth/start`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          authorize_url: draft.authorize_url.trim(),
          client_id: draft.client_id.trim(),
          scope: draft.scope.trim(),
          redirect_uri: redirectUri
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ConnectorOAuthStart>;
      setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), client_secret: ''}}));
      setStatus(body.data.next_action);
      if (body.data.auth_url) {
        window.open(body.data.auth_url, '_blank', 'noopener,noreferrer');
      }
      await refreshAll();
    } catch {
      setStatus('OAuth 授权链接生成失败，请检查 authorize_url、client_id 和后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function exchangeConnectorOAuth(connector: ConnectorAuth) {
    const draft = connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]);
    setLoading(true);
    setStatus('正在向官方 token endpoint 换取访问凭证。');
    try {
      const redirectUri = `${window.location.origin}${apiUrl(`/api/v1/connectors/${connector.key}/oauth/callback`)}`;
      const saveResponse = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/auth`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          status: connector.status || 'pending_auth',
          auth_mode: 'oauth',
          account_name: connector.account_name || '',
          callback_url: redirectUri,
          nonsecret_config: oauthNonsecretConfig(draft, redirectUri),
          secret_fields: draft.client_secret.trim() ? {client_secret: draft.client_secret.trim()} : {},
          read_only_enabled: true,
          send_enabled: false,
          notes: connector.notes || ''
        })
      });
      if (!saveResponse.ok) throw new Error(await saveResponse.text());
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/oauth/exchange`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          token_url: draft.token_url.trim(),
          client_id: draft.client_id.trim(),
          redirect_uri: redirectUri
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ConnectorOAuthExchange>;
      setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), client_secret: ''}}));
      setStatus(body.data.next_action);
      await refreshAll();
    } catch {
      setStatus('OAuth token exchange 失败，请检查 token_url、client_secret、回调 code 和后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function refreshConnectorOAuth(connector: ConnectorAuth) {
    const draft = connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]);
    setLoading(true);
    setStatus('正在刷新 OAuth 访问凭证。');
    try {
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/oauth/refresh`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          token_url: draft.token_url.trim(),
          client_id: draft.client_id.trim()
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ConnectorOAuthRefresh>;
      setStatus(body.data.next_action);
      await refreshAll();
    } catch {
      setStatus('OAuth token refresh 失败，请检查 refresh_token、token_url 和官方参数。');
    } finally {
      setLoading(false);
    }
  }

  async function pullConnectorReadApi(connector: ConnectorAuth, resource: 'messages' | 'leads') {
    const draft = connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]);
    setLoading(true);
    setStatus(resource === 'messages' ? '正在只读拉取平台消息。' : '正在只读拉取平台线索。');
    try {
      const redirectUri = `${window.location.origin}${apiUrl(`/api/v1/connectors/${connector.key}/oauth/callback`)}`;
      const saveResponse = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/auth`), {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          status: connector.status || 'pending_auth',
          auth_mode: connector.auth_mode || 'oauth',
          account_name: connector.account_name || '',
          callback_url: connector.callback_url || redirectUri,
          nonsecret_config: oauthNonsecretConfig(draft, redirectUri),
          secret_fields: draft.client_secret.trim() ? {client_secret: draft.client_secret.trim()} : {},
          read_only_enabled: true,
          send_enabled: false,
          notes: connector.notes || ''
        })
      });
      if (!saveResponse.ok) throw new Error(await saveResponse.text());
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/api/pull`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          resource,
          endpoint_url: resource === 'messages' ? draft.messages_url.trim() : draft.leads_url.trim(),
          limit: 20
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ConnectorReadPull>;
      setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), client_secret: ''}}));
      setStatus(`${body.data.next_action} 新增 ${body.data.imported}，重复 ${body.data.duplicates}，跳过 ${body.data.skipped}。`);
      await refreshAll();
    } catch {
      setStatus('官方 API 只读拉取失败，请检查 endpoint、access_token/session_key 和后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function enableConnectorSendGate(connector: ConnectorAuth) {
    const draft = connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]);
    setLoading(true);
    setStatus('正在启用受控 API 发送闸门。');
    try {
      const response = await fetch(apiUrl(`/api/v1/connectors/${connector.key}/send-gate`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          send_enabled: true,
          confirmation_phrase: 'ENABLE_SUPERVISED_SEND',
          send_url: draft.send_url.trim(),
          rate_limit_per_hour: 20
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<{next_action: string}>;
      setStatus(body.data.next_action);
      await refreshAll();
    } catch {
      setStatus('受控发送闸门启用失败，请确认 send_url 和 access_token/session_key 已配置。');
    } finally {
      setLoading(false);
    }
  }

  async function importKnowledge() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/knowledge/import'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({...importDraft, sync_to_faq: true})
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setStatus(`已导入 ${data.imported} 条知识，追加 ${data.faq_added} 条 FAQ。`);
      await refreshAll();
    } catch {
      setStatus('知识导入失败，请检查内容格式。');
    } finally {
      setLoading(false);
    }
  }

  async function uploadKnowledgeFile() {
    if (!knowledgeFile) {
      setStatus('请先选择 txt、md、csv、json、pdf 或 docx 文件。');
      return;
    }
    setLoading(true);
    setStatus('');
    try {
      const form = new FormData();
      form.append('file', knowledgeFile);
      const query = new URLSearchParams({
        title: importDraft.title || knowledgeFile.name,
        source_type: importDraft.source_type,
        tags: importDraft.tags || '文档导入',
        sync_to_faq: 'true'
      });
      const response = await fetch(apiUrl(`/api/v1/knowledge/upload?${query.toString()}`), {
        method: 'POST',
        headers: authHeaders(token),
        body: form
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<{filename: string; imported: number; faq_added: number}>;
      const data = body.data;
      setStatus(`已从 ${data.filename || knowledgeFile.name} 导入 ${data.imported} 条知识，追加 ${data.faq_added} 条 FAQ。`);
      setKnowledgeFile(null);
      await refreshAll();
    } catch {
      setStatus('文档导入失败。当前支持 txt、md、csv、json、pdf、docx。');
    } finally {
      setLoading(false);
    }
  }

  async function generateServiceScript() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/service-scripts/generate'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify(scriptDraft)
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setScriptResult(data);
      setStatus(data.knowledge_imported ? '客服脚本已生成，并已保存到知识库。' : '客服脚本已生成。');
      await refreshAll();
    } catch {
      setStatus('客服脚本生成失败，请检查 AI 配置或稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function generateReplyDraft() {
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(apiUrl('/api/reply/draft'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          channel: replyDraft.channel,
          customer_name: replyDraft.customer_name,
          message: replyMessageWithPolicy()
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setReplyDraft((current) => ({...current, reply: data.reply}));
      setStatus(data.need_followup ? '已生成回复草稿，此消息建议人工确认。' : '已生成回复草稿。');
    } catch {
      setStatus('回复草稿生成失败，请检查 AI 配置。');
    } finally {
      setLoading(false);
    }
  }

  async function saveReplyPolicyToKnowledge() {
    setLoading(true);
    setStatus('正在保存 AI 客服策略。');
    try {
      const response = await fetch(apiUrl('/api/knowledge/import'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          title: 'AI客服回复策略',
          source_type: 'policy',
          tags: 'AI客服,回复质量,转人工',
          content: replyPolicyText(),
          sync_to_faq: false
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setStatus(`AI 客服策略已保存到知识库：${data.imported} 条。`);
      await refreshAll();
    } catch {
      setStatus('AI 客服策略保存失败，请检查登录状态或后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function queueReplyDraft() {
    setLoading(true);
    setStatus('正在加入人工确认队列。');
    try {
      const response = await fetch(apiUrl('/api/v1/reply-drafts'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          channel: replyDraft.channel,
          customer_name: replyDraft.customer_name,
          message: replyMessageWithPolicy()
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ReplyDraftQueueItem>;
      setReplyDraftQueue((current) => [body.data, ...current.filter((item) => item.id !== body.data.id)]);
      setReplyDraft((current) => ({...current, reply: body.data.draft_text}));
      setStatus('回复草稿已加入人工确认队列。');
    } catch {
      setStatus('加入人工确认队列失败，请检查登录状态或后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function reviewReplyDraft(item: ReplyDraftQueueItem, nextStatus: 'approved' | 'rejected', prepareDispatch = false) {
    setLoading(true);
    setStatus(prepareDispatch ? '正在通过并进入外发准备队列。' : nextStatus === 'approved' ? '正在通过回复草稿。' : '正在驳回复草稿。');
    try {
      const response = await fetch(apiUrl(`/api/v1/reply-drafts/${item.id}/review`), {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({status: nextStatus, draft_text: item.draft_text})
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ReplyDraftQueueItem>;
      setReplyDraftQueue((current) => current.filter((draft) => draft.id !== body.data.id));
      if (prepareDispatch && nextStatus === 'approved') {
        const dispatchResponse = await fetch(apiUrl(`/api/v1/reply-drafts/${body.data.id}/dispatch`), {
          method: 'POST',
          headers: {'Content-Type': 'application/json', ...authHeaders(token)},
          body: JSON.stringify({dispatch_mode: 'manual_copy'})
        });
        if (!dispatchResponse.ok) throw new Error(await dispatchResponse.text());
        const dispatchBody = await dispatchResponse.json() as ApiEnvelope<ReplyDispatchItem>;
        setReplyDispatches((current) => [dispatchBody.data, ...current.filter((dispatch) => dispatch.id !== dispatchBody.data.id)]);
        setStatus(dispatchBody.data.next_action);
      } else {
        setStatus(nextStatus === 'approved' ? '回复草稿已通过，可复制后人工发送。' : '回复草稿已驳回。');
      }
    } catch {
      setStatus('回复草稿审核失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function revokeReplyDispatch(item: ReplyDispatchItem) {
    setLoading(true);
    setStatus('正在撤回外发准备记录。');
    try {
      const response = await fetch(apiUrl(`/api/v1/reply-dispatches/${item.id}/revoke`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({revoke_note: 'operator_cancelled'})
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ReplyDispatchItem>;
      setReplyDispatches((current) => current.map((dispatch) => dispatch.id === body.data.id ? body.data : dispatch));
      setStatus(body.data.next_action);
    } catch {
      setStatus('撤回外发准备记录失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function sendReplyDispatch(item: ReplyDispatchItem) {
    if (!window.confirm('确认使用官方 API 发送这条已审批回复？高风险内容会被后端阻断。')) {
      return;
    }
    setLoading(true);
    setStatus('正在执行受控 API 发送。');
    try {
      const response = await fetch(apiUrl(`/api/v1/reply-dispatches/${item.id}/send`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          confirmation_phrase: 'CONFIRM_PLATFORM_SEND',
          idempotency_key: `ui-dispatch-${item.id}`
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<ReplyDispatchItem>;
      setReplyDispatches((current) => current.map((dispatch) => dispatch.id === body.data.id ? body.data : dispatch));
      setStatus(body.data.next_action);
      await refreshAll();
    } catch {
      setStatus('受控 API 发送失败，请检查发送闸门、官方 send_url、访问凭证和风险标记。');
    } finally {
      setLoading(false);
    }
  }

  async function loadConversation(sessionId: string) {
    try {
      setDetail(await apiGet<ConversationDetail>(`/api/conversations/${sessionId}`));
    } catch {
      setDetail(null);
    }
  }

  async function markHandoff(sessionId: string) {
    await fetch(apiUrl(`/api/conversations/${sessionId}/handoff`), {method: 'POST', headers: authHeaders(token)});
    await refreshAll();
    await loadConversation(sessionId);
  }

  async function loadLocalScripts() {
    try {
      const response = await fetch(apiUrl('/api/local-scripts'));
      if (!response.ok) throw new Error(await response.text());
      setLocalScripts(await response.json());
    } catch {
      setLocalScripts([]);
      setLocalScriptStatus('本机脚本控制台只支持在 127.0.0.1 后端环境运行。');
    }
  }

  async function pollLocalRun(runId: string) {
    for (let index = 0; index < 40; index += 1) {
      const response = await fetch(apiUrl(`/api/local-scripts/runs/${runId}`));
      if (!response.ok) return;
      const data = await response.json() as LocalScriptRun;
      setLocalRun(data);
      if (data.status === 'done' || data.status === 'failed') {
        void refreshAll();
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }

  async function runLocalScript(scriptId: string) {
    setLocalScriptStatus('正在启动本机脚本...');
    setLocalRun(null);
    try {
      const response = await fetch(apiUrl(`/api/local-scripts/${scriptId}/run`), {method: 'POST'});
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json() as LocalScriptRun;
      setLocalRun(data);
      setLocalScriptStatus('脚本已启动，正在读取运行日志。');
      void pollLocalRun(data.run_id);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setLocalScriptStatus(`启动失败。本机脚本需要在 127.0.0.1 后端运行。详情：${detail.slice(0, 180)}`);
    }
  }

  async function runWorkflow(definition: WorkflowDefinition) {
    setLocalScriptStatus(`正在运行 Workflow：${definition.name}`);
    try {
      const response = await fetch(apiUrl(`/api/v1/workflows/${definition.id}/run`), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          payload: {
            message: '手动验收触发：请按当前企业资料生成下一步动作。',
            source: 'automation_center',
            operator: profile.username || 'operator'
          }
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<WorkflowRun>;
      setWorkflowRuns((current) => [body.data, ...current.filter((item) => item.id !== body.data.id)]);
      setLocalScriptStatus(`Workflow 已完成：${definition.name}`);
    } catch {
      setLocalScriptStatus('Workflow 运行失败，请检查后端服务或登录状态。');
    }
  }

  async function generateBusinessReport() {
    setStatus('正在生成经营日报。');
    try {
      const response = await fetch(apiUrl('/api/v1/reports/generate'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({report_type: 'daily'})
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<BusinessReport>;
      setBusinessReports((current) => [body.data, ...current.filter((item) => item.id !== body.data.id)]);
      setStatus('经营日报已生成。');
    } catch {
      setStatus('经营日报生成失败，请检查后端服务。');
    }
  }

  async function exportBusinessReport(report: BusinessReport, format: ReportExport['format'] = 'markdown') {
    try {
      const data = await apiGetData<ReportExport>(`/api/v1/reports/${report.id}/export?format=${format}`);
      if (format === 'markdown') {
        copyText(data.content, '报表内容已复制，Markdown 文件已生成。');
      } else {
        setStatus(`${format === 'pdf' ? 'PDF' : 'Word'} 报表已生成。`);
      }
      window.open(artifactUrl(data.artifact_url), '_blank', 'noopener,noreferrer');
    } catch {
      copyText(report.content, '导出失败，已复制当前报表内容。');
    }
  }

  async function generateDeliveryPack() {
    setLoading(true);
    setStatus('正在生成客户交付包。');
    try {
      const response = await fetch(apiUrl('/api/v1/delivery/packs'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || '客户',
          include_stage_reports: true,
          include_acceptance_matrix: true,
          include_operation_manual: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<DeliveryPack>;
      setDeliveryPacks((current) => [body.data, ...current.filter((item) => item.id !== body.data.id)]);
      if (body.data.zip_url) {
        window.open(artifactUrl(body.data.zip_url), '_blank', 'noopener,noreferrer');
      }
      setStatus('客户交付包已生成，可下载 ZIP 并查看验收文档。');
    } catch {
      setStatus('客户交付包生成失败，请检查后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function generateIntegrationWorkOrder() {
    setLoading(true);
    setStatus('正在生成平台接入工单。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-work-order'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || '客户',
          connectors: [],
          include_done: false
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationWorkOrder>;
      setIntegrationWorkOrder(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus('平台接入工单已生成，可交给客户平台管理员或技术负责人。');
    } catch {
      setStatus('平台接入工单生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function runIntegrationDryRun() {
    setLoading(true);
    setStatus('正在运行平台接入干跑验收。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-dry-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          connectors: [],
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationDryRun>;
      setIntegrationDryRun(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus('平台接入干跑验收已完成。');
    } catch {
      setStatus('平台接入干跑验收失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function syncIntegrationTasks() {
    setLoading(true);
    setStatus('正在同步平台接入缺口到 CRM 任务。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-task-sync'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          connectors: [],
          include_warnings: true,
          owner: '运营负责人',
          due_days: 1
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationTaskSyncResult>;
      setIntegrationTaskSync(body.data);
      if (body.data.tasks.length) {
        setCrmTasks((current) => [...body.data.tasks, ...current.filter((item) => !body.data.tasks.some((task) => task.id === item.id))]);
      }
      setStatus(`已同步平台接入任务：新增 ${body.data.created}，已存在 ${body.data.skipped_existing}。`);
      await refreshAll();
    } catch {
      setStatus('平台接入任务同步失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function reconcileIntegrationTasks() {
    setLoading(true);
    setStatus('正在复验平台接入任务。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-task-reconcile'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          connectors: [],
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationTaskReconcileResult>;
      setIntegrationTaskReconcile(body.data);
      if (body.data.closed_tasks.length) {
        setCrmTasks((current) => current.filter((item) => !body.data.closed_tasks.some((task) => task.id === item.id)));
      }
      setStatus(`平台接入任务复验完成：关闭 ${body.data.closed}，仍打开 ${body.data.still_open}。`);
      await refreshAll();
    } catch {
      setStatus('平台接入任务复验失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generateSLAEscalation() {
    setLoading(true);
    setStatus('正在生成平台接入 SLA 升级简报。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-sla-escalation'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          include_upcoming: false,
          owner: '运营负责人'
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationSLAEscalation>;
      setIntegrationSLAEscalation(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`平台接入 SLA 升级简报已生成：${body.data.items.length} 项。`);
      await refreshAll();
    } catch {
      setStatus('平台接入 SLA 升级简报生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generateSLANotice() {
    setLoading(true);
    setStatus('正在生成平台接入 SLA 责任人通知草稿。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-sla-notice'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          include_upcoming: false,
          owner: '运营负责人',
          channel: 'copy',
          recipient: '客户平台负责人'
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationSLANotice>;
      setIntegrationSLANotice(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`平台接入 SLA 通知草稿已生成：${body.data.items.length} 项，外发前请人工确认。`);
      await refreshAll();
    } catch {
      setStatus('平台接入 SLA 通知草稿生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function recordSLANoticeReceipt(closeTasks = false) {
    if (!integrationSLANotice) return;
    const taskIds = integrationSLANotice.items.map((item) => item.task_id);
    if (closeTasks && !window.confirm('确认责任人已完成这些平台接入任务，并关闭对应 CRM 任务？')) return;
    setLoading(true);
    setStatus(closeTasks ? '正在记录回执并关闭已确认的 CRM 任务。' : '正在记录平台接入 SLA 通知回执。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-sla-notice-receipt'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          notice_id: integrationSLANotice.id,
          recipient: integrationSLANotice.recipient,
          outcome: closeTasks ? 'completed' : 'acknowledged',
          confirmed_task_ids: taskIds,
          close_confirmed_tasks: closeTasks,
          confirm_phrase: closeTasks ? 'CONFIRM_CLOSE' : '',
          notes: closeTasks ? '前端人工确认后关闭通知涉及的接入任务。' : '前端记录责任人已收到 SLA 通知。'
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationSLANoticeReceipt>;
      setIntegrationSLANoticeReceipt(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`平台接入 SLA 回执已记录：关闭 ${body.data.closed_tasks.length} 项，剩余打开 ${body.data.remaining_open} 项。`);
      await refreshAll();
    } catch {
      setStatus('平台接入 SLA 回执记录失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generateSLALoopReport() {
    setLoading(true);
    setStatus('正在生成平台接入 SLA 闭环复盘报表。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/integration-sla-loop-report'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          audit_limit: 30,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<IntegrationSLALoopReport>;
      setIntegrationSLALoopReport(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`平台接入 SLA 闭环复盘报表已生成：打开 ${body.data.total_open} 项，近期关闭 ${body.data.closed_recent} 项。`);
      await refreshAll();
    } catch {
      setStatus('平台接入 SLA 闭环复盘报表生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function recordPlatformAcceptanceEvidence() {
    const scenarios: PlatformAcceptanceScenario[] = ['official_auth', 'callback', 'read_message', 'read_lead', 'draft_reply', 'controlled_send', 'ops_health', 'customer_trial'];
    const connector = window.prompt('Connector', 'website');
    if (!connector) return;
    const scenarioInput = window.prompt(`验收场景：${scenarios.join(' / ')}`, 'customer_trial') as PlatformAcceptanceScenario | null;
    if (!scenarioInput) return;
    const scenario = scenarios.includes(scenarioInput) ? scenarioInput : 'customer_trial';
    const resultInput = window.prompt('结果：pass / warning / fail', 'warning');
    if (!resultInput) return;
    const result = resultInput === 'pass' || resultInput === 'fail' ? resultInput : 'warning';
    const note = window.prompt('脱敏证据摘要', '客户真实平台验收证据摘要，未包含密码、token、验证码或密钥。');
    if (!note) return;
    const evidenceUrl = window.prompt('证据链接（可选）', '') || '';
    if (!window.confirm('确认本次证据不包含密码、token、cookie、验证码或密钥？')) return;
    setLoading(true);
    setStatus('正在登记真实平台验收证据。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          connector,
          scenario,
          result,
          account_label: '客户真实账号',
          operator: '运营负责人',
          evidence_note: note,
          evidence_url: evidenceUrl,
          occurred_at: '',
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidence>;
      setPlatformAcceptanceEvidence(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收证据已登记：${body.data.connector} / ${body.data.scenario} / ${body.data.result}。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收证据登记失败，请确认内容已脱敏并检查后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceReport() {
    setLoading(true);
    setStatus('正在生成真实平台验收证据包。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-report'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          audit_limit: 100,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceReport>;
      setPlatformAcceptanceReport(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收证据包已生成：证据 ${body.data.evidence_total} 条，缺失场景 ${body.data.missing_scenarios.length} 个。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收证据包生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function syncPlatformAcceptanceGaps() {
    setLoading(true);
    setStatus('正在同步真实平台验收缺口到 CRM 任务。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-gap-sync'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: '运营负责人',
          due_days: 2,
          create_tasks: true,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceGapSyncResult>;
      setPlatformAcceptanceGapSync(body.data);
      if (body.data.tasks.length) {
        setCrmTasks((current) => [...body.data.tasks, ...current.filter((item) => !body.data.tasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收缺口已同步：新增 ${body.data.created} 项，已存在 ${body.data.skipped_existing} 项。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收缺口同步失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function reconcilePlatformAcceptanceGaps() {
    setLoading(true);
    setStatus('正在复验真实平台验收证据并关闭匹配 CRM 任务。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-gap-reconcile'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          close_tasks: true,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceGapReconcileResult>;
      setPlatformAcceptanceGapReconcile(body.data);
      if (body.data.closed_tasks.length) {
        setCrmTasks((current) => current.filter((item) => !body.data.closed_tasks.some((task) => task.id === item.id)));
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收缺口复验完成：关闭 ${body.data.closed} 项，仍打开 ${body.data.still_open} 项。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收缺口复验失败，请确认已有 pass 证据并检查后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceChecklist() {
    setLoading(true);
    setStatus('正在生成真实平台验收证据采集清单。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-checklist'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: '运营负责人',
          due_days: 2,
          ensure_tasks: true,
          include_passed: true,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceChecklist>;
      setPlatformAcceptanceChecklist(body.data);
      if (body.data.tasks.length) {
        setCrmTasks((current) => [...body.data.tasks, ...current.filter((item) => !body.data.tasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收证据采集清单已生成：缺失 ${body.data.missing_scenarios.length} 项，清单 ${body.data.items.length} 项。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收证据采集清单生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceNotice() {
    setLoading(true);
    setStatus('正在生成真实平台验收证据责任人通知草稿。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-notice'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: '运营负责人',
          recipient: '客户平台负责人',
          channel: 'copy',
          due_days: 2,
          ensure_tasks: true,
          include_passed: false,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceNotice>;
      setPlatformAcceptanceNotice(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收证据通知草稿已生成：${body.data.items.length} 项待通知。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收证据通知草稿生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceSubmissionLink() {
    const recipient = window.prompt('客户平台负责人', platformAcceptanceNotice?.recipient || '客户平台负责人') || '';
    if (!recipient) return;
    const defaultScenarios = platformAcceptanceReport?.missing_scenarios?.join(',') || '';
    const scenarioInput = window.prompt('提交场景，逗号分隔；留空则使用当前缺失的必需场景', defaultScenarios) || '';
    const scenarios = scenarioInput
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean) as PlatformAcceptanceScenario[];
    setLoading(true);
    setStatus('正在生成客户材料提交链接。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-submission-link'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          recipient,
          owner: 'operations reviewer',
          scenarios,
          due_days: 2,
          expires_days: 7,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceSubmissionLink>;
      setPlatformAcceptanceSubmissionLink(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.submit_url) {
        copyText(body.data.submit_url, '客户材料提交链接已复制；发送前请人工确认接收人。');
      }
      setStatus(`客户材料提交链接已生成：${body.data.scenarios.length} 个场景，${body.data.expires_at} 过期。`);
      await refreshAll();
    } catch {
      setStatus('客户材料提交链接生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceEvidenceManifestLink() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceNotice?.recipient || platformAcceptanceCustomerRoom?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const defaultScenarios = platformAcceptanceReport?.missing_scenarios?.join(',') || '';
    const scenarioInput = window.prompt('Manifest scenarios, comma separated. Leave blank for current missing required scenarios.', defaultScenarios) || '';
    const scenarios = scenarioInput
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean) as PlatformAcceptanceScenario[];
    setLoading(true);
    setStatus('Generating customer evidence manifest link.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-manifest-link'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          scenarios,
          expires_days: 3,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceManifestLink>;
      setPlatformAcceptanceEvidenceManifestLink(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.manifest_url) {
        copyText(body.data.manifest_url, '客户证据清单链接已复制；发送前请人工确认。');
      }
      setStatus(`Evidence manifest link generated: ${body.data.scenarios.length} scenarios, expires ${body.data.expires_at}.`);
      await refreshAll();
    } catch {
      setStatus('Evidence manifest link generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceEvidenceManifestInbox() {
    setLoading(true);
    setStatus('Loading customer evidence manifest inbox.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-manifest-inbox'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          audit_limit: 300,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceManifestInbox>;
      setPlatformAcceptanceEvidenceManifestInbox(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Evidence manifest inbox loaded: ${body.data.total} submissions, ${body.data.ready} ready, ${body.data.blocked} need customer fixes.`);
      await refreshAll();
    } catch {
      setStatus('Evidence manifest inbox failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceManifestImportQueue() {
    setLoading(true);
    setStatus('Loading manifest import queue.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-import-queue'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          audit_limit: 300,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestImportQueue>;
      setPlatformAcceptanceManifestImportQueue(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Manifest import queue loaded: ${body.data.ready} ready, ${body.data.recovered} recovered, ${body.data.needs_customer} need customer, ${body.data.needs_manual_review} manual.`);
      await refreshAll();
    } catch {
      setStatus('Manifest import queue failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function runManifestQueueEvidenceImport(item: PlatformAcceptanceManifestImportQueueItem, execute: boolean) {
    if (!item.import_items.length) {
      setStatus('Manifest queue item has no structured import payload. Open artifacts and review manually.');
      return;
    }
    if (execute && item.status !== 'ready_to_import') {
      setStatus('Recovered manifest payloads are preview-only. Ask the customer to resubmit structured evidence or complete owner review before import.');
      return;
    }
    let confirmPhrase = '';
    if (execute) {
      if (!window.confirm('Only import after manually verifying every sanitized evidence URL. Continue?')) return;
      confirmPhrase = window.prompt('Type CONFIRM_PLATFORM_EVIDENCE to import pass evidence.', '') || '';
      if (confirmPhrase !== 'CONFIRM_PLATFORM_EVIDENCE') {
        setStatus('Evidence import cancelled: confirmation phrase did not match.');
        return;
      }
    }
    setLoading(true);
    setStatus(execute ? 'Importing manifest queue evidence.' : 'Previewing manifest queue evidence import.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-import'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          items: item.import_items,
          required_scenarios: item.scenarios,
          execute,
          confirm_phrase: confirmPhrase,
          close_review_tasks: true,
          reconcile_gap_tasks: true,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true,
          check_url_reachability: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceImportRun>;
      setPlatformAcceptanceEvidenceImport(body.data);
      if (body.data.decisions.length) {
        setPlatformAcceptanceReviewDecision(body.data.decisions[body.data.decisions.length - 1]);
      }
      if (body.data.report_after) {
        setPlatformAcceptanceReport(body.data.report_after);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Manifest queue import ${setupStatusLabel(body.data.status)}: supplied ${body.data.supplied}, imported ${body.data.imported}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Manifest queue import failed. Check evidence URLs, confirmation phrase, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function reviewManifestRecovery(
    item: PlatformAcceptanceManifestImportQueueItem,
    decision: PlatformAcceptanceManifestRecoveryReview['decision'],
    execute: boolean
  ) {
    if (item.status !== 'recovered_for_review') {
      setStatus('Only recovered manifest queue items can use recovery review.');
      return;
    }
    const defaultNote = decision === 'needs_customer_resubmission'
      ? 'Recovered artifact requires a fresh structured customer manifest before evidence import.'
      : 'Recovered artifact reviewed for preview-only handling; no pass evidence registered.';
    const reviewNote = execute ? (window.prompt('Recovery review note. Do not include passwords, tokens, cookies, codes, signatures, or API secrets.', defaultNote) || '') : defaultNote;
    if (execute && !reviewNote.trim()) return;
    const recipient = execute && decision === 'needs_customer_resubmission'
      ? (window.prompt('Customer platform owner', platformAcceptanceEvidenceManifestLink?.recipient || 'customer platform owner') || 'customer platform owner')
      : (platformAcceptanceEvidenceManifestLink?.recipient || 'customer platform owner');
    if (execute && !window.confirm('Confirm this recovery review contains no secrets and does not register pass evidence.')) return;
    setLoading(true);
    setStatus(execute ? 'Recording manifest recovery review.' : 'Previewing manifest recovery review.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-recovery-review'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          submission_id: item.submission_id,
          decision,
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          review_note: reviewNote,
          create_manifest_link: decision === 'needs_customer_resubmission',
          execute,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestRecoveryReview>;
      setPlatformAcceptanceManifestRecoveryReview(body.data);
      if (body.data.manifest_link) {
        setPlatformAcceptanceEvidenceManifestLink(body.data.manifest_link);
        copyText(body.data.manifest_link.manifest_url, 'Customer manifest link copied.');
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      const queueResponse = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-import-queue'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({audit_limit: 300, include_artifact: false})
      });
      if (queueResponse.ok) {
        const queueBody = await queueResponse.json() as ApiEnvelope<PlatformAcceptanceManifestImportQueue>;
        setPlatformAcceptanceManifestImportQueue(queueBody.data);
      }
      setStatus(`Manifest recovery review ${setupStatusLabel(body.data.status)}: ${body.data.next_action}`);
      await refreshAll();
    } catch {
      setStatus('Manifest recovery review failed. Check the recovered item, sanitized note, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function runManifestRecoveryResubmission(execute: boolean) {
    const recipient = platformAcceptanceEvidenceManifestLink?.recipient || platformAcceptanceWatchBoard?.recipient || platformAcceptanceNotice?.recipient || 'customer platform owner';
    const reviewNote = 'Recovered manifest payload requires a fresh structured customer manifest before evidence import.';
    if (execute && !window.confirm('Create customer Manifest resubmission links for recovered queue items? This does not register pass evidence.')) return;
    setLoading(true);
    setStatus(execute ? 'Creating recovery resubmission links.' : 'Previewing recovery resubmission orchestration.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-recovery-resubmission'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          review_note: reviewNote,
          execute,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestRecoveryResubmissionRun>;
      setPlatformAcceptanceManifestRecoveryResubmissionRun(body.data);
      const requestedItem = body.data.items.find((item) => item.manifest_url);
      if (requestedItem?.manifest_url) {
        copyText(requestedItem.manifest_url, 'Recovery resubmission manifest link copied.');
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      await generatePlatformAcceptanceManifestImportQueue();
      setStatus(`Recovery resubmission ${setupStatusLabel(body.data.status)}: requested ${body.data.requested}, already ${body.data.already_requested}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Recovery resubmission orchestration failed. Check recovered queue items and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function generateManifestResubmissionTracker() {
    const recipient = platformAcceptanceEvidenceManifestLink?.recipient || platformAcceptanceWatchBoard?.recipient || platformAcceptanceNotice?.recipient || 'customer platform owner';
    setLoading(true);
    setStatus('Loading Manifest resubmission tracker.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-resubmission-tracker'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          stale_after_hours: 24,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestResubmissionTracker>;
      setPlatformAcceptanceManifestResubmissionTracker(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.reminder_draft) {
        copyText(body.data.reminder_draft, 'Manifest resubmission reminder draft copied.');
      }
      setStatus(`Manifest resubmission tracker ${setupStatusLabel(body.data.status)}: waiting ${body.data.waiting_customer}, ready ${body.data.ready_for_review}, stale ${body.data.stale}.`);
      await refreshAll();
    } catch {
      setStatus('Manifest resubmission tracker failed. Check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generateManifestResubmissionReminder(createTasks: boolean) {
    const recipient = platformAcceptanceManifestResubmissionTracker?.recipient || platformAcceptanceEvidenceManifestLink?.recipient || platformAcceptanceWatchBoard?.recipient || platformAcceptanceNotice?.recipient || 'customer platform owner';
    setLoading(true);
    setStatus(createTasks ? 'Creating Manifest resubmission reminder tasks.' : 'Previewing Manifest resubmission reminder tasks.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-resubmission-reminder'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          stale_after_hours: 24,
          due_hours: 24,
          create_tasks: createTasks,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestResubmissionReminderRun>;
      setPlatformAcceptanceManifestResubmissionReminderRun(body.data);
      if (body.data.tracker) {
        setPlatformAcceptanceManifestResubmissionTracker(body.data.tracker);
      }
      const returnedTasks = body.data.items.map((item) => item.task).filter((task): task is CRMTask => Boolean(task));
      if (returnedTasks.length) {
        setCrmTasks((current) => [...returnedTasks, ...current.filter((item) => !returnedTasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.reminder_draft) {
        copyText(body.data.reminder_draft, 'Manifest resubmission reminder task draft copied.');
      }
      setStatus(`Manifest resubmission reminder ${setupStatusLabel(body.data.status)}: total ${body.data.total}, created ${body.data.created}, existing ${body.data.existing}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Manifest resubmission reminder failed. Check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceManifestFollowupRun() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceEvidenceManifestLink?.recipient || platformAcceptanceWatchBoard?.recipient || platformAcceptanceNotice?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const createManifestLink = window.confirm('Create a fresh manifest link for remaining missing scenarios?');
    setLoading(true);
    setStatus('Generating customer evidence manifest follow-up.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-manifest-followup-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          create_manifest_link: createManifestLink,
          expires_days: 3,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceManifestFollowupRun>;
      setPlatformAcceptanceManifestFollowupRun(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.reminder_draft) {
        copyText(body.data.reminder_draft, 'Manifest follow-up draft copied; review before sending.');
      }
      setStatus(`Manifest follow-up generated: ${body.data.missing_scenarios.length} missing, inbox ${body.data.inbox_total}, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Manifest follow-up failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceSprintPack() {
    const recipient = window.prompt('客户平台负责人', platformAcceptanceNotice?.recipient || '客户平台负责人') || '';
    if (!recipient) return;
    const createLinks = window.confirm('是否为每个未通过验收场景生成客户提交链接？');
    setLoading(true);
    setStatus('正在生成真实平台验收冲刺包。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-sprint-pack'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          recipient,
          due_days: 1,
          expires_days: 7,
          ensure_tasks: true,
          create_links: createLinks,
          include_passed: false,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceSprintPack>;
      setPlatformAcceptanceSprintPack(body.data);
      if (body.data.tasks.length) {
        setCrmTasks((current) => [...body.data.tasks, ...current.filter((item) => !body.data.tasks.some((task) => task.id === item.id))]);
      }
      if (body.data.links.length) {
        setPlatformAcceptanceSubmissionLink(body.data.links[0]);
        copyText(body.data.links[0].submit_url, '第一个客户提交链接已复制；发送前请人工确认接收人。');
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收冲刺包已生成：缺失 ${body.data.missing_scenarios.length} 项，行动 ${body.data.items.length} 项，链接 ${body.data.links.length} 个。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收冲刺包生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceLiveRun() {
    const recipient = window.prompt('客户平台负责人', platformAcceptanceNotice?.recipient || '客户平台负责人') || '';
    if (!recipient) return;
    const createSprintPack = window.confirm('是否同步生成/刷新验收冲刺包和客户提交链接？');
    setLoading(true);
    setStatus('正在生成真实平台验收作战台。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-live-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || '客户',
          owner: 'operations reviewer',
          recipient,
          due_days: 1,
          expires_days: 7,
          ensure_tasks: true,
          create_sprint_pack: createSprintPack,
          create_links: createSprintPack,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceLiveRun>;
      setPlatformAcceptanceLiveRun(body.data);
      if (body.data.sprint_pack) {
        setPlatformAcceptanceSprintPack(body.data.sprint_pack);
        if (body.data.sprint_pack.links.length) {
          setPlatformAcceptanceSubmissionLink(body.data.sprint_pack.links[0]);
        }
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.signoff_draft) {
        copyText(body.data.signoff_draft, '客户最终签署草稿已复制；仅在 ready_for_signoff 时发送。');
      }
      setStatus(`真实平台验收作战台已生成：通过 ${body.data.passed}/${body.data.required_total}，待复核 ${body.data.needs_review}，待补证 ${body.data.missing}。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收作战台生成失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceFinalSignoffLink() {
    const recipient = window.prompt('Final sign-off recipient', platformAcceptanceLiveRun?.recipient || platformAcceptanceNotice?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const signerName = window.prompt('Signer name', recipient) || '';
    if (!signerName) return;
    const signerRole = window.prompt('Signer role', 'platform owner') || '';
    if (!signerRole) return;
    setLoading(true);
    setStatus('Generating final sign-off gate.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-final-signoff-link'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          signer_name: signerName,
          signer_role: signerRole,
          expires_days: 7,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceFinalSignoffLink>;
      setPlatformAcceptanceFinalSignoffLink(body.data);
      setPlatformAcceptanceLiveRun(body.data.live_run);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.status === 'ready' && body.data.submit_url) {
        copyText(body.data.submit_url, 'Final sign-off link copied; send it only after human confirmation.');
      } else {
        setStatus(`Final sign-off gate is blocked: ${body.data.missing_scenarios.length} scenarios still need pass evidence.`);
      }
      await refreshAll();
    } catch {
      setStatus('Final sign-off gate generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceJointDebugRun() {
    const connectorInput = window.prompt('Connector keys to debug, comma separated. Leave blank for configured connectors.', '') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    const attemptPull = window.confirm('Run read-only official API pulls now? This will not send messages.');
    setLoading(true);
    setStatus('Running real platform joint debug.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-joint-debug-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          operator: 'operations reviewer',
          connectors,
          attempt_pull: attemptPull,
          auto_register_pass_evidence: true,
          pull_limit: 3,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceJointDebugRun>;
      setPlatformAcceptanceJointDebugRun(body.data);
      if (body.data.live_run) {
        setPlatformAcceptanceLiveRun(body.data.live_run);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Joint debug finished: passed ${body.data.passed}, missing ${body.data.missing}, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Real platform joint debug failed. Please check connector configuration, official endpoints, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceGapClosureRun() {
    const connectorInput = window.prompt('Connector keys for remaining gap closure, comma separated. Leave blank for configured connectors.', '') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    const attemptExchange = window.confirm('Attempt OAuth token exchange when all required fields are configured?');
    const attemptPull = window.confirm('Attempt read-only message/lead pulls when endpoints and credentials are configured? This will not send messages.');
    const createLinks = window.confirm('Create customer submission links for customer trial evidence?');
    setLoading(true);
    setStatus('Running remaining platform gap closure.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-gap-closure-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient: platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner',
          connectors,
          attempt_exchange: attemptExchange,
          attempt_pull: attemptPull,
          auto_register_pass_evidence: true,
          create_submission_links: createLinks,
          create_gap_tasks: true,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceGapClosureRun>;
      setPlatformAcceptanceGapClosureRun(body.data);
      if (body.data.joint_debug) {
        setPlatformAcceptanceJointDebugRun(body.data.joint_debug);
      }
      if (body.data.final_gate) {
        setPlatformAcceptanceFinalSignoffLink(body.data.final_gate);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      const customerLink = body.data.items.find((item) => item.submission_link?.submit_url)?.submission_link?.submit_url;
      if (customerLink) {
        copyText(customerLink, '客户试运行材料提交链接已复制；发送前请人工确认。');
      }
      setStatus(`Gap closure finished: before ${body.data.missing_before.length}, after ${body.data.missing_after.length}, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Remaining gap closure failed. Please check connector fields, customer submission link settings, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceOwnerActionPack() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connectorInput = window.prompt('Connector keys for owner action pack, comma separated. Leave blank for configured connectors.', '') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    setLoading(true);
    setStatus('Generating customer platform owner action pack.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-owner-action-pack'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connectors,
          create_customer_trial_link: true,
          expires_days: 7,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceOwnerActionPack>;
      setPlatformAcceptanceOwnerActionPack(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.draft_text) {
        copyText(body.data.draft_text, '客户平台负责人行动消息已复制；发送前请人工确认。');
      }
      setStatus(`Owner action pack generated: ${body.data.missing_scenarios.length} missing scenarios, ${body.data.items.length} action items.`);
      await refreshAll();
    } catch {
      setStatus('Customer platform owner action pack generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceOwnerClosureLink() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connectorInput = window.prompt('Allowed connectors for secure closure link, comma separated. Leave blank to let owner choose from defaults.', 'douyin,douyin_dm,wechat_work') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    setLoading(true);
    setStatus('Generating secure owner closure link.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-owner-closure-link'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connectors,
          expires_days: 3,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceOwnerClosureLink>;
      setPlatformAcceptanceOwnerClosureLink(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.submit_url) {
        copyText(body.data.submit_url, 'Secure owner closure link copied; send it only after human confirmation.');
      }
      setStatus(`Secure owner closure link generated: ${body.data.connectors.length || 'default'} connector options, expires ${body.data.expires_at}.`);
      await refreshAll();
    } catch {
      setStatus('Secure owner closure link generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceOwnerClosureRun() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connector = (window.prompt('Connector to update and recheck. Leave blank to only rerun closure.', 'douyin') || '').trim();
    const configRaw = window.prompt('Non-secret connector config JSON only. Example: {"token_url":"","messages_url":"","leads_url":""}. Do not include tokens, cookies, passwords, api_key, session_key, client_secret, or oauth_code.', '{"token_url":"","messages_url":"","leads_url":""}') || '';
    let nonsecretConfig: Record<string, unknown> = {};
    if (configRaw.trim()) {
      try {
        const parsed = JSON.parse(configRaw) as Record<string, unknown>;
        nonsecretConfig = Object.fromEntries(Object.entries(parsed).filter(([, value]) => String(value ?? '').trim()));
      } catch {
        setStatus('Non-secret config JSON is invalid.');
        return;
      }
    }
    const trialEvidenceUrl = (window.prompt('Optional sanitized customer trial evidence URL. Leave blank if not ready.', '') || '').trim();
    const trialNote = trialEvidenceUrl ? (window.prompt('Sanitized customer trial note. Do not include secrets or private customer data.', 'Customer trial material submitted for operations review.') || 'Customer trial material submitted for operations review.') : '';
    if (!window.confirm('Confirm the closure intake contains no passwords, tokens, cookies, verification codes, raw signatures, API secrets, session keys, or private customer data.')) return;
    const scenarioReceipts: PlatformAcceptanceEvidenceReceiptScenario[] = trialEvidenceUrl ? [{
      scenario: 'customer_trial',
      outcome: 'submitted',
      note: trialNote,
      evidence_url: trialEvidenceUrl
    }] : [];
    const connectorUpdates = connector ? [{
      connector,
      status: 'pending_auth',
      auth_mode: 'oauth',
      account_name: profile.business_name || 'customer platform account',
      callback_url: '',
      nonsecret_config: nonsecretConfig,
      secret_fields: {},
      read_only_enabled: true,
      notes: 'Owner closure intake from admin console'
    }] : [];
    setLoading(true);
    setStatus('Running platform owner closure and final gate recheck.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-owner-closure-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connector_updates: connectorUpdates,
          scenario_receipts: scenarioReceipts,
          receipt_outcome: scenarioReceipts.length ? 'submitted' : 'acknowledged',
          notes: trialNote || 'Owner closure recheck from admin console.',
          attempt_exchange: true,
          attempt_pull: true,
          auto_register_pass_evidence: true,
          create_submission_links: true,
          create_gap_tasks: true,
          create_review_tasks: true,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true,
          check_url_reachability: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceOwnerClosureRun>;
      setPlatformAcceptanceOwnerClosureRun(body.data);
      if (body.data.gap_closure) {
        setPlatformAcceptanceGapClosureRun(body.data.gap_closure);
      }
      if (body.data.owner_action_pack) {
        setPlatformAcceptanceOwnerActionPack(body.data.owner_action_pack);
      }
      if (body.data.final_gate) {
        setPlatformAcceptanceFinalSignoffLink(body.data.final_gate);
      }
      if (body.data.receipt) {
        setPlatformAcceptanceReceipt(body.data.receipt);
      }
      if (body.data.review_sync) {
        setPlatformAcceptanceReviewSync(body.data.review_sync);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Owner closure run finished: before ${body.data.missing_before.length}, after ${body.data.missing_after.length}, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Platform owner closure run failed. Check connector fields, sanitized evidence, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceAutoWatchRun() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connectorInput = window.prompt('Connector keys to watch, comma separated. Leave blank for configured connectors.', '') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    const attemptPull = window.confirm('Run read-only official API pulls during watch when credentials and endpoints are configured? This will not send messages.');
    setLoading(true);
    setStatus('Running real platform acceptance auto watch.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-auto-watch-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connectors,
          attempt_exchange: true,
          attempt_pull: attemptPull,
          create_owner_closure_link: true,
          create_review_tasks: true,
          create_gap_tasks: true,
          create_customer_links: true,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceAutoWatchRun>;
      setPlatformAcceptanceAutoWatchRun(body.data);
      if (body.data.review_sync) {
        setPlatformAcceptanceReviewSync(body.data.review_sync);
      }
      if (body.data.joint_debug) {
        setPlatformAcceptanceJointDebugRun(body.data.joint_debug);
      }
      if (body.data.gap_closure) {
        setPlatformAcceptanceGapClosureRun(body.data.gap_closure);
      }
      if (body.data.owner_closure_link) {
        setPlatformAcceptanceOwnerClosureLink(body.data.owner_closure_link);
      }
      if (body.data.owner_action_pack) {
        setPlatformAcceptanceOwnerActionPack(body.data.owner_action_pack);
      }
      if (body.data.final_gate) {
        setPlatformAcceptanceFinalSignoffLink(body.data.final_gate);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.owner_closure_link?.submit_url) {
        copyText(body.data.owner_closure_link.submit_url, 'Secure owner closure link copied; send it after human confirmation.');
      }
      setStatus(`Auto watch finished: before ${body.data.missing_before.length}, after ${body.data.missing_after.length}, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Real platform acceptance auto watch failed. Please check backend service, connector configuration, and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceFinalClosureRun() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceWatchBoard?.recipient || platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connectorInput = window.prompt('Connectors to attempt, comma separated. Leave blank for default options.', 'douyin,douyin_dm,wechat_work') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    const attemptPull = window.confirm('Attempt real read-only connector pulls if credentials/endpoints are configured?');
    setLoading(true);
    setStatus('Running final real-platform closure.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-final-closure-run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connectors,
          attempt_exchange: true,
          attempt_pull: attemptPull,
          create_tasks: true,
          create_customer_links: true,
          create_owner_closure_link: true,
          create_customer_room: true,
          create_resubmission_reminder: true,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceFinalClosureRun>;
      setPlatformAcceptanceFinalClosureRun(body.data);
      if (body.data.report_after) setPlatformAcceptanceReport(body.data.report_after);
      if (body.data.tracker) setPlatformAcceptanceManifestResubmissionTracker(body.data.tracker);
      if (body.data.reminder_run) setPlatformAcceptanceManifestResubmissionReminderRun(body.data.reminder_run);
      if (body.data.auto_watch) {
        setPlatformAcceptanceAutoWatchRun(body.data.auto_watch);
        if (body.data.auto_watch.review_sync) setPlatformAcceptanceReviewSync(body.data.auto_watch.review_sync);
        if (body.data.auto_watch.joint_debug) setPlatformAcceptanceJointDebugRun(body.data.auto_watch.joint_debug);
        if (body.data.auto_watch.gap_closure) setPlatformAcceptanceGapClosureRun(body.data.auto_watch.gap_closure);
        if (body.data.auto_watch.owner_closure_link) setPlatformAcceptanceOwnerClosureLink(body.data.auto_watch.owner_closure_link);
        if (body.data.auto_watch.owner_action_pack) setPlatformAcceptanceOwnerActionPack(body.data.auto_watch.owner_action_pack);
        if (body.data.auto_watch.final_gate) setPlatformAcceptanceFinalSignoffLink(body.data.auto_watch.final_gate);
      }
      if (body.data.customer_room) setPlatformAcceptanceCustomerRoom(body.data.customer_room);
      if (body.data.final_gate) setPlatformAcceptanceFinalSignoffLink(body.data.final_gate);
      const returnedTasks = [
        ...(body.data.reminder_run?.items.map((item) => item.task).filter((task): task is CRMTask => Boolean(task)) || []),
        ...(body.data.auto_watch?.review_sync?.tasks || []),
        ...(body.data.auto_watch?.gap_closure?.gap_sync?.tasks || [])
      ];
      if (returnedTasks.length) {
        setCrmTasks((current) => [...returnedTasks, ...current.filter((item) => !returnedTasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.customer_room?.room_url) {
        copyText(body.data.customer_room.room_url, 'Final closure customer room copied; review before sending.');
      }
      setStatus(`Final closure ${setupStatusLabel(body.data.status)}: before ${body.data.missing_before.length}, after ${body.data.missing_after.length}, tasks ${body.data.created_tasks}/${body.data.existing_tasks}, links ${body.data.secure_links}.`);
      await refreshAll();
    } catch {
      setStatus('Final closure run failed. Check backend service, connector configuration, and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceWatchBoard() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    setLoading(true);
    setStatus('Generating real platform acceptance watch board.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-watch-board'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceWatchBoard>;
      setPlatformAcceptanceWatchBoard(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.reminder_draft) {
        copyText(body.data.reminder_draft, 'Watch board reminder draft copied; review before sending.');
      }
      setStatus(`Watch board generated: ${body.data.missing_scenarios.length} missing scenarios, status ${setupStatusLabel(body.data.status)}.`);
      await refreshAll();
    } catch {
      setStatus('Watch board generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceCustomerRoom() {
    const recipient = window.prompt('Customer platform owner', platformAcceptanceWatchBoard?.recipient || platformAcceptanceOwnerActionPack?.recipient || platformAcceptanceNotice?.recipient || platformAcceptanceLiveRun?.recipient || 'customer platform owner') || '';
    if (!recipient) return;
    const connectorInput = window.prompt('Allowed connectors for customer room, comma separated. Leave blank for default options.', 'douyin,douyin_dm,wechat_work') || '';
    const connectors = connectorInput.split(',').map((item) => item.trim()).filter(Boolean);
    setLoading(true);
    setStatus('Generating customer acceptance room.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-customer-room-link'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          customer_name: profile.business_name || 'customer',
          owner: 'operations reviewer',
          recipient,
          connectors,
          expires_days: 3,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceCustomerRoomLink>;
      setPlatformAcceptanceCustomerRoom(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      if (body.data.room_url) {
        copyText(body.data.room_url, '客户验收房间链接已复制；发送前请人工确认。');
      }
      setStatus(`Customer acceptance room generated: ${body.data.missing_scenarios.length} missing scenarios, evidence ${setupStatusLabel(body.data.evidence_status)}.`);
      await refreshAll();
    } catch {
      setStatus('Customer acceptance room generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function recordPlatformAcceptanceReceipt() {
    if (!platformAcceptanceNotice) return;
    const outcomeInput = window.prompt('回执结果：acknowledged / needs_help / submitted', 'acknowledged');
    if (!outcomeInput) return;
    const outcome = outcomeInput === 'needs_help' || outcomeInput === 'submitted' ? outcomeInput : 'acknowledged';
    const notes = window.prompt('回执备注（不要填写密码、token、验证码或密钥）', '已收到证据采集通知，材料将走客户控制渠道提交。') || '';
    if (!window.confirm('确认回执内容不包含密码、token、cookie、验证码、签名密钥或 API secret？')) return;
    setLoading(true);
    setStatus('正在记录真实平台验收证据采集回执。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-receipt'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          notice_id: platformAcceptanceNotice.id,
          recipient: platformAcceptanceNotice.recipient,
          outcome,
          scenario_receipts: platformAcceptanceNotice.items.map((item) => ({
            scenario: item.scenario,
            outcome,
            note: notes,
            evidence_url: ''
          })),
          notes,
          include_artifact: true,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceReceipt>;
      setPlatformAcceptanceReceipt(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收证据采集回执已记录：${body.data.scenario_receipts.length} 项，状态 ${setupStatusLabel(body.data.status)}。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收证据采集回执记录失败，请检查内容脱敏和后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function syncPlatformAcceptanceReviewTasks() {
    setLoading(true);
    setStatus('正在同步真实平台验收材料复核任务。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-review-sync'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: '运营负责人',
          due_days: 1,
          include_needs_help: true,
          create_tasks: true,
          include_artifact: true,
          audit_limit: 200
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceReviewTaskSync>;
      setPlatformAcceptanceReviewSync(body.data);
      if (body.data.tasks.length) {
        setCrmTasks((current) => [...body.data.tasks, ...current.filter((item) => !body.data.tasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收材料复核任务已同步：新增 ${body.data.created} 项，已存在 ${body.data.skipped_existing} 项。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收材料复核任务同步失败，请检查后端服务和登录状态。');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlatformAcceptanceReviewDesk() {
    setLoading(true);
    setStatus('Generating platform acceptance review desk.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-review-desk'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          due_days: 1,
          include_needs_help: true,
          create_review_tasks: true,
          include_artifact: true,
          audit_limit: 300
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceReviewDesk>;
      setPlatformAcceptanceReviewDesk(body.data);
      setPlatformAcceptanceReviewSync(body.data.review_sync);
      if (body.data.review_sync.tasks.length) {
        setCrmTasks((current) => [...body.data.review_sync.tasks, ...current.filter((item) => !body.data.review_sync.tasks.some((task) => task.id === item.id))]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Review desk generated: ${body.data.ready_to_review} ready to review, ${body.data.needs_evidence} still need evidence.`);
      await refreshAll();
    } catch {
      setStatus('Review desk generation failed. Please check backend service and login state.');
    } finally {
      setLoading(false);
    }
  }

  async function runPlatformAcceptanceReviewExecution(execute: boolean) {
    let confirmPhrase = '';
    if (execute) {
      if (!window.confirm('Only execute after manually reviewing sanitized customer-controlled platform evidence. Continue?')) return;
      confirmPhrase = window.prompt('Type CONFIRM_PLATFORM_EVIDENCE to register pass evidence and reconcile gaps.', '') || '';
      if (confirmPhrase !== 'CONFIRM_PLATFORM_EVIDENCE') {
        setStatus('Review execution cancelled: confirmation phrase did not match.');
        return;
      }
    }
    setLoading(true);
    setStatus(execute ? 'Running platform review execution.' : 'Previewing platform review execution.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-review-execution'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          due_days: 1,
          decisions: [],
          auto_ready_items: true,
          execute,
          confirm_phrase: confirmPhrase,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceReviewExecutionRun>;
      setPlatformAcceptanceReviewExecution(body.data);
      if (body.data.desk_after) {
        setPlatformAcceptanceReviewDesk(body.data.desk_after);
      } else if (body.data.desk_before) {
        setPlatformAcceptanceReviewDesk(body.data.desk_before);
      }
      if (body.data.decisions.length) {
        setPlatformAcceptanceReviewDecision(body.data.decisions[body.data.decisions.length - 1]);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Review execution ${setupStatusLabel(body.data.status)}: requested ${body.data.requested}, executed ${body.data.executed}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Review execution failed. Please check evidence links, confirmation phrase, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function runPlatformAcceptanceEvidenceImport(execute: boolean) {
    const sourceScenarios = platformAcceptanceReviewDesk?.scenarios.filter((item) => item.status !== 'passed') || [];
    const template = sourceScenarios.map((item) => ({
      scenario: item.scenario,
      connector: 'website',
      account_label: 'customer platform account',
      operator: 'operations reviewer',
      evidence_note: item.note || item.next_action || `Sanitized proof for ${item.scenario}.`,
      evidence_url: '',
      review_task_ids: item.task_id ? [item.task_id] : []
    }));
    const rawManifest = window.prompt('Paste sanitized evidence JSON array. Evidence URLs must not contain secrets or placeholders.', JSON.stringify(template, null, 2));
    if (!rawManifest) return;
    let items: unknown;
    try {
      items = JSON.parse(rawManifest);
      if (!Array.isArray(items)) throw new Error('manifest must be an array');
    } catch {
      setStatus('Evidence import cancelled: JSON array could not be parsed.');
      return;
    }
    let confirmPhrase = '';
    if (execute) {
      if (!window.confirm('Only import after manually verifying every sanitized evidence URL. Continue?')) return;
      confirmPhrase = window.prompt('Type CONFIRM_PLATFORM_EVIDENCE to import pass evidence.', '') || '';
      if (confirmPhrase !== 'CONFIRM_PLATFORM_EVIDENCE') {
        setStatus('Evidence import cancelled: confirmation phrase did not match.');
        return;
      }
    }
    setLoading(true);
    setStatus(execute ? 'Importing platform evidence.' : 'Previewing platform evidence import.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-import'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          items,
          execute,
          confirm_phrase: confirmPhrase,
          close_review_tasks: true,
          reconcile_gap_tasks: true,
          include_artifact: true,
          audit_limit: 300,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceImportRun>;
      setPlatformAcceptanceEvidenceImport(body.data);
      if (body.data.decisions.length) {
        setPlatformAcceptanceReviewDecision(body.data.decisions[body.data.decisions.length - 1]);
      }
      if (body.data.report_after) {
        setPlatformAcceptanceReport(body.data.report_after);
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Evidence import ${setupStatusLabel(body.data.status)}: supplied ${body.data.supplied}, imported ${body.data.imported}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Evidence import failed. Check JSON, evidence URLs, confirmation phrase, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function runPlatformAcceptanceEvidenceUrlPrecheck() {
    const sourceScenarios = platformAcceptanceReviewDesk?.scenarios.filter((item) => item.status !== 'passed') || [];
    const template = sourceScenarios.map((item) => ({
      scenario: item.scenario,
      connector: 'website',
      account_label: 'customer platform account',
      operator: 'operations reviewer',
      evidence_note: item.note || item.next_action || `Sanitized proof for ${item.scenario}.`,
      evidence_url: '',
      review_task_ids: item.task_id ? [item.task_id] : []
    }));
    const rawManifest = window.prompt('Paste sanitized evidence JSON array for URL precheck.', JSON.stringify(template, null, 2));
    if (!rawManifest) return;
    let items: unknown;
    try {
      items = JSON.parse(rawManifest);
      if (!Array.isArray(items)) throw new Error('manifest must be an array');
    } catch {
      setStatus('Evidence URL precheck cancelled: JSON array could not be parsed.');
      return;
    }
    setLoading(true);
    setStatus('Running evidence URL precheck.');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-url-precheck'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          owner: 'operations reviewer',
          items,
          check_reachability: true,
          include_artifact: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceUrlPrecheckRun>;
      setPlatformAcceptanceEvidenceUrlPrecheck(body.data);
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`Evidence URL precheck ${setupStatusLabel(body.data.status)}: ok ${body.data.ok}, warning ${body.data.warning}, blocked ${body.data.blocked}.`);
      await refreshAll();
    } catch {
      setStatus('Evidence URL precheck failed. Check JSON, links, and backend service.');
    } finally {
      setLoading(false);
    }
  }

  async function recordPlatformAcceptanceReviewDecision() {
    const scenarios: PlatformAcceptanceScenario[] = ['official_auth', 'callback', 'read_message', 'read_lead', 'draft_reply', 'controlled_send', 'ops_health', 'customer_trial'];
    const scenarioInput = window.prompt(`审核场景：${scenarios.join(' / ')}`, 'ops_health') as PlatformAcceptanceScenario | null;
    if (!scenarioInput) return;
    const scenario = scenarios.includes(scenarioInput) ? scenarioInput : 'ops_health';
    const decisionInput = window.prompt('审核决策：approved / needs_redaction / rejected', 'needs_redaction');
    if (!decisionInput) return;
    const decision = decisionInput === 'approved' || decisionInput === 'rejected' ? decisionInput : 'needs_redaction';
    const taskIdsInput = window.prompt('要关闭的复核任务 ID（逗号分隔，可留空）', platformAcceptanceReviewSync?.tasks.slice(0, 1).map((task) => task.id).join(',') || '') || '';
    const reviewTaskIds = taskIdsInput.split(',').map((item) => Number(item.trim())).filter((item) => Number.isFinite(item) && item > 0);
    const note = window.prompt('脱敏证据摘要或审核备注', '运营审核记录：材料需继续脱敏或等待客户补充。') || '';
    const evidenceUrl = window.prompt('脱敏证据链接（审核通过登记 pass 时必填，其他可留空）', '') || '';
    const registerPassEvidence = decision === 'approved' && window.confirm('是否登记为 pass 证据？只有真实平台脱敏材料已审核通过时才确认。');
    const closeReviewTasks = registerPassEvidence && reviewTaskIds.length > 0 && window.confirm('是否关闭选中的复核任务？');
    const reconcileGapTasks = registerPassEvidence && window.confirm('是否联动复验并关闭匹配的真实平台验收缺口任务？');
    const requestResubmissionLink = decision !== 'approved' && window.confirm('是否生成客户补交材料链接？');
    const confirmPhrase = registerPassEvidence || closeReviewTasks ? window.prompt('请输入确认短语 CONFIRM_PLATFORM_EVIDENCE', '') || '' : '';
    if (!window.confirm('确认审核内容不包含密码、token、cookie、验证码、签名密钥或 API secret？')) return;
    setLoading(true);
    setStatus('正在记录真实平台验收材料审核决策。');
    try {
      const response = await fetch(apiUrl('/api/v1/ops/platform-acceptance-evidence-review-decision'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({
          scenario,
          decision,
          review_task_ids: reviewTaskIds,
          connector: 'website',
          account_label: 'customer platform account',
          operator: 'operations reviewer',
          evidence_note: note,
          evidence_url: evidenceUrl,
          register_pass_evidence: registerPassEvidence,
          close_review_tasks: closeReviewTasks,
          reconcile_gap_tasks: reconcileGapTasks,
          request_resubmission_link: requestResubmissionLink,
          confirm_phrase: confirmPhrase,
          include_artifact: true,
          no_secrets_confirmed: true
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<PlatformAcceptanceEvidenceReviewDecision>;
      setPlatformAcceptanceReviewDecision(body.data);
      if (body.data.closed_review_tasks.length) {
        setCrmTasks((current) => current.filter((item) => !body.data.closed_review_tasks.some((task) => task.id === item.id)));
      }
      if (body.data.resubmission_link) {
        setPlatformAcceptanceSubmissionLink(body.data.resubmission_link);
        copyText(body.data.resubmission_link.submit_url, '客户补交材料链接已复制；发送前请人工确认接收人。');
      }
      if (body.data.artifact_url) {
        window.open(artifactUrl(body.data.artifact_url), '_blank', 'noopener,noreferrer');
      }
      setStatus(`真实平台验收材料审核决策已记录：${setupStatusLabel(body.data.status)}。`);
      await refreshAll();
    } catch {
      setStatus('真实平台验收材料审核决策记录失败，请确认内容脱敏、确认短语和后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function runAcceptanceAudit() {
    setLoading(true);
    setStatus('正在运行最终验收巡检。');
    try {
      const response = await fetch(apiUrl('/api/v1/acceptance/audit'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', ...authHeaders(token)},
        body: JSON.stringify({include_artifact: true})
      });
      if (!response.ok) throw new Error(await response.text());
      const body = await response.json() as ApiEnvelope<AcceptanceAudit>;
      setAcceptanceAudit(body.data);
      setStatus('最终验收巡检已完成。');
    } catch {
      setStatus('最终验收巡检失败，请检查后端服务。');
    } finally {
      setLoading(false);
    }
  }

  async function generateProductMediaPack() {
    setLoading(true);
    setMediaStatus('正在生成商品主图、详情图和短视频预览...');
    try {
      const product_image_data_url = mediaImageFile ? await fileToDataUrl(mediaImageFile) : null;
      const response = await fetch(apiUrl('/api/product-media/pack'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...mediaDraft, product_image_data_url, render_video: true})
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json() as ProductMediaPack;
      setMediaPack(data);
      setMediaStatus(data.video_status === 'rendered' ? '已生成主图、详情图和 MP4 视频。' : '已生成主图、详情图和视频预览。');
    } catch (error) {
      setMediaStatus(`生成失败：${error instanceof Error ? error.message : '请检查后端服务'}`);
    } finally {
      setLoading(false);
    }
  }

  function updateProfile<Key extends keyof MerchantProfile>(key: Key, value: MerchantProfile[Key]) {
    setProfile((current) => ({...current, [key]: value}));
  }

  function updateFaq(index: number, patch: Partial<FAQItem>) {
    setProfile((current) => ({
      ...current,
      faq: current.faq.map((item, itemIndex) => itemIndex === index ? {...item, ...patch} : item)
    }));
  }

  function updateChannel(index: number, patch: Partial<ChannelConfig>) {
    setChannels((current) => current.map((item, itemIndex) => itemIndex === index ? {...item, ...patch} : item));
  }

  function addFaq() {
    setProfile((current) => ({...current, faq: [...current.faq, {question: '', answer: ''}]}));
  }

  function copyText(text: string, nextStatus = '已复制。') {
    if (!navigator.clipboard) {
      setStatus('当前浏览器不允许直接写入剪贴板。');
      return;
    }
    void navigator.clipboard.writeText(text).then(() => setStatus(nextStatus));
  }

  if (!token) {
    return (
      <main className="loginShell">
        <section className="loginCard">
          <div className="brandMark"><Brain size={30} /></div>
          <p>AI Merchant OS</p>
          <h1>AI 商家运营工作台</h1>
          <span>面向企业电商团队和数字化运营团队，统一管理客服、知识库、线索、商品、自动化和经营分析。</span>
          <div className="loginHint">
            <strong>生产登录</strong>
            <code>使用已发放的企业账号</code>
            <strong>安全提示</strong>
            <code>默认密码已关闭</code>
          </div>
          <label>账号<input value={loginDraft.username} onChange={(event) => setLoginDraft({...loginDraft, username: event.target.value})} /></label>
          <label>密码<input type="password" value={loginDraft.password} onChange={(event) => setLoginDraft({...loginDraft, password: event.target.value})} /></label>
          <button className="primaryButton" onClick={login} disabled={loading}>{loading ? <RefreshCw className="spin" size={18} /> : <LogIn size={18} />}登录工作台</button>
          {status && <div className="statusText">{status}</div>}
        </section>
      </main>
    );
  }

  return (
    <main className="brainShell">
      <div className="starField" />
      <aside className="brainSidebar">
        <div className="csBrand">
          <span><Brain size={22} /></span>
          <div>
            <strong>{profile.business_name || 'AI 商家运营工作台'}</strong>
            <small>{profile.merchant_code || '未配置企业码'}</small>
          </div>
        </div>
        <nav>
          {sectionItems.map((item) => (
            <button className={section === item.id ? 'active' : ''} onClick={() => setSection(item.id)} key={item.id}>
              {item.icon}{item.label}
            </button>
          ))}
        </nav>
        <button className="ghostButton" onClick={() => { localStorage.removeItem('cs_token'); setToken(''); }}>退出登录</button>
        {status && <div className="statusText">{status}</div>}
      </aside>

      <section className="brainMain">
        {section === 'enterprise' && renderEnterprise()}
        {section === 'acquisition' && renderAcquisition()}
        {section === 'aiService' && renderAiService()}
        {section === 'crm' && renderCrm()}
        {section === 'knowledge' && renderKnowledge()}
        {section === 'products' && renderProducts()}
        {section === 'automation' && renderAutomation()}
        {section === 'aiDecision' && renderAiDecision()}
        {section === 'analytics' && renderAnalytics()}
        {section === 'settings' && renderSettings()}
      </section>
    </main>
  );

  function renderEnterprise() {
    const todayConsultations = overview?.today_conversations ?? conversations.length;
    const aiReplies = overview?.auto_replies ?? 0;
    const savedMinutes = aiReplies * 3;
    const savedTime = savedMinutes >= 60 ? `${Math.floor(savedMinutes / 60)}h ${savedMinutes % 60}m` : `${savedMinutes}m`;
    const highIntentCustomers = crmOverview?.high_intent ?? conversations.filter((item) => item.intent_score >= 70).length;
    const followupCustomers = crmOverview?.needs_followup ?? overview?.handoff_needed ?? crmTasks.filter((item) => item.status === 'open').length;
    const replyRate = todayConsultations > 0 ? Math.round((aiReplies / todayConsultations) * 100) : 0;
    const highIntentList = conversations.filter((item) => item.intent_score >= 70).slice(0, 4);
    const followupList = conversations.filter((item) => item.need_followup).slice(0, 4);
    const aiSuggestions = [
      followupCustomers > 0
        ? `优先处理 ${followupCustomers} 个待跟进客户，避免高意向咨询冷却。`
        : '当前待跟进压力较低，可以把重点放在新增咨询承接。',
      highIntentCustomers > 0
        ? `把 ${highIntentCustomers} 个高意向客户交给人工确认报价、资质或合作细节。`
        : '高意向客户暂未形成，可优化欢迎语和首轮追问来提高识别率。',
      knowledge.length > 0
        ? `知识库已有 ${knowledge.length} 条内容，建议继续补充价格、退款、开票和交付边界。`
        : '先导入 FAQ、价格表和售后规则，AI 才能减少不确定回复。',
      aiReplies > 0
        ? `AI 已处理 ${aiReplies} 次回复，预计节省 ${savedTime} 人工时间。`
        : '建议先开启网页客服或桌面助手，积累第一批真实咨询样本。'
    ];
    const valueCards = [
      {label: '今日客户咨询', value: todayConsultations, detail: '来自客服会话与渠道入口', tone: 'default'},
      {label: 'AI自动回复数量', value: aiReplies, detail: `${replyRate}% 咨询已由 AI 承接`, tone: 'success'},
      {label: '人工节省时间', value: savedTime, detail: '按每次回复 3 分钟估算', tone: 'purple'},
      {label: '高意向客户', value: highIntentCustomers, detail: '意向分 70 以上', tone: 'gold'},
      {label: '待跟进客户', value: followupCustomers, detail: '需要人工确认或跟进', tone: followupCustomers ? 'danger' : 'default'}
    ];

    return (
      <div className="aiHomeDashboard">
        <section className="aiHomeHero">
          <div>
            <p>AI Operations Command</p>
            <h1>AI 运营驾驶舱</h1>
            <span>把客服自动化转化成老板能直接判断的经营结果：咨询承接、回复效率、高意向客户和待跟进动作。</span>
          </div>
          <div className="aiHomeSignal">
            <small>AI 工作状态</small>
            <strong>{aiStatus?.provider ? '已接入 AI Engine' : '等待 AI Engine 配置'}</strong>
            <span>{aiStatus?.model || aiStatus?.mode || '统一由 AI Engine 处理客服回复与经营建议'}</span>
          </div>
        </section>

        <div className="aiValueGrid">
          {valueCards.map((card) => (
            <article className={`aiValueCard ${card.tone}`} key={card.label}>
              <small>{card.label}</small>
              <strong>{card.value}</strong>
              <span>{card.detail}</span>
            </article>
          ))}
        </div>

        <div className="aiHomeGrid">
          <section className="aiHomePanel advicePanel">
            <div className="aiHomePanelHeader">
              <div>
                <small>AI 今日经营建议</small>
                <strong>下一步该抓什么</strong>
              </div>
              <Sparkles size={18} />
            </div>
            <div className="aiSuggestionList">
              {aiSuggestions.map((item, index) => (
                <article key={item}>
                  <span>{index + 1}</span>
                  <p>{item}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="aiHomePanel">
            <div className="aiHomePanelHeader">
              <div>
                <small>高意向客户</small>
                <strong>{highIntentCustomers} 个值得优先跟进</strong>
              </div>
              <Target size={18} />
            </div>
            <div className="aiCustomerList">
              {highIntentList.length === 0 && <EmptyState text="暂无高意向客户。AI 会按咨询内容和意向分自动识别。" />}
              {highIntentList.map((item) => (
                <button key={item.session_id} onClick={() => { setSelectedSessionId(item.session_id); setSection('aiService'); }}>
                  <strong>{item.visitor_name || '访客'} · {item.intent_score}</strong>
                  <span>{item.last_query}</span>
                  <small>{asDateText(item.updated_at)}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="aiHomePanel">
            <div className="aiHomePanelHeader">
              <div>
                <small>待跟进客户</small>
                <strong>{followupCustomers} 个需要人工确认</strong>
              </div>
              <Headphones size={18} />
            </div>
            <div className="aiCustomerList">
              {followupList.length === 0 && <EmptyState text="暂无待跟进客户。投诉、退款、报价不确定等场景会进入这里。" />}
              {followupList.map((item) => (
                <button key={item.session_id} onClick={() => { setSelectedSessionId(item.session_id); setSection('aiService'); }}>
                  <strong>{item.visitor_name || '访客'} · 需跟进</strong>
                  <span>{item.last_query}</span>
                  <small>{asDateText(item.updated_at)}</small>
                </button>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  function renderAcquisition() {
    const visibleLeads = crmLeads.length
      ? crmLeads
      : leads.map((lead) => ({
          id: Number.parseInt(lead.id, 10) || 0,
          source: lead.source,
          name: lead.name,
          contact: lead.contact,
          need: lead.need,
          status: lead.status,
          sales_stage: lead.status,
          owner: '',
          intent_score: 0,
          tags: [],
          last_session_id: '',
          next_followup_at: '',
          notes: '',
          created_at: lead.created_at,
          updated_at: lead.created_at
        }));
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Acquisition" title="获客中心" desc="统一查看各渠道进入的线索。当前只展示后端已有线索和客服会话，不做虚假线索。" />
        <div className="operatorGrid">
          <section className="panel">
            <div className="panelHeader"><strong>线索池</strong><small>{visibleLeads.length} 条</small></div>
            {visibleLeads.length === 0 && <EmptyState text="暂无后端线索。接入渠道同步或客户主动咨询后会进入这里。" />}
            {visibleLeads.map((lead) => (
              <article className="knowledgeItem" key={lead.id}>
                <strong>{lead.name || '未命名线索'} · {lead.source}</strong>
                <p>{lead.need || '暂无需求描述'}</p>
                <small>{lead.contact || '无联系方式'} · {lead.sales_stage || lead.status || 'new'} · 意向 {lead.intent_score || 0} · {lead.updated_at || lead.created_at}</small>
              </article>
            ))}
          </section>
          <section className="panel">
            <div className="panelHeader"><strong>从会话识别的高意向客户</strong><small>{conversations.filter((item) => item.intent_score >= 70).length} 条</small></div>
            {conversations.filter((item) => item.intent_score >= 70).length === 0 && <EmptyState text="暂无高意向会话。AI 客服产生真实会话后会按意向分进入这里。" />}
            {conversations.filter((item) => item.intent_score >= 70).map((item) => (
              <article className="knowledgeItem" key={item.session_id}>
                <strong>{item.visitor_name} · 意向 {item.intent_score}</strong>
                <p>{item.last_query}</p>
                <small>{item.updated_at} {item.need_followup ? '· 需人工跟进' : ''}</small>
              </article>
            ))}
          </section>
        </div>
      </div>
    );
  }

  function renderAiService() {
    const canControlLocalAgent = Boolean(window.merchantDesktop?.desktopAgent);
    const globallyPaused = Boolean(desktopAgentState?.pauses.some((item) => item.paused && !item.platform && !item.window_title));
    const activeChannel = channels.find((channel) => channel.channel === replyDraft.channel);
    const latestAgentAction = desktopAgentLogs[0];
    const aiWorkflow = workflowDefinitions.find((definition) => definition.id === 'ai_customer_service_desktop_mvp');
    const latestAiWorkflowRun = workflowRuns.find((run) => run.workflow_id === 'ai_customer_service_desktop_mvp');
    const riskyDraftCount = replyDraftQueue.filter((item) => item.risk_flags.length > 0 || item.intent_score >= 70).length;
    const replyHasText = Boolean(replyDraft.reply.trim());
    const qualityChecks = [
      {label: '知识库', value: knowledge.length ? `${knowledge.length} 条可用` : '未导入', state: knowledge.length ? 'ok' : 'warn'},
      {label: '转人工', value: replyDraft.reply.includes('人工') || forbiddenReplyHits.length ? '已触发' : '按策略判断', state: forbiddenReplyHits.length ? 'blocked' : 'ok'},
      {label: '禁用承诺', value: forbiddenReplyHits.length ? forbiddenReplyHits.join(' / ') : '未命中', state: forbiddenReplyHits.length ? 'blocked' : 'ok'},
      {label: '回复长度', value: replyHasText ? `${replyDraft.reply.length} 字` : '待生成', state: replyHasText ? 'ok' : 'warn'}
    ];
    const currentIntentScore = selectedConversation?.intent_score ?? 0;
    const customerTemperature = currentIntentScore >= 70 ? '高意向' : currentIntentScore >= 40 ? '可培育' : '待识别';
    const customerTemperatureClass = currentIntentScore >= 70 ? 'hot' : currentIntentScore >= 40 ? 'warm' : 'cold';
    const activeMessages = detail?.session_id === selectedConversation?.session_id ? detail.messages : [];
    const nextBestAction = selectedConversation?.need_followup
      ? '人工接管并补充报价/售后规则'
      : replyDraft.reply.trim()
        ? '审核回复后准备外发'
        : '生成知识库回复草稿';
    const aiHealthText = aiStatus?.provider ? `${aiStatus.provider}${aiStatus.model ? ` / ${aiStatus.model}` : ''}` : 'AI Engine 待检查';
    const deskMetrics = [
      {label: '今日会话', value: overview?.today_conversations ?? conversations.length, hint: '实时客服入口'},
      {label: '待审核', value: replyDraftQueue.length, hint: replyDraftQueue.length ? '需要人工确认' : '队列清爽', warn: replyDraftQueue.length > 0},
      {label: '高风险', value: riskyDraftCount, hint: riskyDraftCount ? '优先处理' : '暂无拦截', warn: riskyDraftCount > 0},
      {label: '外发准备', value: replyDispatches.length, hint: '复制或 API 发送'},
      {label: '知识条目', value: knowledge.length, hint: knowledge.length ? '可检索' : '先导入资料'},
      {label: 'Agent 动作', value: desktopAgentLogs.length, hint: latestAgentAction?.status || '暂无动作'}
    ];
    const pipelineSteps = [
      {label: '监听消息', value: electronAgentStatus?.running ? '运行中' : '待启动', state: electronAgentStatus?.running ? 'ok' : 'warn'},
      {label: '知识库回复', value: knowledge.length ? '可生成' : '缺资料', state: knowledge.length ? 'ok' : 'warn'},
      {label: '人工审核', value: replyDraftQueue.length ? `${replyDraftQueue.length} 条` : '无积压', state: replyDraftQueue.length ? 'warn' : 'ok'},
      {label: '受控外发', value: globallyPaused ? '已暂停' : desktopAgentMode, state: globallyPaused ? 'blocked' : 'ok'}
    ];
    const latestCustomerText = selectedConversation?.last_query || replyDraft.message;
    const customerNeed = latestCustomerText.includes('价格') || latestCustomerText.includes('多少钱')
      ? '价格与套餐'
      : latestCustomerText.includes('退款') || latestCustomerText.includes('售后')
        ? '售后与风险'
        : latestCustomerText.includes('接入') || latestCustomerText.includes('官网')
          ? '接入咨询'
          : '需求识别';
    const customerProfileItems = [
      {label: '客户阶段', value: selectedConversation?.need_followup ? '人工确认阶段' : replyDraft.reply ? '回复审核阶段' : '首次咨询阶段'},
      {label: '核心需求', value: customerNeed},
      {label: '最近触点', value: activeChannel?.display_name || channelNames[replyDraft.channel] || replyDraft.channel},
      {label: '缺失信息', value: currentIntentScore >= 70 ? '联系方式 / 预算 / 时间' : '预算 / 使用场景'}
    ];
    const intentReasons = [
      currentIntentScore >= 70 ? '表达明确购买或接入意向' : '意向仍需通过追问确认',
      selectedConversation?.need_followup ? '命中人工接管规则' : '未命中强制人工接管',
      latestCustomerText.length > 18 ? '客户问题包含可分析上下文' : '客户信息较短'
    ];
    const recommendedActions = [
      nextBestAction,
      currentIntentScore >= 70 ? '索要联系方式并安排人工跟进' : '补问行业、渠道和咨询量',
      knowledge.length ? '引用知识库边界回答' : '先补充价格、售后、接入资料'
    ];
    const citationSources = knowledge.slice(0, 3);

    return (
      <div className="aiServiceDesk">
        <div className="aiDeskHero">
          <div>
            <p>AI Service Desk</p>
            <h1>AI 客服工作台</h1>
            <span>一个客服坐席可直接使用的生产控制台：监听客户消息，生成知识库回复，人工审核后受控外发。</span>
          </div>
          <div className="aiDeskHeroActions">
            <button onClick={() => selectedConversation && setReplyDraft((current) => ({
              ...current,
              customer_name: selectedConversation.visitor_name || current.customer_name,
              message: selectedConversation.last_query || current.message,
              channel: 'web_widget'
            }))} disabled={!selectedConversation}>
              <Inbox size={16} />带入当前会话
            </button>
            <button className="primaryButton fit" onClick={generateReplyDraft} disabled={loading || !replyDraft.message.trim()}>
              <Sparkles size={16} />生成回复
            </button>
          </div>
        </div>

        <section className="aiOpsStrip">
          <div className="aiOpsStatus">
            <div>
              <small>AI Engine</small>
              <strong>{aiHealthText}</strong>
            </div>
            <div>
              <small>Desktop Agent</small>
              <strong>{globallyPaused ? '人工暂停' : electronAgentStatus?.running ? '监听中' : '待启动'}</strong>
            </div>
            <div>
              <small>Workflow</small>
              <strong>{aiWorkflow ? '客服闭环已接入' : '未接入'}</strong>
            </div>
            <button className={globallyPaused ? 'resumeButton' : 'pauseButton'} onClick={() => setDesktopAgentPaused(!globallyPaused)} disabled={loading}>
              <ShieldAlert size={16} />{globallyPaused ? '恢复自动辅助' : '紧急暂停'}
            </button>
          </div>
          <div className="aiPipeline">
            {pipelineSteps.map((step, index) => (
              <div className={`aiPipelineStep ${step.state}`} key={step.label}>
                <span>{index + 1}</span>
                <div>
                  <strong>{step.label}</strong>
                  <small>{step.value}</small>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="aiDeskMetrics">
          {deskMetrics.map((metric) => (
            <article className={`aiMetricTile ${metric.warn ? 'warn' : ''}`} key={metric.label}>
              <small>{metric.label}</small>
              <strong>{metric.value}</strong>
              <span>{metric.hint}</span>
            </article>
          ))}
        </div>

        <div className="aiDeskGrid">
          <aside className="aiDeskColumn">
            <section className="aiDeskSurface">
              <div className="aiSurfaceHeader">
                <div>
                  <small>Desktop Agent</small>
                  <strong>{globallyPaused ? '人工接管中' : electronAgentStatus?.running ? '本机监听运行中' : '等待启动'}</strong>
                </div>
                <em className={`pill ${globallyPaused ? 'blocked' : electronAgentStatus?.running ? 'connected' : 'ready'}`}>
                  {globallyPaused ? 'paused' : electronAgentStatus?.running ? 'running' : 'ready'}
                </em>
              </div>
              <div className="agentModeControl">
                <label>模式
                  <select value={desktopAgentMode} onChange={(event) => setDesktopAgentMode(event.target.value as DesktopAgentMode)}>
                    <option value="assist">只生成草稿</option>
                    <option value="auto_paste">自动粘贴</option>
                    <option value="auto_send">守卫自动发送</option>
                    <option value="paused">暂停</option>
                  </select>
                </label>
                <div className="deskButtonRow">
                  <button onClick={startLocalDesktopAgent} disabled={loading || !canControlLocalAgent}><Bot size={16} />启动</button>
                  <button onClick={stopLocalDesktopAgent} disabled={!canControlLocalAgent || !electronAgentStatus?.running}>停止</button>
                  <button onClick={() => setDesktopAgentPaused(!globallyPaused)} disabled={loading}><ShieldAlert size={16} />{globallyPaused ? '恢复' : '暂停'}</button>
                </div>
              </div>
              <div className="agentStatusLine">
                <span>会话 <b>{desktopAgentState?.sessions.length ?? 0}</b></span>
                <span>Workflow <b>{aiWorkflow ? '已接入' : '未接入'}</b></span>
                <span>最近 <b>{latestAgentAction?.status || '暂无'}</b></span>
              </div>
            </section>

            <section className="aiDeskSurface">
              <div className="aiSurfaceHeader">
                <div><small>Web Widget</small><strong>网页客服入口</strong></div>
                <a className="compactLink" href={widgetTestUrl} target="_blank" rel="noreferrer"><Code2 size={15} />预览入口</a>
              </div>
              <pre className="miniCode">{widgetCode}</pre>
              <button onClick={() => copyText(widgetCode, '接入代码已复制。')}><Clipboard size={16} />复制接入代码</button>
            </section>

            <section className="aiDeskSurface liveSessionSurface">
              <div className="aiSurfaceHeader">
                <div><small>Live Inbox</small><strong>最近会话</strong></div>
                <small>{conversations.length} 条</small>
              </div>
              <div className="compactConversationList">
                {conversations.length === 0 && <EmptyState text="暂无会话。接入网页客服后，客户咨询会进入这里。" />}
                {conversations.slice(0, 6).map((item) => (
                  <button className={item.session_id === selectedConversation?.session_id ? 'active' : ''} key={item.session_id} onClick={() => setSelectedSessionId(item.session_id)}>
                    <strong>{item.visitor_name || '访客'} · 意向 {item.intent_score}</strong>
                    <span>{item.last_query}</span>
                    <small>{item.need_followup ? '需人工接管' : '可自动辅助'} · {asDateText(item.updated_at)}</small>
                  </button>
                ))}
              </div>
            </section>
          </aside>

          <section className="replyComposerSurface">
            <div className="replyComposerHeader">
              <div>
                <small>Reply Studio</small>
                <h2>生成一条可审核的企业回复</h2>
                <span>{activeChannel?.display_name || channelNames[replyDraft.channel] || replyDraft.channel} · {activeChannel?.mode || 'assist'} · {activeChannel?.status || 'draft'}</span>
              </div>
              <div className="deskButtonRow">
                <button onClick={queueReplyDraft} disabled={loading || !replyDraft.message.trim()}><ShieldAlert size={16} />加入审核</button>
                <button onClick={() => copyText(replyDraft.reply, '回复已复制。')} disabled={!replyDraft.reply}><Clipboard size={16} />复制回复</button>
              </div>
            </div>

            <div className="customerContextBar">
              <div>
                <small>当前客户</small>
                <strong>{selectedConversation?.visitor_name || replyDraft.customer_name || '未选择客户'}</strong>
                <span>{selectedConversation?.last_query || replyDraft.message || '输入客户原话后开始生成'}</span>
              </div>
              <div className="customerContextStats">
                <span className={customerTemperatureClass}><Target size={15} />{customerTemperature} · {currentIntentScore}</span>
                <span><Headphones size={15} />{selectedConversation?.need_followup ? '需人工跟进' : '可自动辅助'}</span>
                <span><Users size={15} />{activeMessages.length || selectedConversation?.message_count || 0} 条消息</span>
                <span><Workflow size={15} />{nextBestAction}</span>
              </div>
            </div>

            <div className="aiInsightGrid">
              <section>
                <small>客户画像</small>
                {customerProfileItems.map((item) => (
                  <div key={item.label}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </section>
              <section>
                <small>意向评分</small>
                <div className="intentScoreDial">
                  <strong>{currentIntentScore}</strong>
                  <span>{customerTemperature}</span>
                </div>
                {intentReasons.map((item) => <p key={item}>{item}</p>)}
              </section>
              <section>
                <small>推荐动作</small>
                {recommendedActions.map((item) => (
                  <p key={item}><Target size={14} />{item}</p>
                ))}
              </section>
            </div>

            <div className="replyInputGrid">
              <label>渠道
                <select value={replyDraft.channel} onChange={(event) => setReplyDraft({...replyDraft, channel: event.target.value})}>
                  {channels.map((channel) => <option key={channel.channel} value={channel.channel}>{channel.display_name || channelNames[channel.channel] || channel.channel}</option>)}
                </select>
              </label>
              <label>客户名
                <input value={replyDraft.customer_name} onChange={(event) => setReplyDraft({...replyDraft, customer_name: event.target.value})} placeholder="可选" />
              </label>
              <label className="wide">客户原话
                <textarea className="replyMessageInput" value={replyDraft.message} onChange={(event) => setReplyDraft({...replyDraft, message: event.target.value})} />
              </label>
            </div>

            <div className="replyPolicyPanel">
              <div className="aiSurfaceHeader">
                <div><small>Quality Policy</small><strong>AI 客服策略配置</strong></div>
                <button onClick={saveReplyPolicyToKnowledge} disabled={loading}><Database size={16} />保存为知识库</button>
              </div>
              <div className="replyPolicyGrid">
                <label>语气<input value={replyPolicyDraft.tone} onChange={(event) => setReplyPolicyDraft({...replyPolicyDraft, tone: event.target.value})} /></label>
                <label>回复目标<input value={replyPolicyDraft.goal} onChange={(event) => setReplyPolicyDraft({...replyPolicyDraft, goal: event.target.value})} /></label>
                <label className="wide">知识边界<textarea value={replyPolicyDraft.boundary} onChange={(event) => setReplyPolicyDraft({...replyPolicyDraft, boundary: event.target.value})} /></label>
                <label className="wide">转人工规则<textarea value={replyPolicyDraft.handoff_rule} onChange={(event) => setReplyPolicyDraft({...replyPolicyDraft, handoff_rule: event.target.value})} /></label>
                <label className="wide">禁止承诺词<input value={replyPolicyDraft.forbidden_terms} onChange={(event) => setReplyPolicyDraft({...replyPolicyDraft, forbidden_terms: event.target.value})} /></label>
              </div>
            </div>

            <div className="replyOutputPanel">
              <div className="aiSurfaceHeader">
                <div><small>AI Reply Suggestion</small><strong>AI 回复建议</strong></div>
                <button className="primaryButton fit" onClick={generateReplyDraft} disabled={loading || !replyDraft.message.trim()}><Send size={16} />重新生成</button>
              </div>
              <textarea className="replyResultBox" value={replyDraft.reply} onChange={(event) => setReplyDraft({...replyDraft, reply: event.target.value})} placeholder="AI 会基于客户原话、回复策略和知识库生成建议。人工确认后再复制或加入审核队列。" />
              <div className="qualityChecklist">
                {qualityChecks.map((item) => (
                  <span className={item.state} key={item.label}>
                    <ListChecks size={15} />
                    <b>{item.label}</b>
                    {item.value}
                  </span>
                ))}
              </div>
            </div>

            <div className="citationPanel">
              <div className="aiSurfaceHeader">
                <div><small>Knowledge Sources</small><strong>知识库引用来源</strong></div>
                <small>{citationSources.length} 条可用</small>
              </div>
              <div className="citationList">
                {citationSources.length === 0 && <EmptyState text="知识库暂无可引用内容。导入企业资料后，AI 回复会有更清晰边界。" />}
                {citationSources.map((item) => (
                  <article key={item.id || item.title}>
                    <strong>{item.title}</strong>
                    <span>{item.source_type}{item.tags ? ` · ${item.tags}` : ''}</span>
                    <p>{item.content}</p>
                  </article>
                ))}
              </div>
            </div>
          </section>

          <aside className="aiDeskColumn reviewColumn">
            <section className="aiDeskSurface queueSurface">
              <div className="aiSurfaceHeader">
                <div><small>Human Review</small><strong>人工确认队列</strong></div>
                <small>{replyDraftQueue.length} 条</small>
              </div>
              {replyDraftQueue.length === 0 && <EmptyState text="暂无待确认回复草稿。" />}
              {replyDraftQueue.slice(0, 5).map((item) => (
                <article className="aiQueueItem" key={item.id}>
                  <div>
                    <strong>{channelNames[item.connector] || item.connector} · 意向 {item.intent_score}</strong>
                    <em className={`pill ${item.risk_flags.length ? 'blocked' : 'ready'}`}>{item.risk_flags.length ? '需人工' : '待审'}</em>
                  </div>
                  <p>{displaySourceText(item.source_text)}</p>
                  <textarea value={item.draft_text} onChange={(event) => setReplyDraftQueue((current) => current.map((draft) => draft.id === item.id ? {...draft, draft_text: event.target.value} : draft))} />
                  <small>{item.customer_name || '未知客户'} · {asDateText(item.created_at)} {item.risk_flags.length ? `· 风险：${item.risk_flags.join(' / ')}` : ''}</small>
                  <div className="deskButtonRow">
                    <button onClick={() => copyText(item.draft_text, '回复草稿已复制，请在平台人工确认后发送。')}><Clipboard size={15} />复制</button>
                    <button onClick={() => reviewReplyDraft(item, 'approved')} disabled={loading}><Save size={15} />通过</button>
                    <button onClick={() => reviewReplyDraft(item, 'approved', true)} disabled={loading}><Send size={15} />准备发送</button>
                    <button onClick={() => reviewReplyDraft(item, 'rejected')} disabled={loading}><ShieldAlert size={15} />驳回</button>
                  </div>
                </article>
              ))}
            </section>

            <section className="aiDeskSurface queueSurface">
              <div className="aiSurfaceHeader">
                <div><small>Dispatch Gate</small><strong>外发准备</strong></div>
                <small>{replyDispatches.length} 条</small>
              </div>
              {replyDispatches.length === 0 && <EmptyState text="通过并准备发送后会进入这里。" />}
              {replyDispatches.slice(0, 5).map((item) => (
                <article className="aiQueueItem" key={item.id}>
                  <div>
                    <strong>{channelNames[item.connector] || item.connector} · {item.dispatch_mode}</strong>
                    <em className={`pill ${item.status === 'revoked' || item.status === 'blocked' ? 'blocked' : 'ready'}`}>{item.status}</em>
                  </div>
                  <p>{item.draft_text}</p>
                  <small>{item.operator || 'system'} · {asDateText(item.created_at)} {item.risk_flags.length ? `· 风险：${item.risk_flags.join(' / ')}` : ''}</small>
                  <div className="deskButtonRow">
                    <button onClick={() => copyText(item.draft_text, '外发文案已复制，请在平台人工确认后发送。')}><Clipboard size={15} />复制</button>
                    <button onClick={() => sendReplyDispatch(item)} disabled={loading || item.status === 'revoked' || item.status === 'sent' || item.status === 'blocked'}><Send size={15} />API 发送</button>
                    <button onClick={() => revokeReplyDispatch(item)} disabled={loading || item.status === 'revoked'}><ShieldAlert size={15} />撤回</button>
                  </div>
                </article>
              ))}
            </section>

            <section className="aiDeskSurface queueSurface">
              <div className="aiSurfaceHeader">
                <div><small>Workflow Log</small><strong>运行日志</strong></div>
                <small>{latestAiWorkflowRun?.status || '暂无'}</small>
              </div>
              {desktopAgentLogs.length === 0 && <EmptyState text="暂无桌面 Agent 动作。" />}
              {desktopAgentLogs.slice(0, 5).map((item) => (
                <article className="aiLogRow" key={item.action_id}>
                  <strong>{item.action} · {item.status}</strong>
                  <span>{item.message_excerpt || item.reason || item.reply_text || '无摘要'}</span>
                  <small>{channelNames[item.channel || item.platform || ''] || item.channel || item.platform || 'desktop'} · {asDateText(item.created_at || item.updated_at)}</small>
                </article>
              ))}
            </section>
          </aside>
        </div>
        {renderConversationInbox()}
      </div>
    );
  }

  function renderCrm() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Customer Intelligence" title="客户管理" desc="统一客户、线索、会话、标签、意向分和人工跟进，让 AI 客服沉淀成可成交客户资产。" />
        <div className="metricGrid six">
          <Metric label="CRM线索" value={crmOverview?.leads ?? crmLeads.length} />
          <Metric label="高意向" value={crmOverview?.high_intent ?? crmLeads.filter((item) => item.intent_score >= 70).length} />
          <Metric label="需跟进" value={crmOverview?.needs_followup ?? crmLeads.filter((item) => item.status === 'needs_followup').length} warn />
          <Metric label="跟进任务" value={crmOverview?.open_tasks ?? crmTasks.length} warn />
          <Metric label="已接入渠道" value={connectors.filter((item) => item.status === 'connected' || item.status === 'assist_only').length} />
          <Metric label="今日自动回复" value={overview?.auto_replies ?? 0} />
        </div>
        <div className="operatorGrid">
          <section className="panel">
            <div className="panelHeader"><strong>CRM 线索</strong><small>{crmLeads.length} 条</small></div>
            {crmLeads.length === 0 && <EmptyState text="暂无 CRM 线索。网页客服高意向咨询或手动录入后会进入这里。" />}
            {crmLeads.slice(0, 8).map((lead) => (
              <article className="knowledgeItem" key={lead.id}>
                <strong>{lead.name || '未命名线索'} · 意向 {lead.intent_score}</strong>
                <p>{lead.need || '暂无需求描述'}</p>
                <small>{lead.source} · {lead.sales_stage} · {lead.contact || '无联系方式'} {lead.tags.length ? `· ${lead.tags.join(' / ')}` : ''}</small>
              </article>
            ))}
          </section>
          <section className="panel">
            <div className="panelHeader"><strong>跟进任务</strong><small>{crmTasks.length} 条</small></div>
            {crmTasks.length === 0 && <EmptyState text="暂无打开中的跟进任务。高意向消息、人工接管或新线索会自动生成任务。" />}
            {crmTasks.slice(0, 8).map((task) => (
              <article className="knowledgeItem" key={task.id}>
                <strong>{task.title} · {task.priority === 'high' ? '高优先级' : task.priority}</strong>
                <p>{task.target_type} #{task.target_id}</p>
                <small>{task.source} · {task.status} · {task.due_at || task.updated_at}</small>
              </article>
            ))}
          </section>
        </div>
        {renderConversationInbox()}
      </div>
    );
  }

  function renderKnowledge() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Knowledge Base" title="知识库" desc="导入企业 FAQ、商品资料、售后政策和客服话术，作为 AI 客服统一知识来源。" />
        <section className="panel">
          <div className="panelHeader"><strong>导入结构化知识</strong><button onClick={importKnowledge} disabled={loading}><Database size={16} />导入</button></div>
          <div className="formGrid">
            <label>标题<input value={importDraft.title} onChange={(event) => setImportDraft({...importDraft, title: event.target.value})} /></label>
            <label>标签<input value={importDraft.tags} onChange={(event) => setImportDraft({...importDraft, tags: event.target.value})} /></label>
            <label>类型
              <select value={importDraft.source_type} onChange={(event) => setImportDraft({...importDraft, source_type: event.target.value})}>
                <option value="faq">FAQ</option>
                <option value="script">客服话术</option>
                <option value="product">商品资料</option>
                <option value="policy">售后政策</option>
                <option value="manual">手动资料</option>
              </select>
            </label>
            <label className="wide">内容<textarea className="largeText" value={importDraft.content} onChange={(event) => setImportDraft({...importDraft, content: event.target.value})} /></label>
          </div>
          <div className="uploadStrip">
            <div>
              <strong>添加文档</strong>
              <small>支持 txt、md、csv、json、PDF 和 Word DOCX，解析后可同步 FAQ。</small>
            </div>
            <label className="filePicker">
              <input type="file" accept=".txt,.md,.csv,.json,.pdf,.docx,text/plain,text/markdown,application/json,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setKnowledgeFile(event.target.files?.[0] ?? null)} />
              {knowledgeFile ? knowledgeFile.name : '选择文档'}
            </label>
            <button className="primaryButton fit" onClick={uploadKnowledgeFile} disabled={loading || !knowledgeFile}><Database size={16} />上传并解析</button>
          </div>
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>FAQ</strong><button onClick={addFaq}>添加问题</button></div>
          {profile.faq.map((item, index) => (
            <div className="faqRow" key={index}>
              <input placeholder="客户常问问题" value={item.question} onChange={(event) => updateFaq(index, {question: event.target.value})} />
              <textarea placeholder="标准答案" value={item.answer} onChange={(event) => updateFaq(index, {answer: event.target.value})} />
            </div>
          ))}
          <button className="primaryButton fit" onClick={saveProfile} disabled={loading}><Save size={16} />保存 FAQ</button>
        </section>
        <div className="knowledgeList">
          {knowledge.length === 0 && <EmptyState text="暂无知识条目。导入 FAQ 或文档后会显示真实数据。" />}
          {knowledge.map((item) => (
            <article className="knowledgeItem" key={item.id ?? `${item.title}-${item.created_at}`}>
              <strong>{item.title}</strong>
              <p>{item.content}</p>
              <small>{item.source_type} · {item.tags || '未打标签'} · {item.created_at}</small>
            </article>
          ))}
        </div>
      </div>
    );
  }

  function renderProducts() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Product Center" title="商品中心" desc="生成商品主图、详情图、短视频预览、上架文案和客服 FAQ。当前使用真实后端生成接口。" />
        <div className="commerceFactory">
          <section className="commerceInputColumn">
            <div className="panel cleanFormPanel">
              <div className="panelHeader"><strong>商品资料</strong><button onClick={generateProductMediaPack} disabled={loading}><Sparkles size={16} />生成素材包</button></div>
              <div className="formGrid">
                <label>商品名<input value={mediaDraft.product_name} onChange={(event) => setMediaDraft({...mediaDraft, product_name: event.target.value})} /></label>
                <label>类目<input value={mediaDraft.category} onChange={(event) => setMediaDraft({...mediaDraft, category: event.target.value})} /></label>
                <label>平台
                  <select value={mediaDraft.platform} onChange={(event) => setMediaDraft({...mediaDraft, platform: event.target.value})}>
                    <option value="douyin">抖音小店</option>
                    <option value="taobao">淘宝</option>
                    <option value="pdd">拼多多</option>
                    <option value="xianyu">闲鱼</option>
                    <option value="xiaohongshu">小红书店铺</option>
                  </select>
                </label>
                <label>价格<input value={mediaDraft.price} onChange={(event) => setMediaDraft({...mediaDraft, price: event.target.value})} /></label>
                <label>目标买家<input value={mediaDraft.audience} onChange={(event) => setMediaDraft({...mediaDraft, audience: event.target.value})} /></label>
                <label>视觉风格<input value={mediaDraft.visual_style} onChange={(event) => setMediaDraft({...mediaDraft, visual_style: event.target.value})} /></label>
                <label className="wide">核心卖点<textarea value={mediaDraft.selling_points} onChange={(event) => setMediaDraft({...mediaDraft, selling_points: event.target.value})} /></label>
                <label className="wide fileInputLabel">商品图片
                  <input type="file" accept="image/*" onChange={(event) => setMediaImageFile(event.target.files?.[0] ?? null)} />
                  <small>{mediaImageFile ? mediaImageFile.name : '上传商品实拍图后，生成结果会更贴近商品。'}</small>
                </label>
              </div>
            </div>
            {mediaStatus && <div className="statusText">{mediaStatus}</div>}
          </section>
          <section className="commerceOutputColumn">
            {!mediaPack && <EmptyState text="还没有生成商品素材包。点击生成后展示主图、详情图、视频预览和上架资料。" />}
            {mediaPack && (
              <div className="mediaPackView">
                <div className="commerceResultHeader">
                  <div>
                    <small>已生成</small>
                    <h2>{mediaPack.product_name}</h2>
                    <p>{mediaPack.video_status === 'rendered' ? '包含 MP4 视频' : '包含视频预览'}</p>
                  </div>
                  <button onClick={generateProductMediaPack} disabled={loading}><RefreshCw size={16} />重新生成</button>
                </div>
                <div className="mediaAssetGrid">
                  <a href={artifactUrl(mediaPack.main_image_url)} target="_blank" rel="noreferrer">
                    <strong>商品主图</strong>
                    <img src={artifactUrl(mediaPack.main_image_url)} alt="商品主图" />
                  </a>
                  <a href={artifactUrl(mediaPack.detail_image_url)} target="_blank" rel="noreferrer">
                    <strong>详情图</strong>
                    <img src={artifactUrl(mediaPack.detail_image_url)} alt="详情图" />
                  </a>
                  {mediaPack.scenes.slice(0, 2).map((scene) => (
                    <a href={artifactUrl(scene.asset_url)} target="_blank" rel="noreferrer" key={scene.title}>
                      <strong>{scene.title}</strong>
                      <img src={artifactUrl(scene.asset_url)} alt={scene.title} />
                      <small>{scene.visual}</small>
                    </a>
                  ))}
                </div>
                <div className="videoPreviewBox">
                  <div className="panelHeader"><strong>短视频预览</strong><a href={artifactUrl(mediaPack.video_url || mediaPack.video_preview_url)} target="_blank" rel="noreferrer">打开</a></div>
                  {mediaPack.video_url ? <video src={artifactUrl(mediaPack.video_url)} controls /> : <iframe title="商品短视频预览" src={artifactUrl(mediaPack.video_preview_url)} />}
                </div>
                <div className="listingDraftBox">
                  <small>推荐标题</small>
                  <p>{mediaPack.listing_draft.titles[0]}</p>
                  <div className="sellingPointList">
                    {mediaPack.listing_draft.selling_points.map((point) => <span key={point}>{point}</span>)}
                  </div>
                  <button onClick={() => copyText(JSON.stringify(mediaPack.listing_draft, null, 2), '上架资料已复制。')}><Clipboard size={16} />复制上架资料</button>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    );
  }

  function renderDesktopAgentPanel(canControlLocalAgent: boolean, globallyPaused: boolean) {
    return (
      <section className="panel desktopAgentPanel">
        <div className="panelHeader">
          <strong>桌面客服助手</strong>
          <div className="rowActions">
            <button onClick={refreshDesktopAgentState} disabled={loading}><RefreshCw size={16} />同步状态</button>
            <button onClick={() => setDesktopAgentPaused(!globallyPaused)} disabled={loading}>
              <ShieldAlert size={16} />{globallyPaused ? '恢复' : '暂停'}
            </button>
          </div>
        </div>
        <div className="desktopAgentControls">
          <label>运行模式
            <select value={desktopAgentMode} onChange={(event) => setDesktopAgentMode(event.target.value as DesktopAgentMode)}>
              <option value="assist">只生成草稿</option>
              <option value="auto_paste">自动粘贴</option>
              <option value="auto_send">守卫自动发送</option>
              <option value="paused">暂停</option>
            </select>
          </label>
          <div className="desktopAgentButtons">
            <button className="primaryButton fit" onClick={startLocalDesktopAgent} disabled={loading || !canControlLocalAgent}>
              <Bot size={16} />启动本机助手
            </button>
            <button className="ghostButton fit" onClick={stopLocalDesktopAgent} disabled={!canControlLocalAgent || !electronAgentStatus?.running}>停止</button>
            <button className="ghostButton fit" onClick={refreshElectronAgentStatus} disabled={!canControlLocalAgent}>查看状态</button>
          </div>
        </div>
        <div className="desktopDownloadRow">
          <a className="downloadTile" href={apiUrl('/downloads/AI-Customer-Agent-Windows.exe')} download>
            <Package size={18} />
            <span>
              <strong>Windows 安装包</strong>
              <small>AI-Customer-Agent-Windows.exe</small>
            </span>
          </a>
          <div className="downloadTile disabledTile">
            <Package size={18} />
            <span>
              <strong>macOS 暂未开放</strong>
              <small>真实 macOS DMG 验收通过后开放</small>
            </span>
          </div>
        </div>
        <div className="metricGrid desktopAgentMetrics">
          <Metric label="Sessions" value={desktopAgentState?.sessions.length ?? 0} />
          <Metric label="Actions" value={desktopAgentLogs.length} />
        </div>
        <div className="desktopAgentStatusRow">
          <span>Backend gate <b>{globallyPaused ? 'Paused' : 'Active'}</b></span>
          <span>Local process <b>{electronAgentStatus?.running ? `PID ${electronAgentStatus.pid}` : canControlLocalAgent ? 'Stopped' : 'Browser'}</b></span>
        </div>
        <div className="desktopAgentColumns">
          <div>
            <div className="panelHeader"><strong>Sessions</strong><small>{desktopAgentState?.sessions.length ?? 0}</small></div>
            {(desktopAgentState?.sessions.length ?? 0) === 0 && <EmptyState text="No desktop Agent session yet." />}
            {desktopAgentState?.sessions.slice(0, 4).map((session) => (
              <article className="knowledgeItem" key={session.session_id}>
                <strong>{session.device_name || session.session_id}</strong>
                <p>{session.os_name || '-'} / {session.platform} / {session.mode}</p>
                <small>{session.paused ? 'paused' : 'active'} · {asDateText(session.last_heartbeat_at || session.updated_at)}</small>
              </article>
            ))}
          </div>
          <div>
            <div className="panelHeader"><strong>Recent Actions</strong><small>{desktopAgentLogs.length}</small></div>
            {desktopAgentLogs.length === 0 && <EmptyState text="No desktop automation action yet." />}
            {desktopAgentLogs.slice(0, 5).map((item) => (
              <article className="knowledgeItem" key={item.action_id}>
                <strong>{item.action} · {item.status}</strong>
                <p>{item.message_excerpt || item.reason || 'No summary'}</p>
                <small>
                  AI {item.reply_meta?.ai_model || item.reply_meta?.ai_mode || '-'} /
                  confidence {typeof item.reply_meta?.confidence === 'number' ? `${Math.round(item.reply_meta.confidence * 100)}%` : '-'} /
                  citations {item.reply_meta?.citations?.length ?? 0} /
                  send {String(item.result?.status || item.status || '-')}
                </small>
                {item.reply_text && <small>{item.reply_text.slice(0, 120)}</small>}
                <small>{item.platform || '-'} · {item.source || '-'} · {asDateText(item.created_at)}</small>
              </article>
            ))}
          </div>
        </div>
        {electronAgentStatus?.logs?.length ? (
          <div className="runLog">
            <div className="panelHeader"><strong>Local Agent Output</strong><small>{electronAgentStatus.logs.length}</small></div>
            <pre>{electronAgentStatus.logs.slice(-12).map((line) => `[${line.type}] ${line.text}`).join('\n')}</pre>
          </div>
        ) : null}
      </section>
    );
  }

  function renderAutomation() {
    const canControlLocalAgent = Boolean(window.merchantDesktop?.desktopAgent);
    const globallyPaused = Boolean(desktopAgentState?.pauses.some((item) => item.paused && !item.platform && !item.window_title));
    return (
      <div className="pageStack">
        {renderDesktopAgentPanel(canControlLocalAgent, globallyPaused)}
        <PageTitle eyebrow="Workflow" title="自动化" desc="消息、线索、定时和人工触发统一进入 Workflow；高风险动作继续要求人工确认。" />
        <section className="panel">
          <div className="panelHeader"><strong>Workflow 定义</strong><small>{workflowDefinitions.length} 个</small></div>
          {workflowDefinitions.length === 0 && <EmptyState text="暂无 Workflow 定义。请检查后端自动化配置。" />}
          <div className="localScriptGrid">
            {workflowDefinitions.map((definition) => (
              <article className="scriptLaunchCard" key={definition.id}>
                <strong>{definition.name}</strong>
                <span>{definition.description || `${definition.module} · ${definition.trigger.type}`}</span>
                <small>{definition.module} · {definition.trigger.type}{definition.trigger.source ? ` / ${definition.trigger.source}` : ''} · {definition.actions.length} 个动作</small>
                <button onClick={() => runWorkflow(definition)} disabled={!definition.enabled || loading}><Send size={16} />手动运行</button>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>Workflow 运行记录</strong><small>{workflowRuns.length} 条</small></div>
          {workflowRuns.length === 0 && <EmptyState text="暂无 Workflow 运行记录。AI 客服自动化运行后会写入这里。" />}
          {workflowRuns.map((run) => (
            <article className="knowledgeItem" key={run.id}>
              <strong>{run.workflow_id} · {statusNames[run.status] || run.status}</strong>
              <p>{run.action_logs.length ? run.action_logs[run.action_logs.length - 1]?.message : '暂无动作日志'}</p>
              <small>{asDateText(run.created_at)} · {run.id}</small>
            </article>
          ))}
        </section>
      </div>
    );
  }

  function renderAiDecision() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="AI Engine" title="AI 决策中心" desc="所有 AI 能力统一进入 AI Engine。当前展示配置状态，并复用客服脚本生成作为已接通能力。" />
        <div className="cosmosPanel">
          <div>
            <small>AI Engine 状态</small>
            <h2>{aiStatus?.mode === 'ai' ? 'AI 模式已启用' : '当前可能是基础回复模式'}</h2>
            <p>{aiStatus?.message || `Provider: ${String(aiStatus?.provider || '-')}, Model: ${String(aiStatus?.model || '-')}`}</p>
          </div>
          <Brain size={42} />
        </div>
        <section className="panel scriptForm">
          <div className="panelHeader"><strong>客服脚本生成</strong><button onClick={generateServiceScript} disabled={loading}><Send size={16} />生成</button></div>
          <div className="formGrid">
            <label>渠道
              <select value={scriptDraft.channel} onChange={(event) => setScriptDraft({...scriptDraft, channel: event.target.value})}>
                {channels.map((channel) => <option key={channel.channel} value={channel.channel}>{channel.display_name || channelNames[channel.channel] || channel.channel}</option>)}
              </select>
            </label>
            <label>场景
              <select value={scriptDraft.scenario} onChange={(event) => setScriptDraft({...scriptDraft, scenario: event.target.value})}>
                <option value="full_pack">完整成交脚本</option>
                <option value="new_customer">新客开场</option>
                <option value="price">价格咨询</option>
                <option value="objection">异议处理</option>
                <option value="after_sale">售后安抚</option>
                <option value="lead_capture">留资转化</option>
              </select>
            </label>
            <label>产品/服务<input value={scriptDraft.product_name} onChange={(event) => setScriptDraft({...scriptDraft, product_name: event.target.value})} placeholder={profile.products_services || '例如：AI 客服系统'} /></label>
            <label>客户痛点<input value={scriptDraft.customer_pain} onChange={(event) => setScriptDraft({...scriptDraft, customer_pain: event.target.value})} placeholder="例如：回复慢、线索漏跟、知识不统一" /></label>
            <label className="wide">优惠/注意事项<textarea value={scriptDraft.offer} onChange={(event) => setScriptDraft({...scriptDraft, offer: event.target.value})} /></label>
          </div>
        </section>
        {scriptResult && (
          <article className="scriptResult">
            <div className="scriptHero">
              <small>{channelNames[scriptResult.channel] || scriptResult.channel}</small>
              <h2>{scriptResult.title}</h2>
              <p>{scriptResult.opening}</p>
            </div>
            <div className="scriptStepList">
              {scriptResult.steps.map((step, index) => (
                <section className="scriptStep" key={`${step.title}-${index}`}>
                  <em>{String(index + 1).padStart(2, '0')}</em>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.message}</p>
                    <small>{step.goal}</small>
                  </div>
                </section>
              ))}
            </div>
          </article>
        )}
      </div>
    );
  }

  function renderAnalytics() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Analytics" title="数据分析" desc="从咨询承接、AI 回复、人工跟进和客户意向看清 AI 客服带来的经营效率。" />
        <div className="metricGrid six">
          <Metric label="今日会话" value={overview?.today_conversations ?? 0} />
          <Metric label="自动回复" value={overview?.auto_replies ?? 0} />
          <Metric label="线索数" value={overview?.leads ?? 0} />
          <Metric label="待人工" value={overview?.handoff_needed ?? 0} warn />
          <Metric label="知识条目" value={overview?.knowledge_items ?? 0} />
          <Metric label="启用渠道" value={overview?.enabled_channels ?? 0} />
        </div>
        <section className="panel">
          <div className="panelHeader"><strong>订阅和额度</strong><small>{usageSummary?.subscription.plan_id || '未加载'}</small></div>
          {usageSummary ? (
            <div className="statusList">
              <div><span>AI 额度</span><em>{usageSummary.remaining.ai ?? 0} / {usageSummary.subscription.ai_quota}</em></div>
              <div><span>Workflow 额度</span><em>{usageSummary.remaining.workflow ?? 0} / {usageSummary.subscription.workflow_quota}</em></div>
              <div><span>Connector 额度</span><em>{usageSummary.remaining.connector ?? 0} / {usageSummary.subscription.connector_quota}</em></div>
              <div><span>席位</span><em>{teamMembers.length} / {usageSummary.subscription.seats}</em></div>
            </div>
          ) : <EmptyState text="订阅和用量接口暂无返回。" />}
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>最近用量</strong><small>{usageSummary?.period || '-'}</small></div>
          {!usageSummary?.recent.length && <EmptyState text="暂无用量记录。AI、Workflow、Connector 和 CRM 操作会逐步写入这里。" />}
          {usageSummary?.recent.map((item) => (
            <article className="knowledgeItem" key={item.id}>
              <strong>{item.usage_type} · {item.quantity}</strong>
              <p>{item.source || 'system'} {item.target_id ? `· ${item.target_id}` : ''}</p>
              <small>{item.created_at}</small>
            </article>
          ))}
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>经营报表</strong><button onClick={generateBusinessReport} disabled={loading}><BarChart3 size={16} />生成日报</button></div>
          {businessReports.length === 0 && <EmptyState text="暂无经营报表。点击生成日报后会保存一份可复盘报告。" />}
          {businessReports.map((report) => (
            <article className="knowledgeItem" key={report.id}>
              <strong>{report.title}</strong>
              <p>{report.summary}</p>
              <small>{report.report_type} · {report.created_at}</small>
              <div className="switchRow">
                <button onClick={() => copyText(report.content, '报表内容已复制。')}><Clipboard size={16} />复制</button>
                <button onClick={() => exportBusinessReport(report, 'markdown')}><Save size={16} />Markdown</button>
                <button onClick={() => exportBusinessReport(report, 'pdf')}><Save size={16} />PDF</button>
                <button onClick={() => exportBusinessReport(report, 'docx')}><Save size={16} />Word</button>
              </div>
            </article>
          ))}
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>客户交付包</strong><button onClick={generateDeliveryPack} disabled={loading}><Package size={16} />生成交付包</button></div>
          {deliveryPacks.length === 0 && <EmptyState text="暂无交付包。点击生成后会打包 README、验收矩阵、操作手册、安全边界和阶段报告。" />}
          {deliveryPacks.map((pack) => (
            <article className="knowledgeItem" key={pack.id}>
              <strong>{pack.title}</strong>
              <p>{pack.summary}</p>
              <small>{pack.customer_name} · {pack.created_at}</small>
              <div className="switchRow">
                <button onClick={() => window.open(artifactUrl(pack.zip_url), '_blank', 'noopener,noreferrer')} disabled={!pack.zip_url}><Save size={16} />下载 ZIP</button>
                {pack.artifacts.slice(0, 6).map((artifact) => (
                  <button key={`${pack.id}-${artifact.name}`} onClick={() => window.open(artifactUrl(artifact.artifact_url), '_blank', 'noopener,noreferrer')}>
                    <Clipboard size={16} />{artifact.name}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>最终验收巡检</strong><button onClick={runAcceptanceAudit} disabled={loading}><ShieldAlert size={16} />运行巡检</button></div>
          {!acceptanceAudit && <EmptyState text="暂无巡检结果。运行后会生成交付评分、风险边界、阻断项和 Markdown 留档。" />}
          {acceptanceAudit && (
            <>
              <article className="knowledgeItem">
                <strong>就绪评分 {acceptanceAudit.readiness_score}</strong>
                <p>{acceptanceAudit.summary}</p>
                <small>{acceptanceAudit.id} · {acceptanceAudit.created_at}</small>
                <div className="switchRow">
                  <em className={`pill ${auditPillClass(acceptanceAudit.status)}`}>{auditStatusLabel(acceptanceAudit.status)}</em>
                  {acceptanceAudit.artifact_url && <button onClick={() => window.open(artifactUrl(acceptanceAudit.artifact_url), '_blank', 'noopener,noreferrer')}><Save size={16} />打开报告</button>}
                </div>
              </article>
              {acceptanceAudit.blockers.length > 0 && (
                <article className="knowledgeItem">
                  <strong>阻断项</strong>
                  {acceptanceAudit.blockers.map((item) => <p key={item}>{item}</p>)}
                </article>
              )}
              {acceptanceAudit.next_actions.length > 0 && (
                <article className="knowledgeItem">
                  <strong>下一步动作</strong>
                  {acceptanceAudit.next_actions.map((item) => <p key={item}>{item}</p>)}
                </article>
              )}
              {acceptanceAudit.items.map((item) => (
                <article className="knowledgeItem" key={item.module}>
                  <div className="panelHeader">
                    <strong>{item.module}</strong>
                    <em className={`pill ${auditPillClass(item.status)}`}>{auditStatusLabel(item.status)}</em>
                  </div>
                  <p>{item.evidence}</p>
                  {item.next_action && <small>{item.next_action}</small>}
                </article>
              ))}
            </>
          )}
        </section>
      </div>
    );
  }

  function renderSettings() {
    return (
      <div className="pageStack">
        <PageTitle eyebrow="Settings" title="设置" desc="统一管理 Connector、渠道模式和系统接入状态。" />
        <section className="panel">
          <div className="panelHeader"><strong>Connector 注册表</strong><small>{connectors.length} 个</small></div>
          {connectors.length === 0 && <EmptyState text="Connector 状态接口暂无返回。" />}
          <div className="statusList">
            {connectors.map((connector, index) => (
              <div key={`${connector.message}-${index}`}>
                <span>{connector.message || `Connector ${index + 1}`}</span>
                <em className={`pill ${connector.status}`}>{statusNames[connector.status] || connector.status}</em>
              </div>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panelHeader">
            <strong className="inlineTitle"><ListChecks size={18} />平台接入配置向导</strong>
            <div className="headerActions">
              <button onClick={generateIntegrationWorkOrder} disabled={loading || !connectorSetupGuide}><Clipboard size={16} />生成工单</button>
              <button onClick={runIntegrationDryRun} disabled={loading || !connectorSetupGuide}><ShieldAlert size={16} />干跑验收</button>
              <button onClick={syncIntegrationTasks} disabled={loading || !connectorSetupGuide}><Target size={16} />同步任务</button>
              <button onClick={reconcileIntegrationTasks} disabled={loading || !connectorSetupGuide}><RefreshCw size={16} />复验关闭</button>
              <button onClick={generateSLAEscalation} disabled={loading || !integrationSLA}><Clipboard size={16} />升级简报</button>
              <button onClick={generateSLANotice} disabled={loading || !integrationSLA}><Send size={16} />通知草稿</button>
              <button onClick={generateSLALoopReport} disabled={loading || !integrationSLA}><BarChart3 size={16} />闭环报表</button>
              <button onClick={recordPlatformAcceptanceEvidence} disabled={loading}><ShieldAlert size={16} />登记证据</button>
              <button onClick={generatePlatformAcceptanceReport} disabled={loading}><Package size={16} />证据包</button>
              <button onClick={syncPlatformAcceptanceGaps} disabled={loading}><Target size={16} />缺口任务</button>
              <button onClick={reconcilePlatformAcceptanceGaps} disabled={loading}><RefreshCw size={16} />复验缺口</button>
              <button onClick={generatePlatformAcceptanceChecklist} disabled={loading}><ListChecks size={16} />证据清单</button>
              <button onClick={generatePlatformAcceptanceNotice} disabled={loading}><Send size={16} />证据通知</button>
              <button onClick={generatePlatformAcceptanceSubmissionLink} disabled={loading}><Send size={16} />客户提交链接</button>
              <button onClick={generatePlatformAcceptanceEvidenceManifestLink} disabled={loading}><Send size={16} />Manifest link</button>
              <button onClick={generatePlatformAcceptanceEvidenceManifestInbox} disabled={loading}><Inbox size={16} />Manifest inbox</button>
              <button onClick={generatePlatformAcceptanceManifestImportQueue} disabled={loading}><Inbox size={16} />Import queue</button>
              <button onClick={() => runManifestRecoveryResubmission(false)} disabled={loading}><Clipboard size={16} />Recovery preview</button>
              <button onClick={() => runManifestRecoveryResubmission(true)} disabled={loading}><Send size={16} />Recovery resubmit</button>
              <button onClick={generateManifestResubmissionTracker} disabled={loading}><BarChart3 size={16} />Resubmit tracker</button>
              <button onClick={() => generateManifestResubmissionReminder(false)} disabled={loading}><Clipboard size={16} />Reminder preview</button>
              <button onClick={() => generateManifestResubmissionReminder(true)} disabled={loading}><Target size={16} />Create reminder tasks</button>
              <button onClick={generatePlatformAcceptanceManifestFollowupRun} disabled={loading}><Send size={16} />Manifest follow-up</button>
              <button onClick={generatePlatformAcceptanceSprintPack} disabled={loading}><Target size={16} />验收冲刺包</button>
              <button onClick={generatePlatformAcceptanceLiveRun} disabled={loading}><ShieldAlert size={16} />验收作战台</button>
              <button onClick={generatePlatformAcceptanceJointDebugRun} disabled={loading}><PlugZap size={16} />联调执行台</button>
              <button onClick={generatePlatformAcceptanceGapClosureRun} disabled={loading}><Target size={16} />缺口闭环</button>
              <button onClick={generatePlatformAcceptanceOwnerActionPack} disabled={loading}><Clipboard size={16} />负责人交接</button>
              <button onClick={generatePlatformAcceptanceOwnerClosureLink} disabled={loading}><Send size={16} />闭环链接</button>
              <button onClick={generatePlatformAcceptanceOwnerClosureRun} disabled={loading}><RefreshCw size={16} />负责人闭环</button>
              <button onClick={generatePlatformAcceptanceAutoWatchRun} disabled={loading}><ShieldAlert size={16} />自动守护</button>
              <button onClick={generatePlatformAcceptanceFinalClosureRun} disabled={loading}><ShieldAlert size={16} />Final closure</button>
              <button onClick={generatePlatformAcceptanceWatchBoard} disabled={loading}><BarChart3 size={16} />守护看板</button>
              <button onClick={generatePlatformAcceptanceCustomerRoom} disabled={loading}><Send size={16} />验收房间</button>
              <button onClick={generatePlatformAcceptanceFinalSignoffLink} disabled={loading}><ShieldAlert size={16} />签署门禁</button>
              <button onClick={syncPlatformAcceptanceReviewTasks} disabled={loading}><Target size={16} />复核任务</button>
              <button onClick={generatePlatformAcceptanceReviewDesk} disabled={loading}><ListChecks size={16} />Review desk</button>
              <button onClick={() => runPlatformAcceptanceReviewExecution(false)} disabled={loading}><Clipboard size={16} />Execution preview</button>
              <button onClick={() => runPlatformAcceptanceReviewExecution(true)} disabled={loading}><ShieldAlert size={16} />Execute review</button>
              <button onClick={runPlatformAcceptanceEvidenceUrlPrecheck} disabled={loading}><ShieldAlert size={16} />URL precheck</button>
              <button onClick={() => runPlatformAcceptanceEvidenceImport(false)} disabled={loading}><Clipboard size={16} />Import preview</button>
              <button onClick={() => runPlatformAcceptanceEvidenceImport(true)} disabled={loading}><ShieldAlert size={16} />Import evidence</button>
              <button onClick={recordPlatformAcceptanceReviewDecision} disabled={loading}><ShieldAlert size={16} />审核决策</button>
              {connectorSetupGuide && <em className={`pill ${setupPillClass(connectorSetupGuide.status)}`}>{setupStatusLabel(connectorSetupGuide.status)}</em>}
            </div>
          </div>
          {!connectorSetupGuide && <EmptyState text="暂无平台接入配置向导结果。" />}
          {connectorSetupGuide && (
            <>
              <div className="setupGuideSummary">
                <strong>{connectorSetupGuide.summary}</strong>
                <small>{connectorSetupGuide.created_at}</small>
                <div className="setupGuideCounts">
                  <span>已完成 <b>{connectorSetupGuide.counts.done || 0}</b></span>
                  <span>待处理 <b>{connectorSetupGuide.counts.todo || 0}</b></span>
                  <span>阻塞 <b>{connectorSetupGuide.counts.blocked || 0}</b></span>
                </div>
                {integrationWorkOrder && (
                  <div className="setupGuideCounts">
                    <span>最近工单 <b>{integrationWorkOrder.items.length}</b></span>
                    <button onClick={() => window.open(artifactUrl(integrationWorkOrder.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationWorkOrder.artifact_url}><Save size={16} />打开工单</button>
                  </div>
                )}
                {integrationDryRun && (
                  <div className="setupGuideCounts">
                    <span>干跑检查 <b>{integrationDryRun.checks.length}</b></span>
                    <span>状态 <b>{auditStatusLabel(integrationDryRun.status)}</b></span>
                    <button onClick={() => window.open(artifactUrl(integrationDryRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationDryRun.artifact_url}><Save size={16} />打开报告</button>
                  </div>
                )}
                {integrationTaskSync && (
                  <div className="setupGuideCounts">
                    <span>新增任务 <b>{integrationTaskSync.created}</b></span>
                    <span>已存在 <b>{integrationTaskSync.skipped_existing}</b></span>
                    <span>干跑状态 <b>{auditStatusLabel(integrationTaskSync.source_dry_run_status)}</b></span>
                  </div>
                )}
                {integrationTaskReconcile && (
                  <div className="setupGuideCounts">
                    <span>已关闭 <b>{integrationTaskReconcile.closed}</b></span>
                    <span>仍打开 <b>{integrationTaskReconcile.still_open}</b></span>
                    <span>剩余检查 <b>{integrationTaskReconcile.remaining_checks.length}</b></span>
                  </div>
                )}
                {integrationSLA && (
                  <>
                    <div className="setupGuideCounts">
                      <span>打开任务 <b>{integrationSLA.total_open}</b></span>
                      <span>逾期 <b>{integrationSLA.overdue}</b></span>
                      <span>今日到期 <b>{integrationSLA.due_today}</b></span>
                      <span>未排期 <b>{integrationSLA.unscheduled}</b></span>
                    </div>
                    {integrationSLAEscalation && (
                      <div className="setupGuideCounts">
                        <span>简报任务 <b>{integrationSLAEscalation.items.length}</b></span>
                        <span>简报状态 <b>{setupStatusLabel(integrationSLAEscalation.status)}</b></span>
                        <button onClick={() => window.open(artifactUrl(integrationSLAEscalation.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationSLAEscalation.artifact_url}><Save size={16} />打开简报</button>
                      </div>
                    )}
                    {integrationSLANotice && (
                      <div className="setupGuideCounts">
                        <span>通知任务 <b>{integrationSLANotice.items.length}</b></span>
                        <span>通知状态 <b>{setupStatusLabel(integrationSLANotice.status)}</b></span>
                        <button onClick={() => window.open(artifactUrl(integrationSLANotice.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationSLANotice.artifact_url}><Save size={16} />打开通知</button>
                        <button onClick={() => copyText(integrationSLANotice.draft_text, '通知草稿已复制，外发前请人工确认。')} disabled={!integrationSLANotice.draft_text}><Clipboard size={16} />复制草稿</button>
                        <button onClick={() => recordSLANoticeReceipt(false)} disabled={loading || !integrationSLANotice.items.length}><ListChecks size={16} />记录回执</button>
                        <button onClick={() => recordSLANoticeReceipt(true)} disabled={loading || !integrationSLANotice.items.length}><RefreshCw size={16} />确认关闭</button>
                      </div>
                    )}
                    {integrationSLANoticeReceipt && (
                      <div className="setupGuideCounts">
                        <span>回执状态 <b>{setupStatusLabel(integrationSLANoticeReceipt.status)}</b></span>
                        <span>已关闭 <b>{integrationSLANoticeReceipt.closed_tasks.length}</b></span>
                        <span>剩余打开 <b>{integrationSLANoticeReceipt.remaining_open}</b></span>
                        <button onClick={() => window.open(artifactUrl(integrationSLANoticeReceipt.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationSLANoticeReceipt.artifact_url}><Save size={16} />打开回执</button>
                      </div>
                    )}
                    {integrationSLALoopReport && (
                      <div className="setupGuideCounts">
                        <span>复盘状态 <b>{setupStatusLabel(integrationSLALoopReport.status)}</b></span>
                        <span>近期回执 <b>{integrationSLALoopReport.receipts_recent}</b></span>
                        <span>近期关闭 <b>{integrationSLALoopReport.closed_recent}</b></span>
                        <span>审计事件 <b>{integrationSLALoopReport.audit_events.length}</b></span>
                        <button onClick={() => window.open(artifactUrl(integrationSLALoopReport.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!integrationSLALoopReport.artifact_url}><Save size={16} />打开复盘</button>
                      </div>
                    )}
                    {platformAcceptanceEvidence && (
                      <div className="setupGuideCounts">
                        <span>最新证据 <b>{platformAcceptanceEvidence.connector}</b></span>
                        <span>场景 <b>{platformAcceptanceEvidence.scenario}</b></span>
                        <span>结果 <b>{setupStatusLabel(platformAcceptanceEvidence.result)}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceEvidence.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidence.artifact_url}><Save size={16} />打开证据</button>
                      </div>
                    )}
                    {platformAcceptanceReport && (
                      <div className="setupGuideCounts">
                        <span>证据包状态 <b>{setupStatusLabel(platformAcceptanceReport.status)}</b></span>
                        <span>证据 <b>{platformAcceptanceReport.evidence_total}</b></span>
                        <span>缺失场景 <b>{platformAcceptanceReport.missing_scenarios.length}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceReport.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReport.artifact_url}><Save size={16} />打开证据包</button>
                      </div>
                    )}
                    {platformAcceptanceGapSync && (
                      <div className="setupGuideCounts">
                        <span>缺口场景 <b>{platformAcceptanceGapSync.missing_scenarios.length}</b></span>
                        <span>新增任务 <b>{platformAcceptanceGapSync.created}</b></span>
                        <span>已存在 <b>{platformAcceptanceGapSync.skipped_existing}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceGapSync.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceGapSync.artifact_url}><Save size={16} />打开清单</button>
                      </div>
                    )}
                    {platformAcceptanceGapReconcile && (
                      <div className="setupGuideCounts">
                        <span>复验状态 <b>{setupStatusLabel(platformAcceptanceGapReconcile.status)}</b></span>
                        <span>已通过场景 <b>{platformAcceptanceGapReconcile.passed_scenarios.length}</b></span>
                        <span>已关闭 <b>{platformAcceptanceGapReconcile.closed}</b></span>
                        <span>仍打开 <b>{platformAcceptanceGapReconcile.still_open}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceGapReconcile.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceGapReconcile.artifact_url}><Save size={16} />打开复验</button>
                      </div>
                    )}
                    {platformAcceptanceChecklist && (
                      <>
                        <div className="setupGuideCounts">
                          <span>采集状态 <b>{setupStatusLabel(platformAcceptanceChecklist.status)}</b></span>
                          <span>缺失场景 <b>{platformAcceptanceChecklist.missing_scenarios.length}</b></span>
                          <span>清单项 <b>{platformAcceptanceChecklist.items.length}</b></span>
                          <span>缺口任务 <b>{platformAcceptanceChecklist.tasks.length}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceChecklist.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceChecklist.artifact_url}><Save size={16} />打开清单</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceChecklist.items.filter((item) => item.status !== 'passed').slice(0, 5).map((item) => (
                            <article key={item.scenario}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.owner || '未分配'} · {item.due_at || '未排期'} · task {item.task_id || '-'}</span>
                              <small>{item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceNotice && (
                      <div className="setupGuideCounts">
                        <span>通知状态 <b>{setupStatusLabel(platformAcceptanceNotice.status)}</b></span>
                        <span>通知场景 <b>{platformAcceptanceNotice.items.length}</b></span>
                        <span>接收人 <b>{platformAcceptanceNotice.recipient}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceNotice.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceNotice.artifact_url}><Save size={16} />打开通知</button>
                        <button onClick={() => copyText(platformAcceptanceNotice.draft_text, '证据通知草稿已复制，外发前请人工确认。')} disabled={!platformAcceptanceNotice.draft_text}><Clipboard size={16} />复制草稿</button>
                        <button onClick={recordPlatformAcceptanceReceipt} disabled={loading || !platformAcceptanceNotice.items.length}><ListChecks size={16} />记录回执</button>
                      </div>
                    )}
                    {platformAcceptanceSubmissionLink && (
                      <div className="setupGuideCounts">
                        <span>提交链接 <b>{setupStatusLabel(platformAcceptanceSubmissionLink.status)}</b></span>
                        <span>提交场景 <b>{platformAcceptanceSubmissionLink.scenarios.length}</b></span>
                        <span>过期 <b>{platformAcceptanceSubmissionLink.expires_at}</b></span>
                        <button onClick={() => window.open(platformAcceptanceSubmissionLink.submit_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceSubmissionLink.submit_url}><Send size={16} />打开提交页</button>
                        <button onClick={() => copyText(platformAcceptanceSubmissionLink.submit_url, '客户材料提交链接已复制。')} disabled={!platformAcceptanceSubmissionLink.submit_url}><Clipboard size={16} />复制链接</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceSubmissionLink.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceSubmissionLink.artifact_url}><Save size={16} />打开链接单</button>
                      </div>
                    )}
                    {platformAcceptanceEvidenceManifestLink && (
                      <div className="setupGuideCounts">
                        <span>证据清单 <b>{setupStatusLabel(platformAcceptanceEvidenceManifestLink.status)}</b></span>
                        <span>清单场景 <b>{platformAcceptanceEvidenceManifestLink.scenarios.length}</b></span>
                        <span>接收人 <b>{platformAcceptanceEvidenceManifestLink.recipient}</b></span>
                        <span>过期 <b>{platformAcceptanceEvidenceManifestLink.expires_at}</b></span>
                        <button onClick={() => window.open(platformAcceptanceEvidenceManifestLink.manifest_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidenceManifestLink.manifest_url}><Send size={16} />打开清单页</button>
                        <button onClick={() => copyText(platformAcceptanceEvidenceManifestLink.manifest_url, '客户证据清单链接已复制。')} disabled={!platformAcceptanceEvidenceManifestLink.manifest_url}><Clipboard size={16} />复制清单</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceEvidenceManifestLink.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidenceManifestLink.artifact_url}><Save size={16} />打开清单报告</button>
                      </div>
                    )}
                    {platformAcceptanceEvidenceManifestInbox && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Manifest inbox <b>{setupStatusLabel(platformAcceptanceEvidenceManifestInbox.status)}</b></span>
                          <span>Submissions <b>{platformAcceptanceEvidenceManifestInbox.total}</b></span>
                          <span>Ready <b>{platformAcceptanceEvidenceManifestInbox.ready}</b></span>
                          <span>Needs fixes <b>{platformAcceptanceEvidenceManifestInbox.blocked}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceEvidenceManifestInbox.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidenceManifestInbox.artifact_url}><Save size={16} />Open inbox report</button>
                        </div>
                        {platformAcceptanceEvidenceManifestInbox.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceEvidenceManifestInbox.items.slice(0, 5).map((item) => (
                              <article key={`${platformAcceptanceEvidenceManifestInbox.id}-${item.submission_id}`}>
                                <strong>{item.submission_id} 路 {setupStatusLabel(item.status)}</strong>
                                <span>ready {item.ready} 路 blocked {item.blocked} 路 scenarios {item.scenarios.length || '-'}</span>
                                <small>{item.next_action}</small>
                                <button onClick={() => window.open(artifactUrl(item.submission_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.submission_artifact_url}><Save size={16} />Submission</button>
                                <button onClick={() => window.open(artifactUrl(item.import_preview_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.import_preview_artifact_url}><Clipboard size={16} />Import preview</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceManifestImportQueue && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Import queue <b>{setupStatusLabel(platformAcceptanceManifestImportQueue.status)}</b></span>
                          <span>Total <b>{platformAcceptanceManifestImportQueue.total}</b></span>
                          <span>Ready <b>{platformAcceptanceManifestImportQueue.ready}</b></span>
                          <span>Recovered <b>{platformAcceptanceManifestImportQueue.recovered}</b></span>
                          <span>Customer <b>{platformAcceptanceManifestImportQueue.needs_customer}</b></span>
                          <span>Manual <b>{platformAcceptanceManifestImportQueue.needs_manual_review}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestImportQueue.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestImportQueue.artifact_url}><Save size={16} />Open queue</button>
                        </div>
                        {platformAcceptanceManifestImportQueue.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceManifestImportQueue.items.slice(0, 5).map((item) => (
                              <article key={`${platformAcceptanceManifestImportQueue.id}-${item.submission_id}`}>
                                <strong>{item.submission_id} 路 {setupStatusLabel(item.status)}</strong>
                                <span>items {item.import_items.length} 路 ready {item.ready} 路 blocked {item.blocked}</span>
                                <small>{item.next_action}</small>
                                <span>source {item.source}{item.recovered ? ' recovered' : ''}</span>
                                {item.recovery_review_status && <span>review {setupStatusLabel(item.recovery_review_status)}</span>}
                                <button onClick={() => runManifestQueueEvidenceImport(item, false)} disabled={!item.import_items.length}><Clipboard size={16} />Preview import</button>
                                <button onClick={() => reviewManifestRecovery(item, 'accepted_for_preview', false)} disabled={item.status !== 'recovered_for_review'}><Clipboard size={16} />Review preview</button>
                                <button onClick={() => reviewManifestRecovery(item, 'accepted_for_preview', true)} disabled={item.status !== 'recovered_for_review'}><ShieldAlert size={16} />Mark reviewed</button>
                                <button onClick={() => reviewManifestRecovery(item, 'needs_customer_resubmission', true)} disabled={item.status !== 'recovered_for_review'}><Send size={16} />Request resubmission</button>
                                <button onClick={() => runManifestQueueEvidenceImport(item, true)} disabled={!item.import_items.length || item.status !== 'ready_to_import'}><ShieldAlert size={16} />Import evidence</button>
                                <button onClick={() => window.open(artifactUrl(item.submission_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.submission_artifact_url}><Save size={16} />Submission</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceManifestRecoveryReview && (
                      <div className="setupGuideCounts">
                        <span>Recovery review <b>{setupStatusLabel(platformAcceptanceManifestRecoveryReview.status)}</b></span>
                        <span>Submission <b>{platformAcceptanceManifestRecoveryReview.submission_id}</b></span>
                        <span>Items <b>{platformAcceptanceManifestRecoveryReview.import_items.length}</b></span>
                        <span>Resubmit <b>{platformAcceptanceManifestRecoveryReview.resubmission_scenarios.length}</b></span>
                        <button onClick={() => window.open(platformAcceptanceManifestRecoveryReview.manifest_link?.manifest_url || '', '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestRecoveryReview.manifest_link?.manifest_url}><Send size={16} />Open manifest</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestRecoveryReview.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestRecoveryReview.artifact_url}><Save size={16} />Open review</button>
                      </div>
                    )}
                    {platformAcceptanceManifestRecoveryResubmissionRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Recovery resubmission <b>{setupStatusLabel(platformAcceptanceManifestRecoveryResubmissionRun.status)}</b></span>
                          <span>Total <b>{platformAcceptanceManifestRecoveryResubmissionRun.total}</b></span>
                          <span>Requested <b>{platformAcceptanceManifestRecoveryResubmissionRun.requested}</b></span>
                          <span>Already <b>{platformAcceptanceManifestRecoveryResubmissionRun.already_requested}</b></span>
                          <span>Blocked <b>{platformAcceptanceManifestRecoveryResubmissionRun.blocked}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestRecoveryResubmissionRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestRecoveryResubmissionRun.artifact_url}><Save size={16} />Open run</button>
                        </div>
                        {platformAcceptanceManifestRecoveryResubmissionRun.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceManifestRecoveryResubmissionRun.items.slice(0, 5).map((item) => (
                              <article key={`${platformAcceptanceManifestRecoveryResubmissionRun.id}-${item.submission_id}`}>
                                <strong>{item.submission_id} 路 {setupStatusLabel(item.status)}</strong>
                                <span>items {item.import_items} 路 scenarios {item.scenarios.length || '-'}</span>
                                <small>{item.next_action}</small>
                                <button onClick={() => window.open(item.manifest_url, '_blank', 'noopener,noreferrer')} disabled={!item.manifest_url}><Send size={16} />Open manifest</button>
                                <button onClick={() => copyText(item.manifest_url, 'Recovery resubmission manifest link copied.')} disabled={!item.manifest_url}><Clipboard size={16} />Copy manifest</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceManifestResubmissionTracker && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Resubmit tracker <b>{setupStatusLabel(platformAcceptanceManifestResubmissionTracker.status)}</b></span>
                          <span>Total <b>{platformAcceptanceManifestResubmissionTracker.total}</b></span>
                          <span>Waiting <b>{platformAcceptanceManifestResubmissionTracker.waiting_customer}</b></span>
                          <span>Ready <b>{platformAcceptanceManifestResubmissionTracker.ready_for_review}</b></span>
                          <span>Stale <b>{platformAcceptanceManifestResubmissionTracker.stale}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestResubmissionTracker.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestResubmissionTracker.artifact_url}><Save size={16} />Open tracker</button>
                          <button onClick={() => copyText(platformAcceptanceManifestResubmissionTracker.reminder_draft, 'Manifest resubmission reminder draft copied.')} disabled={!platformAcceptanceManifestResubmissionTracker.reminder_draft}><Clipboard size={16} />Copy reminder</button>
                        </div>
                        {platformAcceptanceManifestResubmissionTracker.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceManifestResubmissionTracker.items.slice(0, 5).map((item) => (
                              <article key={`${platformAcceptanceManifestResubmissionTracker.id}-${item.submission_id}-${item.manifest_link_id}`}>
                                <strong>{item.submission_id || item.manifest_link_id} 路 {setupStatusLabel(item.status)}</strong>
                                <span>wait {item.wait_hours}h 路 escalation {item.escalation} 路 missing {item.missing_scenarios.length}</span>
                                <small>{item.next_action}</small>
                                <button onClick={() => window.open(artifactUrl(item.latest_submission_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.latest_submission_artifact_url}><Save size={16} />Submission</button>
                                <button onClick={() => window.open(artifactUrl(item.import_preview_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.import_preview_artifact_url}><Clipboard size={16} />Import preview</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceManifestResubmissionReminderRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Reminder tasks <b>{setupStatusLabel(platformAcceptanceManifestResubmissionReminderRun.status)}</b></span>
                          <span>Total <b>{platformAcceptanceManifestResubmissionReminderRun.total}</b></span>
                          <span>Created <b>{platformAcceptanceManifestResubmissionReminderRun.created}</b></span>
                          <span>Existing <b>{platformAcceptanceManifestResubmissionReminderRun.existing}</b></span>
                          <span>Blocked <b>{platformAcceptanceManifestResubmissionReminderRun.blocked}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestResubmissionReminderRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestResubmissionReminderRun.artifact_url}><Save size={16} />Open reminder</button>
                          <button onClick={() => copyText(platformAcceptanceManifestResubmissionReminderRun.reminder_draft, 'Manifest resubmission reminder task draft copied.')} disabled={!platformAcceptanceManifestResubmissionReminderRun.reminder_draft}><Clipboard size={16} />Copy draft</button>
                        </div>
                        {platformAcceptanceManifestResubmissionReminderRun.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceManifestResubmissionReminderRun.items.slice(0, 5).map((item, index) => (
                              <article key={`${platformAcceptanceManifestResubmissionReminderRun.id}-${item.submission_id}-${index}`}>
                                <strong>{item.submission_id || item.title} · {setupStatusLabel(item.action_status)}</strong>
                                <span>{setupStatusLabel(item.tracker_status)} · priority {item.priority} · due {item.due_at || '-'}</span>
                                <small>{item.next_action}</small>
                                <button onClick={() => item.task && setSection('crm')} disabled={!item.task}><Target size={16} />Open tasks</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceManifestFollowupRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Manifest follow-up <b>{setupStatusLabel(platformAcceptanceManifestFollowupRun.status)}</b></span>
                          <span>Missing <b>{platformAcceptanceManifestFollowupRun.missing_scenarios.length}</b></span>
                          <span>Inbox <b>{platformAcceptanceManifestFollowupRun.inbox_total}</b></span>
                          <span>Ready <b>{platformAcceptanceManifestFollowupRun.inbox_ready}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceManifestFollowupRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestFollowupRun.artifact_url}><Save size={16} />Open follow-up</button>
                          <button onClick={() => window.open(platformAcceptanceManifestFollowupRun.manifest_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceManifestFollowupRun.manifest_url}><Send size={16} />Open manifest</button>
                          <button onClick={() => copyText(platformAcceptanceManifestFollowupRun.reminder_draft, 'Manifest follow-up draft copied.')} disabled={!platformAcceptanceManifestFollowupRun.reminder_draft}><Clipboard size={16} />Copy draft</button>
                        </div>
                        {platformAcceptanceManifestFollowupRun.items.length > 0 && (
                          <div className="slaMiniList">
                            {platformAcceptanceManifestFollowupRun.items.map((item) => (
                              <article key={`${platformAcceptanceManifestFollowupRun.id}-${item.scenario}`}>
                                <strong>{item.scenario} 路 {setupStatusLabel(item.status)}</strong>
                                <span>{item.latest_submission_id || 'no submission'} 路 {item.latest_submission_status || '-'}</span>
                                <small>{item.next_action}</small>
                                <button onClick={() => window.open(artifactUrl(item.import_preview_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.import_preview_artifact_url}><Clipboard size={16} />Import preview</button>
                                <button onClick={() => window.open(artifactUrl(item.submission_artifact_url), '_blank', 'noopener,noreferrer')} disabled={!item.submission_artifact_url}><Save size={16} />Submission</button>
                              </article>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    {platformAcceptanceSprintPack && (
                      <>
                        <div className="setupGuideCounts">
                          <span>验收冲刺 <b>{setupStatusLabel(platformAcceptanceSprintPack.status)}</b></span>
                          <span>缺失场景 <b>{platformAcceptanceSprintPack.missing_scenarios.length}</b></span>
                          <span>行动项 <b>{platformAcceptanceSprintPack.items.length}</b></span>
                          <span>客户链接 <b>{platformAcceptanceSprintPack.links.length}</b></span>
                          <span>CRM 任务 <b>{platformAcceptanceSprintPack.tasks.length}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceSprintPack.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceSprintPack.artifact_url}><Save size={16} />打开冲刺包</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceSprintPack.items.slice(0, 5).map((item) => (
                            <article key={`${platformAcceptanceSprintPack.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.owner || '未分配'} · {item.due_at || '未排期'} · task {item.task_id || '-'}</span>
                              <small>{item.next_action}</small>
                              {item.submission_link?.submit_url && (
                                <button onClick={() => window.open(item.submission_link?.submit_url || '', '_blank', 'noopener,noreferrer')}><Send size={16} />打开提交页</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceLiveRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>验收作战 <b>{setupStatusLabel(platformAcceptanceLiveRun.status)}</b></span>
                          <span>通过 <b>{platformAcceptanceLiveRun.passed}/{platformAcceptanceLiveRun.required_total}</b></span>
                          <span>待复核 <b>{platformAcceptanceLiveRun.needs_review}</b></span>
                          <span>需协助 <b>{platformAcceptanceLiveRun.needs_help}</b></span>
                          <span>缺口 <b>{platformAcceptanceLiveRun.missing}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceLiveRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceLiveRun.artifact_url}><Save size={16} />打开作战台</button>
                          <button onClick={() => copyText(platformAcceptanceLiveRun.signoff_draft, '客户最终签署草稿已复制；仅在 ready_for_signoff 时发送。')} disabled={!platformAcceptanceLiveRun.signoff_draft}><Clipboard size={16} />复制签署草稿</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceLiveRun.scenarios.slice(0, 6).map((item) => (
                            <article key={`${platformAcceptanceLiveRun.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>evidence {item.evidence_count} · submissions {item.customer_submission_count} · review {item.review_task_count} · gap {item.gap_task_id || '-'}</span>
                              <small>{item.next_action}</small>
                              {item.submission_link?.submit_url && (
                                <button onClick={() => window.open(item.submission_link?.submit_url || '', '_blank', 'noopener,noreferrer')}><Send size={16} />打开提交页</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceJointDebugRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>联调执行 <b>{setupStatusLabel(platformAcceptanceJointDebugRun.status)}</b></span>
                          <span>通过 <b>{platformAcceptanceJointDebugRun.passed}</b></span>
                          <span>缺口 <b>{platformAcceptanceJointDebugRun.missing}</b></span>
                          <span>Connector <b>{platformAcceptanceJointDebugRun.connectors.length}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceJointDebugRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceJointDebugRun.artifact_url}><Save size={16} />打开联调报告</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceJointDebugRun.scenarios.map((item) => (
                            <article key={`${platformAcceptanceJointDebugRun.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.connector || '-'} · {item.pull_result ? `${item.pull_result.status} / imported ${item.pull_result.imported}` : 'no pull'}</span>
                              <small>{item.next_action || item.evidence_summary}</small>
                              {item.registered_evidence?.artifact_url && (
                                <button onClick={() => window.open(artifactUrl(item.registered_evidence?.artifact_url || ''), '_blank', 'noopener,noreferrer')}><Save size={16} />打开证据</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceGapClosureRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>缺口闭环 <b>{setupStatusLabel(platformAcceptanceGapClosureRun.status)}</b></span>
                          <span>闭环前 <b>{platformAcceptanceGapClosureRun.missing_before.length}</b></span>
                          <span>闭环后 <b>{platformAcceptanceGapClosureRun.missing_after.length}</b></span>
                          <span>行动项 <b>{platformAcceptanceGapClosureRun.items.length}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceGapClosureRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceGapClosureRun.artifact_url}><Save size={16} />打开闭环报告</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceGapClosureRun.items.map((item) => (
                            <article key={`${platformAcceptanceGapClosureRun.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.connector || '-'} · missing {item.missing_fields.join(' / ') || '-'}</span>
                              <small>{item.next_action || item.evidence_summary}</small>
                              {item.submission_link?.submit_url && (
                                <button onClick={() => window.open(item.submission_link?.submit_url || '', '_blank', 'noopener,noreferrer')}><Send size={16} />打开客户链接</button>
                              )}
                              {item.registered_evidence?.artifact_url && (
                                <button onClick={() => window.open(artifactUrl(item.registered_evidence?.artifact_url || ''), '_blank', 'noopener,noreferrer')}><Save size={16} />打开证据</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceOwnerActionPack && (
                      <>
                        <div className="setupGuideCounts">
                          <span>负责人交接 <b>{setupStatusLabel(platformAcceptanceOwnerActionPack.status)}</b></span>
                          <span>缺口 <b>{platformAcceptanceOwnerActionPack.missing_scenarios.length}</b></span>
                          <span>行动项 <b>{platformAcceptanceOwnerActionPack.items.length}</b></span>
                          <span>接收人 <b>{platformAcceptanceOwnerActionPack.recipient}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceOwnerActionPack.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceOwnerActionPack.artifact_url}><Save size={16} />打开交接包</button>
                          <button onClick={() => copyText(platformAcceptanceOwnerActionPack.draft_text, '客户平台负责人行动消息已复制。')} disabled={!platformAcceptanceOwnerActionPack.draft_text}><Clipboard size={16} />复制消息</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceOwnerActionPack.items.map((item) => (
                            <article key={`${platformAcceptanceOwnerActionPack.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.connector || '-'} · required {item.required_fields.join(' / ') || '-'}</span>
                              <small>{item.action_text}</small>
                              {item.callback_url && <code>{item.callback_url}</code>}
                              {item.submission_link?.submit_url && (
                                <button onClick={() => window.open(item.submission_link?.submit_url || '', '_blank', 'noopener,noreferrer')}><Send size={16} />打开客户链接</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceOwnerClosureLink && (
                      <div className="setupGuideCounts">
                        <span>闭环链接 <b>{setupStatusLabel(platformAcceptanceOwnerClosureLink.status)}</b></span>
                        <span>Connector <b>{platformAcceptanceOwnerClosureLink.connectors.length || 'default'}</b></span>
                        <span>接收人 <b>{platformAcceptanceOwnerClosureLink.recipient}</b></span>
                        <span>到期 <b>{platformAcceptanceOwnerClosureLink.expires_at || '-'}</b></span>
                        <button onClick={() => window.open(platformAcceptanceOwnerClosureLink.submit_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceOwnerClosureLink.submit_url}><Send size={16} />打开闭环页</button>
                        <button onClick={() => copyText(platformAcceptanceOwnerClosureLink.submit_url, '安全闭环链接已复制。')} disabled={!platformAcceptanceOwnerClosureLink.submit_url}><Clipboard size={16} />复制链接</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceOwnerClosureLink.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceOwnerClosureLink.artifact_url}><Save size={16} />打开链接报告</button>
                      </div>
                    )}
                    {platformAcceptanceOwnerClosureRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>负责人闭环 <b>{setupStatusLabel(platformAcceptanceOwnerClosureRun.status)}</b></span>
                          <span>闭环前 <b>{platformAcceptanceOwnerClosureRun.missing_before.length}</b></span>
                          <span>闭环后 <b>{platformAcceptanceOwnerClosureRun.missing_after.length}</b></span>
                          <span>Connector <b>{platformAcceptanceOwnerClosureRun.connector_results.length}</b></span>
                          <span>回执 <b>{platformAcceptanceOwnerClosureRun.receipt ? 1 : 0}</b></span>
                          <span>复核 <b>{platformAcceptanceOwnerClosureRun.review_sync?.created || 0}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceOwnerClosureRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceOwnerClosureRun.artifact_url}><Save size={16} />打开闭环报告</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceOwnerClosureRun.connector_results.map((item) => (
                            <article key={`${platformAcceptanceOwnerClosureRun.id}-${item.connector}`}>
                              <strong>{item.connector} 路 {setupStatusLabel(item.status)}</strong>
                              <span>applied {item.applied_fields.join(' / ') || '-'} 路 secret fields {item.secret_field_names.join(' / ') || '-'}</span>
                              <small>{item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceFinalClosureRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>Final closure <b>{setupStatusLabel(platformAcceptanceFinalClosureRun.status)}</b></span>
                          <span>Before <b>{platformAcceptanceFinalClosureRun.missing_before.length}</b></span>
                          <span>After <b>{platformAcceptanceFinalClosureRun.missing_after.length}</b></span>
                          <span>Tasks <b>{platformAcceptanceFinalClosureRun.created_tasks}/{platformAcceptanceFinalClosureRun.existing_tasks}</b></span>
                          <span>Links <b>{platformAcceptanceFinalClosureRun.secure_links}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceFinalClosureRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceFinalClosureRun.artifact_url}><Save size={16} />Open closure</button>
                        </div>
                        <div className="slaMiniList">
                          <article>
                            <strong>Evidence {setupStatusLabel(platformAcceptanceFinalClosureRun.report_after?.status || 'blocked')}</strong>
                            <span>Missing {platformAcceptanceFinalClosureRun.missing_after.join(' / ') || 'none'}</span>
                            <small>{platformAcceptanceFinalClosureRun.summary}</small>
                          </article>
                          {platformAcceptanceFinalClosureRun.auto_watch && (
                            <article>
                              <strong>Auto watch · {setupStatusLabel(platformAcceptanceFinalClosureRun.auto_watch.status)}</strong>
                              <span>Actions {platformAcceptanceFinalClosureRun.auto_watch.actions.length}</span>
                              <button onClick={() => window.open(artifactUrl(platformAcceptanceFinalClosureRun.auto_watch?.artifact_url || ''), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceFinalClosureRun.auto_watch.artifact_url}><Save size={16} />Open auto watch</button>
                            </article>
                          )}
                          {platformAcceptanceFinalClosureRun.customer_room && (
                            <article>
                              <strong>Customer room · {setupStatusLabel(platformAcceptanceFinalClosureRun.customer_room.status)}</strong>
                              <span>Missing {platformAcceptanceFinalClosureRun.customer_room.missing_scenarios.length}</span>
                              <button onClick={() => copyText(platformAcceptanceFinalClosureRun.customer_room?.room_url || '', 'Final closure customer room copied; review before sending.')} disabled={!platformAcceptanceFinalClosureRun.customer_room.room_url}><Clipboard size={16} />Copy room</button>
                            </article>
                          )}
                        </div>
                      </>
                    )}
                    {platformAcceptanceAutoWatchRun && (
                      <>
                        <div className="setupGuideCounts">
                          <span>自动守护 <b>{setupStatusLabel(platformAcceptanceAutoWatchRun.status)}</b></span>
                          <span>守护前 <b>{platformAcceptanceAutoWatchRun.missing_before.length}</b></span>
                          <span>守护后 <b>{platformAcceptanceAutoWatchRun.missing_after.length}</b></span>
                          <span>动作 <b>{platformAcceptanceAutoWatchRun.actions.length}</b></span>
                          <span>下次巡检 <b>{platformAcceptanceAutoWatchRun.next_probe_at || '-'}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceAutoWatchRun.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceAutoWatchRun.artifact_url}><Save size={16} />打开守护报告</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceAutoWatchRun.actions.map((item) => (
                            <article key={`${platformAcceptanceAutoWatchRun.id}-${item.step}`}>
                              <strong>{item.step} 路 {setupStatusLabel(item.status)}</strong>
                              <span>{item.summary}</span>
                              <small>{item.next_action}</small>
                              {item.artifact_url && (
                                <button onClick={() => window.open(artifactUrl(item.artifact_url), '_blank', 'noopener,noreferrer')}><Save size={16} />打开产物</button>
                              )}
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceWatchBoard && (
                      <>
                        <div className="setupGuideCounts">
                          <span>守护看板 <b>{setupStatusLabel(platformAcceptanceWatchBoard.status)}</b></span>
                          <span>证据 <b>{setupStatusLabel(platformAcceptanceWatchBoard.evidence_status)}</b></span>
                          <span>缺口 <b>{platformAcceptanceWatchBoard.missing_scenarios.length}</b></span>
                          <span>打开任务 <b>{platformAcceptanceWatchBoard.open_gap_tasks}</b></span>
                          <span>接收人 <b>{platformAcceptanceWatchBoard.recipient}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceWatchBoard.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceWatchBoard.artifact_url}><Save size={16} />打开看板</button>
                          <button onClick={() => copyText(platformAcceptanceWatchBoard.reminder_draft, '守护提醒草稿已复制。')} disabled={!platformAcceptanceWatchBoard.reminder_draft}><Clipboard size={16} />复制提醒</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceWatchBoard.scenarios.map((item) => (
                            <article key={`${platformAcceptanceWatchBoard.id}-${item.scenario}`}>
                              <strong>{item.scenario} 路 {setupStatusLabel(item.status)}</strong>
                              <span>wait {item.wait_hours}h 路 escalation {item.escalation} 路 task {item.task_id || '-'}</span>
                              <small>{item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceCustomerRoom && (
                      <div className="setupGuideCounts">
                        <span>验收房间 <b>{setupStatusLabel(platformAcceptanceCustomerRoom.status)}</b></span>
                        <span>证据 <b>{setupStatusLabel(platformAcceptanceCustomerRoom.evidence_status)}</b></span>
                        <span>缺口 <b>{platformAcceptanceCustomerRoom.missing_scenarios.length}</b></span>
                        <span>接收人 <b>{platformAcceptanceCustomerRoom.recipient}</b></span>
                        <span>到期 <b>{platformAcceptanceCustomerRoom.expires_at || '-'}</b></span>
                        <button onClick={() => window.open(platformAcceptanceCustomerRoom.room_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceCustomerRoom.room_url}><Send size={16} />打开房间</button>
                        <button onClick={() => copyText(platformAcceptanceCustomerRoom.room_url, '客户验收房间链接已复制。')} disabled={!platformAcceptanceCustomerRoom.room_url}><Clipboard size={16} />复制房间</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceCustomerRoom.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceCustomerRoom.artifact_url}><Save size={16} />打开房间报告</button>
                      </div>
                    )}
                    {platformAcceptanceFinalSignoffLink && (
                      <div className="setupGuideCounts">
                        <span>签署门禁 <b>{setupStatusLabel(platformAcceptanceFinalSignoffLink.status)}</b></span>
                        <span>缺口场景 <b>{platformAcceptanceFinalSignoffLink.missing_scenarios.length}</b></span>
                        <span>签署人 <b>{platformAcceptanceFinalSignoffLink.signer_name}</b></span>
                        <span>到期 <b>{platformAcceptanceFinalSignoffLink.expires_at || '-'}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceFinalSignoffLink.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceFinalSignoffLink.artifact_url}><Save size={16} />打开门禁报告</button>
                        <button onClick={() => window.open(platformAcceptanceFinalSignoffLink.submit_url, '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceFinalSignoffLink.submit_url}><Send size={16} />打开签署页</button>
                        <button onClick={() => copyText(platformAcceptanceFinalSignoffLink.submit_url, '最终签署链接已复制；发送前请人工确认。')} disabled={!platformAcceptanceFinalSignoffLink.submit_url}><Clipboard size={16} />复制签署链接</button>
                      </div>
                    )}
                    {platformAcceptanceCustomerSubmission && (
                      <div className="setupGuideCounts">
                        <span>客户提交 <b>{setupStatusLabel(platformAcceptanceCustomerSubmission.status)}</b></span>
                        <span>提交场景 <b>{platformAcceptanceCustomerSubmission.scenarios.length}</b></span>
                        <span>复核新增 <b>{platformAcceptanceCustomerSubmission.review_sync.created}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceCustomerSubmission.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceCustomerSubmission.artifact_url}><Save size={16} />打开提交记录</button>
                      </div>
                    )}
                    {platformAcceptanceReceipt && (
                      <div className="setupGuideCounts">
                        <span>回执状态 <b>{setupStatusLabel(platformAcceptanceReceipt.status)}</b></span>
                        <span>回执场景 <b>{platformAcceptanceReceipt.scenario_receipts.length}</b></span>
                        <span>结果 <b>{setupStatusLabel(platformAcceptanceReceipt.outcome)}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceReceipt.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReceipt.artifact_url}><Save size={16} />打开回执</button>
                      </div>
                    )}
                    {platformAcceptanceReviewSync && (
                      <div className="setupGuideCounts">
                        <span>复核状态 <b>{setupStatusLabel(platformAcceptanceReviewSync.status)}</b></span>
                        <span>已提交 <b>{platformAcceptanceReviewSync.submitted}</b></span>
                        <span>需协助 <b>{platformAcceptanceReviewSync.needs_help}</b></span>
                        <span>新增任务 <b>{platformAcceptanceReviewSync.created}</b></span>
                        <span>已存在 <b>{platformAcceptanceReviewSync.skipped_existing}</b></span>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceReviewSync.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReviewSync.artifact_url}><Save size={16} />打开复核</button>
                      </div>
                    )}
                    {platformAcceptanceReviewDesk && (
                      <>
                        <div className="setupGuideCounts">
                          <span>处理台 <b>{setupStatusLabel(platformAcceptanceReviewDesk.status)}</b></span>
                          <span>已通过 <b>{platformAcceptanceReviewDesk.passed}/{platformAcceptanceReviewDesk.required_total}</b></span>
                          <span>待审核 <b>{platformAcceptanceReviewDesk.ready_to_review}</b></span>
                          <span>需协助 <b>{platformAcceptanceReviewDesk.needs_customer_help}</b></span>
                          <span>待补证 <b>{platformAcceptanceReviewDesk.needs_evidence}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceReviewDesk.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReviewDesk.artifact_url}><Save size={16} />打开处理台</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceReviewDesk.scenarios.map((item) => (
                            <article key={`${platformAcceptanceReviewDesk.id}-${item.scenario}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>task {item.task_id || '-'} · decision {item.recommended_decision} · pass {item.can_register_pass ? 'ready' : 'blocked'}</span>
                              <small>{item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceReviewExecution && (
                      <>
                        <div className="setupGuideCounts">
                          <span>执行台 <b>{setupStatusLabel(platformAcceptanceReviewExecution.status)}</b></span>
                          <span>请求 <b>{platformAcceptanceReviewExecution.requested}</b></span>
                          <span>执行 <b>{platformAcceptanceReviewExecution.executed}</b></span>
                          <span>阻塞 <b>{platformAcceptanceReviewExecution.blocked}</b></span>
                          <span>登记证据 <b>{platformAcceptanceReviewExecution.evidence_registered}</b></span>
                          <span>关闭缺口 <b>{platformAcceptanceReviewExecution.gap_closed}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceReviewExecution.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReviewExecution.artifact_url}><Save size={16} />打开执行台</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceReviewExecution.items.map((item, index) => (
                            <article key={`${platformAcceptanceReviewExecution.id}-${item.scenario}-${index}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>{item.decision} · evidence {item.evidence_registered ? 'registered' : 'no'} · gap closed {item.gap_closed}</span>
                              <small>{item.error || item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceEvidenceUrlPrecheck && (
                      <>
                        <div className="setupGuideCounts">
                          <span>URL precheck <b>{setupStatusLabel(platformAcceptanceEvidenceUrlPrecheck.status)}</b></span>
                          <span>Checked <b>{platformAcceptanceEvidenceUrlPrecheck.checked}</b></span>
                          <span>OK <b>{platformAcceptanceEvidenceUrlPrecheck.ok}</b></span>
                          <span>Warning <b>{platformAcceptanceEvidenceUrlPrecheck.warning}</b></span>
                          <span>Blocked <b>{platformAcceptanceEvidenceUrlPrecheck.blocked}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceEvidenceUrlPrecheck.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidenceUrlPrecheck.artifact_url}><Save size={16} />Open URL report</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceEvidenceUrlPrecheck.items.map((item, index) => (
                            <article key={`${platformAcceptanceEvidenceUrlPrecheck.id}-${item.scenario}-${index}`}>
                              <strong>{item.scenario} 路 {setupStatusLabel(item.status)}</strong>
                              <span>HTTP {item.http_status || '-'} 路 {item.host || '-'}</span>
                              <small>{item.reason || item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceEvidenceImport && (
                      <>
                        <div className="setupGuideCounts">
                          <span>证据导入 <b>{setupStatusLabel(platformAcceptanceEvidenceImport.status)}</b></span>
                          <span>供应 <b>{platformAcceptanceEvidenceImport.supplied}/{platformAcceptanceEvidenceImport.required_total}</b></span>
                          <span>就绪 <b>{platformAcceptanceEvidenceImport.ready}</b></span>
                          <span>导入 <b>{platformAcceptanceEvidenceImport.imported}</b></span>
                          <span>阻塞 <b>{platformAcceptanceEvidenceImport.blocked}</b></span>
                          <span>登记证据 <b>{platformAcceptanceEvidenceImport.evidence_registered}</b></span>
                          <button onClick={() => window.open(artifactUrl(platformAcceptanceEvidenceImport.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceEvidenceImport.artifact_url}><Save size={16} />打开导入报告</button>
                        </div>
                        <div className="slaMiniList">
                          {platformAcceptanceEvidenceImport.items.map((item, index) => (
                            <article key={`${platformAcceptanceEvidenceImport.id}-${item.scenario}-${index}`}>
                              <strong>{item.scenario} · {setupStatusLabel(item.status)}</strong>
                              <span>evidence {item.evidence_id || '-'} · gap closed {item.gap_closed} · URL {item.url_precheck?.status || '-'}</span>
                              <small>{item.error || item.next_action}</small>
                            </article>
                          ))}
                        </div>
                      </>
                    )}
                    {platformAcceptanceReviewDecision && (
                      <div className="setupGuideCounts">
                        <span>审核状态 <b>{setupStatusLabel(platformAcceptanceReviewDecision.status)}</b></span>
                        <span>场景 <b>{platformAcceptanceReviewDecision.scenario}</b></span>
                        <span>决策 <b>{setupStatusLabel(platformAcceptanceReviewDecision.decision)}</b></span>
                        <span>关闭复核 <b>{platformAcceptanceReviewDecision.closed_review_tasks.length}</b></span>
                        <span>登记证据 <b>{platformAcceptanceReviewDecision.evidence ? 1 : 0}</b></span>
                        <span>关闭缺口 <b>{platformAcceptanceReviewDecision.gap_reconcile?.closed || 0}</b></span>
                        <span>补交链接 <b>{platformAcceptanceReviewDecision.resubmission_link ? 1 : 0}</b></span>
                        <button onClick={() => window.open(platformAcceptanceReviewDecision.resubmission_link?.submit_url || '', '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReviewDecision.resubmission_link?.submit_url}><Send size={16} />打开补交页</button>
                        <button onClick={() => window.open(artifactUrl(platformAcceptanceReviewDecision.artifact_url), '_blank', 'noopener,noreferrer')} disabled={!platformAcceptanceReviewDecision.artifact_url}><Save size={16} />打开决策</button>
                      </div>
                    )}
                    {integrationSLA.items.length > 0 && (
                      <div className="slaMiniList">
                        {integrationSLA.items.slice(0, 5).map((item) => (
                          <article key={item.task_id}>
                            <strong>{item.connector || 'unknown'} · {item.check}</strong>
                            <span>{item.owner || '未分配'} · {item.sla_status} · {item.due_at || '未排期'}</span>
                          </article>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="localScriptGrid">
                {connectorSetupGuide.tasks.map((task) => (
                  <article className="scriptLaunchCard setupTaskCard" key={task.id}>
                    <div className="panelHeader">
                      <strong>{task.label}</strong>
                      <em className={`pill ${setupPillClass(task.status)}`}>{setupStatusLabel(task.status)}</em>
                    </div>
                    <span>{task.title}</span>
                    <small>{task.category} · {setupStatusLabel(task.severity)}</small>
                    {task.evidence && <p>{task.evidence}</p>}
                    <small>{task.next_action}</small>
                    {task.required_fields.length > 0 && <small>需要：{task.required_fields.join(' / ')}</small>}
                    {task.configured_fields.length > 0 && <small>已配置：{task.configured_fields.join(' / ')}</small>}
                    {task.endpoint_hint && <code>{task.endpoint_hint}</code>}
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
        <section className="panel">
          <div className="panelHeader"><strong>平台授权和只读入站</strong><small>{connectorAuths.length} 个</small></div>
          {connectorAuths.length === 0 && <EmptyState text="暂无平台授权状态。请确认 /api/v1/connectors/auth 可访问。" />}
          <div className="localScriptGrid">
            {connectorAuths.map((connector) => (
              <article className="scriptLaunchCard" key={connector.key}>
                <strong>{connector.label}</strong>
                <span>{connector.auth_mode} · {connector.safety_level === 'read_only' ? '只读入站' : connector.safety_level === 'draft_only' ? '草稿辅助' : '需人工确认'}</span>
                <small>{connector.capabilities.join(' / ') || '暂无能力'} </small>
                <small>{connector.missing_fields.length ? `缺少：${connector.missing_fields.join('、')}` : '授权字段已满足或无需授权'}</small>
                {(connector.auth_mode === 'oauth' || connector.missing_fields.some((field) => field.includes('secret'))) && (
                  <>
                    <label>OAuth 授权地址
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).authorize_url}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), authorize_url: event.target.value}}))}
                        placeholder="官方 authorize_url"
                      />
                    </label>
                    <label>OAuth Client ID
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).client_id}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), client_id: event.target.value}}))}
                        placeholder="client_id / app_key"
                      />
                    </label>
                    <label>OAuth Client Secret
                      <input
                        type="password"
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).client_secret}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), client_secret: event.target.value}}))}
                        placeholder={connector.configured_fields.includes('client_secret') || connector.configured_fields.includes('app_secret') ? '已配置，留空不修改' : 'client_secret / app_secret'}
                      />
                    </label>
                    <label>Token Endpoint
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).token_url}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), token_url: event.target.value}}))}
                        placeholder="官方 token_url / oauth_token_url"
                      />
                    </label>
                    <label>消息只读 API
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).messages_url}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), messages_url: event.target.value}}))}
                        placeholder="官方 messages_url / read_messages_url"
                      />
                    </label>
                    <label>线索只读 API
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).leads_url}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), leads_url: event.target.value}}))}
                        placeholder="官方 leads_url / read_leads_url"
                      />
                    </label>
                    <label>发送 API
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).send_url}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), send_url: event.target.value}}))}
                        placeholder="官方 send_url / reply_send_url"
                      />
                    </label>
                    <label>授权范围
                      <input
                        value={connectorOAuthDraftOrDefault(connectorOAuthDrafts[connector.key]).scope}
                        onChange={(event) => setConnectorOAuthDrafts((current) => ({...current, [connector.key]: {...connectorOAuthDraftOrDefault(current[connector.key]), scope: event.target.value}}))}
                        placeholder="scope，可选"
                      />
                    </label>
                    <button className="primaryButton fit" onClick={() => startConnectorOAuth(connector)} disabled={loading}><PlugZap size={16} />生成 OAuth 链接</button>
                    <button className="primaryButton fit" onClick={() => exchangeConnectorOAuth(connector)} disabled={loading}><RefreshCw size={16} />换取 Token</button>
                    <button className="primaryButton fit" onClick={() => refreshConnectorOAuth(connector)} disabled={loading}><RefreshCw size={16} />刷新 Token</button>
                    <button className="primaryButton fit" onClick={() => pullConnectorReadApi(connector, 'messages')} disabled={loading}><Inbox size={16} />拉取消息</button>
                    <button className="primaryButton fit" onClick={() => pullConnectorReadApi(connector, 'leads')} disabled={loading}><Target size={16} />拉取线索</button>
                    <button className="primaryButton fit" onClick={() => enableConnectorSendGate(connector)} disabled={loading}><Send size={16} />启用受控发送</button>
                  </>
                )}
                <code>{`${window.location.origin}${apiUrl(`/api/v1/webhooks/${connector.key}/messages?merchant_code=${profile.merchant_code || 'MERCHANT_CODE'}`)}`}</code>
                <label>Webhook 签名密钥
                  <input
                    type="password"
                    value={connectorSecretDrafts[connector.key] || ''}
                    onChange={(event) => setConnectorSecretDrafts((current) => ({...current, [connector.key]: event.target.value}))}
                    placeholder={connector.configured_fields.includes('webhook_token') || connector.configured_fields.includes('webhook_secret') ? '已配置，留空不修改' : '未配置'}
                  />
                </label>
                <button className="primaryButton fit" onClick={() => saveConnectorWebhookSecret(connector)} disabled={loading || !(connectorSecretDrafts[connector.key] || '').trim()}><ShieldAlert size={16} />保存签名密钥</button>
                <em className={`pill ${connector.status}`}>{statusNames[connector.status] || connector.status}</em>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panelHeader">
            <strong>Connector 运维健康</strong>
            {connectorHealth && <em className={`pill ${auditPillClass(connectorHealth.status)}`}>{auditStatusLabel(connectorHealth.status)}</em>}
          </div>
          {!connectorHealth && <EmptyState text="暂无 Connector 健康巡检结果。" />}
          {connectorHealth && (
            <>
              <article className="knowledgeItem">
                <strong>{connectorHealth.summary}</strong>
                <small>{connectorHealth.created_at}</small>
                {connectorHealth.alerts.slice(0, 4).map((alert) => <p key={alert}>{alert}</p>)}
              </article>
              <div className="localScriptGrid">
                {connectorHealth.items.map((item) => (
                  <article className="scriptLaunchCard" key={item.connector}>
                    <div className="panelHeader">
                      <strong>{item.label}</strong>
                      <em className={`pill ${auditPillClass(item.status)}`}>{auditStatusLabel(item.status)}</em>
                    </div>
                    <span>{item.auth_mode} · {item.auth_status} · {item.send_enabled ? '受控发送已开启' : '发送闸门关闭'}</span>
                    <small>待外发 {item.pending_dispatches} · 发送失败 {item.failed_dispatches} · 近期失败 {item.recent_failures}</small>
                    {item.token_expires_at && <small>Token 到期：{item.token_expires_at}</small>}
                    {item.last_sync_at && <small>最近同步：{item.last_sync_at}</small>}
                    {item.alerts.slice(0, 3).map((alert) => <small key={alert}>{alert}</small>)}
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
        <div className="operatorGrid">
          <section className="panel">
            <div className="panelHeader"><strong>团队成员和权限</strong><small>{teamMembers.length} 人</small></div>
            {teamMembers.length === 0 && <EmptyState text="暂无团队成员。后端会自动生成企业 owner 成员。" />}
            {teamMembers.map((member) => (
              <article className="knowledgeItem" key={member.id}>
                <strong>{member.name} · {member.role}</strong>
                <p>{member.permissions.slice(0, 6).join(' / ') || '暂无权限'}</p>
                <small>{member.email || '无邮箱'} · {member.status} · {member.updated_at || member.created_at}</small>
              </article>
            ))}
          </section>
          <section className="panel">
            <div className="panelHeader"><strong>最近审计日志</strong><small>{auditLogs.length} 条</small></div>
            {auditLogs.length === 0 && <EmptyState text="暂无审计日志。保存渠道、更新 CRM 或 Connector 后会出现。" />}
            {auditLogs.map((log) => (
              <article className="knowledgeItem" key={log.id}>
                <strong>{log.action}</strong>
                <p>{log.summary || `${log.target_type} #${log.target_id}`}</p>
                <small>{log.actor || 'system'} · {log.created_at}</small>
              </article>
            ))}
          </section>
        </div>
        <section className="channelGrid">
          {channels.map((channel, index) => (
            <div className="channelPanel" key={channel.channel}>
              <div className="channelTop">
                <div>
                  <strong>{channel.display_name || channelNames[channel.channel] || channel.channel}</strong>
                  <small>{channel.channel}</small>
                </div>
                <em className={`pill ${channel.status}`}>{statusNames[channel.status] || channel.status}</em>
              </div>
              <label>模式
                <select value={channel.mode} onChange={(event) => updateChannel(index, {mode: event.target.value as ChannelConfig['mode']})}>
                  <option value="assist">辅助回复</option>
                  <option value="official_api">官方 API</option>
                  <option value="manual">人工接管</option>
                </select>
              </label>
              <label>状态
                <select value={channel.status} onChange={(event) => updateChannel(index, {status: event.target.value as ChannelConfig['status']})}>
                  <option value="draft">未配置</option>
                  <option value="ready">待联调</option>
                  <option value="connected">已接入</option>
                  <option value="blocked">缺权限</option>
                </select>
              </label>
              <label>接入地址 / 回调地址<input value={channel.official_api_url} onChange={(event) => updateChannel(index, {official_api_url: event.target.value})} placeholder="有平台接入信息时填写" /></label>
              <label>备注<textarea value={channel.notes} onChange={(event) => updateChannel(index, {notes: event.target.value})} /></label>
              <div className="switchRow">
                <label><input type="checkbox" checked={channel.auto_reply_enabled} onChange={(event) => updateChannel(index, {auto_reply_enabled: event.target.checked})} />自动回复</label>
                <label><input type="checkbox" checked={channel.handoff_required} onChange={(event) => updateChannel(index, {handoff_required: event.target.checked})} />人工确认</label>
              </div>
              <button className="primaryButton fit" onClick={() => saveChannel(channel)} disabled={loading}><Save size={16} />保存渠道</button>
            </div>
          ))}
        </section>
      </div>
    );
  }

  function renderConversationInbox() {
    return (
      <div className="inboxLayout">
        <div className="conversationList">
          <PageTitle eyebrow="Inbox" title="会话收件箱" desc="AI 自动回复后的真实会话会沉淀在这里。" compact />
          {conversations.length === 0 && <EmptyState text="暂无会话。接入网页客服后，客户咨询会沉淀在这里。" />}
          {conversations.map((item) => (
            <button className={`conversationItem ${item.session_id === selectedConversation?.session_id ? 'active' : ''}`} key={item.session_id} onClick={() => setSelectedSessionId(item.session_id)}>
              <strong>{item.visitor_name || '访客'}</strong>
              <span>{item.last_query}</span>
              <small>{item.message_count} 轮 · 意向 {item.intent_score} · {item.updated_at}</small>
              {item.need_followup && <em><ShieldAlert size={14} />需接管</em>}
            </button>
          ))}
        </div>
        <div className="conversationDetail">
          {selectedConversation ? (
            <>
              <div className="detailHeader">
                <div><small>Session</small><strong>{selectedConversation.session_id}</strong></div>
                <button onClick={() => markHandoff(selectedConversation.session_id)}><ShieldAlert size={16} />标记人工接管</button>
              </div>
              <div className="messageStream">
                {(detail?.messages ?? []).map((message, index) => (
                  <div className={`chatBubble ${message.role}`} key={`${message.created_at}-${index}`}>
                    <small>{message.role === 'visitor' ? '访客' : 'AI 客服'} · {message.created_at}</small>
                    <span>{message.text}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <EmptyState text="请选择一个会话。" />}
        </div>
      </div>
    );
  }
}

function PageTitle({eyebrow, title, desc, compact = false}: {eyebrow: string; title: string; desc: string; compact?: boolean}) {
  return (
    <div className={`pageTitle ${compact ? 'compact' : ''}`}>
      <p>{eyebrow}</p>
      <h1>{title}</h1>
      <span>{desc}</span>
    </div>
  );
}

function Metric({label, value, warn = false}: {label: string; value: number; warn?: boolean}) {
  return (
    <div className={`metricCard ${warn ? 'warn' : ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function EmptyState({text}: {text: string}) {
  return (
    <div className="emptyState">
      <PlugZap size={24} />
      <span>{text}</span>
    </div>
  );
}

const useInternalGrowth =
  window.location.pathname.startsWith('/internal-growth') ||
  new URLSearchParams(window.location.search).get('app') === 'internal-growth';

createRoot(document.getElementById('root')!).render(useInternalGrowth ? <InternalGrowthApp /> : <App />);
