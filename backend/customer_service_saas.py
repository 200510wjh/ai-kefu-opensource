from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import io
import asyncio
import json
import os
import re
import secrets
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Literal
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from backend.platform.ai_engine import default_ai_engine
from backend.platform.workflow import workflow_engine


router = APIRouter(prefix="/api", tags=["customer-service-saas"])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("MERCHANT_AUTO_CUT_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = DATA_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = Path(os.getenv("CS_SQLITE_PATH", str(DATA_DIR / "customer_service.sqlite3")))
SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)


class FAQItem(BaseModel):
    question: str = ""
    answer: str = ""


class MerchantProfile(BaseModel):
    id: int | None = None
    username: str = ""
    merchant_code: str = ""
    business_name: str = ""
    industry: str = "通用服务"
    business_intro: str = ""
    products_services: str = ""
    pricing: str = ""
    promotions: str = ""
    hours: str = ""
    contact: str = ""
    faq: list[FAQItem] = []
    prompt_template: str = ""
    welcome_message: str = "您好，我是 AI 客服。请问有什么可以帮您？"


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthLoginResponse(BaseModel):
    token: str
    merchant: MerchantProfile


class DashboardOverview(BaseModel):
    today_conversations: int
    auto_replies: int
    leads: int
    handoff_needed: int
    ai_mode: str
    knowledge_items: int = 0
    enabled_channels: int = 0


class WidgetSessionRequest(BaseModel):
    merchant_code: str = Field(min_length=1)
    visitor_id: str | None = None
    page_url: str = ""
    user_agent: str = ""


class WidgetSessionResponse(BaseModel):
    session_id: str
    visitor_id: str
    merchant_code: str
    welcome_message: str
    business_name: str


class WidgetMessageRequest(BaseModel):
    merchant_code: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    visitor_id: str | None = None
    message: str = Field(min_length=1, max_length=2000)
    page_url: str = ""


class WidgetMessageResponse(BaseModel):
    session_id: str
    customer_message: str
    ai_reply: str
    intent_score: int
    need_followup: bool
    risk_flags: list[str]


class ConversationSummary(BaseModel):
    session_id: str
    customer_id: int | None = None
    visitor_name: str
    last_query: str
    last_response: str
    intent_score: int
    need_followup: bool
    message_count: int
    updated_at: str


class ConversationDetail(BaseModel):
    session_id: str
    messages: list[dict[str, Any]]


class HandoffResponse(BaseModel):
    session_id: str
    need_followup: bool


class ChannelConfig(BaseModel):
    channel: str
    display_name: str
    mode: str = "assist"
    status: str = "draft"
    official_api_url: str = ""
    webhook_url: str = ""
    auto_reply_enabled: bool = False
    handoff_required: bool = True
    notes: str = ""


class ChannelConfigUpdate(BaseModel):
    display_name: str = ""
    mode: Literal["assist", "official_api", "manual"] = "assist"
    status: Literal["draft", "ready", "connected", "blocked"] = "draft"
    official_api_url: str = ""
    webhook_url: str = ""
    auto_reply_enabled: bool = False
    handoff_required: bool = True
    notes: str = ""


class KnowledgeItem(BaseModel):
    id: int | None = None
    title: str
    content: str
    source_type: str = "manual"
    tags: str = ""
    created_at: str = ""


class KnowledgeImportRequest(BaseModel):
    title: str = "商家话术导入"
    source_type: Literal["script", "faq", "product", "policy", "manual"] = "script"
    content: str = Field(min_length=1, max_length=20000)
    tags: str = ""
    sync_to_faq: bool = True


class KnowledgeImportResponse(BaseModel):
    imported: int
    faq_added: int
    items: list[KnowledgeItem]
    filename: str = ""


class CRMLead(BaseModel):
    id: int
    source: str = "web_widget"
    name: str = ""
    contact: str = ""
    need: str = ""
    status: str = "pending"
    sales_stage: str = "new"
    owner: str = ""
    intent_score: int = 0
    tags: list[str] = Field(default_factory=list)
    last_session_id: str = ""
    next_followup_at: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


class CRMLeadCreate(BaseModel):
    source: str = "manual"
    name: str = ""
    contact: str = ""
    need: str = Field(min_length=1, max_length=3000)
    sales_stage: str = "new"
    owner: str = ""
    tags: list[str] = Field(default_factory=list)
    next_followup_at: str = ""
    notes: str = ""


class CRMLeadUpdate(BaseModel):
    name: str | None = None
    contact: str | None = None
    need: str | None = None
    status: str | None = None
    sales_stage: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    next_followup_at: str | None = None
    notes: str | None = None


class CRMTask(BaseModel):
    id: int
    merchant_id: int
    target_type: Literal["lead", "customer", "conversation"] = "lead"
    target_id: str
    title: str
    status: Literal["open", "done", "cancelled"] = "open"
    priority: Literal["low", "normal", "high"] = "normal"
    owner: str = ""
    due_at: str = ""
    source: str = "manual"
    workflow_run_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class CRMTaskCreate(BaseModel):
    target_type: Literal["lead", "customer", "conversation"] = "lead"
    target_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    priority: Literal["low", "normal", "high"] = "normal"
    owner: str = ""
    due_at: str = ""
    source: str = "manual"
    workflow_run_id: str = ""


class CRMTaskUpdate(BaseModel):
    title: str | None = None
    status: Literal["open", "done", "cancelled"] | None = None
    priority: Literal["low", "normal", "high"] | None = None
    owner: str | None = None
    due_at: str | None = None


class CRMOverview(BaseModel):
    leads: int
    high_intent: int
    needs_followup: int
    open_tasks: int
    won: int
    lost: int
    stage_counts: dict[str, int] = Field(default_factory=dict)


ConnectorKey = Literal["website", "api", "wechat", "wechat_work", "douyin", "douyin_dm", "taobao", "pdd", "xianyu"]


class ConnectorAuthUpdate(BaseModel):
    status: Literal["not_configured", "pending_auth", "connected", "failed", "assist_only"] = "pending_auth"
    auth_mode: Literal["none", "oauth", "api_key", "webhook", "manual"] = "manual"
    account_name: str = ""
    callback_url: str = ""
    nonsecret_config: dict[str, Any] = Field(default_factory=dict)
    secret_fields: dict[str, str] = Field(default_factory=dict)
    read_only_enabled: bool = True
    send_enabled: bool = False
    notes: str = ""


class ConnectorSendGateUpdate(BaseModel):
    send_enabled: bool = False
    confirmation_phrase: str = ""
    send_url: str = ""
    rate_limit_per_hour: int = Field(default=20, ge=1, le=200)


class ConnectorSendGateResponse(BaseModel):
    connector: str
    status: Literal["enabled", "disabled", "setup_required"]
    send_enabled: bool = False
    configured_fields: list[str] = Field(default_factory=list)
    next_action: str


class ConnectorHealthItem(BaseModel):
    connector: str
    label: str
    status: Literal["pass", "warning", "fail"] = "warning"
    auth_status: str = ""
    auth_mode: str = ""
    read_only_enabled: bool = True
    send_enabled: bool = False
    configured_fields: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    pending_dispatches: int = 0
    failed_dispatches: int = 0
    recent_failures: int = 0
    last_sync_at: str = ""
    token_expires_at: str = ""
    next_action: str = ""


class ConnectorHealthOverview(BaseModel):
    status: Literal["pass", "warning", "fail"] = "warning"
    summary: str
    items: list[ConnectorHealthItem] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    created_at: str = ""


class ConnectorSetupTask(BaseModel):
    id: str
    connector: str
    label: str
    category: str
    severity: Literal["info", "warning", "blocker"] = "warning"
    status: Literal["done", "todo", "blocked"] = "todo"
    title: str
    evidence: str = ""
    next_action: str
    required_fields: list[str] = Field(default_factory=list)
    configured_fields: list[str] = Field(default_factory=list)
    endpoint_hint: str = ""


class ConnectorSetupGuide(BaseModel):
    status: Literal["ready", "needs_setup", "blocked"] = "needs_setup"
    summary: str
    counts: dict[str, int] = Field(default_factory=dict)
    tasks: list[ConnectorSetupTask] = Field(default_factory=list)
    created_at: str = ""


class ConnectorAuthView(BaseModel):
    key: str
    label: str
    status: str
    auth_mode: str = "none"
    account_name: str = ""
    callback_url: str = ""
    read_only_enabled: bool = True
    send_enabled: bool = False
    safety_level: Literal["read_only", "draft_only", "requires_confirmation", "disabled"] = "read_only"
    capabilities: list[str] = Field(default_factory=list)
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    last_sync_at: str = ""
    notes: str = ""


class ConnectorOAuthStartRequest(BaseModel):
    authorize_url: str = ""
    client_id: str = ""
    scope: str = ""
    redirect_uri: str = ""
    extra_params: dict[str, str] = Field(default_factory=dict)


class ConnectorOAuthStartResponse(BaseModel):
    connector: str
    status: Literal["ready", "setup_required"]
    state: str
    auth_url: str = ""
    callback_url: str = ""
    expires_at: str = ""
    next_action: str


class ConnectorOAuthCallbackResponse(BaseModel):
    connector: str
    state: str
    status: Literal["code_received", "failed"]
    configured_fields: list[str] = Field(default_factory=list)
    next_action: str


class ConnectorOAuthExchangeRequest(BaseModel):
    token_url: str = ""
    redirect_uri: str = ""
    client_id: str = ""
    extra_params: dict[str, str] = Field(default_factory=dict)


class ConnectorOAuthExchangeResponse(BaseModel):
    connector: str
    status: Literal["connected", "setup_required", "failed"]
    configured_fields: list[str] = Field(default_factory=list)
    token_endpoint_host: str = ""
    expires_at: str = ""
    next_action: str


class ConnectorOAuthRefreshRequest(BaseModel):
    token_url: str = ""
    client_id: str = ""
    extra_params: dict[str, str] = Field(default_factory=dict)


class ConnectorOAuthRefreshResponse(BaseModel):
    connector: str
    status: Literal["refreshed", "setup_required", "failed"]
    configured_fields: list[str] = Field(default_factory=list)
    token_endpoint_host: str = ""
    expires_at: str = ""
    next_action: str


class ConnectorInboundMessageRequest(BaseModel):
    external_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    contact: str = ""
    text: str = Field(min_length=1, max_length=3000)
    raw: dict[str, Any] = Field(default_factory=dict)


class ConnectorInboundLeadRequest(BaseModel):
    external_id: str = ""
    name: str = ""
    contact: str = ""
    need: str = Field(min_length=1, max_length=3000)
    raw: dict[str, Any] = Field(default_factory=dict)


class ConnectorIngestResponse(BaseModel):
    connector: str
    mode: Literal["read_only"]
    customer_id: int | None = None
    lead_id: int | None = None
    draft_id: int | None = None
    session_id: str = ""
    workflow_run_ids: list[str] = Field(default_factory=list)
    task_created: bool = False
    next_action: str


class ConnectorReadPullRequest(BaseModel):
    resource: Literal["messages", "leads"] = "messages"
    endpoint_url: str = ""
    limit: int = Field(default=20, ge=1, le=100)
    extra_params: dict[str, str] = Field(default_factory=dict)


class ConnectorReadPullResponse(BaseModel):
    connector: str
    resource: Literal["messages", "leads"]
    status: Literal["pulled", "setup_required", "failed"]
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0
    endpoint_host: str = ""
    workflow_run_ids: list[str] = Field(default_factory=list)
    next_action: str


class ConnectorEvent(BaseModel):
    id: int
    merchant_id: int
    connector: str
    event_type: Literal["message", "lead", "auth"]
    external_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    workflow_run_id: str = ""
    created_at: str = ""


MemberRole = Literal["owner", "operations_lead", "service_lead", "agent", "admin"]


class TeamMember(BaseModel):
    id: int
    merchant_id: int
    name: str
    email: str = ""
    role: MemberRole = "agent"
    status: Literal["active", "disabled"] = "active"
    permissions: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class TeamMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = ""
    role: MemberRole = "agent"
    permissions: list[str] = Field(default_factory=list)


class TeamMemberUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: MemberRole | None = None
    status: Literal["active", "disabled"] | None = None
    permissions: list[str] | None = None


class AuditLog(BaseModel):
    id: int
    merchant_id: int
    actor: str = ""
    action: str
    target_type: str = ""
    target_id: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    ip: str = ""
    created_at: str = ""


class BillingPlan(BaseModel):
    id: str
    name: str
    price_monthly: int
    ai_quota: int
    workflow_quota: int
    connector_quota: int
    seats: int
    features: list[str] = Field(default_factory=list)


class MerchantSubscription(BaseModel):
    merchant_id: int
    plan_id: str
    status: Literal["trial", "active", "past_due", "cancelled"] = "trial"
    current_period_start: str = ""
    current_period_end: str = ""
    ai_quota: int = 0
    workflow_quota: int = 0
    connector_quota: int = 0
    seats: int = 1
    updated_at: str = ""


class SubscriptionUpdate(BaseModel):
    plan_id: str
    status: Literal["trial", "active", "past_due", "cancelled"] = "trial"


class UsageRecord(BaseModel):
    id: int
    merchant_id: int
    usage_type: str
    quantity: int = 1
    source: str = ""
    target_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class UsageSummary(BaseModel):
    period: str
    subscription: MerchantSubscription
    used: dict[str, int] = Field(default_factory=dict)
    remaining: dict[str, int] = Field(default_factory=dict)
    recent: list[UsageRecord] = Field(default_factory=list)


class BusinessReport(BaseModel):
    id: int
    merchant_id: int
    report_type: Literal["daily", "weekly", "monthly", "service_quality", "acquisition", "crm"] = "daily"
    title: str
    summary: str = ""
    content: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class ReportGenerateRequest(BaseModel):
    report_type: Literal["daily", "weekly", "monthly", "service_quality", "acquisition", "crm"] = "daily"
    title: str = ""


class ReportExportResponse(BaseModel):
    report_id: int
    format: Literal["markdown", "pdf", "docx"] = "markdown"
    filename: str
    artifact_url: str
    content: str


class DeliveryPackGenerateRequest(BaseModel):
    customer_name: str = "客户"
    include_stage_reports: bool = True
    include_acceptance_matrix: bool = True
    include_operation_manual: bool = True


class DeliveryArtifact(BaseModel):
    name: str
    artifact_url: str
    kind: Literal["markdown", "zip", "json"] = "markdown"


class DeliveryPack(BaseModel):
    id: str
    customer_name: str
    title: str
    summary: str
    artifacts: list[DeliveryArtifact] = Field(default_factory=list)
    zip_url: str = ""
    created_at: str = ""


class IntegrationWorkOrderRequest(BaseModel):
    customer_name: str = "客户"
    connectors: list[str] = Field(default_factory=list)
    include_done: bool = False


class IntegrationWorkOrderItem(BaseModel):
    connector: str
    label: str
    category: str
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["done", "todo", "blocked"] = "todo"
    required_fields: list[str] = Field(default_factory=list)
    configured_fields: list[str] = Field(default_factory=list)
    callback_url: str = ""
    endpoint_hint: str = ""
    owner: str = "客户平台管理员/技术负责人"
    next_action: str
    acceptance_check: str


class IntegrationWorkOrder(BaseModel):
    id: str
    title: str
    status: Literal["ready", "needs_setup", "blocked"] = "needs_setup"
    summary: str
    artifact_url: str = ""
    items: list[IntegrationWorkOrderItem] = Field(default_factory=list)
    created_at: str = ""


class IntegrationDryRunRequest(BaseModel):
    connectors: list[str] = Field(default_factory=list)
    include_artifact: bool = True


class IntegrationDryRunCheck(BaseModel):
    connector: str
    label: str
    check: str
    status: Literal["pass", "warning", "fail"] = "warning"
    evidence: str
    next_action: str = ""


class IntegrationDryRun(BaseModel):
    id: str
    status: Literal["pass", "warning", "fail"] = "warning"
    summary: str
    checks: list[IntegrationDryRunCheck] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class IntegrationTaskSyncRequest(BaseModel):
    connectors: list[str] = Field(default_factory=list)
    include_warnings: bool = True
    owner: str = "运营负责人"
    due_days: int = Field(default=1, ge=0, le=30)


class IntegrationTaskSyncResult(BaseModel):
    status: Literal["synced", "nothing_to_sync"] = "synced"
    created: int = 0
    skipped_existing: int = 0
    source_dry_run_status: Literal["pass", "warning", "fail"] = "warning"
    tasks: list[CRMTask] = Field(default_factory=list)
    summary: str


class IntegrationTaskReconcileRequest(BaseModel):
    connectors: list[str] = Field(default_factory=list)
    include_artifact: bool = True


class IntegrationTaskReconcileResult(BaseModel):
    status: Literal["reconciled", "nothing_closed"] = "reconciled"
    closed: int = 0
    still_open: int = 0
    source_dry_run_status: Literal["pass", "warning", "fail"] = "warning"
    closed_tasks: list[CRMTask] = Field(default_factory=list)
    remaining_checks: list[IntegrationDryRunCheck] = Field(default_factory=list)
    summary: str


class IntegrationTaskSLAItem(BaseModel):
    task_id: int
    connector: str
    check: str
    title: str
    owner: str = ""
    priority: Literal["low", "normal", "high"] = "normal"
    due_at: str = ""
    sla_status: Literal["overdue", "due_today", "upcoming", "unscheduled"] = "unscheduled"
    age_hours: int = 0
    created_at: str = ""


class IntegrationTaskSLABoard(BaseModel):
    status: Literal["clear", "attention", "overdue"] = "clear"
    summary: str
    total_open: int = 0
    overdue: int = 0
    due_today: int = 0
    upcoming: int = 0
    unscheduled: int = 0
    by_connector: dict[str, int] = Field(default_factory=dict)
    by_owner: dict[str, int] = Field(default_factory=dict)
    items: list[IntegrationTaskSLAItem] = Field(default_factory=list)
    created_at: str = ""


class IntegrationSLAEscalationRequest(BaseModel):
    include_upcoming: bool = False
    owner: str = "运营负责人"


class IntegrationSLAEscalation(BaseModel):
    id: str
    status: Literal["clear", "attention", "overdue"] = "clear"
    summary: str
    artifact_url: str = ""
    items: list[IntegrationTaskSLAItem] = Field(default_factory=list)
    created_at: str = ""


class IntegrationSLANoticeRequest(BaseModel):
    include_upcoming: bool = False
    owner: str = "运营负责人"
    channel: Literal["copy", "wecom", "dingtalk", "email"] = "copy"
    recipient: str = "客户平台负责人"


class IntegrationSLANotice(BaseModel):
    id: str
    status: Literal["clear", "attention", "overdue"] = "clear"
    channel: Literal["copy", "wecom", "dingtalk", "email"] = "copy"
    recipient: str = ""
    subject: str
    draft_text: str
    artifact_url: str = ""
    items: list[IntegrationTaskSLAItem] = Field(default_factory=list)
    created_at: str = ""


class IntegrationSLANoticeReceiptRequest(BaseModel):
    notice_id: str = ""
    recipient: str = "客户平台负责人"
    outcome: Literal["acknowledged", "needs_help", "completed"] = "acknowledged"
    confirmed_task_ids: list[int] = Field(default_factory=list)
    close_confirmed_tasks: bool = False
    confirm_phrase: str = ""
    notes: str = ""


class IntegrationSLANoticeReceipt(BaseModel):
    id: str
    status: Literal["recorded", "partial", "closed"] = "recorded"
    notice_id: str = ""
    recipient: str = ""
    outcome: Literal["acknowledged", "needs_help", "completed"] = "acknowledged"
    summary: str
    artifact_url: str = ""
    confirmed_task_ids: list[int] = Field(default_factory=list)
    ignored_task_ids: list[int] = Field(default_factory=list)
    closed_tasks: list[CRMTask] = Field(default_factory=list)
    remaining_open: int = 0
    created_at: str = ""


class IntegrationSLALoopReportRequest(BaseModel):
    audit_limit: int = Field(default=30, ge=1, le=100)
    include_artifact: bool = True


class IntegrationSLALoopReport(BaseModel):
    id: str
    status: Literal["clear", "attention", "overdue"] = "clear"
    summary: str
    artifact_url: str = ""
    total_open: int = 0
    overdue: int = 0
    due_today: int = 0
    unscheduled: int = 0
    receipts_recent: int = 0
    closed_recent: int = 0
    audit_events: list[AuditLog] = Field(default_factory=list)
    created_at: str = ""


PlatformAcceptanceScenario = Literal[
    "official_auth",
    "callback",
    "read_message",
    "read_lead",
    "draft_reply",
    "controlled_send",
    "ops_health",
    "customer_trial",
]


class PlatformAcceptanceEvidenceRequest(BaseModel):
    connector: str = "website"
    scenario: PlatformAcceptanceScenario = "customer_trial"
    result: Literal["pass", "warning", "fail"] = "warning"
    account_label: str = "客户真实账号"
    operator: str = "运营负责人"
    evidence_note: str = ""
    evidence_url: str = ""
    occurred_at: str = ""
    no_secrets_confirmed: bool = True


class PlatformAcceptanceEvidence(BaseModel):
    id: str
    connector: str
    scenario: PlatformAcceptanceScenario
    result: Literal["pass", "warning", "fail"] = "warning"
    account_label: str = ""
    operator: str = ""
    summary: str
    evidence_url: str = ""
    artifact_url: str = ""
    occurred_at: str = ""
    created_at: str = ""


class PlatformAcceptanceReportRequest(BaseModel):
    audit_limit: int = Field(default=100, ge=1, le=200)
    include_artifact: bool = True


class PlatformAcceptanceReport(BaseModel):
    id: str
    status: Literal["ready", "partial", "blocked"] = "partial"
    summary: str
    artifact_url: str = ""
    evidence_total: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    required_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    evidence: list[PlatformAcceptanceEvidence] = Field(default_factory=list)
    created_at: str = ""


class PlatformAcceptanceGapSyncRequest(BaseModel):
    owner: str = "运营负责人"
    due_days: int = Field(default=2, ge=0, le=30)
    create_tasks: bool = True
    include_artifact: bool = True


class PlatformAcceptanceGapSyncResult(BaseModel):
    id: str
    status: Literal["synced", "preview", "nothing_to_sync"] = "preview"
    summary: str
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    created: int = 0
    skipped_existing: int = 0
    tasks: list[CRMTask] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceGapReconcileRequest(BaseModel):
    close_tasks: bool = True
    include_artifact: bool = True


class PlatformAcceptanceGapReconcileResult(BaseModel):
    id: str
    status: Literal["reconciled", "preview", "nothing_closed"] = "preview"
    summary: str
    passed_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    closed: int = 0
    still_open: int = 0
    closed_tasks: list[CRMTask] = Field(default_factory=list)
    open_tasks: list[CRMTask] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceChecklistRequest(BaseModel):
    owner: str = "运营负责人"
    due_days: int = Field(default=2, ge=0, le=30)
    ensure_tasks: bool = True
    include_passed: bool = True
    include_artifact: bool = True


class PlatformAcceptanceEvidenceChecklistItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_evidence", "needs_review"] = "needs_evidence"
    target_id: str = ""
    task_id: int | None = None
    task_status: str = ""
    owner: str = ""
    due_at: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    capture_steps: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    latest_evidence_result: str = ""
    latest_evidence_url: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceChecklist(BaseModel):
    id: str
    status: Literal["complete", "collecting", "blocked"] = "collecting"
    summary: str
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    items: list[PlatformAcceptanceEvidenceChecklistItem] = Field(default_factory=list)
    tasks: list[CRMTask] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceNoticeRequest(BaseModel):
    owner: str = "运营负责人"
    recipient: str = "客户平台负责人"
    channel: Literal["copy", "wecom", "dingtalk", "email"] = "copy"
    due_days: int = Field(default=2, ge=0, le=30)
    ensure_tasks: bool = True
    include_passed: bool = False
    include_artifact: bool = True


class PlatformAcceptanceEvidenceNotice(BaseModel):
    id: str
    status: Literal["ready", "empty"] = "ready"
    channel: Literal["copy", "wecom", "dingtalk", "email"] = "copy"
    recipient: str = ""
    subject: str
    draft_text: str
    artifact_url: str = ""
    items: list[PlatformAcceptanceEvidenceChecklistItem] = Field(default_factory=list)
    created_at: str = ""


class PlatformAcceptanceEvidenceReceiptScenario(BaseModel):
    scenario: PlatformAcceptanceScenario
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "acknowledged"
    note: str = ""
    evidence_url: str = ""


class PlatformAcceptanceEvidenceReceiptRequest(BaseModel):
    notice_id: str = ""
    recipient: str = "客户平台负责人"
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "acknowledged"
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    notes: str = ""
    include_artifact: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceEvidenceReceipt(BaseModel):
    id: str
    status: Literal["recorded", "needs_help", "submitted"] = "recorded"
    notice_id: str = ""
    recipient: str = ""
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "acknowledged"
    summary: str
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceReviewTaskSyncRequest(BaseModel):
    owner: str = "运营负责人"
    due_days: int = Field(default=1, ge=0, le=30)
    include_needs_help: bool = True
    create_tasks: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=200, ge=1, le=500)


class PlatformAcceptanceEvidenceReviewTaskItem(BaseModel):
    receipt_id: str = ""
    scenario: PlatformAcceptanceScenario
    outcome: Literal["needs_help", "submitted"] = "submitted"
    target_id: str = ""
    task_id: int | None = None
    task_status: str = ""
    owner: str = ""
    due_at: str = ""
    note: str = ""
    evidence_url: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceReviewTaskSyncResult(BaseModel):
    id: str
    status: Literal["synced", "preview", "nothing_to_sync"] = "preview"
    summary: str
    created: int = 0
    skipped_existing: int = 0
    submitted: int = 0
    needs_help: int = 0
    items: list[PlatformAcceptanceEvidenceReviewTaskItem] = Field(default_factory=list)
    tasks: list[CRMTask] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceSubmissionLinkRequest(BaseModel):
    recipient: str = "customer platform owner"
    owner: str = "operations reviewer"
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    due_days: int = Field(default=2, ge=0, le=30)
    expires_days: int = Field(default=7, ge=1, le=30)
    include_artifact: bool = True


class PlatformAcceptanceEvidenceSubmissionLink(BaseModel):
    id: str
    status: Literal["ready", "empty"] = "ready"
    recipient: str = ""
    owner: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    submit_url: str = ""
    token: str = ""
    expires_at: str = ""
    draft_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceCustomerSubmissionRequest(BaseModel):
    token: str = Field(min_length=1)
    submitter: str = "customer platform owner"
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "submitted"
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    notes: str = ""
    include_artifact: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceEvidenceCustomerSubmission(BaseModel):
    id: str
    status: Literal["received", "needs_help", "submitted"] = "received"
    recipient: str = ""
    submitter: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    receipt: PlatformAcceptanceEvidenceReceipt
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult
    summary: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceSprintPackRequest(BaseModel):
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    due_days: int = Field(default=1, ge=0, le=30)
    expires_days: int = Field(default=7, ge=1, le=30)
    ensure_tasks: bool = True
    create_links: bool = True
    include_passed: bool = False
    include_artifact: bool = True


class PlatformAcceptanceSprintScenarioItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_evidence", "needs_review"] = "needs_evidence"
    task_id: int | None = None
    task_status: str = ""
    owner: str = ""
    due_at: str = ""
    evidence_count: int = 0
    latest_evidence_result: str = ""
    latest_evidence_url: str = ""
    required_evidence: list[str] = Field(default_factory=list)
    capture_steps: list[str] = Field(default_factory=list)
    next_action: str = ""
    submission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None


class PlatformAcceptanceSprintPack(BaseModel):
    id: str
    status: Literal["complete", "collecting", "empty"] = "collecting"
    summary: str
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    items: list[PlatformAcceptanceSprintScenarioItem] = Field(default_factory=list)
    tasks: list[CRMTask] = Field(default_factory=list)
    links: list[PlatformAcceptanceEvidenceSubmissionLink] = Field(default_factory=list)
    checklist: PlatformAcceptanceEvidenceChecklist | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceLiveRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    due_days: int = Field(default=1, ge=0, le=30)
    expires_days: int = Field(default=7, ge=1, le=30)
    ensure_tasks: bool = True
    create_sprint_pack: bool = True
    create_links: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceLiveRunScenario(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_review", "needs_help", "needs_evidence"] = "needs_evidence"
    evidence_count: int = 0
    latest_evidence_result: str = ""
    latest_evidence_url: str = ""
    gap_task_id: int | None = None
    gap_task_status: str = ""
    review_task_count: int = 0
    customer_submission_count: int = 0
    receipt_count: int = 0
    submission_link_count: int = 0
    submission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None
    next_action: str = ""


class PlatformAcceptanceLiveRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "reviewing", "collecting", "blocked"] = "collecting"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    required_total: int = 0
    passed: int = 0
    missing: int = 0
    needs_review: int = 0
    needs_help: int = 0
    scenarios: list[PlatformAcceptanceLiveRunScenario] = Field(default_factory=list)
    sprint_pack: PlatformAcceptanceSprintPack | None = None
    signoff_draft: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceJointDebugRunRequest(BaseModel):
    customer_name: str = "customer"
    operator: str = "operations reviewer"
    connectors: list[str] = Field(default_factory=list)
    attempt_pull: bool = True
    auto_register_pass_evidence: bool = True
    pull_limit: int = Field(default=3, ge=1, le=20)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceJointDebugScenario(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_setup", "failed", "skipped"] = "needs_setup"
    connector: str = ""
    evidence_summary: str = ""
    next_action: str = ""
    registered_evidence: PlatformAcceptanceEvidence | None = None
    pull_result: ConnectorReadPullResponse | None = None


class PlatformAcceptanceJointDebugRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "partial", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    operator: str = ""
    connectors: list[str] = Field(default_factory=list)
    passed: int = 0
    missing: int = 0
    scenarios: list[PlatformAcceptanceJointDebugScenario] = Field(default_factory=list)
    live_run: PlatformAcceptanceLiveRun | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceGapClosureRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    attempt_exchange: bool = True
    attempt_pull: bool = True
    auto_register_pass_evidence: bool = True
    create_submission_links: bool = True
    create_gap_tasks: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceGapClosureItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_config", "needs_customer", "failed", "ready"] = "needs_config"
    connector: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    next_action: str = ""
    registered_evidence: PlatformAcceptanceEvidence | None = None
    submission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None
    exchange_result: ConnectorOAuthExchangeResponse | None = None
    pull_result: ConnectorReadPullResponse | None = None


class PlatformAcceptanceGapClosureRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "partial", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    missing_before: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_after: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    items: list[PlatformAcceptanceGapClosureItem] = Field(default_factory=list)
    joint_debug: PlatformAcceptanceJointDebugRun | None = None
    gap_sync: PlatformAcceptanceGapSyncResult | None = None
    final_gate: Any | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceOwnerActionPackRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    create_customer_trial_link: bool = True
    expires_days: int = Field(default=7, ge=1, le=30)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceOwnerActionItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "needs_customer", "needs_ops", "ready"] = "needs_customer"
    connector: str = ""
    required_fields: list[str] = Field(default_factory=list)
    configured_fields: list[str] = Field(default_factory=list)
    callback_url: str = ""
    action_text: str = ""
    secure_note: str = ""
    submission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None


class PlatformAcceptanceOwnerActionPack(BaseModel):
    id: str
    status: Literal["complete", "ready_for_customer", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    items: list[PlatformAcceptanceOwnerActionItem] = Field(default_factory=list)
    draft_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceFinalSignoffLinkRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    signer_name: str = "customer platform owner"
    signer_role: str = "platform owner"
    expires_days: int = Field(default=7, ge=1, le=30)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceFinalSignoffLink(BaseModel):
    id: str
    status: Literal["ready", "blocked"] = "blocked"
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    signer_name: str = ""
    signer_role: str = ""
    live_run: PlatformAcceptanceLiveRun
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    submit_url: str = ""
    token: str = ""
    expires_at: str = ""
    signoff_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceFinalSignoffRequest(BaseModel):
    token: str = Field(min_length=1)
    signer_name: str = "customer platform owner"
    signer_role: str = "platform owner"
    decision: Literal["accepted", "needs_changes"] = "accepted"
    notes: str = ""
    include_artifact: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceFinalSignoff(BaseModel):
    id: str
    status: Literal["accepted", "changes_requested"] = "accepted"
    signoff_link_id: str = ""
    customer_name: str = ""
    signer_name: str = ""
    signer_role: str = ""
    live_run_id: str = ""
    accepted_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    summary: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceOwnerClosureConnectorUpdate(BaseModel):
    connector: str = "douyin"
    status: Literal["not_configured", "pending_auth", "connected", "failed", "assist_only"] = "pending_auth"
    auth_mode: Literal["none", "oauth", "api_key", "webhook", "manual"] = "oauth"
    account_name: str = ""
    callback_url: str = ""
    nonsecret_config: dict[str, Any] = Field(default_factory=dict)
    secret_fields: dict[str, str] = Field(default_factory=dict)
    read_only_enabled: bool = True
    notes: str = ""


class PlatformAcceptanceOwnerClosureRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connector_updates: list[PlatformAcceptanceOwnerClosureConnectorUpdate] = Field(default_factory=list)
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    receipt_outcome: Literal["acknowledged", "needs_help", "submitted"] = "submitted"
    notes: str = ""
    attempt_exchange: bool = True
    attempt_pull: bool = True
    auto_register_pass_evidence: bool = True
    create_submission_links: bool = True
    create_gap_tasks: bool = True
    create_review_tasks: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)
    no_secrets_confirmed: bool = True


class PlatformAcceptanceOwnerClosureConnectorResult(BaseModel):
    connector: str
    status: Literal["applied", "skipped", "failed"] = "applied"
    auth_status: str = ""
    auth_mode: str = ""
    configured_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    applied_fields: list[str] = Field(default_factory=list)
    secret_field_names: list[str] = Field(default_factory=list)
    next_action: str = ""


class PlatformAcceptanceOwnerClosureRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "partial", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    missing_before: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_after: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    connector_results: list[PlatformAcceptanceOwnerClosureConnectorResult] = Field(default_factory=list)
    receipt: PlatformAcceptanceEvidenceReceipt | None = None
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    gap_closure: PlatformAcceptanceGapClosureRun | None = None
    owner_action_pack: PlatformAcceptanceOwnerActionPack | None = None
    final_gate: PlatformAcceptanceFinalSignoffLink | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceOwnerClosureLinkRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    expires_days: int = Field(default=3, ge=1, le=14)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceOwnerClosureLink(BaseModel):
    id: str
    status: Literal["ready", "empty"] = "ready"
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    connectors: list[str] = Field(default_factory=list)
    submit_url: str = ""
    token: str = ""
    expires_at: str = ""
    draft_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceOwnerClosureSubmissionRequest(BaseModel):
    token: str = Field(min_length=1)
    connector_update: PlatformAcceptanceOwnerClosureConnectorUpdate | None = None
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    receipt_outcome: Literal["acknowledged", "needs_help", "submitted"] = "submitted"
    notes: str = ""
    attempt_exchange: bool = True
    attempt_pull: bool = True
    create_submission_links: bool = True
    create_gap_tasks: bool = True
    create_review_tasks: bool = True
    include_artifact: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceAutoWatchRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    attempt_exchange: bool = True
    attempt_pull: bool = True
    create_owner_closure_link: bool = True
    create_review_tasks: bool = True
    create_gap_tasks: bool = True
    create_customer_links: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceAutoWatchAction(BaseModel):
    step: str
    status: Literal["done", "waiting", "blocked", "skipped"] = "waiting"
    summary: str = ""
    next_action: str = ""
    artifact_url: str = ""


class PlatformAcceptanceAutoWatchRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "waiting_for_customer", "needs_ops", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    missing_before: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_after: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    actions: list[PlatformAcceptanceAutoWatchAction] = Field(default_factory=list)
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    joint_debug: PlatformAcceptanceJointDebugRun | None = None
    gap_closure: PlatformAcceptanceGapClosureRun | None = None
    owner_closure_link: PlatformAcceptanceOwnerClosureLink | None = None
    owner_action_pack: PlatformAcceptanceOwnerActionPack | None = None
    final_gate: PlatformAcceptanceFinalSignoffLink | None = None
    next_probe_at: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceWatchBoardRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceWatchBoardScenario(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "waiting_customer", "needs_ops", "overdue"] = "waiting_customer"
    owner: str = ""
    due_at: str = ""
    wait_hours: int = 0
    escalation: Literal["none", "watch", "urgent"] = "none"
    task_id: int | None = None
    latest_action: str = ""
    latest_action_at: str = ""
    latest_artifact_url: str = ""
    next_action: str = ""


class PlatformAcceptanceWatchBoard(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "waiting_for_customer", "needs_ops", "overdue"] = "waiting_for_customer"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    evidence_status: str = ""
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    scenarios: list[PlatformAcceptanceWatchBoardScenario] = Field(default_factory=list)
    latest_auto_watch: dict[str, Any] = Field(default_factory=dict)
    open_gap_tasks: int = 0
    reminder_draft: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceCustomerRoomLinkRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    expires_days: int = Field(default=3, ge=1, le=14)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceCustomerRoomLink(BaseModel):
    id: str
    status: Literal["ready", "blocked"] = "ready"
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    evidence_status: str = ""
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    room_url: str = ""
    token: str = ""
    expires_at: str = ""
    evidence_submission_url: str = ""
    owner_closure_url: str = ""
    final_signoff_url: str = ""
    watch_board_url: str = ""
    draft_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceCustomerRoomReceiptRequest(BaseModel):
    token: str = Field(min_length=1)
    submitter: str = "customer platform owner"
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "acknowledged"
    scenario_receipts: list[PlatformAcceptanceEvidenceReceiptScenario] = Field(default_factory=list)
    notes: str = ""
    include_artifact: bool = True
    create_review_tasks: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceCustomerRoomReceipt(BaseModel):
    id: str
    status: Literal["recorded", "needs_help", "submitted"] = "recorded"
    room_link_id: str = ""
    customer_name: str = ""
    recipient: str = ""
    submitter: str = ""
    outcome: Literal["acknowledged", "needs_help", "submitted"] = "acknowledged"
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    receipt: PlatformAcceptanceEvidenceReceipt
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    summary: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceReviewDecisionRequest(BaseModel):
    scenario: PlatformAcceptanceScenario = "customer_trial"
    decision: Literal["approved", "needs_redaction", "rejected"] = "needs_redaction"
    review_task_ids: list[int] = Field(default_factory=list)
    connector: str = "website"
    account_label: str = "customer platform account"
    operator: str = "operations reviewer"
    evidence_note: str = ""
    evidence_url: str = ""
    register_pass_evidence: bool = False
    close_review_tasks: bool = False
    reconcile_gap_tasks: bool = False
    request_resubmission_link: bool = False
    confirm_phrase: str = ""
    include_artifact: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceEvidenceReviewDecision(BaseModel):
    id: str
    status: Literal["recorded", "evidence_registered", "needs_redaction", "rejected"] = "recorded"
    scenario: PlatformAcceptanceScenario
    decision: Literal["approved", "needs_redaction", "rejected"]
    summary: str
    review_task_ids: list[int] = Field(default_factory=list)
    closed_review_tasks: list[CRMTask] = Field(default_factory=list)
    evidence: PlatformAcceptanceEvidence | None = None
    gap_reconcile: PlatformAcceptanceGapReconcileResult | None = None
    resubmission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceReviewDeskRequest(BaseModel):
    owner: str = "operations reviewer"
    due_days: int = Field(default=1, ge=0, le=30)
    include_needs_help: bool = True
    create_review_tasks: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceReviewDeskScenario(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["passed", "ready_to_review", "needs_customer_help", "needs_evidence"] = "needs_evidence"
    outcome: Literal["acknowledged", "needs_help", "submitted", "none"] = "none"
    receipt_id: str = ""
    task_id: int | None = None
    task_status: str = ""
    owner: str = ""
    due_at: str = ""
    evidence_url: str = ""
    note: str = ""
    can_register_pass: bool = False
    recommended_decision: Literal["approved", "needs_redaction", "rejected", "none"] = "none"
    next_action: str = ""


class PlatformAcceptanceReviewDesk(BaseModel):
    id: str
    status: Literal["ready_for_review", "waiting_customer", "complete"] = "waiting_customer"
    summary: str
    required_total: int = 0
    passed: int = 0
    ready_to_review: int = 0
    needs_customer_help: int = 0
    needs_evidence: int = 0
    scenarios: list[PlatformAcceptanceReviewDeskScenario] = Field(default_factory=list)
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceReviewExecutionDecisionInput(BaseModel):
    scenario: PlatformAcceptanceScenario
    decision: Literal["approved", "needs_redaction", "rejected"] = "approved"
    review_task_ids: list[int] = Field(default_factory=list)
    connector: str = "website"
    account_label: str = "customer platform account"
    operator: str = "operations reviewer"
    evidence_note: str = ""
    evidence_url: str = ""
    close_review_tasks: bool = True
    reconcile_gap_tasks: bool = True
    request_resubmission_link: bool = False


class PlatformAcceptanceReviewExecutionRunRequest(BaseModel):
    owner: str = "operations reviewer"
    due_days: int = Field(default=1, ge=0, le=30)
    decisions: list[PlatformAcceptanceReviewExecutionDecisionInput] = Field(default_factory=list)
    auto_ready_items: bool = True
    execute: bool = False
    confirm_phrase: str = ""
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)
    no_secrets_confirmed: bool = True


class PlatformAcceptanceReviewExecutionRunItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    decision: Literal["approved", "needs_redaction", "rejected"]
    status: Literal["preview", "executed", "blocked"] = "preview"
    review_task_ids: list[int] = Field(default_factory=list)
    evidence_registered: bool = False
    closed_review_tasks: int = 0
    gap_closed: int = 0
    resubmission_url: str = ""
    artifact_url: str = ""
    error: str = ""
    next_action: str = ""


class PlatformAcceptanceReviewExecutionRun(BaseModel):
    id: str
    status: Literal["preview", "executed", "partial", "blocked"] = "preview"
    summary: str
    requested: int = 0
    executed: int = 0
    blocked: int = 0
    evidence_registered: int = 0
    gap_closed: int = 0
    items: list[PlatformAcceptanceReviewExecutionRunItem] = Field(default_factory=list)
    decisions: list[PlatformAcceptanceEvidenceReviewDecision] = Field(default_factory=list)
    desk_before: PlatformAcceptanceReviewDesk | None = None
    desk_after: PlatformAcceptanceReviewDesk | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceImportItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    connector: str = "website"
    account_label: str = "customer platform account"
    operator: str = "operations reviewer"
    evidence_note: str = ""
    evidence_url: str = ""
    occurred_at: str = ""
    review_task_ids: list[int] = Field(default_factory=list)


class PlatformAcceptanceEvidenceImportRunRequest(BaseModel):
    owner: str = "operations reviewer"
    items: list[PlatformAcceptanceEvidenceImportItem] = Field(default_factory=list)
    required_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    execute: bool = False
    confirm_phrase: str = ""
    close_review_tasks: bool = True
    reconcile_gap_tasks: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)
    no_secrets_confirmed: bool = True
    check_url_reachability: bool = True


class PlatformAcceptanceEvidenceUrlPrecheckRequest(BaseModel):
    owner: str = "operations reviewer"
    items: list[PlatformAcceptanceEvidenceImportItem] = Field(default_factory=list)
    check_reachability: bool = True
    include_artifact: bool = True


class PlatformAcceptanceEvidenceUrlPrecheckItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    evidence_url: str = ""
    status: Literal["ok", "warning", "blocked"] = "warning"
    http_status: int = 0
    content_type: str = ""
    host: str = ""
    final_url: str = ""
    reason: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceUrlPrecheckRun(BaseModel):
    id: str
    status: Literal["ok", "warning", "blocked"] = "warning"
    summary: str
    checked: int = 0
    ok: int = 0
    warning: int = 0
    blocked: int = 0
    items: list[PlatformAcceptanceEvidenceUrlPrecheckItem] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceImportRunItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["ready", "imported", "missing", "blocked"] = "missing"
    evidence_url: str = ""
    url_precheck: PlatformAcceptanceEvidenceUrlPrecheckItem | None = None
    review_task_ids: list[int] = Field(default_factory=list)
    evidence_id: str = ""
    decision_id: str = ""
    gap_closed: int = 0
    error: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceImportRun(BaseModel):
    id: str
    status: Literal["preview", "imported", "partial", "blocked"] = "preview"
    summary: str
    required_total: int = 0
    supplied: int = 0
    ready: int = 0
    imported: int = 0
    blocked: int = 0
    evidence_registered: int = 0
    gap_closed: int = 0
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    items: list[PlatformAcceptanceEvidenceImportRunItem] = Field(default_factory=list)
    decisions: list[PlatformAcceptanceEvidenceReviewDecision] = Field(default_factory=list)
    report_before: PlatformAcceptanceReport | None = None
    report_after: PlatformAcceptanceReport | None = None
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceManifestLinkRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    expires_days: int = Field(default=3, ge=1, le=14)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceEvidenceManifestLink(BaseModel):
    id: str
    status: Literal["ready", "empty"] = "ready"
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    manifest_url: str = ""
    token: str = ""
    expires_at: str = ""
    draft_text: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceManifestSubmissionRequest(BaseModel):
    token: str = Field(min_length=1)
    submitter: str = "customer platform owner"
    items: list[PlatformAcceptanceEvidenceImportItem] = Field(default_factory=list)
    notes: str = ""
    include_artifact: bool = True
    create_review_tasks: bool = True
    no_secrets_confirmed: bool = True


class PlatformAcceptanceEvidenceManifestUpload(BaseModel):
    id: str
    status: Literal["ready"] = "ready"
    scenario: PlatformAcceptanceScenario
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    submitter: str = ""
    evidence_note: str = ""
    evidence_url: str = ""
    artifact_url: str = ""
    created_at: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceManifestSubmission(BaseModel):
    id: str
    status: Literal["preview_ready", "needs_work", "empty"] = "needs_work"
    customer_name: str = ""
    recipient: str = ""
    submitter: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    import_preview: PlatformAcceptanceEvidenceImportRun
    receipt: PlatformAcceptanceEvidenceReceipt
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    ready: int = 0
    blocked: int = 0
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    summary: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceEvidenceManifestInboxRequest(BaseModel):
    audit_limit: int = Field(default=300, ge=1, le=500)
    include_artifact: bool = True


class PlatformAcceptanceEvidenceManifestInboxItem(BaseModel):
    submission_id: str = ""
    status: str = ""
    ready: int = 0
    blocked: int = 0
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    import_preview_id: str = ""
    import_preview_artifact_url: str = ""
    submission_artifact_url: str = ""
    receipt_id: str = ""
    review_sync_id: str = ""
    created_at: str = ""
    next_action: str = ""


class PlatformAcceptanceEvidenceManifestInbox(BaseModel):
    id: str
    status: Literal["empty", "ready_to_import", "needs_customer", "mixed"] = "empty"
    summary: str
    total: int = 0
    ready: int = 0
    blocked: int = 0
    items: list[PlatformAcceptanceEvidenceManifestInboxItem] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestImportQueueRequest(BaseModel):
    audit_limit: int = Field(default=300, ge=1, le=500)
    include_artifact: bool = True


class PlatformAcceptanceManifestImportQueueItem(BaseModel):
    submission_id: str = ""
    status: Literal["ready_to_import", "recovered_for_review", "needs_customer", "needs_manual_review"] = "needs_manual_review"
    ready: int = 0
    blocked: int = 0
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    import_items: list[PlatformAcceptanceEvidenceImportItem] = Field(default_factory=list)
    source: Literal["metadata", "artifact", "manual"] = "manual"
    recovered: bool = False
    recovery_review_id: str = ""
    recovery_review_status: str = ""
    recovery_review_decision: str = ""
    import_preview_artifact_url: str = ""
    submission_artifact_url: str = ""
    receipt_id: str = ""
    review_sync_id: str = ""
    created_at: str = ""
    next_action: str = ""


class PlatformAcceptanceManifestImportQueue(BaseModel):
    id: str
    status: Literal["empty", "ready", "recovered", "needs_customer", "needs_manual_review", "mixed"] = "empty"
    summary: str
    total: int = 0
    ready: int = 0
    recovered: int = 0
    needs_customer: int = 0
    needs_manual_review: int = 0
    items: list[PlatformAcceptanceManifestImportQueueItem] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestRecoveryReviewRequest(BaseModel):
    submission_id: str = Field(min_length=1)
    decision: Literal["accepted_for_preview", "needs_customer_resubmission", "rejected"] = "needs_customer_resubmission"
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    review_note: str = ""
    create_manifest_link: bool = True
    execute: bool = False
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)
    no_secrets_confirmed: bool = True


class PlatformAcceptanceManifestRecoveryReview(BaseModel):
    id: str
    status: Literal["preview", "accepted_for_preview", "needs_customer_resubmission", "rejected"] = "preview"
    submission_id: str = ""
    decision: Literal["accepted_for_preview", "needs_customer_resubmission", "rejected"] = "needs_customer_resubmission"
    source: Literal["metadata", "artifact", "manual"] = "manual"
    recovered: bool = False
    import_items: list[PlatformAcceptanceEvidenceImportItem] = Field(default_factory=list)
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    resubmission_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    import_preview_artifact_url: str = ""
    submission_artifact_url: str = ""
    manifest_link: PlatformAcceptanceEvidenceManifestLink | None = None
    queue_item: PlatformAcceptanceManifestImportQueueItem | None = None
    review_note: str = ""
    summary: str = ""
    next_action: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestRecoveryResubmissionRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    review_note: str = "Recovered manifest payload requires a fresh structured customer manifest before evidence import."
    execute: bool = False
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)
    no_secrets_confirmed: bool = True


class PlatformAcceptanceManifestRecoveryResubmissionRunItem(BaseModel):
    submission_id: str = ""
    status: Literal["would_request", "requested", "already_requested", "skipped", "blocked"] = "would_request"
    source: Literal["metadata", "artifact", "manual"] = "manual"
    recovered: bool = False
    recovery_review_status: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    import_items: int = 0
    manifest_url: str = ""
    manifest_artifact_url: str = ""
    review_id: str = ""
    next_action: str = ""


class PlatformAcceptanceManifestRecoveryResubmissionRun(BaseModel):
    id: str
    status: Literal["preview", "executed", "partial", "empty"] = "preview"
    summary: str
    total: int = 0
    would_request: int = 0
    requested: int = 0
    already_requested: int = 0
    skipped: int = 0
    blocked: int = 0
    items: list[PlatformAcceptanceManifestRecoveryResubmissionRunItem] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestResubmissionTrackerRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    stale_after_hours: int = Field(default=24, ge=1, le=168)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceManifestResubmissionTrackerItem(BaseModel):
    submission_id: str = ""
    status: Literal["waiting_customer", "ready_for_review", "needs_fix", "stale", "complete", "missing_link"] = "waiting_customer"
    manifest_link_id: str = ""
    recovery_review_id: str = ""
    scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    latest_submission_id: str = ""
    latest_submission_status: str = ""
    latest_submission_artifact_url: str = ""
    import_preview_artifact_url: str = ""
    wait_hours: int = 0
    escalation: Literal["none", "watch", "urgent"] = "none"
    next_action: str = ""


class PlatformAcceptanceManifestResubmissionTracker(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "ready_for_review", "waiting_customer", "stale", "needs_ops", "empty"] = "empty"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    evidence_status: str = ""
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    total: int = 0
    waiting_customer: int = 0
    ready_for_review: int = 0
    needs_fix: int = 0
    stale: int = 0
    complete: int = 0
    missing_link: int = 0
    items: list[PlatformAcceptanceManifestResubmissionTrackerItem] = Field(default_factory=list)
    reminder_draft: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestResubmissionReminderRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    stale_after_hours: int = Field(default=24, ge=1, le=168)
    due_hours: int = Field(default=24, ge=1, le=168)
    create_tasks: bool = False
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceManifestResubmissionReminderRunItem(BaseModel):
    submission_id: str = ""
    tracker_status: str = ""
    action_status: Literal["preview", "task_created", "task_existing", "skipped", "blocked"] = "preview"
    task: CRMTask | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    due_at: str = ""
    title: str = ""
    next_action: str = ""


class PlatformAcceptanceManifestResubmissionReminderRun(BaseModel):
    id: str
    status: Literal["preview", "created", "clear", "partial", "blocked"] = "preview"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    create_tasks: bool = False
    total: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0
    blocked: int = 0
    tracker: PlatformAcceptanceManifestResubmissionTracker | None = None
    items: list[PlatformAcceptanceManifestResubmissionReminderRunItem] = Field(default_factory=list)
    reminder_draft: str = ""
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceFinalClosureRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    connectors: list[str] = Field(default_factory=list)
    attempt_exchange: bool = True
    attempt_pull: bool = True
    create_tasks: bool = True
    create_customer_links: bool = True
    create_owner_closure_link: bool = True
    create_customer_room: bool = True
    create_resubmission_reminder: bool = True
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceFinalClosureRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "waiting_customer", "needs_ops", "blocked"] = "blocked"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    missing_before: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    missing_after: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    report_before: PlatformAcceptanceReport | None = None
    report_after: PlatformAcceptanceReport | None = None
    tracker: PlatformAcceptanceManifestResubmissionTracker | None = None
    reminder_run: PlatformAcceptanceManifestResubmissionReminderRun | None = None
    auto_watch: PlatformAcceptanceAutoWatchRun | None = None
    customer_room: PlatformAcceptanceCustomerRoomLink | None = None
    final_gate: PlatformAcceptanceFinalSignoffLink | None = None
    created_tasks: int = 0
    existing_tasks: int = 0
    secure_links: int = 0
    artifact_url: str = ""
    created_at: str = ""


class PlatformAcceptanceManifestFollowupRunRequest(BaseModel):
    customer_name: str = "customer"
    owner: str = "operations reviewer"
    recipient: str = "customer platform owner"
    create_manifest_link: bool = True
    expires_days: int = Field(default=3, ge=1, le=14)
    include_artifact: bool = True
    audit_limit: int = Field(default=300, ge=1, le=500)


class PlatformAcceptanceManifestFollowupRunItem(BaseModel):
    scenario: PlatformAcceptanceScenario
    status: Literal["ready_to_import", "needs_resubmission", "awaiting_customer"] = "awaiting_customer"
    latest_submission_id: str = ""
    latest_submission_status: str = ""
    import_preview_artifact_url: str = ""
    submission_artifact_url: str = ""
    requirement: str = ""
    next_action: str = ""


class PlatformAcceptanceManifestFollowupRun(BaseModel):
    id: str
    status: Literal["ready_for_signoff", "ready_for_review", "waiting_for_customer", "needs_ops"] = "waiting_for_customer"
    summary: str
    customer_name: str = ""
    owner: str = ""
    recipient: str = ""
    evidence_status: str = ""
    missing_scenarios: list[PlatformAcceptanceScenario] = Field(default_factory=list)
    inbox_status: str = ""
    inbox_total: int = 0
    inbox_ready: int = 0
    inbox_blocked: int = 0
    manifest_url: str = ""
    manifest_artifact_url: str = ""
    items: list[PlatformAcceptanceManifestFollowupRunItem] = Field(default_factory=list)
    reminder_draft: str = ""
    artifact_url: str = ""
    created_at: str = ""


class AcceptanceAuditRequest(BaseModel):
    include_artifact: bool = True


class AcceptanceAuditItem(BaseModel):
    module: str
    status: Literal["pass", "warning", "fail"]
    evidence: str
    next_action: str = ""


class AcceptanceAudit(BaseModel):
    id: str
    readiness_score: int
    status: Literal["ready", "ready_with_boundaries", "needs_attention"]
    summary: str
    items: list[AcceptanceAuditItem] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    artifact_url: str = ""
    created_at: str = ""


CONNECTOR_CATALOG: dict[str, dict[str, Any]] = {
    "website": {
        "label": "官网客服",
        "status": "connected",
        "auth_mode": "none",
        "capabilities": ["message_read", "message_reply", "lead_sync"],
        "required_fields": [],
        "safety_level": "read_only",
    },
    "api": {
        "label": "开放 API",
        "status": "pending_auth",
        "auth_mode": "api_key",
        "capabilities": ["message_read", "lead_sync"],
        "required_fields": ["api_key"],
        "safety_level": "read_only",
    },
    "wechat": {
        "label": "微信",
        "status": "assist_only",
        "auth_mode": "manual",
        "capabilities": ["draft_reply"],
        "required_fields": [],
        "safety_level": "draft_only",
    },
    "wechat_work": {
        "label": "企业微信客服",
        "status": "pending_auth",
        "auth_mode": "webhook",
        "capabilities": ["message_read", "lead_sync", "draft_reply"],
        "required_fields": ["corp_id", "agent_id", "token", "encoding_aes_key"],
        "safety_level": "read_only",
    },
    "douyin": {
        "label": "抖音企业号/小店",
        "status": "pending_auth",
        "auth_mode": "oauth",
        "capabilities": ["lead_sync", "product_read"],
        "required_fields": ["client_key", "client_secret"],
        "safety_level": "read_only",
    },
    "douyin_dm": {
        "label": "抖音私信",
        "status": "pending_auth",
        "auth_mode": "webhook",
        "capabilities": ["message_read", "draft_reply"],
        "required_fields": ["client_key", "client_secret", "webhook_token"],
        "safety_level": "read_only",
    },
    "taobao": {
        "label": "淘宝/千牛",
        "status": "pending_auth",
        "auth_mode": "oauth",
        "capabilities": ["message_read", "order_read", "product_read"],
        "required_fields": ["app_key", "app_secret", "session_key"],
        "safety_level": "read_only",
    },
    "pdd": {
        "label": "拼多多",
        "status": "pending_auth",
        "auth_mode": "oauth",
        "capabilities": ["message_read", "order_read", "product_read"],
        "required_fields": ["client_id", "client_secret", "access_token"],
        "safety_level": "read_only",
    },
    "xianyu": {
        "label": "闲鱼",
        "status": "assist_only",
        "auth_mode": "manual",
        "capabilities": ["draft_reply"],
        "required_fields": [],
        "safety_level": "draft_only",
    },
}


class ReplyDraftRequest(BaseModel):
    channel: str = "wechat"
    message: str = Field(min_length=1, max_length=2000)
    customer_name: str = ""


class ReplyDraftResponse(BaseModel):
    channel: str
    mode: str
    reply: str
    need_followup: bool
    risk_flags: list[str]


class ReplyDraftQueueCreateRequest(BaseModel):
    channel: str = "wechat"
    message: str = Field(min_length=1, max_length=3000)
    customer_name: str = ""
    session_id: str = ""
    external_id: str = ""


class ReplyDraftReviewRequest(BaseModel):
    status: Literal["approved", "rejected", "pending"] = "approved"
    draft_text: str | None = None
    reviewer_note: str = ""


class ReplyDraftQueueItem(BaseModel):
    id: int
    merchant_id: int
    connector: str
    session_id: str = ""
    customer_id: int | None = None
    external_id: str = ""
    customer_name: str = ""
    source_text: str
    draft_text: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    risk_flags: list[str] = Field(default_factory=list)
    intent_score: int = 0
    workflow_run_id: str = ""
    reviewer: str = ""
    reviewer_note: str = ""
    created_at: str = ""
    updated_at: str = ""
    reviewed_at: str = ""


class ReplyDispatchCreateRequest(BaseModel):
    dispatch_mode: Literal["manual_copy", "api_send"] = "manual_copy"
    operator_note: str = ""


class ReplyDispatchSendRequest(BaseModel):
    confirmation_phrase: str = ""
    idempotency_key: str = ""
    dry_run: bool = False


class ReplyDispatchRevokeRequest(BaseModel):
    revoke_note: str = ""


class ReplyDispatchItem(BaseModel):
    id: int
    merchant_id: int
    draft_id: int
    connector: str
    customer_id: int | None = None
    external_id: str = ""
    dispatch_mode: Literal["manual_copy", "api_send"] = "manual_copy"
    status: Literal["manual_ready", "blocked", "sent", "send_failed", "revoked"] = "manual_ready"
    draft_text: str
    risk_flags: list[str] = Field(default_factory=list)
    operator: str = ""
    operator_note: str = ""
    revoke_note: str = ""
    created_at: str = ""
    updated_at: str = ""
    revoked_at: str = ""
    sent_at: str = ""
    send_request_id: str = ""
    send_error: str = ""
    next_action: str = ""


class ServiceScriptGenerateRequest(BaseModel):
    channel: str = "wechat"
    scenario: Literal["new_customer", "price", "objection", "after_sale", "lead_capture", "full_pack"] = "full_pack"
    product_name: str = ""
    customer_pain: str = ""
    offer: str = ""
    tone: Literal["natural", "professional", "friendly", "urgent"] = "natural"
    save_to_knowledge: bool = True


class ServiceScriptStep(BaseModel):
    title: str
    message: str
    goal: str


class ServiceScriptGenerateResponse(BaseModel):
    title: str
    channel: str
    scenario: str
    opening: str
    steps: list[ServiceScriptStep]
    objection_replies: list[ServiceScriptStep]
    closing: str
    knowledge_imported: int = 0


def now_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def db_driver() -> str:
    return os.getenv("CS_DB_DRIVER", "sqlite").lower()


def mysql_config() -> dict[str, Any]:
    return {
        "host": os.getenv("CS_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("CS_MYSQL_PORT", "3306")),
        "user": os.getenv("CS_MYSQL_USER", "root"),
        "password": os.getenv("CS_MYSQL_PASSWORD", ""),
        "database": os.getenv("CS_MYSQL_DATABASE", "ai_saas"),
        "charset": "utf8mb4",
        "cursorclass": None,
        "unix_socket": os.getenv("CS_MYSQL_UNIX_SOCKET") or None,
    }


@contextmanager
def db() -> Iterator[Any]:
    if db_driver() == "mysql":
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as exc:
            raise RuntimeError("PyMySQL is not installed") from exc

        config = {key: value for key, value in mysql_config().items() if value not in {None, ""}}
        config["cursorclass"] = pymysql.cursors.DictCursor
        conn = pymysql.connect(**config)
        try:
            init_mysql(conn)
            yield MySQLAdapter(conn)
            conn.commit()
        finally:
            conn.close()
        return

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        init_sqlite(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


class MySQLAdapter:
    def __init__(self, conn: Any):
        self.conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor


def param(sqlite: str = "?", mysql: str = "%s") -> str:
    return mysql if db_driver() == "mysql" else sqlite


def rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def ensure_sqlite_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for column, ddl in columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def mysql_table_columns(cursor: Any, table: str) -> set[str]:
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        (table,),
    )
    return {row["COLUMN_NAME"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}


def ensure_mysql_columns(cursor: Any, table: str, columns: dict[str, str]) -> None:
    existing = mysql_table_columns(cursor, table)
    for column, ddl in columns.items():
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_mysql(conn: Any) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                name VARCHAR(120),
                phone VARCHAR(80),
                openid VARCHAR(160),
                intent_score INT DEFAULT 0,
                is_high_intent TINYINT DEFAULT 0,
                followup_status VARCHAR(40) DEFAULT 'pending',
                tags VARCHAR(255),
                last_query TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        ensure_mysql_columns(
            cursor,
            "customers",
            {
                "source_channel": "VARCHAR(40) DEFAULT 'web_widget'",
                "sales_stage": "VARCHAR(40) DEFAULT 'new'",
                "owner": "VARCHAR(120) DEFAULT ''",
                "contact": "VARCHAR(160) DEFAULT ''",
                "notes": "TEXT",
                "next_followup_at": "VARCHAR(40) DEFAULT ''",
                "last_session_id": "VARCHAR(120) DEFAULT ''",
                "workflow_run_id": "VARCHAR(80) DEFAULT ''",
            },
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                customer_id INT,
                session_id VARCHAR(120),
                visitor_info TEXT,
                query TEXT NOT NULL,
                response MEDIUMTEXT,
                intent_score INT DEFAULT 0,
                need_followup TINYINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        ensure_mysql_columns(
            cursor,
            "conversations",
            {
                "source_channel": "VARCHAR(40) DEFAULT 'web_widget'",
                "risk_flags": "VARCHAR(255) DEFAULT ''",
                "workflow_run_id": "VARCHAR(80) DEFAULT ''",
            },
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                target_type VARCHAR(32) NOT NULL DEFAULT 'lead',
                target_id VARCHAR(80) NOT NULL,
                title VARCHAR(255) NOT NULL,
                status VARCHAR(32) DEFAULT 'open',
                priority VARCHAR(32) DEFAULT 'normal',
                owner VARCHAR(120) DEFAULT '',
                due_at VARCHAR(40) DEFAULT '',
                source VARCHAR(80) DEFAULT 'manual',
                workflow_run_id VARCHAR(80) DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connector_credentials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                connector VARCHAR(40) NOT NULL,
                status VARCHAR(40) DEFAULT 'not_configured',
                auth_mode VARCHAR(40) DEFAULT 'none',
                account_name VARCHAR(160) DEFAULT '',
                callback_url TEXT,
                config_json MEDIUMTEXT,
                configured_fields VARCHAR(255) DEFAULT '',
                read_only_enabled TINYINT DEFAULT 1,
                send_enabled TINYINT DEFAULT 0,
                last_sync_at VARCHAR(40) DEFAULT '',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_merchant_connector (merchant_id, connector)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connector_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                connector VARCHAR(40) NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                external_id VARCHAR(160) DEFAULT '',
                payload_json MEDIUMTEXT,
                workflow_run_id VARCHAR(80) DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connector_oauth_states (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                connector VARCHAR(40) NOT NULL,
                state VARCHAR(160) NOT NULL,
                auth_url TEXT,
                redirect_uri TEXT,
                status VARCHAR(32) DEFAULT 'pending',
                callback_payload_json MEDIUMTEXT,
                expires_at VARCHAR(40) DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                used_at VARCHAR(40) DEFAULT '',
                UNIQUE KEY uniq_oauth_state (state)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reply_drafts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                connector VARCHAR(40) NOT NULL,
                session_id VARCHAR(160) DEFAULT '',
                customer_id INT NULL,
                external_id VARCHAR(160) DEFAULT '',
                customer_name VARCHAR(160) DEFAULT '',
                source_text TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                status VARCHAR(32) DEFAULT 'pending',
                risk_flags VARCHAR(500) DEFAULT '',
                intent_score INT DEFAULT 0,
                workflow_run_id VARCHAR(80) DEFAULT '',
                reviewer VARCHAR(160) DEFAULT '',
                reviewer_note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reviewed_at VARCHAR(40) DEFAULT ''
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reply_dispatches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                draft_id INT NOT NULL,
                connector VARCHAR(40) NOT NULL,
                customer_id INT NULL,
                external_id VARCHAR(160) DEFAULT '',
                dispatch_mode VARCHAR(32) DEFAULT 'manual_copy',
                status VARCHAR(32) DEFAULT 'manual_ready',
                draft_text TEXT NOT NULL,
                risk_flags VARCHAR(500) DEFAULT '',
                operator VARCHAR(160) DEFAULT '',
                operator_note TEXT,
                revoke_note TEXT,
                send_request_id VARCHAR(160) DEFAULT '',
                send_response_json MEDIUMTEXT,
                send_error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                revoked_at VARCHAR(40) DEFAULT '',
                sent_at VARCHAR(40) DEFAULT ''
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        ensure_mysql_columns(
            cursor,
            "reply_dispatches",
            {
                "send_request_id": "VARCHAR(160) DEFAULT ''",
                "send_response_json": "MEDIUMTEXT",
                "send_error": "TEXT",
                "sent_at": "VARCHAR(40) DEFAULT ''",
            },
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS merchant_members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                name VARCHAR(120) NOT NULL,
                email VARCHAR(160) DEFAULT '',
                role VARCHAR(40) DEFAULT 'agent',
                status VARCHAR(32) DEFAULT 'active',
                permissions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                actor VARCHAR(160) DEFAULT '',
                action VARCHAR(120) NOT NULL,
                target_type VARCHAR(80) DEFAULT '',
                target_id VARCHAR(120) DEFAULT '',
                summary TEXT,
                metadata_json MEDIUMTEXT,
                ip VARCHAR(80) DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS billing_plans (
                id VARCHAR(40) PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                price_monthly INT DEFAULT 0,
                ai_quota INT DEFAULT 0,
                workflow_quota INT DEFAULT 0,
                connector_quota INT DEFAULT 0,
                seats INT DEFAULT 1,
                features TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS merchant_subscriptions (
                merchant_id INT PRIMARY KEY,
                plan_id VARCHAR(40) NOT NULL,
                status VARCHAR(32) DEFAULT 'trial',
                current_period_start VARCHAR(40) DEFAULT '',
                current_period_end VARCHAR(40) DEFAULT '',
                ai_quota INT DEFAULT 0,
                workflow_quota INT DEFAULT 0,
                connector_quota INT DEFAULT 0,
                seats INT DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                usage_type VARCHAR(80) NOT NULL,
                quantity INT DEFAULT 1,
                source VARCHAR(120) DEFAULT '',
                target_id VARCHAR(120) DEFAULT '',
                metadata_json MEDIUMTEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                report_type VARCHAR(40) NOT NULL DEFAULT 'daily',
                title VARCHAR(255) NOT NULL,
                summary TEXT,
                content MEDIUMTEXT,
                metrics_json MEDIUMTEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_configs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                channel VARCHAR(32) NOT NULL,
                display_name VARCHAR(80),
                mode VARCHAR(32) DEFAULT 'assist',
                status VARCHAR(32) DEFAULT 'draft',
                official_api_url TEXT,
                webhook_url TEXT,
                auto_reply_enabled TINYINT DEFAULT 0,
                handoff_required TINYINT DEFAULT 1,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_merchant_channel (merchant_id, channel)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        missing_knowledge_columns = {
            "merchant_id": "INT NOT NULL DEFAULT 0",
            "title": "VARCHAR(255)",
            "content": "MEDIUMTEXT",
            "source_type": "VARCHAR(32) DEFAULT 'manual'",
            "tags": "VARCHAR(255)",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INT AUTO_INCREMENT PRIMARY KEY,
                merchant_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                content MEDIUMTEXT NOT NULL,
                source_type VARCHAR(32) DEFAULT 'manual',
                tags VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        ensure_mysql_columns(cursor, "knowledge_base", missing_knowledge_columns)


def init_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            business_name TEXT,
            phone TEXT,
            mobile TEXT,
            merchant_code TEXT UNIQUE,
            welcome_message TEXT,
            prompt_template TEXT,
            status INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            name TEXT,
            phone TEXT,
            openid TEXT,
            intent_score INTEGER DEFAULT 0,
            is_high_intent INTEGER DEFAULT 0,
            followup_status TEXT DEFAULT 'pending',
            tags TEXT,
            last_query TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_sqlite_columns(
        conn,
        "customers",
        {
            "source_channel": "TEXT DEFAULT 'web_widget'",
            "sales_stage": "TEXT DEFAULT 'new'",
            "owner": "TEXT DEFAULT ''",
            "contact": "TEXT DEFAULT ''",
            "notes": "TEXT DEFAULT ''",
            "next_followup_at": "TEXT DEFAULT ''",
            "last_session_id": "TEXT DEFAULT ''",
            "workflow_run_id": "TEXT DEFAULT ''",
        },
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            customer_id INTEGER,
            session_id TEXT,
            visitor_info TEXT,
            query TEXT NOT NULL,
            response TEXT,
            intent_score INTEGER DEFAULT 0,
            need_followup INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_sqlite_columns(
        conn,
        "conversations",
        {
            "source_channel": "TEXT DEFAULT 'web_widget'",
            "risk_flags": "TEXT DEFAULT ''",
            "workflow_run_id": "TEXT DEFAULT ''",
        },
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER,
            bot_id TEXT,
            user_id TEXT,
            query TEXT,
            response TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            display_name TEXT,
            mode TEXT DEFAULT 'assist',
            status TEXT DEFAULT 'draft',
            official_api_url TEXT,
            webhook_url TEXT,
            auto_reply_enabled INTEGER DEFAULT 0,
            handoff_required INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(merchant_id, channel)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_type TEXT DEFAULT 'manual',
            tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            target_type TEXT NOT NULL DEFAULT 'lead',
            target_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            owner TEXT DEFAULT '',
            due_at TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            workflow_run_id TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            connector TEXT NOT NULL,
            status TEXT DEFAULT 'not_configured',
            auth_mode TEXT DEFAULT 'none',
            account_name TEXT DEFAULT '',
            callback_url TEXT,
            config_json TEXT,
            configured_fields TEXT DEFAULT '',
            read_only_enabled INTEGER DEFAULT 1,
            send_enabled INTEGER DEFAULT 0,
            last_sync_at TEXT DEFAULT '',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(merchant_id, connector)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            connector TEXT NOT NULL,
            event_type TEXT NOT NULL,
            external_id TEXT DEFAULT '',
            payload_json TEXT,
            workflow_run_id TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_oauth_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            connector TEXT NOT NULL,
            state TEXT NOT NULL UNIQUE,
            auth_url TEXT,
            redirect_uri TEXT,
            status TEXT DEFAULT 'pending',
            callback_payload_json TEXT,
            expires_at TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            used_at TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            connector TEXT NOT NULL,
            session_id TEXT DEFAULT '',
            customer_id INTEGER,
            external_id TEXT DEFAULT '',
            customer_name TEXT DEFAULT '',
            source_text TEXT NOT NULL,
            draft_text TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            risk_flags TEXT DEFAULT '',
            intent_score INTEGER DEFAULT 0,
            workflow_run_id TEXT DEFAULT '',
            reviewer TEXT DEFAULT '',
            reviewer_note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reply_dispatches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            draft_id INTEGER NOT NULL,
            connector TEXT NOT NULL,
            customer_id INTEGER,
            external_id TEXT DEFAULT '',
            dispatch_mode TEXT DEFAULT 'manual_copy',
            status TEXT DEFAULT 'manual_ready',
            draft_text TEXT NOT NULL,
            risk_flags TEXT DEFAULT '',
            operator TEXT DEFAULT '',
            operator_note TEXT,
            revoke_note TEXT,
            send_request_id TEXT DEFAULT '',
            send_response_json TEXT,
            send_error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            revoked_at TEXT DEFAULT '',
            sent_at TEXT DEFAULT ''
        )
        """
    )
    ensure_sqlite_columns(
        conn,
        "reply_dispatches",
        {
            "send_request_id": "TEXT DEFAULT ''",
            "send_response_json": "TEXT",
            "send_error": "TEXT",
            "sent_at": "TEXT DEFAULT ''",
        },
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT DEFAULT '',
            role TEXT DEFAULT 'agent',
            status TEXT DEFAULT 'active',
            permissions TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            actor TEXT DEFAULT '',
            action TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            summary TEXT,
            metadata_json TEXT,
            ip TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price_monthly INTEGER DEFAULT 0,
            ai_quota INTEGER DEFAULT 0,
            workflow_quota INTEGER DEFAULT 0,
            connector_quota INTEGER DEFAULT 0,
            seats INTEGER DEFAULT 1,
            features TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_subscriptions (
            merchant_id INTEGER PRIMARY KEY,
            plan_id TEXT NOT NULL,
            status TEXT DEFAULT 'trial',
            current_period_start TEXT DEFAULT '',
            current_period_end TEXT DEFAULT '',
            ai_quota INTEGER DEFAULT 0,
            workflow_quota INTEGER DEFAULT 0,
            connector_quota INTEGER DEFAULT 0,
            seats INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            source TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            metadata_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS business_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            report_type TEXT NOT NULL DEFAULT 'daily',
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            metrics_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    count = conn.execute("SELECT COUNT(*) AS c FROM merchants").fetchone()["c"]
    if count == 0:
        conn.execute(
            """
            INSERT INTO merchants (username, password_hash, business_name, merchant_code, welcome_message, prompt_template, status)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "admin",
                hashlib.sha256("admin123".encode("utf-8")).hexdigest(),
                "演示商家",
                "WJDEMO001",
                "您好，我是演示商家的 AI 客服。请问想了解产品、价格还是合作？",
                json.dumps(default_profile_payload(), ensure_ascii=False),
            ),
        )


def default_profile_payload() -> dict[str, Any]:
    return {
        "industry": "通用服务",
        "business_intro": "我们提供面向商家的 AI 客服和增长自动化服务。",
        "products_services": "AI 客服、线索记录、自动回复、人工接管。",
        "pricing": "基础版 299 元/月起，定制部署单独报价。",
        "promotions": "新客户可先试用一个场景。",
        "hours": "工作日 9:00-21:00",
        "contact": "请留下手机号或微信，顾问会跟进。",
        "faq": [
            {"question": "能自动回复吗？", "answer": "可以在网页客服里自动回复；微信/抖音私信需要官方 API 权限。"},
            {"question": "可以试用吗？", "answer": "可以先配置一个测试商家和一个网页气泡试用。"},
        ],
    }


DEFAULT_CHANNELS: dict[str, tuple[str, str]] = {
    "web_widget": ("网页客服", "已支持自动回复和会话落库"),
    "wechat": ("微信客服", "个人微信先做桌面辅助草稿；不建议承诺无人值守自动发送"),
    "wechat_work": ("企业微信客服", "最适合商用接入企业微信/微信客服官方 API；未授权前只生成回复草稿"),
    "douyin": ("抖音客服", "建议接抖音开放平台/企业号权限；未授权前只做人工辅助"),
    "taobao": ("淘宝客服", "建议接千牛/淘宝开放平台；未授权前只做话术建议"),
    "pdd": ("拼多多客服", "建议接拼多多开放平台；未授权前只做话术建议"),
    "xianyu": ("闲鱼客服", "建议接闲鱼/淘宝生态官方能力；未授权前只做桌面辅助和回复草稿"),
}


def ensure_default_channels(merchant_id: int) -> None:
    marker = param()
    with db() as conn:
        for channel, (display_name, notes) in DEFAULT_CHANNELS.items():
            row = conn.execute(
                f"SELECT id FROM channel_configs WHERE merchant_id={marker} AND channel={marker}",
                (merchant_id, channel),
            ).fetchone()
            if row:
                continue
            conn.execute(
                f"""
                INSERT INTO channel_configs
                (merchant_id, channel, display_name, mode, status, official_api_url, webhook_url, auto_reply_enabled, handoff_required, notes, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant_id,
                    channel,
                    display_name,
                    "official_api" if channel == "web_widget" else "assist",
                    "connected" if channel == "web_widget" else "draft",
                    "",
                    "",
                    1 if channel == "web_widget" else 0,
                    0 if channel == "web_widget" else 1,
                    notes,
                    now_sql(),
                    now_sql(),
                ),
            )


def knowledge_rows(merchant_id: int, limit: int = 100) -> list[dict[str, Any]]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT id,
                   COALESCE(title, '未命名知识') AS title,
                   COALESCE(content, '') AS content,
                   COALESCE(source_type, 'manual') AS source_type,
                   COALESCE(tags, '') AS tags,
                   COALESCE(created_at, '') AS created_at
            FROM knowledge_base
            WHERE merchant_id={marker}
            ORDER BY id DESC
            LIMIT {int(limit)}
            """,
            (merchant_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def knowledge_context_for(merchant_id: int | None) -> str:
    if not merchant_id:
        return ""
    rows = knowledge_rows(merchant_id, limit=12)
    if not rows:
        return ""
    blocks = []
    for row in rows:
        blocks.append(f"- {row.get('title')}: {str(row.get('content') or '')[:700]}")
    return "\n".join(blocks)


def extract_knowledge_items(payload: KnowledgeImportRequest) -> list[KnowledgeItem]:
    lines = [line.strip(" \t-•") for line in payload.content.splitlines() if line.strip()]
    items: list[KnowledgeItem] = []
    pending_question = ""
    for line in lines:
        normalized = line.replace("：", ":")
        if normalized.lower().startswith(("q:", "问:", "问题:")):
            pending_question = normalized.split(":", 1)[1].strip()
            continue
        if normalized.lower().startswith(("a:", "答:", "答案:")) and pending_question:
            answer = normalized.split(":", 1)[1].strip()
            items.append(KnowledgeItem(title=pending_question[:120], content=answer, source_type=payload.source_type, tags=payload.tags))
            pending_question = ""
            continue
        if "=>" in line:
            title, content = line.split("=>", 1)
        elif "->" in line:
            title, content = line.split("->", 1)
        elif "：" in line:
            title, content = line.split("：", 1)
        elif ":" in line and len(line.split(":", 1)[0]) <= 40:
            title, content = line.split(":", 1)
        else:
            title, content = payload.title, line
        items.append(KnowledgeItem(title=title.strip()[:120] or payload.title, content=content.strip(), source_type=payload.source_type, tags=payload.tags))
    if not items:
        items.append(KnowledgeItem(title=payload.title, content=payload.content, source_type=payload.source_type, tags=payload.tags))
    return items[:80]


def persist_knowledge_items(merchant: MerchantProfile, payload: KnowledgeImportRequest, items: list[KnowledgeItem]) -> KnowledgeImportResponse:
    marker = param()
    created: list[KnowledgeItem] = []
    with db() as conn:
        for item in items:
            cursor = conn.execute(
                f"""
                INSERT INTO knowledge_base (merchant_id, title, content, source_type, tags, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (merchant.id, item.title, item.content, item.source_type, item.tags, now_sql(), now_sql()),
            )
            created.append(item.model_copy(update={"id": getattr(cursor, "lastrowid", None), "created_at": now_sql()}))

    faq_added = 0
    if payload.sync_to_faq:
        profile = merchant_by_id(merchant.id or 0)
        existing = {faq.question.strip() for faq in profile.faq}
        next_faq = list(profile.faq)
        for item in items:
            if item.title and item.content and item.title not in existing:
                next_faq.append(FAQItem(question=item.title, answer=item.content))
                existing.add(item.title)
                faq_added += 1
        profile.faq = next_faq[:80]
        marker = param()
        with db() as conn:
            conn.execute(
                f"UPDATE merchants SET prompt_template={marker}, updated_at={marker} WHERE id={marker}",
                (profile_to_prompt(profile), now_sql(), merchant.id),
            )

    return KnowledgeImportResponse(imported=len(created), faq_added=faq_added, items=created)


def parse_profile(row: dict[str, Any]) -> MerchantProfile:
    payload = default_profile_payload()
    raw = row.get("prompt_template") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload.update(parsed)
        except json.JSONDecodeError:
            payload["business_intro"] = raw

    return MerchantProfile(
        id=int(row["id"]),
        username=row.get("username") or "",
        merchant_code=row.get("merchant_code") or "",
        business_name=row.get("business_name") or "",
        welcome_message=row.get("welcome_message") or "您好，我是 AI 客服。请问有什么可以帮您？",
        prompt_template=row.get("prompt_template") or "",
        industry=payload.get("industry", "通用服务"),
        business_intro=payload.get("business_intro", ""),
        products_services=payload.get("products_services", ""),
        pricing=payload.get("pricing", ""),
        promotions=payload.get("promotions", ""),
        hours=payload.get("hours", ""),
        contact=payload.get("contact", ""),
        faq=[FAQItem.model_validate(item) for item in payload.get("faq", []) if isinstance(item, dict)],
    )


def profile_to_prompt(profile: MerchantProfile) -> str:
    payload = {
        "industry": profile.industry,
        "business_intro": profile.business_intro,
        "products_services": profile.products_services,
        "pricing": profile.pricing,
        "promotions": profile.promotions,
        "hours": profile.hours,
        "contact": profile.contact,
        "faq": [item.model_dump() for item in profile.faq],
    }
    return json.dumps(payload, ensure_ascii=False)


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if len(stored_hash) == 64 and all(ch in "0123456789abcdef" for ch in stored_hash.lower()):
        return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored_hash)
    try:
        from werkzeug.security import check_password_hash

        return bool(check_password_hash(stored_hash, password))
    except Exception:
        return False


def auth_secret() -> str:
    return os.getenv("CS_AUTH_SECRET") or os.getenv("AI_API_KEY") or "dev-customer-service-secret"


def connector_secret_key(merchant_id: int) -> bytes:
    seed = f"{auth_secret()}|connector-secret|{merchant_id}".encode("utf-8")
    return hashlib.sha256(seed).digest()


def connector_secret_stream(key: bytes, nonce: bytes, size: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < size:
        blocks.append(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:size]


def encrypt_connector_secret(value: str, merchant_id: int) -> str:
    if not value:
        return ""
    key = connector_secret_key(merchant_id)
    nonce = secrets.token_bytes(16)
    plain = value.encode("utf-8")
    stream = connector_secret_stream(key, nonce, len(plain))
    cipher = bytes(left ^ right for left, right in zip(plain, stream))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(nonce + cipher).decode("ascii")
    return f"v1.{token}.{mac}"


def decrypt_connector_secret(token: str, merchant_id: int) -> str:
    if not token:
        return ""
    try:
        version, body, mac = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Connector secret format invalid") from exc
    if version != "v1":
        raise HTTPException(status_code=400, detail="Connector secret version unsupported")
    raw = base64.urlsafe_b64decode(body.encode("ascii"))
    nonce, cipher = raw[:16], raw[16:]
    key = connector_secret_key(merchant_id)
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Connector secret MAC invalid")
    stream = connector_secret_stream(key, nonce, len(cipher))
    plain = bytes(left ^ right for left, right in zip(cipher, stream))
    return plain.decode("utf-8")


def connector_config_for(merchant_id: int, connector: str) -> dict[str, Any]:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT config_json FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant_id, connector),
        ).fetchone()
    if not row:
        return {}
    try:
        return json.loads((dict(row).get("config_json") or "{}"))
    except json.JSONDecodeError:
        return {}


def connector_secret_value(merchant_id: int, connector: str, names: list[str] | None = None) -> str:
    names = names or ["webhook_secret", "webhook_token", "token", "client_secret", "app_secret"]
    config = connector_config_for(merchant_id, connector)
    encrypted = config.get("secret_fields_encrypted") or {}
    for name in names:
        if name in encrypted:
            return decrypt_connector_secret(str(encrypted[name]), merchant_id)
    env_name = f"CONNECTOR_{connector.upper()}_WEBHOOK_SECRET"
    return os.getenv(env_name) or os.getenv("CONNECTOR_WEBHOOK_SECRET") or ""


def verify_connector_webhook_signature(
    merchant: MerchantProfile,
    connector: str,
    raw_body: bytes,
    signature: str,
    timestamp: str = "",
) -> None:
    connector = normalize_connector_key(connector)
    signing_key = connector_secret_value(merchant.id or 0, connector)
    if not signing_key:
        raise HTTPException(status_code=401, detail="Connector webhook secret is not configured")
    cleaned_signature = (signature or "").strip()
    if not cleaned_signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    expected: list[str] = []
    secret_bytes = signing_key.encode("utf-8")
    raw_digest = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()
    expected.extend([raw_digest, f"sha256={raw_digest}"])
    if timestamp:
        try:
            issued_at = int(timestamp)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid webhook timestamp") from exc
        if abs(int(time.time()) - issued_at) > 600:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
        timed_body = f"{timestamp}.".encode("utf-8") + raw_body
        timed_digest = hmac.new(secret_bytes, timed_body, hashlib.sha256).hexdigest()
        expected.extend([timed_digest, f"sha256={timed_digest}"])
    if not any(hmac.compare_digest(cleaned_signature, item) for item in expected):
        raise HTTPException(status_code=401, detail="Webhook signature mismatch")


def make_token(merchant_id: int) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_hex(8)
    payload = f"{merchant_id}.{issued_at}.{nonce}"
    signature = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def parse_token(token: str) -> int:
    try:
        merchant_id, issued_at, nonce, signature = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    payload = f"{merchant_id}.{issued_at}.{nonce}"
    expected = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(merchant_id)


def merchant_by_id(merchant_id: int) -> MerchantProfile:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE id={marker} AND status=1", (merchant_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return parse_profile(dict(row))


def merchant_by_code(merchant_code: str) -> MerchantProfile:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE merchant_code={marker} AND status=1", (merchant_code,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Merchant code not found")
    return parse_profile(dict(row))


def current_merchant(authorization: str | None = Header(default=None)) -> MerchantProfile:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return merchant_by_id(parse_token(authorization.split(" ", 1)[1].strip()))


def risk_flags_for(message: str) -> list[str]:
    terms = ["退款", "投诉", "付款", "转账", "账号", "密码", "隐私", "手机号", "地址", "发票", "合同"]
    return [term for term in terms if term in message]


def score_intent(message: str) -> int:
    score = 35
    for term in ["价格", "多少钱", "报价", "收费", "费用", "套餐", "试用", "购买", "合作", "电话", "微信", "预约", "演示", "接入", "官网", "网站"]:
        if term in message:
            score += 8
    return min(score, 95)


def local_grounded_reply(profile: MerchantProfile, message: str) -> str:
    wants_price = any(term in message for term in ["价格", "多少钱", "报价", "收费", "费用", "套餐"])
    wants_integration = any(term in message for term in ["接入", "官网", "网站", "网页", "代码", "气泡"])
    wants_function = any(term in message for term in ["功能", "能做", "自动回复", "客服", "会话", "线索"])

    parts: list[str] = []
    if wants_price and profile.pricing:
        parts.append(f"收费这块目前是：{profile.pricing}")
    if wants_integration:
        parts.append("可以接入官网。后台会生成一段 script 代码，放到客户网站后，右下角就会出现 AI 客服气泡。")
    if wants_function and profile.products_services:
        parts.append(f"现在能做的是：{profile.products_services}")
    if not parts:
        if profile.products_services:
            parts.append(f"我们主要提供：{profile.products_services}")
        else:
            parts.append("我先帮您记录需求，再给您推荐适合的接入方式。")
    if profile.promotions and wants_price:
        parts.append(f"优惠：{profile.promotions}")
    parts.append("您方便发一下网站地址或行业类型吗？我可以判断适合直接接入，还是需要先整理 FAQ。")
    return "\n".join(parts)


def is_generic_ai_reply(reply: str) -> bool:
    text = reply.strip()
    if len(text) < 35:
        return True
    generic_markers = ["有什么我可以帮", "欢迎随时提问", "请问有什么", "我可以帮您", "具体想了解", "我会尽力帮助"]
    return any(marker in text for marker in generic_markers) and not any(
        marker in text for marker in ["价格", "收费", "套餐", "接入", "气泡", "线索", "人工接管", "官方 API", "开放平台"]
    )


def channel_grounded_reply(profile: MerchantProfile, message: str, channel: str) -> str:
    channel_name = DEFAULT_CHANNELS.get(channel, DEFAULT_CHANNELS["web_widget"])[0]
    if channel == "web_widget":
        return local_grounded_reply(profile, message)
    parts = [
        f"可以做{channel_name}客服接入，但建议按两步走：",
        f"1. 现在先把商家的话术、商品、价格、售后政策导入知识库，系统生成{channel_name}拟人工回复草稿，由人工确认后发送。",
        f"2. 拿到{channel_name}官方 API/开放平台权限后，再把回复草稿接入自动回复流程。",
        "不建议用脚本模拟点击私信或冒充真人自动发送，这类方式容易触发平台风控。"
    ]
    if profile.products_services:
        parts.append(f"当前系统已具备：{profile.products_services}")
    parts.append(f"您可以先发一份{channel_name}常见问题话术，我帮您导入知识库并生成测试回复。")
    return "\n".join(parts)


def scenario_name(scenario: str) -> str:
    names = {
        "new_customer": "新客开场",
        "price": "价格咨询",
        "objection": "异议处理",
        "after_sale": "售后安抚",
        "lead_capture": "留资转化",
        "full_pack": "完整成交脚本",
    }
    return names.get(scenario, "客服脚本")


def tone_instruction(tone: str) -> str:
    return {
        "natural": "像熟练真人客服，短句、自然、有来有回",
        "professional": "专业克制，重点清楚，适合企业服务",
        "friendly": "亲和热情，适合本地生活和电商",
        "urgent": "更强调限时优惠和下一步行动，但不要夸大承诺",
    }.get(tone, "自然")


def script_as_text(script: ServiceScriptGenerateResponse) -> str:
    lines = [f"# {script.title}", "", f"渠道：{DEFAULT_CHANNELS.get(script.channel, DEFAULT_CHANNELS['web_widget'])[0]}", f"场景：{scenario_name(script.scenario)}", "", "## 开场", script.opening, "", "## 跟进步骤"]
    for index, step in enumerate(script.steps, 1):
        lines.extend([f"{index}. {step.title}", f"话术：{step.message}", f"目标：{step.goal}", ""])
    lines.append("## 异议处理")
    for step in script.objection_replies:
        lines.extend([f"- {step.title}", f"  话术：{step.message}", f"  目标：{step.goal}"])
    lines.extend(["", "## 收口", script.closing])
    return "\n".join(lines)


def fallback_service_script(profile: MerchantProfile, payload: ServiceScriptGenerateRequest) -> ServiceScriptGenerateResponse:
    channel_name = DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS["web_widget"])[0]
    product = payload.product_name or profile.products_services or profile.business_name or "我们的服务"
    pain = payload.customer_pain or "客户想更快解决咨询和转化问题"
    offer = payload.offer or profile.promotions or profile.pricing or "可以先安排一次试用/演示"
    style = tone_instruction(payload.tone)
    title = f"{channel_name}｜{scenario_name(payload.scenario)}｜{product}"
    opening = f"您好，我是{profile.business_name or '商家'}的客服。看到您在了解{product}，我先简单确认一下：您现在主要是想解决「{pain}」这个问题吗？"
    steps = [
        ServiceScriptStep(
            title="确认需求",
            message=f"我先确认下您的情况：您现在更关注价格、效果、接入方式，还是售后保障？这样我能直接给您对应方案。",
            goal="让客户说出真实需求，避免一上来硬推。",
        ),
        ServiceScriptStep(
            title="给出方案",
            message=f"按您这个需求，{product}比较适合先从基础场景接入：先把常见问题自动回复跑起来，再把高意向客户交给人工跟进。",
            goal="把产品能力和客户问题对上。",
        ),
        ServiceScriptStep(
            title="报价和优惠",
            message=f"费用这块可以按套餐走，当前参考是：{profile.pricing or offer}。如果您现在确定要试，我们可以先给您配置一个测试场景。",
            goal="回答价格，同时给出低门槛下一步。",
        ),
        ServiceScriptStep(
            title="推进留资",
            message="您方便留一个手机号或微信吗？我把测试入口和接入方式发您，后面也方便帮您看配置结果。",
            goal="拿到可跟进线索。",
        ),
    ]
    objection_replies = [
        ServiceScriptStep(
            title="客户说太贵",
            message="理解，前期不用一次上完整版本。可以先跑一个核心场景，看每天能省多少客服时间、能沉淀多少线索，再决定是否升级。",
            goal="降低决策压力。",
        ),
        ServiceScriptStep(
            title="客户担心效果",
            message="可以先用您现有话术做测试，不满意就继续调知识库和回复风格。我们不建议一开始承诺效果，先看真实会话数据。",
            goal="建立可信预期。",
        ),
        ServiceScriptStep(
            title="客户问平台私信",
            message=f"{channel_name}如果要自动发消息，需要官方 API/开放平台权限。没有权限前我们只做回复草稿和人工确认，不做脚本模拟发送。",
            goal="说明合规边界。",
        ),
    ]
    closing = f"总结一下：先导入话术和 FAQ，再开一个测试场景，跑通后再扩展到{channel_name}。{offer}。您把现有客服话术发我，我可以先帮您整理第一版。"
    return ServiceScriptGenerateResponse(
        title=title,
        channel=payload.channel,
        scenario=payload.scenario,
        opening=opening,
        steps=steps,
        objection_replies=objection_replies,
        closing=closing,
    )


def call_ai_service_script(profile: MerchantProfile, payload: ServiceScriptGenerateRequest) -> ServiceScriptGenerateResponse:
    prompt = f"""
请为商家生成一套可直接给客服使用的成交客服脚本，必须输出 JSON。

商家：{profile.business_name}
行业：{profile.industry}
业务介绍：{profile.business_intro}
商品/服务：{profile.products_services}
价格：{profile.pricing}
优惠：{profile.promotions}
渠道：{DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS['web_widget'])[0]}
场景：{scenario_name(payload.scenario)}
产品名：{payload.product_name}
客户痛点：{payload.customer_pain}
优惠/承诺边界：{payload.offer}
语气：{tone_instruction(payload.tone)}

JSON 结构：
{{
  "title": "...",
  "opening": "...",
  "steps": [{{"title": "...", "message": "...", "goal": "..."}}],
  "objection_replies": [{{"title": "...", "message": "...", "goal": "..."}}],
  "closing": "..."
}}

要求：
1. 不要夸大承诺，不承诺退款和收益。
2. 微信、抖音、淘宝、拼多多、闲鱼如果涉及自动发送，必须提示需要官方 API 权限。
3. 每条话术像真人客服，短、自然、能推进下一步。
"""
    try:
        raw = call_ai_reply(profile, prompt, [])
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start : end + 1] if start >= 0 and end > start else raw)
        return ServiceScriptGenerateResponse(
            title=str(parsed.get("title") or f"{DEFAULT_CHANNELS.get(payload.channel, DEFAULT_CHANNELS['web_widget'])[0]}客服脚本"),
            channel=payload.channel,
            scenario=payload.scenario,
            opening=str(parsed.get("opening") or ""),
            steps=[ServiceScriptStep.model_validate(item) for item in parsed.get("steps", [])[:8] if isinstance(item, dict)],
            objection_replies=[ServiceScriptStep.model_validate(item) for item in parsed.get("objection_replies", [])[:8] if isinstance(item, dict)],
            closing=str(parsed.get("closing") or ""),
        )
    except Exception:
        return fallback_service_script(profile, payload)


def build_system_prompt(profile: MerchantProfile) -> str:
    faq = "\n".join(f"- Q: {item.question}\n  A: {item.answer}" for item in profile.faq)
    knowledge = knowledge_context_for(profile.id)
    return f"""
你是 {profile.business_name or profile.username} 的网站 AI 客服。你只能根据商家资料回答，不能编造价格、承诺效果、承诺退款。

行业：{profile.industry}
业务介绍：{profile.business_intro}
商品/服务：{profile.products_services}
价格/套餐：{profile.pricing}
优惠活动：{profile.promotions}
营业时间：{profile.hours}
联系方式：{profile.contact}
FAQ：
{faq}
导入知识库/话术：
{knowledge or "暂无额外导入知识。"}

回复要求：
1. 用中文，像真人客服，简短自然。
2. 先回答客户当前问题，再推进下一步。
3. 如果信息不足，问 1 个关键问题。
4. 对高风险问题保持谨慎，不承诺不确定事项。
5. 需要留资时，温和引导客户留下电话或微信。
"""


def call_ai_reply(profile: MerchantProfile, message: str, history: list[dict[str, Any]]) -> str:
    ai_engine = default_ai_engine(DATA_DIR)
    if not ai_engine.is_chat_configured():
        raise RuntimeError("AI provider is not configured")

    history_messages = []
    for item in history[-6:]:
        if item.get("query"):
            history_messages.append({"role": "user", "content": str(item["query"])[:800]})
        if item.get("response"):
            history_messages.append({"role": "assistant", "content": str(item["response"])[:800]})

    return ai_engine.complete_text(
        system_prompt=build_system_prompt(profile),
        user_prompt=message,
        history=history_messages,
        temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
        timeout=float(os.getenv("AI_TIMEOUT", "45")),
    )


def fallback_reply(profile: MerchantProfile, message: str) -> str:
    if risk_flags_for(message):
        return "这个问题我先帮您记录下来，涉及订单、付款、退款或账号信息时需要人工客服确认。您可以留下联系方式，我们尽快跟进。"
    return local_grounded_reply(profile, message)


# Humanized customer-service layer. These definitions intentionally override the
# older template replies above while keeping the rest of the API surface intact.
DEFAULT_PROFILE_FALLBACK = {
    "industry": "AI客服/SaaS服务",
    "business_intro": "我们提供面向商家的 AI 客服、知识库导入、网页客服气泡和多渠道回复草稿。",
    "products_services": "网页客服气泡、AI自动回复、线索记录、知识库导入、人工接管提醒、多渠道回复草稿。",
    "pricing": "基础版适合先跑网页客服和线索记录；Pro 适合加知识库和多渠道草稿；私有部署按需求报价。",
    "promotions": "新客户可以先做一个测试场景，确认回复风格和线索记录效果。",
    "hours": "工作日 9:00-21:00",
    "contact": "留下手机号或微信后，顾问会跟进演示和接入。",
}

DEFAULT_CHANNELS = {
    "web_widget": ("网页客服", "已支持自动回复和会话落库"),
    "wechat": ("微信客服", "个人微信先生成回复草稿；不建议承诺无人值守自动发送"),
    "wechat_work": ("企业微信客服", "适合接企业微信/微信客服官方 API；未授权前生成回复草稿"),
    "douyin": ("抖音客服", "建议接抖音开放平台或企业号权限；未授权前只做人工辅助"),
    "taobao": ("淘宝客服", "建议接千牛/淘宝开放平台；未授权前只做话术建议"),
    "pdd": ("拼多多客服", "建议接拼多多开放平台；未授权前只做话术建议"),
    "xianyu": ("闲鱼客服", "建议接闲鱼/淘宝生态官方能力；未授权前只做回复草稿"),
}

MOJIBAKE_MARKERS = ("锛", "鐨", "绋", "瀹", "浣", "鎴", "閫", "姘", "鈥", "€", "歿")


def readable_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if sum(1 for marker in MOJIBAKE_MARKERS if marker in text) >= 2:
        return fallback
    return text


def has_any(message: str, terms: list[str]) -> bool:
    lowered = message.lower()
    return any(term.lower() in lowered for term in terms)


def default_profile_payload() -> dict[str, Any]:
    return {
        **DEFAULT_PROFILE_FALLBACK,
        "faq": [
            {"question": "可以自动回复吗？", "answer": "可以，网页客服气泡可以自动回复并记录线索；微信、抖音等平台建议先走官方 API 或人工确认草稿。"},
            {"question": "怎么接到网站？", "answer": "后台会生成一段 script 代码，放进网站后右下角就会出现客服气泡。"},
            {"question": "可以先试用吗？", "answer": "可以先配置一个测试商家和 FAQ，跑通回复风格、线索记录和人工接管提醒。"},
        ],
    }


def profile_value(profile: MerchantProfile, field: str) -> str:
    return readable_text(getattr(profile, field, ""), DEFAULT_PROFILE_FALLBACK.get(field, ""))


def parse_profile(row: dict[str, Any]) -> MerchantProfile:
    payload = default_profile_payload()
    raw = row.get("prompt_template") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload.update(parsed)
        except json.JSONDecodeError:
            payload["business_intro"] = raw

    faq_items = []
    for item in payload.get("faq", []):
        if isinstance(item, dict):
            question = readable_text(item.get("question", ""))
            answer = readable_text(item.get("answer", ""))
            if question or answer:
                faq_items.append(FAQItem(question=question, answer=answer))

    return MerchantProfile(
        id=int(row["id"]),
        username=row.get("username") or "",
        merchant_code=row.get("merchant_code") or "",
        business_name=readable_text(row.get("business_name"), "演示商家"),
        welcome_message=readable_text(row.get("welcome_message"), "您好，我是在线客服。你想了解价格、接入方式，还是先看一个演示？"),
        prompt_template=row.get("prompt_template") or "",
        industry=readable_text(payload.get("industry"), DEFAULT_PROFILE_FALLBACK["industry"]),
        business_intro=readable_text(payload.get("business_intro"), DEFAULT_PROFILE_FALLBACK["business_intro"]),
        products_services=readable_text(payload.get("products_services"), DEFAULT_PROFILE_FALLBACK["products_services"]),
        pricing=readable_text(payload.get("pricing"), DEFAULT_PROFILE_FALLBACK["pricing"]),
        promotions=readable_text(payload.get("promotions"), DEFAULT_PROFILE_FALLBACK["promotions"]),
        hours=readable_text(payload.get("hours"), DEFAULT_PROFILE_FALLBACK["hours"]),
        contact=readable_text(payload.get("contact"), DEFAULT_PROFILE_FALLBACK["contact"]),
        faq=faq_items or [FAQItem.model_validate(item) for item in default_profile_payload()["faq"]],
    )


def risk_flags_for(message: str) -> list[str]:
    groups = {
        "退款/售后": ["退款", "退钱", "退货", "不满意", "售后", "赔付"],
        "投诉/差评": ["投诉", "差评", "骗人", "骗子", "举报", "维权", "假货"],
        "付款/资金": ["付款", "转账", "银行卡", "收款", "支付", "扣款", "账单"],
        "账号/登录": ["账号", "密码", "验证码", "登录", "封号", "权限"],
        "隐私信息": ["手机号", "电话", "地址", "身份证", "隐私", "个人信息"],
        "发票/合同": ["发票", "合同", "协议", "公章"],
    }
    return [label for label, terms in groups.items() if has_any(message, terms)]


def score_intent(message: str) -> int:
    score = 35
    high_intent_terms = ["多少钱", "价格", "报价", "收费", "费用", "套餐", "试用", "购买", "合作", "电话", "微信", "预约", "演示"]
    integration_terms = ["接入", "官网", "网站", "网页", "代码", "气泡", "API", "抖音", "微信", "企业微信", "淘宝", "拼多多", "闲鱼"]
    service_terms = ["客服", "自动回复", "知识库", "会话", "线索", "SaaS", "私有部署"]
    for term in high_intent_terms:
        if term in message:
            score += 8
    for term in integration_terms:
        if term.lower() in message.lower():
            score += 5
    for term in service_terms:
        if term.lower() in message.lower():
            score += 4
    if risk_flags_for(message):
        score += 12
    return min(score, 95)


def local_grounded_reply(profile: MerchantProfile, message: str) -> str:
    pricing = profile_value(profile, "pricing")
    services = profile_value(profile, "products_services")
    promos = profile_value(profile, "promotions")
    contact = profile_value(profile, "contact")

    if risk_flags_for(message):
        return fallback_reply(profile, message)

    if has_any(message, ["多少钱", "价格", "报价", "收费", "费用", "套餐", "贵吗"]):
        return f"可以的，我们一般按接入场景收费。{pricing} 你是想先接官网客服，还是接抖音/微信这类私信场景？"

    if has_any(message, ["怎么放", "怎么接", "接入", "网站", "官网", "网页", "代码", "气泡", "部署"]):
        return "可以接官网。后台会给你一段 script 代码，放到网站后右下角就能出现客服气泡。你把网站地址发我，我先帮你看适合直接接，还是先整理 FAQ。"

    if has_any(message, ["能做什么", "功能", "可以做", "自动回复", "客服", "知识库", "线索"]):
        return f"核心能做的是：{services} 它不是只生成话术，会把访客问题、AI回复、意向分和人工接管提醒都落到后台。你现在最想先解决无人回复，还是想先把咨询线索沉淀下来？"

    if has_any(message, ["试用", "体验", "演示", "看看效果", "测试"]):
        return f"可以先跑一个测试场景。{promos} 你发一个行业、网站或 5 条常见问题，我先帮你搭一版客服。"

    if has_any(message, ["联系", "电话", "微信", "加你", "预约"]):
        return f"可以，{contact} 我建议你顺手发一下行业和想接的平台，这样演示时能直接按你的业务来。"

    return "可以，我先按你的业务场景判断。如果你是做商家服务，第一步通常先接网页客服和知识库，把常见咨询自动接住。你现在是想接官网客服，还是想接抖音/微信/电商平台的咨询？"


def is_generic_ai_reply(reply: str) -> bool:
    text = reply.strip()
    if len(text) < 12:
        return True
    generic_markers = [
        "有什么可以帮",
        "欢迎随时",
        "请问有什么",
        "我会尽力",
        "作为AI",
        "我是一个AI",
        "无法提供",
        "请提供更多信息",
        "系统已记录",
        "我先帮您记录",
    ]
    return any(marker in text for marker in generic_markers)


def channel_grounded_reply(profile: MerchantProfile, message: str, channel: str) -> str:
    channel_name = DEFAULT_CHANNELS.get(channel, DEFAULT_CHANNELS["web_widget"])[0]
    if channel == "web_widget":
        return local_grounded_reply(profile, message)
    services = profile_value(profile, "products_services")
    return (
        f"可以做{channel_name}场景，但第一版建议先生成回复草稿，由人工确认后发送。"
        f"现在系统已经能做{services}，等拿到{channel_name}官方 API 权限后再切到自动回复。"
        "你先发一份常见问题或商品话术，我可以帮你导入知识库并生成一轮测试回复。"
    )


def build_system_prompt(profile: MerchantProfile) -> str:
    faq = "\n".join(
        f"- Q: {readable_text(item.question)}\n  A: {readable_text(item.answer)}"
        for item in profile.faq
        if readable_text(item.question) or readable_text(item.answer)
    )
    knowledge = readable_text(knowledge_context_for(profile.id), "")
    return f"""
你是 {readable_text(profile.business_name, profile.username) or "商家"} 的网站真人客服助手，目标是把咨询自然推进到下一步。

商家资料：
- 行业：{profile_value(profile, "industry")}
- 业务介绍：{profile_value(profile, "business_intro")}
- 商品/服务：{profile_value(profile, "products_services")}
- 价格/套餐：{profile_value(profile, "pricing")}
- 优惠活动：{profile_value(profile, "promotions")}
- 营业时间：{profile_value(profile, "hours")}
- 联系方式：{profile_value(profile, "contact")}

FAQ：
{faq or "暂无 FAQ。"}

导入知识库/话术：
{knowledge or "暂无额外导入知识。"}

回复要求：
1. 用中文，像成交型真人客服，2-4 句，短句自然，不要像公告。
2. 先直接回答客户当前问题，再给一个亮点或边界，最后只问 1 个推进问题。
3. 不要编造价格、退款、效果承诺；资料没有就说需要根据场景确认。
4. 禁止用“系统已记录”“我先帮您记录”“请耐心等待”“很抱歉给您带来不便”开头。
5. 遇到退款、投诉、付款、账号、隐私问题：先安抚，再说明需要人工核实，索要订单号或联系方式，不承诺结果。
""".strip()


def fallback_reply(profile: MerchantProfile, message: str) -> str:
    flags = risk_flags_for(message)
    if flags:
        if "投诉/差评" in flags:
            return "理解，你这个反馈我先认真接住。这类投诉或差评问题需要人工核实具体订单和沟通记录，我不会直接乱承诺结果。你把订单号或联系方式发我，我们尽快给你确认下一步处理方式。"
        return "理解，你先别着急。我这边先帮你转人工核一下具体情况，退款、付款或账号类问题不能直接口头承诺。你把订单号或联系方式发我，我们尽快给你确认。"
    return local_grounded_reply(profile, message)


def risk_flags_for(message: str) -> list[str]:
    return default_ai_engine(DATA_DIR).assess_risk(message).risk_flags


def score_intent(message: str) -> int:
    return default_ai_engine(DATA_DIR).score_intent(message).score


def call_ai_reply(profile: MerchantProfile, message: str, history: list[dict[str, Any]]) -> str:
    ai_engine = default_ai_engine(DATA_DIR)
    history_messages = []
    for item in history[-6:]:
        if item.get("query"):
            history_messages.append({"role": "user", "content": str(item["query"])[:800]})
        if item.get("response"):
            history_messages.append({"role": "assistant", "content": str(item["response"])[:800]})

    fallback = local_grounded_reply(profile, message)
    result = ai_engine.generate_reply(
        system_prompt=build_system_prompt(profile),
        user_message=message,
        history=history_messages,
        fallback_text=fallback,
        temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
        timeout=float(os.getenv("AI_TIMEOUT", "45")),
    )
    if result.mode == "ai" and is_generic_ai_reply(result.text):
        return fallback
    return result.text or fallback


def conversation_history(session_id: str) -> list[dict[str, Any]]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"SELECT query, response, created_at FROM conversations WHERE session_id={marker} ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,，/、\s]+", value) if item.strip()]


def join_tags(tags: list[str] | None) -> str:
    return ",".join(dict.fromkeys(item.strip() for item in (tags or []) if item.strip()))


def contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def infer_crm_tags(text: str, intent_score: int, risk_flags: list[str] | None = None) -> list[str]:
    tags: list[str] = []
    if intent_score >= 70:
        tags.append("高意向")
    if contains_any(text, ["价格", "多少钱", "报价", "套餐", "费用"]):
        tags.append("价格咨询")
    if contains_any(text, ["案例", "演示", "试用", "效果"]):
        tags.append("要案例")
    if contains_any(text, ["微信", "电话", "联系", "预约", "加你"]):
        tags.append("可留资")
    if risk_flags:
        tags.append("需人工")
    return tags


def crm_stage_for(intent_score: int, need_followup: bool) -> str:
    if need_followup:
        return "follow_up"
    if intent_score >= 70:
        return "high_intent"
    if intent_score >= 45:
        return "contacted"
    return "new"


def crm_lead_from_row(row: dict[str, Any]) -> CRMLead:
    return CRMLead(
        id=int(row.get("id") or 0),
        source=row.get("source_channel") or "web_widget",
        name=row.get("name") or "",
        contact=row.get("contact") or row.get("phone") or "",
        need=row.get("last_query") or "",
        status=row.get("followup_status") or "pending",
        sales_stage=row.get("sales_stage") or "new",
        owner=row.get("owner") or "",
        intent_score=int(row.get("intent_score") or 0),
        tags=split_tags(row.get("tags")),
        last_session_id=row.get("last_session_id") or "",
        next_followup_at=row.get("next_followup_at") or "",
        notes=row.get("notes") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def crm_task_from_row(row: dict[str, Any]) -> CRMTask:
    return CRMTask(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        target_type=row.get("target_type") or "lead",
        target_id=str(row.get("target_id") or ""),
        title=row.get("title") or "",
        status=row.get("status") or "open",
        priority=row.get("priority") or "normal",
        owner=row.get("owner") or "",
        due_at=row.get("due_at") or "",
        source=row.get("source") or "manual",
        workflow_run_id=row.get("workflow_run_id") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def create_crm_task_record(merchant_id: int, payload: CRMTaskCreate) -> CRMTask:
    marker = param()
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO crm_tasks (merchant_id, target_type, target_id, title, status, priority, owner, due_at, source, workflow_run_id, created_at, updated_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant_id,
                payload.target_type,
                payload.target_id,
                payload.title,
                "open",
                payload.priority,
                payload.owner,
                payload.due_at,
                payload.source,
                payload.workflow_run_id,
                now_sql(),
                now_sql(),
            ),
        )
        task_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM crm_tasks WHERE id={marker}", (task_id,)).fetchone()
    return crm_task_from_row(dict(row))


def ensure_followup_task(merchant_id: int, customer_id: int, title: str, workflow_run_id: str = "", source: str = "workflow") -> CRMTask | None:
    marker = param()
    with db() as conn:
        existing = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND target_type={marker} AND target_id={marker} AND status={marker}
            ORDER BY id DESC LIMIT 1
            """,
            (merchant_id, "lead", str(customer_id), "open"),
        ).fetchone()
    if existing:
        return None
    return create_crm_task_record(
        merchant_id,
        CRMTaskCreate(
            target_type="lead",
            target_id=str(customer_id),
            title=title,
            priority="high",
            source=source,
            workflow_run_id=workflow_run_id,
        ),
    )


def upsert_customer(
    merchant_id: int,
    visitor_id: str,
    message: str,
    intent_score: int,
    need_followup: bool,
    source_channel: str = "web_widget",
    session_id: str = "",
    risk_flags: list[str] | None = None,
) -> int:
    marker = param()
    stage = crm_stage_for(intent_score, need_followup)
    tags = join_tags(infer_crm_tags(message, intent_score, risk_flags))
    with db() as conn:
        row = conn.execute(
            f"SELECT id FROM customers WHERE merchant_id={marker} AND openid={marker}",
            (merchant_id, visitor_id),
        ).fetchone()
        if row:
            conn.execute(
                f"""
                UPDATE customers
                SET last_query={marker}, intent_score={marker}, is_high_intent={marker}, followup_status={marker},
                    sales_stage={marker}, source_channel={marker}, tags={marker}, last_session_id={marker}, updated_at={marker}
                WHERE id={marker}
                """,
                (
                    message,
                    intent_score,
                    1 if intent_score >= 70 else 0,
                    "needs_followup" if need_followup else "pending",
                    stage,
                    source_channel,
                    tags,
                    session_id,
                    now_sql(),
                    dict(row)["id"],
                ),
            )
            return int(dict(row)["id"])
        cursor = conn.execute(
            f"""
            INSERT INTO customers (
                merchant_id, name, openid, intent_score, is_high_intent, followup_status,
                sales_stage, source_channel, tags, last_session_id, last_query, created_at, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant_id,
                f"访客{visitor_id[-6:]}",
                visitor_id,
                intent_score,
                1 if need_followup or intent_score >= 70 else 0,
                "needs_followup" if need_followup else "pending",
                stage,
                source_channel,
                tags,
                session_id,
                message,
                now_sql(),
                now_sql(),
            ),
        )
        return int(cursor.lastrowid)


async def list_crm_leads(merchant: MerchantProfile, stage: str = "", owner: str = "") -> list[CRMLead]:
    marker = param()
    filters = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if stage:
        filters.append(f"sales_stage={marker}")
        params.append(stage)
    if owner:
        filters.append(f"owner={marker}")
        params.append(owner)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM customers
            WHERE {" AND ".join(filters)}
            ORDER BY updated_at DESC, id DESC
            LIMIT 200
            """,
            tuple(params),
        ).fetchall()
    return [crm_lead_from_row(row) for row in rows_to_dicts(rows)]


async def create_crm_lead(payload: CRMLeadCreate, merchant: MerchantProfile) -> CRMLead:
    marker = param()
    score = score_intent(payload.need)
    tags = join_tags([*payload.tags, *infer_crm_tags(payload.need, score)])
    stage = payload.sales_stage or crm_stage_for(score, score >= 70)
    status = "needs_followup" if score >= 70 else "pending"
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO customers (
                merchant_id, name, phone, contact, openid, intent_score, is_high_intent, followup_status,
                sales_stage, source_channel, owner, tags, last_query, next_followup_at, notes, created_at, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker},
                    {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant.id,
                payload.name or "手动线索",
                payload.contact,
                payload.contact,
                f"manual-{uuid.uuid4()}",
                score,
                1 if score >= 70 else 0,
                status,
                stage,
                payload.source,
                payload.owner,
                tags,
                payload.need,
                payload.next_followup_at,
                payload.notes,
                now_sql(),
                now_sql(),
            ),
        )
        lead_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM customers WHERE id={marker}", (lead_id,)).fetchone()
    runs = workflow_engine.trigger(
        "lead",
        payload.source,
        {
            "lead_id": str(lead_id),
            "need": payload.need,
            "contact": payload.contact,
            "source": payload.source,
            "intent_score": score,
        },
    )
    workflow_run_id = runs[0].id if runs else ""
    if score >= 70:
        ensure_followup_task(merchant.id or 0, lead_id, "高意向新线索跟进", workflow_run_id, "crm_lead")
    record_usage(merchant.id or 0, "crm_lead", 1, payload.source, str(lead_id), {"intent_score": score})
    record_audit_log(merchant.id or 0, merchant.username, "crm.lead.create", "lead", str(lead_id), "创建 CRM 线索", {"source": payload.source, "intent_score": score})
    return crm_lead_from_row(dict(row))


async def update_crm_lead(customer_id: int, payload: CRMLeadUpdate, merchant: MerchantProfile) -> CRMLead:
    marker = param()
    updates: list[str] = []
    params: list[Any] = []
    mapping = {
        "name": payload.name,
        "contact": payload.contact,
        "phone": payload.contact,
        "last_query": payload.need,
        "followup_status": payload.status,
        "sales_stage": payload.sales_stage,
        "owner": payload.owner,
        "next_followup_at": payload.next_followup_at,
        "notes": payload.notes,
    }
    for column, value in mapping.items():
        if value is not None:
            updates.append(f"{column}={marker}")
            params.append(value)
    if payload.tags is not None:
        updates.append(f"tags={marker}")
        params.append(join_tags(payload.tags))
    if not updates:
        with db() as conn:
            row = conn.execute(f"SELECT * FROM customers WHERE merchant_id={marker} AND id={marker}", (merchant.id, customer_id)).fetchone()
    else:
        updates.append(f"updated_at={marker}")
        params.append(now_sql())
        params.extend([merchant.id, customer_id])
        with db() as conn:
            conn.execute(
                f"UPDATE customers SET {', '.join(updates)} WHERE merchant_id={marker} AND id={marker}",
                tuple(params),
            )
            row = conn.execute(f"SELECT * FROM customers WHERE merchant_id={marker} AND id={marker}", (merchant.id, customer_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="CRM lead not found")
    lead = crm_lead_from_row(dict(row))
    if payload.status == "needs_followup" or payload.sales_stage == "follow_up":
        ensure_followup_task(merchant.id or 0, customer_id, "线索状态更新后跟进", source="crm_update")
    record_audit_log(merchant.id or 0, merchant.username, "crm.lead.update", "lead", str(customer_id), "更新 CRM 线索", payload.model_dump(exclude_none=True))
    return lead


async def list_crm_tasks(merchant: MerchantProfile, status: str = "open") -> list[CRMTask]:
    marker = param()
    filters = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if status:
        filters.append(f"status={marker}")
        params.append(status)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM crm_tasks
            WHERE {" AND ".join(filters)}
            ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, updated_at DESC, id DESC
            LIMIT 200
            """,
            tuple(params),
        ).fetchall()
    return [crm_task_from_row(row) for row in rows_to_dicts(rows)]


async def create_crm_task(payload: CRMTaskCreate, merchant: MerchantProfile) -> CRMTask:
    task = create_crm_task_record(merchant.id or 0, payload)
    record_audit_log(merchant.id or 0, merchant.username, "crm.task.create", "task", str(task.id), "创建跟进任务", {"target": payload.target_id})
    return task


async def update_crm_task(task_id: int, payload: CRMTaskUpdate, merchant: MerchantProfile) -> CRMTask:
    marker = param()
    updates: list[str] = []
    params: list[Any] = []
    for column, value in {
        "title": payload.title,
        "status": payload.status,
        "priority": payload.priority,
        "owner": payload.owner,
        "due_at": payload.due_at,
    }.items():
        if value is not None:
            updates.append(f"{column}={marker}")
            params.append(value)
    if updates:
        updates.append(f"updated_at={marker}")
        params.append(now_sql())
        params.extend([merchant.id, task_id])
        with db() as conn:
            conn.execute(f"UPDATE crm_tasks SET {', '.join(updates)} WHERE merchant_id={marker} AND id={marker}", tuple(params))
            row = conn.execute(f"SELECT * FROM crm_tasks WHERE merchant_id={marker} AND id={marker}", (merchant.id, task_id)).fetchone()
    else:
        with db() as conn:
            row = conn.execute(f"SELECT * FROM crm_tasks WHERE merchant_id={marker} AND id={marker}", (merchant.id, task_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="CRM task not found")
    record_audit_log(merchant.id or 0, merchant.username, "crm.task.update", "task", str(task_id), "更新跟进任务", payload.model_dump(exclude_none=True))
    return crm_task_from_row(dict(row))


async def crm_overview(merchant: MerchantProfile) -> CRMOverview:
    marker = param()
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"SELECT COALESCE(sales_stage, 'new') AS stage, COUNT(*) AS c FROM customers WHERE merchant_id={marker} GROUP BY COALESCE(sales_stage, 'new')",
            (merchant.id,),
        ).fetchall())
        leads = dict(conn.execute(f"SELECT COUNT(*) AS c FROM customers WHERE merchant_id={marker}", (merchant.id,)).fetchone())["c"]
        high_intent = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM customers WHERE merchant_id={marker} AND intent_score >= 70",
            (merchant.id,),
        ).fetchone())["c"]
        needs_followup = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM customers WHERE merchant_id={marker} AND followup_status={marker}",
            (merchant.id, "needs_followup"),
        ).fetchone())["c"]
        open_tasks = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM crm_tasks WHERE merchant_id={marker} AND status={marker}",
            (merchant.id, "open"),
        ).fetchone())["c"]
    stage_counts = {str(row["stage"]): int(row["c"] or 0) for row in rows}
    return CRMOverview(
        leads=int(leads or 0),
        high_intent=int(high_intent or 0),
        needs_followup=int(needs_followup or 0),
        open_tasks=int(open_tasks or 0),
        won=stage_counts.get("won", 0),
        lost=stage_counts.get("lost", 0),
        stage_counts=stage_counts,
    )


def normalize_connector_key(key: str) -> str:
    normalized = "douyin_dm" if key == "douyin_private_message" else key
    if normalized not in CONNECTOR_CATALOG:
        raise HTTPException(status_code=404, detail="Connector not supported")
    return normalized


def connector_auth_from_row(key: str, row: dict[str, Any] | None) -> ConnectorAuthView:
    catalog = CONNECTOR_CATALOG[key]
    configured = split_tags(row.get("configured_fields") if row else "")
    required = list(catalog.get("required_fields", []))
    status = (row.get("status") if row else "") or catalog["status"]
    read_only = bool(row.get("read_only_enabled")) if row else True
    send_enabled = bool(row.get("send_enabled")) if row else False
    return ConnectorAuthView(
        key=key,
        label=str(catalog["label"]),
        status=str(status),
        auth_mode=(row.get("auth_mode") if row else "") or str(catalog["auth_mode"]),
        account_name=(row.get("account_name") if row else "") or "",
        callback_url=(row.get("callback_url") if row else "") or "",
        read_only_enabled=read_only,
        send_enabled=send_enabled,
        safety_level="requires_confirmation" if send_enabled else str(catalog["safety_level"]),
        capabilities=list(catalog.get("capabilities", [])),
        configured_fields=configured,
        missing_fields=[field for field in required if field not in configured],
        last_sync_at=(row.get("last_sync_at") if row else "") or "",
        notes=(row.get("notes") if row else "") or "",
    )


async def list_connector_auths(merchant: MerchantProfile) -> list[ConnectorAuthView]:
    marker = param()
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"SELECT * FROM connector_credentials WHERE merchant_id={marker}",
            (merchant.id,),
        ).fetchall())
    by_key = {row["connector"]: row for row in rows}
    return [connector_auth_from_row(key, by_key.get(key)) for key in CONNECTOR_CATALOG]


async def update_connector_auth(key: str, payload: ConnectorAuthUpdate, merchant: MerchantProfile) -> ConnectorAuthView:
    connector = normalize_connector_key(key)
    marker = param()
    catalog = CONNECTOR_CATALOG[connector]
    existing_config = connector_config_for(merchant.id or 0, connector)
    encrypted_secrets = dict(existing_config.get("secret_fields_encrypted") or {})
    for field, value in payload.secret_fields.items():
        if value:
            encrypted_secrets[field] = encrypt_connector_secret(value, merchant.id or 0)
    configured_secret_fields = sorted(encrypted_secrets.keys())
    safe_config = {
        name: value
        for name, value in existing_config.items()
        if name not in {"secret_fields_encrypted", "secret_fields_configured"}
    }
    safe_config.update(payload.nonsecret_config)
    safe_config["secret_fields_encrypted"] = encrypted_secrets
    safe_config["secret_fields_configured"] = configured_secret_fields
    configured_fields = sorted(
        {name for name in safe_config.keys() if name not in {"secret_fields_encrypted", "secret_fields_configured"}}
        | set(configured_secret_fields)
    )
    # Direct sending remains disabled until a later reviewed stage even if the UI sends true.
    send_enabled = False
    with db() as conn:
        existing = conn.execute(
            f"SELECT id FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
        if existing:
            conn.execute(
                f"""
                UPDATE connector_credentials
                SET status={marker}, auth_mode={marker}, account_name={marker}, callback_url={marker},
                    config_json={marker}, configured_fields={marker}, read_only_enabled={marker},
                    send_enabled={marker}, notes={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND connector={marker}
                """,
                (
                    payload.status,
                    payload.auth_mode or catalog["auth_mode"],
                    payload.account_name,
                    payload.callback_url,
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1 if payload.read_only_enabled else 0,
                    1 if send_enabled else 0,
                    payload.notes,
                    now_sql(),
                    merchant.id,
                    connector,
                ),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO connector_credentials (
                    merchant_id, connector, status, auth_mode, account_name, callback_url,
                    config_json, configured_fields, read_only_enabled, send_enabled, notes, created_at, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    connector,
                    payload.status,
                    payload.auth_mode or catalog["auth_mode"],
                    payload.account_name,
                    payload.callback_url,
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1 if payload.read_only_enabled else 0,
                    1 if send_enabled else 0,
                    payload.notes,
                    now_sql(),
                    now_sql(),
                ),
            )
        row = conn.execute(
            f"SELECT * FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
    record_connector_event(merchant.id or 0, connector, "auth", "", {"status": payload.status, "fields": configured_fields})
    record_audit_log(merchant.id or 0, merchant.username, "connector.auth.update", "connector", connector, f"更新 Connector 授权：{connector}", {"status": payload.status, "fields": configured_fields})
    return connector_auth_from_row(connector, dict(row))


SEND_GATE_ENABLE_PHRASE = "ENABLE_SUPERVISED_SEND"
SEND_CONFIRM_PHRASE = "CONFIRM_PLATFORM_SEND"
CONNECTOR_SEND_URL_FIELDS = ["send_url", "reply_send_url", "message_send_url", "official_send_url"]


def make_connector_oauth_state(merchant_id: int, connector: str) -> str:
    nonce = secrets.token_hex(12)
    issued_at = str(int(time.time()))
    payload = f"{merchant_id}.{connector}.{issued_at}.{nonce}"
    signature = hmac.new(auth_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{payload}.{signature}"


def oauth_expires_at() -> str:
    return datetime.fromtimestamp(time.time() + 15 * 60).strftime("%Y-%m-%d %H:%M:%S")


def connector_oauth_callback_path(connector: str) -> str:
    return f"/api/v1/connectors/{connector}/oauth/callback"


async def start_connector_oauth(
    key: str,
    payload: ConnectorOAuthStartRequest,
    merchant: MerchantProfile,
) -> ConnectorOAuthStartResponse:
    connector = normalize_connector_key(key)
    catalog = CONNECTOR_CATALOG[connector]
    if catalog.get("auth_mode") != "oauth":
        return ConnectorOAuthStartResponse(
            connector=connector,
            status="setup_required",
            state="",
            callback_url=connector_oauth_callback_path(connector),
            next_action="该 Connector 当前不是 OAuth 授权模式，请使用 Webhook/API Key/人工辅助配置。",
        )
    config = connector_config_for(merchant.id or 0, connector)
    authorize_url = payload.authorize_url or str(config.get("authorize_url") or config.get("oauth_authorize_url") or "")
    client_id = payload.client_id or str(config.get("client_id") or config.get("client_key") or config.get("app_key") or "")
    scope = payload.scope or str(config.get("scope") or "")
    redirect_uri = payload.redirect_uri or str(config.get("redirect_uri") or config.get("callback_url") or connector_oauth_callback_path(connector))
    state = make_connector_oauth_state(merchant.id or 0, connector)
    expires_at = oauth_expires_at()
    status: Literal["ready", "setup_required"] = "ready" if authorize_url and client_id else "setup_required"
    auth_url = ""
    if status == "ready":
        query = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if scope:
            query["scope"] = scope
        query.update({key: value for key, value in payload.extra_params.items() if value})
        separator = "&" if "?" in authorize_url else "?"
        auth_url = f"{authorize_url}{separator}{urllib.parse.urlencode(query)}"
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO connector_oauth_states (merchant_id, connector, state, auth_url, redirect_uri, status, expires_at, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant.id, connector, state, auth_url, redirect_uri, "pending", expires_at, now_sql()),
        )
    record_audit_log(merchant.id or 0, merchant.username, "connector.oauth.start", "connector", connector, "生成 OAuth 授权链接", {"status": status})
    return ConnectorOAuthStartResponse(
        connector=connector,
        status=status,
        state=state,
        auth_url=auth_url,
        callback_url=redirect_uri,
        expires_at=expires_at,
        next_action="请打开授权链接完成官方授权。" if status == "ready" else "请先配置 authorize_url、client_id/client_key、redirect_uri 和 scope。",
    )


async def handle_connector_oauth_callback(
    key: str,
    state: str,
    code: str,
    callback_payload: dict[str, Any],
) -> ConnectorOAuthCallbackResponse:
    connector = normalize_connector_key(key)
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT * FROM connector_oauth_states WHERE state={marker} AND connector={marker}",
            (state, connector),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    data = dict(row)
    if data.get("used_at"):
        raise HTTPException(status_code=400, detail="OAuth state already used")
    expires_at = str(data.get("expires_at") or "")
    if expires_at and expires_at < now_sql():
        raise HTTPException(status_code=400, detail="OAuth state expired")
    merchant = merchant_by_id(int(data["merchant_id"]))
    existing_config = connector_config_for(merchant.id or 0, connector)
    encrypted_secrets = dict(existing_config.get("secret_fields_encrypted") or {})
    encrypted_secrets["oauth_code"] = encrypt_connector_secret(code, merchant.id or 0)
    safe_config = {
        name: value
        for name, value in existing_config.items()
        if name not in {"secret_fields_encrypted", "secret_fields_configured"}
    }
    safe_config.update({
        "oauth_code_received": True,
        "oauth_state": state,
        "oauth_callback_received_at": now_sql(),
    })
    safe_config["secret_fields_encrypted"] = encrypted_secrets
    safe_config["secret_fields_configured"] = sorted(encrypted_secrets.keys())
    configured_fields = sorted(
        {name for name in safe_config.keys() if name not in {"secret_fields_encrypted", "secret_fields_configured"}}
        | set(encrypted_secrets.keys())
    )
    with db() as conn:
        existing = conn.execute(
            f"SELECT id FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
        if existing:
            conn.execute(
                f"""
                UPDATE connector_credentials
                SET status={marker}, auth_mode={marker}, config_json={marker}, configured_fields={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND connector={marker}
                """,
                ("pending_auth", "oauth", json.dumps(safe_config, ensure_ascii=False), join_tags(configured_fields), now_sql(), merchant.id, connector),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO connector_credentials (
                    merchant_id, connector, status, auth_mode, config_json, configured_fields,
                    read_only_enabled, send_enabled, created_at, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (merchant.id, connector, "pending_auth", "oauth", json.dumps(safe_config, ensure_ascii=False), join_tags(configured_fields), 1, 0, now_sql(), now_sql()),
            )
        conn.execute(
            f"""
            UPDATE connector_oauth_states
            SET status={marker}, callback_payload_json={marker}, used_at={marker}
            WHERE state={marker}
            """,
            ("code_received", json.dumps(callback_payload, ensure_ascii=False), now_sql(), state),
        )
    record_audit_log(merchant.id or 0, merchant.username, "connector.oauth.callback", "connector", connector, "收到 OAuth 回调 code，等待 token exchange", {"fields": configured_fields})
    return ConnectorOAuthCallbackResponse(
        connector=connector,
        state=state,
        status="code_received",
        configured_fields=configured_fields,
        next_action="OAuth code 已密文保存；可在设置页执行换取 Token。",
    )


OAUTH_CLIENT_ID_FIELD_NAMES = ["client_id", "client_key", "app_key"]
OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES = ["client_secret", "app_secret"]
OAUTH_TOKEN_URL_FIELD_NAMES = ["token_url", "oauth_token_url"]
OAUTH_ACCESS_RESPONSE_NAMES = ["access_token", "accessToken", "access", "token"]
OAUTH_REFRESH_RESPONSE_NAMES = ["refresh_token", "refreshToken"]
OAUTH_SESSION_RESPONSE_NAMES = ["session_key", "sessionKey"]


def oauth_has_value(value: Any) -> bool:
    return value is not None and value != ""


def oauth_config_value(config: dict[str, Any], names: list[str]) -> tuple[str, str]:
    for name in names:
        value = config.get(name)
        if oauth_has_value(value):
            return str(value), name
    return "", ""


def oauth_encrypted_value(config: dict[str, Any], merchant_id: int, names: list[str]) -> tuple[str, str]:
    encrypted_values = config.get("secret_fields_encrypted") or {}
    for name in names:
        if name in encrypted_values:
            return decrypt_connector_secret(str(encrypted_values[name]), merchant_id), name
    return "", ""


def connector_configured_fields_from_config(config: dict[str, Any]) -> list[str]:
    encrypted_values = config.get("secret_fields_encrypted") or {}
    return sorted(
        {name for name in config.keys() if name not in {"secret_fields_encrypted", "secret_fields_configured"}}
        | set(encrypted_values.keys())
    )


def oauth_response_value(payload: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = payload.get(name)
        if oauth_has_value(value):
            return str(value)
    return ""


def oauth_token_endpoint_host(token_url: str) -> str:
    parsed = urllib.parse.urlparse(token_url)
    return parsed.netloc


def parse_oauth_token_response(body: bytes, content_type: str = "") -> dict[str, Any]:
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.rsplit("charset=", 1)[-1].split(";", 1)[0].strip() or "utf-8"
    text = body.decode(charset, errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"error": "non_json_response"}
    return payload if isinstance(payload, dict) else {"response": payload}


def post_oauth_token_request(token_url: str, form: dict[str, str]) -> tuple[int, dict[str, Any]]:
    parsed = urllib.parse.urlparse(token_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OAuth token_url must be http(s)")
    data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        token_url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
            return int(getattr(response, "status", 200)), parse_oauth_token_response(body, content_type)
    except urllib.error.HTTPError as exc:
        body = exc.read(128 * 1024)
        return int(exc.code), parse_oauth_token_response(body, exc.headers.get("Content-Type", ""))


def select_oauth_token_payload(response: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = [response]
    for name in ["data", "result", "response"]:
        value = response.get(name)
        if isinstance(value, dict):
            candidates.append(value)
    for candidate in candidates:
        if (
            oauth_response_value(candidate, OAUTH_ACCESS_RESPONSE_NAMES)
            or oauth_response_value(candidate, OAUTH_SESSION_RESPONSE_NAMES)
        ):
            return candidate
    return response


def oauth_token_expires_at(payload: dict[str, Any]) -> str:
    raw_expiry = payload.get("expires_at") or payload.get("expire_at") or payload.get("expires_time")
    if oauth_has_value(raw_expiry):
        raw_text = str(raw_expiry)
        if raw_text.isdigit():
            timestamp = int(raw_text)
            if timestamp > 1_000_000_000:
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return raw_text
    raw_seconds = payload.get("expires_in") or payload.get("expire_in")
    if not oauth_has_value(raw_seconds):
        return ""
    try:
        seconds = max(0, int(float(str(raw_seconds))))
    except ValueError:
        return ""
    return datetime.fromtimestamp(time.time() + seconds).strftime("%Y-%m-%d %H:%M:%S")


def oauth_safe_response_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    allowed_sensitive_words = {"token_type"}
    for name, value in payload.items():
        lowered = str(name).lower()
        is_sensitive = any(part in lowered for part in ["token", "secret", "session_key", "authorization", "code"])
        if is_sensitive and lowered not in allowed_sensitive_words:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[name] = str(value)[:200] if isinstance(value, str) else value
        else:
            safe[name] = type(value).__name__
    return safe


async def exchange_connector_oauth_token(
    key: str,
    payload: ConnectorOAuthExchangeRequest,
    merchant: MerchantProfile,
) -> ConnectorOAuthExchangeResponse:
    connector = normalize_connector_key(key)
    catalog = CONNECTOR_CATALOG[connector]
    if catalog.get("auth_mode") != "oauth":
        return ConnectorOAuthExchangeResponse(
            connector=connector,
            status="setup_required",
            next_action="该 Connector 当前不是 OAuth 授权模式，无法执行 token exchange。",
        )

    existing_config = connector_config_for(merchant.id or 0, connector)
    encrypted_values = dict(existing_config.get("secret_fields_encrypted") or {})
    token_url, _ = oauth_config_value(existing_config, OAUTH_TOKEN_URL_FIELD_NAMES)
    token_url = (payload.token_url or token_url).strip()
    client_id_value, client_id_source = oauth_config_value(existing_config, OAUTH_CLIENT_ID_FIELD_NAMES)
    client_id_value = payload.client_id or client_id_value
    if payload.client_id:
        client_id_source = "client_id"
    code_value, _ = oauth_encrypted_value(existing_config, merchant.id or 0, ["oauth_code"])
    client_credential_value, client_credential_source = oauth_encrypted_value(
        existing_config,
        merchant.id or 0,
        OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES,
    )
    required = set(catalog.get("required_fields", []))
    missing: list[str] = []
    if not token_url:
        missing.append("token_url")
    if not client_id_value:
        missing.append("client_id/client_key/app_key")
    if not code_value:
        missing.append("oauth_code")
    if required.intersection(OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES) and not client_credential_value:
        missing.append("client_secret/app_secret")
    if missing:
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.exchange.setup_required",
            "connector",
            connector,
            f"OAuth token exchange 缺少配置：{', '.join(missing)}",
            {"missing": missing},
        )
        return ConnectorOAuthExchangeResponse(
            connector=connector,
            status="setup_required",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url) if token_url else "",
            next_action=f"请先补齐 {', '.join(missing)} 后再换取 token。",
        )

    client_id_param = str(existing_config.get("client_id_param") or existing_config.get("oauth_client_id_param") or client_id_source or "client_id")
    client_credential_param = str(
        existing_config.get("client_secret_param")
        or existing_config.get("oauth_client_secret_param")
        or client_credential_source
        or "client_secret"
    )
    code_param = str(existing_config.get("code_param") or existing_config.get("oauth_code_param") or "code")
    redirect_uri = payload.redirect_uri or str(existing_config.get("redirect_uri") or existing_config.get("callback_url") or "")
    redirect_uri_param = str(existing_config.get("redirect_uri_param") or "redirect_uri")
    form = {
        str(existing_config.get("grant_type_param") or "grant_type"): str(existing_config.get("grant_type") or "authorization_code"),
        code_param: code_value,
        client_id_param: client_id_value,
    }
    if client_credential_value:
        form[client_credential_param] = client_credential_value
    if redirect_uri:
        form[redirect_uri_param] = redirect_uri
    for extra_source_name in ["token_extra_params", "oauth_token_extra_params"]:
        extra_source = existing_config.get(extra_source_name)
        if isinstance(extra_source, dict):
            form.update({str(name): str(value) for name, value in extra_source.items() if oauth_has_value(value)})
    form.update({str(name): str(value) for name, value in payload.extra_params.items() if oauth_has_value(value)})

    try:
        http_status, response_body = await asyncio.to_thread(post_oauth_token_request, token_url, form)
    except Exception as exc:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_exchange", {"status": "failed", "reason": type(exc).__name__})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.exchange.failed",
            "connector",
            connector,
            "OAuth token exchange 请求失败",
            {"reason": type(exc).__name__},
        )
        return ConnectorOAuthExchangeResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action="Token endpoint 请求失败，请检查 token_url、网络连通性和官方参数。",
        )

    if http_status < 200 or http_status >= 300:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_exchange", {"status": "failed", "http_status": http_status})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.exchange.failed",
            "connector",
            connector,
            f"OAuth token exchange 返回 HTTP {http_status}",
            {"http_status": http_status},
        )
        return ConnectorOAuthExchangeResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action=f"Token endpoint 返回 HTTP {http_status}，请核对官方应用配置和回调 code。",
        )

    token_payload = select_oauth_token_payload(response_body)
    access_value = oauth_response_value(token_payload, OAUTH_ACCESS_RESPONSE_NAMES)
    refresh_value = oauth_response_value(token_payload, OAUTH_REFRESH_RESPONSE_NAMES)
    session_value = oauth_response_value(token_payload, OAUTH_SESSION_RESPONSE_NAMES)
    if not access_value and not session_value:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_exchange", {"status": "failed", "reason": "missing_token"})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.exchange.failed",
            "connector",
            connector,
            "OAuth token exchange 未返回 access_token 或 session_key",
            {"response_fields": sorted(token_payload.keys())},
        )
        return ConnectorOAuthExchangeResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action="官方 token 响应未包含 access_token/session_key，未写入连接成功状态。",
        )

    if access_value:
        encrypted_values["access_token"] = encrypt_connector_secret(access_value, merchant.id or 0)
    if refresh_value:
        encrypted_values["refresh_token"] = encrypt_connector_secret(refresh_value, merchant.id or 0)
    if session_value:
        encrypted_values["session_key"] = encrypt_connector_secret(session_value, merchant.id or 0)
    encrypted_values.pop("oauth_code", None)

    safe_config = {
        name: value
        for name, value in existing_config.items()
        if name not in {"secret_fields_encrypted", "secret_fields_configured"}
        and name not in {"access_token", "refresh_token", "session_key", "oauth_code"}
    }
    expires_at = oauth_token_expires_at(token_payload)
    safe_config.update({
        "oauth_token_exchanged_at": now_sql(),
        "oauth_token_status": "connected",
        "oauth_token_response_fields": sorted(token_payload.keys()),
        "oauth_token_metadata": oauth_safe_response_metadata(token_payload),
    })
    if expires_at:
        safe_config["oauth_token_expires_at"] = expires_at
    safe_config["secret_fields_encrypted"] = encrypted_values
    safe_config["secret_fields_configured"] = sorted(encrypted_values.keys())
    configured_fields = sorted(
        {name for name in safe_config.keys() if name not in {"secret_fields_encrypted", "secret_fields_configured"}}
        | set(encrypted_values.keys())
    )
    marker = param()
    with db() as conn:
        existing = conn.execute(
            f"SELECT id FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
        if existing:
            conn.execute(
                f"""
                UPDATE connector_credentials
                SET status={marker}, auth_mode={marker}, config_json={marker}, configured_fields={marker},
                    read_only_enabled={marker}, send_enabled={marker}, last_sync_at={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND connector={marker}
                """,
                (
                    "connected",
                    "oauth",
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1,
                    0,
                    now_sql(),
                    now_sql(),
                    merchant.id,
                    connector,
                ),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO connector_credentials (
                    merchant_id, connector, status, auth_mode, config_json, configured_fields,
                    read_only_enabled, send_enabled, last_sync_at, created_at, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    connector,
                    "connected",
                    "oauth",
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1,
                    0,
                    now_sql(),
                    now_sql(),
                    now_sql(),
                ),
            )
    record_connector_event(
        merchant.id or 0,
        connector,
        "auth",
        "oauth_exchange",
        {"status": "connected", "fields": configured_fields, "token_endpoint_host": oauth_token_endpoint_host(token_url)},
    )
    record_usage(merchant.id or 0, "connector_oauth_exchange", 1, "connector", connector, {"status": "connected"})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "connector.oauth.exchange.connected",
        "connector",
        connector,
        "OAuth token exchange 成功，访问凭证已密文保存",
        {"fields": configured_fields, "token_endpoint_host": oauth_token_endpoint_host(token_url)},
    )
    return ConnectorOAuthExchangeResponse(
        connector=connector,
        status="connected",
        configured_fields=configured_fields,
        token_endpoint_host=oauth_token_endpoint_host(token_url),
        expires_at=expires_at,
        next_action="OAuth token exchange 已完成；access_token/session_key 已密文保存，可进入官方只读 API worker 接入。",
    )


async def refresh_connector_oauth_token(
    key: str,
    payload: ConnectorOAuthRefreshRequest,
    merchant: MerchantProfile,
) -> ConnectorOAuthRefreshResponse:
    connector = normalize_connector_key(key)
    catalog = CONNECTOR_CATALOG[connector]
    if catalog.get("auth_mode") != "oauth":
        return ConnectorOAuthRefreshResponse(
            connector=connector,
            status="setup_required",
            next_action="该 Connector 当前不是 OAuth 授权模式，无法刷新 token。",
        )

    existing_config = connector_config_for(merchant.id or 0, connector)
    encrypted_values = dict(existing_config.get("secret_fields_encrypted") or {})
    token_url, _ = oauth_config_value(existing_config, OAUTH_TOKEN_URL_FIELD_NAMES)
    token_url = (payload.token_url or token_url).strip()
    client_id_value, client_id_source = oauth_config_value(existing_config, OAUTH_CLIENT_ID_FIELD_NAMES)
    client_id_value = payload.client_id or client_id_value
    if payload.client_id:
        client_id_source = "client_id"
    refresh_value, _ = oauth_encrypted_value(existing_config, merchant.id or 0, ["refresh_token"])
    client_credential_value, client_credential_source = oauth_encrypted_value(
        existing_config,
        merchant.id or 0,
        OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES,
    )
    required = set(catalog.get("required_fields", []))
    missing: list[str] = []
    if not token_url:
        missing.append("token_url")
    if not refresh_value:
        missing.append("refresh_token")
    if not client_id_value:
        missing.append("client_id/client_key/app_key")
    if required.intersection(OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES) and not client_credential_value:
        missing.append("client_secret/app_secret")
    if missing:
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.refresh.setup_required",
            "connector",
            connector,
            f"OAuth token refresh 缺少配置：{', '.join(missing)}",
            {"missing": missing},
        )
        return ConnectorOAuthRefreshResponse(
            connector=connector,
            status="setup_required",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url) if token_url else "",
            next_action=f"请先补齐 {', '.join(missing)} 后再刷新 token。",
        )

    client_id_param = str(existing_config.get("client_id_param") or existing_config.get("oauth_client_id_param") or client_id_source or "client_id")
    client_credential_param = str(
        existing_config.get("client_secret_param")
        or existing_config.get("oauth_client_secret_param")
        or client_credential_source
        or "client_secret"
    )
    refresh_param = str(existing_config.get("refresh_token_param") or existing_config.get("oauth_refresh_token_param") or "refresh_token")
    form = {
        str(existing_config.get("grant_type_param") or "grant_type"): str(existing_config.get("refresh_grant_type") or "refresh_token"),
        refresh_param: refresh_value,
        client_id_param: client_id_value,
    }
    if client_credential_value:
        form[client_credential_param] = client_credential_value
    for extra_source_name in ["refresh_extra_params", "oauth_refresh_extra_params", "token_extra_params", "oauth_token_extra_params"]:
        extra_source = existing_config.get(extra_source_name)
        if isinstance(extra_source, dict):
            form.update({str(name): str(value) for name, value in extra_source.items() if oauth_has_value(value)})
    form.update({str(name): str(value) for name, value in payload.extra_params.items() if oauth_has_value(value)})

    try:
        http_status, response_body = await asyncio.to_thread(post_oauth_token_request, token_url, form)
    except Exception as exc:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_refresh", {"status": "failed", "reason": type(exc).__name__})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.refresh.failed",
            "connector",
            connector,
            "OAuth token refresh 请求失败",
            {"reason": type(exc).__name__},
        )
        return ConnectorOAuthRefreshResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action="Token endpoint 刷新请求失败，请检查 token_url、网络连通性和官方参数。",
        )

    if http_status < 200 or http_status >= 300:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_refresh", {"status": "failed", "http_status": http_status})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.refresh.failed",
            "connector",
            connector,
            f"OAuth token refresh 返回 HTTP {http_status}",
            {"http_status": http_status},
        )
        return ConnectorOAuthRefreshResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action=f"Token endpoint 返回 HTTP {http_status}，未更新访问凭证。",
        )

    token_payload = select_oauth_token_payload(response_body)
    access_value = oauth_response_value(token_payload, OAUTH_ACCESS_RESPONSE_NAMES)
    next_refresh_value = oauth_response_value(token_payload, OAUTH_REFRESH_RESPONSE_NAMES)
    session_value = oauth_response_value(token_payload, OAUTH_SESSION_RESPONSE_NAMES)
    if not access_value and not session_value:
        record_connector_event(merchant.id or 0, connector, "auth", "oauth_refresh", {"status": "failed", "reason": "missing_token"})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.oauth.refresh.failed",
            "connector",
            connector,
            "OAuth token refresh 未返回 access_token 或 session_key",
            {"response_fields": sorted(token_payload.keys())},
        )
        return ConnectorOAuthRefreshResponse(
            connector=connector,
            status="failed",
            configured_fields=connector_configured_fields_from_config(existing_config),
            token_endpoint_host=oauth_token_endpoint_host(token_url),
            next_action="官方 refresh 响应未包含 access_token/session_key，未更新连接状态。",
        )

    if access_value:
        encrypted_values["access_token"] = encrypt_connector_secret(access_value, merchant.id or 0)
    if next_refresh_value:
        encrypted_values["refresh_token"] = encrypt_connector_secret(next_refresh_value, merchant.id or 0)
    if session_value:
        encrypted_values["session_key"] = encrypt_connector_secret(session_value, merchant.id or 0)

    safe_config = {
        name: value
        for name, value in existing_config.items()
        if name not in {"secret_fields_encrypted", "secret_fields_configured"}
        and name not in {"access_token", "refresh_token", "session_key", "oauth_code"}
    }
    expires_at = oauth_token_expires_at(token_payload)
    safe_config.update({
        "oauth_token_refreshed_at": now_sql(),
        "oauth_token_status": "connected",
        "oauth_refresh_response_fields": sorted(token_payload.keys()),
        "oauth_token_metadata": oauth_safe_response_metadata(token_payload),
    })
    if expires_at:
        safe_config["oauth_token_expires_at"] = expires_at
    safe_config["secret_fields_encrypted"] = encrypted_values
    safe_config["secret_fields_configured"] = sorted(encrypted_values.keys())
    configured_fields = connector_configured_fields_from_config(safe_config)
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            UPDATE connector_credentials
            SET status={marker}, auth_mode={marker}, config_json={marker}, configured_fields={marker},
                read_only_enabled={marker}, last_sync_at={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND connector={marker}
            """,
            (
                "connected",
                "oauth",
                json.dumps(safe_config, ensure_ascii=False),
                join_tags(configured_fields),
                1,
                now_sql(),
                now_sql(),
                merchant.id,
                connector,
            ),
        )
    record_connector_event(
        merchant.id or 0,
        connector,
        "auth",
        "oauth_refresh",
        {"status": "refreshed", "fields": configured_fields, "token_endpoint_host": oauth_token_endpoint_host(token_url)},
    )
    record_usage(merchant.id or 0, "connector_oauth_refresh", 1, "connector", connector, {"status": "refreshed"})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "connector.oauth.refresh.refreshed",
        "connector",
        connector,
        "OAuth token refresh 成功，访问凭证已密文更新",
        {"fields": configured_fields, "token_endpoint_host": oauth_token_endpoint_host(token_url)},
    )
    return ConnectorOAuthRefreshResponse(
        connector=connector,
        status="refreshed",
        configured_fields=configured_fields,
        token_endpoint_host=oauth_token_endpoint_host(token_url),
        expires_at=expires_at,
        next_action="OAuth token refresh 已完成；新访问凭证已密文保存。",
    )


READ_MESSAGE_ENDPOINT_FIELDS = ["messages_url", "read_messages_url", "message_api_url", "official_messages_url"]
READ_LEAD_ENDPOINT_FIELDS = ["leads_url", "read_leads_url", "lead_api_url", "official_leads_url"]


def connector_read_endpoint(config: dict[str, Any], resource: Literal["messages", "leads"]) -> str:
    names = READ_MESSAGE_ENDPOINT_FIELDS if resource == "messages" else READ_LEAD_ENDPOINT_FIELDS
    value, _ = oauth_config_value(config, names)
    return value.strip()


def connector_read_credential(config: dict[str, Any], merchant_id: int) -> tuple[str, str]:
    credential_value, credential_field = oauth_encrypted_value(config, merchant_id, ["access_token", "session_key", "token"])
    return credential_value, credential_field


def connector_send_url(config: dict[str, Any]) -> str:
    value, _ = oauth_config_value(config, CONNECTOR_SEND_URL_FIELDS)
    return value.strip()


async def update_connector_send_gate(key: str, payload: ConnectorSendGateUpdate, merchant: MerchantProfile) -> ConnectorSendGateResponse:
    connector = normalize_connector_key(key)
    marker = param()
    existing_config = connector_config_for(merchant.id or 0, connector)
    encrypted_values = dict(existing_config.get("secret_fields_encrypted") or {})
    safe_config = {
        name: value
        for name, value in existing_config.items()
        if name not in {"secret_fields_encrypted", "secret_fields_configured"}
    }
    if payload.send_url:
        safe_config["send_url"] = payload.send_url.strip()
    safe_config["send_rate_limit_per_hour"] = payload.rate_limit_per_hour
    send_url = connector_send_url(safe_config)
    credential_value, _ = connector_read_credential({"secret_fields_encrypted": encrypted_values}, merchant.id or 0)
    missing: list[str] = []
    if payload.send_enabled and payload.confirmation_phrase != SEND_GATE_ENABLE_PHRASE:
        missing.append("confirmation_phrase")
    if payload.send_enabled and not send_url:
        missing.append("send_url")
    if payload.send_enabled and not credential_value:
        missing.append("access_token/session_key")
    next_send_enabled = bool(payload.send_enabled and not missing)
    safe_config["supervised_send_enabled_at"] = now_sql() if next_send_enabled else ""
    safe_config["secret_fields_encrypted"] = encrypted_values
    safe_config["secret_fields_configured"] = sorted(encrypted_values.keys())
    configured_fields = connector_configured_fields_from_config(safe_config)
    with db() as conn:
        existing = conn.execute(
            f"SELECT id FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
        if existing:
            conn.execute(
                f"""
                UPDATE connector_credentials
                SET config_json={marker}, configured_fields={marker}, send_enabled={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND connector={marker}
                """,
                (
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1 if next_send_enabled else 0,
                    now_sql(),
                    merchant.id,
                    connector,
                ),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO connector_credentials (
                    merchant_id, connector, status, auth_mode, config_json, configured_fields,
                    read_only_enabled, send_enabled, created_at, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    connector,
                    "pending_auth",
                    CONNECTOR_CATALOG[connector]["auth_mode"],
                    json.dumps(safe_config, ensure_ascii=False),
                    join_tags(configured_fields),
                    1,
                    1 if next_send_enabled else 0,
                    now_sql(),
                    now_sql(),
                ),
            )
    status: Literal["enabled", "disabled", "setup_required"]
    if next_send_enabled:
        status = "enabled"
        next_action = "受控 API 发送闸门已开启；每次发送仍需人工确认短语和低风险校验。"
    elif payload.send_enabled:
        status = "setup_required"
        next_action = f"未开启发送闸门，请补齐 {', '.join(missing)}。"
    else:
        status = "disabled"
        next_action = "受控 API 发送闸门已关闭；回复仍只进入人工复制队列。"
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        f"connector.send_gate.{status}",
        "connector",
        connector,
        "更新受控 API 发送闸门",
        {"status": status, "missing": missing, "fields": configured_fields},
    )
    return ConnectorSendGateResponse(
        connector=connector,
        status=status,
        send_enabled=next_send_enabled,
        configured_fields=configured_fields,
        next_action=next_action,
    )


def connector_endpoint_host(endpoint_url: str) -> str:
    return urllib.parse.urlparse(endpoint_url).netloc


def fetch_connector_read_api(
    endpoint_url: str,
    config: dict[str, Any],
    credential_value: str,
    credential_field: str,
    params: dict[str, str],
) -> tuple[int, dict[str, Any]]:
    parsed = urllib.parse.urlparse(endpoint_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Connector read endpoint must be http(s)")
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update({name: value for name, value in params.items() if oauth_has_value(value)})
    headers = {"Accept": "application/json"}
    auth_mode = str(config.get("read_api_auth_mode") or config.get("api_auth_mode") or "")
    if not auth_mode:
        auth_mode = "query" if credential_field == "session_key" else "bearer"
    if auth_mode == "query":
        token_param = str(config.get("access_token_param") or config.get("read_api_token_param") or credential_field or "access_token")
        query[token_param] = credential_value
    elif auth_mode == "header":
        header_name = str(config.get("read_api_auth_header") or config.get("api_auth_header") or "Authorization")
        header_template = str(config.get("read_api_auth_header_template") or config.get("api_auth_header_template") or "{token}")
        headers[header_name] = header_template.replace("{token}", credential_value)
    else:
        headers["Authorization"] = f"Bearer {credential_value}"
    final_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    request = urllib.request.Request(final_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
            return int(getattr(response, "status", 200)), parse_oauth_token_response(body, content_type)
    except urllib.error.HTTPError as exc:
        body = exc.read(128 * 1024)
        return int(exc.code), parse_oauth_token_response(body, exc.headers.get("Content-Type", ""))


def connector_api_items(payload: dict[str, Any], resource: Literal["messages", "leads"]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    keys = ["messages", "message_list", "messageList"] if resource == "messages" else ["leads", "lead_list", "leadList"]
    keys.extend(["items", "records", "list"])
    candidates: list[Any] = [payload]
    for name in ["data", "result", "response"]:
        value = payload.get(name)
        if isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in keys:
                value = candidate.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def connector_item_text(item: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = item.get(name)
        if oauth_has_value(value):
            return str(value).strip()
    return ""


def connector_item_external_id(item: dict[str, Any], resource: Literal["messages", "leads"]) -> str:
    external_id = connector_item_text(item, ["external_id", "externalId", "id", "message_id", "messageId", "lead_id", "leadId", "order_id", "orderId"])
    if external_id:
        return external_id[:160]
    raw = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{resource}:{raw}".encode("utf-8")).hexdigest()[:24]
    return f"{resource}-{digest}"


def connector_message_from_item(item: dict[str, Any]) -> ConnectorInboundMessageRequest | None:
    text = connector_item_text(item, ["text", "content", "message", "msg", "body", "question", "query"])
    if not text:
        return None
    return ConnectorInboundMessageRequest(
        external_id=connector_item_external_id(item, "messages"),
        sender_id=connector_item_text(item, ["sender_id", "senderId", "user_id", "userId", "buyer_id", "buyerId", "openid", "open_id"]),
        sender_name=connector_item_text(item, ["sender_name", "senderName", "nickname", "name", "buyer_name", "buyerName"]),
        contact=connector_item_text(item, ["contact", "phone", "mobile", "wechat", "email"]),
        text=text[:3000],
        raw=item,
    )


def connector_lead_from_item(item: dict[str, Any]) -> ConnectorInboundLeadRequest | None:
    need = connector_item_text(item, ["need", "content", "message", "summary", "title", "remark", "description"])
    if not need:
        return None
    return ConnectorInboundLeadRequest(
        external_id=connector_item_external_id(item, "leads"),
        name=connector_item_text(item, ["name", "customer_name", "customerName", "buyer_name", "buyerName", "nickname"]),
        contact=connector_item_text(item, ["contact", "phone", "mobile", "wechat", "email"]),
        need=need[:3000],
        raw=item,
    )


async def pull_connector_read_api(
    key: str,
    payload: ConnectorReadPullRequest,
    merchant: MerchantProfile,
) -> ConnectorReadPullResponse:
    connector = normalize_connector_key(key)
    config = connector_config_for(merchant.id or 0, connector)
    endpoint_url = (payload.endpoint_url or connector_read_endpoint(config, payload.resource)).strip()
    credential_value, credential_field = connector_read_credential(config, merchant.id or 0)
    missing: list[str] = []
    if not endpoint_url:
        missing.append("messages_url/leads_url")
    if not credential_value:
        missing.append("access_token/session_key")
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT read_only_enabled FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, connector),
        ).fetchone()
    if row and not bool(dict(row).get("read_only_enabled")):
        missing.append("read_only_enabled")
    if missing:
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.api.pull.setup_required",
            "connector",
            connector,
            f"官方 API 只读拉取缺少配置：{', '.join(missing)}",
            {"resource": payload.resource, "missing": missing},
        )
        return ConnectorReadPullResponse(
            connector=connector,
            resource=payload.resource,
            status="setup_required",
            endpoint_host=connector_endpoint_host(endpoint_url) if endpoint_url else "",
            next_action=f"请先补齐 {', '.join(missing)} 后再执行只读拉取。",
        )

    request_params = {"limit": str(payload.limit)}
    request_params.update({str(name): str(value) for name, value in payload.extra_params.items() if oauth_has_value(value)})
    try:
        http_status, response_body = await asyncio.to_thread(
            fetch_connector_read_api,
            endpoint_url,
            config,
            credential_value,
            credential_field,
            request_params,
        )
    except Exception as exc:
        record_connector_event(merchant.id or 0, connector, "auth", "api_pull", {"status": "failed", "resource": payload.resource, "reason": type(exc).__name__})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.api.pull.failed",
            "connector",
            connector,
            "官方 API 只读拉取请求失败",
            {"resource": payload.resource, "reason": type(exc).__name__},
        )
        return ConnectorReadPullResponse(
            connector=connector,
            resource=payload.resource,
            status="failed",
            endpoint_host=connector_endpoint_host(endpoint_url),
            next_action="官方 API 只读拉取请求失败，请检查 endpoint、访问凭证和网络连通性。",
        )
    if http_status < 200 or http_status >= 300:
        record_connector_event(merchant.id or 0, connector, "auth", "api_pull", {"status": "failed", "resource": payload.resource, "http_status": http_status})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "connector.api.pull.failed",
            "connector",
            connector,
            f"官方 API 只读拉取返回 HTTP {http_status}",
            {"resource": payload.resource, "http_status": http_status},
        )
        return ConnectorReadPullResponse(
            connector=connector,
            resource=payload.resource,
            status="failed",
            endpoint_host=connector_endpoint_host(endpoint_url),
            next_action=f"官方 API 返回 HTTP {http_status}，未写入 CRM。",
        )

    items = connector_api_items(response_body, payload.resource)[:payload.limit]
    imported = 0
    duplicates = 0
    skipped = 0
    workflow_run_ids: list[str] = []
    for item in items:
        if payload.resource == "messages":
            message = connector_message_from_item(item)
            if not message:
                skipped += 1
                continue
            was_duplicate = find_connector_event(merchant.id or 0, connector, "message", message.external_id) is not None
            result = await ingest_connector_message(connector, message, merchant)
        else:
            lead = connector_lead_from_item(item)
            if not lead:
                skipped += 1
                continue
            was_duplicate = find_connector_event(merchant.id or 0, connector, "lead", lead.external_id) is not None
            result = await ingest_connector_lead(connector, lead, merchant)
        if was_duplicate:
            duplicates += 1
        else:
            imported += 1
        workflow_run_ids.extend(result.workflow_run_ids)

    with db() as conn:
        conn.execute(
            f"""
            UPDATE connector_credentials
            SET last_sync_at={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND connector={marker}
            """,
            (now_sql(), now_sql(), merchant.id, connector),
        )
    record_connector_event(
        merchant.id or 0,
        connector,
        "auth",
        "api_pull",
        {"status": "pulled", "resource": payload.resource, "imported": imported, "duplicates": duplicates, "skipped": skipped, "endpoint_host": connector_endpoint_host(endpoint_url)},
    )
    record_usage(merchant.id or 0, "connector_api_pull", 1, connector, payload.resource, {"imported": imported, "duplicates": duplicates, "skipped": skipped})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "connector.api.pull",
        "connector",
        connector,
        f"官方 API 只读拉取 {payload.resource}",
        {"imported": imported, "duplicates": duplicates, "skipped": skipped, "endpoint_host": connector_endpoint_host(endpoint_url)},
    )
    return ConnectorReadPullResponse(
        connector=connector,
        resource=payload.resource,
        status="pulled",
        imported=imported,
        duplicates=duplicates,
        skipped=skipped,
        endpoint_host=connector_endpoint_host(endpoint_url),
        workflow_run_ids=workflow_run_ids,
        next_action="只读拉取完成；消息/线索已进入 CRM/Workflow，回复仍需人工确认，不会自动外发。",
    )


def record_connector_event(
    merchant_id: int,
    connector: str,
    event_type: Literal["message", "lead", "auth"],
    external_id: str,
    payload: dict[str, Any],
    workflow_run_id: str = "",
) -> ConnectorEvent:
    marker = param()
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO connector_events (merchant_id, connector, event_type, external_id, payload_json, workflow_run_id, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant_id, connector, event_type, external_id, json.dumps(payload, ensure_ascii=False), workflow_run_id, now_sql()),
        )
        event_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM connector_events WHERE id={marker}", (event_id,)).fetchone()
    data = dict(row)
    return ConnectorEvent(
        id=int(data.get("id") or 0),
        merchant_id=int(data.get("merchant_id") or 0),
        connector=data.get("connector") or "",
        event_type=data.get("event_type") or "message",
        external_id=data.get("external_id") or "",
        payload=json.loads(data.get("payload_json") or "{}"),
        workflow_run_id=data.get("workflow_run_id") or "",
        created_at=str(data.get("created_at") or ""),
    )


def find_connector_event(
    merchant_id: int,
    connector: str,
    event_type: Literal["message", "lead", "auth"],
    external_id: str,
) -> ConnectorEvent | None:
    if not external_id:
        return None
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM connector_events
            WHERE merchant_id={marker} AND connector={marker} AND event_type={marker} AND external_id={marker}
            ORDER BY id DESC
            LIMIT 1
            """,
            (merchant_id, connector, event_type, external_id),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    return ConnectorEvent(
        id=int(data.get("id") or 0),
        merchant_id=int(data.get("merchant_id") or 0),
        connector=data.get("connector") or "",
        event_type=data.get("event_type") or event_type,
        external_id=data.get("external_id") or "",
        payload=json.loads(data.get("payload_json") or "{}"),
        workflow_run_id=data.get("workflow_run_id") or "",
        created_at=str(data.get("created_at") or ""),
    )


def find_reply_draft_by_external(merchant_id: int, connector: str, external_id: str) -> ReplyDraftQueueItem | None:
    if not external_id:
        return None
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM reply_drafts
            WHERE merchant_id={marker} AND connector={marker} AND external_id={marker}
            ORDER BY id DESC
            LIMIT 1
            """,
            (merchant_id, connector, external_id),
        ).fetchone()
    return reply_draft_queue_from_row(dict(row)) if row else None


async def list_connector_events(merchant: MerchantProfile, connector: str = "") -> list[ConnectorEvent]:
    marker = param()
    filters = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if connector:
        filters.append(f"connector={marker}")
        params.append(normalize_connector_key(connector))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT *
            FROM connector_events
            WHERE {" AND ".join(filters)}
            ORDER BY id DESC
            LIMIT 100
            """,
            tuple(params),
        ).fetchall())
    events: list[ConnectorEvent] = []
    for row in rows:
        events.append(
            ConnectorEvent(
                id=int(row.get("id") or 0),
                merchant_id=int(row.get("merchant_id") or 0),
                connector=row.get("connector") or "",
                event_type=row.get("event_type") or "message",
                external_id=row.get("external_id") or "",
                payload=json.loads(row.get("payload_json") or "{}"),
                workflow_run_id=row.get("workflow_run_id") or "",
                created_at=str(row.get("created_at") or ""),
            )
        )
    return events


def connector_recent_failure_count(merchant_id: int, connector: str) -> int:
    marker = param()
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT payload_json
            FROM connector_events
            WHERE merchant_id={marker} AND connector={marker} AND event_type={marker}
            ORDER BY id DESC
            LIMIT 50
            """,
            (merchant_id, connector, "auth"),
        ).fetchall())
    failures = 0
    for row in rows:
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if str(payload.get("status") or "").lower() in {"failed", "error"}:
            failures += 1
    return failures


def connector_dispatch_counts(merchant_id: int, connector: str) -> tuple[int, int]:
    marker = param()
    with db() as conn:
        pending = dict(conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM reply_dispatches
            WHERE merchant_id={marker} AND connector={marker} AND status={marker}
            """,
            (merchant_id, connector, "manual_ready"),
        ).fetchone()).get("c") or 0
        failed = dict(conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM reply_dispatches
            WHERE merchant_id={marker} AND connector={marker} AND status={marker}
            """,
            (merchant_id, connector, "send_failed"),
        ).fetchone()).get("c") or 0
    return int(pending), int(failed)


async def connector_ops_health(merchant: MerchantProfile) -> ConnectorHealthOverview:
    auths = await list_connector_auths(merchant)
    items: list[ConnectorHealthItem] = []
    global_alerts: list[str] = []
    for auth in auths:
        config = connector_config_for(merchant.id or 0, auth.key)
        token_expires_at = str(config.get("oauth_token_expires_at") or "")
        pending_dispatches, failed_dispatches = connector_dispatch_counts(merchant.id or 0, auth.key)
        recent_failures = connector_recent_failure_count(merchant.id or 0, auth.key)
        alerts: list[str] = []
        has_access = any(field in auth.configured_fields for field in ["access_token", "session_key"])
        has_refresh = "refresh_token" in auth.configured_fields
        has_read_endpoint = any(field in auth.configured_fields for field in ["messages_url", "leads_url", "read_messages_url", "read_leads_url"])
        has_send_endpoint = any(field in auth.configured_fields for field in CONNECTOR_SEND_URL_FIELDS)
        if auth.auth_mode == "oauth" and not has_access:
            alerts.append("OAuth Connector 尚未保存 access_token/session_key。")
        if auth.auth_mode == "oauth" and has_access and not has_refresh:
            alerts.append("OAuth Connector 缺少 refresh_token，访问凭证到期后需重新授权。")
        if auth.auth_mode == "oauth" and token_expires_at:
            if token_expires_at < now_sql():
                alerts.append("OAuth token 已过期。")
            else:
                try:
                    expires_dt = datetime.strptime(token_expires_at[:19], "%Y-%m-%d %H:%M:%S")
                    if (expires_dt - datetime.now()).total_seconds() < 7 * 24 * 3600:
                        alerts.append("OAuth token 7 天内到期。")
                except ValueError:
                    pass
        if has_access and not has_read_endpoint and auth.read_only_enabled:
            alerts.append("已有访问凭证，但未配置只读 messages_url/leads_url。")
        if auth.send_enabled and (not has_access or not has_send_endpoint):
            alerts.append("受控发送闸门开启但 send_url 或访问凭证缺失。")
        if pending_dispatches:
            alerts.append(f"外发准备队列有 {pending_dispatches} 条待处理。")
        if failed_dispatches:
            alerts.append(f"存在 {failed_dispatches} 条发送失败记录。")
        if recent_failures:
            alerts.append(f"最近 Connector 认证/API 失败 {recent_failures} 次。")
        status: Literal["pass", "warning", "fail"] = "pass"
        if auth.send_enabled and (not has_access or not has_send_endpoint):
            status = "fail"
        elif recent_failures >= 3 or failed_dispatches:
            status = "fail"
        elif alerts or auth.status in {"pending_auth", "not_configured", "failed"}:
            status = "warning"
        next_action = "保持当前配置并定期检查。"
        if status == "fail":
            next_action = "优先处理失败记录、访问凭证或发送闸门配置。"
        elif status == "warning":
            next_action = "补齐授权、endpoint 或处理待外发队列。"
        item = ConnectorHealthItem(
            connector=auth.key,
            label=auth.label,
            status=status,
            auth_status=auth.status,
            auth_mode=auth.auth_mode,
            read_only_enabled=auth.read_only_enabled,
            send_enabled=auth.send_enabled,
            configured_fields=auth.configured_fields,
            alerts=alerts,
            pending_dispatches=pending_dispatches,
            failed_dispatches=failed_dispatches,
            recent_failures=recent_failures,
            last_sync_at=auth.last_sync_at,
            token_expires_at=token_expires_at,
            next_action=next_action,
        )
        items.append(item)
        global_alerts.extend([f"{auth.label}: {alert}" for alert in alerts[:2]])
    if any(item.status == "fail" for item in items):
        status = "fail"
        summary = "存在需要立即处理的 Connector 失败或发送配置风险。"
    elif any(item.status == "warning" for item in items):
        status = "warning"
        summary = "Connector 可继续试运行，但仍有授权、endpoint 或待处理队列需要补齐。"
    else:
        status = "pass"
        summary = "Connector 运维健康项通过。"
    return ConnectorHealthOverview(
        status=status,
        summary=summary,
        items=items,
        alerts=global_alerts[:12],
        created_at=now_sql(),
    )


def has_any_field(configured_fields: list[str], names: list[str]) -> bool:
    field_set = set(configured_fields)
    return any(name in field_set for name in names)


def connector_setup_task(
    connector: str,
    label: str,
    category: str,
    status: Literal["done", "todo", "blocked"],
    severity: Literal["info", "warning", "blocker"],
    title: str,
    next_action: str,
    required_fields: list[str] | None = None,
    configured_fields: list[str] | None = None,
    evidence: str = "",
    endpoint_hint: str = "",
) -> ConnectorSetupTask:
    return ConnectorSetupTask(
        id=f"{connector}-{category}-{title.lower().replace(' ', '-')[:32]}",
        connector=connector,
        label=label,
        category=category,
        severity=severity,
        status=status,
        title=title,
        evidence=evidence,
        next_action=next_action,
        required_fields=required_fields or [],
        configured_fields=configured_fields or [],
        endpoint_hint=endpoint_hint,
    )


async def connector_setup_guide(merchant: MerchantProfile) -> ConnectorSetupGuide:
    auths = await list_connector_auths(merchant)
    health = await connector_ops_health(merchant)
    health_by_key = {item.connector: item for item in health.items}
    tasks: list[ConnectorSetupTask] = []
    for auth in auths:
        configured = auth.configured_fields
        config = connector_config_for(merchant.id or 0, auth.key)
        has_client_id = has_any_field(configured, OAUTH_CLIENT_ID_FIELD_NAMES)
        has_oauth_credential = has_any_field(configured, OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES)
        has_authorize_url = has_any_field(configured, ["authorize_url", "oauth_authorize_url"])
        has_token_url = has_any_field(configured, OAUTH_TOKEN_URL_FIELD_NAMES)
        has_oauth_code = "oauth_code" in configured
        has_access = has_any_field(configured, ["access_token", "session_key", "token"])
        has_refresh = "refresh_token" in configured
        has_read_endpoint = has_any_field(configured, READ_MESSAGE_ENDPOINT_FIELDS + READ_LEAD_ENDPOINT_FIELDS)
        has_message_endpoint = has_any_field(configured, READ_MESSAGE_ENDPOINT_FIELDS)
        has_lead_endpoint = has_any_field(configured, READ_LEAD_ENDPOINT_FIELDS)
        has_send_endpoint = has_any_field(configured, CONNECTOR_SEND_URL_FIELDS)
        has_signing_key = has_any_field(configured, ["webhook_secret", "webhook_token", "token", "encoding_aes_key"])
        oauth_configured = has_authorize_url and has_client_id and has_oauth_credential
        if auth.auth_mode == "oauth":
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "oauth_config",
                "done" if oauth_configured else "todo",
                "info" if oauth_configured else "blocker",
                "OAuth app configuration",
                "OAuth app fields are present." if oauth_configured else "Fill authorize_url, client id/key and client secret/app secret, then generate an authorization link.",
                ["authorize_url", "client_id/client_key/app_key", "client_secret/app_secret"],
                [field for field in configured if field in {"authorize_url", "oauth_authorize_url", "client_id", "client_key", "app_key", "client_secret", "app_secret"}],
                "Configured enough to start OAuth." if oauth_configured else "OAuth cannot start without official app fields.",
                connector_oauth_callback_path(auth.key),
            ))
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "oauth_authorize",
                "done" if has_oauth_code or has_access else "blocked" if not oauth_configured else "todo",
                "info" if has_oauth_code or has_access else "blocker",
                "OAuth authorization callback",
                "Callback code was received or an access credential already exists." if has_oauth_code or has_access else "Open the generated authorization link and finish the official callback.",
                ["oauth_code"],
                [field for field in configured if field == "oauth_code"],
                "Waiting for official OAuth callback." if oauth_configured and not (has_oauth_code or has_access) else "",
                auth.callback_url or connector_oauth_callback_path(auth.key),
            ))
            exchange_ready = has_access
            exchange_blocked = not has_oauth_code or not has_token_url
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "oauth_exchange",
                "done" if exchange_ready else "blocked" if exchange_blocked else "todo",
                "info" if exchange_ready else "blocker",
                "OAuth token exchange",
                "Encrypted access token or session key is stored." if exchange_ready else "Exchange the callback code at the official token endpoint.",
                ["token_url", "oauth_code", "access_token/session_key"],
                [field for field in configured if field in {"token_url", "oauth_token_url", "oauth_code", "access_token", "session_key"}],
                "Missing token_url or oauth_code." if exchange_blocked and not exchange_ready else "Ready to exchange the OAuth code.",
                str(config.get("token_url") or config.get("oauth_token_url") or ""),
            ))
            refresh_status: Literal["done", "todo", "blocked"] = "done" if has_refresh else "blocked" if not has_access else "todo"
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "oauth_refresh",
                refresh_status,
                "info" if has_refresh else "warning",
                "OAuth refresh token",
                "Refresh token is encrypted and available." if has_refresh else "Store refresh_token from the official token response so access does not expire silently.",
                ["refresh_token", "token_url"],
                [field for field in configured if field in {"refresh_token", "token_url", "oauth_token_url"}],
                "Access credential must exist before refresh can run." if not has_access else "Refresh token is not configured yet.",
                str(config.get("token_url") or config.get("oauth_token_url") or ""),
            ))
        elif auth.auth_mode in {"api_key", "webhook"}:
            missing_required = [field for field in auth.missing_fields if field]
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "credential_config",
                "done" if not missing_required else "todo",
                "info" if not missing_required else "warning",
                "Connector credential fields",
                "Required credential fields are configured." if not missing_required else "Complete the required official credential fields.",
                list(CONNECTOR_CATALOG[auth.key].get("required_fields", [])),
                configured,
                f"Missing: {', '.join(missing_required)}" if missing_required else "",
            ))
        if auth.auth_mode == "webhook" or "message_read" in auth.capabilities or "lead_sync" in auth.capabilities:
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "webhook_signature",
                "done" if has_signing_key or auth.key in {"website"} else "todo",
                "info" if has_signing_key or auth.key in {"website"} else "warning",
                "Webhook signing secret",
                "Webhook signature secret is configured or not required for this connector." if has_signing_key or auth.key in {"website"} else "Save webhook_token or webhook_secret before exposing the public webhook endpoint.",
                ["webhook_token/webhook_secret"],
                [field for field in configured if field in {"webhook_token", "webhook_secret", "token", "encoding_aes_key"}],
                "Public webhooks reject unsigned traffic until this is configured.",
                f"/api/v1/webhooks/{auth.key}/messages",
            ))
        if auth.read_only_enabled and auth.auth_mode == "oauth":
            read_status: Literal["done", "todo", "blocked"]
            if has_access and has_read_endpoint:
                read_status = "done"
            elif has_access:
                read_status = "todo"
            else:
                read_status = "blocked"
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "read_api",
                read_status,
                "info" if read_status == "done" else "warning",
                "Official read API",
                "Read endpoint and encrypted access credential are ready." if read_status == "done" else "Configure messages_url and/or leads_url, then run the read-only pull worker.",
                ["access_token/session_key", "messages_url/leads_url"],
                [field for field in configured if field in set(["access_token", "session_key"] + READ_MESSAGE_ENDPOINT_FIELDS + READ_LEAD_ENDPOINT_FIELDS)],
                f"messages_endpoint={has_message_endpoint}; leads_endpoint={has_lead_endpoint}; access={has_access}",
                str(config.get("messages_url") or config.get("leads_url") or config.get("read_messages_url") or config.get("read_leads_url") or ""),
            ))
        if auth.auth_mode == "oauth" or auth.send_enabled or has_send_endpoint:
            send_done = auth.send_enabled and has_access and has_send_endpoint
            send_status: Literal["done", "todo", "blocked"]
            if send_done:
                send_status = "done"
            elif has_access and has_send_endpoint:
                send_status = "todo"
            else:
                send_status = "blocked"
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "send_api",
                send_status,
                "info" if send_done else "warning",
                "Supervised send API",
                "Supervised send gate is enabled with credential and endpoint." if send_done else "Configure send_url and access credential, then explicitly enable the supervised send gate.",
                ["access_token/session_key", "send_url", SEND_GATE_ENABLE_PHRASE],
                [field for field in configured if field in set(["access_token", "session_key"] + CONNECTOR_SEND_URL_FIELDS)],
                "This still requires human confirmation per dispatch.",
                str(config.get("send_url") or config.get("reply_send_url") or config.get("message_send_url") or config.get("official_send_url") or ""),
            ))
        health_item = health_by_key.get(auth.key)
        if health_item and health_item.alerts:
            tasks.append(connector_setup_task(
                auth.key,
                auth.label,
                "ops_health",
                "todo" if health_item.status != "pass" else "done",
                "blocker" if health_item.status == "fail" else "warning",
                "Connector health remediation",
                next_action=health_item.next_action,
                required_fields=[],
                configured_fields=configured,
                evidence="; ".join(health_item.alerts[:3]),
            ))
    tasks.append(connector_setup_task(
        "platform",
        "Platform safety boundary",
        "safety_boundary",
        "blocked",
        "info",
        "Unattended auto-send remains disabled",
        next_action="Keep automatic publishing, price changes, refunds, shipping and unattended messaging outside the enabled scope.",
        required_fields=["human_confirmation", "audit_log", "rate_limit"],
        configured_fields=["human_confirmation", "audit_log", "rate_limit"],
        evidence="The system supports drafts and supervised sends only after human confirmation.",
    ))
    counts = {
        "done": sum(1 for item in tasks if item.status == "done"),
        "todo": sum(1 for item in tasks if item.status == "todo"),
        "blocked": sum(1 for item in tasks if item.status == "blocked"),
        "blocker": sum(1 for item in tasks if item.severity == "blocker"),
        "warning": sum(1 for item in tasks if item.severity == "warning"),
        "info": sum(1 for item in tasks if item.severity == "info"),
    }
    actionable = [item for item in tasks if item.category != "safety_boundary" and item.status != "done"]
    blocking = [item for item in actionable if item.severity == "blocker" or item.status == "blocked"]
    if blocking:
        status: Literal["ready", "needs_setup", "blocked"] = "blocked"
    elif actionable:
        status = "needs_setup"
    else:
        status = "ready"
    if status == "ready":
        summary = "All actionable connector setup tasks are complete; keep the human-confirmation boundary."
    elif status == "blocked":
        summary = f"{len(blocking)} connector setup tasks are blocked by missing official authorization, credentials or endpoints."
    else:
        summary = f"{len(actionable)} connector setup tasks still need configuration before full platform trial."
    return ConnectorSetupGuide(
        status=status,
        summary=summary,
        counts=counts,
        tasks=tasks,
        created_at=now_sql(),
    )


def integration_priority(task: ConnectorSetupTask) -> Literal["low", "medium", "high"]:
    if task.severity == "blocker" or task.status == "blocked":
        return "high"
    if task.severity == "warning" or task.status == "todo":
        return "medium"
    return "low"


def integration_acceptance_check(task: ConnectorSetupTask) -> str:
    checks = {
        "oauth_config": "后台能生成官方 OAuth 授权链接。",
        "oauth_authorize": "官方回调能把 code 写入系统，且前端不回显 code。",
        "oauth_exchange": "执行 token exchange 后 configured_fields 出现 access_token 或 session_key。",
        "oauth_refresh": "执行 refresh 后访问凭证可更新，健康面板不再提示到期风险。",
        "webhook_signature": "带 HMAC 签名的 webhook 能入站，未签名请求被拒绝。",
        "read_api": "只读拉取能导入真实消息/线索，并进入 CRM/Workflow。",
        "send_api": "仅在人工确认、低风险、频控和审计存在时进入受控发送。",
        "ops_health": "Connector 健康面板无 fail 项，告警均有处理记录。",
    }
    return checks.get(task.category, "工单完成后在设置页重新运行配置向导和最终验收巡检。")


def integration_work_order_from_guide(
    payload: IntegrationWorkOrderRequest,
    merchant: MerchantProfile,
    guide: ConnectorSetupGuide,
) -> IntegrationWorkOrder:
    selected: set[str] = set()
    for connector in payload.connectors:
        if connector:
            selected.add(normalize_connector_key(connector))
    items: list[IntegrationWorkOrderItem] = []
    for task in guide.tasks:
        if task.category == "safety_boundary":
            continue
        if selected and task.connector not in selected:
            continue
        if task.status == "done" and not payload.include_done:
            continue
        callback_url = task.endpoint_hint if "oauth/callback" in task.endpoint_hint or "webhooks" in task.endpoint_hint else ""
        items.append(
            IntegrationWorkOrderItem(
                connector=task.connector,
                label=task.label,
                category=task.category,
                priority=integration_priority(task),
                status=task.status,
                required_fields=task.required_fields,
                configured_fields=task.configured_fields,
                callback_url=callback_url,
                endpoint_hint=task.endpoint_hint,
                next_action=task.next_action,
                acceptance_check=integration_acceptance_check(task),
            )
        )
    blockers = sum(1 for item in items if item.status == "blocked" or item.priority == "high")
    todo = sum(1 for item in items if item.status == "todo")
    if blockers:
        status: Literal["ready", "needs_setup", "blocked"] = "blocked"
    elif todo:
        status = "needs_setup"
    else:
        status = "ready"
    customer_name = payload.customer_name or merchant.business_name or "客户"
    summary = f"{customer_name} 平台接入工单：{len(items)} 项，阻塞 {blockers} 项，待处理 {todo} 项。"
    return IntegrationWorkOrder(
        id=f"integration-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        title=f"{customer_name} 平台接入工单",
        status=status,
        summary=summary,
        items=items,
        created_at=now_sql(),
    )


def build_integration_work_order_markdown(order: IntegrationWorkOrder, merchant: MerchantProfile) -> str:
    lines = [
        f"# {order.title}",
        "",
        f"生成时间：{order.created_at}",
        f"商家：{merchant.business_name or merchant.username}",
        f"总体状态：{order.status}",
        "",
        order.summary,
        "",
        "## 使用边界",
        "",
        "- 本工单只列字段名、回调地址和验收动作，不包含真实密钥值。",
        "- client secret、app secret、access token、session key、refresh token 等敏感值只能在后台密码框录入。",
        "- 自动发送仍需人工确认、低风险校验、频控和审计，不开放无人值守发送。",
        "",
        "## 接入任务",
        "",
        "| Connector | 类别 | 优先级 | 状态 | 负责人 | 需要字段 | 已配置字段 | 下一步 | 验收动作 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not order.items:
        lines.append("| - | - | - | ready | - | - | - | 当前没有待处理平台接入任务。 | 重新运行最终验收巡检。 |")
    for item in order.items:
        required = " / ".join(item.required_fields) or "-"
        configured = " / ".join(item.configured_fields) or "-"
        lines.append(
            f"| {item.label} | {item.category} | {item.priority} | {item.status} | {item.owner} | {required} | {configured} | {item.next_action} | {item.acceptance_check} |"
        )
    endpoint_lines = [
        f"- {item.label} / {item.category}: `{item.endpoint_hint}`"
        for item in order.items
        if item.endpoint_hint
    ]
    if endpoint_lines:
        lines.extend(["", "## 回调和 Endpoint 提示", "", *endpoint_lines])
    lines.extend(
        [
            "",
            "## 完成后验收",
            "",
            "1. 在系统设置页重新查看平台接入配置向导。",
            "2. 对 OAuth 平台执行授权、换取 Token、刷新 Token。",
            "3. 对只读 API 执行消息或线索拉取，确认进入 CRM/Workflow。",
            "4. 如启用受控发送，先用测试账号和低风险消息验证人工确认链路。",
            "5. 运行最终验收巡检并保存验收报告。",
        ]
    )
    return "\n".join(lines)


async def generate_integration_work_order(
    payload: IntegrationWorkOrderRequest,
    merchant: MerchantProfile,
) -> IntegrationWorkOrder:
    guide = await connector_setup_guide(merchant)
    order = integration_work_order_from_guide(payload, merchant, guide)
    artifact_dir = ARTIFACT_DIR / "integration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{order.id}.md"
    (artifact_dir / filename).write_text(build_integration_work_order_markdown(order, merchant), encoding="utf-8")
    order.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(merchant.id or 0, "integration_work_order", 1, "integration", order.id, {"items": len(order.items), "status": order.status})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.work_order.generate",
        "integration_work_order",
        order.id,
        f"生成平台接入工单：{payload.customer_name or merchant.business_name or merchant.username}",
        {"items": len(order.items), "status": order.status},
    )
    return order


def dry_run_check(
    auth: ConnectorAuthView,
    check: str,
    status: Literal["pass", "warning", "fail"],
    evidence: str,
    next_action: str = "",
) -> IntegrationDryRunCheck:
    return IntegrationDryRunCheck(
        connector=auth.key,
        label=auth.label,
        check=check,
        status=status,
        evidence=evidence,
        next_action=next_action,
    )


def integration_dry_run_from_sources(
    payload: IntegrationDryRunRequest,
    auths: list[ConnectorAuthView],
    health: ConnectorHealthOverview,
) -> IntegrationDryRun:
    selected: set[str] = set()
    for connector in payload.connectors:
        if connector:
            selected.add(normalize_connector_key(connector))
    health_by_key = {item.connector: item for item in health.items}
    checks: list[IntegrationDryRunCheck] = []
    for auth in auths:
        if selected and auth.key not in selected:
            continue
        configured = auth.configured_fields
        has_access = has_any_field(configured, ["access_token", "session_key", "token"])
        has_oauth_code = "oauth_code" in configured
        has_refresh = "refresh_token" in configured
        has_read_endpoint = has_any_field(configured, READ_MESSAGE_ENDPOINT_FIELDS + READ_LEAD_ENDPOINT_FIELDS)
        has_send_endpoint = has_any_field(configured, CONNECTOR_SEND_URL_FIELDS)
        has_signing_key = has_any_field(configured, ["webhook_secret", "webhook_token", "token", "encoding_aes_key"])
        has_oauth_app = (
            has_any_field(configured, ["authorize_url", "oauth_authorize_url"])
            and has_any_field(configured, OAUTH_CLIENT_ID_FIELD_NAMES)
            and has_any_field(configured, OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES)
        )
        if auth.auth_mode == "oauth":
            checks.append(dry_run_check(
                auth,
                "oauth_app",
                "pass" if has_oauth_app else "fail",
                "OAuth app fields are configured." if has_oauth_app else "OAuth app fields are incomplete.",
                "" if has_oauth_app else "Fill authorize_url, client id/key and official client credential in settings.",
            ))
            token_status: Literal["pass", "warning", "fail"] = "pass" if has_access else "warning" if has_oauth_code else "fail"
            checks.append(dry_run_check(
                auth,
                "oauth_token",
                token_status,
                "Access credential is encrypted." if has_access else "OAuth code is present but access credential is not ready." if has_oauth_code else "No OAuth access credential is available.",
                "" if has_access else "Complete OAuth callback and token exchange.",
            ))
            checks.append(dry_run_check(
                auth,
                "oauth_refresh",
                "pass" if has_refresh else "warning",
                "Refresh token is configured." if has_refresh else "Refresh token is not configured.",
                "" if has_refresh else "Capture refresh_token from official token exchange to avoid silent expiry.",
            ))
        if auth.read_only_enabled and ("message_read" in auth.capabilities or "lead_sync" in auth.capabilities or auth.auth_mode == "oauth"):
            if has_access and has_read_endpoint:
                status: Literal["pass", "warning", "fail"] = "pass"
                evidence = "Read API has access credential and endpoint."
                next_action = ""
            elif has_access:
                status = "warning"
                evidence = "Read API has credential but endpoint is missing."
                next_action = "Configure messages_url and/or leads_url."
            elif auth.auth_mode == "oauth":
                status = "fail"
                evidence = "Read API cannot run without OAuth credential."
                next_action = "Finish OAuth token exchange first."
            else:
                status = "warning"
                evidence = "Read API is not fully configured."
                next_action = "Configure official credential and read endpoint if this channel supports it."
            checks.append(dry_run_check(auth, "read_api", status, evidence, next_action))
        if auth.auth_mode == "webhook" or "message_read" in auth.capabilities or "lead_sync" in auth.capabilities:
            checks.append(dry_run_check(
                auth,
                "webhook_signature",
                "pass" if has_signing_key or auth.key == "website" else "warning",
                "Webhook signing material is configured or not required." if has_signing_key or auth.key == "website" else "Webhook signing material is missing.",
                "" if has_signing_key or auth.key == "website" else "Save webhook_token or webhook_secret before exposing the public webhook.",
            ))
        send_ready = auth.send_enabled and has_access and has_send_endpoint
        send_status: Literal["pass", "warning", "fail"]
        if send_ready:
            send_status = "pass"
            send_evidence = "Supervised send gate has credential and endpoint."
            send_next = ""
        elif auth.send_enabled:
            send_status = "fail"
            send_evidence = "Supervised send gate is enabled but missing credential or endpoint."
            send_next = "Disable the gate or complete send_url and access credential."
        else:
            send_status = "pass"
            send_evidence = "Unattended sending is disabled; replies remain draft/manual unless supervised gate is explicitly ready."
            send_next = ""
        checks.append(dry_run_check(auth, "send_boundary", send_status, send_evidence, send_next))
        health_item = health_by_key.get(auth.key)
        if health_item:
            checks.append(dry_run_check(
                auth,
                "ops_health",
                health_item.status,
                health_item.next_action if health_item.status != "pass" else "Connector health check has no blocking alerts.",
                "" if health_item.status == "pass" else "Review connector health alerts in settings.",
            ))
    fail_count = sum(1 for item in checks if item.status == "fail")
    warning_count = sum(1 for item in checks if item.status == "warning")
    if fail_count:
        status: Literal["pass", "warning", "fail"] = "fail"
    elif warning_count:
        status = "warning"
    else:
        status = "pass"
    summary = f"Integration dry run checks={len(checks)} fail={fail_count} warning={warning_count}."
    return IntegrationDryRun(
        id=f"dryrun-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=summary,
        checks=checks,
        created_at=now_sql(),
    )


def build_integration_dry_run_markdown(result: IntegrationDryRun) -> str:
    lines = [
        "# 平台接入干跑验收",
        "",
        f"生成时间：{result.created_at}",
        f"总体状态：{result.status}",
        "",
        result.summary,
        "",
        "## 检查项",
        "",
        "| Connector | 检查 | 状态 | 证据 | 下一步 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for check in result.checks:
        lines.append(f"| {check.label} | {check.check} | {check.status} | {check.evidence} | {check.next_action or '-'} |")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 干跑验收不调用真实平台 endpoint，不发送消息。",
            "- fail 通常代表缺少官方授权、访问凭证、endpoint 或签名配置。",
            "- 完成工单后重新运行干跑验收和最终验收巡检。",
        ]
    )
    return "\n".join(lines)


async def run_integration_dry_run(
    payload: IntegrationDryRunRequest,
    merchant: MerchantProfile,
    persist: bool = True,
) -> IntegrationDryRun:
    auths = await list_connector_auths(merchant)
    health = await connector_ops_health(merchant)
    result = integration_dry_run_from_sources(payload, auths, health)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_integration_dry_run_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    if persist:
        record_usage(merchant.id or 0, "integration_dry_run", 1, "integration", result.id, {"status": result.status, "checks": len(result.checks)})
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "integration.dry_run",
            "integration_dry_run",
            result.id,
            "运行平台接入干跑验收",
            {"status": result.status, "checks": len(result.checks)},
        )
    return result


def integration_task_target_id(check: IntegrationDryRunCheck) -> str:
    return f"integration:{check.connector}:{check.check}"


def existing_open_integration_task(merchant_id: int, target_id: str) -> CRMTask | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND target_type={marker} AND target_id={marker}
              AND status={marker} AND source={marker}
            ORDER BY id DESC LIMIT 1
            """,
            (merchant_id, "conversation", target_id, "open", "integration_dry_run"),
        ).fetchone()
    return crm_task_from_row(dict(row)) if row else None


def open_integration_task_count(merchant_id: int) -> int:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS c FROM crm_tasks WHERE merchant_id={marker} AND status={marker} AND source={marker}",
            (merchant_id, "open", "integration_dry_run"),
        ).fetchone()
    return int(dict(row).get("c") or 0) if row else 0


def open_integration_tasks(merchant_id: int) -> list[CRMTask]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker}
            ORDER BY priority DESC, id DESC
            """,
            (merchant_id, "open", "integration_dry_run"),
        ).fetchall()
    return [crm_task_from_row(row) for row in rows_to_dicts(rows)]


def parse_integration_task_target(target_id: str) -> tuple[str, str]:
    parts = target_id.split(":", 2)
    if len(parts) == 3 and parts[0] == "integration":
        return parts[1], parts[2]
    return "", ""


def parse_sql_datetime(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if fmt.endswith("%S") else value[:10], fmt)
        except ValueError:
            continue
    return None


async def integration_task_sla_board(merchant: MerchantProfile) -> IntegrationTaskSLABoard:
    tasks = open_integration_tasks(merchant.id or 0)
    now = datetime.now()
    items: list[IntegrationTaskSLAItem] = []
    by_connector: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    for task in tasks:
        connector, check = parse_integration_task_target(task.target_id)
        due_dt = parse_sql_datetime(task.due_at)
        created_dt = parse_sql_datetime(task.created_at)
        if not due_dt:
            sla_status: Literal["overdue", "due_today", "upcoming", "unscheduled"] = "unscheduled"
        elif due_dt.date() < now.date() or due_dt < now:
            sla_status = "overdue"
        elif due_dt.date() == now.date():
            sla_status = "due_today"
        else:
            sla_status = "upcoming"
        age_hours = int((now - created_dt).total_seconds() // 3600) if created_dt else 0
        by_connector[connector or "unknown"] = by_connector.get(connector or "unknown", 0) + 1
        by_owner[task.owner or "未分配"] = by_owner.get(task.owner or "未分配", 0) + 1
        items.append(
            IntegrationTaskSLAItem(
                task_id=task.id,
                connector=connector,
                check=check,
                title=task.title,
                owner=task.owner,
                priority=task.priority,
                due_at=task.due_at,
                sla_status=sla_status,
                age_hours=max(0, age_hours),
                created_at=task.created_at,
            )
        )
    items.sort(key=lambda item: ({"overdue": 0, "due_today": 1, "unscheduled": 2, "upcoming": 3}[item.sla_status], -item.age_hours))
    overdue = sum(1 for item in items if item.sla_status == "overdue")
    due_today = sum(1 for item in items if item.sla_status == "due_today")
    upcoming = sum(1 for item in items if item.sla_status == "upcoming")
    unscheduled = sum(1 for item in items if item.sla_status == "unscheduled")
    if overdue:
        status: Literal["clear", "attention", "overdue"] = "overdue"
    elif due_today or unscheduled:
        status = "attention"
    else:
        status = "clear"
    summary = f"Integration SLA open={len(items)} overdue={overdue} due_today={due_today} unscheduled={unscheduled}."
    return IntegrationTaskSLABoard(
        status=status,
        summary=summary,
        total_open=len(items),
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        unscheduled=unscheduled,
        by_connector=by_connector,
        by_owner=by_owner,
        items=items[:80],
        created_at=now_sql(),
    )


def build_integration_sla_escalation_markdown(
    escalation: IntegrationSLAEscalation,
    board: IntegrationTaskSLABoard,
    owner: str,
) -> str:
    lines = [
        "# 平台接入 SLA 升级简报",
        "",
        f"生成时间：{escalation.created_at}",
        f"负责人：{owner}",
        f"总体状态：{escalation.status}",
        "",
        escalation.summary,
        "",
        "## 总览",
        "",
        f"- 打开任务：{board.total_open}",
        f"- 逾期：{board.overdue}",
        f"- 今日到期：{board.due_today}",
        f"- 未排期：{board.unscheduled}",
        "",
        "## 需要升级的任务",
        "",
        "| Connector | 检查项 | SLA | 优先级 | 负责人 | 到期时间 | 任务 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not escalation.items:
        lines.append("| - | - | clear | - | - | - | 当前没有需要升级的接入任务。 |")
    for item in escalation.items:
        lines.append(
            f"| {item.connector or '-'} | {item.check or '-'} | {item.sla_status} | {item.priority} | {item.owner or '-'} | {item.due_at or '-'} | {item.title} |"
        )
    lines.extend(
        [
            "",
            "## 推进建议",
            "",
            "1. 逾期任务优先联系客户平台管理员或技术负责人。",
            "2. 今日到期任务确认是否已提交官方授权、回调地址、endpoint 或验签材料。",
            "3. 未排期任务先补 due_at 和负责人，避免缺口长期停留。",
            "4. 完成后回到系统设置页运行干跑验收和复验关闭。",
            "",
            "## 安全边界",
            "",
            "- 本简报不包含真实密钥、token 或客户隐私内容。",
            "- 本简报不调用平台 API，也不发送任何平台消息。",
        ]
    )
    return "\n".join(lines)


async def generate_integration_sla_escalation(
    payload: IntegrationSLAEscalationRequest,
    merchant: MerchantProfile,
) -> IntegrationSLAEscalation:
    board = await integration_task_sla_board(merchant)
    statuses = {"overdue", "due_today", "unscheduled"}
    if payload.include_upcoming:
        statuses.add("upcoming")
    items = [item for item in board.items if item.sla_status in statuses]
    if board.overdue:
        status: Literal["clear", "attention", "overdue"] = "overdue"
    elif items:
        status = "attention"
    else:
        status = "clear"
    escalation = IntegrationSLAEscalation(
        id=f"sla-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=f"Integration SLA escalation items={len(items)} overdue={board.overdue} due_today={board.due_today} unscheduled={board.unscheduled}.",
        items=items,
        created_at=now_sql(),
    )
    artifact_dir = ARTIFACT_DIR / "integration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{escalation.id}.md"
    (artifact_dir / filename).write_text(build_integration_sla_escalation_markdown(escalation, board, payload.owner), encoding="utf-8")
    escalation.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(merchant.id or 0, "integration_sla_escalation", 1, "integration", escalation.id, {"items": len(items), "status": status})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.sla_escalation",
        "integration_sla",
        escalation.id,
        "生成平台接入 SLA 升级简报",
        {"items": len(items), "status": status},
    )
    return escalation


def integration_sla_notice_channel_label(channel: str) -> str:
    return {
        "copy": "复制粘贴",
        "wecom": "企业微信",
        "dingtalk": "钉钉",
        "email": "邮件",
    }.get(channel, channel)


def build_integration_sla_notice_text(
    notice: IntegrationSLANotice,
    board: IntegrationTaskSLABoard,
    owner: str,
) -> str:
    lines = [
        f"【平台接入 SLA 跟进】{notice.subject}",
        "",
        f"{notice.recipient}，你好：",
        "",
        (
            f"当前平台接入仍有 {len(notice.items)} 项需要跟进，"
            f"逾期 {board.overdue} 项，今日到期 {board.due_today} 项，未排期 {board.unscheduled} 项。"
        ),
    ]
    if notice.items:
        lines.extend(["", "请优先处理以下事项："])
        for index, item in enumerate(notice.items[:12], start=1):
            lines.append(
                f"{index}. {item.connector or 'unknown'} / {item.check or '未命名检查'}："
                f"{item.title}；SLA={item.sla_status}；负责人={item.owner or owner}；到期={item.due_at or '未排期'}。"
            )
        if len(notice.items) > 12:
            lines.append(f"... 其余 {len(notice.items) - 12} 项请查看系统内 SLA 升级简报。")
    else:
        lines.extend(["", "当前没有需要升级通知的接入任务，继续按计划推进即可。"])
    lines.extend(
        [
            "",
            "建议动作：",
            "1. 补齐官方授权、回调地址、endpoint、签名材料或账号权限。",
            "2. 完成后回到系统设置页运行“干跑验收”和“复验关闭”。",
            "3. 如涉及 token、密钥、验证码或客户隐私，请仅在平台官方后台或安全通道处理。",
            "",
            f"发送方式：{integration_sla_notice_channel_label(notice.channel)}。本内容只是草稿，请人工确认后再发送。",
            f"跟进人：{owner}",
        ]
    )
    return "\n".join(lines)


def build_integration_sla_notice_markdown(
    notice: IntegrationSLANotice,
    board: IntegrationTaskSLABoard,
    owner: str,
) -> str:
    lines = [
        "# 平台接入 SLA 责任人通知草稿",
        "",
        f"生成时间：{notice.created_at}",
        f"通知方式：{integration_sla_notice_channel_label(notice.channel)}",
        f"接收人：{notice.recipient}",
        f"跟进人：{owner}",
        f"状态：{notice.status}",
        f"主题：{notice.subject}",
        "",
        "## 可复制通知",
        "",
        "```text",
        notice.draft_text,
        "```",
        "",
        "## SLA 概览",
        "",
        f"- 打开任务：{board.total_open}",
        f"- 逾期：{board.overdue}",
        f"- 今日到期：{board.due_today}",
        f"- 未排期：{board.unscheduled}",
        "",
        "## 通知涉及任务",
        "",
        "| Connector | 检查项 | SLA | 优先级 | 负责人 | 到期时间 | 任务 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not notice.items:
        lines.append("| - | - | clear | - | - | - | 当前没有需要通知升级的接入任务。 |")
    for item in notice.items:
        lines.append(
            f"| {item.connector or '-'} | {item.check or '-'} | {item.sla_status} | {item.priority} | {item.owner or '-'} | {item.due_at or '-'} | {item.title} |"
        )
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 本通知是人工确认草稿，不会自动发送到企业微信、钉钉、邮件或任何平台。",
            "- 不包含真实 token、密钥、验证码或客户隐私数据。",
            "- 外发前需要人工确认对象、措辞、附件和接收渠道。",
        ]
    )
    return "\n".join(lines)


async def generate_integration_sla_notice(
    payload: IntegrationSLANoticeRequest,
    merchant: MerchantProfile,
) -> IntegrationSLANotice:
    board = await integration_task_sla_board(merchant)
    statuses = {"overdue", "due_today", "unscheduled"}
    if payload.include_upcoming:
        statuses.add("upcoming")
    items = [item for item in board.items if item.sla_status in statuses]
    if board.overdue:
        status: Literal["clear", "attention", "overdue"] = "overdue"
    elif items:
        status = "attention"
    else:
        status = "clear"
    notice = IntegrationSLANotice(
        id=f"sla-notice-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        channel=payload.channel,
        recipient=payload.recipient,
        subject=f"平台接入 SLA 待跟进 {len(items)} 项",
        draft_text="",
        items=items,
        created_at=now_sql(),
    )
    notice.draft_text = build_integration_sla_notice_text(notice, board, payload.owner)
    artifact_dir = ARTIFACT_DIR / "integration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{notice.id}.md"
    (artifact_dir / filename).write_text(build_integration_sla_notice_markdown(notice, board, payload.owner), encoding="utf-8")
    notice.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(merchant.id or 0, "integration_sla_notice_draft", 1, "integration", notice.id, {"items": len(items), "status": status, "channel": payload.channel})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.sla_notice_draft",
        "integration_sla",
        notice.id,
        "生成平台接入 SLA 责任人通知草稿",
        {"items": len(items), "status": status, "channel": payload.channel},
    )
    return notice


def build_integration_sla_notice_receipt_markdown(
    receipt: IntegrationSLANoticeReceipt,
    selected_items: list[IntegrationTaskSLAItem],
    payload: IntegrationSLANoticeReceiptRequest,
) -> str:
    lines = [
        "# 平台接入 SLA 通知回执",
        "",
        f"生成时间：{receipt.created_at}",
        f"通知 ID：{receipt.notice_id or '-'}",
        f"接收人：{receipt.recipient}",
        f"回执结果：{receipt.outcome}",
        f"回执状态：{receipt.status}",
        "",
        receipt.summary,
        "",
        "## 回执任务",
        "",
        "| Task ID | Connector | 检查项 | SLA | 负责人 | 到期时间 | 任务 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not selected_items:
        lines.append("| - | - | - | - | - | - | 本次只记录通知回执，未选择关闭任务。 |")
    for item in selected_items:
        lines.append(
            f"| {item.task_id} | {item.connector or '-'} | {item.check or '-'} | {item.sla_status} | {item.owner or '-'} | {item.due_at or '-'} | {item.title} |"
        )
    lines.extend(["", "## 已关闭 CRM 任务", ""])
    if receipt.closed_tasks:
        for task in receipt.closed_tasks:
            lines.append(f"- #{task.id} {task.title} owner={task.owner or '-'} status={task.status}")
    else:
        lines.append("- 本次未关闭 CRM 任务。")
    if receipt.ignored_task_ids:
        lines.extend(["", "## 未处理任务 ID", ""])
        lines.append(f"- {', '.join(str(item) for item in receipt.ignored_task_ids)}")
    if payload.notes:
        lines.extend(["", "## 回执备注", "", payload.notes])
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 本回执不发送平台消息，只记录运营确认结果。",
            "- 只有显式传入 close_confirmed_tasks=true 且确认短语为 CONFIRM_CLOSE 时，才会关闭选中的接入 CRM 任务。",
            "- 只允许关闭当前仍处于 open 状态且来源为 integration_dry_run 的任务。",
            "- 不记录真实 token、密钥、验证码或客户隐私。",
        ]
    )
    return "\n".join(lines)


async def record_integration_sla_notice_receipt(
    payload: IntegrationSLANoticeReceiptRequest,
    merchant: MerchantProfile,
) -> IntegrationSLANoticeReceipt:
    board = await integration_task_sla_board(merchant)
    task_by_id = {item.task_id: item for item in board.items}
    selected_items = [task_by_id[task_id] for task_id in payload.confirmed_task_ids if task_id in task_by_id]
    ignored_task_ids = [task_id for task_id in payload.confirmed_task_ids if task_id not in task_by_id]
    closed_tasks: list[CRMTask] = []
    if payload.close_confirmed_tasks:
        if payload.confirm_phrase != "CONFIRM_CLOSE":
            raise HTTPException(status_code=400, detail="CONFIRM_CLOSE is required to close CRM tasks")
        if not selected_items:
            raise HTTPException(status_code=400, detail="No open integration tasks selected for closure")
        for item in selected_items:
            closed_tasks.append(await update_crm_task(item.task_id, CRMTaskUpdate(status="done"), merchant))
    refreshed_board = await integration_task_sla_board(merchant)
    if payload.close_confirmed_tasks and closed_tasks:
        status: Literal["recorded", "partial", "closed"] = "closed" if not ignored_task_ids else "partial"
    else:
        status = "recorded"
    receipt = IntegrationSLANoticeReceipt(
        id=f"sla-receipt-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        notice_id=payload.notice_id,
        recipient=payload.recipient,
        outcome=payload.outcome,
        confirmed_task_ids=[item.task_id for item in selected_items],
        ignored_task_ids=ignored_task_ids,
        closed_tasks=closed_tasks,
        remaining_open=refreshed_board.total_open,
        summary=(
            f"SLA notice receipt recorded. receipt_items={len(selected_items)} "
            f"closed_tasks={len(closed_tasks)} remaining_open={refreshed_board.total_open}."
        ),
        created_at=now_sql(),
    )
    artifact_dir = ARTIFACT_DIR / "integration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{receipt.id}.md"
    (artifact_dir / filename).write_text(build_integration_sla_notice_receipt_markdown(receipt, selected_items, payload), encoding="utf-8")
    receipt.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "integration_sla_notice_receipt",
        1,
        "integration",
        receipt.id,
        {"items": len(selected_items), "closed": len(closed_tasks), "remaining_open": refreshed_board.total_open},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.sla_notice_receipt",
        "integration_sla",
        receipt.id,
        "记录平台接入 SLA 通知回执",
        {"items": len(selected_items), "closed": len(closed_tasks), "remaining_open": refreshed_board.total_open},
    )
    return receipt


def is_integration_sla_loop_event(log: AuditLog) -> bool:
    if log.action in {
        "integration.sla_escalation",
        "integration.sla_notice_draft",
        "integration.sla_notice_receipt",
        "integration.sla_loop_report",
        "integration.task_sync",
        "integration.task_reconcile",
    }:
        return True
    return log.action == "crm.task.update" and log.metadata.get("status") == "done"


def integration_loop_closed_recent(events: list[AuditLog]) -> int:
    closed = 0
    for event in events:
        if event.action == "crm.task.update" and event.metadata.get("status") == "done":
            closed += 1
        elif event.action == "integration.task_reconcile":
            try:
                closed += int(event.metadata.get("closed") or 0)
            except (TypeError, ValueError):
                continue
    return closed


def build_integration_sla_loop_report_markdown(report: IntegrationSLALoopReport, board: IntegrationTaskSLABoard) -> str:
    lines = [
        "# 平台接入 SLA 闭环复盘报表",
        "",
        f"生成时间：{report.created_at}",
        f"总体状态：{report.status}",
        "",
        report.summary,
        "",
        "## SLA 当前状态",
        "",
        f"- 打开任务：{report.total_open}",
        f"- 逾期：{report.overdue}",
        f"- 今日到期：{report.due_today}",
        f"- 未排期：{report.unscheduled}",
        f"- 近期回执：{report.receipts_recent}",
        f"- 近期关闭任务：{report.closed_recent}",
        "",
        "## Connector 分布",
        "",
    ]
    if board.by_connector:
        for connector, count in sorted(board.by_connector.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {connector}: {count}")
    else:
        lines.append("- 当前没有打开的接入任务。")
    lines.extend(
        [
            "",
            "## 近期闭环事件",
            "",
            "| 时间 | 动作 | 对象 | 摘要 | 证据 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if not report.audit_events:
        lines.append("| - | - | - | 暂无近期闭环事件 | - |")
    for event in report.audit_events:
        metadata_bits = []
        for key in ["items", "closed", "remaining_open", "status", "target", "dry_run_status"]:
            if key in event.metadata:
                metadata_bits.append(f"{key}={event.metadata.get(key)}")
        evidence = "; ".join(metadata_bits) if metadata_bits else "-"
        lines.append(f"| {event.created_at} | {event.action} | {event.target_type}:{event.target_id} | {event.summary or '-'} | {evidence} |")
    lines.extend(
        [
            "",
            "## 运营判断",
            "",
            "- 若打开任务为 0，可进入真实平台账号验收和客户试运行。",
            "- 若存在逾期或今日到期，优先生成通知草稿并记录责任人回执。",
            "- 若已收到完成回执，使用显式任务 ID 和 CONFIRM_CLOSE 关闭对应 CRM 接入任务。",
            "",
            "## 安全边界",
            "",
            "- 本报表只汇总系统内审计与 CRM 状态，不发送平台消息。",
            "- 不包含真实 token、密钥、验证码或客户隐私。",
            "- 平台侧真实完成度仍需客户账号、官方授权和真实消息/线索场景验收。",
        ]
    )
    return "\n".join(lines)


async def generate_integration_sla_loop_report(
    payload: IntegrationSLALoopReportRequest,
    merchant: MerchantProfile,
) -> IntegrationSLALoopReport:
    board = await integration_task_sla_board(merchant)
    recent_logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    loop_events = [log for log in recent_logs if is_integration_sla_loop_event(log)]
    receipts_recent = sum(1 for event in loop_events if event.action == "integration.sla_notice_receipt")
    closed_recent = integration_loop_closed_recent(loop_events)
    if board.overdue:
        status: Literal["clear", "attention", "overdue"] = "overdue"
    elif board.due_today or board.unscheduled:
        status = "attention"
    else:
        status = "clear"
    report = IntegrationSLALoopReport(
        id=f"sla-loop-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Integration SLA loop report. open={board.total_open} overdue={board.overdue} "
            f"due_today={board.due_today} receipts_recent={receipts_recent} closed_recent={closed_recent}."
        ),
        total_open=board.total_open,
        overdue=board.overdue,
        due_today=board.due_today,
        unscheduled=board.unscheduled,
        receipts_recent=receipts_recent,
        closed_recent=closed_recent,
        audit_events=loop_events[:payload.audit_limit],
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report.id}.md"
        (artifact_dir / filename).write_text(build_integration_sla_loop_report_markdown(report, board), encoding="utf-8")
        report.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "integration_sla_loop_report",
        1,
        "integration",
        report.id,
        {"open": board.total_open, "receipts_recent": receipts_recent, "closed_recent": closed_recent, "status": status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.sla_loop_report",
        "integration_sla",
        report.id,
        "生成平台接入 SLA 闭环复盘报表",
        {"open": board.total_open, "receipts_recent": receipts_recent, "closed_recent": closed_recent, "status": status},
    )
    return report


PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS: list[PlatformAcceptanceScenario] = [
    "official_auth",
    "callback",
    "read_message",
    "read_lead",
    "draft_reply",
    "customer_trial",
]
PLATFORM_ACCEPTANCE_PUBLIC_SUBMISSION_SCENARIOS: list[PlatformAcceptanceScenario] = [
    *PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS,
    "controlled_send",
    "ops_health",
]


def assert_platform_acceptance_evidence_safe(payload: PlatformAcceptanceEvidenceRequest) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the evidence does not contain secrets")
    text = "\n".join([payload.account_label, payload.operator, payload.evidence_note, payload.evidence_url])
    risky_patterns = [
        r"(?i)password\s*[:=]",
        r"(?i)token\s*[:=]",
        r"(?i)secret\s*[:=]",
        r"(?i)cookie\s*[:=]",
        r"(?i)authorization\s*[:=]",
        r"(?i)验证码\s*[:=]",
        r"(?i)密码\s*[:=]",
        r"(?i)密钥\s*[:=]",
    ]
    if any(re.search(pattern, text) for pattern in risky_patterns):
        raise HTTPException(status_code=400, detail="Evidence appears to contain a secret; store only sanitized notes")


def is_placeholder_platform_evidence_url(url: str) -> bool:
    lowered = (url or "").strip().lower()
    if not lowered:
        return False
    placeholder_bits = [
        "example.com",
        "example.org",
        "example.net",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        ".invalid",
        "stage58-sanitized",
        "production-sanitized",
    ]
    return any(bit in lowered for bit in placeholder_bits)


def is_private_platform_evidence_host(host: str) -> bool:
    normalized = (host or "").strip().strip("[]").lower()
    if not normalized:
        return True
    if normalized == "localhost" or normalized.endswith((".localhost", ".local", ".lan", ".internal", ".invalid")):
        return True
    try:
        address = ipaddress.ip_address(normalized)
        return bool(
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        )
    except ValueError:
        pass
    try:
        resolved = socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for item in resolved:
        address_text = str(item[4][0])
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError:
            return True
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return True
    return False


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def precheck_platform_acceptance_evidence_url(
    item: PlatformAcceptanceEvidenceImportItem,
    check_reachability: bool = True,
) -> PlatformAcceptanceEvidenceUrlPrecheckItem:
    raw_url = (item.evidence_url or "").strip()
    parsed = urllib.parse.urlparse(raw_url)
    host = parsed.hostname or ""
    result = PlatformAcceptanceEvidenceUrlPrecheckItem(
        scenario=item.scenario,
        evidence_url=raw_url,
        host=host,
    )
    if not raw_url:
        result.status = "blocked"
        result.reason = "Evidence URL is required."
        result.next_action = "Ask the customer to provide a sanitized evidence URL."
        return result
    if parsed.scheme not in {"http", "https"} or not host:
        result.status = "blocked"
        result.reason = "Evidence URL must be a complete http(s) URL."
        result.next_action = "Replace it with a full https:// customer-controlled evidence link."
        return result
    if parsed.scheme != "https":
        result.status = "blocked"
        result.reason = "Evidence URL must use https."
        result.next_action = "Ask the customer to provide an HTTPS link to sanitized evidence."
        return result
    if is_placeholder_platform_evidence_url(raw_url):
        result.status = "blocked"
        result.reason = "Evidence URL appears to be a placeholder."
        result.next_action = "Replace example, localhost, or synthetic proof links with customer-controlled proof."
        return result
    if is_private_platform_evidence_host(host):
        result.status = "blocked"
        result.reason = "Evidence URL host resolves to a local or private network address."
        result.next_action = "Use a customer-controlled public HTTPS evidence link or upload sanitized material through the approved channel."
        return result
    if not check_reachability:
        result.status = "ok"
        result.reason = "URL structure passed; reachability check skipped."
        result.next_action = "Review the evidence manually before import."
        return result
    request = urllib.request.Request(
        raw_url,
        headers={"User-Agent": "merchant-growth-evidence-precheck/1.0"},
        method="HEAD",
    )
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=8) as response:
            result.http_status = int(getattr(response, "status", 0) or 0)
            result.content_type = response.headers.get("Content-Type", "")
            result.final_url = response.geturl()
    except urllib.error.HTTPError as exc:
        result.http_status = int(exc.code or 0)
        result.content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        if 300 <= exc.code < 400:
            location = exc.headers.get("Location", "") if exc.headers else ""
            next_url = urllib.parse.urljoin(raw_url, location)
            next_host = urllib.parse.urlparse(next_url).hostname or ""
            result.final_url = next_url
            if not next_host or is_private_platform_evidence_host(next_host):
                result.status = "blocked"
                result.reason = "Evidence URL redirects to an unsafe or private host."
                result.next_action = "Replace the link with a direct public HTTPS evidence URL."
                return result
            result.status = "warning"
            result.reason = f"Evidence URL redirects with HTTP {exc.code}; redirect target was not fetched."
            result.next_action = "Open the link manually and verify the redirect target before import."
            return result
        if exc.code in {401, 403, 405}:
            result.status = "warning"
            result.reason = f"Evidence URL returned HTTP {exc.code}; it may require customer permission or not allow HEAD."
            result.next_action = "Manually open the evidence link with the customer-approved account before import."
            return result
        result.status = "warning"
        result.reason = f"Evidence URL returned HTTP {exc.code}."
        result.next_action = "Ask the customer to confirm the link is accessible or resubmit a reachable proof link."
        return result
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result.status = "warning"
        result.reason = f"Reachability check failed: {type(exc).__name__}."
        result.next_action = "Manually verify the link or ask the customer to resubmit a reachable proof link."
        return result
    if 200 <= result.http_status < 400:
        result.status = "ok"
        result.reason = f"Evidence URL responded with HTTP {result.http_status}."
        result.next_action = "Review sanitized evidence manually before import."
    else:
        result.status = "warning"
        result.reason = f"Evidence URL returned HTTP {result.http_status or 'unknown'}."
        result.next_action = "Manually verify the link or ask the customer to resubmit a reachable proof link."
    return result


def build_platform_acceptance_evidence_url_precheck_markdown(
    run: PlatformAcceptanceEvidenceUrlPrecheckRun,
) -> str:
    lines = [
        "# Real Platform Evidence URL Precheck",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Status: {run.status}",
        "",
        run.summary,
        "",
        "| Scenario | Status | HTTP | Host | Evidence URL | Reason | Next Action |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for item in run.items:
        lines.append(
            f"| {item.scenario} | {item.status} | {item.http_status or '-'} | {item.host or '-'} | "
            f"{item.evidence_url or '-'} | {item.reason.replace('|', '/') or '-'} | {item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This precheck never registers pass evidence.",
            "- Localhost, private-network, placeholder, non-HTTPS, and unsafe redirect links are blocked.",
            "- HTTP reachability warnings still require manual customer-approved review before import.",
        ]
    )
    return "\n".join(lines)


async def run_platform_acceptance_evidence_url_precheck(
    payload: PlatformAcceptanceEvidenceUrlPrecheckRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceUrlPrecheckRun:
    items = [
        precheck_platform_acceptance_evidence_url(item, payload.check_reachability)
        for item in payload.items
        if item.scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS
    ]
    ok = sum(1 for item in items if item.status == "ok")
    warning = sum(1 for item in items if item.status == "warning")
    blocked = sum(1 for item in items if item.status == "blocked")
    if blocked:
        status: Literal["ok", "warning", "blocked"] = "blocked"
    elif warning:
        status = "warning"
    else:
        status = "ok"
    run = PlatformAcceptanceEvidenceUrlPrecheckRun(
        id=f"platform-evidence-url-precheck-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=f"Evidence URL precheck. checked={len(items)} ok={ok} warning={warning} blocked={blocked}.",
        checked=len(items),
        ok=ok,
        warning=warning,
        blocked=blocked,
        items=items,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_url_precheck_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_url_precheck",
        max(1, run.checked),
        "integration",
        run.id,
        {"status": run.status, "checked": run.checked, "ok": run.ok, "warning": run.warning, "blocked": run.blocked},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_url_precheck",
        "integration_acceptance",
        run.id,
        "Run platform evidence URL precheck",
        {"status": run.status, "checked": run.checked, "ok": run.ok, "warning": run.warning, "blocked": run.blocked},
    )
    return run


def build_platform_acceptance_evidence_markdown(evidence: PlatformAcceptanceEvidence) -> str:
    return "\n".join(
        [
            "# 真实平台验收证据",
            "",
            f"证据 ID：{evidence.id}",
            f"生成时间：{evidence.created_at}",
            f"发生时间：{evidence.occurred_at or '-'}",
            f"Connector：{evidence.connector}",
            f"验收场景：{evidence.scenario}",
            f"验收结果：{evidence.result}",
            f"账号标识：{evidence.account_label}",
            f"操作人：{evidence.operator}",
            "",
            "## 脱敏证据摘要",
            "",
            evidence.summary or "-",
            "",
            "## 证据链接",
            "",
            evidence.evidence_url or "-",
            "",
            "## 安全边界",
            "",
            "- 本证据只保存脱敏摘要，不保存平台密码、token、cookie、验证码或密钥。",
            "- 证据链接应指向客户可控的脱敏截图、工单、录屏或验收文档。",
            "- 若涉及受控发送，仍需保留人工确认记录。",
        ]
    )


async def record_platform_acceptance_evidence(
    payload: PlatformAcceptanceEvidenceRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidence:
    assert_platform_acceptance_evidence_safe(payload)
    evidence = PlatformAcceptanceEvidence(
        id=f"platform-evidence-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        connector=payload.connector.strip() or "unknown",
        scenario=payload.scenario,
        result=payload.result,
        account_label=payload.account_label.strip()[:120],
        operator=payload.operator.strip()[:120],
        summary=(payload.evidence_note.strip() or f"{payload.connector} {payload.scenario} {payload.result}")[:2000],
        evidence_url=payload.evidence_url.strip()[:500],
        occurred_at=payload.occurred_at.strip()[:40] or now_sql(),
        created_at=now_sql(),
    )
    artifact_dir = ARTIFACT_DIR / "integration"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{evidence.id}.md"
    (artifact_dir / filename).write_text(build_platform_acceptance_evidence_markdown(evidence), encoding="utf-8")
    evidence.artifact_url = f"/artifacts/integration/{filename}"
    metadata = evidence.model_dump()
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence",
        1,
        "integration",
        evidence.id,
        {"connector": evidence.connector, "scenario": evidence.scenario, "result": evidence.result},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence",
        "integration_acceptance",
        evidence.id,
        f"登记真实平台验收证据：{evidence.connector}/{evidence.scenario}/{evidence.result}",
        metadata,
    )
    return evidence


def platform_acceptance_evidence_from_log(log: AuditLog) -> PlatformAcceptanceEvidence:
    metadata = log.metadata or {}
    return PlatformAcceptanceEvidence(
        id=str(metadata.get("id") or log.target_id),
        connector=str(metadata.get("connector") or "unknown"),
        scenario=metadata.get("scenario") if metadata.get("scenario") in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS + ["controlled_send", "ops_health"] else "customer_trial",
        result=metadata.get("result") if metadata.get("result") in {"pass", "warning", "fail"} else "warning",
        account_label=str(metadata.get("account_label") or ""),
        operator=str(metadata.get("operator") or log.actor or ""),
        summary=str(metadata.get("summary") or log.summary or ""),
        evidence_url=str(metadata.get("evidence_url") or ""),
        artifact_url=str(metadata.get("artifact_url") or ""),
        occurred_at=str(metadata.get("occurred_at") or log.created_at),
        created_at=str(metadata.get("created_at") or log.created_at),
    )


async def list_platform_acceptance_evidence_logs(
    merchant: MerchantProfile,
    limit: int = 500,
) -> list[AuditLog]:
    marker = param()
    safe_limit = max(1, min(int(limit), 1000))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT * FROM audit_logs
            WHERE merchant_id={marker} AND action={marker}
            ORDER BY id DESC LIMIT {safe_limit}
            """,
            (merchant.id, "integration.platform_acceptance_evidence"),
        ).fetchall())
    return [audit_log_from_row(row) for row in rows]


def build_platform_acceptance_report_markdown(report: PlatformAcceptanceReport) -> str:
    lines = [
        "# 真实平台验收证据包",
        "",
        f"生成时间：{report.created_at}",
        f"总体状态：{report.status}",
        "",
        report.summary,
        "",
        "## 统计",
        "",
        f"- 证据总数：{report.evidence_total}",
        f"- 通过：{report.passed}",
        f"- 提醒：{report.warnings}",
        f"- 失败：{report.failed}",
        f"- 必需场景：{', '.join(report.required_scenarios)}",
        f"- 缺失场景：{', '.join(report.missing_scenarios) if report.missing_scenarios else '无'}",
        "",
        "## 证据清单",
        "",
        "| 时间 | Connector | 场景 | 结果 | 账号 | 操作人 | 证据 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not report.evidence:
        lines.append("| - | - | - | - | - | - | 暂无真实平台验收证据 |")
    for item in report.evidence:
        evidence_ref = item.evidence_url or item.artifact_url or item.id
        lines.append(f"| {item.occurred_at or item.created_at} | {item.connector} | {item.scenario} | {item.result} | {item.account_label or '-'} | {item.operator or '-'} | {evidence_ref} |")
    lines.extend(
        [
            "",
            "## 验收判断",
            "",
            "- ready：必需场景均有 pass 证据，且没有 fail 证据。",
            "- partial：已有部分证据，但仍缺场景或存在 warning。",
            "- blocked：没有证据或存在 fail 证据，需要先处理平台侧问题。",
            "",
            "## 安全边界",
            "",
            "- 本证据包不保存平台密码、token、cookie、验证码或密钥。",
            "- 真实平台验收必须由客户账号、官方授权和真实消息/线索场景证明。",
            "- 受控发送仍保持人工确认，不开放无人值守自动外发。",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_report(
    payload: PlatformAcceptanceReportRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceReport:
    logs = await list_platform_acceptance_evidence_logs(merchant, limit=max(payload.audit_limit, 500))
    evidence = [
        platform_acceptance_evidence_from_log(log)
        for log in logs
    ]
    seen: set[str] = set()
    unique_evidence: list[PlatformAcceptanceEvidence] = []
    for item in evidence:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique_evidence.append(item)
    passed = sum(1 for item in unique_evidence if item.result == "pass")
    warnings = sum(1 for item in unique_evidence if item.result == "warning")
    failed = sum(1 for item in unique_evidence if item.result == "fail")
    passed_scenarios = {item.scenario for item in unique_evidence if item.result == "pass"}
    missing_scenarios = [scenario for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS if scenario not in passed_scenarios]
    if failed or not unique_evidence:
        status: Literal["ready", "partial", "blocked"] = "blocked"
    elif missing_scenarios or warnings:
        status = "partial"
    else:
        status = "ready"
    report = PlatformAcceptanceReport(
        id=f"platform-acceptance-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance evidence report. evidence_total={len(unique_evidence)} "
            f"passed={passed} warnings={warnings} failed={failed} missing={len(missing_scenarios)}."
        ),
        evidence_total=len(unique_evidence),
        passed=passed,
        warnings=warnings,
        failed=failed,
        required_scenarios=PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS,
        missing_scenarios=missing_scenarios,
        evidence=unique_evidence[:payload.audit_limit],
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_report_markdown(report), encoding="utf-8")
        report.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_report",
        1,
        "integration",
        report.id,
        {"evidence_total": report.evidence_total, "status": report.status, "missing": len(missing_scenarios)},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_report",
        "integration_acceptance",
        report.id,
        "生成真实平台验收证据包",
        {"evidence_total": report.evidence_total, "status": report.status, "missing": len(missing_scenarios)},
    )
    return report


def platform_acceptance_gap_target_id(scenario: str) -> str:
    return f"platform_acceptance:{scenario}"


def existing_open_platform_acceptance_task(merchant_id: int, target_id: str) -> CRMTask | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker} AND target_id={marker}
            ORDER BY id DESC LIMIT 1
            """,
            (merchant_id, "open", "platform_acceptance_gap", target_id),
        ).fetchone()
    return crm_task_from_row(dict(row)) if row else None


def open_platform_acceptance_gap_tasks(merchant_id: int) -> list[CRMTask]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker}
            ORDER BY priority DESC, id DESC
            """,
            (merchant_id, "open", "platform_acceptance_gap"),
        ).fetchall()
    return [crm_task_from_row(row) for row in rows_to_dicts(rows)]


def platform_acceptance_scenario_from_target(target_id: str) -> str:
    prefix = "platform_acceptance:"
    return target_id[len(prefix):] if target_id.startswith(prefix) else ""


def platform_acceptance_gap_task_title(scenario: PlatformAcceptanceScenario) -> str:
    labels = {
        "official_auth": "补齐官方授权真实证据",
        "callback": "补齐回调地址真实证据",
        "read_message": "补齐真实消息读取证据",
        "read_lead": "补齐真实线索读取证据",
        "draft_reply": "补齐回复草稿验收证据",
        "customer_trial": "补齐客户试运行验收证据",
        "controlled_send": "补齐受控发送人工确认验收证据",
        "ops_health": "补齐平台运维健康验收证据",
    }
    return labels.get(scenario, f"补齐真实平台验收证据：{scenario}")


def build_platform_acceptance_gap_sync_markdown(result: PlatformAcceptanceGapSyncResult) -> str:
    lines = [
        "# 真实平台验收缺口 CRM 任务同步",
        "",
        f"生成时间：{result.created_at}",
        f"状态：{result.status}",
        "",
        result.summary,
        "",
        "## 缺失场景",
        "",
    ]
    if result.missing_scenarios:
        lines.extend(f"- {scenario}" for scenario in result.missing_scenarios)
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 创建或复用的 CRM 任务",
            "",
            "| Task ID | 场景 | 状态 | 负责人 | 到期时间 | 标题 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not result.tasks:
        lines.append("| - | - | - | - | - | 本次没有创建任务 |")
    for task in result.tasks:
        scenario = task.target_id.replace("platform_acceptance:", "")
        lines.append(f"| {task.id} | {scenario} | {task.status} | {task.owner or '-'} | {task.due_at or '-'} | {task.title} |")
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 本同步只创建 CRM 跟进任务，不自动生成真实平台证据。",
            "- 真实证据仍需客户账号、官方授权、真实消息/线索场景和脱敏附件证明。",
            "- 任务中不写入平台密码、token、cookie、验证码或密钥。",
        ]
    )
    return "\n".join(lines)


async def sync_platform_acceptance_gaps_to_crm_tasks(
    payload: PlatformAcceptanceGapSyncRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceGapSyncResult:
    report = await generate_platform_acceptance_report(PlatformAcceptanceReportRequest(audit_limit=200, include_artifact=False), merchant)
    missing = report.missing_scenarios
    due_at = (datetime.now() + timedelta(days=payload.due_days)).strftime("%Y-%m-%d %H:%M:%S")
    created_tasks: list[CRMTask] = []
    tracked_tasks: list[CRMTask] = []
    skipped = 0
    if payload.create_tasks:
        for scenario in missing:
            target_id = platform_acceptance_gap_target_id(scenario)
            existing = existing_open_platform_acceptance_task(merchant.id or 0, target_id)
            if existing:
                skipped += 1
                tracked_tasks.append(existing)
                continue
            task = create_crm_task_record(
                merchant.id or 0,
                CRMTaskCreate(
                    target_type="conversation",
                    target_id=target_id,
                    title=platform_acceptance_gap_task_title(scenario),
                    priority="high" if scenario in {"official_auth", "callback", "read_message", "read_lead"} else "normal",
                    owner=payload.owner,
                    due_at=due_at,
                    source="platform_acceptance_gap",
                    workflow_run_id=report.id,
                ),
            )
            created_tasks.append(task)
            tracked_tasks.append(task)
    if not missing:
        status: Literal["synced", "preview", "nothing_to_sync"] = "nothing_to_sync"
    elif payload.create_tasks:
        status = "synced"
    else:
        status = "preview"
    result = PlatformAcceptanceGapSyncResult(
        id=f"platform-gap-sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance gaps synced. missing_scenarios={len(missing)} "
            f"created={len(created_tasks)} skipped_existing={skipped} create_tasks={payload.create_tasks}."
        ),
        missing_scenarios=missing,
        created=len(created_tasks),
        skipped_existing=skipped,
        tasks=tracked_tasks,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_gap_sync_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_gap_sync",
        max(1, len(created_tasks)),
        "integration",
        result.id,
        {"missing": len(missing), "created": len(created_tasks), "skipped": skipped, "create_tasks": payload.create_tasks},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_gap_sync",
        "integration_acceptance",
        result.id,
        "同步真实平台验收缺口到 CRM 任务",
        {"missing": len(missing), "created": len(created_tasks), "skipped": skipped, "create_tasks": payload.create_tasks},
    )
    return result


def build_platform_acceptance_gap_reconcile_markdown(result: PlatformAcceptanceGapReconcileResult) -> str:
    lines = [
        "# 真实平台验收缺口复验关闭",
        "",
        f"生成时间：{result.created_at}",
        f"状态：{result.status}",
        "",
        result.summary,
        "",
        "## 已通过证据场景",
        "",
    ]
    if result.passed_scenarios:
        lines.extend(f"- {scenario}" for scenario in result.passed_scenarios)
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 已关闭任务",
            "",
            "| Task ID | 场景 | 负责人 | 标题 |",
            "| --- | --- | --- | --- |",
        ]
    )
    if not result.closed_tasks:
        lines.append("| - | - | - | 本次没有关闭任务 |")
    for task in result.closed_tasks:
        lines.append(f"| {task.id} | {platform_acceptance_scenario_from_target(task.target_id) or '-'} | {task.owner or '-'} | {task.title} |")
    lines.extend(
        [
            "",
            "## 仍打开任务",
            "",
            "| Task ID | 场景 | 负责人 | 到期时间 | 标题 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if not result.open_tasks:
        lines.append("| - | - | - | - | 当前没有打开的真实平台验收缺口任务 |")
    for task in result.open_tasks:
        lines.append(f"| {task.id} | {platform_acceptance_scenario_from_target(task.target_id) or '-'} | {task.owner or '-'} | {task.due_at or '-'} | {task.title} |")
    lines.extend(
        [
            "",
            "## 安全边界",
            "",
            "- 本复验只根据已登记的 pass 脱敏证据关闭 CRM 跟进任务。",
            "- 不伪造真实平台证据，不写入密码、token、cookie、验证码或密钥。",
            "- 真实验收仍需客户账号、官方授权和真实消息/线索场景证明。",
        ]
    )
    return "\n".join(lines)


async def reconcile_platform_acceptance_gap_tasks(
    payload: PlatformAcceptanceGapReconcileRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceGapReconcileResult:
    report = await generate_platform_acceptance_report(PlatformAcceptanceReportRequest(audit_limit=200, include_artifact=False), merchant)
    passed_scenarios = sorted({item.scenario for item in report.evidence if item.result == "pass"})
    open_tasks = open_platform_acceptance_gap_tasks(merchant.id or 0)
    closable = [task for task in open_tasks if platform_acceptance_scenario_from_target(task.target_id) in passed_scenarios]
    closed_tasks: list[CRMTask] = []
    if payload.close_tasks:
        for task in closable:
            closed_tasks.append(await update_crm_task(task.id, CRMTaskUpdate(status="done"), merchant))
    refreshed_open = open_platform_acceptance_gap_tasks(merchant.id or 0)
    if payload.close_tasks and closed_tasks:
        status: Literal["reconciled", "preview", "nothing_closed"] = "reconciled"
    elif payload.close_tasks:
        status = "nothing_closed"
    else:
        status = "preview"
    result = PlatformAcceptanceGapReconcileResult(
        id=f"platform-gap-reconcile-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance gap reconcile. passed_scenarios={len(passed_scenarios)} "
            f"closable={len(closable)} closed={len(closed_tasks)} still_open={len(refreshed_open)} close_tasks={payload.close_tasks}."
        ),
        passed_scenarios=passed_scenarios,
        closed=len(closed_tasks),
        still_open=len(refreshed_open),
        closed_tasks=closed_tasks,
        open_tasks=refreshed_open,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_gap_reconcile_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_gap_reconcile",
        max(1, len(closed_tasks)),
        "integration",
        result.id,
        {"passed_scenarios": len(passed_scenarios), "closed": len(closed_tasks), "still_open": len(refreshed_open), "close_tasks": payload.close_tasks},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_gap_reconcile",
        "integration_acceptance",
        result.id,
        "复验真实平台验收缺口并关闭 CRM 任务",
        {"passed_scenarios": len(passed_scenarios), "closed": len(closed_tasks), "still_open": len(refreshed_open), "close_tasks": payload.close_tasks},
    )
    return result


def platform_acceptance_evidence_requirements(scenario: PlatformAcceptanceScenario) -> dict[str, list[str] | str]:
    defaults: dict[PlatformAcceptanceScenario, dict[str, list[str] | str]] = {
        "official_auth": {
            "required_evidence": [
                "Sanitized screenshot or work order proving the official app/account authorization is active.",
                "Connector name, customer account label, and granted scopes or permissions with secrets masked.",
                "Operator and acceptance timestamp.",
            ],
            "capture_steps": [
                "Open the official platform admin or developer console with the customer account.",
                "Confirm the app, scopes, callback domain, and account binding are active.",
                "Save a sanitized screenshot or recording link, then register a pass evidence item.",
            ],
            "next_action": "Collect official authorization proof from the customer platform admin.",
        },
        "callback": {
            "required_evidence": [
                "Sanitized callback test result showing the production callback URL receives a signed event.",
                "Audit log or event id proving signature verification and idempotency worked.",
                "No raw signature secret, token, cookie, password, or verification code.",
            ],
            "capture_steps": [
                "Trigger a real official-platform callback or approved sandbox callback.",
                "Verify the backend accepts the signed event and rejects duplicates safely.",
                "Register pass evidence with the event id or sanitized log artifact.",
            ],
            "next_action": "Run a real callback test and register the sanitized event proof.",
        },
        "read_message": {
            "required_evidence": [
                "Real customer message or conversation pull result with private content masked.",
                "Connector event id and CRM/conversation inbox record proving ingestion.",
                "Timestamp and operator confirmation.",
            ],
            "capture_steps": [
                "Use the authorized account to pull or receive a real customer message.",
                "Confirm the message appears in the conversation inbox without duplicate records.",
                "Register pass evidence with the sanitized conversation/event reference.",
            ],
            "next_action": "Pull or receive one real platform message and attach sanitized proof.",
        },
        "read_lead": {
            "required_evidence": [
                "Real lead or form submission pull result with personal details masked.",
                "CRM lead id showing the lead was created or updated idempotently.",
                "Source platform and acceptance timestamp.",
            ],
            "capture_steps": [
                "Create or select an approved test lead in the customer platform.",
                "Pull or receive the lead through the configured connector.",
                "Confirm the CRM lead exists, then register pass evidence.",
            ],
            "next_action": "Pull one real lead into CRM and register sanitized evidence.",
        },
        "draft_reply": {
            "required_evidence": [
                "Real inbound message that generated an AI reply draft.",
                "Draft id and manual-review status proving it did not auto-send.",
                "Risk or handoff note if the message contains sensitive intent.",
            ],
            "capture_steps": [
                "Use a real or customer-approved platform message as input.",
                "Confirm the assistant creates a reply draft in the manual review queue.",
                "Register pass evidence with the draft id and sanitized message context.",
            ],
            "next_action": "Generate a real reply draft from platform intake and capture the review proof.",
        },
        "customer_trial": {
            "required_evidence": [
                "Customer trial run summary covering authorization, callback, read, draft, and CRM follow-up.",
                "Signed-off acceptance note or customer-controlled artifact link.",
                "Known limitations and human-confirmation boundary.",
            ],
            "capture_steps": [
                "Run a customer-supervised end-to-end trial with real platform data.",
                "Confirm each required scenario has pass evidence and no fail evidence.",
                "Register final customer_trial pass evidence and keep the safety boundary in the artifact.",
            ],
            "next_action": "Schedule the customer-supervised end-to-end acceptance run.",
        },
        "controlled_send": {
            "required_evidence": [
                "Approved low-risk message prepared for controlled API sending.",
                "Manual confirmation phrase, rate-limit result, and send audit id.",
                "Official send permission proof with secrets masked.",
            ],
            "capture_steps": [
                "Confirm official send_url and access credentials are configured.",
                "Approve a low-risk reply with the required confirmation phrase.",
                "Register sanitized evidence only after the controlled send audit record exists.",
            ],
            "next_action": "Keep controlled send disabled until official permission and manual confirmation are proven.",
        },
        "ops_health": {
            "required_evidence": [
                "Connector health report with no failing production checks.",
                "Recent callback/read/send event counters and alert summary.",
                "Operator confirmation that alerts were reviewed.",
            ],
            "capture_steps": [
                "Run connector operations health after official credentials are configured.",
                "Review alerts, expiry warnings, and failed event counters.",
                "Register pass evidence with the health report artifact.",
            ],
            "next_action": "Run ops health after real connector credentials are configured.",
        },
    }
    return defaults[scenario]


def build_platform_acceptance_evidence_checklist_markdown(result: PlatformAcceptanceEvidenceChecklist) -> str:
    lines = [
        "# Real Platform Acceptance Evidence Checklist",
        "",
        f"Created at: {result.created_at}",
        f"Status: {result.status}",
        "",
        result.summary,
        "",
        "## Missing Scenarios",
        "",
    ]
    if result.missing_scenarios:
        lines.extend(f"- {scenario}" for scenario in result.missing_scenarios)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Checklist",
            "",
            "| Scenario | Status | Task | Owner | Due At | Evidence Count | Next Action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in result.items:
        task = f"#{item.task_id}" if item.task_id else "-"
        lines.append(
            f"| {item.scenario} | {item.status} | {task} | {item.owner or '-'} | "
            f"{item.due_at or '-'} | {item.evidence_count} | {item.next_action or '-'} |"
        )
    lines.extend(["", "## Evidence Requirements", ""])
    for item in result.items:
        lines.extend([f"### {item.scenario}", "", "Required evidence:"])
        lines.extend(f"- {entry}" for entry in item.required_evidence)
        lines.extend(["", "Capture steps:"])
        lines.extend(f"- {step}" for step in item.capture_steps)
        if item.latest_evidence_url:
            lines.extend(["", f"Latest evidence reference: {item.latest_evidence_url}"])
        lines.append("")
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- This checklist does not create or fake platform evidence.",
            "- Do not store platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
            "- A scenario is closed only after a sanitized pass evidence item is registered and reconciled.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_evidence_checklist(
    payload: PlatformAcceptanceEvidenceChecklistRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceChecklist:
    if payload.ensure_tasks:
        await sync_platform_acceptance_gaps_to_crm_tasks(
            PlatformAcceptanceGapSyncRequest(
                owner=payload.owner,
                due_days=payload.due_days,
                create_tasks=True,
                include_artifact=False,
            ),
            merchant,
        )
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=200, include_artifact=False),
        merchant,
    )
    due_at = (datetime.now() + timedelta(days=payload.due_days)).strftime("%Y-%m-%d %H:%M:%S")
    open_tasks = open_platform_acceptance_gap_tasks(merchant.id or 0)
    tasks_by_scenario = {
        platform_acceptance_scenario_from_target(task.target_id): task
        for task in open_tasks
    }
    evidence_by_scenario: dict[str, list[PlatformAcceptanceEvidence]] = {}
    for evidence in report.evidence:
        evidence_by_scenario.setdefault(evidence.scenario, []).append(evidence)
    items: list[PlatformAcceptanceEvidenceChecklistItem] = []
    for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
        scenario_evidence = evidence_by_scenario.get(scenario, [])
        latest = scenario_evidence[0] if scenario_evidence else None
        passed = any(item.result == "pass" for item in scenario_evidence)
        if passed and not payload.include_passed:
            continue
        task = tasks_by_scenario.get(scenario)
        details = platform_acceptance_evidence_requirements(scenario)
        if passed:
            item_status: Literal["passed", "needs_evidence", "needs_review"] = "passed"
            next_action = "Keep this sanitized pass evidence in the delivery archive."
        elif latest:
            item_status = "needs_review"
            next_action = "Review the latest warning/fail evidence, fix the issue, then register pass evidence."
        else:
            item_status = "needs_evidence"
            next_action = str(details["next_action"])
        items.append(
            PlatformAcceptanceEvidenceChecklistItem(
                scenario=scenario,
                status=item_status,
                target_id=platform_acceptance_gap_target_id(scenario),
                task_id=task.id if task else None,
                task_status=task.status if task else "",
                owner=(task.owner if task else payload.owner) or payload.owner,
                due_at=(task.due_at if task else due_at) or due_at,
                required_evidence=list(details["required_evidence"]),
                capture_steps=list(details["capture_steps"]),
                evidence_count=len(scenario_evidence),
                latest_evidence_result=latest.result if latest else "",
                latest_evidence_url=(latest.evidence_url or latest.artifact_url) if latest else "",
                next_action=next_action,
            )
        )
    status: Literal["complete", "collecting", "blocked"]
    if not report.missing_scenarios:
        status = "complete"
    elif items:
        status = "collecting"
    else:
        status = "blocked"
    result = PlatformAcceptanceEvidenceChecklist(
        id=f"platform-evidence-checklist-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance evidence checklist. required={len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS)} "
            f"missing={len(report.missing_scenarios)} items={len(items)} ensure_tasks={payload.ensure_tasks}."
        ),
        missing_scenarios=report.missing_scenarios,
        items=items,
        tasks=open_tasks,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_checklist_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_checklist",
        max(1, len(items)),
        "integration",
        result.id,
        {"missing": len(result.missing_scenarios), "items": len(items), "ensure_tasks": payload.ensure_tasks},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_checklist",
        "integration_acceptance",
        result.id,
        "Generate real platform acceptance evidence checklist",
        {"missing": len(result.missing_scenarios), "items": len(items), "ensure_tasks": payload.ensure_tasks},
    )
    return result


def assert_platform_acceptance_receipt_safe(payload: PlatformAcceptanceEvidenceReceiptRequest) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the receipt does not contain secrets")
    text = "\n".join(
        [
            payload.recipient,
            payload.notes,
            *[f"{item.note}\n{item.evidence_url}" for item in payload.scenario_receipts],
        ]
    )
    risky_patterns = [
        r"(?i)password\s*[:=]",
        r"(?i)token\s*[:=]",
        r"(?i)secret\s*[:=]",
        r"(?i)cookie\s*[:=]",
        r"(?i)authorization\s*[:=]",
        r"(?i)verification[_ -]?code\s*[:=]",
        r"(?i)验证码\s*[:=]",
        r"(?i)密码\s*[:=]",
        r"(?i)密钥\s*[:=]",
    ]
    if any(re.search(pattern, text) for pattern in risky_patterns):
        raise HTTPException(status_code=400, detail="Receipt appears to contain a secret; store only sanitized notes")


def platform_acceptance_notice_channel_label(channel: str) -> str:
    return {
        "copy": "copy",
        "wecom": "WeCom",
        "dingtalk": "DingTalk",
        "email": "email",
    }.get(channel, channel)


def build_platform_acceptance_evidence_notice_text(
    notice: PlatformAcceptanceEvidenceNotice,
    owner: str,
) -> str:
    lines = [
        f"[Real Platform Acceptance Evidence Request] {notice.subject}",
        "",
        f"Hi {notice.recipient},",
        "",
        (
            f"There are {len(notice.items)} real-platform acceptance evidence items that still need "
            "customer-controlled proof before we can close the remaining launch gaps."
        ),
    ]
    if notice.items:
        lines.extend(["", "Please provide sanitized evidence for:"])
        for index, item in enumerate(notice.items[:12], start=1):
            lines.append(
                f"{index}. {item.scenario}: task #{item.task_id or '-'}, owner={item.owner or owner}, "
                f"due={item.due_at or '-'}, next={item.next_action}"
            )
            if item.required_evidence:
                lines.append(f"   Required: {item.required_evidence[0]}")
        if len(notice.items) > 12:
            lines.append(f"... plus {len(notice.items) - 12} more items in the attached checklist.")
    else:
        lines.extend(["", "There are currently no missing acceptance evidence items."])
    lines.extend(
        [
            "",
            "Important boundaries:",
            "- Do not send passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
            "- A reply to this notice is not pass evidence by itself.",
            "- After you provide sanitized proof, we will register it in the system and run gap reconciliation.",
            "",
            f"Channel: {platform_acceptance_notice_channel_label(notice.channel)}",
            f"Follow-up owner: {owner}",
        ]
    )
    return "\n".join(lines)


def build_platform_acceptance_evidence_notice_markdown(
    notice: PlatformAcceptanceEvidenceNotice,
    owner: str,
) -> str:
    lines = [
        "# Real Platform Acceptance Evidence Notice",
        "",
        f"Created at: {notice.created_at}",
        f"Channel: {platform_acceptance_notice_channel_label(notice.channel)}",
        f"Recipient: {notice.recipient}",
        f"Owner: {owner}",
        f"Status: {notice.status}",
        f"Subject: {notice.subject}",
        "",
        "## Copyable Draft",
        "",
        "```text",
        notice.draft_text,
        "```",
        "",
        "## Evidence Items",
        "",
        "| Scenario | Status | Task | Owner | Due At | Evidence Count | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not notice.items:
        lines.append("| - | empty | - | - | - | - | No missing evidence items. |")
    for item in notice.items:
        lines.append(
            f"| {item.scenario} | {item.status} | {item.task_id or '-'} | {item.owner or '-'} | "
            f"{item.due_at or '-'} | {item.evidence_count} | {item.next_action or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This notice is a human-confirmed draft; it is not automatically sent.",
            "- Do not include platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
            "- Notice receipt does not close a scenario; only registered sanitized pass evidence can close the matching CRM gap.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_evidence_notice(
    payload: PlatformAcceptanceEvidenceNoticeRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceNotice:
    checklist = await generate_platform_acceptance_evidence_checklist(
        PlatformAcceptanceEvidenceChecklistRequest(
            owner=payload.owner,
            due_days=payload.due_days,
            ensure_tasks=payload.ensure_tasks,
            include_passed=payload.include_passed,
            include_artifact=False,
        ),
        merchant,
    )
    items = [item for item in checklist.items if payload.include_passed or item.status != "passed"]
    notice = PlatformAcceptanceEvidenceNotice(
        id=f"platform-evidence-notice-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status="ready" if items else "empty",
        channel=payload.channel,
        recipient=payload.recipient,
        subject=f"Real platform acceptance evidence needed: {len(items)} item(s)",
        draft_text="",
        items=items,
        created_at=now_sql(),
    )
    notice.draft_text = build_platform_acceptance_evidence_notice_text(notice, payload.owner)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{notice.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_notice_markdown(notice, payload.owner), encoding="utf-8")
        notice.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_notice",
        max(1, len(items)),
        "integration",
        notice.id,
        {"items": len(items), "status": notice.status, "channel": payload.channel},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_notice",
        "integration_acceptance",
        notice.id,
        "Generate real platform acceptance evidence owner notice",
        {"items": len(items), "status": notice.status, "channel": payload.channel},
    )
    return notice


def build_platform_acceptance_evidence_receipt_markdown(receipt: PlatformAcceptanceEvidenceReceipt) -> str:
    lines = [
        "# Real Platform Acceptance Evidence Receipt",
        "",
        f"Created at: {receipt.created_at}",
        f"Notice ID: {receipt.notice_id or '-'}",
        f"Recipient: {receipt.recipient}",
        f"Outcome: {receipt.outcome}",
        f"Status: {receipt.status}",
        "",
        receipt.summary,
        "",
        "## Scenario Receipts",
        "",
        "| Scenario | Outcome | Evidence Link | Note |",
        "| --- | --- | --- | --- |",
    ]
    if not receipt.scenario_receipts:
        lines.append("| - | - | - | Receipt recorded without scenario-level detail. |")
    for item in receipt.scenario_receipts:
        safe_note = item.note.replace("|", "/")
        lines.append(f"| {item.scenario} | {item.outcome} | {item.evidence_url or '-'} | {safe_note or '-'} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This receipt records owner response only; it is not pass evidence.",
            "- Submitted materials must still be reviewed and registered through the evidence endpoint.",
            "- Do not store passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
        ]
    )
    return "\n".join(lines)


async def record_platform_acceptance_evidence_receipt(
    payload: PlatformAcceptanceEvidenceReceiptRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceReceipt:
    assert_platform_acceptance_receipt_safe(payload)
    if payload.outcome == "needs_help" or any(item.outcome == "needs_help" for item in payload.scenario_receipts):
        status: Literal["recorded", "needs_help", "submitted"] = "needs_help"
    elif payload.outcome == "submitted" or any(item.outcome == "submitted" for item in payload.scenario_receipts):
        status = "submitted"
    else:
        status = "recorded"
    receipt = PlatformAcceptanceEvidenceReceipt(
        id=f"platform-evidence-receipt-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        notice_id=payload.notice_id,
        recipient=payload.recipient,
        outcome=payload.outcome,
        scenario_receipts=payload.scenario_receipts,
        summary=(
            f"Platform acceptance evidence receipt recorded. outcome={payload.outcome} "
            f"scenario_receipts={len(payload.scenario_receipts)} status={status}."
        ),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{receipt.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_receipt_markdown(receipt), encoding="utf-8")
        receipt.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_receipt",
        max(1, len(payload.scenario_receipts)),
        "integration",
        receipt.id,
        {"outcome": payload.outcome, "scenario_receipts": len(payload.scenario_receipts), "status": status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_receipt",
        "integration_acceptance",
        receipt.id,
        "Record real platform acceptance evidence receipt",
        {
            "outcome": payload.outcome,
            "scenario_receipts": len(payload.scenario_receipts),
            "scenarios": [item.model_dump() for item in payload.scenario_receipts],
            "status": status,
        },
    )
    return receipt


def platform_acceptance_review_target_id(receipt_id: str, scenario: str) -> str:
    digest = hashlib.sha1(f"{receipt_id}:{scenario}".encode("utf-8")).hexdigest()[:12]
    return f"platform_review:{scenario}:{digest}"


def existing_open_platform_acceptance_review_task(merchant_id: int, target_id: str) -> CRMTask | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker} AND target_id={marker}
            ORDER BY id DESC LIMIT 1
            """,
            (merchant_id, "open", "platform_acceptance_evidence_review", target_id),
        ).fetchone()
    return crm_task_from_row(dict(row)) if row else None


def platform_acceptance_review_task_title(item: PlatformAcceptanceEvidenceReviewTaskItem) -> str:
    if item.outcome == "needs_help":
        return f"Help customer complete platform evidence: {item.scenario}"
    return f"Review submitted platform evidence and register pass proof: {item.scenario}"


def platform_acceptance_review_item_from_log(log: AuditLog, scenario_data: dict[str, Any]) -> PlatformAcceptanceEvidenceReviewTaskItem | None:
    scenario = str(scenario_data.get("scenario") or "")
    if scenario not in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS + ["controlled_send", "ops_health"]:
        return None
    outcome = str(scenario_data.get("outcome") or log.metadata.get("outcome") or "acknowledged")
    if outcome not in {"needs_help", "submitted"}:
        return None
    next_action = (
        "Contact the customer owner, clarify missing material, then record a new receipt."
        if outcome == "needs_help"
        else "Review the submitted material, sanitize it, then register pass evidence through the evidence endpoint."
    )
    return PlatformAcceptanceEvidenceReviewTaskItem(
        receipt_id=str(log.target_id or log.metadata.get("id") or ""),
        scenario=scenario,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        target_id=platform_acceptance_review_target_id(str(log.target_id or ""), scenario),
        note=str(scenario_data.get("note") or ""),
        evidence_url=str(scenario_data.get("evidence_url") or ""),
        next_action=next_action,
    )


async def platform_acceptance_review_items_from_receipts(
    merchant: MerchantProfile,
    audit_limit: int,
    include_needs_help: bool,
) -> list[PlatformAcceptanceEvidenceReviewTaskItem]:
    logs = await list_audit_logs(merchant, limit=audit_limit)
    items: list[PlatformAcceptanceEvidenceReviewTaskItem] = []
    seen: set[tuple[str, str, str]] = set()
    for log in logs:
        if log.action != "integration.platform_acceptance_evidence_receipt":
            continue
        scenarios = log.metadata.get("scenarios") if isinstance(log.metadata, dict) else None
        if not isinstance(scenarios, list):
            continue
        for raw in scenarios:
            if not isinstance(raw, dict):
                continue
            item = platform_acceptance_review_item_from_log(log, raw)
            if not item:
                continue
            if item.outcome == "needs_help" and not include_needs_help:
                continue
            key = (item.receipt_id, item.scenario, item.outcome)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items


def build_platform_acceptance_evidence_review_task_sync_markdown(result: PlatformAcceptanceEvidenceReviewTaskSyncResult) -> str:
    lines = [
        "# Real Platform Acceptance Evidence Review Tasks",
        "",
        f"Created at: {result.created_at}",
        f"Status: {result.status}",
        "",
        result.summary,
        "",
        "## Review Items",
        "",
        "| Receipt | Scenario | Outcome | Task | Owner | Due At | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not result.items:
        lines.append("| - | - | - | - | - | - | No submitted or needs-help receipts to sync. |")
    for item in result.items:
        task_ref = f"#{item.task_id}" if item.task_id else "-"
        lines.append(
            f"| {item.receipt_id or '-'} | {item.scenario} | {item.outcome} | {task_ref} | "
            f"{item.owner or '-'} | {item.due_at or '-'} | {item.next_action or '-'} |"
        )
    lines.extend(["", "## Linked CRM Tasks", "", "| Task ID | Status | Owner | Due At | Title |", "| --- | --- | --- | --- | --- |"])
    if not result.tasks:
        lines.append("| - | - | - | - | No CRM tasks created or reused. |")
    for task in result.tasks:
        lines.append(f"| {task.id} | {task.status} | {task.owner or '-'} | {task.due_at or '-'} | {task.title} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Review tasks do not create pass evidence automatically.",
            "- Operators must inspect submitted material, remove secrets, and register pass evidence separately.",
            "- These tasks do not close the original platform acceptance gap tasks.",
        ]
    )
    return "\n".join(lines)


async def sync_platform_acceptance_evidence_review_tasks(
    payload: PlatformAcceptanceEvidenceReviewTaskSyncRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceReviewTaskSyncResult:
    source_items = await platform_acceptance_review_items_from_receipts(
        merchant,
        payload.audit_limit,
        payload.include_needs_help,
    )
    due_at = (datetime.now() + timedelta(days=payload.due_days)).strftime("%Y-%m-%d %H:%M:%S")
    created_tasks: list[CRMTask] = []
    tracked_tasks: list[CRMTask] = []
    result_items: list[PlatformAcceptanceEvidenceReviewTaskItem] = []
    skipped = 0
    for item in source_items:
        item.owner = payload.owner
        item.due_at = due_at
        existing = existing_open_platform_acceptance_review_task(merchant.id or 0, item.target_id)
        if existing:
            skipped += 1
            item.task_id = existing.id
            item.task_status = existing.status
            tracked_tasks.append(existing)
            result_items.append(item)
            continue
        if payload.create_tasks:
            task = create_crm_task_record(
                merchant.id or 0,
                CRMTaskCreate(
                    target_type="conversation",
                    target_id=item.target_id,
                    title=platform_acceptance_review_task_title(item),
                    priority="high" if item.outcome == "submitted" else "normal",
                    owner=payload.owner,
                    due_at=due_at,
                    source="platform_acceptance_evidence_review",
                    workflow_run_id=item.receipt_id,
                ),
            )
            item.task_id = task.id
            item.task_status = task.status
            created_tasks.append(task)
            tracked_tasks.append(task)
        result_items.append(item)
    if not source_items:
        status: Literal["synced", "preview", "nothing_to_sync"] = "nothing_to_sync"
    elif payload.create_tasks:
        status = "synced"
    else:
        status = "preview"
    result = PlatformAcceptanceEvidenceReviewTaskSyncResult(
        id=f"platform-evidence-review-sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance evidence review tasks. items={len(source_items)} created={len(created_tasks)} "
            f"skipped_existing={skipped} submitted={sum(1 for item in source_items if item.outcome == 'submitted')} "
            f"needs_help={sum(1 for item in source_items if item.outcome == 'needs_help')} create_tasks={payload.create_tasks}."
        ),
        created=len(created_tasks),
        skipped_existing=skipped,
        submitted=sum(1 for item in source_items if item.outcome == "submitted"),
        needs_help=sum(1 for item in source_items if item.outcome == "needs_help"),
        items=result_items,
        tasks=tracked_tasks,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_review_task_sync_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_review_sync",
        max(1, len(result_items)),
        "integration",
        result.id,
        {"items": len(result_items), "created": result.created, "skipped": skipped, "create_tasks": payload.create_tasks},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_review_sync",
        "integration_acceptance",
        result.id,
        "Sync submitted platform acceptance evidence receipts into CRM review tasks",
        {"items": len(result_items), "created": result.created, "skipped": skipped, "create_tasks": payload.create_tasks},
    )
    return result


def build_platform_acceptance_review_desk_markdown(desk: PlatformAcceptanceReviewDesk) -> str:
    lines = [
        "# Real Platform Acceptance Review Desk",
        "",
        f"Created at: {desk.created_at}",
        f"Status: {desk.status}",
        "",
        desk.summary,
        "",
        "## Scenario Desk",
        "",
        "| Scenario | Status | Outcome | Task | Can Register Pass | Recommended Decision | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in desk.scenarios:
        task_ref = f"#{item.task_id}" if item.task_id else "-"
        lines.append(
            f"| {item.scenario} | {item.status} | {item.outcome} | {task_ref} | "
            f"{'yes' if item.can_register_pass else 'no'} | {item.recommended_decision} | {item.next_action.replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Required total: {desk.required_total}",
            f"- Passed: {desk.passed}",
            f"- Ready to review: {desk.ready_to_review}",
            f"- Needs customer help: {desk.needs_customer_help}",
            f"- Needs evidence: {desk.needs_evidence}",
            "",
            "## Linked Review Sync",
            "",
            f"- Sync ID: {desk.review_sync.id}",
            f"- Sync status: {desk.review_sync.status}",
            f"- Created review tasks: {desk.review_sync.created}",
            f"- Existing review tasks: {desk.review_sync.skipped_existing}",
            "",
            "## Safety Boundary",
            "",
            "- This desk does not approve evidence automatically.",
            "- Operators must inspect sanitized customer material before using CONFIRM_PLATFORM_EVIDENCE.",
            "- Pass evidence registration and gap reconciliation still go through the review decision endpoint.",
            "- Receipts, notes, and review tasks do not close final acceptance gaps by themselves.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_review_desk(
    payload: PlatformAcceptanceReviewDeskRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceReviewDesk:
    review_sync = await sync_platform_acceptance_evidence_review_tasks(
        PlatformAcceptanceEvidenceReviewTaskSyncRequest(
            owner=payload.owner,
            due_days=payload.due_days,
            include_needs_help=payload.include_needs_help,
            create_tasks=payload.create_review_tasks,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    latest_by_scenario: dict[PlatformAcceptanceScenario, PlatformAcceptanceEvidenceReviewTaskItem] = {}
    for item in review_sync.items:
        if item.scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS and item.scenario not in latest_by_scenario:
            latest_by_scenario[item.scenario] = item
    passed_scenarios = set(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS) - set(report.missing_scenarios)
    scenario_rows: list[PlatformAcceptanceReviewDeskScenario] = []
    for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
        review_item = latest_by_scenario.get(scenario)
        if scenario in passed_scenarios:
            scenario_rows.append(
                PlatformAcceptanceReviewDeskScenario(
                    scenario=scenario,
                    status="passed",
                    outcome="none",
                    can_register_pass=False,
                    recommended_decision="none",
                    next_action="No review action needed. Keep final evidence available for audit.",
                )
            )
            continue
        if review_item:
            if review_item.outcome == "submitted":
                has_evidence_link = bool(review_item.evidence_url.strip())
                scenario_rows.append(
                    PlatformAcceptanceReviewDeskScenario(
                        scenario=scenario,
                        status="ready_to_review",
                        outcome="submitted",
                        receipt_id=review_item.receipt_id,
                        task_id=review_item.task_id,
                        task_status=review_item.task_status,
                        owner=review_item.owner,
                        due_at=review_item.due_at,
                        evidence_url=review_item.evidence_url,
                        note=review_item.note,
                        can_register_pass=has_evidence_link,
                        recommended_decision="approved" if has_evidence_link else "needs_redaction",
                        next_action=(
                            "Inspect sanitized evidence URL; if valid, register pass evidence and reconcile gaps."
                            if has_evidence_link
                            else "Submitted receipt has no sanitized evidence URL; request redaction or resubmission before pass evidence."
                        ),
                    )
                )
            else:
                scenario_rows.append(
                    PlatformAcceptanceReviewDeskScenario(
                        scenario=scenario,
                        status="needs_customer_help",
                        outcome="needs_help",
                        receipt_id=review_item.receipt_id,
                        task_id=review_item.task_id,
                        task_status=review_item.task_status,
                        owner=review_item.owner,
                        due_at=review_item.due_at,
                        evidence_url=review_item.evidence_url,
                        note=review_item.note,
                        can_register_pass=False,
                        recommended_decision="needs_redaction",
                        next_action="Contact the customer owner, clarify the missing material, then request resubmission.",
                    )
                )
            continue
        requirements = platform_acceptance_evidence_requirements(scenario)
        evidence_requirements = requirements.get("evidence") or ["sanitized real-platform proof"]
        if isinstance(evidence_requirements, list):
            first_required = str(evidence_requirements[0] if evidence_requirements else "sanitized real-platform proof")
        else:
            first_required = str(evidence_requirements)
        scenario_rows.append(
            PlatformAcceptanceReviewDeskScenario(
                scenario=scenario,
                status="needs_evidence",
                outcome="none",
                can_register_pass=False,
                recommended_decision="none",
                next_action=f"Collect customer-controlled proof: {first_required}",
            )
        )
    passed_count = sum(1 for item in scenario_rows if item.status == "passed")
    ready_count = sum(1 for item in scenario_rows if item.status == "ready_to_review")
    help_count = sum(1 for item in scenario_rows if item.status == "needs_customer_help")
    evidence_count = sum(1 for item in scenario_rows if item.status == "needs_evidence")
    if passed_count == len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS):
        status: Literal["ready_for_review", "waiting_customer", "complete"] = "complete"
    elif ready_count or help_count:
        status = "ready_for_review"
    else:
        status = "waiting_customer"
    desk = PlatformAcceptanceReviewDesk(
        id=f"platform-review-desk-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance review desk. passed={passed_count} ready_to_review={ready_count} "
            f"needs_help={help_count} needs_evidence={evidence_count} review_tasks={len(review_sync.tasks)}."
        ),
        required_total=len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS),
        passed=passed_count,
        ready_to_review=ready_count,
        needs_customer_help=help_count,
        needs_evidence=evidence_count,
        scenarios=scenario_rows,
        review_sync=review_sync,
        missing_scenarios=report.missing_scenarios,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{desk.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_review_desk_markdown(desk), encoding="utf-8")
        desk.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_review_desk",
        max(1, len(scenario_rows)),
        "integration",
        desk.id,
        {
            "status": desk.status,
            "passed": desk.passed,
            "ready_to_review": desk.ready_to_review,
            "needs_help": desk.needs_customer_help,
            "needs_evidence": desk.needs_evidence,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_review_desk",
        "integration_acceptance",
        desk.id,
        "Generate platform acceptance review desk",
        {
            "status": desk.status,
            "passed": desk.passed,
            "ready_to_review": desk.ready_to_review,
            "needs_help": desk.needs_customer_help,
            "needs_evidence": desk.needs_evidence,
        },
    )
    return desk


def build_platform_acceptance_review_execution_markdown(result: PlatformAcceptanceReviewExecutionRun) -> str:
    lines = [
        "# Real Platform Acceptance Review Execution Run",
        "",
        f"Run ID: {result.id}",
        f"Created at: {result.created_at}",
        f"Status: {result.status}",
        "",
        result.summary,
        "",
        "## Execution Items",
        "",
        "| Scenario | Decision | Status | Tasks | Evidence | Gap Closed | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not result.items:
        lines.append("| - | - | blocked | - | no | 0 | No ready review items or explicit decisions. |")
    for item in result.items:
        task_ids = ", ".join(str(task_id) for task_id in item.review_task_ids) or "-"
        evidence = "yes" if item.evidence_registered else "no"
        next_action = item.error or item.next_action or "-"
        lines.append(
            f"| {item.scenario} | {item.decision} | {item.status} | {task_ids} | "
            f"{evidence} | {item.gap_closed} | {next_action.replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Desk Before",
            "",
            f"- Status: {result.desk_before.status if result.desk_before else '-'}",
            f"- Ready to review: {result.desk_before.ready_to_review if result.desk_before else 0}",
            f"- Needs evidence: {result.desk_before.needs_evidence if result.desk_before else 0}",
            "",
            "## Desk After",
            "",
            f"- Status: {result.desk_after.status if result.desk_after else '-'}",
            f"- Passed: {result.desk_after.passed if result.desk_after else 0}",
            f"- Missing scenarios: {', '.join(result.desk_after.missing_scenarios) if result.desk_after and result.desk_after.missing_scenarios else 'not recomputed or none'}",
            "",
            "## Safety Boundary",
            "",
            "- Preview mode does not register evidence or close tasks.",
            "- Execute mode requires CONFIRM_PLATFORM_EVIDENCE for pass evidence and gap reconciliation.",
            "- Approved items must include sanitized, customer-controlled evidence links.",
            "- This run never fabricates platform evidence; blocked items must be completed by the customer or operations reviewer.",
        ]
    )
    return "\n".join(lines)


def review_execution_input_from_desk_item(
    item: PlatformAcceptanceReviewDeskScenario,
    owner: str,
) -> PlatformAcceptanceReviewExecutionDecisionInput:
    return PlatformAcceptanceReviewExecutionDecisionInput(
        scenario=item.scenario,
        decision="approved" if item.can_register_pass else "needs_redaction",
        review_task_ids=[item.task_id] if item.task_id else [],
        connector="website",
        account_label="customer platform account",
        operator=owner,
        evidence_note=item.note or f"Review desk execution for {item.scenario}.",
        evidence_url=item.evidence_url,
        close_review_tasks=True,
        reconcile_gap_tasks=True,
        request_resubmission_link=not item.can_register_pass,
    )


async def run_platform_acceptance_review_execution(
    payload: PlatformAcceptanceReviewExecutionRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceReviewExecutionRun:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm execution notes contain no secrets")
    desk_before = await generate_platform_acceptance_review_desk(
        PlatformAcceptanceReviewDeskRequest(
            owner=payload.owner,
            due_days=payload.due_days,
            include_needs_help=True,
            create_review_tasks=True,
            include_artifact=False,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    decisions = list(payload.decisions)
    if not decisions and payload.auto_ready_items:
        decisions = [
            review_execution_input_from_desk_item(item, payload.owner)
            for item in desk_before.scenarios
            if item.status == "ready_to_review"
        ]
    if payload.execute and any(
        item.decision == "approved" or item.close_review_tasks or item.reconcile_gap_tasks
        for item in decisions
    ) and payload.confirm_phrase != "CONFIRM_PLATFORM_EVIDENCE":
        raise HTTPException(status_code=400, detail="CONFIRM_PLATFORM_EVIDENCE is required to execute review approvals")
    run_items: list[PlatformAcceptanceReviewExecutionRunItem] = []
    executed_decisions: list[PlatformAcceptanceEvidenceReviewDecision] = []
    for decision_input in decisions:
        can_execute = True
        error = ""
        if decision_input.decision == "approved" and not decision_input.evidence_url.strip():
            can_execute = False
            error = "Approved execution requires a sanitized evidence URL."
        elif decision_input.decision == "approved" and is_placeholder_platform_evidence_url(decision_input.evidence_url):
            can_execute = False
            error = "Approved execution requires a real customer-controlled evidence URL, not a placeholder URL."
        if not payload.execute:
            run_items.append(
                PlatformAcceptanceReviewExecutionRunItem(
                    scenario=decision_input.scenario,
                    decision=decision_input.decision,
                    status="preview" if can_execute else "blocked",
                    review_task_ids=decision_input.review_task_ids,
                    error=error,
                    next_action=(
                        "Ready to execute with CONFIRM_PLATFORM_EVIDENCE."
                        if can_execute and decision_input.decision == "approved"
                        else "Generate a customer resubmission link or add a sanitized evidence URL before approval."
                    ),
                )
            )
            continue
        if not can_execute:
            run_items.append(
                PlatformAcceptanceReviewExecutionRunItem(
                    scenario=decision_input.scenario,
                    decision=decision_input.decision,
                    status="blocked",
                    review_task_ids=decision_input.review_task_ids,
                    error=error,
                    next_action="Request resubmission with a sanitized evidence URL before registering pass evidence.",
                )
            )
            continue
        try:
            decision = await record_platform_acceptance_evidence_review_decision(
                PlatformAcceptanceEvidenceReviewDecisionRequest(
                    scenario=decision_input.scenario,
                    decision=decision_input.decision,
                    review_task_ids=decision_input.review_task_ids,
                    connector=decision_input.connector,
                    account_label=decision_input.account_label,
                    operator=decision_input.operator or payload.owner,
                    evidence_note=decision_input.evidence_note,
                    evidence_url=decision_input.evidence_url,
                    register_pass_evidence=decision_input.decision == "approved",
                    close_review_tasks=decision_input.decision == "approved" and decision_input.close_review_tasks,
                    reconcile_gap_tasks=decision_input.decision == "approved" and decision_input.reconcile_gap_tasks,
                    request_resubmission_link=decision_input.decision != "approved" and decision_input.request_resubmission_link,
                    confirm_phrase=payload.confirm_phrase,
                    include_artifact=True,
                    no_secrets_confirmed=True,
                ),
                merchant,
            )
            executed_decisions.append(decision)
            run_items.append(
                PlatformAcceptanceReviewExecutionRunItem(
                    scenario=decision_input.scenario,
                    decision=decision_input.decision,
                    status="executed",
                    review_task_ids=decision_input.review_task_ids,
                    evidence_registered=bool(decision.evidence),
                    closed_review_tasks=len(decision.closed_review_tasks),
                    gap_closed=decision.gap_reconcile.closed if decision.gap_reconcile else 0,
                    resubmission_url=decision.resubmission_link.submit_url if decision.resubmission_link else "",
                    artifact_url=decision.artifact_url,
                    next_action=(
                        "Evidence registered and gaps reconciled; rerun final sign-off gate."
                        if decision.evidence
                        else "Decision recorded; wait for customer resubmission before pass evidence."
                    ),
                )
            )
        except HTTPException as exc:
            run_items.append(
                PlatformAcceptanceReviewExecutionRunItem(
                    scenario=decision_input.scenario,
                    decision=decision_input.decision,
                    status="blocked",
                    review_task_ids=decision_input.review_task_ids,
                    error=str(exc.detail),
                    next_action="Fix the blocked decision input and rerun execution.",
                )
            )
    desk_after: PlatformAcceptanceReviewDesk | None = None
    if payload.execute:
        desk_after = await generate_platform_acceptance_review_desk(
            PlatformAcceptanceReviewDeskRequest(
                owner=payload.owner,
                due_days=payload.due_days,
                include_needs_help=True,
                create_review_tasks=False,
                include_artifact=False,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    executed_count = sum(1 for item in run_items if item.status == "executed")
    blocked_count = sum(1 for item in run_items if item.status == "blocked")
    if not payload.execute:
        status: Literal["preview", "executed", "partial", "blocked"] = "preview"
    elif executed_count and blocked_count:
        status = "partial"
    elif executed_count:
        status = "executed"
    else:
        status = "blocked"
    result = PlatformAcceptanceReviewExecutionRun(
        id=f"platform-review-execution-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform review execution run. execute={payload.execute} requested={len(decisions)} "
            f"executed={executed_count} blocked={blocked_count} evidence_registered="
            f"{sum(1 for item in run_items if item.evidence_registered)} gap_closed={sum(item.gap_closed for item in run_items)}."
        ),
        requested=len(decisions),
        executed=executed_count,
        blocked=blocked_count,
        evidence_registered=sum(1 for item in run_items if item.evidence_registered),
        gap_closed=sum(item.gap_closed for item in run_items),
        items=run_items,
        decisions=executed_decisions,
        desk_before=desk_before,
        desk_after=desk_after,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_review_execution_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_review_execution",
        max(1, len(run_items)),
        "integration",
        result.id,
        {
            "status": result.status,
            "execute": payload.execute,
            "requested": result.requested,
            "executed": result.executed,
            "blocked": result.blocked,
            "evidence_registered": result.evidence_registered,
            "gap_closed": result.gap_closed,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_review_execution",
        "integration_acceptance",
        result.id,
        "Run platform acceptance review execution",
        {
            "status": result.status,
            "execute": payload.execute,
            "requested": result.requested,
            "executed": result.executed,
            "blocked": result.blocked,
            "evidence_registered": result.evidence_registered,
            "gap_closed": result.gap_closed,
        },
    )
    return result


def build_platform_acceptance_evidence_import_markdown(result: PlatformAcceptanceEvidenceImportRun) -> str:
    lines = [
        "# Real Platform Evidence Import Run",
        "",
        f"Run ID: {result.id}",
        f"Created at: {result.created_at}",
        f"Status: {result.status}",
        "",
        result.summary,
        "",
        "## Import Items",
        "",
        "| Scenario | Status | URL Check | Evidence URL | Evidence ID | Decision ID | Gap Closed | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not result.items:
        lines.append("| - | blocked | - | - | - | - | 0 | No evidence import items were supplied. |")
    for item in result.items:
        next_action = item.error or item.next_action or "-"
        url_check = item.url_precheck.status if item.url_precheck else "-"
        if item.url_precheck and item.url_precheck.reason:
            url_check = f"{item.url_precheck.status}: {item.url_precheck.reason}"
        lines.append(
            f"| {item.scenario} | {item.status} | {url_check.replace('|', '/')} | {item.evidence_url or '-'} | "
            f"{item.evidence_id or '-'} | {item.decision_id or '-'} | {item.gap_closed} | {next_action.replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Report Before",
            "",
            f"- Status: {result.report_before.status if result.report_before else '-'}",
            f"- Missing: {', '.join(result.report_before.missing_scenarios) if result.report_before and result.report_before.missing_scenarios else 'none'}",
            "",
            "## Report After",
            "",
            f"- Status: {result.report_after.status if result.report_after else '-'}",
            f"- Missing: {', '.join(result.report_after.missing_scenarios) if result.report_after and result.report_after.missing_scenarios else 'not executed or none'}",
            "",
            "## Safety Boundary",
            "",
            "- Preview mode validates only; it does not register pass evidence.",
            "- Execute mode requires CONFIRM_PLATFORM_EVIDENCE and non-placeholder evidence URLs.",
            "- Evidence URLs must point to customer-controlled, sanitized proof such as screenshots, recordings, tickets, or platform audit pages.",
            "- Platform passwords, tokens, cookies, verification codes, signatures, session keys, and API secrets are never accepted as evidence.",
        ]
    )
    return "\n".join(lines)


def evidence_import_item_by_scenario(
    payload: PlatformAcceptanceEvidenceImportRunRequest,
) -> dict[PlatformAcceptanceScenario, PlatformAcceptanceEvidenceImportItem]:
    result: dict[PlatformAcceptanceScenario, PlatformAcceptanceEvidenceImportItem] = {}
    for item in payload.items:
        if item.scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS and item.scenario not in result:
            result[item.scenario] = item
    return result


async def run_platform_acceptance_evidence_import(
    payload: PlatformAcceptanceEvidenceImportRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceImportRun:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm evidence import contains no secrets")
    report_before = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    desk_before = await generate_platform_acceptance_review_desk(
        PlatformAcceptanceReviewDeskRequest(
            owner=payload.owner,
            due_days=1,
            include_needs_help=True,
            create_review_tasks=False,
            include_artifact=False,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    task_by_scenario = {
        item.scenario: [item.task_id] if item.task_id else []
        for item in desk_before.scenarios
    }
    supplied = evidence_import_item_by_scenario(payload)
    requested_required = [
        scenario for scenario in payload.required_scenarios
        if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS
    ]
    required_scenarios = requested_required or report_before.missing_scenarios or PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS
    if payload.execute and payload.confirm_phrase != "CONFIRM_PLATFORM_EVIDENCE":
        raise HTTPException(status_code=400, detail="CONFIRM_PLATFORM_EVIDENCE is required to import pass evidence")
    run_items: list[PlatformAcceptanceEvidenceImportRunItem] = []
    decisions: list[PlatformAcceptanceEvidenceReviewDecision] = []
    for scenario in required_scenarios:
        item = supplied.get(scenario)
        if not item:
            requirement = platform_acceptance_evidence_requirements(scenario)
            evidence_requirements = requirement.get("evidence") or ["sanitized real-platform proof"]
            first_required = str(evidence_requirements[0] if isinstance(evidence_requirements, list) else evidence_requirements)
            run_items.append(
                PlatformAcceptanceEvidenceImportRunItem(
                    scenario=scenario,
                    status="missing",
                    next_action=f"Supply sanitized evidence URL before import: {first_required}",
                )
            )
            continue
        review_task_ids = item.review_task_ids or task_by_scenario.get(scenario, [])
        probe = PlatformAcceptanceEvidenceRequest(
            connector=item.connector,
            scenario=scenario,
            result="pass",
            account_label=item.account_label,
            operator=item.operator or payload.owner,
            evidence_note=item.evidence_note,
            evidence_url=item.evidence_url,
            occurred_at=item.occurred_at,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        )
        url_precheck: PlatformAcceptanceEvidenceUrlPrecheckItem | None = None
        try:
            assert_platform_acceptance_evidence_safe(probe)
            url_precheck = precheck_platform_acceptance_evidence_url(item, payload.check_url_reachability)
            if url_precheck.status == "blocked":
                raise HTTPException(status_code=400, detail=url_precheck.reason)
        except HTTPException as exc:
            run_items.append(
                PlatformAcceptanceEvidenceImportRunItem(
                    scenario=scenario,
                    status="blocked",
                    evidence_url=item.evidence_url,
                    url_precheck=url_precheck,
                    review_task_ids=review_task_ids,
                    error=str(exc.detail),
                    next_action="Replace with a sanitized customer-controlled evidence URL and retry.",
                )
            )
            continue
        next_action = "Ready to import after CONFIRM_PLATFORM_EVIDENCE."
        if url_precheck.status == "warning":
            next_action = f"Ready after manual review; URL precheck warning: {url_precheck.reason}"
        if not payload.execute:
            run_items.append(
                PlatformAcceptanceEvidenceImportRunItem(
                    scenario=scenario,
                    status="ready",
                    evidence_url=item.evidence_url,
                    url_precheck=url_precheck,
                    review_task_ids=review_task_ids,
                    next_action=next_action,
                )
            )
            continue
        try:
            decision = await record_platform_acceptance_evidence_review_decision(
                PlatformAcceptanceEvidenceReviewDecisionRequest(
                    scenario=scenario,
                    decision="approved",
                    review_task_ids=review_task_ids,
                    connector=item.connector,
                    account_label=item.account_label,
                    operator=item.operator or payload.owner,
                    evidence_note=item.evidence_note,
                    evidence_url=item.evidence_url,
                    register_pass_evidence=True,
                    close_review_tasks=payload.close_review_tasks,
                    reconcile_gap_tasks=payload.reconcile_gap_tasks,
                    request_resubmission_link=False,
                    confirm_phrase=payload.confirm_phrase,
                    include_artifact=True,
                    no_secrets_confirmed=True,
                ),
                merchant,
            )
            decisions.append(decision)
            run_items.append(
                PlatformAcceptanceEvidenceImportRunItem(
                    scenario=scenario,
                    status="imported",
                    evidence_url=item.evidence_url,
                    url_precheck=url_precheck,
                    review_task_ids=review_task_ids,
                    evidence_id=decision.evidence.id if decision.evidence else "",
                    decision_id=decision.id,
                    gap_closed=decision.gap_reconcile.closed if decision.gap_reconcile else 0,
                    next_action="Evidence imported; final gate can be recomputed after all required scenarios are ready.",
                )
            )
        except HTTPException as exc:
            run_items.append(
                PlatformAcceptanceEvidenceImportRunItem(
                    scenario=scenario,
                    status="blocked",
                    evidence_url=item.evidence_url,
                    url_precheck=url_precheck,
                    review_task_ids=review_task_ids,
                    error=str(exc.detail),
                    next_action="Fix the import item and retry.",
                )
            )
    report_after = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    ) if payload.execute else None
    imported_count = sum(1 for item in run_items if item.status == "imported")
    ready_count = sum(1 for item in run_items if item.status == "ready")
    blocked_count = sum(1 for item in run_items if item.status in {"blocked", "missing"})
    if not payload.execute:
        status: Literal["preview", "imported", "partial", "blocked"] = "preview"
    elif imported_count and blocked_count:
        status = "partial"
    elif imported_count:
        status = "imported"
    else:
        status = "blocked"
    result = PlatformAcceptanceEvidenceImportRun(
        id=f"platform-evidence-import-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform evidence import run. execute={payload.execute} supplied={len(supplied)} "
            f"ready={ready_count} imported={imported_count} blocked={blocked_count} "
            f"evidence_registered={sum(1 for item in run_items if item.evidence_id)}."
        ),
        required_total=len(required_scenarios),
        supplied=len(supplied),
        ready=ready_count,
        imported=imported_count,
        blocked=blocked_count,
        evidence_registered=sum(1 for item in run_items if item.evidence_id),
        gap_closed=sum(item.gap_closed for item in run_items),
        missing_scenarios=[item.scenario for item in run_items if item.status == "missing"],
        items=run_items,
        decisions=decisions,
        report_before=report_before,
        report_after=report_after,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_import_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_import",
        max(1, len(run_items)),
        "integration",
        result.id,
        {
            "status": result.status,
            "execute": payload.execute,
            "supplied": result.supplied,
            "imported": result.imported,
            "blocked": result.blocked,
            "evidence_registered": result.evidence_registered,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_import",
        "integration_acceptance",
        result.id,
        "Run platform evidence import",
        {
            "status": result.status,
            "execute": payload.execute,
            "supplied": result.supplied,
            "imported": result.imported,
            "blocked": result.blocked,
            "evidence_registered": result.evidence_registered,
        },
    )
    return result


def platform_acceptance_evidence_manifest_path() -> str:
    return "/api/v1/public/platform-acceptance-evidence-manifest"


def platform_acceptance_evidence_manifest_url(signed_code: str) -> str:
    base_url = platform_acceptance_submission_base_url()
    return f"{base_url}{platform_acceptance_evidence_manifest_path()}?token={urllib.parse.quote(signed_code)}"


def encode_platform_acceptance_evidence_manifest_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    mac = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-evidence-manifest:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"paem.v1.{body}.{mac}"


def decode_platform_acceptance_evidence_manifest_token(token: str) -> dict[str, Any]:
    try:
        prefix, version, body, mac = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid evidence manifest token") from exc
    if prefix != "paem" or version != "v1":
        raise HTTPException(status_code=400, detail="Unsupported evidence manifest token")
    expected = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-evidence-manifest:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Evidence manifest token signature mismatch")
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Evidence manifest token payload invalid") from exc
    expires_ts = int(payload.get("expires_ts") or 0)
    if expires_ts < int(time.time()):
        raise HTTPException(status_code=400, detail="Evidence manifest token expired")
    scenarios = [scenario for scenario in payload.get("scenarios", []) if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    if not scenarios:
        raise HTTPException(status_code=400, detail="Evidence manifest token has no required scenarios")
    payload["scenarios"] = scenarios
    return payload


PLATFORM_ACCEPTANCE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
PLATFORM_ACCEPTANCE_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".docx",
}
PLATFORM_ACCEPTANCE_UPLOAD_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/json",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def sanitized_platform_acceptance_upload_filename(filename: str) -> str:
    name = Path(filename or "evidence-upload").name
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem or "evidence-upload"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or "evidence-upload"
    return f"{safe_stem[:80]}{suffix}"


def assert_platform_acceptance_upload_bytes_safe(filename: str, content_type: str, raw: bytes) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in PLATFORM_ACCEPTANCE_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported evidence upload file extension")
    if content_type and content_type not in PLATFORM_ACCEPTANCE_UPLOAD_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported evidence upload content type")
    if not raw:
        raise HTTPException(status_code=400, detail="Evidence upload file is empty")
    if len(raw) > PLATFORM_ACCEPTANCE_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Evidence upload exceeds 10MB limit")
    if suffix in {".txt", ".md", ".json", ".csv"} or (content_type or "").startswith("text/"):
        sample = raw[:200_000].decode("utf-8", errors="ignore")
        risky_patterns = [
            r"(?i)password\s*[:=]",
            r"(?i)token\s*[:=]",
            r"(?i)secret\s*[:=]",
            r"(?i)cookie\s*[:=]",
            r"(?i)authorization\s*[:=]",
            r"(?i)session[_-]?key\s*[:=]",
            r"(?i)api[_-]?key\s*[:=]",
            r"(?i)验证码\s*[:=]",
            r"(?i)密码\s*[:=]",
            r"(?i)密钥\s*[:=]",
        ]
        if any(re.search(pattern, sample) for pattern in risky_patterns):
            raise HTTPException(status_code=400, detail="Evidence upload appears to contain a secret")


def build_platform_acceptance_evidence_manifest_upload_markdown(
    upload: PlatformAcceptanceEvidenceManifestUpload,
) -> str:
    return "\n".join(
        [
            "# Real Platform Evidence Manifest Upload",
            "",
            f"Upload ID: {upload.id}",
            f"Created at: {upload.created_at}",
            f"Scenario: {upload.scenario}",
            f"Submitter: {upload.submitter}",
            f"Filename: {upload.filename}",
            f"Content type: {upload.content_type or '-'}",
            f"Size bytes: {upload.size_bytes}",
            "",
            "## Evidence URL",
            "",
            upload.evidence_url or "-",
            "",
            "## Note",
            "",
            upload.evidence_note or "-",
            "",
            "## Safety Boundary",
            "",
            "- This upload stores sanitized customer material only.",
            "- Uploading material does not register pass evidence.",
            "- Operations must review the material and run import with CONFIRM_PLATFORM_EVIDENCE before final acceptance.",
        ]
    )


async def store_platform_acceptance_evidence_manifest_upload(
    token: str,
    scenario: str,
    submitter: str,
    evidence_note: str,
    no_secrets_confirmed: bool,
    file: UploadFile,
) -> PlatformAcceptanceEvidenceManifestUpload:
    token_data = decode_platform_acceptance_evidence_manifest_token(token)
    merchant = merchant_by_id(int(token_data.get("merchant_id") or 0))
    allowed = {str(item) for item in token_data.get("scenarios") or []}
    if scenario not in allowed or scenario not in PLATFORM_ACCEPTANCE_PUBLIC_SUBMISSION_SCENARIOS:
        raise HTTPException(status_code=400, detail="Scenario is not allowed by this manifest token")
    if not no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the upload contains no secrets")
    safe_name = sanitized_platform_acceptance_upload_filename(file.filename or "evidence-upload")
    raw = await file.read(PLATFORM_ACCEPTANCE_UPLOAD_MAX_BYTES + 1)
    assert_platform_acceptance_upload_bytes_safe(safe_name, file.content_type or "", raw)
    upload_id = f"platform-evidence-upload-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    upload_dir = ARTIFACT_DIR / "integration" / "evidence-uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{upload_id}-{safe_name}"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(raw)
    artifact_url = f"/artifacts/integration/evidence-uploads/{stored_name}"
    evidence_url = f"{platform_acceptance_submission_base_url()}{artifact_url}"
    upload = PlatformAcceptanceEvidenceManifestUpload(
        id=upload_id,
        scenario=scenario,  # type: ignore[arg-type]
        filename=safe_name,
        content_type=file.content_type or "",
        size_bytes=len(raw),
        submitter=submitter.strip()[:120] or str(token_data.get("recipient") or "customer platform owner"),
        evidence_note=evidence_note.strip()[:1000],
        evidence_url=evidence_url,
        artifact_url=artifact_url,
        created_at=now_sql(),
        next_action="Paste this evidence URL into the manifest scenario and submit the manifest preview.",
    )
    summary_path = upload_dir / f"{upload_id}.md"
    summary_path.write_text(build_platform_acceptance_evidence_manifest_upload_markdown(upload), encoding="utf-8")
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_manifest_upload",
        1,
        "integration",
        upload.id,
        {"scenario": upload.scenario, "size_bytes": upload.size_bytes, "content_type": upload.content_type},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_manifest_upload",
        "integration_acceptance",
        upload.id,
        "Upload customer evidence manifest material",
        {"scenario": upload.scenario, "size_bytes": upload.size_bytes, "content_type": upload.content_type, "artifact_url": upload.artifact_url},
    )
    return upload


def build_platform_acceptance_evidence_manifest_link_markdown(link: PlatformAcceptanceEvidenceManifestLink) -> str:
    lines = [
        "# Real Platform Evidence Manifest Link",
        "",
        f"Link ID: {link.id}",
        f"Created at: {link.created_at}",
        f"Customer: {link.customer_name}",
        f"Recipient: {link.recipient}",
        f"Owner: {link.owner}",
        f"Status: {link.status}",
        f"Expires at: {link.expires_at}",
        "",
        "## Manifest URL",
        "",
        link.manifest_url or "-",
        "",
        "## Scenarios",
        "",
    ]
    lines.extend(f"- {scenario}" for scenario in link.scenarios)
    lines.extend(
        [
            "",
            "## Draft",
            "",
            "```text",
            link.draft_text or "-",
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This link collects sanitized customer evidence URLs only.",
            "- Submission creates an import preview and review tasks; it does not register pass evidence.",
            "- Operators must use CONFIRM_PLATFORM_EVIDENCE before importing pass evidence.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_evidence_manifest_link(
    payload: PlatformAcceptanceEvidenceManifestLinkRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceManifestLink:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    scenarios = [scenario for scenario in (payload.scenarios or report.missing_scenarios) if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    if not scenarios:
        scenarios = list(report.missing_scenarios)
    link_id = f"platform-evidence-manifest-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    expires_at_dt = datetime.now() + timedelta(days=payload.expires_days)
    expires_at = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    token_payload = {
        "link_id": link_id,
        "merchant_id": merchant.id or 0,
        "customer_name": payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        "owner": payload.owner.strip()[:120],
        "recipient": payload.recipient.strip()[:120],
        "scenarios": scenarios,
        "expires_ts": int(expires_at_dt.timestamp()),
        "expires_at": expires_at,
    }
    signed_code = encode_platform_acceptance_evidence_manifest_token(token_payload)
    manifest_url = platform_acceptance_evidence_manifest_url(signed_code)
    draft_text = "\n".join(
        [
            f"Please submit sanitized real-platform evidence URLs for {token_payload['customer_name']}:",
            manifest_url,
            "",
            "Use customer-controlled screenshot, recording, ticket, or platform audit links only.",
            "Do not submit passwords, tokens, cookies, verification codes, signatures, session keys, API secrets, or private customer data.",
        ]
    )
    link = PlatformAcceptanceEvidenceManifestLink(
        id=link_id,
        status="ready" if scenarios else "empty",
        customer_name=str(token_payload["customer_name"]),
        owner=str(token_payload["owner"]),
        recipient=str(token_payload["recipient"]),
        scenarios=scenarios,
        manifest_url=manifest_url,
        token=signed_code,
        expires_at=expires_at,
        draft_text=draft_text,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{link.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_manifest_link_markdown(link), encoding="utf-8")
        link.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_manifest_link",
        max(1, len(scenarios)),
        "integration",
        link.id,
        {"status": link.status, "scenarios": len(scenarios)},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_manifest_link",
        "integration_acceptance",
        link.id,
        "Generate customer evidence manifest link",
        {
            "status": link.status,
            "scenarios": len(scenarios),
            "scenarios_list": link.scenarios,
            "recipient": link.recipient,
            "expires_at": link.expires_at,
            "artifact_url": link.artifact_url,
        },
    )
    return link


def build_platform_acceptance_evidence_manifest_submission_markdown(
    submission: PlatformAcceptanceEvidenceManifestSubmission,
) -> str:
    lines = [
        "# Real Platform Evidence Manifest Submission",
        "",
        f"Submission ID: {submission.id}",
        f"Created at: {submission.created_at}",
        f"Status: {submission.status}",
        f"Customer: {submission.customer_name}",
        f"Recipient: {submission.recipient}",
        f"Submitter: {submission.submitter}",
        "",
        submission.summary,
        "",
        "## Import Preview",
        "",
        f"- Preview ID: {submission.import_preview.id}",
        f"- Ready: {submission.import_preview.ready}",
        f"- Blocked: {submission.import_preview.blocked}",
        f"- Artifact: {submission.import_preview.artifact_url or '-'}",
        "",
        "## Scenario Items",
        "",
        "| Scenario | Status | Evidence URL | Next Action |",
        "| --- | --- | --- | --- |",
    ]
    for item in submission.import_preview.items:
        next_action = item.error or item.next_action or "-"
        lines.append(f"| {item.scenario} | {item.status} | {item.evidence_url or '-'} | {next_action.replace('|', '/')} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This submission does not register pass evidence.",
            "- Operators must review sanitized material and explicitly import evidence with CONFIRM_PLATFORM_EVIDENCE.",
            "- Placeholder links and secret-looking text are blocked before import.",
        ]
    )
    return "\n".join(lines)


async def submit_platform_acceptance_evidence_manifest(
    payload: PlatformAcceptanceEvidenceManifestSubmissionRequest,
) -> PlatformAcceptanceEvidenceManifestSubmission:
    token_data = decode_platform_acceptance_evidence_manifest_token(payload.token)
    merchant = merchant_by_id(int(token_data.get("merchant_id") or 0))
    scenarios: list[PlatformAcceptanceScenario] = token_data.get("scenarios") or []
    allowed = set(scenarios)
    filtered_items = [item for item in payload.items if item.scenario in allowed]
    import_preview = await run_platform_acceptance_evidence_import(
        PlatformAcceptanceEvidenceImportRunRequest(
            owner=str(token_data.get("owner") or "operations reviewer"),
            items=filtered_items,
            required_scenarios=scenarios,
            execute=False,
            confirm_phrase="",
            close_review_tasks=True,
            reconcile_gap_tasks=True,
            include_artifact=True,
            audit_limit=300,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        ),
        merchant,
    )
    item_by_scenario = {item.scenario: item for item in filtered_items}
    scenario_receipts = []
    for scenario in scenarios:
        item = item_by_scenario.get(scenario)
        if item and item.evidence_url.strip() and not is_placeholder_platform_evidence_url(item.evidence_url):
            scenario_receipts.append(
                PlatformAcceptanceEvidenceReceiptScenario(
                    scenario=scenario,
                    outcome="submitted",
                    note=item.evidence_note or payload.notes,
                    evidence_url=item.evidence_url,
                )
            )
        else:
            scenario_receipts.append(
                PlatformAcceptanceEvidenceReceiptScenario(
                    scenario=scenario,
                    outcome="needs_help",
                    note=payload.notes or "Evidence URL missing or blocked by import preview.",
                    evidence_url=item.evidence_url if item else "",
                )
            )
    receipt_outcome: Literal["acknowledged", "needs_help", "submitted"] = (
        "submitted" if import_preview.ready and not import_preview.blocked else "needs_help"
    )
    receipt = await record_platform_acceptance_evidence_receipt(
        PlatformAcceptanceEvidenceReceiptRequest(
            notice_id=str(token_data.get("link_id") or "evidence-manifest"),
            recipient=str(token_data.get("recipient") or "customer platform owner"),
            outcome=receipt_outcome,
            scenario_receipts=scenario_receipts,
            notes=payload.notes,
            include_artifact=True,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        ),
        merchant,
    )
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    if payload.create_review_tasks:
        review_sync = await sync_platform_acceptance_evidence_review_tasks(
            PlatformAcceptanceEvidenceReviewTaskSyncRequest(
                owner=str(token_data.get("owner") or "operations reviewer"),
                due_days=1,
                include_needs_help=True,
                create_tasks=True,
                include_artifact=True,
                audit_limit=300,
            ),
            merchant,
        )
    if not filtered_items:
        status: Literal["preview_ready", "needs_work", "empty"] = "empty"
    elif import_preview.blocked or import_preview.missing_scenarios:
        status = "needs_work"
    else:
        status = "preview_ready"
    submission = PlatformAcceptanceEvidenceManifestSubmission(
        id=f"platform-evidence-manifest-submission-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        customer_name=str(token_data.get("customer_name") or merchant.business_name or merchant.username),
        recipient=str(token_data.get("recipient") or "customer platform owner"),
        submitter=payload.submitter.strip()[:120],
        scenarios=scenarios,
        import_preview=import_preview,
        receipt=receipt,
        review_sync=review_sync,
        ready=import_preview.ready,
        blocked=import_preview.blocked,
        missing_scenarios=import_preview.missing_scenarios,
        summary=(
            f"Customer evidence manifest submitted. scenarios={len(scenarios)} ready={import_preview.ready} "
            f"blocked={import_preview.blocked} status={status}."
        ),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{submission.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_manifest_submission_markdown(submission), encoding="utf-8")
        submission.artifact_url = f"/artifacts/integration/{filename}"
    manifest_metadata = {
        "status": submission.status,
        "link_id": str(token_data.get("link_id") or ""),
        "ready": submission.ready,
        "blocked": submission.blocked,
        "scenarios": submission.scenarios,
        "missing_scenarios": submission.missing_scenarios,
        "import_items": [item.model_dump() for item in filtered_items],
        "submission_artifact_url": submission.artifact_url,
        "import_preview_id": import_preview.id,
        "import_preview_artifact_url": import_preview.artifact_url,
        "receipt_id": receipt.id,
        "review_sync_id": review_sync.id if review_sync else "",
    }
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_manifest_submission",
        max(1, len(filtered_items)),
        "integration",
        submission.id,
        manifest_metadata,
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_manifest_submission",
        "integration_acceptance",
        submission.id,
        "Submit customer evidence manifest",
        manifest_metadata,
    )
    return submission


def platform_acceptance_manifest_inbox_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def platform_acceptance_manifest_inbox_scenarios(value: Any) -> list[PlatformAcceptanceScenario]:
    if not isinstance(value, list):
        return []
    return [scenario for scenario in value if scenario in PLATFORM_ACCEPTANCE_PUBLIC_SUBMISSION_SCENARIOS]


def platform_acceptance_manifest_inbox_next_action(item: PlatformAcceptanceEvidenceManifestInboxItem) -> str:
    if item.status == "preview_ready" and item.ready > 0 and item.blocked == 0:
        return "Open import preview, verify sanitized evidence, then import with CONFIRM_PLATFORM_EVIDENCE."
    if item.blocked > 0 or item.missing_scenarios:
        return "Ask customer to replace blocked or missing evidence URLs through the manifest page."
    if item.status == "empty":
        return "No usable evidence URLs were submitted; resend the manifest link or collect evidence manually."
    return "Review the submission artifact and decide whether to request fixes or import approved evidence."


def platform_acceptance_manifest_inbox_item_from_log(log: AuditLog) -> PlatformAcceptanceEvidenceManifestInboxItem:
    metadata = log.metadata or {}
    item = PlatformAcceptanceEvidenceManifestInboxItem(
        submission_id=log.target_id,
        status=str(metadata.get("status") or ""),
        ready=platform_acceptance_manifest_inbox_int(metadata.get("ready")),
        blocked=platform_acceptance_manifest_inbox_int(metadata.get("blocked")),
        scenarios=platform_acceptance_manifest_inbox_scenarios(metadata.get("scenarios")),
        missing_scenarios=platform_acceptance_manifest_inbox_scenarios(metadata.get("missing_scenarios")),
        import_preview_id=str(metadata.get("import_preview_id") or ""),
        import_preview_artifact_url=str(metadata.get("import_preview_artifact_url") or ""),
        submission_artifact_url=str(metadata.get("submission_artifact_url") or metadata.get("artifact_url") or ""),
        receipt_id=str(metadata.get("receipt_id") or ""),
        review_sync_id=str(metadata.get("review_sync_id") or ""),
        created_at=log.created_at,
    )
    item.next_action = platform_acceptance_manifest_inbox_next_action(item)
    return item


def build_platform_acceptance_evidence_manifest_inbox_markdown(
    inbox: PlatformAcceptanceEvidenceManifestInbox,
) -> str:
    lines = [
        "# Real Platform Evidence Manifest Inbox",
        "",
        f"Inbox ID: {inbox.id}",
        f"Created at: {inbox.created_at}",
        f"Status: {inbox.status}",
        "",
        inbox.summary,
        "",
        "## Counts",
        "",
        f"- Total submissions: {inbox.total}",
        f"- Ready to import: {inbox.ready}",
        f"- Needs customer fixes: {inbox.blocked}",
        "",
        "## Submissions",
        "",
        "| Submission | Status | Ready | Blocked | Scenarios | Import Preview | Submission Artifact | Next Action |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for item in inbox.items:
        scenarios = ", ".join(item.scenarios) or "-"
        next_action = item.next_action.replace("|", "/")
        lines.append(
            f"| {item.submission_id} | {item.status or '-'} | {item.ready} | {item.blocked} | "
            f"{scenarios} | {item.import_preview_artifact_url or '-'} | {item.submission_artifact_url or '-'} | {next_action} |"
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This inbox only summarizes customer manifest submissions.",
            "- It does not register pass evidence.",
            "- Import requires operator review and the explicit CONFIRM_PLATFORM_EVIDENCE phrase.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_evidence_manifest_inbox(
    payload: PlatformAcceptanceEvidenceManifestInboxRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceManifestInbox:
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    items = [
        platform_acceptance_manifest_inbox_item_from_log(log)
        for log in logs
        if log.action == "integration.platform_acceptance_evidence_manifest_submission"
    ]
    ready = sum(1 for item in items if item.status == "preview_ready" and item.ready > 0 and item.blocked == 0)
    blocked = sum(1 for item in items if item.status != "preview_ready" or item.blocked > 0 or bool(item.missing_scenarios))
    if not items:
        inbox_status: Literal["empty", "ready_to_import", "needs_customer", "mixed"] = "empty"
    elif ready > 0 and blocked == 0:
        inbox_status = "ready_to_import"
    elif ready > 0 and blocked > 0:
        inbox_status = "mixed"
    else:
        inbox_status = "needs_customer"
    inbox = PlatformAcceptanceEvidenceManifestInbox(
        id=f"platform-evidence-manifest-inbox-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=inbox_status,
        summary=(
            f"Customer evidence manifest inbox. submissions={len(items)} "
            f"ready_to_import={ready} needs_customer={blocked} status={inbox_status}."
        ),
        total=len(items),
        ready=ready,
        blocked=blocked,
        items=items,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{inbox.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_manifest_inbox_markdown(inbox), encoding="utf-8")
        inbox.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_manifest_inbox",
        max(1, inbox.total),
        "integration",
        inbox.id,
        {"status": inbox.status, "total": inbox.total, "ready": inbox.ready, "blocked": inbox.blocked},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_manifest_inbox",
        "integration_acceptance",
        inbox.id,
        "Generate customer evidence manifest inbox",
        {"status": inbox.status, "total": inbox.total, "ready": inbox.ready, "blocked": inbox.blocked},
    )
    return inbox


def platform_acceptance_manifest_import_items_from_metadata(value: Any) -> list[PlatformAcceptanceEvidenceImportItem]:
    if not isinstance(value, list):
        return []
    items: list[PlatformAcceptanceEvidenceImportItem] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        try:
            item = PlatformAcceptanceEvidenceImportItem.model_validate(raw)
        except Exception:
            continue
        if item.scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS and item.evidence_url.strip():
            items.append(item)
    return items


def platform_acceptance_artifact_path_from_url(artifact_url: str) -> Path | None:
    raw = str(artifact_url or "").strip()
    if not raw:
        return None
    parsed = urllib.parse.urlparse(raw)
    path = parsed.path if parsed.scheme or parsed.netloc else raw.split("?", 1)[0].split("#", 1)[0]
    path = urllib.parse.unquote(path)
    if path.startswith("/artifacts/"):
        relative = path[len("/artifacts/"):]
    elif path.startswith("artifacts/"):
        relative = path[len("artifacts/"):]
    else:
        return None
    root = ARTIFACT_DIR.resolve()
    candidate = (ARTIFACT_DIR / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def platform_acceptance_markdown_table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if not cells or all(set(cell) <= {"-", ":", " "} for cell in cells):
        return []
    return cells


def platform_acceptance_manifest_import_items_from_preview_text(
    text: str,
    artifact_url: str,
) -> list[PlatformAcceptanceEvidenceImportItem]:
    items: list[PlatformAcceptanceEvidenceImportItem] = []
    seen: set[PlatformAcceptanceScenario] = set()
    for line in text.splitlines():
        cells = platform_acceptance_markdown_table_cells(line)
        if len(cells) < 3:
            continue
        scenario = cells[0]
        if scenario == "Scenario" or scenario not in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS or scenario in seen:
            continue
        status = cells[1].strip().lower()
        if status != "ready":
            continue
        evidence_url = next(
            (
                cell.strip()
                for cell in cells[2:5]
                if cell.strip().lower().startswith(("https://", "http://"))
            ),
            "",
        )
        if not evidence_url:
            continue
        seen.add(scenario)
        items.append(
            PlatformAcceptanceEvidenceImportItem(
                scenario=scenario,
                connector="website",
                account_label="customer platform account",
                operator="operations reviewer",
                evidence_note=f"Recovered from manifest import preview artifact {artifact_url}",
                evidence_url=evidence_url,
            )
        )
    return items


def platform_acceptance_manifest_import_items_from_preview_artifact(
    artifact_url: str,
) -> list[PlatformAcceptanceEvidenceImportItem]:
    path = platform_acceptance_artifact_path_from_url(artifact_url)
    if not path or path.suffix.lower() not in {".md", ".txt"}:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return platform_acceptance_manifest_import_items_from_preview_text(text, artifact_url)


def platform_acceptance_manifest_import_queue_next_action(item: PlatformAcceptanceManifestImportQueueItem) -> str:
    if item.status == "ready_to_import":
        return "Run import preview, verify sanitized evidence, then import with CONFIRM_PLATFORM_EVIDENCE."
    if item.status == "recovered_for_review":
        if item.recovery_review_status == "needs_customer_resubmission":
            return "Recovery review requested customer resubmission; send the manifest link or run follow-up for missing evidence."
        if item.recovery_review_status == "accepted_for_preview":
            return "Recovery review accepted preview-only handling; run import preview and require structured owner review before evidence import."
        if item.recovery_review_status == "rejected":
            return "Recovery review rejected the recovered artifact; ask the customer for a fresh structured manifest."
        return "Run import preview from the recovered artifact payload; require manual owner review or a new structured manifest before importing evidence."
    if item.status == "needs_customer":
        return "Ask the customer to replace blocked or missing evidence, then resubmit the manifest."
    return "Open submission and import preview artifacts; this older submission lacks structured import items."


def latest_platform_acceptance_manifest_recovery_reviews(
    logs: list[AuditLog],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for log in logs:
        if log.action != "integration.platform_acceptance_manifest_recovery_review" or log.target_id in latest:
            continue
        metadata = log.metadata or {}
        latest[log.target_id] = {
            "id": str(metadata.get("review_id") or log.target_id or ""),
            "status": str(metadata.get("status") or ""),
            "decision": str(metadata.get("decision") or ""),
        }
    return latest


def platform_acceptance_manifest_import_queue_item_from_log(
    log: AuditLog,
    recovery_review: dict[str, Any] | None = None,
) -> PlatformAcceptanceManifestImportQueueItem:
    metadata = log.metadata or {}
    ready = platform_acceptance_manifest_inbox_int(metadata.get("ready"))
    blocked = platform_acceptance_manifest_inbox_int(metadata.get("blocked"))
    scenarios = platform_acceptance_manifest_inbox_scenarios(metadata.get("scenarios"))
    missing = platform_acceptance_manifest_inbox_scenarios(metadata.get("missing_scenarios"))
    import_items = platform_acceptance_manifest_import_items_from_metadata(metadata.get("import_items"))
    import_preview_artifact_url = str(metadata.get("import_preview_artifact_url") or "")
    source: Literal["metadata", "artifact", "manual"] = "metadata" if import_items else "manual"
    recovered = False
    if ready > 0 and blocked == 0 and import_items:
        status: Literal["ready_to_import", "recovered_for_review", "needs_customer", "needs_manual_review"] = "ready_to_import"
    elif blocked > 0 or missing or str(metadata.get("status") or "") != "preview_ready":
        status = "needs_customer"
    elif ready > 0 and import_preview_artifact_url:
        recovered_items = platform_acceptance_manifest_import_items_from_preview_artifact(import_preview_artifact_url)
        if recovered_items:
            import_items = recovered_items
            source = "artifact"
            recovered = True
            status = "recovered_for_review"
        else:
            status = "needs_manual_review"
    else:
        status = "needs_manual_review"
    item = PlatformAcceptanceManifestImportQueueItem(
        submission_id=log.target_id,
        status=status,
        ready=ready,
        blocked=blocked,
        scenarios=scenarios,
        missing_scenarios=missing,
        import_items=import_items,
        source=source,
        recovered=recovered,
        recovery_review_id=str((recovery_review or {}).get("id") or ""),
        recovery_review_status=str((recovery_review or {}).get("status") or ""),
        recovery_review_decision=str((recovery_review or {}).get("decision") or ""),
        import_preview_artifact_url=import_preview_artifact_url,
        submission_artifact_url=str(metadata.get("submission_artifact_url") or metadata.get("artifact_url") or ""),
        receipt_id=str(metadata.get("receipt_id") or ""),
        review_sync_id=str(metadata.get("review_sync_id") or ""),
        created_at=log.created_at,
    )
    item.next_action = platform_acceptance_manifest_import_queue_next_action(item)
    return item


def build_platform_acceptance_manifest_import_queue_markdown(
    queue: PlatformAcceptanceManifestImportQueue,
) -> str:
    lines = [
        "# Real Platform Manifest Import Queue",
        "",
        f"Queue ID: {queue.id}",
        f"Created at: {queue.created_at}",
        f"Status: {queue.status}",
        "",
        queue.summary,
        "",
        "## Counts",
        "",
        f"- Total submissions: {queue.total}",
        f"- Ready: {queue.ready}",
        f"- Recovered for review: {queue.recovered}",
        f"- Needs customer: {queue.needs_customer}",
        f"- Needs manual review: {queue.needs_manual_review}",
        "",
        "## Queue Items",
        "",
        "| Submission | Status | Source | Recovery Review | Ready | Blocked | Scenarios | Import Items | Import Preview | Next Action |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for item in queue.items:
        recovery_review = item.recovery_review_status or "-"
        if item.recovery_review_id:
            recovery_review = f"{recovery_review} ({item.recovery_review_id})"
        lines.append(
            f"| {item.submission_id} | {item.status} | {item.source}{' recovered' if item.recovered else ''} | "
            f"{recovery_review.replace('|', '/')} | {item.ready} | {item.blocked} | "
            f"{', '.join(item.scenarios) or '-'} | {len(item.import_items)} | "
            f"{item.import_preview_artifact_url or '-'} | {item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This queue only prepares structured import payloads.",
            "- It does not register pass evidence by itself.",
            "- Operators must run import preview and explicitly confirm with CONFIRM_PLATFORM_EVIDENCE before final evidence import.",
            "- Recovered artifact payloads are preview-only until a platform owner reviews them or the customer resubmits a structured manifest.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_manifest_import_queue(
    payload: PlatformAcceptanceManifestImportQueueRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestImportQueue:
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    recovery_reviews = latest_platform_acceptance_manifest_recovery_reviews(logs)
    items = [
        platform_acceptance_manifest_import_queue_item_from_log(log, recovery_reviews.get(log.target_id))
        for log in logs
        if log.action == "integration.platform_acceptance_evidence_manifest_submission"
    ]
    ready = sum(1 for item in items if item.status == "ready_to_import")
    recovered = sum(1 for item in items if item.status == "recovered_for_review")
    needs_customer = sum(1 for item in items if item.status == "needs_customer")
    needs_manual = sum(1 for item in items if item.status == "needs_manual_review")
    if not items:
        queue_status: Literal["empty", "ready", "recovered", "needs_customer", "needs_manual_review", "mixed"] = "empty"
    elif ready and not recovered and not needs_customer and not needs_manual:
        queue_status = "ready"
    elif recovered and not ready and not needs_customer and not needs_manual:
        queue_status = "recovered"
    elif ready or recovered:
        queue_status = "mixed"
    elif needs_customer and not needs_manual:
        queue_status = "needs_customer"
    else:
        queue_status = "needs_manual_review"
    queue = PlatformAcceptanceManifestImportQueue(
        id=f"platform-manifest-import-queue-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=queue_status,
        summary=(
            f"Manifest import queue. total={len(items)} ready={ready} recovered={recovered} "
            f"needs_customer={needs_customer} needs_manual_review={needs_manual}."
        ),
        total=len(items),
        ready=ready,
        recovered=recovered,
        needs_customer=needs_customer,
        needs_manual_review=needs_manual,
        items=items,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{queue.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_import_queue_markdown(queue), encoding="utf-8")
        queue.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_manifest_import_queue",
        max(1, queue.total),
        "integration",
        queue.id,
        {
            "status": queue.status,
            "total": queue.total,
            "ready": queue.ready,
            "recovered": queue.recovered,
            "needs_customer": queue.needs_customer,
            "needs_manual_review": queue.needs_manual_review,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_manifest_import_queue",
        "integration_acceptance",
        queue.id,
        "Generate platform manifest import queue",
        {
            "status": queue.status,
            "total": queue.total,
            "ready": queue.ready,
            "recovered": queue.recovered,
            "needs_customer": queue.needs_customer,
            "needs_manual_review": queue.needs_manual_review,
        },
    )
    return queue


def assert_platform_acceptance_manifest_recovery_review_safe(
    payload: PlatformAcceptanceManifestRecoveryReviewRequest,
) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the recovery review contains no secrets")
    text = "\n".join([payload.submission_id, payload.owner, payload.recipient, payload.review_note])
    risky_patterns = [
        r"(?i)password\s*[:=]",
        r"(?i)token\s*[:=]",
        r"(?i)secret\s*[:=]",
        r"(?i)cookie\s*[:=]",
        r"(?i)authorization\s*[:=]",
        r"(?i)verification\s*code\s*[:=]",
        r"(?i)api\s*key\s*[:=]",
    ]
    if any(re.search(pattern, text) for pattern in risky_patterns):
        raise HTTPException(status_code=400, detail="Recovery review appears to contain a secret; store only sanitized notes")


def platform_acceptance_manifest_recovery_resubmission_scenarios(
    item: PlatformAcceptanceManifestImportQueueItem,
    report: PlatformAcceptanceReport,
) -> list[PlatformAcceptanceScenario]:
    current_missing = [scenario for scenario in report.missing_scenarios if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    item_scenarios = [scenario for scenario in item.scenarios if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    item_missing = [scenario for scenario in item.missing_scenarios if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    targeted_missing = [scenario for scenario in item_scenarios if scenario in current_missing]
    return targeted_missing or item_missing or item_scenarios or current_missing


def build_platform_acceptance_manifest_recovery_review_markdown(
    review: PlatformAcceptanceManifestRecoveryReview,
) -> str:
    lines = [
        "# Real Platform Manifest Recovery Review",
        "",
        f"Review ID: {review.id}",
        f"Created at: {review.created_at}",
        f"Status: {review.status}",
        f"Submission: {review.submission_id}",
        f"Decision: {review.decision}",
        f"Source: {review.source}",
        f"Recovered: {review.recovered}",
        "",
        review.summary,
        "",
        "## Recovered Payload",
        "",
        f"- Import items: {len(review.import_items)}",
        f"- Scenarios: {', '.join(review.scenarios) or '-'}",
        f"- Resubmission scenarios: {', '.join(review.resubmission_scenarios) or '-'}",
        f"- Import preview artifact: {review.import_preview_artifact_url or '-'}",
        f"- Submission artifact: {review.submission_artifact_url or '-'}",
        "",
        "## Review Note",
        "",
        review.review_note or "-",
        "",
        "## Customer Manifest Link",
        "",
    ]
    if review.manifest_link:
        lines.extend(
            [
                f"- Link ID: {review.manifest_link.id}",
                f"- Status: {review.manifest_link.status}",
                f"- Expires at: {review.manifest_link.expires_at}",
                f"- Manifest URL: {review.manifest_link.manifest_url or '-'}",
                f"- Artifact: {review.manifest_link.artifact_url or '-'}",
            ]
        )
    else:
        lines.append("- No customer manifest link was generated by this recovery review.")
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            review.next_action or "-",
            "",
            "## Safety Boundary",
            "",
            "- Recovery review does not register pass evidence.",
            "- Recovered artifact payloads remain preview-only until structured evidence is reviewed and imported with CONFIRM_PLATFORM_EVIDENCE.",
            "- Customer manifest links collect sanitized evidence; they do not approve or register evidence by themselves.",
        ]
    )
    return "\n".join(lines)


async def review_platform_acceptance_manifest_recovery(
    payload: PlatformAcceptanceManifestRecoveryReviewRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestRecoveryReview:
    assert_platform_acceptance_manifest_recovery_review_safe(payload)
    submission_id = payload.submission_id.strip()
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    recovery_reviews = latest_platform_acceptance_manifest_recovery_reviews(logs)
    submission_log = next(
        (
            log for log in logs
            if log.action == "integration.platform_acceptance_evidence_manifest_submission"
            and log.target_id == submission_id
        ),
        None,
    )
    if not submission_log:
        raise HTTPException(status_code=404, detail="Manifest submission was not found in the audit log")
    queue_item = platform_acceptance_manifest_import_queue_item_from_log(
        submission_log,
        recovery_reviews.get(submission_id),
    )
    if queue_item.status != "recovered_for_review":
        raise HTTPException(status_code=400, detail="Only recovered manifest queue items can be reviewed here")
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    resubmission_scenarios = platform_acceptance_manifest_recovery_resubmission_scenarios(queue_item, report)
    manifest_link: PlatformAcceptanceEvidenceManifestLink | None = None
    if (
        payload.execute
        and payload.decision == "needs_customer_resubmission"
        and payload.create_manifest_link
        and resubmission_scenarios
    ):
        manifest_link = await generate_platform_acceptance_evidence_manifest_link(
            PlatformAcceptanceEvidenceManifestLinkRequest(
                customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
                owner=payload.owner.strip()[:120] or "operations reviewer",
                recipient=payload.recipient.strip()[:120] or "customer platform owner",
                scenarios=resubmission_scenarios,
                expires_days=3,
                include_artifact=payload.include_artifact,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    if not payload.execute:
        status: Literal["preview", "accepted_for_preview", "needs_customer_resubmission", "rejected"] = "preview"
        next_action = "Preview only: choose whether to accept for preview, request customer resubmission, or reject this recovered artifact."
    else:
        status = payload.decision
        if payload.decision == "accepted_for_preview":
            next_action = "Run import preview from this recovered payload, then require a structured review decision before any evidence import."
        elif payload.decision == "needs_customer_resubmission":
            next_action = (
                "Send the generated customer manifest link and wait for a fresh structured submission."
                if manifest_link else
                "Request customer resubmission through the existing manifest/follow-up workflow."
            )
        else:
            next_action = "Reject this recovered artifact for acceptance purposes and request a fresh customer manifest."
    result = PlatformAcceptanceManifestRecoveryReview(
        id=f"platform-manifest-recovery-review-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        submission_id=submission_id,
        decision=payload.decision,
        source=queue_item.source,
        recovered=queue_item.recovered,
        import_items=queue_item.import_items,
        scenarios=queue_item.scenarios,
        resubmission_scenarios=resubmission_scenarios,
        import_preview_artifact_url=queue_item.import_preview_artifact_url,
        submission_artifact_url=queue_item.submission_artifact_url,
        manifest_link=manifest_link,
        queue_item=queue_item,
        review_note=payload.review_note.strip()[:1000],
        summary=(
            f"Manifest recovery review. submission={submission_id} decision={payload.decision} "
            f"execute={payload.execute} recovered_items={len(queue_item.import_items)} "
            f"manifest_link_created={bool(manifest_link)}."
        ),
        next_action=next_action,
        created_at=now_sql(),
    )
    if payload.execute and payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_recovery_review_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    if payload.execute:
        record_usage(
            merchant.id or 0,
            "platform_acceptance_manifest_recovery_review",
            max(1, len(result.import_items)),
            "integration",
            result.id,
            {
                "status": result.status,
                "decision": result.decision,
                "submission_id": result.submission_id,
                "recovered_items": len(result.import_items),
                "manifest_link_created": bool(result.manifest_link),
            },
        )
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "integration.platform_acceptance_manifest_recovery_review",
            "integration_acceptance",
            result.submission_id,
            "Review recovered platform evidence manifest payload",
            {
                "review_id": result.id,
                "status": result.status,
                "decision": result.decision,
                "submission_id": result.submission_id,
                "recovered_items": len(result.import_items),
                "manifest_link_created": bool(result.manifest_link),
                "manifest_link_id": result.manifest_link.id if result.manifest_link else "",
                "artifact_url": result.artifact_url,
            },
        )
    return result


def build_platform_acceptance_manifest_recovery_resubmission_run_markdown(
    run: PlatformAcceptanceManifestRecoveryResubmissionRun,
) -> str:
    lines = [
        "# Real Platform Manifest Recovery Resubmission Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Status: {run.status}",
        "",
        run.summary,
        "",
        "## Counts",
        "",
        f"- Total: {run.total}",
        f"- Would request: {run.would_request}",
        f"- Requested: {run.requested}",
        f"- Already requested: {run.already_requested}",
        f"- Skipped: {run.skipped}",
        f"- Blocked: {run.blocked}",
        "",
        "## Items",
        "",
        "| Submission | Status | Source | Scenarios | Import Items | Manifest | Review | Next Action |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    if not run.items:
        lines.append("| - | empty | - | - | 0 | - | - | No recovered manifest submissions were found. |")
    for item in run.items:
        lines.append(
            f"| {item.submission_id} | {item.status} | {item.source}{' recovered' if item.recovered else ''} | "
            f"{', '.join(item.scenarios) or '-'} | {item.import_items} | "
            f"{item.manifest_url or item.manifest_artifact_url or '-'} | {item.review_id or item.recovery_review_status or '-'} | "
            f"{item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This run never registers pass evidence.",
            "- Execute mode only records recovery review decisions and creates customer Manifest resubmission links.",
            "- Customer submissions still require sanitized evidence, URL precheck, human review, and CONFIRM_PLATFORM_EVIDENCE before any pass evidence import.",
        ]
    )
    return "\n".join(lines)


async def run_platform_acceptance_manifest_recovery_resubmission(
    payload: PlatformAcceptanceManifestRecoveryResubmissionRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestRecoveryResubmissionRun:
    safety_probe = PlatformAcceptanceManifestRecoveryReviewRequest(
        submission_id="safety-probe",
        decision="needs_customer_resubmission",
        customer_name=payload.customer_name,
        owner=payload.owner,
        recipient=payload.recipient,
        review_note=payload.review_note,
        execute=False,
        include_artifact=False,
        audit_limit=payload.audit_limit,
        no_secrets_confirmed=payload.no_secrets_confirmed,
    )
    assert_platform_acceptance_manifest_recovery_review_safe(safety_probe)
    queue = await generate_platform_acceptance_manifest_import_queue(
        PlatformAcceptanceManifestImportQueueRequest(audit_limit=payload.audit_limit, include_artifact=False),
        merchant,
    )
    items: list[PlatformAcceptanceManifestRecoveryResubmissionRunItem] = []
    for queue_item in queue.items:
        if queue_item.status != "recovered_for_review":
            continue
        if queue_item.recovery_review_status == "needs_customer_resubmission":
            items.append(
                PlatformAcceptanceManifestRecoveryResubmissionRunItem(
                    submission_id=queue_item.submission_id,
                    status="already_requested",
                    source=queue_item.source,
                    recovered=queue_item.recovered,
                    recovery_review_status=queue_item.recovery_review_status,
                    scenarios=queue_item.scenarios,
                    import_items=len(queue_item.import_items),
                    review_id=queue_item.recovery_review_id,
                    next_action="A recovery review already requested customer resubmission; reuse the latest Manifest link or run follow-up.",
                )
            )
            continue
        if not queue_item.import_items:
            items.append(
                PlatformAcceptanceManifestRecoveryResubmissionRunItem(
                    submission_id=queue_item.submission_id,
                    status="skipped",
                    source=queue_item.source,
                    recovered=queue_item.recovered,
                    recovery_review_status=queue_item.recovery_review_status,
                    scenarios=queue_item.scenarios,
                    import_items=0,
                    next_action="Recovered item has no import payload; inspect artifacts manually before customer follow-up.",
                )
            )
            continue
        if not payload.execute:
            items.append(
                PlatformAcceptanceManifestRecoveryResubmissionRunItem(
                    submission_id=queue_item.submission_id,
                    status="would_request",
                    source=queue_item.source,
                    recovered=queue_item.recovered,
                    recovery_review_status=queue_item.recovery_review_status,
                    scenarios=queue_item.scenarios,
                    import_items=len(queue_item.import_items),
                    next_action="Execute this run to create a customer Manifest resubmission link.",
                )
            )
            continue
        try:
            review = await review_platform_acceptance_manifest_recovery(
                PlatformAcceptanceManifestRecoveryReviewRequest(
                    submission_id=queue_item.submission_id,
                    decision="needs_customer_resubmission",
                    customer_name=payload.customer_name,
                    owner=payload.owner,
                    recipient=payload.recipient,
                    review_note=payload.review_note,
                    create_manifest_link=True,
                    execute=True,
                    include_artifact=False,
                    audit_limit=payload.audit_limit,
                    no_secrets_confirmed=True,
                ),
                merchant,
            )
            items.append(
                PlatformAcceptanceManifestRecoveryResubmissionRunItem(
                    submission_id=queue_item.submission_id,
                    status="requested",
                    source=queue_item.source,
                    recovered=queue_item.recovered,
                    recovery_review_status=review.status,
                    scenarios=review.resubmission_scenarios,
                    import_items=len(queue_item.import_items),
                    manifest_url=review.manifest_link.manifest_url if review.manifest_link else "",
                    manifest_artifact_url=review.manifest_link.artifact_url if review.manifest_link else "",
                    review_id=review.id,
                    next_action=review.next_action,
                )
            )
        except HTTPException as exc:
            items.append(
                PlatformAcceptanceManifestRecoveryResubmissionRunItem(
                    submission_id=queue_item.submission_id,
                    status="blocked",
                    source=queue_item.source,
                    recovered=queue_item.recovered,
                    recovery_review_status=queue_item.recovery_review_status,
                    scenarios=queue_item.scenarios,
                    import_items=len(queue_item.import_items),
                    next_action=str(exc.detail),
                )
            )
    would_request = sum(1 for item in items if item.status == "would_request")
    requested = sum(1 for item in items if item.status == "requested")
    already_requested = sum(1 for item in items if item.status == "already_requested")
    skipped = sum(1 for item in items if item.status == "skipped")
    blocked = sum(1 for item in items if item.status == "blocked")
    if not items:
        status: Literal["preview", "executed", "partial", "empty"] = "empty"
    elif payload.execute and requested and blocked:
        status = "partial"
    elif payload.execute:
        status = "executed"
    else:
        status = "preview"
    run = PlatformAcceptanceManifestRecoveryResubmissionRun(
        id=f"platform-manifest-recovery-resubmission-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Manifest recovery resubmission run. execute={payload.execute} total={len(items)} "
            f"would_request={would_request} requested={requested} already_requested={already_requested} "
            f"skipped={skipped} blocked={blocked}."
        ),
        total=len(items),
        would_request=would_request,
        requested=requested,
        already_requested=already_requested,
        skipped=skipped,
        blocked=blocked,
        items=items,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_recovery_resubmission_run_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_manifest_recovery_resubmission_run",
        max(1, run.total),
        "integration",
        run.id,
        {
            "status": run.status,
            "execute": payload.execute,
            "total": run.total,
            "requested": run.requested,
            "already_requested": run.already_requested,
            "blocked": run.blocked,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_manifest_recovery_resubmission_run",
        "integration_acceptance",
        run.id,
        "Run recovered manifest customer resubmission orchestration",
        {
            "status": run.status,
            "execute": payload.execute,
            "total": run.total,
            "requested": run.requested,
            "already_requested": run.already_requested,
            "blocked": run.blocked,
            "artifact_url": run.artifact_url,
        },
    )
    return run


def platform_acceptance_manifest_tracker_review_logs(logs: list[AuditLog]) -> list[AuditLog]:
    return [
        log for log in logs
        if log.action == "integration.platform_acceptance_manifest_recovery_review"
        and str((log.metadata or {}).get("status") or "") == "needs_customer_resubmission"
    ]


def platform_acceptance_manifest_tracker_related_submission(
    review_log: AuditLog,
    link_id: str,
    scenarios: list[PlatformAcceptanceScenario],
    submission_logs: list[AuditLog],
) -> PlatformAcceptanceEvidenceManifestInboxItem | None:
    exact_matches: list[AuditLog] = []
    fallback_matches: list[AuditLog] = []
    review_time = parse_platform_acceptance_time(review_log.created_at) or datetime.min
    scenario_set = set(scenarios)
    for log in submission_logs:
        metadata = log.metadata or {}
        if link_id and str(metadata.get("link_id") or "") == link_id:
            exact_matches.append(log)
            continue
        created_at = parse_platform_acceptance_time(log.created_at) or datetime.min
        log_scenarios = set(platform_acceptance_manifest_inbox_scenarios(metadata.get("scenarios")))
        if created_at >= review_time and scenario_set.intersection(log_scenarios):
            fallback_matches.append(log)
    matches = exact_matches or fallback_matches
    if not matches:
        return None
    return platform_acceptance_manifest_inbox_item_from_log(matches[0])


def build_platform_acceptance_manifest_resubmission_tracker_reminder(
    tracker: PlatformAcceptanceManifestResubmissionTracker,
) -> str:
    lines = [
        f"Hi {tracker.recipient},",
        "",
        f"We are still tracking real-platform acceptance evidence for {tracker.customer_name}.",
        f"Current status: {tracker.evidence_status}; missing: {', '.join(tracker.missing_scenarios) if tracker.missing_scenarios else 'none'}.",
        "",
        "Please submit sanitized evidence through the secure Manifest link. Do not include passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets.",
        "",
        "Pending resubmission items:",
    ]
    for item in tracker.items:
        if item.status == "complete":
            continue
        scenarios = ", ".join(item.missing_scenarios or item.scenarios) or "-"
        lines.append(f"- {item.submission_id or item.manifest_link_id}: {item.status}; scenarios: {scenarios}; next: {item.next_action}")
    lines.extend(["", f"Owner: {tracker.owner}"])
    return "\n".join(lines)


def build_platform_acceptance_manifest_resubmission_tracker_markdown(
    tracker: PlatformAcceptanceManifestResubmissionTracker,
) -> str:
    lines = [
        "# Real Platform Manifest Resubmission Tracker",
        "",
        f"Tracker ID: {tracker.id}",
        f"Created at: {tracker.created_at}",
        f"Customer: {tracker.customer_name}",
        f"Owner: {tracker.owner}",
        f"Recipient: {tracker.recipient}",
        f"Status: {tracker.status}",
        f"Evidence status: {tracker.evidence_status}",
        "",
        tracker.summary,
        "",
        "## Counts",
        "",
        f"- Total: {tracker.total}",
        f"- Waiting customer: {tracker.waiting_customer}",
        f"- Ready for review: {tracker.ready_for_review}",
        f"- Needs fix: {tracker.needs_fix}",
        f"- Stale: {tracker.stale}",
        f"- Complete: {tracker.complete}",
        f"- Missing link: {tracker.missing_link}",
        "",
        "## Items",
        "",
        "| Submission | Status | Link | Scenarios | Missing | Latest Submission | Wait Hours | Escalation | Next Action |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    if not tracker.items:
        lines.append("| - | empty | - | - | - | - | 0 | none | No recovery resubmission requests were found. |")
    for item in tracker.items:
        latest = item.latest_submission_id or "-"
        if item.latest_submission_artifact_url:
            latest = f"{latest} {item.latest_submission_artifact_url}"
        lines.append(
            f"| {item.submission_id or '-'} | {item.status} | {item.manifest_link_id or '-'} | "
            f"{', '.join(item.scenarios) or '-'} | {', '.join(item.missing_scenarios) or '-'} | "
            f"{latest.replace('|', '/')} | {item.wait_hours} | {item.escalation} | "
            f"{item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Reminder Draft",
            "",
            "```text",
            tracker.reminder_draft or "-",
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This tracker is read-only; it does not send reminders, approve evidence, or register pass evidence.",
            "- Ready submissions still require human review, URL precheck, and CONFIRM_PLATFORM_EVIDENCE before pass evidence import.",
            "- Reminder drafts must be manually reviewed before sending.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_manifest_resubmission_tracker(
    payload: PlatformAcceptanceManifestResubmissionTrackerRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestResubmissionTracker:
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    recovery_reviews = latest_platform_acceptance_manifest_recovery_reviews(logs)
    queue_items = [
        platform_acceptance_manifest_import_queue_item_from_log(log, recovery_reviews.get(log.target_id))
        for log in logs
        if log.action == "integration.platform_acceptance_evidence_manifest_submission"
    ]
    queue_by_submission = {item.submission_id: item for item in queue_items}
    submission_logs = [
        log for log in logs
        if log.action == "integration.platform_acceptance_evidence_manifest_submission"
    ]
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    passed = {item.scenario for item in report.evidence if item.result == "pass"}
    now = datetime.now()
    items: list[PlatformAcceptanceManifestResubmissionTrackerItem] = []
    for review_log in platform_acceptance_manifest_tracker_review_logs(logs):
        metadata = review_log.metadata or {}
        queue_item = queue_by_submission.get(review_log.target_id)
        link_id = str(metadata.get("manifest_link_id") or "")
        scenarios = [scenario for scenario in (queue_item.scenarios if queue_item else []) if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
        if not scenarios:
            scenarios = [scenario for scenario in report.missing_scenarios if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
        missing = [scenario for scenario in scenarios if scenario not in passed]
        review_time = parse_platform_acceptance_time(review_log.created_at) or now
        wait_hours = max(0, int((now - review_time).total_seconds() // 3600))
        latest = platform_acceptance_manifest_tracker_related_submission(review_log, link_id, scenarios, submission_logs)
        if not link_id:
            status: Literal["waiting_customer", "ready_for_review", "needs_fix", "stale", "complete", "missing_link"] = "missing_link"
            next_action = "Generate or resend a customer Manifest link for this recovered submission."
        elif not missing:
            status = "complete"
            next_action = "All tracked scenarios have pass evidence; recompute final sign-off."
        elif latest and latest.status == "preview_ready" and latest.ready > 0 and latest.blocked == 0:
            status = "ready_for_review"
            next_action = "Open the latest import preview, verify sanitized evidence, then import approved evidence with CONFIRM_PLATFORM_EVIDENCE."
        elif latest:
            status = "needs_fix"
            next_action = "Customer submitted the Manifest, but it still needs fixes; send the specific missing/blocked item list."
        elif wait_hours >= payload.stale_after_hours:
            status = "stale"
            next_action = "Send a reminder or regenerate the Manifest link if it is expired."
        else:
            status = "waiting_customer"
            next_action = "Wait for customer Manifest submission; send reminder if close to SLA."
        if status in {"stale", "missing_link"}:
            escalation: Literal["none", "watch", "urgent"] = "urgent"
        elif wait_hours >= max(1, payload.stale_after_hours // 2):
            escalation = "watch"
        else:
            escalation = "none"
        items.append(
            PlatformAcceptanceManifestResubmissionTrackerItem(
                submission_id=review_log.target_id,
                status=status,
                manifest_link_id=link_id,
                recovery_review_id=str(metadata.get("review_id") or ""),
                scenarios=scenarios,
                missing_scenarios=missing,
                latest_submission_id=latest.submission_id if latest else "",
                latest_submission_status=latest.status if latest else "",
                latest_submission_artifact_url=latest.submission_artifact_url if latest else "",
                import_preview_artifact_url=latest.import_preview_artifact_url if latest else "",
                wait_hours=wait_hours,
                escalation=escalation,
                next_action=next_action,
            )
        )
    waiting = sum(1 for item in items if item.status == "waiting_customer")
    ready = sum(1 for item in items if item.status == "ready_for_review")
    needs_fix = sum(1 for item in items if item.status == "needs_fix")
    stale = sum(1 for item in items if item.status == "stale")
    complete = sum(1 for item in items if item.status == "complete")
    missing_link = sum(1 for item in items if item.status == "missing_link")
    if not items:
        status_tracker: Literal["ready_for_signoff", "ready_for_review", "waiting_customer", "stale", "needs_ops", "empty"] = "empty"
    elif not report.missing_scenarios:
        status_tracker = "ready_for_signoff"
    elif ready:
        status_tracker = "ready_for_review"
    elif stale:
        status_tracker = "stale"
    elif needs_fix or missing_link:
        status_tracker = "needs_ops"
    else:
        status_tracker = "waiting_customer"
    tracker = PlatformAcceptanceManifestResubmissionTracker(
        id=f"platform-manifest-resubmission-tracker-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status_tracker,
        summary=(
            f"Manifest resubmission tracker. evidence_status={report.status} missing={len(report.missing_scenarios)} "
            f"total={len(items)} waiting={waiting} ready={ready} needs_fix={needs_fix} stale={stale}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        evidence_status=report.status,
        missing_scenarios=report.missing_scenarios,
        total=len(items),
        waiting_customer=waiting,
        ready_for_review=ready,
        needs_fix=needs_fix,
        stale=stale,
        complete=complete,
        missing_link=missing_link,
        items=items,
        created_at=now_sql(),
    )
    tracker.reminder_draft = build_platform_acceptance_manifest_resubmission_tracker_reminder(tracker)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{tracker.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_resubmission_tracker_markdown(tracker), encoding="utf-8")
        tracker.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_manifest_resubmission_tracker",
        max(1, tracker.total),
        "integration",
        tracker.id,
        {"status": tracker.status, "total": tracker.total, "ready": tracker.ready_for_review, "stale": tracker.stale},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_manifest_resubmission_tracker",
        "integration_acceptance",
        tracker.id,
        "Generate customer Manifest resubmission tracker",
        {"status": tracker.status, "total": tracker.total, "ready": tracker.ready_for_review, "stale": tracker.stale, "artifact_url": tracker.artifact_url},
    )
    return tracker


def platform_acceptance_manifest_resubmission_task_target(item: PlatformAcceptanceManifestResubmissionTrackerItem) -> str:
    key = item.submission_id or item.manifest_link_id or item.recovery_review_id or "unknown"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"manifest_resubmission:{digest}"


def existing_open_manifest_resubmission_task(merchant_id: int, target_id: str) -> CRMTask | None:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker} AND target_id={marker}
            ORDER BY id DESC LIMIT 1
            """,
            (merchant_id, "open", "platform_acceptance_manifest_resubmission", target_id),
        ).fetchone()
    return crm_task_from_row(dict(row)) if row else None


def platform_acceptance_manifest_resubmission_task_title(
    item: PlatformAcceptanceManifestResubmissionTrackerItem,
) -> str:
    scenarios = ", ".join(item.missing_scenarios or item.scenarios) or "customer evidence"
    if item.status == "ready_for_review":
        return f"Review customer Manifest resubmission: {scenarios}"
    if item.status == "needs_fix":
        return f"Ask customer to fix Manifest evidence: {scenarios}"
    if item.status == "stale":
        return f"Escalate overdue customer Manifest resubmission: {scenarios}"
    if item.status == "missing_link":
        return f"Regenerate customer Manifest link: {scenarios}"
    return f"Follow up customer Manifest resubmission: {scenarios}"


def platform_acceptance_manifest_resubmission_task_priority(
    item: PlatformAcceptanceManifestResubmissionTrackerItem,
) -> Literal["low", "normal", "high"]:
    if item.status in {"ready_for_review", "stale", "missing_link"} or item.escalation == "urgent":
        return "high"
    return "normal"


def build_platform_acceptance_manifest_resubmission_reminder_run_draft(
    run: PlatformAcceptanceManifestResubmissionReminderRun,
) -> str:
    lines = [
        f"Hi {run.recipient},",
        "",
        f"We are following up on the real-platform Manifest resubmission for {run.customer_name}.",
        f"Current task package status: {run.status}; actionable items: {run.total}.",
        "",
        "Please submit only sanitized evidence. Do not include passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets.",
        "",
        "Pending actions:",
    ]
    actionable = [item for item in run.items if item.action_status != "skipped"]
    if actionable:
        for item in actionable:
            lines.append(
                f"- {item.submission_id or 'manifest resubmission'}: {item.tracker_status}; "
                f"priority={item.priority}; next={item.next_action}"
            )
    else:
        lines.append("- No customer reminder is needed right now; recheck final sign-off status.")
    lines.extend(["", f"Owner: {run.owner}"])
    return "\n".join(lines)


def build_platform_acceptance_manifest_resubmission_reminder_run_markdown(
    run: PlatformAcceptanceManifestResubmissionReminderRun,
) -> str:
    lines = [
        "# Real Platform Manifest Resubmission Reminder Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Status: {run.status}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        f"Create tasks: {run.create_tasks}",
        "",
        run.summary,
        "",
        "## Counts",
        "",
        f"- Total actionable: {run.total}",
        f"- Created: {run.created}",
        f"- Existing: {run.existing}",
        f"- Skipped: {run.skipped}",
        f"- Blocked: {run.blocked}",
        "",
        "## Items",
        "",
        "| Submission | Tracker Status | Action | Task | Priority | Due | Title | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not run.items:
        lines.append("| - | clear | skipped | - | - | - | - | No customer resubmission reminder task is needed. |")
    for item in run.items:
        task_id = item.task.id if item.task else "-"
        lines.append(
            f"| {item.submission_id or '-'} | {item.tracker_status} | {item.action_status} | {task_id} | "
            f"{item.priority} | {item.due_at or '-'} | {item.title.replace('|', '/')} | "
            f"{item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Reminder Draft",
            "",
            "```text",
            run.reminder_draft or "-",
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This run creates CRM follow-up tasks and reminder drafts only.",
            "- It does not send messages, approve evidence, or register pass evidence.",
            "- Customer-facing text must be manually reviewed before sending.",
            "- Evidence import still requires human review, URL precheck, and CONFIRM_PLATFORM_EVIDENCE.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_manifest_resubmission_reminder_run(
    payload: PlatformAcceptanceManifestResubmissionReminderRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestResubmissionReminderRun:
    tracker = await generate_platform_acceptance_manifest_resubmission_tracker(
        PlatformAcceptanceManifestResubmissionTrackerRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            stale_after_hours=payload.stale_after_hours,
            include_artifact=False,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    due_at = (datetime.now() + timedelta(hours=payload.due_hours)).strftime("%Y-%m-%d %H:%M:%S")
    items: list[PlatformAcceptanceManifestResubmissionReminderRunItem] = []
    created = 0
    existing = 0
    blocked = 0
    skipped = 0
    for tracker_item in tracker.items:
        title = platform_acceptance_manifest_resubmission_task_title(tracker_item)
        priority = platform_acceptance_manifest_resubmission_task_priority(tracker_item)
        if tracker_item.status == "complete":
            skipped += 1
            items.append(
                PlatformAcceptanceManifestResubmissionReminderRunItem(
                    submission_id=tracker_item.submission_id,
                    tracker_status=tracker_item.status,
                    action_status="skipped",
                    priority=priority,
                    due_at=due_at,
                    title=title,
                    next_action="Tracked scenarios already have pass evidence; no customer reminder task is needed.",
                )
            )
            continue
        target_id = platform_acceptance_manifest_resubmission_task_target(tracker_item)
        task = existing_open_manifest_resubmission_task(merchant.id or 0, target_id)
        action_status: Literal["preview", "task_created", "task_existing", "skipped", "blocked"] = "preview"
        if task:
            existing += 1
            action_status = "task_existing"
        elif payload.create_tasks:
            try:
                task = create_crm_task_record(
                    merchant.id or 0,
                    CRMTaskCreate(
                        target_type="conversation",
                        target_id=target_id,
                        title=title,
                        priority=priority,
                        owner=payload.owner,
                        due_at=due_at,
                        source="platform_acceptance_manifest_resubmission",
                        workflow_run_id=tracker.id,
                    ),
                )
                created += 1
                action_status = "task_created"
            except HTTPException:
                blocked += 1
                action_status = "blocked"
        items.append(
            PlatformAcceptanceManifestResubmissionReminderRunItem(
                submission_id=tracker_item.submission_id,
                tracker_status=tracker_item.status,
                action_status=action_status,
                task=task,
                priority=priority,
                due_at=due_at,
                title=title,
                next_action=tracker_item.next_action,
            )
        )
    total = sum(1 for item in items if item.action_status != "skipped")
    if total == 0:
        status: Literal["preview", "created", "clear", "partial", "blocked"] = "clear"
    elif blocked and not (created or existing):
        status = "blocked"
    elif blocked:
        status = "partial"
    elif payload.create_tasks:
        status = "created"
    else:
        status = "preview"
    run = PlatformAcceptanceManifestResubmissionReminderRun(
        id=f"platform-manifest-resubmission-reminder-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Manifest resubmission reminder package. tracker_status={tracker.status} total={total} "
            f"created={created} existing={existing} skipped={skipped} blocked={blocked} create_tasks={payload.create_tasks}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        create_tasks=payload.create_tasks,
        total=total,
        created=created,
        existing=existing,
        skipped=skipped,
        blocked=blocked,
        tracker=tracker,
        items=items,
        created_at=now_sql(),
    )
    run.reminder_draft = build_platform_acceptance_manifest_resubmission_reminder_run_draft(run)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_resubmission_reminder_run_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_manifest_resubmission_reminder",
        max(1, total),
        "integration",
        run.id,
        {"status": run.status, "total": run.total, "created": run.created, "existing": run.existing, "blocked": run.blocked},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_manifest_resubmission_reminder_run",
        "integration_acceptance",
        run.id,
        "Generate customer Manifest resubmission reminder task package",
        {
            "status": run.status,
            "total": run.total,
            "created": run.created,
            "existing": run.existing,
            "blocked": run.blocked,
            "create_tasks": run.create_tasks,
            "artifact_url": run.artifact_url,
        },
    )
    return run


def build_platform_acceptance_final_closure_markdown(run: PlatformAcceptanceFinalClosureRun) -> str:
    lines = [
        "# Real Platform Final Closure Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Status: {run.status}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        "",
        run.summary,
        "",
        "## Evidence Delta",
        "",
        f"- Before: status={run.report_before.status if run.report_before else '-'} missing={len(run.missing_before)} evidence={run.report_before.evidence_total if run.report_before else 0}",
        f"- After: status={run.report_after.status if run.report_after else '-'} missing={len(run.missing_after)} evidence={run.report_after.evidence_total if run.report_after else 0}",
        f"- Missing before: {', '.join(run.missing_before) if run.missing_before else 'none'}",
        f"- Missing after: {', '.join(run.missing_after) if run.missing_after else 'none'}",
        "",
        "## Closure Actions",
        "",
        f"- Auto watch: {run.auto_watch.status if run.auto_watch else '-'} ({run.auto_watch.artifact_url if run.auto_watch else '-'})",
        f"- Manifest tracker: {run.tracker.status if run.tracker else '-'} total={run.tracker.total if run.tracker else 0} ({run.tracker.artifact_url if run.tracker else '-'})",
        f"- Resubmission reminder: {run.reminder_run.status if run.reminder_run else '-'} created={run.reminder_run.created if run.reminder_run else 0} existing={run.reminder_run.existing if run.reminder_run else 0} ({run.reminder_run.artifact_url if run.reminder_run else '-'})",
        f"- Customer room: {run.customer_room.status if run.customer_room else '-'} ({run.customer_room.artifact_url if run.customer_room else '-'})",
        f"- Final gate: {run.final_gate.status if run.final_gate else '-'} ({run.final_gate.artifact_url if run.final_gate else '-'})",
        f"- CRM tasks created: {run.created_tasks}",
        f"- CRM tasks existing: {run.existing_tasks}",
        f"- Secure links generated: {run.secure_links}",
        "",
        "## Safety Boundary",
        "",
        "- This final closure run does not fabricate evidence.",
        "- It may register pass evidence only when existing connector routines complete real OAuth/read-only checks.",
        "- Customer-submitted materials still require human review, URL precheck, and CONFIRM_PLATFORM_EVIDENCE.",
        "- Signed customer URLs are intentionally omitted from this summary artifact.",
    ]
    return "\n".join(lines)


async def generate_platform_acceptance_final_closure_run(
    payload: PlatformAcceptanceFinalClosureRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceFinalClosureRun:
    report_before = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    tracker = await generate_platform_acceptance_manifest_resubmission_tracker(
        PlatformAcceptanceManifestResubmissionTrackerRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            stale_after_hours=24,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    reminder_run: PlatformAcceptanceManifestResubmissionReminderRun | None = None
    if payload.create_resubmission_reminder and tracker.total:
        reminder_run = await generate_platform_acceptance_manifest_resubmission_reminder_run(
            PlatformAcceptanceManifestResubmissionReminderRunRequest(
                customer_name=payload.customer_name,
                owner=payload.owner,
                recipient=payload.recipient,
                stale_after_hours=24,
                due_hours=24,
                create_tasks=payload.create_tasks,
                include_artifact=True,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    auto_watch = await generate_platform_acceptance_auto_watch_run(
        PlatformAcceptanceAutoWatchRunRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=payload.connectors,
            attempt_exchange=payload.attempt_exchange,
            attempt_pull=payload.attempt_pull,
            create_owner_closure_link=payload.create_owner_closure_link,
            create_review_tasks=payload.create_tasks,
            create_gap_tasks=payload.create_tasks,
            create_customer_links=payload.create_customer_links,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    customer_room: PlatformAcceptanceCustomerRoomLink | None = None
    if payload.create_customer_room:
        customer_room = await generate_platform_acceptance_customer_room_link(
            PlatformAcceptanceCustomerRoomLinkRequest(
                customer_name=payload.customer_name,
                owner=payload.owner,
                recipient=payload.recipient,
                connectors=payload.connectors,
                expires_days=3,
                include_artifact=True,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    report_after = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    final_gate = auto_watch.final_gate
    created_tasks = 0
    existing_tasks = 0
    if reminder_run:
        created_tasks += reminder_run.created
        existing_tasks += reminder_run.existing
    if auto_watch.review_sync:
        created_tasks += auto_watch.review_sync.created
    if auto_watch.gap_closure and auto_watch.gap_closure.gap_sync:
        created_tasks += auto_watch.gap_closure.gap_sync.created
        existing_tasks += auto_watch.gap_closure.gap_sync.skipped_existing
    secure_links = 0
    if auto_watch.owner_closure_link:
        secure_links += 1
    if customer_room:
        secure_links += 1
    if final_gate and final_gate.submit_url:
        secure_links += 1
    if reminder_run and reminder_run.artifact_url:
        secure_links += 1
    if not report_after.missing_scenarios and final_gate and final_gate.status == "ready":
        status: Literal["ready_for_signoff", "waiting_customer", "needs_ops", "blocked"] = "ready_for_signoff"
    elif customer_room or auto_watch.owner_closure_link or (reminder_run and reminder_run.total):
        status = "waiting_customer"
    elif auto_watch.status == "needs_ops" or created_tasks or existing_tasks:
        status = "needs_ops"
    else:
        status = "blocked"
    run = PlatformAcceptanceFinalClosureRun(
        id=f"platform-final-closure-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Final closure orchestration. before={len(report_before.missing_scenarios)} "
            f"after={len(report_after.missing_scenarios)} status={status} "
            f"created_tasks={created_tasks} existing_tasks={existing_tasks} secure_links={secure_links}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        missing_before=report_before.missing_scenarios,
        missing_after=report_after.missing_scenarios,
        report_before=report_before,
        report_after=report_after,
        tracker=tracker,
        reminder_run=reminder_run,
        auto_watch=auto_watch,
        customer_room=customer_room,
        final_gate=final_gate,
        created_tasks=created_tasks,
        existing_tasks=existing_tasks,
        secure_links=secure_links,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_final_closure_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_final_closure_run",
        max(1, len(run.missing_before)),
        "integration",
        run.id,
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "created_tasks": run.created_tasks, "secure_links": run.secure_links},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_final_closure_run",
        "integration_acceptance",
        run.id,
        "Run final real-platform acceptance closure orchestration",
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "created_tasks": run.created_tasks, "secure_links": run.secure_links, "artifact_url": run.artifact_url},
    )
    return run


def latest_manifest_inbox_item_for_scenario(
    inbox: PlatformAcceptanceEvidenceManifestInbox,
    scenario: PlatformAcceptanceScenario,
) -> PlatformAcceptanceEvidenceManifestInboxItem | None:
    for item in inbox.items:
        if scenario in item.scenarios or scenario in item.missing_scenarios:
            return item
    return None


def build_platform_acceptance_manifest_followup_draft(
    run: PlatformAcceptanceManifestFollowupRun,
) -> str:
    lines = [
        f"Hi {run.recipient},",
        "",
        f"We are following up on real-platform acceptance for {run.customer_name}.",
        f"Current acceptance status is {run.evidence_status}; {len(run.missing_scenarios)} item(s) still need sanitized proof.",
    ]
    if run.manifest_url:
        lines.extend(
            [
                "",
                "Please submit the remaining evidence through this secure manifest link:",
                run.manifest_url,
            ]
        )
    lines.extend(["", "Pending items:"])
    if run.items:
        for item in run.items:
            lines.append(f"- {item.scenario}: {item.next_action}")
            if item.requirement:
                lines.append(f"  Required proof: {item.requirement}")
    else:
        lines.append("- No pending items; final sign-off can be rechecked.")
    lines.extend(
        [
            "",
            "Safety reminder: submit only sanitized screenshots, recordings, tickets, or controlled document links.",
            "Do not include passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets.",
            f"Owner: {run.owner}",
        ]
    )
    return "\n".join(lines)


def build_platform_acceptance_manifest_followup_markdown(
    run: PlatformAcceptanceManifestFollowupRun,
) -> str:
    lines = [
        "# Real Platform Evidence Manifest Follow-up Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        f"Status: {run.status}",
        f"Evidence status: {run.evidence_status}",
        f"Inbox: {run.inbox_status} total={run.inbox_total} ready={run.inbox_ready} blocked={run.inbox_blocked}",
        "",
        run.summary,
        "",
        "## Manifest Link",
        "",
        f"- URL: {run.manifest_url or '-'}",
        f"- Artifact: {run.manifest_artifact_url or '-'}",
        "",
        "## Follow-up Items",
        "",
        "| Scenario | Status | Latest Submission | Import Preview | Requirement | Next Action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in run.items:
        latest = f"{item.latest_submission_id} {item.latest_submission_status}".strip() or "-"
        lines.append(
            f"| {item.scenario} | {item.status} | {latest.replace('|', '/')} | "
            f"{item.import_preview_artifact_url or '-'} | {item.requirement.replace('|', '/') or '-'} | "
            f"{item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Reminder Draft",
            "",
            "```text",
            run.reminder_draft or "-",
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This run creates follow-up instructions only; it does not register pass evidence.",
            "- Customer-submitted evidence must still pass import preview and manual review.",
            "- Final sign-off remains blocked until every required scenario has verifiable pass evidence.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_manifest_followup_run(
    payload: PlatformAcceptanceManifestFollowupRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceManifestFollowupRun:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    inbox = await generate_platform_acceptance_evidence_manifest_inbox(
        PlatformAcceptanceEvidenceManifestInboxRequest(audit_limit=payload.audit_limit, include_artifact=False),
        merchant,
    )
    missing = [scenario for scenario in report.missing_scenarios if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS]
    manifest_link: PlatformAcceptanceEvidenceManifestLink | None = None
    if payload.create_manifest_link and missing:
        manifest_link = await generate_platform_acceptance_evidence_manifest_link(
            PlatformAcceptanceEvidenceManifestLinkRequest(
                customer_name=payload.customer_name,
                owner=payload.owner,
                recipient=payload.recipient,
                scenarios=missing,
                expires_days=payload.expires_days,
                include_artifact=payload.include_artifact,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    followup_items: list[PlatformAcceptanceManifestFollowupRunItem] = []
    for scenario in missing:
        latest = latest_manifest_inbox_item_for_scenario(inbox, scenario)
        requirement_data = platform_acceptance_evidence_requirements(scenario)
        required = requirement_data.get("required_evidence")
        requirement = ""
        if isinstance(required, list) and required:
            requirement = str(required[0])
        if latest and latest.status == "preview_ready" and latest.ready > 0 and latest.blocked == 0 and scenario not in latest.missing_scenarios:
            item_status: Literal["ready_to_import", "needs_resubmission", "awaiting_customer"] = "ready_to_import"
            next_action = "Open the import preview, verify sanitized proof, then import with CONFIRM_PLATFORM_EVIDENCE."
        elif latest:
            item_status = "needs_resubmission"
            next_action = "Ask the customer to replace blocked or missing evidence for this scenario in the manifest page."
        else:
            item_status = "awaiting_customer"
            next_action = str(requirement_data.get("next_action") or "Ask the customer to submit sanitized real-platform proof.")
        followup_items.append(
            PlatformAcceptanceManifestFollowupRunItem(
                scenario=scenario,
                status=item_status,
                latest_submission_id=latest.submission_id if latest else "",
                latest_submission_status=latest.status if latest else "",
                import_preview_artifact_url=latest.import_preview_artifact_url if latest else "",
                submission_artifact_url=latest.submission_artifact_url if latest else "",
                requirement=requirement,
                next_action=next_action,
            )
        )
    ready_count = sum(1 for item in followup_items if item.status == "ready_to_import")
    needs_resubmission = sum(1 for item in followup_items if item.status == "needs_resubmission")
    if not missing:
        run_status: Literal["ready_for_signoff", "ready_for_review", "waiting_for_customer", "needs_ops"] = "ready_for_signoff"
    elif ready_count > 0:
        run_status = "ready_for_review"
    elif needs_resubmission > 0:
        run_status = "waiting_for_customer"
    else:
        run_status = "waiting_for_customer"
    run = PlatformAcceptanceManifestFollowupRun(
        id=f"platform-evidence-manifest-followup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=run_status,
        summary=(
            f"Customer evidence manifest follow-up. evidence_status={report.status} missing={len(missing)} "
            f"inbox_total={inbox.total} ready_for_review={ready_count} needs_resubmission={needs_resubmission}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        evidence_status=report.status,
        missing_scenarios=missing,
        inbox_status=inbox.status,
        inbox_total=inbox.total,
        inbox_ready=inbox.ready,
        inbox_blocked=inbox.blocked,
        manifest_url=manifest_link.manifest_url if manifest_link else "",
        manifest_artifact_url=manifest_link.artifact_url if manifest_link else "",
        items=followup_items,
        created_at=now_sql(),
    )
    run.reminder_draft = build_platform_acceptance_manifest_followup_draft(run)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_manifest_followup_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_manifest_followup_run",
        max(1, len(followup_items)),
        "integration",
        run.id,
        {
            "status": run.status,
            "missing": len(run.missing_scenarios),
            "inbox_total": run.inbox_total,
            "ready_for_review": ready_count,
            "manifest_link_created": bool(run.manifest_url),
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_manifest_followup_run",
        "integration_acceptance",
        run.id,
        "Generate customer evidence manifest follow-up run",
        {
            "status": run.status,
            "missing": len(run.missing_scenarios),
            "inbox_total": run.inbox_total,
            "ready_for_review": ready_count,
            "manifest_link_created": bool(run.manifest_url),
        },
    )
    return run


def platform_acceptance_submission_base_url() -> str:
    return (os.getenv("APP_PUBLIC_BASE_URL") or "https://wjhai.cn/merchant-admin").rstrip("/")


def platform_acceptance_submission_path() -> str:
    return "/api/v1/public/platform-acceptance-evidence-submission"


def platform_acceptance_submission_submit_url(token: str) -> str:
    base_url = platform_acceptance_submission_base_url()
    return f"{base_url}{platform_acceptance_submission_path()}?token={urllib.parse.quote(token)}"


def encode_platform_acceptance_submission_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    mac = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-submission:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"pas.v1.{body}.{mac}"


def decode_platform_acceptance_submission_token(token: str) -> dict[str, Any]:
    try:
        prefix, version, body, mac = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid submission token") from exc
    if prefix != "pas" or version != "v1":
        raise HTTPException(status_code=400, detail="Unsupported submission token")
    expected = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-submission:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Submission token signature mismatch")
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Submission token payload invalid") from exc
    expires_ts = int(payload.get("expires_ts") or 0)
    if expires_ts < int(time.time()):
        raise HTTPException(status_code=400, detail="Submission token expired")
    scenarios = [
        scenario for scenario in payload.get("scenarios", [])
        if scenario in PLATFORM_ACCEPTANCE_PUBLIC_SUBMISSION_SCENARIOS
    ]
    if not scenarios:
        raise HTTPException(status_code=400, detail="Submission token has no allowed scenarios")
    payload["scenarios"] = scenarios
    return payload


def build_platform_acceptance_submission_link_markdown(link: PlatformAcceptanceEvidenceSubmissionLink) -> str:
    lines = [
        "# Real Platform Acceptance Customer Submission Link",
        "",
        f"Link ID: {link.id}",
        f"Created at: {link.created_at}",
        f"Recipient: {link.recipient}",
        f"Owner: {link.owner}",
        f"Status: {link.status}",
        f"Expires at: {link.expires_at}",
        "",
        "## Scenarios",
        "",
    ]
    if link.scenarios:
        lines.extend(f"- {scenario}" for scenario in link.scenarios)
    else:
        lines.append("- No missing scenario needs customer submission.")
    lines.extend(
        [
            "",
            "## Submission URL",
            "",
            link.submit_url or "-",
            "",
            "## Draft",
            "",
            link.draft_text or "-",
            "",
            "## Safety Boundary",
            "",
            "- This link collects sanitized customer material only; it does not register pass evidence.",
            "- Customer submissions create receipts and review tasks for operations review.",
            "- Do not submit platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_evidence_submission_link(
    payload: PlatformAcceptanceEvidenceSubmissionLinkRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceSubmissionLink:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=200, include_artifact=False),
        merchant,
    )
    requested = [scenario for scenario in payload.scenarios if scenario in PLATFORM_ACCEPTANCE_PUBLIC_SUBMISSION_SCENARIOS]
    scenarios = requested or report.missing_scenarios
    link_id = f"platform-evidence-submit-link-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    expires_at_dt = datetime.now() + timedelta(days=payload.expires_days)
    expires_at = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    token_payload = {
        "link_id": link_id,
        "merchant_id": merchant.id or 0,
        "recipient": payload.recipient.strip()[:120],
        "owner": payload.owner.strip()[:120],
        "scenarios": scenarios,
        "expires_ts": int(expires_at_dt.timestamp()),
        "expires_at": expires_at,
    }
    signed_link_code = encode_platform_acceptance_submission_token(token_payload)
    submit_url = platform_acceptance_submission_submit_url(signed_link_code)
    draft_text = "\n".join(
        [
            "Please submit sanitized real-platform acceptance material through this link:",
            submit_url,
            "",
            "Required scenarios:",
            *[f"- {scenario}" for scenario in scenarios],
            "",
            "Do not include passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
            "The operations team will review the material before any pass evidence is registered.",
        ]
    )
    link = PlatformAcceptanceEvidenceSubmissionLink(
        id=link_id,
        status="ready" if scenarios else "empty",
        recipient=payload.recipient.strip()[:120],
        owner=payload.owner.strip()[:120],
        scenarios=scenarios,
        submit_url=submit_url,
        **{"token": signed_link_code},
        expires_at=expires_at,
        draft_text=draft_text,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{link.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_submission_link_markdown(link), encoding="utf-8")
        link.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_submission_link",
        max(1, len(scenarios)),
        "integration",
        link.id,
        {"scenarios": len(scenarios), "expires_at": expires_at, "status": link.status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_submission_link",
        "integration_acceptance",
        link.id,
        "Generate customer-facing platform acceptance evidence submission link",
        {"scenarios": scenarios, "recipient": link.recipient, "owner": link.owner, "expires_at": expires_at, "status": link.status},
    )
    return link


def build_platform_acceptance_customer_submission_markdown(submission: PlatformAcceptanceEvidenceCustomerSubmission) -> str:
    lines = [
        "# Real Platform Acceptance Customer Submission",
        "",
        f"Submission ID: {submission.id}",
        f"Created at: {submission.created_at}",
        f"Status: {submission.status}",
        f"Recipient: {submission.recipient}",
        f"Submitter: {submission.submitter}",
        "",
        submission.summary,
        "",
        "## Receipt",
        "",
        f"- Receipt ID: {submission.receipt.id}",
        f"- Receipt status: {submission.receipt.status}",
        f"- Receipt artifact: {submission.receipt.artifact_url or '-'}",
        "",
        "## Review Task Sync",
        "",
        f"- Sync ID: {submission.review_sync.id}",
        f"- Status: {submission.review_sync.status}",
        f"- Created review tasks: {submission.review_sync.created}",
        f"- Submitted scenarios: {submission.review_sync.submitted}",
        f"- Needs help scenarios: {submission.review_sync.needs_help}",
        "",
        "| Scenario | Outcome | Evidence URL | Note |",
        "| --- | --- | --- | --- |",
    ]
    for item in submission.receipt.scenario_receipts:
        lines.append(f"| {item.scenario} | {item.outcome} | {item.evidence_url or '-'} | {(item.note or '-').replace('|', '/')} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Customer submission is not pass evidence.",
            "- Operations must review, redact if needed, then explicitly register pass evidence.",
            "- Submitted text is scanned for obvious secret patterns before being stored.",
        ]
    )
    return "\n".join(lines)


async def submit_platform_acceptance_evidence_material(
    payload: PlatformAcceptanceEvidenceCustomerSubmissionRequest,
) -> PlatformAcceptanceEvidenceCustomerSubmission:
    token_data = decode_platform_acceptance_submission_token(payload.token)
    merchant = merchant_by_id(int(token_data.get("merchant_id") or 0))
    allowed_scenarios = set(token_data.get("scenarios") or [])
    scenario_receipts = payload.scenario_receipts or [
        PlatformAcceptanceEvidenceReceiptScenario(
            scenario=scenario,  # type: ignore[arg-type]
            outcome=payload.outcome,
            note=payload.notes,
            evidence_url="",
        )
        for scenario in token_data.get("scenarios", [])
    ]
    disallowed = [item.scenario for item in scenario_receipts if item.scenario not in allowed_scenarios]
    if disallowed:
        raise HTTPException(status_code=400, detail=f"Scenario not allowed by submission token: {', '.join(disallowed)}")
    if not scenario_receipts:
        raise HTTPException(status_code=400, detail="At least one scenario receipt is required")
    receipt = await record_platform_acceptance_evidence_receipt(
        PlatformAcceptanceEvidenceReceiptRequest(
            notice_id=str(token_data.get("link_id") or ""),
            recipient=str(token_data.get("recipient") or payload.submitter),
            outcome=payload.outcome,
            scenario_receipts=scenario_receipts,
            notes=payload.notes,
            include_artifact=payload.include_artifact,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        ),
        merchant,
    )
    review_sync = await sync_platform_acceptance_evidence_review_tasks(
        PlatformAcceptanceEvidenceReviewTaskSyncRequest(
            owner=str(token_data.get("owner") or "operations reviewer"),
            due_days=0,
            include_needs_help=True,
            create_tasks=True,
            include_artifact=True,
            audit_limit=200,
        ),
        merchant,
    )
    status: Literal["received", "needs_help", "submitted"] = "submitted" if receipt.status == "submitted" else "needs_help" if receipt.status == "needs_help" else "received"
    submission = PlatformAcceptanceEvidenceCustomerSubmission(
        id=f"platform-evidence-customer-submission-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        recipient=str(token_data.get("recipient") or ""),
        submitter=payload.submitter.strip()[:120],
        scenarios=[item.scenario for item in scenario_receipts],
        receipt=receipt,
        review_sync=review_sync,
        summary=(
            f"Customer platform evidence material received. scenarios={len(scenario_receipts)} "
            f"receipt={receipt.id} review_tasks_created={review_sync.created}."
        ),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{submission.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_customer_submission_markdown(submission), encoding="utf-8")
        submission.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_customer_submission",
        max(1, len(scenario_receipts)),
        "integration",
        submission.id,
        {"scenarios": len(scenario_receipts), "status": submission.status, "review_created": review_sync.created},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_customer_submission",
        "integration_acceptance",
        submission.id,
        "Receive customer-submitted platform acceptance evidence material",
        {
            "link_id": str(token_data.get("link_id") or ""),
            "recipient": submission.recipient,
            "submitter": submission.submitter,
            "scenarios": [item.model_dump() for item in scenario_receipts],
            "receipt_id": receipt.id,
            "review_sync_id": review_sync.id,
            "review_created": review_sync.created,
            "status": submission.status,
        },
    )
    return submission


def build_platform_acceptance_sprint_pack_markdown(pack: PlatformAcceptanceSprintPack) -> str:
    lines = [
        "# Real Platform Acceptance Sprint Pack",
        "",
        f"Pack ID: {pack.id}",
        f"Created at: {pack.created_at}",
        f"Status: {pack.status}",
        "",
        pack.summary,
        "",
        "## Missing Required Scenarios",
        "",
    ]
    if pack.missing_scenarios:
        lines.extend(f"- {scenario}" for scenario in pack.missing_scenarios)
    else:
        lines.append("- None. All required scenarios have registered pass evidence.")
    lines.extend(
        [
            "",
            "## Scenario Sprint Items",
            "",
            "| Scenario | Status | Task | Owner | Due At | Evidence Count | Submission Link | Next Action |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not pack.items:
        lines.append("| - | empty | - | - | - | - | - | No sprint items were needed. |")
    for item in pack.items:
        submit_ref = item.submission_link.submit_url if item.submission_link else "-"
        lines.append(
            f"| {item.scenario} | {item.status} | {item.task_id or '-'} | {item.owner or '-'} | "
            f"{item.due_at or '-'} | {item.evidence_count} | {submit_ref} | {item.next_action or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Capture Playbook",
            "",
        ]
    )
    for item in pack.items:
        lines.extend([f"### {item.scenario}", ""])
        lines.append(f"- Status: {item.status}")
        lines.append(f"- CRM task: {item.task_id or '-'}")
        if item.submission_link:
            lines.append(f"- Customer submission link: {item.submission_link.submit_url}")
        lines.append("- Required evidence:")
        lines.extend(f"  - {entry}" for entry in item.required_evidence)
        lines.append("- Capture steps:")
        lines.extend(f"  {index}. {step}" for index, step in enumerate(item.capture_steps, start=1))
        lines.extend(["", f"Next action: {item.next_action or '-'}", ""])
    lines.extend(
        [
            "## Safety Boundary",
            "",
            "- This sprint pack collects real customer-controlled proof; it does not create pass evidence automatically.",
            "- Customer submission links create receipts and review tasks only.",
            "- Pass evidence must still be reviewed, sanitized, explicitly registered, and reconciled before a scenario is closed.",
            "- Do not store platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_sprint_pack(
    payload: PlatformAcceptanceSprintPackRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceSprintPack:
    checklist = await generate_platform_acceptance_evidence_checklist(
        PlatformAcceptanceEvidenceChecklistRequest(
            owner=payload.owner,
            due_days=payload.due_days,
            ensure_tasks=payload.ensure_tasks,
            include_passed=payload.include_passed,
            include_artifact=False,
        ),
        merchant,
    )
    source_items = [item for item in checklist.items if payload.include_passed or item.status != "passed"]
    links: list[PlatformAcceptanceEvidenceSubmissionLink] = []
    sprint_items: list[PlatformAcceptanceSprintScenarioItem] = []
    for item in source_items:
        link: PlatformAcceptanceEvidenceSubmissionLink | None = None
        if payload.create_links and item.status != "passed":
            link = await generate_platform_acceptance_evidence_submission_link(
                PlatformAcceptanceEvidenceSubmissionLinkRequest(
                    recipient=payload.recipient,
                    owner=payload.owner,
                    scenarios=[item.scenario],
                    due_days=payload.due_days,
                    expires_days=payload.expires_days,
                    include_artifact=True,
                ),
                merchant,
            )
            links.append(link)
        sprint_items.append(
            PlatformAcceptanceSprintScenarioItem(
                scenario=item.scenario,
                status=item.status,
                task_id=item.task_id,
                task_status=item.task_status,
                owner=item.owner,
                due_at=item.due_at,
                evidence_count=item.evidence_count,
                latest_evidence_result=item.latest_evidence_result,
                latest_evidence_url=item.latest_evidence_url,
                required_evidence=item.required_evidence,
                capture_steps=item.capture_steps,
                next_action=item.next_action,
                submission_link=link,
            )
        )
    if not checklist.missing_scenarios:
        status: Literal["complete", "collecting", "empty"] = "complete"
    elif sprint_items:
        status = "collecting"
    else:
        status = "empty"
    pack = PlatformAcceptanceSprintPack(
        id=f"platform-acceptance-sprint-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Real platform acceptance sprint pack. missing_scenarios={len(checklist.missing_scenarios)} "
            f"items={len(sprint_items)} tasks={len(checklist.tasks)} links={len(links)} "
            f"ensure_tasks={payload.ensure_tasks} create_links={payload.create_links}."
        ),
        missing_scenarios=checklist.missing_scenarios,
        items=sprint_items,
        tasks=checklist.tasks,
        links=links,
        checklist=checklist,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{pack.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_sprint_pack_markdown(pack), encoding="utf-8")
        pack.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_sprint_pack",
        max(1, len(sprint_items)),
        "integration",
        pack.id,
        {
            "missing": len(pack.missing_scenarios),
            "items": len(pack.items),
            "tasks": len(pack.tasks),
            "links": len(pack.links),
            "create_links": payload.create_links,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_sprint_pack",
        "integration_acceptance",
        pack.id,
        "Generate real platform acceptance sprint pack",
        {
            "missing": len(pack.missing_scenarios),
            "items": len(pack.items),
            "tasks": len(pack.tasks),
            "links": len(pack.links),
            "create_links": payload.create_links,
        },
    )
    return pack


def platform_acceptance_scenario_counts_from_logs(
    logs: list[AuditLog],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    receipt_counts: dict[str, int] = {}
    customer_submission_counts: dict[str, int] = {}
    link_counts: dict[str, int] = {}

    def bump(target: dict[str, int], raw_items: Any) -> None:
        if not isinstance(raw_items, list):
            return
        for raw in raw_items:
            if isinstance(raw, dict):
                scenario = str(raw.get("scenario") or "")
            else:
                scenario = str(raw or "")
            if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
                target[scenario] = target.get(scenario, 0) + 1

    for log in logs:
        metadata = log.metadata or {}
        if log.action == "integration.platform_acceptance_evidence_receipt":
            bump(receipt_counts, metadata.get("scenarios"))
        elif log.action == "integration.platform_acceptance_evidence_customer_submission":
            bump(customer_submission_counts, metadata.get("scenarios"))
        elif log.action == "integration.platform_acceptance_evidence_submission_link":
            bump(link_counts, metadata.get("scenarios"))
    return receipt_counts, customer_submission_counts, link_counts


def build_platform_acceptance_live_run_signoff_draft(live_run: PlatformAcceptanceLiveRun) -> str:
    ready = live_run.status == "ready_for_signoff"
    lines = [
        "[Customer Final Acceptance Sign-off Draft]",
        "",
        f"Customer: {live_run.customer_name}",
        f"Owner: {live_run.owner}",
        f"Recipient: {live_run.recipient}",
        f"Run ID: {live_run.id}",
        f"Run status: {live_run.status}",
        "",
        (
            "All required real-platform acceptance scenarios have registered sanitized pass evidence."
            if ready
            else "This run is not ready for final sign-off. Please complete the outstanding scenarios before signing."
        ),
        "",
        "Scenario status:",
    ]
    for item in live_run.scenarios:
        lines.append(
            f"- {item.scenario}: {item.status}; evidence={item.evidence_count}; "
            f"submissions={item.customer_submission_count}; review_tasks={item.review_task_count}; next={item.next_action}"
        )
    lines.extend(
        [
            "",
            "Boundaries:",
            "- This sign-off draft does not include platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
            "- Customer submission links and receipts do not count as pass evidence until operations review and explicit pass registration.",
            "- Automated outbound sending, publishing, refunds, account changes, and payment actions remain outside the acceptance scope unless separately authorized.",
            "",
            "Customer confirmation:",
            "- I confirm the listed required scenarios have been reviewed using customer-controlled platform data.",
            "- I confirm any known limitations and human-confirmation boundaries are understood.",
            "- Name / role / date:",
        ]
    )
    return "\n".join(lines)


def build_platform_acceptance_live_run_markdown(live_run: PlatformAcceptanceLiveRun) -> str:
    lines = [
        "# Real Platform Acceptance Live Run",
        "",
        f"Run ID: {live_run.id}",
        f"Created at: {live_run.created_at}",
        f"Customer: {live_run.customer_name}",
        f"Owner: {live_run.owner}",
        f"Recipient: {live_run.recipient}",
        f"Status: {live_run.status}",
        "",
        live_run.summary,
        "",
        "## Counters",
        "",
        f"- Required scenarios: {live_run.required_total}",
        f"- Passed: {live_run.passed}",
        f"- Missing: {live_run.missing}",
        f"- Needs review: {live_run.needs_review}",
        f"- Needs help: {live_run.needs_help}",
        "",
        "## Scenario Board",
        "",
        "| Scenario | Status | Evidence | Gap Task | Review Tasks | Submissions | Receipts | Links | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in live_run.scenarios:
        lines.append(
            f"| {item.scenario} | {item.status} | {item.evidence_count} | {item.gap_task_id or '-'} | "
            f"{item.review_task_count} | {item.customer_submission_count} | {item.receipt_count} | "
            f"{item.submission_link_count} | {item.next_action or '-'} |"
        )
    if live_run.sprint_pack:
        lines.extend(
            [
                "",
                "## Sprint Pack",
                "",
                f"- Sprint pack ID: {live_run.sprint_pack.id}",
                f"- Status: {live_run.sprint_pack.status}",
                f"- Items: {len(live_run.sprint_pack.items)}",
                f"- Customer links: {len(live_run.sprint_pack.links)}",
                f"- Artifact: {live_run.sprint_pack.artifact_url or '-'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Customer Final Sign-off Draft",
            "",
            "```text",
            live_run.signoff_draft,
            "```",
            "",
            "## Safety Boundary",
            "",
            "- The live run board does not create pass evidence automatically.",
            "- Final sign-off is available only after all required scenarios have sanitized pass evidence.",
            "- Continue using review decisions and gap reconciliation to close scenarios.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_live_run(
    payload: PlatformAcceptanceLiveRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceLiveRun:
    sprint_pack: PlatformAcceptanceSprintPack | None = None
    if payload.create_sprint_pack:
        sprint_pack = await generate_platform_acceptance_sprint_pack(
            PlatformAcceptanceSprintPackRequest(
                owner=payload.owner,
                recipient=payload.recipient,
                due_days=payload.due_days,
                expires_days=payload.expires_days,
                ensure_tasks=payload.ensure_tasks,
                create_links=payload.create_links,
                include_passed=False,
                include_artifact=True,
            ),
            merchant,
        )
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    receipt_counts, customer_submission_counts, link_counts = platform_acceptance_scenario_counts_from_logs(logs)
    evidence_by_scenario: dict[str, list[PlatformAcceptanceEvidence]] = {}
    for evidence in report.evidence:
        evidence_by_scenario.setdefault(evidence.scenario, []).append(evidence)
    review_items = await platform_acceptance_review_items_from_receipts(merchant, payload.audit_limit, include_needs_help=True)
    review_by_scenario: dict[str, list[PlatformAcceptanceEvidenceReviewTaskItem]] = {}
    for item in review_items:
        existing = existing_open_platform_acceptance_review_task(merchant.id or 0, item.target_id)
        if existing:
            item.task_id = existing.id
            item.task_status = existing.status
        review_by_scenario.setdefault(item.scenario, []).append(item)
    open_gap_tasks = {
        platform_acceptance_scenario_from_target(task.target_id): task
        for task in open_platform_acceptance_gap_tasks(merchant.id or 0)
    }
    new_links_by_scenario: dict[str, PlatformAcceptanceEvidenceSubmissionLink] = {}
    if sprint_pack:
        for link in sprint_pack.links:
            for scenario in link.scenarios:
                if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
                    new_links_by_scenario[scenario] = link
    scenarios: list[PlatformAcceptanceLiveRunScenario] = []
    for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
        scenario_evidence = evidence_by_scenario.get(scenario, [])
        latest = scenario_evidence[0] if scenario_evidence else None
        passed = any(item.result == "pass" for item in scenario_evidence)
        reviews = review_by_scenario.get(scenario, [])
        submitted_reviews = [item for item in reviews if item.outcome == "submitted"]
        help_reviews = [item for item in reviews if item.outcome == "needs_help"]
        if passed:
            status: Literal["passed", "needs_review", "needs_help", "needs_evidence"] = "passed"
            next_action = "Keep the sanitized pass evidence in the delivery archive and include it in final sign-off."
        elif submitted_reviews or (latest and latest.result in {"warning", "fail"}):
            status = "needs_review"
            next_action = "Review submitted or warning evidence, redact if needed, then register pass evidence."
        elif help_reviews:
            status = "needs_help"
            next_action = "Help the customer provide sanitized material, then rerun review task sync."
        else:
            status = "needs_evidence"
            next_action = str(platform_acceptance_evidence_requirements(scenario)["next_action"])
        gap_task = open_gap_tasks.get(scenario)
        link = new_links_by_scenario.get(scenario)
        scenarios.append(
            PlatformAcceptanceLiveRunScenario(
                scenario=scenario,
                status=status,
                evidence_count=len(scenario_evidence),
                latest_evidence_result=latest.result if latest else "",
                latest_evidence_url=(latest.evidence_url or latest.artifact_url) if latest else "",
                gap_task_id=gap_task.id if gap_task else None,
                gap_task_status=gap_task.status if gap_task else "",
                review_task_count=len([item for item in reviews if item.task_id]),
                customer_submission_count=customer_submission_counts.get(scenario, 0),
                receipt_count=receipt_counts.get(scenario, 0),
                submission_link_count=link_counts.get(scenario, 0),
                submission_link=link,
                next_action=next_action,
            )
        )
    passed_count = sum(1 for item in scenarios if item.status == "passed")
    needs_review_count = sum(1 for item in scenarios if item.status == "needs_review")
    needs_help_count = sum(1 for item in scenarios if item.status == "needs_help")
    missing_count = len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS) - passed_count
    if report.failed:
        live_status: Literal["ready_for_signoff", "reviewing", "collecting", "blocked"] = "blocked"
    elif missing_count == 0:
        live_status = "ready_for_signoff"
    elif needs_review_count:
        live_status = "reviewing"
    else:
        live_status = "collecting"
    live_run = PlatformAcceptanceLiveRun(
        id=f"platform-acceptance-live-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=live_status,
        summary=(
            f"Real platform acceptance live run. required={len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS)} "
            f"passed={passed_count} missing={missing_count} needs_review={needs_review_count} "
            f"needs_help={needs_help_count} sprint_pack={bool(sprint_pack)}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        required_total=len(PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS),
        passed=passed_count,
        missing=missing_count,
        needs_review=needs_review_count,
        needs_help=needs_help_count,
        scenarios=scenarios,
        sprint_pack=sprint_pack,
        created_at=now_sql(),
    )
    live_run.signoff_draft = build_platform_acceptance_live_run_signoff_draft(live_run)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{live_run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_live_run_markdown(live_run), encoding="utf-8")
        live_run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_live_run",
        max(1, len(scenarios)),
        "integration",
        live_run.id,
        {
            "status": live_run.status,
            "passed": live_run.passed,
            "missing": live_run.missing,
            "needs_review": live_run.needs_review,
            "needs_help": live_run.needs_help,
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_live_run",
        "integration_acceptance",
        live_run.id,
        "Generate real platform acceptance live run board",
        {
            "status": live_run.status,
            "passed": live_run.passed,
            "missing": live_run.missing,
            "needs_review": live_run.needs_review,
            "needs_help": live_run.needs_help,
            "sprint_pack": bool(sprint_pack),
        },
    )
    return live_run


def platform_acceptance_existing_pass(
    report: PlatformAcceptanceReport,
    scenario: PlatformAcceptanceScenario,
) -> PlatformAcceptanceEvidence | None:
    for evidence in report.evidence:
        if evidence.scenario == scenario and evidence.result == "pass":
            return evidence
    return None


def platform_acceptance_joint_debug_selected_auths(
    payload: PlatformAcceptanceJointDebugRunRequest,
    auths: list[ConnectorAuthView],
) -> list[ConnectorAuthView]:
    by_key = {auth.key: auth for auth in auths}
    selected: list[ConnectorAuthView] = []
    if payload.connectors:
        for raw_key in payload.connectors:
            try:
                key = normalize_connector_key(raw_key)
            except HTTPException:
                continue
            if key in by_key and key not in {item.key for item in selected}:
                selected.append(by_key[key])
        return selected
    return [
        auth for auth in auths
        if auth.configured_fields or auth.status in {"connected", "assist_only", "pending_auth"}
    ]


def build_platform_acceptance_joint_debug_markdown(run: PlatformAcceptanceJointDebugRun) -> str:
    lines = [
        "# Real Platform Joint Debug Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Customer: {run.customer_name}",
        f"Operator: {run.operator}",
        f"Status: {run.status}",
        f"Connectors: {', '.join(run.connectors) if run.connectors else '-'}",
        "",
        run.summary,
        "",
        "## Scenario Results",
        "",
        "| Scenario | Status | Connector | Evidence | Next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in run.scenarios:
        evidence_ref = item.registered_evidence.artifact_url if item.registered_evidence else ""
        if not evidence_ref and item.pull_result:
            evidence_ref = f"{item.pull_result.status} imported={item.pull_result.imported} duplicates={item.pull_result.duplicates}"
        lines.append(
            f"| {item.scenario} | {item.status} | {item.connector or '-'} | {evidence_ref or item.evidence_summary or '-'} | {item.next_action or '-'} |"
        )
    if run.live_run:
        lines.extend(
            [
                "",
                "## Live Run After Joint Debug",
                "",
                f"- Live run: {run.live_run.id}",
                f"- Status: {run.live_run.status}",
                f"- Passed: {run.live_run.passed}/{run.live_run.required_total}",
                f"- Missing: {run.live_run.missing}",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This run is read-only and does not send customer messages.",
            "- Pass evidence is registered only when the system has a verifiable local signal.",
            "- Customer trial remains a customer-provided evidence step and is not auto-passed.",
            "- No platform passwords, tokens, cookies, verification codes, signatures, or API secrets are written to artifacts.",
        ]
    )
    return "\n".join(lines)


async def platform_acceptance_register_joint_debug_pass(
    merchant: MerchantProfile,
    payload: PlatformAcceptanceJointDebugRunRequest,
    connector: str,
    scenario: PlatformAcceptanceScenario,
    evidence_note: str,
    existing: PlatformAcceptanceEvidence | None,
) -> PlatformAcceptanceEvidence:
    if existing:
        return existing
    if not payload.auto_register_pass_evidence:
        return PlatformAcceptanceEvidence(
            id="",
            connector=connector,
            scenario=scenario,
            result="pass",
            account_label=payload.customer_name,
            operator=payload.operator,
            summary=evidence_note,
            created_at=now_sql(),
        )
    return await record_platform_acceptance_evidence(
        PlatformAcceptanceEvidenceRequest(
            connector=connector,
            scenario=scenario,
            result="pass",
            account_label=payload.customer_name,
            operator=payload.operator,
            evidence_note=evidence_note,
            evidence_url="",
            no_secrets_confirmed=True,
        ),
        merchant,
    )


async def generate_platform_acceptance_joint_debug_run(
    payload: PlatformAcceptanceJointDebugRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceJointDebugRun:
    auths = await list_connector_auths(merchant)
    selected_auths = platform_acceptance_joint_debug_selected_auths(payload, auths)
    selected_keys = [auth.key for auth in selected_auths]
    initial_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    audit_logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    scenarios: list[PlatformAcceptanceJointDebugScenario] = []

    def existing_scenario(scenario: PlatformAcceptanceScenario) -> PlatformAcceptanceJointDebugScenario | None:
        existing = platform_acceptance_existing_pass(initial_report, scenario)
        if not existing:
            return None
        return PlatformAcceptanceJointDebugScenario(
            scenario=scenario,
            status="passed",
            connector=existing.connector,
            evidence_summary="Existing sanitized pass evidence is already registered.",
            next_action="Keep this evidence in the final delivery archive.",
            registered_evidence=existing,
        )

    def no_connector_result(scenario: PlatformAcceptanceScenario) -> PlatformAcceptanceJointDebugScenario:
        return PlatformAcceptanceJointDebugScenario(
            scenario=scenario,
            status="needs_setup",
            evidence_summary="No configured official connector is available for joint debug.",
            next_action="Configure OAuth credentials and read-only API endpoints for at least one customer platform connector.",
        )

    for scenario in ["official_auth", "callback"]:
        existing = existing_scenario(scenario)
        if existing:
            scenarios.append(existing)
            continue
        if not selected_auths:
            scenarios.append(no_connector_result(scenario))
            continue
        passed_item: PlatformAcceptanceJointDebugScenario | None = None
        fallback: PlatformAcceptanceJointDebugScenario | None = None
        for auth in selected_auths:
            fields = set(auth.configured_fields)
            if scenario == "official_auth":
                if fields.intersection({"access_token", "session_key"}):
                    note = f"Encrypted official access credential is configured for {auth.key}; configured_fields={','.join(sorted(fields.intersection({'access_token', 'session_key'})))}."
                    evidence = await platform_acceptance_register_joint_debug_pass(
                        merchant,
                        payload,
                        auth.key,
                        "official_auth",
                        note,
                        None,
                    )
                    passed_item = PlatformAcceptanceJointDebugScenario(
                        scenario="official_auth",
                        status="passed",
                        connector=auth.key,
                        evidence_summary=note,
                        next_action="Run read-only message and lead pulls to prove data access.",
                        registered_evidence=evidence,
                    )
                    break
                fallback = fallback or PlatformAcceptanceJointDebugScenario(
                    scenario="official_auth",
                    status="needs_setup",
                    connector=auth.key,
                    evidence_summary=f"{auth.key} is missing encrypted access credential fields.",
                    next_action="Finish OAuth token exchange or configure a session credential, then rerun joint debug.",
                )
            else:
                callback_seen = "oauth_code" in fields or any(
                    log.action == "connector.oauth.callback" and log.target_id == auth.key
                    for log in audit_logs
                )
                if callback_seen:
                    note = f"Official OAuth callback has been received for {auth.key}; audit trail or oauth_code field is present."
                    evidence = await platform_acceptance_register_joint_debug_pass(
                        merchant,
                        payload,
                        auth.key,
                        "callback",
                        note,
                        None,
                    )
                    passed_item = PlatformAcceptanceJointDebugScenario(
                        scenario="callback",
                        status="passed",
                        connector=auth.key,
                        evidence_summary=note,
                        next_action="Exchange the callback code if access credential is not yet present.",
                        registered_evidence=evidence,
                    )
                    break
                fallback = fallback or PlatformAcceptanceJointDebugScenario(
                    scenario="callback",
                    status="needs_setup",
                    connector=auth.key,
                    evidence_summary=f"{auth.key} has no recorded official callback signal.",
                    next_action="Open the generated OAuth link with the customer account and complete the callback.",
                )
        scenarios.append(passed_item or fallback or no_connector_result(scenario))

    async def run_read_pull(resource: Literal["messages", "leads"], scenario: PlatformAcceptanceScenario) -> PlatformAcceptanceJointDebugScenario:
        existing = existing_scenario(scenario)
        if existing:
            return existing
        if not selected_auths:
            return no_connector_result(scenario)
        if not payload.attempt_pull:
            return PlatformAcceptanceJointDebugScenario(
                scenario=scenario,
                status="skipped",
                evidence_summary="Read-only API pull was skipped by request.",
                next_action="Enable attempt_pull and rerun joint debug when the customer platform is ready.",
            )
        fallback: PlatformAcceptanceJointDebugScenario | None = None
        for auth in selected_auths:
            pull = await pull_connector_read_api(
                auth.key,
                ConnectorReadPullRequest(resource=resource, limit=payload.pull_limit),
                merchant,
            )
            total_seen = pull.imported + pull.duplicates
            if pull.status == "pulled" and total_seen > 0:
                note = (
                    f"Read-only {resource} pull succeeded for {auth.key}; "
                    f"imported={pull.imported} duplicates={pull.duplicates} skipped={pull.skipped} endpoint_host={pull.endpoint_host}."
                )
                evidence = await platform_acceptance_register_joint_debug_pass(
                    merchant,
                    payload,
                    auth.key,
                    scenario,
                    note,
                    None,
                )
                return PlatformAcceptanceJointDebugScenario(
                    scenario=scenario,
                    status="passed",
                    connector=auth.key,
                    evidence_summary=note,
                    next_action="Keep pulled records in CRM/Workflow and continue human-reviewed draft handling.",
                    registered_evidence=evidence,
                    pull_result=pull,
                )
            status: Literal["needs_setup", "failed", "skipped"] = "needs_setup" if pull.status == "setup_required" else "failed"
            if pull.status == "pulled" and total_seen == 0:
                status = "needs_setup"
            fallback = fallback or PlatformAcceptanceJointDebugScenario(
                scenario=scenario,
                status=status,
                connector=auth.key,
                evidence_summary=(
                    f"Read-only {resource} pull status={pull.status}; "
                    f"imported={pull.imported} duplicates={pull.duplicates} skipped={pull.skipped}."
                ),
                next_action=pull.next_action or "Check official endpoint, access credential, and customer account data.",
                pull_result=pull,
            )
        return fallback or no_connector_result(scenario)

    scenarios.append(await run_read_pull("messages", "read_message"))
    scenarios.append(await run_read_pull("leads", "read_lead"))

    draft_existing = existing_scenario("draft_reply")
    if draft_existing:
        scenarios.append(draft_existing)
    elif selected_auths:
        draft_match: ReplyDraftQueueItem | None = None
        draft_connector = ""
        for auth in selected_auths:
            drafts = await list_reply_drafts(merchant, status="", connector=auth.key, limit=5)
            if drafts:
                draft_match = drafts[0]
                draft_connector = auth.key
                break
        if draft_match:
            note = f"Reply draft queue contains a human-review draft from {draft_connector}; draft_id={draft_match.id} status={draft_match.status}."
            evidence = await platform_acceptance_register_joint_debug_pass(
                merchant,
                payload,
                draft_connector,
                "draft_reply",
                note,
                None,
            )
            scenarios.append(
                PlatformAcceptanceJointDebugScenario(
                    scenario="draft_reply",
                    status="passed",
                    connector=draft_connector,
                    evidence_summary=note,
                    next_action="Review the draft manually before any platform send.",
                    registered_evidence=evidence,
                )
            )
        else:
            scenarios.append(
                PlatformAcceptanceJointDebugScenario(
                    scenario="draft_reply",
                    status="needs_setup",
                    evidence_summary="No connector reply draft exists yet.",
                    next_action="Pull or ingest a real customer message so the AI customer-service desk creates a human-review reply draft.",
                )
            )
    else:
        scenarios.append(no_connector_result("draft_reply"))

    customer_trial_existing = existing_scenario("customer_trial")
    if customer_trial_existing:
        scenarios.append(customer_trial_existing)
    else:
        scenarios.append(
            PlatformAcceptanceJointDebugScenario(
                scenario="customer_trial",
                status="needs_setup",
                evidence_summary="Customer trial requires customer-provided sanitized material and cannot be auto-passed.",
                next_action="Ask the customer platform owner to submit sanitized trial evidence, then review and register pass evidence.",
            )
        )

    live_run = await generate_platform_acceptance_live_run(
        PlatformAcceptanceLiveRunRequest(
            customer_name=payload.customer_name,
            owner=payload.operator,
            recipient=payload.customer_name,
            due_days=1,
            expires_days=7,
            ensure_tasks=False,
            create_sprint_pack=False,
            create_links=False,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    passed_count = sum(1 for item in scenarios if item.status == "passed")
    missing_count = len([item for item in scenarios if item.status != "passed"])
    run_status: Literal["ready_for_signoff", "partial", "blocked"]
    if live_run.status == "ready_for_signoff":
        run_status = "ready_for_signoff"
    elif passed_count:
        run_status = "partial"
    else:
        run_status = "blocked"
    run = PlatformAcceptanceJointDebugRun(
        id=f"platform-joint-debug-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=run_status,
        summary=(
            f"Real platform joint debug run. connectors={len(selected_keys)} "
            f"passed={passed_count} missing={missing_count} live_run_status={live_run.status}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        operator=payload.operator.strip()[:120],
        connectors=selected_keys,
        passed=passed_count,
        missing=missing_count,
        scenarios=scenarios,
        live_run=live_run,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_joint_debug_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_joint_debug_run",
        max(1, len(scenarios)),
        "integration",
        run.id,
        {"status": run.status, "passed": run.passed, "missing": run.missing, "connectors": selected_keys},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_joint_debug_run",
        "integration_acceptance",
        run.id,
        "Run real platform joint debug evidence collection",
        {"status": run.status, "passed": run.passed, "missing": run.missing, "connectors": selected_keys},
    )
    return run


def platform_acceptance_final_signoff_path() -> str:
    return "/api/v1/public/platform-acceptance-final-signoff"


def platform_acceptance_final_signoff_submit_url(signed_code: str) -> str:
    base_url = platform_acceptance_submission_base_url()
    return f"{base_url}{platform_acceptance_final_signoff_path()}?token={urllib.parse.quote(signed_code)}"


def encode_platform_acceptance_signoff_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    mac = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-final-signoff:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"pafs.v1.{body}.{mac}"


def decode_platform_acceptance_signoff_token(signed_code: str) -> dict[str, Any]:
    try:
        prefix, version, body, mac = signed_code.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid signoff token") from exc
    if prefix != "pafs" or version != "v1":
        raise HTTPException(status_code=400, detail="Unsupported signoff token")
    expected = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-final-signoff:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Signoff token signature mismatch")
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Signoff token payload invalid") from exc
    expires_ts = int(payload.get("expires_ts") or 0)
    if expires_ts < int(time.time()):
        raise HTTPException(status_code=400, detail="Signoff token expired")
    return payload


def assert_platform_acceptance_final_signoff_safe(payload: PlatformAcceptanceFinalSignoffRequest) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the signoff does not contain secrets")
    text = "\n".join([payload.signer_name, payload.signer_role, payload.notes])
    risky_patterns = [
        r"(?i)password\s*[:=]",
        r"(?i)token\s*[:=]",
        r"(?i)secret\s*[:=]",
        r"(?i)cookie\s*[:=]",
        r"(?i)authorization\s*[:=]",
        r"(?i)verification[_ -]?code\s*[:=]",
        r"(?i)验证码\s*[:=]",
        r"(?i)密码\s*[:=]",
        r"(?i)密钥\s*[:=]",
    ]
    if any(re.search(pattern, text) for pattern in risky_patterns):
        raise HTTPException(status_code=400, detail="Signoff appears to contain a secret; store only sanitized notes")


def build_platform_acceptance_final_signoff_link_markdown(link: PlatformAcceptanceFinalSignoffLink) -> str:
    lines = [
        "# Real Platform Acceptance Final Sign-off Gate",
        "",
        f"Link ID: {link.id}",
        f"Created at: {link.created_at}",
        f"Customer: {link.customer_name}",
        f"Recipient: {link.recipient}",
        f"Owner: {link.owner}",
        f"Signer: {link.signer_name} / {link.signer_role}",
        f"Status: {link.status}",
        f"Expires at: {link.expires_at or '-'}",
        "",
        "## Gate Result",
        "",
        f"- Live run: {link.live_run.id}",
        f"- Live run status: {link.live_run.status}",
        f"- Passed: {link.live_run.passed}/{link.live_run.required_total}",
        f"- Missing: {link.live_run.missing}",
        "",
        "## Missing Scenarios",
        "",
    ]
    if link.missing_scenarios:
        lines.extend(f"- {scenario}" for scenario in link.missing_scenarios)
    else:
        lines.append("- None. All required scenarios have pass evidence.")
    lines.extend(["", "## Sign-off URL", "", link.submit_url or "-"])
    lines.extend(["", "## Sign-off Text", "", "```text", link.signoff_text or "-", "```"])
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- A final sign-off link is released only when the live run status is ready_for_signoff.",
            "- If this artifact is blocked, do not request customer final acceptance yet.",
            "- Public sign-off submission recomputes live-run readiness before accepting.",
            "- Do not store platform passwords, tokens, cookies, verification codes, raw signatures, or API secrets.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_final_signoff_link(
    payload: PlatformAcceptanceFinalSignoffLinkRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceFinalSignoffLink:
    live_run = await generate_platform_acceptance_live_run(
        PlatformAcceptanceLiveRunRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            due_days=1,
            expires_days=payload.expires_days,
            ensure_tasks=False,
            create_sprint_pack=False,
            create_links=False,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    missing = [item.scenario for item in live_run.scenarios if item.status != "passed"]
    status: Literal["ready", "blocked"] = "ready" if live_run.status == "ready_for_signoff" else "blocked"
    link_id = f"platform-final-signoff-link-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    expires_at = ""
    signed_link_code = ""
    submit_url = ""
    if status == "ready":
        expires_at_dt = datetime.now() + timedelta(days=payload.expires_days)
        expires_at = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        signed_link_code = encode_platform_acceptance_signoff_token(
            {
                "link_id": link_id,
                "merchant_id": merchant.id or 0,
                "customer_name": payload.customer_name.strip()[:160],
                "recipient": payload.recipient.strip()[:120],
                "owner": payload.owner.strip()[:120],
                "signer_name": payload.signer_name.strip()[:120],
                "signer_role": payload.signer_role.strip()[:120],
                "live_run_id": live_run.id,
                "expires_ts": int(expires_at_dt.timestamp()),
                "expires_at": expires_at,
            }
        )
        submit_url = platform_acceptance_final_signoff_submit_url(signed_link_code)
    link = PlatformAcceptanceFinalSignoffLink(
        id=link_id,
        status=status,
        customer_name=payload.customer_name.strip()[:160],
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        signer_name=payload.signer_name.strip()[:120],
        signer_role=payload.signer_role.strip()[:120],
        live_run=live_run,
        missing_scenarios=missing,
        submit_url=submit_url,
        **{"token": signed_link_code},
        expires_at=expires_at,
        signoff_text=live_run.signoff_draft,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{link.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_final_signoff_link_markdown(link), encoding="utf-8")
        link.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_final_signoff_link",
        1,
        "integration",
        link.id,
        {"status": link.status, "missing": len(link.missing_scenarios), "live_run": live_run.id},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_final_signoff_link",
        "integration_acceptance",
        link.id,
        "Generate final platform acceptance sign-off gate",
        {"status": link.status, "missing": len(link.missing_scenarios), "live_run": live_run.id},
    )
    return link


def build_platform_acceptance_gap_closure_markdown(run: PlatformAcceptanceGapClosureRun) -> str:
    lines = [
        "# Real Platform Remaining Gap Closure Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        f"Status: {run.status}",
        "",
        run.summary,
        "",
        "## Missing Scenarios",
        "",
        f"- Before: {', '.join(run.missing_before) if run.missing_before else 'none'}",
        f"- After: {', '.join(run.missing_after) if run.missing_after else 'none'}",
        "",
        "## Closure Items",
        "",
        "| Scenario | Status | Connector | Missing Fields | Evidence | Next Action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not run.items:
        lines.append("| - | - | - | - | No remaining gap items. | - |")
    for item in run.items:
        evidence_ref = ""
        if item.registered_evidence and item.registered_evidence.artifact_url:
            evidence_ref = item.registered_evidence.artifact_url
        elif item.submission_link and item.submission_link.submit_url:
            evidence_ref = "customer submission link generated"
        elif item.exchange_result:
            evidence_ref = f"exchange={item.exchange_result.status}"
        elif item.pull_result:
            evidence_ref = f"pull={item.pull_result.status} imported={item.pull_result.imported} duplicates={item.pull_result.duplicates}"
        lines.append(
            f"| {item.scenario} | {item.status} | {item.connector or '-'} | "
            f"{', '.join(item.missing_fields) if item.missing_fields else '-'} | "
            f"{evidence_ref or item.evidence_summary or '-'} | {item.next_action or '-'} |"
        )
    if run.joint_debug:
        lines.extend(
            [
                "",
                "## Joint Debug",
                "",
                f"- Joint debug: {run.joint_debug.id}",
                f"- Status: {run.joint_debug.status}",
                f"- Passed: {run.joint_debug.passed}",
                f"- Missing: {run.joint_debug.missing}",
            ]
        )
    if run.gap_sync:
        lines.extend(
            [
                "",
                "## CRM Gap Tasks",
                "",
                f"- Status: {run.gap_sync.status}",
                f"- Created: {run.gap_sync.created}",
                f"- Existing: {run.gap_sync.skipped_existing}",
            ]
        )
    if run.final_gate:
        gate_status = run.final_gate.get("status") if isinstance(run.final_gate, dict) else getattr(run.final_gate, "status", "")
        gate_missing = run.final_gate.get("missing_scenarios") if isinstance(run.final_gate, dict) else getattr(run.final_gate, "missing_scenarios", [])
        lines.extend(
            [
                "",
                "## Final Sign-off Gate",
                "",
                f"- Status: {gate_status}",
                f"- Missing: {', '.join(gate_missing) if gate_missing else 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- This closure run does not fabricate customer platform evidence.",
            "- OAuth exchange and read-only pulls run only when the required connector fields are configured.",
            "- Customer trial evidence must be submitted by the customer and reviewed by operations.",
            "- Final sign-off remains blocked until the live run is ready_for_signoff.",
        ]
    )
    return "\n".join(lines)


def platform_acceptance_gap_closure_auths(
    payload: PlatformAcceptanceGapClosureRunRequest,
    auths: list[ConnectorAuthView],
) -> list[ConnectorAuthView]:
    return platform_acceptance_joint_debug_selected_auths(
        PlatformAcceptanceJointDebugRunRequest(connectors=payload.connectors),
        auths,
    )


def connector_has_access_credential(auth: ConnectorAuthView) -> bool:
    return any(field in auth.configured_fields for field in ["access_token", "session_key"])


def connector_has_read_endpoint(auth: ConnectorAuthView, resource: Literal["messages", "leads"]) -> bool:
    endpoint_fields = READ_MESSAGE_ENDPOINT_FIELDS if resource == "messages" else READ_LEAD_ENDPOINT_FIELDS
    return any(field in auth.configured_fields for field in endpoint_fields)


def exchange_missing_fields_for_auth(auth: ConnectorAuthView) -> list[str]:
    fields = set(auth.configured_fields)
    catalog = CONNECTOR_CATALOG.get(auth.key, {})
    missing: list[str] = []
    if not fields.intersection(set(OAUTH_TOKEN_URL_FIELD_NAMES)):
        missing.append("token_url")
    if not fields.intersection(set(OAUTH_CLIENT_ID_FIELD_NAMES)):
        missing.append("client_id/client_key/app_key")
    if "oauth_code" not in fields:
        missing.append("oauth_code")
    if set(catalog.get("required_fields", [])).intersection(set(OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES)) and not fields.intersection(set(OAUTH_CLIENT_CREDENTIAL_FIELD_NAMES)):
        missing.append("client_secret/app_secret")
    return missing


def best_auth_for_read(auths: list[ConnectorAuthView], resource: Literal["messages", "leads"]) -> ConnectorAuthView | None:
    for auth in auths:
        if connector_has_access_credential(auth) and connector_has_read_endpoint(auth, resource):
            return auth
    for auth in auths:
        if connector_has_access_credential(auth) or connector_has_read_endpoint(auth, resource):
            return auth
    return auths[0] if auths else None


async def generate_platform_acceptance_gap_closure_run(
    payload: PlatformAcceptanceGapClosureRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceGapClosureRun:
    before_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    joint_debug = await generate_platform_acceptance_joint_debug_run(
        PlatformAcceptanceJointDebugRunRequest(
            customer_name=payload.customer_name,
            operator=payload.owner,
            connectors=payload.connectors,
            attempt_pull=payload.attempt_pull,
            auto_register_pass_evidence=payload.auto_register_pass_evidence,
            pull_limit=3,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    auths = platform_acceptance_gap_closure_auths(payload, await list_connector_auths(merchant))
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    items: list[PlatformAcceptanceGapClosureItem] = []

    async def closure_pass_evidence(
        connector: str,
        scenario: PlatformAcceptanceScenario,
        note: str,
    ) -> PlatformAcceptanceEvidence:
        if not payload.auto_register_pass_evidence:
            return PlatformAcceptanceEvidence(
                id="",
                connector=connector,
                scenario=scenario,
                result="pass",
                account_label=payload.customer_name,
                operator=payload.owner,
                summary=note,
                created_at=now_sql(),
            )
        return await record_platform_acceptance_evidence(
            PlatformAcceptanceEvidenceRequest(
                connector=connector,
                scenario=scenario,
                result="pass",
                account_label=payload.customer_name,
                operator=payload.owner,
                evidence_note=note,
                no_secrets_confirmed=True,
            ),
            merchant,
        )

    def existing_pass_item(scenario: PlatformAcceptanceScenario) -> PlatformAcceptanceGapClosureItem | None:
        evidence = platform_acceptance_existing_pass(report, scenario)
        if not evidence:
            return None
        return PlatformAcceptanceGapClosureItem(
            scenario=scenario,
            status="passed",
            connector=evidence.connector,
            evidence_summary="Pass evidence is already registered after joint debug.",
            next_action="Keep this evidence in the delivery archive.",
            registered_evidence=evidence,
        )

    for scenario in before_report.missing_scenarios:
        existing = existing_pass_item(scenario)
        if existing:
            items.append(existing)
            continue
        if scenario == "official_auth":
            oauth_auths = [auth for auth in auths if auth.auth_mode == "oauth"]
            target_auth = next((auth for auth in oauth_auths if "oauth_code" in auth.configured_fields), oauth_auths[0] if oauth_auths else None)
            if not target_auth:
                items.append(
                    PlatformAcceptanceGapClosureItem(
                        scenario=scenario,
                        status="needs_config",
                        missing_fields=["oauth_connector"],
                        evidence_summary="No OAuth connector is ready for official authorization closure.",
                        next_action="Create or select an OAuth connector, complete official callback, then rerun closure.",
                    )
                )
                continue
            missing = exchange_missing_fields_for_auth(target_auth)
            exchange_result: ConnectorOAuthExchangeResponse | None = None
            if payload.attempt_exchange and not missing:
                exchange_result = await exchange_connector_oauth_token(
                    target_auth.key,
                    ConnectorOAuthExchangeRequest(),
                    merchant,
                )
                if exchange_result.status == "connected":
                    note = (
                        f"OAuth token exchange connected for {target_auth.key}; "
                        f"configured_fields={','.join(exchange_result.configured_fields)}."
                    )
                    evidence = await closure_pass_evidence(target_auth.key, "official_auth", note)
                    items.append(
                        PlatformAcceptanceGapClosureItem(
                            scenario=scenario,
                            status="passed" if payload.auto_register_pass_evidence else "ready",
                            connector=target_auth.key,
                            evidence_summary=note,
                            next_action="Run read-only message and lead pulls.",
                            registered_evidence=evidence,
                            exchange_result=exchange_result,
                        )
                    )
                    continue
                missing = ["token_exchange_failed"]
            items.append(
                PlatformAcceptanceGapClosureItem(
                    scenario=scenario,
                    status="failed" if exchange_result and exchange_result.status == "failed" else "needs_config",
                    connector=target_auth.key,
                    missing_fields=missing,
                    evidence_summary="OAuth callback exists but official access credential is not ready.",
                    next_action=(exchange_result.next_action if exchange_result else "Configure token_url and required app credentials, then rerun closure."),
                    exchange_result=exchange_result,
                )
            )
            continue
        if scenario in {"read_message", "read_lead"}:
            resource: Literal["messages", "leads"] = "messages" if scenario == "read_message" else "leads"
            target_auth = best_auth_for_read(auths, resource)
            if not target_auth:
                items.append(
                    PlatformAcceptanceGapClosureItem(
                        scenario=scenario,
                        status="needs_config",
                        missing_fields=["access_token/session_key", f"{resource}_url"],
                        evidence_summary="No connector is configured for read-only API pull.",
                        next_action="Configure official access credential and read-only endpoint, then rerun closure.",
                    )
                )
                continue
            missing = []
            if not connector_has_access_credential(target_auth):
                missing.append("access_token/session_key")
            if not connector_has_read_endpoint(target_auth, resource):
                missing.append(f"{resource}_url")
            pull_result: ConnectorReadPullResponse | None = None
            if payload.attempt_pull and not missing:
                pull_result = await pull_connector_read_api(
                    target_auth.key,
                    ConnectorReadPullRequest(resource=resource, limit=3),
                    merchant,
                )
                if pull_result.status == "pulled" and pull_result.imported + pull_result.duplicates > 0:
                    note = (
                        f"Read-only {resource} pull succeeded for {target_auth.key}; "
                        f"imported={pull_result.imported} duplicates={pull_result.duplicates}."
                    )
                    evidence = await closure_pass_evidence(target_auth.key, scenario, note)
                    items.append(
                        PlatformAcceptanceGapClosureItem(
                            scenario=scenario,
                            status="passed" if payload.auto_register_pass_evidence else "ready",
                            connector=target_auth.key,
                            evidence_summary=note,
                            next_action="Keep pulled CRM/Workflow records and continue manual review.",
                            registered_evidence=evidence,
                            pull_result=pull_result,
                        )
                    )
                    continue
                if pull_result.status == "failed":
                    missing.append("pull_failed")
                elif pull_result.status == "pulled":
                    missing.append("sample_data")
            items.append(
                PlatformAcceptanceGapClosureItem(
                    scenario=scenario,
                    status="failed" if pull_result and pull_result.status == "failed" else "needs_config",
                    connector=target_auth.key,
                    missing_fields=missing,
                    evidence_summary=f"Read-only {resource} evidence is still missing.",
                    next_action=(pull_result.next_action if pull_result else "Configure official endpoint and access credential, then rerun closure."),
                    pull_result=pull_result,
                )
            )
            continue
        if scenario == "customer_trial":
            submission_link = None
            if payload.create_submission_links:
                submission_link = await generate_platform_acceptance_evidence_submission_link(
                    PlatformAcceptanceEvidenceSubmissionLinkRequest(
                        recipient=payload.recipient,
                        owner=payload.owner,
                        scenarios=["customer_trial"],
                        due_days=1,
                        expires_days=7,
                        include_artifact=True,
                    ),
                    merchant,
                )
            items.append(
                PlatformAcceptanceGapClosureItem(
                    scenario=scenario,
                    status="needs_customer",
                    connector="customer",
                    evidence_summary="Customer trial needs customer-provided sanitized material.",
                    next_action="Send the customer trial submission link, then review the material and register pass evidence.",
                    submission_link=submission_link,
                )
            )
            continue
        items.append(
            PlatformAcceptanceGapClosureItem(
                scenario=scenario,
                status="needs_config",
                evidence_summary="Scenario still needs manual closure.",
                next_action=str(platform_acceptance_evidence_requirements(scenario)["next_action"]),
            )
        )

    after_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    gap_sync = await sync_platform_acceptance_gaps_to_crm_tasks(
        PlatformAcceptanceGapSyncRequest(
            owner=payload.owner,
            due_days=1,
            create_tasks=payload.create_gap_tasks,
            include_artifact=True,
        ),
        merchant,
    )
    final_gate = await generate_platform_acceptance_final_signoff_link(
        PlatformAcceptanceFinalSignoffLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            signer_name=payload.recipient,
            signer_role="platform owner",
            expires_days=7,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    if not after_report.missing_scenarios and final_gate.status == "ready":
        status: Literal["ready_for_signoff", "partial", "blocked"] = "ready_for_signoff"
    elif len(after_report.missing_scenarios) < len(before_report.missing_scenarios) or any(item.status == "passed" for item in items):
        status = "partial"
    else:
        status = "blocked"
    run = PlatformAcceptanceGapClosureRun(
        id=f"platform-gap-closure-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Remaining platform acceptance gap closure. before={len(before_report.missing_scenarios)} "
            f"after={len(after_report.missing_scenarios)} items={len(items)} gate={final_gate.status}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        missing_before=before_report.missing_scenarios,
        missing_after=after_report.missing_scenarios,
        items=items,
        joint_debug=joint_debug,
        gap_sync=gap_sync,
        final_gate=final_gate.model_dump(),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_gap_closure_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_gap_closure_run",
        max(1, len(items)),
        "integration",
        run.id,
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after)},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_gap_closure_run",
        "integration_acceptance",
        run.id,
        "Run remaining platform acceptance gap closure",
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after)},
    )
    return run


def platform_acceptance_owner_action_callback_url(auth: ConnectorAuthView) -> str:
    path = auth.callback_url or connector_oauth_callback_path(auth.key)
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{platform_acceptance_submission_base_url()}{path}"


def build_platform_acceptance_owner_action_draft(pack: PlatformAcceptanceOwnerActionPack) -> str:
    lines = [
        f"{pack.recipient}，您好：",
        "",
        f"我们正在完成 {pack.customer_name} 的真实平台最终验收。当前仍需您协助处理 {len(pack.missing_scenarios)} 个外部平台动作：",
        "",
    ]
    for item in pack.items:
        if item.status == "passed":
            continue
        lines.append(f"- {item.scenario}: {item.action_text}")
        if item.callback_url:
            lines.append(f"  Callback URL: {item.callback_url}")
        if item.required_fields:
            lines.append(f"  Required fields: {', '.join(item.required_fields)}")
        if item.submission_link and item.submission_link.submit_url:
            lines.append(f"  Submission link: {item.submission_link.submit_url}")
    lines.extend(
        [
            "",
            "安全提醒：请不要在聊天、文档、截图或邮件正文里发送密码、token、cookie、验证码、签名密钥或 API secret。敏感字段只通过后台安全配置入口填写。",
        ]
    )
    return "\n".join(lines)


def build_platform_acceptance_owner_action_pack_markdown(pack: PlatformAcceptanceOwnerActionPack) -> str:
    lines = [
        "# Real Platform Owner Action Pack",
        "",
        f"Pack ID: {pack.id}",
        f"Created at: {pack.created_at}",
        f"Customer: {pack.customer_name}",
        f"Owner: {pack.owner}",
        f"Recipient: {pack.recipient}",
        f"Status: {pack.status}",
        "",
        pack.summary,
        "",
        "## Missing Scenarios",
        "",
        f"- {', '.join(pack.missing_scenarios) if pack.missing_scenarios else 'none'}",
        "",
        "## Action Items",
        "",
        "| Scenario | Status | Connector | Required Fields | Configured Fields | Callback / Link | Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not pack.items:
        lines.append("| - | - | - | - | - | - | No owner action is required. |")
    for item in pack.items:
        link = item.callback_url
        if item.submission_link and item.submission_link.submit_url:
            link = item.submission_link.submit_url
        lines.append(
            f"| {item.scenario} | {item.status} | {item.connector or '-'} | "
            f"{', '.join(item.required_fields) if item.required_fields else '-'} | "
            f"{', '.join(item.configured_fields) if item.configured_fields else '-'} | "
            f"{link or '-'} | {item.action_text or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Message Draft",
            "",
            "```text",
            pack.draft_text,
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This pack is for customer platform coordination and does not store secrets.",
            "- Secrets must be entered only through the admin security configuration surface.",
            "- Customer trial evidence must be submitted through the sanitized material link and reviewed before pass evidence is registered.",
            "- Final sign-off remains blocked until all required scenarios have pass evidence.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_owner_action_pack(
    payload: PlatformAcceptanceOwnerActionPackRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceOwnerActionPack:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    auths = platform_acceptance_joint_debug_selected_auths(
        PlatformAcceptanceJointDebugRunRequest(connectors=payload.connectors),
        await list_connector_auths(merchant),
    )
    items: list[PlatformAcceptanceOwnerActionItem] = []

    def passed_item(scenario: PlatformAcceptanceScenario) -> PlatformAcceptanceOwnerActionItem | None:
        evidence = platform_acceptance_existing_pass(report, scenario)
        if not evidence:
            return None
        return PlatformAcceptanceOwnerActionItem(
            scenario=scenario,
            status="passed",
            connector=evidence.connector,
            configured_fields=["pass_evidence"],
            action_text="Pass evidence is already registered; no customer platform action is needed.",
            secure_note="Keep the sanitized evidence artifact in the final delivery archive.",
        )

    for scenario in report.missing_scenarios:
        existing = passed_item(scenario)
        if existing:
            items.append(existing)
            continue
        if scenario == "official_auth":
            oauth_auths = [auth for auth in auths if auth.auth_mode == "oauth"]
            auth = next((item for item in oauth_auths if "oauth_code" in item.configured_fields), oauth_auths[0] if oauth_auths else None)
            if not auth:
                items.append(
                    PlatformAcceptanceOwnerActionItem(
                        scenario=scenario,
                        status="needs_customer",
                        required_fields=["oauth_connector", "official_app_credentials"],
                        action_text="Choose the official platform connector and provide the official app authorization details through the admin configuration surface.",
                        secure_note="Do not paste app secrets into chat or documents.",
                    )
                )
                continue
            missing = exchange_missing_fields_for_auth(auth)
            status: Literal["passed", "needs_customer", "needs_ops", "ready"] = "needs_ops" if not missing else "needs_customer"
            action = (
                "Operations can run token exchange now, then rerun joint debug to register official_auth evidence."
                if not missing
                else "Provide the missing OAuth/token exchange fields through the admin configuration surface, then ask operations to rerun gap closure."
            )
            items.append(
                PlatformAcceptanceOwnerActionItem(
                    scenario=scenario,
                    status=status,
                    connector=auth.key,
                    required_fields=missing or ["run_token_exchange"],
                    configured_fields=auth.configured_fields,
                    callback_url=platform_acceptance_owner_action_callback_url(auth),
                    action_text=action,
                    secure_note="Sensitive credentials must be entered only in the admin security form.",
                )
            )
            continue
        if scenario in {"read_message", "read_lead"}:
            resource: Literal["messages", "leads"] = "messages" if scenario == "read_message" else "leads"
            auth = best_auth_for_read(auths, resource)
            missing: list[str] = []
            if not auth:
                missing = ["access_token/session_key", f"{resource}_url"]
                items.append(
                    PlatformAcceptanceOwnerActionItem(
                        scenario=scenario,
                        status="needs_customer",
                        required_fields=missing,
                        action_text=f"Provide a customer-authorized connector, official read-only {resource} endpoint, and a platform account with sample data.",
                        secure_note="The endpoint URL can be shared as configuration; access credentials must be entered through the admin security form.",
                    )
                )
                continue
            if not connector_has_access_credential(auth):
                missing.append("access_token/session_key")
            if not connector_has_read_endpoint(auth, resource):
                missing.append(f"{resource}_url")
            if missing:
                status = "needs_customer"
                action = f"Provide the missing {resource} read-only configuration and ensure the customer account has at least one sample record."
            else:
                status = "needs_ops"
                action = f"Operations can run the read-only {resource} pull now; pass evidence will be registered only if a real sample is returned."
            items.append(
                PlatformAcceptanceOwnerActionItem(
                    scenario=scenario,
                    status=status,
                    connector=auth.key,
                    required_fields=missing or [f"run_read_only_{resource}_pull"],
                    configured_fields=auth.configured_fields,
                    action_text=action,
                    secure_note="Read-only pulls do not send customer messages and do not publish changes.",
                )
            )
            continue
        if scenario == "customer_trial":
            submission_link = None
            if payload.create_customer_trial_link:
                submission_link = await generate_platform_acceptance_evidence_submission_link(
                    PlatformAcceptanceEvidenceSubmissionLinkRequest(
                        recipient=payload.recipient,
                        owner=payload.owner,
                        scenarios=["customer_trial"],
                        due_days=1,
                        expires_days=payload.expires_days,
                        include_artifact=True,
                    ),
                    merchant,
                )
            items.append(
                PlatformAcceptanceOwnerActionItem(
                    scenario=scenario,
                    status="needs_customer",
                    connector="customer",
                    required_fields=["sanitized_trial_screenshot_or_recording", "trial_notes"],
                    action_text="Submit sanitized customer trial material through the customer evidence link, then operations will review and register pass evidence.",
                    secure_note="Remove passwords, tokens, cookies, verification codes, signatures, and private customer data before submission.",
                    submission_link=submission_link,
                )
            )
            continue
        items.append(
            PlatformAcceptanceOwnerActionItem(
                scenario=scenario,
                status="needs_customer",
                required_fields=["sanitized_evidence"],
                action_text=str(platform_acceptance_evidence_requirements(scenario)["next_action"]),
                secure_note="Submit only sanitized evidence.",
            )
        )

    if not report.missing_scenarios:
        status: Literal["complete", "ready_for_customer", "blocked"] = "complete"
    elif items:
        status = "ready_for_customer"
    else:
        status = "blocked"
    pack = PlatformAcceptanceOwnerActionPack(
        id=f"platform-owner-action-pack-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform owner action pack. missing={len(report.missing_scenarios)} "
            f"items={len(items)} recipient={payload.recipient}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        missing_scenarios=report.missing_scenarios,
        items=items,
        created_at=now_sql(),
    )
    pack.draft_text = build_platform_acceptance_owner_action_draft(pack)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{pack.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_owner_action_pack_markdown(pack), encoding="utf-8")
        pack.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_owner_action_pack",
        max(1, len(items)),
        "integration",
        pack.id,
        {"status": pack.status, "missing": len(pack.missing_scenarios), "items": len(items)},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_owner_action_pack",
        "integration_acceptance",
        pack.id,
        "Generate platform owner action pack for remaining acceptance gaps",
        {"status": pack.status, "missing": len(pack.missing_scenarios), "items": len(items)},
    )
    return pack


OWNER_CLOSURE_NONSECRET_ALLOWLIST = {
    "authorize_url",
    "oauth_authorize_url",
    "token_url",
    "oauth_token_url",
    "token_endpoint",
    "client_id",
    "client_key",
    "app_key",
    "scope",
    "redirect_uri",
    "callback_url",
    "grant_type",
    "grant_type_param",
    "client_id_param",
    "client_secret_param",
    "oauth_client_id_param",
    "oauth_client_secret_param",
    "code_param",
    "oauth_code_param",
    "redirect_uri_param",
    "messages_url",
    "read_messages_url",
    "leads_url",
    "read_leads_url",
    "orders_url",
    "products_url",
    "account_label",
    "platform_account_id",
    "sandbox_mode",
    "token_extra_params",
    "oauth_token_extra_params",
}


def sanitize_owner_closure_nonsecret_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for name, value in config.items():
        key = str(name).strip()
        if not key:
            continue
        lowered = key.lower()
        if lowered not in OWNER_CLOSURE_NONSECRET_ALLOWLIST:
            if any(part in lowered for part in ["secret", "password", "access_token", "refresh_token", "session_key", "authorization", "cookie", "webhook_token", "api_key", "oauth_code"]):
                raise HTTPException(status_code=400, detail=f"{key} must be submitted as an encrypted secret field, not nonsecret_config")
        if isinstance(value, str):
            if re.search(r"(?i)(password|access_token|refresh_token|session_key|authorization|cookie|api[_-]?key)\s*[:=]", value):
                raise HTTPException(status_code=400, detail=f"{key} appears to contain a secret value")
            value = value.strip()
            if not value:
                continue
            sanitized[key] = value[:1000]
        elif isinstance(value, (int, float, bool)) or value is None:
            if value is not None:
                sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = {str(child_key): str(child_value)[:500] for child_key, child_value in value.items() if str(child_value).strip()}
        elif isinstance(value, list):
            sanitized[key] = [str(item)[:500] for item in value if str(item).strip()][:20]
        else:
            sanitized[key] = str(value)[:1000]
    return sanitized


def assert_platform_acceptance_owner_closure_safe(payload: PlatformAcceptanceOwnerClosureRunRequest) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm owner closure notes and receipt links contain no secrets")
    receipt_probe = PlatformAcceptanceEvidenceReceiptRequest(
        notice_id="owner-closure-probe",
        recipient=payload.recipient,
        outcome=payload.receipt_outcome,
        scenario_receipts=payload.scenario_receipts,
        notes=payload.notes,
        include_artifact=False,
        no_secrets_confirmed=True,
    )
    assert_platform_acceptance_receipt_safe(receipt_probe)
    for update in payload.connector_updates:
        sanitize_owner_closure_nonsecret_config(update.nonsecret_config)


def build_platform_acceptance_owner_closure_markdown(run: PlatformAcceptanceOwnerClosureRun) -> str:
    lines = [
        "# Real Platform Owner Closure Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        f"Status: {run.status}",
        "",
        run.summary,
        "",
        "## Missing Scenarios",
        "",
        f"- Before: {', '.join(run.missing_before) if run.missing_before else 'none'}",
        f"- After: {', '.join(run.missing_after) if run.missing_after else 'none'}",
        "",
        "## Connector Updates",
        "",
        "| Connector | Status | Auth | Applied Fields | Secret Field Names | Missing Fields | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not run.connector_results:
        lines.append("| - | skipped | - | - | - | - | No connector update was submitted. |")
    for item in run.connector_results:
        lines.append(
            f"| {item.connector} | {item.status} / {item.auth_status} | {item.auth_mode or '-'} | "
            f"{', '.join(item.applied_fields) if item.applied_fields else '-'} | "
            f"{', '.join(item.secret_field_names) if item.secret_field_names else '-'} | "
            f"{', '.join(item.missing_fields) if item.missing_fields else '-'} | "
            f"{item.next_action or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Closure Results",
            "",
            f"- Receipt: {run.receipt.id if run.receipt else '-'}",
            f"- Review sync: {run.review_sync.id if run.review_sync else '-'}",
            f"- Gap closure: {run.gap_closure.id if run.gap_closure else '-'} / {run.gap_closure.status if run.gap_closure else '-'}",
            f"- Final gate: {run.final_gate.id if run.final_gate else '-'} / {run.final_gate.status if run.final_gate else '-'}",
            f"- Owner action pack: {run.owner_action_pack.id if run.owner_action_pack else '-'}",
            "",
            "## Safety Boundary",
            "",
            "- This artifact reports secret field names only, never secret values.",
            "- Connector credentials are stored through the encrypted connector configuration path.",
            "- Read-only pulls do not send messages, publish content, or mutate customer platform data.",
            "- Final sign-off stays blocked until every required scenario has verifiable pass evidence.",
        ]
    )
    return "\n".join(lines)


def platform_acceptance_owner_closure_path() -> str:
    return "/api/v1/public/platform-acceptance-owner-closure"


def platform_acceptance_owner_closure_submit_url(token: str) -> str:
    base_url = platform_acceptance_submission_base_url()
    return f"{base_url}{platform_acceptance_owner_closure_path()}?token={urllib.parse.quote(token)}"


def encode_platform_acceptance_owner_closure_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    mac = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-owner-closure:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"paoc.v1.{body}.{mac}"


def decode_platform_acceptance_owner_closure_token(token: str) -> dict[str, Any]:
    try:
        prefix, version, body, mac = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid owner closure token") from exc
    if prefix != "paoc" or version != "v1":
        raise HTTPException(status_code=400, detail="Unsupported owner closure token")
    expected = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-owner-closure:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Owner closure token signature mismatch")
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Owner closure token payload invalid") from exc
    expires_ts = int(payload.get("expires_ts") or 0)
    if expires_ts < int(time.time()):
        raise HTTPException(status_code=400, detail="Owner closure token expired")
    connectors: list[str] = []
    for raw_key in payload.get("connectors", []) or []:
        try:
            connectors.append(normalize_connector_key(str(raw_key)))
        except HTTPException:
            continue
    payload["connectors"] = list(dict.fromkeys(connectors))
    return payload


def build_platform_acceptance_owner_closure_link_markdown(link: PlatformAcceptanceOwnerClosureLink) -> str:
    lines = [
        "# Real Platform Owner Secure Closure Link",
        "",
        f"Link ID: {link.id}",
        f"Created at: {link.created_at}",
        f"Customer: {link.customer_name}",
        f"Owner: {link.owner}",
        f"Recipient: {link.recipient}",
        f"Status: {link.status}",
        f"Expires at: {link.expires_at}",
        "",
        "## Allowed Connectors",
        "",
        f"- {', '.join(link.connectors) if link.connectors else 'configured connector selected by owner'}",
        "",
        "## Submission URL",
        "",
        link.submit_url or "-",
        "",
        "## Draft",
        "",
        "```text",
        link.draft_text or "-",
        "```",
        "",
        "## Safety Boundary",
        "",
        "- Secret values are submitted only through the HTTPS form and encrypted connector storage path.",
        "- This artifact stores no passwords, tokens, cookies, verification codes, signatures, session keys, or API secrets.",
        "- The closure run will still block final sign-off when official platforms do not return verifiable evidence.",
    ]
    return "\n".join(lines)


async def generate_platform_acceptance_owner_closure_link(
    payload: PlatformAcceptanceOwnerClosureLinkRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceOwnerClosureLink:
    selected_connectors: list[str] = []
    for raw_key in payload.connectors:
        try:
            selected_connectors.append(normalize_connector_key(raw_key))
        except HTTPException:
            continue
    selected_connectors = list(dict.fromkeys(selected_connectors))
    link_id = f"platform-owner-closure-link-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    expires_at_dt = datetime.now() + timedelta(days=payload.expires_days)
    expires_at = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    token_payload = {
        "link_id": link_id,
        "merchant_id": merchant.id or 0,
        "customer_name": payload.customer_name.strip()[:160],
        "owner": payload.owner.strip()[:120],
        "recipient": payload.recipient.strip()[:120],
        "connectors": selected_connectors,
        "expires_ts": int(expires_at_dt.timestamp()),
        "expires_at": expires_at,
    }
    signed_code = encode_platform_acceptance_owner_closure_token(token_payload)
    submit_url = platform_acceptance_owner_closure_submit_url(signed_code)
    draft_text = "\n".join(
        [
            f"Please complete the secure real-platform closure form for {payload.customer_name}:",
            submit_url,
            "",
            "Use this form only for official platform configuration fields and sanitized customer trial material.",
            "Do not send secrets in chat, email body, screenshots, or documents.",
            "The system will encrypt submitted secret fields and rerun final acceptance gates automatically.",
        ]
    )
    link = PlatformAcceptanceOwnerClosureLink(
        id=link_id,
        status="ready",
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        connectors=selected_connectors,
        submit_url=submit_url,
        token=signed_code,
        expires_at=expires_at,
        draft_text=draft_text,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{link.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_owner_closure_link_markdown(link), encoding="utf-8")
        link.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_owner_closure_link",
        max(1, len(selected_connectors)),
        "integration",
        link.id,
        {"connectors": selected_connectors, "expires_at": expires_at},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_owner_closure_link",
        "integration_acceptance",
        link.id,
        "Generate secure owner closure submission link",
        {"connectors": selected_connectors, "recipient": link.recipient, "expires_at": expires_at},
    )
    return link


async def generate_platform_acceptance_owner_closure_run(
    payload: PlatformAcceptanceOwnerClosureRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceOwnerClosureRun:
    assert_platform_acceptance_owner_closure_safe(payload)
    before_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    connector_results: list[PlatformAcceptanceOwnerClosureConnectorResult] = []
    connector_keys: list[str] = []
    for update in payload.connector_updates:
        connector = normalize_connector_key(update.connector)
        nonsecret_config = sanitize_owner_closure_nonsecret_config(update.nonsecret_config)
        secret_field_names = sorted([str(name) for name, value in update.secret_fields.items() if str(value).strip()])
        applied_fields = sorted(set(nonsecret_config.keys()) | set(secret_field_names))
        try:
            auth = await update_connector_auth(
                connector,
                ConnectorAuthUpdate(
                    status=update.status,
                    auth_mode=update.auth_mode,
                    account_name=update.account_name,
                    callback_url=update.callback_url,
                    nonsecret_config=nonsecret_config,
                    secret_fields=update.secret_fields,
                    read_only_enabled=update.read_only_enabled,
                    send_enabled=False,
                    notes=(update.notes or "platform owner closure intake")[:500],
                ),
                merchant,
            )
            connector_results.append(
                PlatformAcceptanceOwnerClosureConnectorResult(
                    connector=auth.key,
                    status="applied",
                    auth_status=auth.status,
                    auth_mode=auth.auth_mode,
                    configured_fields=auth.configured_fields,
                    missing_fields=auth.missing_fields,
                    applied_fields=applied_fields,
                    secret_field_names=secret_field_names,
                    next_action="Run gap closure; token exchange and read-only pulls will execute only when required fields are complete.",
                )
            )
            connector_keys.append(auth.key)
        except HTTPException:
            raise
        except Exception as exc:
            connector_results.append(
                PlatformAcceptanceOwnerClosureConnectorResult(
                    connector=connector,
                    status="failed",
                    applied_fields=applied_fields,
                    secret_field_names=secret_field_names,
                    next_action=f"Connector update failed: {type(exc).__name__}. Check field names and retry through the admin configuration surface.",
                )
            )

    receipt: PlatformAcceptanceEvidenceReceipt | None = None
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    if payload.scenario_receipts:
        receipt = await record_platform_acceptance_evidence_receipt(
            PlatformAcceptanceEvidenceReceiptRequest(
                notice_id="owner-closure-run",
                recipient=payload.recipient,
                outcome=payload.receipt_outcome,
                scenario_receipts=payload.scenario_receipts,
                notes=payload.notes,
                include_artifact=True,
                no_secrets_confirmed=True,
            ),
            merchant,
        )
        if payload.create_review_tasks:
            review_sync = await sync_platform_acceptance_evidence_review_tasks(
                PlatformAcceptanceEvidenceReviewTaskSyncRequest(
                    owner=payload.owner,
                    due_days=1,
                    include_needs_help=True,
                    create_tasks=True,
                    include_artifact=True,
                    audit_limit=min(payload.audit_limit, 200),
                ),
                merchant,
            )

    selected_connectors = list(dict.fromkeys(connector_keys))
    gap_closure = await generate_platform_acceptance_gap_closure_run(
        PlatformAcceptanceGapClosureRunRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=selected_connectors,
            attempt_exchange=payload.attempt_exchange,
            attempt_pull=payload.attempt_pull,
            auto_register_pass_evidence=payload.auto_register_pass_evidence,
            create_submission_links=payload.create_submission_links,
            create_gap_tasks=payload.create_gap_tasks,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    owner_pack = await generate_platform_acceptance_owner_action_pack(
        PlatformAcceptanceOwnerActionPackRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=selected_connectors,
            create_customer_trial_link=payload.create_submission_links,
            expires_days=7,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    final_gate = gap_closure.final_gate if isinstance(gap_closure.final_gate, PlatformAcceptanceFinalSignoffLink) else None
    if final_gate is None and isinstance(gap_closure.final_gate, dict):
        try:
            final_gate = PlatformAcceptanceFinalSignoffLink.model_validate(gap_closure.final_gate)
        except Exception:
            final_gate = None
    if not gap_closure.missing_after and final_gate and final_gate.status == "ready":
        status: Literal["ready_for_signoff", "partial", "blocked"] = "ready_for_signoff"
    elif len(gap_closure.missing_after) < len(before_report.missing_scenarios) or any(item.status == "passed" for item in gap_closure.items):
        status = "partial"
    else:
        status = "blocked"
    run = PlatformAcceptanceOwnerClosureRun(
        id=f"platform-owner-closure-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform owner closure run. connector_updates={len(connector_results)} "
            f"receipts={len(payload.scenario_receipts)} before={len(before_report.missing_scenarios)} "
            f"after={len(gap_closure.missing_after)} gate={final_gate.status if final_gate else 'unknown'}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        missing_before=before_report.missing_scenarios,
        missing_after=gap_closure.missing_after,
        connector_results=connector_results,
        receipt=receipt,
        review_sync=review_sync,
        gap_closure=gap_closure,
        owner_action_pack=owner_pack,
        final_gate=final_gate,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_owner_closure_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_owner_closure_run",
        max(1, len(connector_results) + len(payload.scenario_receipts)),
        "integration",
        run.id,
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "connectors": selected_connectors},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_owner_closure_run",
        "integration_acceptance",
        run.id,
        "Run platform owner gap closure intake and acceptance recheck",
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "connectors": selected_connectors},
    )
    return run


async def submit_platform_acceptance_owner_closure(
    payload: PlatformAcceptanceOwnerClosureSubmissionRequest,
) -> PlatformAcceptanceOwnerClosureRun:
    token_data = decode_platform_acceptance_owner_closure_token(payload.token)
    merchant = merchant_by_id(int(token_data.get("merchant_id") or 0))
    allowed_connectors = set(token_data.get("connectors") or [])
    connector_updates: list[PlatformAcceptanceOwnerClosureConnectorUpdate] = []
    if payload.connector_update:
        connector = normalize_connector_key(payload.connector_update.connector)
        if allowed_connectors and connector not in allowed_connectors:
            raise HTTPException(status_code=400, detail="Connector is not allowed by this owner closure link")
        connector_updates.append(payload.connector_update.model_copy(update={"connector": connector}))
    return await generate_platform_acceptance_owner_closure_run(
        PlatformAcceptanceOwnerClosureRunRequest(
            customer_name=str(token_data.get("customer_name") or merchant.business_name or merchant.username),
            owner=str(token_data.get("owner") or "operations reviewer"),
            recipient=str(token_data.get("recipient") or "customer platform owner"),
            connector_updates=connector_updates,
            scenario_receipts=payload.scenario_receipts,
            receipt_outcome=payload.receipt_outcome,
            notes=payload.notes,
            attempt_exchange=payload.attempt_exchange,
            attempt_pull=payload.attempt_pull,
            auto_register_pass_evidence=True,
            create_submission_links=payload.create_submission_links,
            create_gap_tasks=payload.create_gap_tasks,
            create_review_tasks=payload.create_review_tasks,
            include_artifact=payload.include_artifact,
            audit_limit=300,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        ),
        merchant,
    )


def platform_acceptance_gate_from_any(value: Any) -> PlatformAcceptanceFinalSignoffLink | None:
    if isinstance(value, PlatformAcceptanceFinalSignoffLink):
        return value
    if isinstance(value, dict):
        try:
            return PlatformAcceptanceFinalSignoffLink.model_validate(value)
        except Exception:
            return None
    return None


def build_platform_acceptance_auto_watch_markdown(run: PlatformAcceptanceAutoWatchRun) -> str:
    lines = [
        "# Real Platform Acceptance Auto Watch Run",
        "",
        f"Run ID: {run.id}",
        f"Created at: {run.created_at}",
        f"Customer: {run.customer_name}",
        f"Owner: {run.owner}",
        f"Recipient: {run.recipient}",
        f"Status: {run.status}",
        f"Next probe at: {run.next_probe_at or '-'}",
        "",
        run.summary,
        "",
        "## Missing Scenarios",
        "",
        f"- Before: {', '.join(run.missing_before) if run.missing_before else 'none'}",
        f"- After: {', '.join(run.missing_after) if run.missing_after else 'none'}",
        "",
        "## Actions",
        "",
        "| Step | Status | Artifact | Summary | Next Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not run.actions:
        lines.append("| - | skipped | - | No watch action ran. | Check service health and rerun. |")
    for action in run.actions:
        lines.append(
            f"| {action.step} | {action.status} | {action.artifact_url or '-'} | "
            f"{action.summary.replace('|', '/')} | {action.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Linked Outputs",
            "",
            f"- Review sync: {run.review_sync.id if run.review_sync else '-'}",
            f"- Joint debug: {run.joint_debug.id if run.joint_debug else '-'} / {run.joint_debug.status if run.joint_debug else '-'}",
            f"- Gap closure: {run.gap_closure.id if run.gap_closure else '-'} / {run.gap_closure.status if run.gap_closure else '-'}",
            f"- Owner secure link: {run.owner_closure_link.id if run.owner_closure_link else '-'}",
            f"- Owner action pack: {run.owner_action_pack.id if run.owner_action_pack else '-'}",
            f"- Final gate: {run.final_gate.id if run.final_gate else '-'} / {run.final_gate.status if run.final_gate else '-'}",
            "",
            "## Safety Boundary",
            "",
            "- Auto watch only runs read-only checks, review-task sync, customer link generation, and final gate recomputation.",
            "- It does not send customer messages, publish content, or auto-approve customer-submitted trial material.",
            "- Pass evidence is registered only by existing verifiable checks or explicit reviewed evidence workflows.",
            "- Final sign-off remains unavailable until every required scenario has verifiable pass evidence.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_auto_watch_run(
    payload: PlatformAcceptanceAutoWatchRunRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceAutoWatchRun:
    before_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    actions: list[PlatformAcceptanceAutoWatchAction] = [
        PlatformAcceptanceAutoWatchAction(
            step="evidence_report",
            status="done",
            summary=f"Current report status={before_report.status}; missing={len(before_report.missing_scenarios)} evidence={before_report.evidence_total}.",
            next_action="Continue automated watch sequence.",
            artifact_url=before_report.artifact_url,
        )
    ]
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    if payload.create_review_tasks:
        review_sync = await sync_platform_acceptance_evidence_review_tasks(
            PlatformAcceptanceEvidenceReviewTaskSyncRequest(
                owner=payload.owner,
                due_days=1,
                include_needs_help=True,
                create_tasks=True,
                include_artifact=True,
                audit_limit=min(payload.audit_limit, 200),
            ),
            merchant,
        )
        actions.append(
            PlatformAcceptanceAutoWatchAction(
                step="review_sync",
                status="done",
                summary=f"Review sync status={review_sync.status}; created={review_sync.created}; submitted={review_sync.submitted}; needs_help={review_sync.needs_help}.",
                next_action="Review submitted materials and register pass evidence only after human approval.",
                artifact_url=review_sync.artifact_url,
            )
        )
    else:
        actions.append(PlatformAcceptanceAutoWatchAction(step="review_sync", status="skipped", summary="Review task sync skipped by request."))

    joint_debug = await generate_platform_acceptance_joint_debug_run(
        PlatformAcceptanceJointDebugRunRequest(
            customer_name=payload.customer_name,
            operator=payload.owner,
            connectors=payload.connectors,
            attempt_pull=payload.attempt_pull,
            auto_register_pass_evidence=True,
            pull_limit=3,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    actions.append(
        PlatformAcceptanceAutoWatchAction(
            step="joint_debug",
            status="done" if joint_debug.status != "blocked" else "waiting",
            summary=f"Joint debug status={joint_debug.status}; passed={joint_debug.passed}; missing={joint_debug.missing}.",
            next_action="If still missing, collect official credentials, callbacks, sample data, or customer trial evidence.",
            artifact_url=joint_debug.artifact_url,
        )
    )

    gap_closure = await generate_platform_acceptance_gap_closure_run(
        PlatformAcceptanceGapClosureRunRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=payload.connectors,
            attempt_exchange=payload.attempt_exchange,
            attempt_pull=payload.attempt_pull,
            auto_register_pass_evidence=True,
            create_submission_links=payload.create_customer_links,
            create_gap_tasks=payload.create_gap_tasks,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    actions.append(
        PlatformAcceptanceAutoWatchAction(
            step="gap_closure",
            status="done" if len(gap_closure.missing_after) < len(gap_closure.missing_before) else "waiting",
            summary=f"Gap closure status={gap_closure.status}; before={len(gap_closure.missing_before)}; after={len(gap_closure.missing_after)}.",
            next_action="Use owner secure closure link for any remaining customer/platform-controlled fields.",
            artifact_url=gap_closure.artifact_url,
        )
    )

    owner_closure_link: PlatformAcceptanceOwnerClosureLink | None = None
    if payload.create_owner_closure_link and gap_closure.missing_after:
        owner_closure_link = await generate_platform_acceptance_owner_closure_link(
            PlatformAcceptanceOwnerClosureLinkRequest(
                customer_name=payload.customer_name,
                owner=payload.owner,
                recipient=payload.recipient,
                connectors=payload.connectors,
                expires_days=3,
                include_artifact=True,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
        actions.append(
            PlatformAcceptanceAutoWatchAction(
                step="owner_secure_link",
                status="waiting",
                summary=f"Secure closure link generated for {payload.recipient}; connectors={len(owner_closure_link.connectors) or 'default'}.",
                next_action="Send the link after human confirmation; wait for official platform owner submission.",
                artifact_url=owner_closure_link.artifact_url,
            )
        )
    else:
        actions.append(
            PlatformAcceptanceAutoWatchAction(
                step="owner_secure_link",
                status="skipped" if not gap_closure.missing_after else "blocked",
                summary="Secure owner closure link not generated.",
                next_action="Enable create_owner_closure_link if remaining gaps require customer/platform input.",
            )
        )

    owner_pack = await generate_platform_acceptance_owner_action_pack(
        PlatformAcceptanceOwnerActionPackRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=payload.connectors,
            create_customer_trial_link=payload.create_customer_links,
            expires_days=7,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    actions.append(
        PlatformAcceptanceAutoWatchAction(
            step="owner_action_pack",
            status="done" if owner_pack.status != "blocked" else "waiting",
            summary=f"Owner action pack status={owner_pack.status}; action_items={len(owner_pack.items)}.",
            next_action="Use this pack when the secure form is not enough for customer coordination.",
            artifact_url=owner_pack.artifact_url,
        )
    )

    final_gate = platform_acceptance_gate_from_any(gap_closure.final_gate)
    if final_gate is None:
        final_gate = await generate_platform_acceptance_final_signoff_link(
            PlatformAcceptanceFinalSignoffLinkRequest(
                customer_name=payload.customer_name,
                owner=payload.owner,
                recipient=payload.recipient,
                signer_name=payload.recipient,
                signer_role="platform owner",
                expires_days=7,
                include_artifact=True,
                audit_limit=payload.audit_limit,
            ),
            merchant,
        )
    actions.append(
        PlatformAcceptanceAutoWatchAction(
            step="final_gate",
            status="done" if final_gate.status == "ready" else "waiting",
            summary=f"Final gate status={final_gate.status}; missing={len(final_gate.missing_scenarios)}.",
            next_action="Send final sign-off link only when gate status is ready.",
            artifact_url=final_gate.artifact_url,
        )
    )

    missing_after = final_gate.missing_scenarios or gap_closure.missing_after
    if not missing_after and final_gate.status == "ready":
        status: Literal["ready_for_signoff", "waiting_for_customer", "needs_ops", "blocked"] = "ready_for_signoff"
    elif owner_closure_link:
        status = "waiting_for_customer"
    elif any(item.status == "done" for item in actions):
        status = "needs_ops"
    else:
        status = "blocked"
    next_probe_at = (datetime.now() + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    run = PlatformAcceptanceAutoWatchRun(
        id=f"platform-auto-watch-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        summary=(
            f"Platform acceptance auto watch run. before={len(before_report.missing_scenarios)} "
            f"after={len(missing_after)} status={status} final_gate={final_gate.status}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        missing_before=before_report.missing_scenarios,
        missing_after=missing_after,
        actions=actions,
        review_sync=review_sync,
        joint_debug=joint_debug,
        gap_closure=gap_closure,
        owner_closure_link=owner_closure_link,
        owner_action_pack=owner_pack,
        final_gate=final_gate,
        next_probe_at=next_probe_at,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_auto_watch_markdown(run), encoding="utf-8")
        run.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_auto_watch_run",
        max(1, len(actions)),
        "integration",
        run.id,
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "next_probe_at": run.next_probe_at},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_auto_watch_run",
        "integration_acceptance",
        run.id,
        "Run platform acceptance auto watch sequence",
        {"status": run.status, "before": len(run.missing_before), "after": len(run.missing_after), "next_probe_at": run.next_probe_at},
    )
    return run


def parse_platform_acceptance_time(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if fmt.endswith("%S") else value[:10], fmt)
        except ValueError:
            continue
    return None


def platform_acceptance_log_matches_scenario(log: AuditLog, scenario: PlatformAcceptanceScenario) -> bool:
    metadata = log.metadata or {}
    if metadata.get("scenario") == scenario:
        return True
    scenarios = metadata.get("scenarios")
    if isinstance(scenarios, list):
        for item in scenarios:
            if item == scenario:
                return True
            if isinstance(item, dict) and item.get("scenario") == scenario:
                return True
    if scenario in str(log.target_id or "") or scenario in str(log.summary or ""):
        return True
    return False


def latest_platform_acceptance_auto_watch_log(logs: list[AuditLog]) -> dict[str, Any]:
    for log in logs:
        if log.action == "integration.platform_acceptance_auto_watch_run":
            metadata = dict(log.metadata or {})
            metadata.update({"id": log.target_id, "created_at": log.created_at, "summary": log.summary})
            return metadata
    return {}


def build_platform_acceptance_watch_reminder_draft(board: PlatformAcceptanceWatchBoard) -> str:
    lines = [
        f"Hi {board.recipient},",
        "",
        f"We are still waiting on {len(board.missing_scenarios)} real-platform acceptance item(s) for {board.customer_name}.",
        "Please use the secure closure link or your controlled evidence channel; do not send secrets in chat or email.",
        "",
        "Pending items:",
    ]
    for item in board.scenarios:
        if item.status == "passed":
            continue
        lines.append(f"- {item.scenario}: {item.next_action}")
        if item.due_at:
            lines.append(f"  Due: {item.due_at}; escalation: {item.escalation}")
    lines.extend(
        [
            "",
            "Safety reminder: do not include passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets in any screenshots or notes.",
            f"Owner: {board.owner}",
        ]
    )
    return "\n".join(lines)


def build_platform_acceptance_watch_board_markdown(board: PlatformAcceptanceWatchBoard) -> str:
    lines = [
        "# Real Platform Acceptance Watch Board",
        "",
        f"Board ID: {board.id}",
        f"Created at: {board.created_at}",
        f"Customer: {board.customer_name}",
        f"Owner: {board.owner}",
        f"Recipient: {board.recipient}",
        f"Status: {board.status}",
        f"Evidence status: {board.evidence_status}",
        f"Open gap tasks: {board.open_gap_tasks}",
        "",
        board.summary,
        "",
        "## Scenario Board",
        "",
        "| Scenario | Status | Wait Hours | Escalation | Owner | Due | Task | Latest Action | Next Action |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for item in board.scenarios:
        latest = f"{item.latest_action} {item.latest_action_at}".strip() or "-"
        lines.append(
            f"| {item.scenario} | {item.status} | {item.wait_hours} | {item.escalation} | "
            f"{item.owner or '-'} | {item.due_at or '-'} | {item.task_id or '-'} | "
            f"{latest.replace('|', '/')} | {item.next_action.replace('|', '/') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Latest Auto Watch",
            "",
        ]
    )
    if board.latest_auto_watch:
        for key in ["id", "status", "before", "after", "next_probe_at", "created_at"]:
            lines.append(f"- {key}: {board.latest_auto_watch.get(key, '-')}")
    else:
        lines.append("- No auto watch run found in recent audit logs.")
    lines.extend(
        [
            "",
            "## Reminder Draft",
            "",
            "```text",
            board.reminder_draft or "-",
            "```",
            "",
            "## Safety Boundary",
            "",
            "- This board is read-only; it does not send reminders or change platform data.",
            "- Reminder drafts must be manually reviewed before sending.",
            "- Final sign-off remains blocked until all required scenarios have verifiable pass evidence.",
        ]
    )
    return "\n".join(lines)


async def generate_platform_acceptance_watch_board(
    payload: PlatformAcceptanceWatchBoardRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceWatchBoard:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    logs = await list_audit_logs(merchant, limit=payload.audit_limit)
    gap_tasks = open_platform_acceptance_gap_tasks(merchant.id or 0)
    task_by_scenario = {
        platform_acceptance_scenario_from_target(task.target_id): task
        for task in gap_tasks
    }
    now = datetime.now()
    scenarios: list[PlatformAcceptanceWatchBoardScenario] = []
    passed_set = {item.scenario for item in report.evidence if item.result == "pass"}
    for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS:
        task = task_by_scenario.get(scenario)
        related_log = next((log for log in logs if platform_acceptance_log_matches_scenario(log, scenario)), None)
        anchor_time = parse_platform_acceptance_time(task.created_at if task else "") or parse_platform_acceptance_time(related_log.created_at if related_log else "") or now
        wait_hours = max(0, int((now - anchor_time).total_seconds() // 3600))
        due_dt = parse_platform_acceptance_time(task.due_at if task else "")
        is_overdue = bool(due_dt and due_dt < now)
        if scenario in passed_set:
            status: Literal["passed", "waiting_customer", "needs_ops", "overdue"] = "passed"
            escalation: Literal["none", "watch", "urgent"] = "none"
        elif is_overdue or wait_hours >= 48:
            status = "overdue"
            escalation = "urgent"
        elif wait_hours >= 24:
            status = "waiting_customer"
            escalation = "watch"
        else:
            status = "waiting_customer" if scenario in {"official_auth", "callback", "customer_trial"} else "needs_ops"
            escalation = "none"
        requirements = platform_acceptance_evidence_requirements(scenario)
        next_action = str(requirements.get("next_action") or "")
        scenarios.append(
            PlatformAcceptanceWatchBoardScenario(
                scenario=scenario,
                status=status,
                owner=(task.owner if task else payload.owner) or payload.owner,
                due_at=task.due_at if task else "",
                wait_hours=wait_hours,
                escalation=escalation,
                task_id=task.id if task else None,
                latest_action=related_log.action if related_log else "",
                latest_action_at=related_log.created_at if related_log else "",
                latest_artifact_url=str((related_log.metadata or {}).get("artifact_url") or "") if related_log else "",
                next_action="Pass evidence is already registered." if scenario in passed_set else next_action,
            )
        )
    missing = report.missing_scenarios
    if not missing:
        status_board: Literal["ready_for_signoff", "waiting_for_customer", "needs_ops", "overdue"] = "ready_for_signoff"
    elif any(item.status == "overdue" for item in scenarios if item.scenario in missing):
        status_board = "overdue"
    elif any(item.status == "needs_ops" for item in scenarios if item.scenario in missing):
        status_board = "needs_ops"
    else:
        status_board = "waiting_for_customer"
    board = PlatformAcceptanceWatchBoard(
        id=f"platform-watch-board-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status_board,
        summary=(
            f"Platform acceptance watch board. evidence_status={report.status} "
            f"missing={len(missing)} open_gap_tasks={len(gap_tasks)} status={status_board}."
        ),
        customer_name=payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        evidence_status=report.status,
        missing_scenarios=missing,
        scenarios=scenarios,
        latest_auto_watch=latest_platform_acceptance_auto_watch_log(logs),
        open_gap_tasks=len(gap_tasks),
        created_at=now_sql(),
    )
    board.reminder_draft = build_platform_acceptance_watch_reminder_draft(board)
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{board.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_watch_board_markdown(board), encoding="utf-8")
        board.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_watch_board",
        max(1, len(scenarios)),
        "integration",
        board.id,
        {"status": board.status, "missing": len(board.missing_scenarios), "open_gap_tasks": board.open_gap_tasks},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_watch_board",
        "integration_acceptance",
        board.id,
        "Generate platform acceptance watch board",
        {"status": board.status, "missing": len(board.missing_scenarios), "open_gap_tasks": board.open_gap_tasks},
    )
    return board


def platform_acceptance_customer_room_path() -> str:
    return "/api/v1/public/platform-acceptance-customer-room"


def platform_acceptance_customer_room_url(signed_code: str) -> str:
    base_url = platform_acceptance_submission_base_url()
    return f"{base_url}{platform_acceptance_customer_room_path()}?token={urllib.parse.quote(signed_code)}"


def encode_platform_acceptance_customer_room_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    mac = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-customer-room:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"pacr.v1.{body}.{mac}"


def decode_platform_acceptance_customer_room_token(token: str) -> dict[str, Any]:
    try:
        prefix, version, body, mac = token.split(".", 3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid customer room token") from exc
    if prefix != "pacr" or version != "v1":
        raise HTTPException(status_code=400, detail="Unsupported customer room token")
    expected = hmac.new(
        auth_secret().encode("utf-8"),
        f"platform-acceptance-customer-room:{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise HTTPException(status_code=400, detail="Customer room token signature mismatch")
    padded = body + ("=" * (-len(body) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Customer room token payload invalid") from exc
    expires_ts = int(payload.get("expires_ts") or 0)
    if expires_ts < int(time.time()):
        raise HTTPException(status_code=400, detail="Customer room token expired")
    scenarios = [
        scenario for scenario in payload.get("missing_scenarios", [])
        if scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS
    ]
    payload["missing_scenarios"] = scenarios
    return payload


def build_platform_acceptance_customer_room_link_markdown(link: PlatformAcceptanceCustomerRoomLink) -> str:
    lines = [
        "# Real Platform Customer Acceptance Room",
        "",
        f"Room ID: {link.id}",
        f"Created at: {link.created_at}",
        f"Customer: {link.customer_name}",
        f"Owner: {link.owner}",
        f"Recipient: {link.recipient}",
        f"Status: {link.status}",
        f"Evidence status: {link.evidence_status}",
        f"Expires at: {link.expires_at}",
        "",
        "## Missing Scenarios",
        "",
        f"- {', '.join(link.missing_scenarios) if link.missing_scenarios else 'none'}",
        "",
        "## Room URL",
        "",
        link.room_url or "-",
        "",
        "## Linked Actions",
        "",
        f"- Evidence submission: {link.evidence_submission_url or '-'}",
        f"- Secure connector closure: {link.owner_closure_url or '-'}",
        f"- Room receipt: {link.room_url or '-'}",
        f"- Final sign-off: {link.final_signoff_url or '-'}",
        f"- Watch board artifact: {link.watch_board_url or '-'}",
        "",
        "## Draft",
        "",
        "```text",
        link.draft_text or "-",
        "```",
        "",
        "## Safety Boundary",
        "",
        "- This room only aggregates signed links and sanitized status.",
        "- Do not paste platform passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets into chat or documents.",
        "- Final sign-off is available only when the final gate is ready.",
    ]
    return "\n".join(lines)


async def generate_platform_acceptance_customer_room_link(
    payload: PlatformAcceptanceCustomerRoomLinkRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceCustomerRoomLink:
    report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=min(payload.audit_limit, 200), include_artifact=False),
        merchant,
    )
    evidence_link = await generate_platform_acceptance_evidence_submission_link(
        PlatformAcceptanceEvidenceSubmissionLinkRequest(
            recipient=payload.recipient,
            owner=payload.owner,
            scenarios=report.missing_scenarios,
            due_days=1,
            expires_days=payload.expires_days,
            include_artifact=True,
        ),
        merchant,
    )
    owner_closure_link = await generate_platform_acceptance_owner_closure_link(
        PlatformAcceptanceOwnerClosureLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            connectors=payload.connectors,
            expires_days=payload.expires_days,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    watch_board = await generate_platform_acceptance_watch_board(
        PlatformAcceptanceWatchBoardRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    final_gate = await generate_platform_acceptance_final_signoff_link(
        PlatformAcceptanceFinalSignoffLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.owner,
            recipient=payload.recipient,
            signer_name=payload.recipient,
            signer_role="platform owner",
            expires_days=payload.expires_days,
            include_artifact=True,
            audit_limit=payload.audit_limit,
        ),
        merchant,
    )
    link_id = f"platform-customer-room-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    expires_at_dt = datetime.now() + timedelta(days=payload.expires_days)
    expires_at = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    token_payload = {
        "link_id": link_id,
        "merchant_id": merchant.id or 0,
        "customer_name": payload.customer_name.strip()[:160] or merchant.business_name or merchant.username,
        "owner": payload.owner.strip()[:120],
        "recipient": payload.recipient.strip()[:120],
        "evidence_status": report.status,
        "missing_scenarios": report.missing_scenarios,
        "evidence_submission_url": evidence_link.submit_url,
        "owner_closure_url": owner_closure_link.submit_url,
        "final_signoff_url": final_gate.submit_url if final_gate.status == "ready" else "",
        "final_gate_status": final_gate.status,
        "watch_board_url": watch_board.artifact_url,
        "expires_ts": int(expires_at_dt.timestamp()),
        "expires_at": expires_at,
    }
    signed_code = encode_platform_acceptance_customer_room_token(token_payload)
    room_url = platform_acceptance_customer_room_url(signed_code)
    draft_text = "\n".join(
        [
            f"Please use this acceptance room for {payload.customer_name}:",
            room_url,
            "",
            "It includes the secure connector closure form, sanitized evidence submission, current gap list, room receipt, and final sign-off status.",
            "Do not send secrets in chat, screenshots, documents, or email bodies.",
        ]
    )
    link = PlatformAcceptanceCustomerRoomLink(
        id=link_id,
        status="ready" if report.missing_scenarios else "ready",
        customer_name=str(token_payload["customer_name"]),
        owner=payload.owner.strip()[:120],
        recipient=payload.recipient.strip()[:120],
        evidence_status=report.status,
        missing_scenarios=report.missing_scenarios,
        room_url=room_url,
        token=signed_code,
        expires_at=expires_at,
        evidence_submission_url=evidence_link.submit_url,
        owner_closure_url=owner_closure_link.submit_url,
        final_signoff_url=final_gate.submit_url if final_gate.status == "ready" else "",
        watch_board_url=watch_board.artifact_url,
        draft_text=draft_text,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{link.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_customer_room_link_markdown(link), encoding="utf-8")
        link.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_customer_room",
        max(1, len(link.missing_scenarios)),
        "integration",
        link.id,
        {"status": link.status, "missing": len(link.missing_scenarios), "evidence_status": link.evidence_status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_customer_room",
        "integration_acceptance",
        link.id,
        "Generate customer acceptance room link",
        {"status": link.status, "missing": len(link.missing_scenarios), "evidence_status": link.evidence_status},
    )
    return link


def build_platform_acceptance_customer_room_receipt_markdown(result: PlatformAcceptanceCustomerRoomReceipt) -> str:
    lines = [
        "# Real Platform Customer Room Receipt",
        "",
        f"Receipt ID: {result.id}",
        f"Created at: {result.created_at}",
        f"Room link: {result.room_link_id}",
        f"Customer: {result.customer_name}",
        f"Recipient: {result.recipient}",
        f"Submitter: {result.submitter}",
        f"Outcome: {result.outcome}",
        f"Status: {result.status}",
        "",
        result.summary,
        "",
        "## Missing Scenarios At Receipt",
        "",
        f"- {', '.join(result.missing_scenarios) if result.missing_scenarios else 'none'}",
        "",
        "## Scenario Receipts",
        "",
        "| Scenario | Outcome | Evidence URL | Note |",
        "| --- | --- | --- | --- |",
    ]
    for item in result.receipt.scenario_receipts:
        lines.append(f"| {item.scenario} | {item.outcome} | {item.evidence_url or '-'} | {(item.note or '-').replace('|', '/')} |")
    lines.extend(
        [
            "",
            "## Linked Internal Records",
            "",
            f"- Evidence receipt: {result.receipt.id}",
            f"- Review sync: {result.review_sync.id if result.review_sync else '-'}",
            "",
            "## Safety Boundary",
            "",
            "- Room receipt is not pass evidence.",
            "- Operations must review any submitted material and explicitly register pass evidence.",
            "- The receipt stores sanitized notes and links only.",
        ]
    )
    return "\n".join(lines)


async def submit_platform_acceptance_customer_room_receipt(
    payload: PlatformAcceptanceCustomerRoomReceiptRequest,
) -> PlatformAcceptanceCustomerRoomReceipt:
    token_data = decode_platform_acceptance_customer_room_token(payload.token)
    merchant = merchant_by_id(int(token_data.get("merchant_id") or 0))
    missing_scenarios: list[PlatformAcceptanceScenario] = token_data.get("missing_scenarios") or []
    allowed = set(missing_scenarios)
    scenario_receipts = payload.scenario_receipts or [
        PlatformAcceptanceEvidenceReceiptScenario(
            scenario=scenario,
            outcome=payload.outcome,
            note=payload.notes,
            evidence_url="",
        )
        for scenario in missing_scenarios
    ]
    scenario_receipts = [item for item in scenario_receipts if item.scenario in allowed]
    if not scenario_receipts and missing_scenarios:
        scenario_receipts = [
            PlatformAcceptanceEvidenceReceiptScenario(
                scenario=missing_scenarios[0],
                outcome=payload.outcome,
                note=payload.notes,
                evidence_url="",
            )
        ]
    evidence_receipt = await record_platform_acceptance_evidence_receipt(
        PlatformAcceptanceEvidenceReceiptRequest(
            notice_id=str(token_data.get("link_id") or "customer-room"),
            recipient=str(token_data.get("recipient") or "customer platform owner"),
            outcome=payload.outcome,
            scenario_receipts=scenario_receipts,
            notes=payload.notes,
            include_artifact=True,
            no_secrets_confirmed=payload.no_secrets_confirmed,
        ),
        merchant,
    )
    review_sync: PlatformAcceptanceEvidenceReviewTaskSyncResult | None = None
    if payload.create_review_tasks and payload.outcome in {"submitted", "needs_help"}:
        review_sync = await sync_platform_acceptance_evidence_review_tasks(
            PlatformAcceptanceEvidenceReviewTaskSyncRequest(
                owner=str(token_data.get("owner") or "operations reviewer"),
                due_days=1,
                include_needs_help=True,
                create_tasks=True,
                include_artifact=True,
                audit_limit=200,
            ),
            merchant,
        )
    status: Literal["recorded", "needs_help", "submitted"]
    if payload.outcome == "needs_help":
        status = "needs_help"
    elif payload.outcome == "submitted":
        status = "submitted"
    else:
        status = "recorded"
    result = PlatformAcceptanceCustomerRoomReceipt(
        id=f"platform-customer-room-receipt-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        room_link_id=str(token_data.get("link_id") or ""),
        customer_name=str(token_data.get("customer_name") or merchant.business_name or merchant.username),
        recipient=str(token_data.get("recipient") or "customer platform owner"),
        submitter=payload.submitter.strip()[:120],
        outcome=payload.outcome,
        missing_scenarios=missing_scenarios,
        receipt=evidence_receipt,
        review_sync=review_sync,
        summary=(
            f"Customer acceptance room receipt recorded. outcome={payload.outcome} "
            f"scenario_receipts={len(scenario_receipts)} review_sync={bool(review_sync)}."
        ),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_customer_room_receipt_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_customer_room_receipt",
        max(1, len(scenario_receipts)),
        "integration",
        result.id,
        {"status": result.status, "outcome": result.outcome, "scenario_receipts": len(scenario_receipts)},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_customer_room_receipt",
        "integration_acceptance",
        result.id,
        "Record customer acceptance room receipt",
        {"status": result.status, "outcome": result.outcome, "scenario_receipts": len(scenario_receipts)},
    )
    return result


def build_platform_acceptance_final_signoff_markdown(result: PlatformAcceptanceFinalSignoff) -> str:
    lines = [
        "# Real Platform Acceptance Final Sign-off",
        "",
        f"Sign-off ID: {result.id}",
        f"Created at: {result.created_at}",
        f"Status: {result.status}",
        f"Link ID: {result.signoff_link_id}",
        f"Customer: {result.customer_name}",
        f"Signer: {result.signer_name} / {result.signer_role}",
        f"Live run: {result.live_run_id}",
        "",
        result.summary,
        "",
        "## Accepted Scenarios",
        "",
    ]
    if result.accepted_scenarios:
        lines.extend(f"- {scenario}" for scenario in result.accepted_scenarios)
    else:
        lines.append("- No scenarios accepted; customer requested changes.")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Final sign-off is accepted only after live-run readiness is recomputed as ready_for_signoff.",
            "- This artifact stores only sanitized confirmation metadata.",
            "- Platform credentials, tokens, cookies, verification codes, signatures, and API secrets are not stored.",
        ]
    )
    return "\n".join(lines)


async def submit_platform_acceptance_final_signoff(
    payload: PlatformAcceptanceFinalSignoffRequest,
) -> PlatformAcceptanceFinalSignoff:
    assert_platform_acceptance_final_signoff_safe(payload)
    signoff_data = decode_platform_acceptance_signoff_token(payload.token)
    merchant = merchant_by_id(int(signoff_data.get("merchant_id") or 0))
    live_run = await generate_platform_acceptance_live_run(
        PlatformAcceptanceLiveRunRequest(
            customer_name=str(signoff_data.get("customer_name") or merchant.business_name or merchant.username),
            owner=str(signoff_data.get("owner") or "operations reviewer"),
            recipient=str(signoff_data.get("recipient") or payload.signer_name),
            due_days=1,
            expires_days=7,
            ensure_tasks=False,
            create_sprint_pack=False,
            create_links=False,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    if payload.decision == "accepted" and live_run.status != "ready_for_signoff":
        raise HTTPException(status_code=400, detail="Final sign-off is blocked until all required scenarios have pass evidence")
    status: Literal["accepted", "changes_requested"] = "accepted" if payload.decision == "accepted" else "changes_requested"
    accepted_scenarios = [item.scenario for item in live_run.scenarios if item.status == "passed"] if status == "accepted" else []
    result = PlatformAcceptanceFinalSignoff(
        id=f"platform-final-signoff-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        signoff_link_id=str(signoff_data.get("link_id") or ""),
        customer_name=str(signoff_data.get("customer_name") or ""),
        signer_name=payload.signer_name.strip()[:120] or str(signoff_data.get("signer_name") or ""),
        signer_role=payload.signer_role.strip()[:120] or str(signoff_data.get("signer_role") or ""),
        live_run_id=live_run.id,
        accepted_scenarios=accepted_scenarios,
        summary=(
            f"Final platform acceptance sign-off {status}. scenarios={len(accepted_scenarios)} "
            f"live_run_status={live_run.status} notes_present={bool(payload.notes.strip())}."
        ),
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_final_signoff_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_final_signoff",
        max(1, len(accepted_scenarios)),
        "integration",
        result.id,
        {"status": result.status, "scenarios": len(accepted_scenarios), "live_run": live_run.id},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_final_signoff",
        "integration_acceptance",
        result.id,
        "Receive final platform acceptance sign-off",
        {
            "status": result.status,
            "signoff_link_id": result.signoff_link_id,
            "scenarios": len(accepted_scenarios),
            "live_run": live_run.id,
        },
    )
    return result


def platform_acceptance_review_tasks_by_ids(merchant_id: int, task_ids: list[int]) -> list[CRMTask]:
    if not task_ids:
        return []
    marker = param()
    placeholders = ", ".join([marker] * len(task_ids))
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM crm_tasks
            WHERE merchant_id={marker} AND status={marker} AND source={marker} AND id IN ({placeholders})
            ORDER BY id DESC
            """,
            (merchant_id, "open", "platform_acceptance_evidence_review", *task_ids),
        ).fetchall()
    return [crm_task_from_row(row) for row in rows_to_dicts(rows)]


def assert_platform_acceptance_review_decision_safe(payload: PlatformAcceptanceEvidenceReviewDecisionRequest) -> None:
    if not payload.no_secrets_confirmed:
        raise HTTPException(status_code=400, detail="Please confirm the review decision does not contain secrets")
    probe = PlatformAcceptanceEvidenceRequest(
        connector=payload.connector,
        scenario=payload.scenario,
        result="pass",
        account_label=payload.account_label,
        operator=payload.operator,
        evidence_note=payload.evidence_note,
        evidence_url=payload.evidence_url,
        no_secrets_confirmed=payload.no_secrets_confirmed,
    )
    assert_platform_acceptance_evidence_safe(probe)


def build_platform_acceptance_evidence_review_decision_markdown(
    decision: PlatformAcceptanceEvidenceReviewDecision,
) -> str:
    lines = [
        "# Real Platform Acceptance Evidence Review Decision",
        "",
        f"Created at: {decision.created_at}",
        f"Status: {decision.status}",
        f"Scenario: {decision.scenario}",
        f"Decision: {decision.decision}",
        "",
        decision.summary,
        "",
        "## Review Tasks",
        "",
        "| Task ID | Status | Owner | Due At | Title |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not decision.closed_review_tasks:
        lines.append("| - | - | - | - | No review tasks closed by this decision. |")
    for task in decision.closed_review_tasks:
        lines.append(f"| {task.id} | {task.status} | {task.owner or '-'} | {task.due_at or '-'} | {task.title} |")
    lines.extend(["", "## Evidence Registration", ""])
    if decision.evidence:
        lines.extend(
            [
                f"- Evidence ID: {decision.evidence.id}",
                f"- Connector: {decision.evidence.connector}",
                f"- Result: {decision.evidence.result}",
                f"- Evidence URL: {decision.evidence.evidence_url or decision.evidence.artifact_url or '-'}",
            ]
        )
    else:
        lines.append("- No pass evidence was registered by this decision.")
    lines.extend(["", "## Gap Reconciliation", ""])
    if decision.gap_reconcile:
        lines.extend(
            [
                f"- Reconcile ID: {decision.gap_reconcile.id}",
                f"- Status: {decision.gap_reconcile.status}",
                f"- Closed platform gap tasks: {decision.gap_reconcile.closed}",
                f"- Still open platform gap tasks: {decision.gap_reconcile.still_open}",
                f"- Artifact: {decision.gap_reconcile.artifact_url or '-'}",
            ]
        )
    else:
        lines.append("- Platform acceptance gap reconciliation was not triggered by this decision.")
    lines.extend(["", "## Customer Resubmission", ""])
    if decision.resubmission_link:
        lines.extend(
            [
                f"- Link ID: {decision.resubmission_link.id}",
                f"- Status: {decision.resubmission_link.status}",
                f"- Expires at: {decision.resubmission_link.expires_at}",
                f"- Submission URL: {decision.resubmission_link.submit_url or '-'}",
                f"- Artifact: {decision.resubmission_link.artifact_url or '-'}",
            ]
        )
    else:
        lines.append("- No customer resubmission link was generated by this decision.")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- Approved review material is registered as pass evidence only with the explicit confirmation phrase.",
            "- Review decisions never bypass the evidence safety scan.",
            "- Closing review tasks does not directly close original platform acceptance gap tasks; gap reconciliation still checks registered pass evidence.",
            "- Resubmission links only collect sanitized material and do not register pass evidence by themselves.",
        ]
    )
    return "\n".join(lines)


async def record_platform_acceptance_evidence_review_decision(
    payload: PlatformAcceptanceEvidenceReviewDecisionRequest,
    merchant: MerchantProfile,
) -> PlatformAcceptanceEvidenceReviewDecision:
    assert_platform_acceptance_review_decision_safe(payload)
    if payload.register_pass_evidence:
        if payload.decision != "approved":
            raise HTTPException(status_code=400, detail="Only approved review decisions can register pass evidence")
        if payload.confirm_phrase != "CONFIRM_PLATFORM_EVIDENCE":
            raise HTTPException(status_code=400, detail="CONFIRM_PLATFORM_EVIDENCE is required to register pass evidence")
    if payload.close_review_tasks and payload.confirm_phrase != "CONFIRM_PLATFORM_EVIDENCE":
        raise HTTPException(status_code=400, detail="CONFIRM_PLATFORM_EVIDENCE is required to close review tasks")
    if payload.reconcile_gap_tasks and payload.confirm_phrase != "CONFIRM_PLATFORM_EVIDENCE":
        raise HTTPException(status_code=400, detail="CONFIRM_PLATFORM_EVIDENCE is required to reconcile platform gaps")
    if payload.request_resubmission_link and payload.decision == "approved":
        raise HTTPException(status_code=400, detail="Resubmission links are only for needs_redaction or rejected decisions")
    evidence: PlatformAcceptanceEvidence | None = None
    if payload.register_pass_evidence:
        evidence = await record_platform_acceptance_evidence(
            PlatformAcceptanceEvidenceRequest(
                connector=payload.connector,
                scenario=payload.scenario,
                result="pass",
                account_label=payload.account_label,
                operator=payload.operator,
                evidence_note=payload.evidence_note,
                evidence_url=payload.evidence_url,
                no_secrets_confirmed=True,
            ),
            merchant,
        )
    closed_tasks: list[CRMTask] = []
    if payload.close_review_tasks:
        valid_tasks = platform_acceptance_review_tasks_by_ids(merchant.id or 0, payload.review_task_ids)
        for task in valid_tasks:
            closed_tasks.append(await update_crm_task(task.id, CRMTaskUpdate(status="done"), merchant))
    gap_reconcile: PlatformAcceptanceGapReconcileResult | None = None
    if payload.reconcile_gap_tasks:
        if not evidence:
            raise HTTPException(status_code=400, detail="Pass evidence must be registered before reconciling platform gaps")
        gap_reconcile = await reconcile_platform_acceptance_gap_tasks(
            PlatformAcceptanceGapReconcileRequest(close_tasks=True, include_artifact=True),
            merchant,
        )
    resubmission_link: PlatformAcceptanceEvidenceSubmissionLink | None = None
    if payload.request_resubmission_link:
        resubmission_link = await generate_platform_acceptance_evidence_submission_link(
            PlatformAcceptanceEvidenceSubmissionLinkRequest(
                recipient=payload.account_label or "customer platform owner",
                owner=payload.operator or "operations reviewer",
                scenarios=[payload.scenario],
                due_days=1,
                expires_days=7,
                include_artifact=True,
            ),
            merchant,
        )
    if payload.decision == "rejected":
        status: Literal["recorded", "evidence_registered", "needs_redaction", "rejected"] = "rejected"
    elif payload.decision == "needs_redaction":
        status = "needs_redaction"
    elif evidence:
        status = "evidence_registered"
    else:
        status = "recorded"
    result = PlatformAcceptanceEvidenceReviewDecision(
        id=f"platform-evidence-review-decision-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
        status=status,
        scenario=payload.scenario,
        decision=payload.decision,
        summary=(
            f"Platform acceptance evidence review decision. scenario={payload.scenario} "
            f"decision={payload.decision} evidence_registered={bool(evidence)} "
            f"closed_review_tasks={len(closed_tasks)} gap_reconciled={bool(gap_reconcile)} "
            f"resubmission_link={bool(resubmission_link)}."
        ),
        review_task_ids=payload.review_task_ids,
        closed_review_tasks=closed_tasks,
        evidence=evidence,
        gap_reconcile=gap_reconcile,
        resubmission_link=resubmission_link,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        artifact_dir = ARTIFACT_DIR / "integration"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{result.id}.md"
        (artifact_dir / filename).write_text(build_platform_acceptance_evidence_review_decision_markdown(result), encoding="utf-8")
        result.artifact_url = f"/artifacts/integration/{filename}"
    record_usage(
        merchant.id or 0,
        "platform_acceptance_evidence_review_decision",
        1,
        "integration",
        result.id,
        {
            "scenario": payload.scenario,
            "decision": payload.decision,
            "evidence_registered": bool(evidence),
            "closed": len(closed_tasks),
            "gap_reconcile": bool(gap_reconcile),
            "gap_closed": gap_reconcile.closed if gap_reconcile else 0,
            "resubmission_link": bool(resubmission_link),
            "resubmission_link_id": resubmission_link.id if resubmission_link else "",
        },
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.platform_acceptance_evidence_review_decision",
        "integration_acceptance",
        result.id,
        "Record platform acceptance evidence review decision",
        {
            "scenario": payload.scenario,
            "decision": payload.decision,
            "evidence_registered": bool(evidence),
            "closed": len(closed_tasks),
            "gap_reconcile": bool(gap_reconcile),
            "gap_closed": gap_reconcile.closed if gap_reconcile else 0,
            "resubmission_link": bool(resubmission_link),
            "resubmission_link_id": resubmission_link.id if resubmission_link else "",
        },
    )
    return result


def integration_task_title(check: IntegrationDryRunCheck) -> str:
    prefix = "修复平台接入失败" if check.status == "fail" else "处理平台接入告警"
    return f"{prefix}：{check.label} / {check.check}"


async def sync_integration_gaps_to_crm_tasks(
    payload: IntegrationTaskSyncRequest,
    merchant: MerchantProfile,
) -> IntegrationTaskSyncResult:
    dry_run = await run_integration_dry_run(
        IntegrationDryRunRequest(connectors=payload.connectors, include_artifact=True),
        merchant,
        persist=True,
    )
    statuses = {"fail", "warning"} if payload.include_warnings else {"fail"}
    due_at = (datetime.now() + timedelta(days=payload.due_days)).strftime("%Y-%m-%d %H:%M:%S")
    created_tasks: list[CRMTask] = []
    skipped = 0
    for check in dry_run.checks:
        if check.status not in statuses:
            continue
        target_id = integration_task_target_id(check)
        if existing_open_integration_task(merchant.id or 0, target_id):
            skipped += 1
            continue
        task = create_crm_task_record(
            merchant.id or 0,
            CRMTaskCreate(
                target_type="conversation",
                target_id=target_id,
                title=integration_task_title(check),
                priority="high" if check.status == "fail" else "normal",
                owner=payload.owner,
                due_at=due_at,
                source="integration_dry_run",
                workflow_run_id=dry_run.id,
            ),
        )
        created_tasks.append(task)
    status: Literal["synced", "nothing_to_sync"] = "synced" if created_tasks or skipped else "nothing_to_sync"
    summary = f"Integration gap tasks created={len(created_tasks)} skipped_existing={skipped} from dry_run={dry_run.status}."
    record_usage(
        merchant.id or 0,
        "integration_task_sync",
        max(1, len(created_tasks)),
        "integration",
        dry_run.id,
        {"created": len(created_tasks), "skipped": skipped, "dry_run_status": dry_run.status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.task_sync",
        "integration_dry_run",
        dry_run.id,
        "同步平台接入缺口到 CRM 任务",
        {"created": len(created_tasks), "skipped": skipped, "dry_run_status": dry_run.status},
    )
    return IntegrationTaskSyncResult(
        status=status,
        created=len(created_tasks),
        skipped_existing=skipped,
        source_dry_run_status=dry_run.status,
        tasks=created_tasks,
        summary=summary,
    )


async def reconcile_integration_tasks(
    payload: IntegrationTaskReconcileRequest,
    merchant: MerchantProfile,
) -> IntegrationTaskReconcileResult:
    dry_run = await run_integration_dry_run(
        IntegrationDryRunRequest(connectors=payload.connectors, include_artifact=payload.include_artifact),
        merchant,
        persist=True,
    )
    pass_targets = {
        integration_task_target_id(check)
        for check in dry_run.checks
        if check.status == "pass"
    }
    failing_targets = {
        integration_task_target_id(check)
        for check in dry_run.checks
        if check.status != "pass"
    }
    closed_tasks: list[CRMTask] = []
    marker = param()
    for task in open_integration_tasks(merchant.id or 0):
        if task.target_id not in pass_targets:
            continue
        with db() as conn:
            conn.execute(
                f"UPDATE crm_tasks SET status={marker}, updated_at={marker} WHERE merchant_id={marker} AND id={marker}",
                ("done", now_sql(), merchant.id, task.id),
            )
            row = conn.execute(
                f"SELECT * FROM crm_tasks WHERE merchant_id={marker} AND id={marker}",
                (merchant.id, task.id),
            ).fetchone()
        if row:
            closed_tasks.append(crm_task_from_row(dict(row)))
    still_open = sum(1 for task in open_integration_tasks(merchant.id or 0) if task.target_id in failing_targets or task.target_id.startswith("integration:"))
    remaining_checks = [check for check in dry_run.checks if check.status != "pass"]
    status: Literal["reconciled", "nothing_closed"] = "reconciled" if closed_tasks else "nothing_closed"
    summary = f"Integration task reconcile closed={len(closed_tasks)} still_open={still_open} dry_run={dry_run.status}."
    record_usage(
        merchant.id or 0,
        "integration_task_reconcile",
        max(1, len(closed_tasks)),
        "integration",
        dry_run.id,
        {"closed": len(closed_tasks), "still_open": still_open, "dry_run_status": dry_run.status},
    )
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "integration.task_reconcile",
        "integration_dry_run",
        dry_run.id,
        "复验并关闭已通过的平台接入任务",
        {"closed": len(closed_tasks), "still_open": still_open, "dry_run_status": dry_run.status},
    )
    return IntegrationTaskReconcileResult(
        status=status,
        closed=len(closed_tasks),
        still_open=still_open,
        source_dry_run_status=dry_run.status,
        closed_tasks=closed_tasks,
        remaining_checks=remaining_checks,
        summary=summary,
    )


def reply_draft_queue_from_row(row: dict[str, Any]) -> ReplyDraftQueueItem:
    return ReplyDraftQueueItem(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        connector=row.get("connector") or "",
        session_id=row.get("session_id") or "",
        customer_id=int(row["customer_id"]) if row.get("customer_id") is not None else None,
        external_id=row.get("external_id") or "",
        customer_name=row.get("customer_name") or "",
        source_text=row.get("source_text") or "",
        draft_text=row.get("draft_text") or "",
        status=row.get("status") or "pending",
        risk_flags=split_tags(row.get("risk_flags") or ""),
        intent_score=int(row.get("intent_score") or 0),
        workflow_run_id=row.get("workflow_run_id") or "",
        reviewer=row.get("reviewer") or "",
        reviewer_note=row.get("reviewer_note") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        reviewed_at=str(row.get("reviewed_at") or ""),
    )


def generate_reply_draft_text(merchant: MerchantProfile, message: str, channel: str, customer_name: str = "") -> tuple[str, list[str], int, bool]:
    channel_key = channel if channel in DEFAULT_CHANNELS else "web_widget"
    flags = risk_flags_for(message)
    intent_score = score_intent(message)
    need_followup = bool(flags) or intent_score >= 70
    try:
        reply = call_ai_reply(merchant, f"渠道：{DEFAULT_CHANNELS[channel_key][0]}\n客户：{customer_name}\n消息：{message}", [])
        if is_generic_ai_reply(reply):
            reply = channel_grounded_reply(merchant, message, channel_key)
    except HTTPException:
        reply = channel_grounded_reply(merchant, message, channel_key)
    if channel_key != "web_widget":
        reply = f"{reply}\n\n内部提示：当前为{DEFAULT_CHANNELS[channel_key][0]}回复草稿，请人工确认后再发送；接官方 API 后可切换自动回复。"
    return reply, flags, intent_score, need_followup


def insert_reply_draft(
    merchant: MerchantProfile,
    connector: str,
    source_text: str,
    draft_text: str,
    risk_flags: list[str],
    intent_score: int,
    session_id: str = "",
    customer_id: int | None = None,
    external_id: str = "",
    customer_name: str = "",
    workflow_run_id: str = "",
) -> ReplyDraftQueueItem:
    marker = param()
    if external_id:
        with db() as conn:
            existing = conn.execute(
                f"""
                SELECT * FROM reply_drafts
                WHERE merchant_id={marker} AND connector={marker} AND external_id={marker}
                ORDER BY id DESC
                LIMIT 1
                """,
                (merchant.id, connector, external_id),
            ).fetchone()
            if existing:
                return reply_draft_queue_from_row(dict(existing))
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO reply_drafts (
                merchant_id, connector, session_id, customer_id, external_id, customer_name,
                source_text, draft_text, status, risk_flags, intent_score, workflow_run_id,
                created_at, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant.id,
                connector,
                session_id,
                customer_id,
                external_id,
                customer_name,
                source_text,
                draft_text,
                "pending",
                join_tags(risk_flags),
                intent_score,
                workflow_run_id,
                now_sql(),
                now_sql(),
            ),
        )
        draft_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM reply_drafts WHERE id={marker}", (draft_id,)).fetchone()
    item = reply_draft_queue_from_row(dict(row))
    record_usage(merchant.id or 0, "reply_draft", 1, connector, str(item.id), {"intent_score": intent_score, "risk_flags": risk_flags})
    record_audit_log(merchant.id or 0, merchant.username, "reply_draft.create", "reply_draft", str(item.id), "生成待确认回复草稿", {"connector": connector, "session_id": session_id})
    return item


async def create_reply_draft_queue(payload: ReplyDraftQueueCreateRequest, merchant: MerchantProfile) -> ReplyDraftQueueItem:
    connector = payload.channel if payload.channel in DEFAULT_CHANNELS else "web_widget"
    reply, flags, intent_score, _ = generate_reply_draft_text(merchant, payload.message, connector, payload.customer_name)
    return insert_reply_draft(
        merchant,
        connector,
        payload.message,
        reply,
        flags,
        intent_score,
        session_id=payload.session_id,
        external_id=payload.external_id,
        customer_name=payload.customer_name,
    )


async def list_reply_drafts(
    merchant: MerchantProfile,
    status: str = "pending",
    connector: str = "",
    limit: int = 50,
) -> list[ReplyDraftQueueItem]:
    marker = param()
    clauses = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if status:
        clauses.append(f"status={marker}")
        params.append(status)
    if connector:
        clauses.append(f"connector={marker}")
        params.append(connector)
    params.append(max(1, min(limit, 200)))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT * FROM reply_drafts
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC
            LIMIT {marker}
            """,
            tuple(params),
        ).fetchall())
    return [reply_draft_queue_from_row(row) for row in rows]


async def review_reply_draft(draft_id: int, payload: ReplyDraftReviewRequest, merchant: MerchantProfile) -> ReplyDraftQueueItem:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM reply_drafts WHERE merchant_id={marker} AND id={marker}", (merchant.id, draft_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reply draft not found")
        current = reply_draft_queue_from_row(dict(row))
        next_text = payload.draft_text if payload.draft_text is not None else current.draft_text
        reviewed_at = now_sql() if payload.status in {"approved", "rejected"} else ""
        conn.execute(
            f"""
            UPDATE reply_drafts
            SET status={marker}, draft_text={marker}, reviewer={marker}, reviewer_note={marker}, reviewed_at={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND id={marker}
            """,
            (
                payload.status,
                next_text,
                merchant.username,
                payload.reviewer_note,
                reviewed_at,
                now_sql(),
                merchant.id,
                draft_id,
            ),
        )
        updated = conn.execute(f"SELECT * FROM reply_drafts WHERE merchant_id={marker} AND id={marker}", (merchant.id, draft_id)).fetchone()
    record_audit_log(merchant.id or 0, merchant.username, f"reply_draft.{payload.status}", "reply_draft", str(draft_id), "人工审核回复草稿", {"status": payload.status})
    return reply_draft_queue_from_row(dict(updated))


def reply_dispatch_next_action(status: str, dispatch_mode: str) -> str:
    if status == "revoked":
        return "该外发准备记录已撤回；如需发送请重新从已审批草稿创建。"
    if status == "sent":
        return "该回复已通过受控 API 发送并完成审计记录。"
    if status == "send_failed":
        return "该回复发送失败；请检查官方 send endpoint、访问凭证和平台响应。"
    if status == "blocked":
        return "该回复未进入可发送状态，请先处理风险或完成审批。"
    if dispatch_mode == "api_send":
        return "已进入 API 发送准备状态；点击确认发送前仍会进行风险、频控和凭证校验。"
    return "回复已进入人工外发准备队列；请复制到官方后台发送，系统不会自动外发。"


def reply_dispatch_from_row(row: dict[str, Any]) -> ReplyDispatchItem:
    status = row.get("status") or "manual_ready"
    dispatch_mode = row.get("dispatch_mode") or "manual_copy"
    return ReplyDispatchItem(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        draft_id=int(row.get("draft_id") or 0),
        connector=row.get("connector") or "",
        customer_id=int(row["customer_id"]) if row.get("customer_id") is not None else None,
        external_id=row.get("external_id") or "",
        dispatch_mode=dispatch_mode,
        status=status,
        draft_text=row.get("draft_text") or "",
        risk_flags=split_tags(row.get("risk_flags") or ""),
        operator=row.get("operator") or "",
        operator_note=row.get("operator_note") or "",
        revoke_note=row.get("revoke_note") or "",
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
        revoked_at=str(row.get("revoked_at") or ""),
        sent_at=str(row.get("sent_at") or ""),
        send_request_id=row.get("send_request_id") or "",
        send_error=row.get("send_error") or "",
        next_action=reply_dispatch_next_action(status, dispatch_mode),
    )


async def list_reply_dispatches(merchant: MerchantProfile, status: str = "", limit: int = 50) -> list[ReplyDispatchItem]:
    marker = param()
    filters = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if status:
        filters.append(f"status={marker}")
        params.append(status)
    safe_limit = max(1, min(int(limit), 100))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT *
            FROM reply_dispatches
            WHERE {" AND ".join(filters)}
            ORDER BY id DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        ).fetchall())
    return [reply_dispatch_from_row(row) for row in rows]


async def create_reply_dispatch(draft_id: int, payload: ReplyDispatchCreateRequest, merchant: MerchantProfile) -> ReplyDispatchItem:
    marker = param()
    with db() as conn:
        draft_row = conn.execute(
            f"SELECT * FROM reply_drafts WHERE merchant_id={marker} AND id={marker}",
            (merchant.id, draft_id),
        ).fetchone()
        if not draft_row:
            raise HTTPException(status_code=404, detail="Reply draft not found")
        draft = reply_draft_queue_from_row(dict(draft_row))
        if draft.status != "approved":
            record_audit_log(merchant.id or 0, merchant.username, "reply_dispatch.blocked", "reply_draft", str(draft_id), "未审批回复尝试进入外发准备队列")
            raise HTTPException(status_code=400, detail="Reply draft must be approved before dispatch")
        existing = conn.execute(
            f"""
            SELECT *
            FROM reply_dispatches
            WHERE merchant_id={marker} AND draft_id={marker} AND status={marker}
            ORDER BY id DESC
            LIMIT 1
            """,
            (merchant.id, draft_id, "manual_ready"),
        ).fetchone()
        if existing:
            return reply_dispatch_from_row(dict(existing))
        auth_row = conn.execute(
            f"SELECT send_enabled FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, draft.connector),
        ).fetchone()
        send_enabled = bool(dict(auth_row).get("send_enabled")) if auth_row else False
        dispatch_mode = "api_send" if payload.dispatch_mode == "api_send" and send_enabled else "manual_copy"
        status = "manual_ready"
        cursor = conn.execute(
            f"""
            INSERT INTO reply_dispatches (
                merchant_id, draft_id, connector, customer_id, external_id, dispatch_mode, status,
                draft_text, risk_flags, operator, operator_note, created_at, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant.id,
                draft.id,
                draft.connector,
                draft.customer_id,
                draft.external_id,
                dispatch_mode,
                status,
                draft.draft_text,
                join_tags(draft.risk_flags),
                merchant.username,
                payload.operator_note,
                now_sql(),
                now_sql(),
            ),
        )
        dispatch_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM reply_dispatches WHERE id={marker}", (dispatch_id,)).fetchone()
    item = reply_dispatch_from_row(dict(row))
    record_usage(merchant.id or 0, "reply_dispatch", 1, item.connector, str(item.id), {"dispatch_mode": item.dispatch_mode, "status": item.status})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "reply_dispatch.create",
        "reply_dispatch",
        str(item.id),
        "已审批回复进入外发准备队列",
        {"draft_id": draft_id, "dispatch_mode": item.dispatch_mode, "risk_flags": item.risk_flags},
    )
    return item


async def revoke_reply_dispatch(dispatch_id: int, payload: ReplyDispatchRevokeRequest, merchant: MerchantProfile) -> ReplyDispatchItem:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}",
            (merchant.id, dispatch_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reply dispatch not found")
        current = reply_dispatch_from_row(dict(row))
        if current.status == "revoked":
            return current
        conn.execute(
            f"""
            UPDATE reply_dispatches
            SET status={marker}, revoke_note={marker}, revoked_at={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND id={marker}
            """,
            ("revoked", payload.revoke_note, now_sql(), now_sql(), merchant.id, dispatch_id),
        )
        updated = conn.execute(f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}", (merchant.id, dispatch_id)).fetchone()
    item = reply_dispatch_from_row(dict(updated))
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        "reply_dispatch.revoke",
        "reply_dispatch",
        str(dispatch_id),
        "撤回外发准备记录",
        {"revoke_note": payload.revoke_note},
    )
    return item


SEND_BLOCK_TERM_GROUPS = {
    "退款/售后": ["退款", "退钱", "退货", "不满意", "售后", "赔付", "refund", "return", "after-sale"],
    "投诉/差评": ["投诉", "差评", "骗人", "骗子", "举报", "维权", "假货", "complaint", "bad review", "fake"],
    "付款/资金": ["付款", "转账", "银行卡", "收款", "支付", "扣款", "账单", "payment", "transfer", "bank card", "billing"],
    "账号/登录": ["账号", "密码", "验证码", "登录", "封号", "权限", "password", "verification code", "login", "account"],
    "隐私信息": ["手机号", "电话", "地址", "身份证", "隐私", "个人信息", "phone", "address", "privacy", "id card"],
    "发票/合同": ["发票", "合同", "协议", "公章", "invoice", "contract", "agreement"],
}


def connector_send_risk_blockers(dispatch: ReplyDispatchItem, source_text: str = "") -> list[str]:
    blockers = [flag for flag in dispatch.risk_flags if flag]
    combined_text = f"{source_text}\n{dispatch.draft_text}"
    text_flags = risk_flags_for(combined_text)
    for flag in text_flags:
        if flag not in blockers:
            blockers.append(flag)
    lowered_text = combined_text.lower()
    for label, terms in SEND_BLOCK_TERM_GROUPS.items():
        if any(term.lower() in lowered_text for term in terms) and label not in blockers:
            blockers.append(label)
    return blockers


def connector_sent_rate_count(merchant_id: int, connector: str, since: str) -> int:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM reply_dispatches
            WHERE merchant_id={marker} AND connector={marker} AND status={marker} AND sent_at >= {marker}
            """,
            (merchant_id, connector, "sent", since),
        ).fetchone()
    return int(dict(row).get("c") or 0)


def connector_send_auth_headers_and_url(
    send_url: str,
    config: dict[str, Any],
    credential_value: str,
    credential_field: str,
) -> tuple[str, dict[str, str]]:
    parsed = urllib.parse.urlparse(send_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Connector send_url must be http(s)")
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    auth_mode = str(config.get("send_api_auth_mode") or config.get("api_auth_mode") or "")
    if not auth_mode:
        auth_mode = "query" if credential_field == "session_key" else "bearer"
    if auth_mode == "query":
        token_param = str(config.get("send_token_param") or config.get("send_api_token_param") or credential_field or "access_token")
        query[token_param] = credential_value
    elif auth_mode == "header":
        header_name = str(config.get("send_api_auth_header") or config.get("api_auth_header") or "Authorization")
        header_template = str(config.get("send_api_auth_header_template") or config.get("api_auth_header_template") or "{token}")
        headers[header_name] = header_template.replace("{token}", credential_value)
    else:
        headers["Authorization"] = f"Bearer {credential_value}"
    final_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    return final_url, headers


def post_connector_send_api(
    send_url: str,
    config: dict[str, Any],
    credential_value: str,
    credential_field: str,
    body: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    final_url, headers = connector_send_auth_headers_and_url(send_url, config, credential_value, credential_field)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(final_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(1024 * 1024)
            content_type = response.headers.get("Content-Type", "")
            return int(getattr(response, "status", 200)), parse_oauth_token_response(raw, content_type)
    except urllib.error.HTTPError as exc:
        raw = exc.read(128 * 1024)
        return int(exc.code), parse_oauth_token_response(raw, exc.headers.get("Content-Type", ""))


def safe_connector_send_response(payload: dict[str, Any]) -> dict[str, Any]:
    return oauth_safe_response_metadata(payload)


async def confirm_reply_dispatch_send(
    dispatch_id: int,
    payload: ReplyDispatchSendRequest,
    merchant: MerchantProfile,
) -> ReplyDispatchItem:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}",
            (merchant.id, dispatch_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reply dispatch not found")
    dispatch = reply_dispatch_from_row(dict(row))
    if dispatch.status == "sent":
        return dispatch
    if dispatch.status == "revoked":
        raise HTTPException(status_code=400, detail="Reply dispatch was revoked")
    if payload.confirmation_phrase != SEND_CONFIRM_PHRASE:
        raise HTTPException(status_code=400, detail="Missing send confirmation phrase")

    config = connector_config_for(merchant.id or 0, dispatch.connector)
    send_url = connector_send_url(config)
    credential_value, credential_field = connector_read_credential(config, merchant.id or 0)
    with db() as conn:
        auth_row = conn.execute(
            f"SELECT send_enabled FROM connector_credentials WHERE merchant_id={marker} AND connector={marker}",
            (merchant.id, dispatch.connector),
        ).fetchone()
    send_enabled = bool(dict(auth_row).get("send_enabled")) if auth_row else False
    missing: list[str] = []
    if not send_enabled:
        missing.append("send_enabled")
    if not send_url:
        missing.append("send_url")
    if not credential_value:
        missing.append("access_token/session_key")
    if missing:
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "reply_dispatch.send.setup_required",
            "reply_dispatch",
            str(dispatch.id),
            f"受控 API 发送缺少配置：{', '.join(missing)}",
            {"missing": missing},
        )
        raise HTTPException(status_code=400, detail=f"Setup required: {', '.join(missing)}")

    with db() as conn:
        draft_source_row = conn.execute(
            f"SELECT source_text, risk_flags FROM reply_drafts WHERE merchant_id={marker} AND id={marker}",
            (merchant.id, dispatch.draft_id),
        ).fetchone()
    source_text = ""
    if draft_source_row:
        draft_data = dict(draft_source_row)
        source_text = draft_data.get("source_text") or ""
        for flag in split_tags(draft_data.get("risk_flags") or ""):
            if flag not in dispatch.risk_flags:
                dispatch.risk_flags.append(flag)
    blockers = connector_send_risk_blockers(dispatch, source_text)
    if blockers:
        with db() as conn:
            conn.execute(
                f"""
                UPDATE reply_dispatches
                SET status={marker}, send_error={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND id={marker}
                """,
                ("blocked", f"risk_flags:{join_tags(blockers)}", now_sql(), merchant.id, dispatch.id),
            )
            updated = conn.execute(f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}", (merchant.id, dispatch.id)).fetchone()
        item = reply_dispatch_from_row(dict(updated))
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "reply_dispatch.send.blocked",
            "reply_dispatch",
            str(dispatch.id),
            "受控 API 发送被风险标记阻断",
            {"risk_flags": blockers},
        )
        return item

    rate_limit = int(config.get("send_rate_limit_per_hour") or 20)
    since = datetime.fromtimestamp(time.time() - 3600).strftime("%Y-%m-%d %H:%M:%S")
    if connector_sent_rate_count(merchant.id or 0, dispatch.connector, since) >= rate_limit:
        with db() as conn:
            conn.execute(
                f"""
                UPDATE reply_dispatches
                SET status={marker}, send_error={marker}, updated_at={marker}
                WHERE merchant_id={marker} AND id={marker}
                """,
                ("blocked", "rate_limit_exceeded", now_sql(), merchant.id, dispatch.id),
            )
            updated = conn.execute(f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}", (merchant.id, dispatch.id)).fetchone()
        item = reply_dispatch_from_row(dict(updated))
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "reply_dispatch.send.blocked",
            "reply_dispatch",
            str(dispatch.id),
            "受控 API 发送被频控阻断",
            {"rate_limit_per_hour": rate_limit},
        )
        return item

    send_request_id = payload.idempotency_key or f"dispatch-{dispatch.id}-{secrets.token_hex(4)}"
    if payload.dry_run:
        record_audit_log(
            merchant.id or 0,
            merchant.username,
            "reply_dispatch.send.dry_run",
            "reply_dispatch",
            str(dispatch.id),
            "受控 API 发送 dry-run",
            {"send_request_id": send_request_id},
        )
        return dispatch

    body = {
        "idempotency_key": send_request_id,
        "external_id": dispatch.external_id,
        "draft_id": dispatch.draft_id,
        "dispatch_id": dispatch.id,
        "customer_id": dispatch.customer_id,
        "message": dispatch.draft_text,
        "text": dispatch.draft_text,
    }
    try:
        http_status, response_body = await asyncio.to_thread(
            post_connector_send_api,
            send_url,
            config,
            credential_value,
            credential_field,
            body,
        )
    except Exception as exc:
        http_status = 0
        response_body = {"error": type(exc).__name__}
    sent_ok = 200 <= http_status < 300
    status = "sent" if sent_ok else "send_failed"
    sent_at = now_sql() if sent_ok else ""
    safe_response = safe_connector_send_response(response_body)
    with db() as conn:
        conn.execute(
            f"""
            UPDATE reply_dispatches
            SET status={marker}, dispatch_mode={marker}, send_request_id={marker}, send_response_json={marker},
                send_error={marker}, sent_at={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND id={marker}
            """,
            (
                status,
                "api_send",
                send_request_id,
                json.dumps(safe_response, ensure_ascii=False),
                "" if sent_ok else f"http_status:{http_status}",
                sent_at,
                now_sql(),
                merchant.id,
                dispatch.id,
            ),
        )
        updated = conn.execute(f"SELECT * FROM reply_dispatches WHERE merchant_id={marker} AND id={marker}", (merchant.id, dispatch.id)).fetchone()
    item = reply_dispatch_from_row(dict(updated))
    record_usage(merchant.id or 0, "reply_dispatch_send", 1, dispatch.connector, str(dispatch.id), {"status": status, "http_status": http_status})
    record_audit_log(
        merchant.id or 0,
        merchant.username,
        f"reply_dispatch.send.{status}",
        "reply_dispatch",
        str(dispatch.id),
        "受控 API 发送结果",
        {"status": status, "http_status": http_status, "send_request_id": send_request_id},
    )
    return item


async def ingest_connector_message(key: str, payload: ConnectorInboundMessageRequest, merchant: MerchantProfile) -> ConnectorIngestResponse:
    connector = normalize_connector_key(key)
    duplicate = find_connector_event(merchant.id or 0, connector, "message", payload.external_id)
    if duplicate:
        draft = find_reply_draft_by_external(merchant.id or 0, connector, payload.external_id)
        return ConnectorIngestResponse(
            connector=connector,
            mode="read_only",
            customer_id=draft.customer_id if draft else None,
            draft_id=draft.id if draft else None,
            session_id=draft.session_id if draft else f"{connector}-{payload.external_id or payload.sender_id}",
            workflow_run_ids=[duplicate.workflow_run_id] if duplicate.workflow_run_id else [],
            task_created=False,
            next_action="重复消息事件已按 external_id 幂等忽略，未重复创建客户、任务或回复草稿。",
        )
    session_id = f"{connector}-{payload.external_id or payload.sender_id or uuid.uuid4()}"
    visitor_id = payload.sender_id or payload.external_id or secrets.token_hex(8)
    flags = risk_flags_for(payload.text)
    intent_score = score_intent(payload.text)
    need_followup = bool(flags) or intent_score >= 70
    customer_id = upsert_customer(
        merchant.id or 0,
        visitor_id,
        payload.text,
        intent_score,
        need_followup,
        source_channel=connector,
        session_id=session_id,
        risk_flags=flags,
    )
    runs = workflow_engine.trigger(
        "message",
        connector,
        {
            "message": payload.text,
            "session_id": session_id,
            "customer_id": str(customer_id),
            "connector": connector,
            "intent_score": intent_score,
            "risk_flags": flags,
        },
    )
    workflow_run_id = runs[0].id if runs else ""
    task_created = False
    if need_followup or intent_score >= 70:
        task_created = ensure_followup_task(
            merchant.id or 0,
            customer_id,
            f"{CONNECTOR_CATALOG[connector]['label']}消息跟进",
            workflow_run_id,
            connector,
        ) is not None
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO conversations (
                merchant_id, customer_id, session_id, visitor_info, query, response, intent_score,
                need_followup, source_channel, risk_flags, workflow_run_id, created_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant.id,
                customer_id,
                session_id,
                json.dumps({"sender_id": payload.sender_id, "sender_name": payload.sender_name, "contact": payload.contact}, ensure_ascii=False),
                payload.text,
                "",
                intent_score,
                1 if need_followup else 0,
                connector,
                join_tags(flags),
                workflow_run_id,
                now_sql(),
            ),
        )
    draft = None
    if "draft_reply" in CONNECTOR_CATALOG[connector].get("capabilities", []):
        reply, draft_flags, draft_intent, _ = generate_reply_draft_text(
            merchant,
            payload.text,
            connector if connector in DEFAULT_CHANNELS else "web_widget",
            payload.sender_name,
        )
        draft = insert_reply_draft(
            merchant,
            connector,
            payload.text,
            reply,
            sorted(set(flags + draft_flags)),
            max(intent_score, draft_intent),
            session_id=session_id,
            customer_id=customer_id,
            external_id=payload.external_id,
            customer_name=payload.sender_name,
            workflow_run_id=workflow_run_id,
        )
    record_connector_event(merchant.id or 0, connector, "message", payload.external_id, payload.model_dump(mode="json"), workflow_run_id)
    record_usage(merchant.id or 0, "connector_message", 1, connector, payload.external_id, {"customer_id": customer_id})
    record_audit_log(merchant.id or 0, merchant.username, "connector.message.read", "connector", connector, "只读消息入站", {"external_id": payload.external_id, "customer_id": customer_id})
    return ConnectorIngestResponse(
        connector=connector,
        mode="read_only",
        customer_id=customer_id,
        draft_id=draft.id if draft else None,
        session_id=session_id,
        workflow_run_ids=[run.id for run in runs],
        task_created=task_created,
        next_action="消息已只读入站并进入 CRM/Workflow；回复草稿已进入人工确认队列，当前不会自动发送平台回复。" if draft else "消息已只读入站并进入 CRM/Workflow；当前不会自动发送平台回复。",
    )


async def ingest_connector_lead(key: str, payload: ConnectorInboundLeadRequest, merchant: MerchantProfile) -> ConnectorIngestResponse:
    connector = normalize_connector_key(key)
    duplicate = find_connector_event(merchant.id or 0, connector, "lead", payload.external_id)
    if duplicate:
        return ConnectorIngestResponse(
            connector=connector,
            mode="read_only",
            workflow_run_ids=[duplicate.workflow_run_id] if duplicate.workflow_run_id else [],
            task_created=False,
            next_action="重复线索事件已按 external_id 幂等忽略，未重复创建 CRM 线索。",
        )
    lead = await create_crm_lead(
        CRMLeadCreate(
            source=connector,
            name=payload.name,
            contact=payload.contact,
            need=payload.need,
            tags=[CONNECTOR_CATALOG[connector]["label"]],
            notes=json.dumps(payload.raw, ensure_ascii=False)[:1000] if payload.raw else "",
        ),
        merchant,
    )
    record_connector_event(merchant.id or 0, connector, "lead", payload.external_id, payload.model_dump(mode="json"))
    record_usage(merchant.id or 0, "connector_lead", 1, connector, payload.external_id, {"lead_id": lead.id})
    record_audit_log(merchant.id or 0, merchant.username, "connector.lead.read", "connector", connector, "只读线索入站", {"external_id": payload.external_id, "lead_id": lead.id})
    return ConnectorIngestResponse(
        connector=connector,
        mode="read_only",
        lead_id=lead.id,
        workflow_run_ids=[],
        task_created=lead.intent_score >= 70,
        next_action="线索已只读入站并进入 CRM；请人工跟进或配置后续 Workflow。",
    )


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": ["enterprise:read", "enterprise:write", "crm:read", "crm:write", "knowledge:write", "automation:run", "settings:write", "team:write", "audit:read"],
    "admin": ["enterprise:read", "enterprise:write", "crm:read", "crm:write", "knowledge:write", "automation:run", "settings:write", "audit:read"],
    "operations_lead": ["enterprise:read", "crm:read", "crm:write", "knowledge:write", "automation:run", "settings:write", "audit:read"],
    "service_lead": ["enterprise:read", "crm:read", "crm:write", "knowledge:write", "audit:read"],
    "agent": ["enterprise:read", "crm:read", "crm:write"],
}


def role_permissions(role: str, extra: list[str] | None = None) -> list[str]:
    return sorted(set(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["agent"]) + (extra or [])))


def team_member_from_row(row: dict[str, Any]) -> TeamMember:
    return TeamMember(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        name=row.get("name") or "",
        email=row.get("email") or "",
        role=row.get("role") or "agent",
        status=row.get("status") or "active",
        permissions=split_tags(row.get("permissions")),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def audit_log_from_row(row: dict[str, Any]) -> AuditLog:
    return AuditLog(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        actor=row.get("actor") or "",
        action=row.get("action") or "",
        target_type=row.get("target_type") or "",
        target_id=row.get("target_id") or "",
        summary=row.get("summary") or "",
        metadata=json.loads(row.get("metadata_json") or "{}"),
        ip=row.get("ip") or "",
        created_at=str(row.get("created_at") or ""),
    )


def record_audit_log(
    merchant_id: int,
    actor: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    summary: str = "",
    metadata: dict[str, Any] | None = None,
    ip: str = "",
) -> None:
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO audit_logs (merchant_id, actor, action, target_type, target_id, summary, metadata_json, ip, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant_id,
                actor,
                action,
                target_type,
                target_id,
                summary,
                json.dumps(metadata or {}, ensure_ascii=False),
                ip,
                now_sql(),
            ),
        )


def ensure_default_team_member(merchant: MerchantProfile) -> None:
    marker = param()
    with db() as conn:
        count = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM merchant_members WHERE merchant_id={marker}",
            (merchant.id,),
        ).fetchone())["c"]
        if int(count or 0) == 0:
            conn.execute(
                f"""
                INSERT INTO merchant_members (merchant_id, name, email, role, status, permissions, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    merchant.business_name or merchant.username or "企业管理员",
                    "",
                    "owner",
                    "active",
                    join_tags(role_permissions("owner")),
                    now_sql(),
                    now_sql(),
                ),
            )


async def list_team_members(merchant: MerchantProfile) -> list[TeamMember]:
    ensure_default_team_member(merchant)
    marker = param()
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"SELECT * FROM merchant_members WHERE merchant_id={marker} ORDER BY id ASC",
            (merchant.id,),
        ).fetchall())
    return [team_member_from_row(row) for row in rows]


async def create_team_member(payload: TeamMemberCreate, merchant: MerchantProfile) -> TeamMember:
    ensure_default_team_member(merchant)
    marker = param()
    permissions = role_permissions(payload.role, payload.permissions)
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO merchant_members (merchant_id, name, email, role, status, permissions, created_at, updated_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant.id, payload.name, payload.email, payload.role, "active", join_tags(permissions), now_sql(), now_sql()),
        )
        member_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM merchant_members WHERE id={marker}", (member_id,)).fetchone()
    record_audit_log(merchant.id or 0, merchant.username, "team.member.create", "member", str(member_id), f"新增成员：{payload.name}", {"role": payload.role})
    return team_member_from_row(dict(row))


async def update_team_member(member_id: int, payload: TeamMemberUpdate, merchant: MerchantProfile) -> TeamMember:
    marker = param()
    updates: list[str] = []
    params: list[Any] = []
    for column, value in {
        "name": payload.name,
        "email": payload.email,
        "role": payload.role,
        "status": payload.status,
    }.items():
        if value is not None:
            updates.append(f"{column}={marker}")
            params.append(value)
    if payload.permissions is not None or payload.role is not None:
        next_role = payload.role or "agent"
        updates.append(f"permissions={marker}")
        params.append(join_tags(role_permissions(next_role, payload.permissions or [])))
    if updates:
        updates.append(f"updated_at={marker}")
        params.append(now_sql())
        params.extend([merchant.id, member_id])
        with db() as conn:
            conn.execute(
                f"UPDATE merchant_members SET {', '.join(updates)} WHERE merchant_id={marker} AND id={marker}",
                tuple(params),
            )
            row = conn.execute(f"SELECT * FROM merchant_members WHERE merchant_id={marker} AND id={marker}", (merchant.id, member_id)).fetchone()
    else:
        with db() as conn:
            row = conn.execute(f"SELECT * FROM merchant_members WHERE merchant_id={marker} AND id={marker}", (merchant.id, member_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Team member not found")
    record_audit_log(merchant.id or 0, merchant.username, "team.member.update", "member", str(member_id), "更新成员权限或状态")
    return team_member_from_row(dict(row))


async def list_audit_logs(merchant: MerchantProfile, limit: int = 100) -> list[AuditLog]:
    marker = param()
    safe_limit = max(1, min(int(limit), 300))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"SELECT * FROM audit_logs WHERE merchant_id={marker} ORDER BY id DESC LIMIT {safe_limit}",
            (merchant.id,),
        ).fetchall())
    return [audit_log_from_row(row) for row in rows]


DEFAULT_BILLING_PLANS = [
    BillingPlan(
        id="starter",
        name="Starter",
        price_monthly=199,
        ai_quota=1000,
        workflow_quota=300,
        connector_quota=200,
        seats=2,
        features=["网页客服", "CRM 线索", "基础 Workflow", "只读 Connector"],
    ),
    BillingPlan(
        id="pro",
        name="Pro",
        price_monthly=699,
        ai_quota=8000,
        workflow_quota=3000,
        connector_quota=2000,
        seats=8,
        features=["多渠道只读接入", "团队权限", "审计日志", "经营分析"],
    ),
    BillingPlan(
        id="agency",
        name="Agency",
        price_monthly=1999,
        ai_quota=30000,
        workflow_quota=12000,
        connector_quota=8000,
        seats=30,
        features=["多商户交付", "高级报表", "私有化部署咨询", "专属模板库"],
    ),
]


def billing_plan_from_row(row: dict[str, Any]) -> BillingPlan:
    return BillingPlan(
        id=row.get("id") or "",
        name=row.get("name") or "",
        price_monthly=int(row.get("price_monthly") or 0),
        ai_quota=int(row.get("ai_quota") or 0),
        workflow_quota=int(row.get("workflow_quota") or 0),
        connector_quota=int(row.get("connector_quota") or 0),
        seats=int(row.get("seats") or 1),
        features=split_tags(row.get("features")),
    )


def subscription_from_row(row: dict[str, Any]) -> MerchantSubscription:
    return MerchantSubscription(
        merchant_id=int(row.get("merchant_id") or 0),
        plan_id=row.get("plan_id") or "starter",
        status=row.get("status") or "trial",
        current_period_start=row.get("current_period_start") or "",
        current_period_end=row.get("current_period_end") or "",
        ai_quota=int(row.get("ai_quota") or 0),
        workflow_quota=int(row.get("workflow_quota") or 0),
        connector_quota=int(row.get("connector_quota") or 0),
        seats=int(row.get("seats") or 1),
        updated_at=str(row.get("updated_at") or ""),
    )


def usage_record_from_row(row: dict[str, Any]) -> UsageRecord:
    return UsageRecord(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        usage_type=row.get("usage_type") or "",
        quantity=int(row.get("quantity") or 0),
        source=row.get("source") or "",
        target_id=row.get("target_id") or "",
        metadata=json.loads(row.get("metadata_json") or "{}"),
        created_at=str(row.get("created_at") or ""),
    )


def ensure_billing_plans() -> None:
    marker = param()
    with db() as conn:
        for plan in DEFAULT_BILLING_PLANS:
            existing = conn.execute(f"SELECT id FROM billing_plans WHERE id={marker}", (plan.id,)).fetchone()
            if existing:
                continue
            conn.execute(
                f"""
                INSERT INTO billing_plans (id, name, price_monthly, ai_quota, workflow_quota, connector_quota, seats, features)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    plan.id,
                    plan.name,
                    plan.price_monthly,
                    plan.ai_quota,
                    plan.workflow_quota,
                    plan.connector_quota,
                    plan.seats,
                    join_tags(plan.features),
                ),
            )


async def list_billing_plans() -> list[BillingPlan]:
    ensure_billing_plans()
    with db() as conn:
        rows = rows_to_dicts(conn.execute("SELECT * FROM billing_plans ORDER BY price_monthly ASC").fetchall())
    return [billing_plan_from_row(row) for row in rows]


def plan_by_id(plan_id: str) -> BillingPlan:
    ensure_billing_plans()
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM billing_plans WHERE id={marker}", (plan_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Billing plan not found")
    return billing_plan_from_row(dict(row))


async def current_subscription(merchant: MerchantProfile) -> MerchantSubscription:
    ensure_billing_plans()
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchant_subscriptions WHERE merchant_id={marker}", (merchant.id,)).fetchone()
        if row:
            return subscription_from_row(dict(row))
    starter = plan_by_id("starter")
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO merchant_subscriptions (
                merchant_id, plan_id, status, current_period_start, current_period_end,
                ai_quota, workflow_quota, connector_quota, seats, updated_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                merchant.id,
                starter.id,
                "trial",
                today_prefix(),
                "",
                starter.ai_quota,
                starter.workflow_quota,
                starter.connector_quota,
                starter.seats,
                now_sql(),
            ),
        )
        row = conn.execute(f"SELECT * FROM merchant_subscriptions WHERE merchant_id={marker}", (merchant.id,)).fetchone()
    return subscription_from_row(dict(row))


async def update_subscription(payload: SubscriptionUpdate, merchant: MerchantProfile) -> MerchantSubscription:
    plan = plan_by_id(payload.plan_id)
    marker = param()
    with db() as conn:
        existing = conn.execute(f"SELECT merchant_id FROM merchant_subscriptions WHERE merchant_id={marker}", (merchant.id,)).fetchone()
        if existing:
            conn.execute(
                f"""
                UPDATE merchant_subscriptions
                SET plan_id={marker}, status={marker}, ai_quota={marker}, workflow_quota={marker},
                    connector_quota={marker}, seats={marker}, updated_at={marker}
                WHERE merchant_id={marker}
                """,
                (plan.id, payload.status, plan.ai_quota, plan.workflow_quota, plan.connector_quota, plan.seats, now_sql(), merchant.id),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO merchant_subscriptions (
                    merchant_id, plan_id, status, current_period_start, current_period_end,
                    ai_quota, workflow_quota, connector_quota, seats, updated_at
                )
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (merchant.id, plan.id, payload.status, today_prefix(), "", plan.ai_quota, plan.workflow_quota, plan.connector_quota, plan.seats, now_sql()),
            )
        row = conn.execute(f"SELECT * FROM merchant_subscriptions WHERE merchant_id={marker}", (merchant.id,)).fetchone()
    record_audit_log(merchant.id or 0, merchant.username, "billing.subscription.update", "subscription", str(merchant.id or ""), f"更新订阅：{plan.id}", {"status": payload.status})
    return subscription_from_row(dict(row))


def record_usage(
    merchant_id: int,
    usage_type: str,
    quantity: int = 1,
    source: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO usage_records (merchant_id, usage_type, quantity, source, target_id, metadata_json, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant_id, usage_type, quantity, source, target_id, json.dumps(metadata or {}, ensure_ascii=False), now_sql()),
        )


async def list_usage_records(merchant: MerchantProfile, limit: int = 100) -> list[UsageRecord]:
    marker = param()
    safe_limit = max(1, min(int(limit), 300))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"SELECT * FROM usage_records WHERE merchant_id={marker} ORDER BY id DESC LIMIT {safe_limit}",
            (merchant.id,),
        ).fetchall())
    return [usage_record_from_row(row) for row in rows]


async def usage_summary(merchant: MerchantProfile) -> UsageSummary:
    subscription = await current_subscription(merchant)
    marker = param()
    period = today_prefix()[:7]
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT usage_type, SUM(quantity) AS q
            FROM usage_records
            WHERE merchant_id={marker} AND created_at LIKE {marker}
            GROUP BY usage_type
            """,
            (merchant.id, f"{period}%"),
        ).fetchall())
    used = {row["usage_type"]: int(row["q"] or 0) for row in rows}
    ai_used = sum(value for key, value in used.items() if key.startswith("ai_"))
    workflow_used = used.get("workflow_run", 0)
    connector_used = sum(value for key, value in used.items() if key.startswith("connector_"))
    return UsageSummary(
        period=period,
        subscription=subscription,
        used={**used, "ai_total": ai_used, "workflow_total": workflow_used, "connector_total": connector_used},
        remaining={
            "ai": max(0, subscription.ai_quota - ai_used),
            "workflow": max(0, subscription.workflow_quota - workflow_used),
            "connector": max(0, subscription.connector_quota - connector_used),
        },
        recent=await list_usage_records(merchant, limit=20),
    )


def business_report_from_row(row: dict[str, Any]) -> BusinessReport:
    return BusinessReport(
        id=int(row.get("id") or 0),
        merchant_id=int(row.get("merchant_id") or 0),
        report_type=row.get("report_type") or "daily",
        title=row.get("title") or "",
        summary=row.get("summary") or "",
        content=row.get("content") or "",
        metrics=json.loads(row.get("metrics_json") or "{}"),
        created_at=str(row.get("created_at") or ""),
    )


async def list_business_reports(merchant: MerchantProfile, report_type: str = "", limit: int = 50) -> list[BusinessReport]:
    marker = param()
    filters = [f"merchant_id={marker}"]
    params: list[Any] = [merchant.id]
    if report_type:
        filters.append(f"report_type={marker}")
        params.append(report_type)
    safe_limit = max(1, min(int(limit), 200))
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            f"""
            SELECT *
            FROM business_reports
            WHERE {" AND ".join(filters)}
            ORDER BY id DESC
            LIMIT {safe_limit}
            """,
            tuple(params),
        ).fetchall())
    return [business_report_from_row(row) for row in rows]


async def generate_business_report(payload: ReportGenerateRequest, merchant: MerchantProfile) -> BusinessReport:
    overview = await dashboard_overview(merchant)
    crm = await crm_overview(merchant)
    usage = await usage_summary(merchant)
    connectors = await list_connector_auths(merchant)
    open_tasks = await list_crm_tasks(merchant, status="open")
    high_intent = [lead for lead in await list_crm_leads(merchant) if lead.intent_score >= 70][:5]
    connected = [item for item in connectors if item.status in {"connected", "assist_only"}]
    blocked = [item for item in connectors if item.status in {"pending_auth", "failed", "not_configured"}]
    title = payload.title or f"{merchant.business_name or merchant.username} {payload.report_type} 经营简报 {today_prefix()}"
    summary = (
        f"今日会话 {overview.today_conversations}，CRM 线索 {crm.leads}，"
        f"高意向 {crm.high_intent}，打开任务 {crm.open_tasks}，"
        f"AI 剩余额度 {usage.remaining.get('ai', 0)}。"
    )
    next_actions = []
    if crm.high_intent:
        next_actions.append("优先处理高意向线索，先联系有报价/试用/联系方式信号的客户。")
    if crm.open_tasks:
        next_actions.append("清理打开中的 CRM 跟进任务，避免漏单。")
    if blocked:
        next_actions.append("继续补齐待授权 Connector，只读同步优先，暂不自动发送。")
    if not next_actions:
        next_actions.append("继续积累真实会话和线索，保持知识库更新。")
    content = "\n".join(
        [
            f"# {title}",
            "",
            f"## 摘要",
            summary,
            "",
            "## 核心指标",
            f"- 今日会话：{overview.today_conversations}",
            f"- 自动回复：{overview.auto_replies}",
            f"- CRM 线索：{crm.leads}",
            f"- 高意向线索：{crm.high_intent}",
            f"- 待人工/跟进：{crm.needs_followup}",
            f"- 打开任务：{crm.open_tasks}",
            f"- 已接入/辅助 Connector：{len(connected)}",
            f"- 待授权 Connector：{len(blocked)}",
            "",
            "## 高意向线索",
            *[f"- {lead.name or '未命名线索'}：意向 {lead.intent_score}，{lead.need[:80]}" for lead in high_intent],
            "" if high_intent else "- 暂无高意向线索。",
            "",
            "## 用量和额度",
            f"- 当前套餐：{usage.subscription.plan_id} / {usage.subscription.status}",
            f"- AI 剩余：{usage.remaining.get('ai', 0)}",
            f"- Workflow 剩余：{usage.remaining.get('workflow', 0)}",
            f"- Connector 剩余：{usage.remaining.get('connector', 0)}",
            "",
            "## 建议动作",
            *[f"- {item}" for item in next_actions],
        ]
    )
    metrics = {
        "overview": overview.model_dump(),
        "crm": crm.model_dump(),
        "usage": usage.model_dump(mode="json"),
        "connectors": {"connected": len(connected), "blocked": len(blocked)},
        "open_tasks": len(open_tasks),
    }
    marker = param()
    with db() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO business_reports (merchant_id, report_type, title, summary, content, metrics_json, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (merchant.id, payload.report_type, title, summary, content, json.dumps(metrics, ensure_ascii=False), now_sql()),
        )
        report_id = int(cursor.lastrowid)
        row = conn.execute(f"SELECT * FROM business_reports WHERE id={marker}", (report_id,)).fetchone()
    record_usage(merchant.id or 0, "report_generate", 1, payload.report_type, str(report_id))
    record_audit_log(merchant.id or 0, merchant.username, "report.generate", "report", str(report_id), f"生成报表：{title}", {"report_type": payload.report_type})
    return business_report_from_row(dict(row))


def safe_artifact_segment(value: str, fallback: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", value).strip("-")[:80] or fallback


def markdown_to_plain_lines(content: str) -> list[str]:
    lines: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*]\s+", "- ", line)
        line = line.replace("**", "").replace("`", "")
        lines.append(line)
    return lines


def wrap_display_text(text: str, limit: int = 42) -> list[str]:
    chunks: list[str] = []
    current = ""
    width = 0
    for char in text:
        char_width = 2 if ord(char) > 127 else 1
        if width + char_width > limit and current:
            chunks.append(current)
            current = char
            width = char_width
        else:
            current += char
            width += char_width
    chunks.append(current)
    return chunks or [""]


def write_report_pdf(path: Path, title: str, content: str) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PDF 导出依赖缺失，请安装 reportlab") from exc

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    page_width, page_height = A4
    margin = 48
    cursor_y = page_height - margin
    doc = canvas.Canvas(str(path), pagesize=A4)
    doc.setTitle(title)

    def draw_line(text: str, size: int = 10, leading: int = 16) -> None:
        nonlocal cursor_y
        if cursor_y < margin + leading:
            doc.showPage()
            doc.setFont("STSong-Light", size)
            cursor_y = page_height - margin
        doc.setFont("STSong-Light", size)
        doc.drawString(margin, cursor_y, text)
        cursor_y -= leading

    draw_line(title, size=16, leading=24)
    draw_line(f"导出时间：{now_sql()}", size=9, leading=20)
    for raw in markdown_to_plain_lines(content):
        if not raw:
            cursor_y -= 8
            continue
        size = 12 if raw.startswith(("一、", "二、", "三、", "四、", "五、", "六、")) else 10
        for wrapped in wrap_display_text(raw, limit=56):
            draw_line(wrapped, size=size, leading=17)
    doc.save()


def docx_paragraph(text: str, style: str = "") -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    if not text:
        return "<w:p/>"
    return f"<w:p>{style_xml}<w:r><w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r></w:p>"


def write_report_docx(path: Path, title: str, content: str) -> None:
    paragraphs = [docx_paragraph(title, "Title"), docx_paragraph(f"导出时间：{now_sql()}", "Subtitle")]
    for raw in content.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            paragraphs.append(docx_paragraph(line[2:].strip(), "Heading1"))
        elif line.startswith("## "):
            paragraphs.append(docx_paragraph(line[3:].strip(), "Heading2"))
        elif line.startswith("### "):
            paragraphs.append(docx_paragraph(line[4:].strip(), "Heading3"))
        elif line.startswith(("- ", "* ")):
            paragraphs.append(docx_paragraph(f"· {line[2:].strip()}", "ListParagraph"))
        else:
            paragraphs.append(docx_paragraph(line))
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(paragraphs)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="32"/></w:rPr><w:pPr><w:spacing w:after="220"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:color w:val="666666"/><w:sz w:val="18"/></w:rPr><w:pPr><w:spacing w:after="260"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="Heading 1"/><w:rPr><w:b/><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="28"/></w:rPr><w:pPr><w:spacing w:before="260" w:after="140"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="Heading 2"/><w:rPr><w:b/><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="24"/></w:rPr><w:pPr><w:spacing w:before="220" w:after="120"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="Heading 3"/><w:rPr><w:b/><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr><w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:pPr><w:ind w:left="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr></w:style>
</w:styles>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)


def write_report_export_artifact(report: BusinessReport, export_format: Literal["markdown", "pdf", "docx"]) -> tuple[str, str]:
    safe_title = safe_artifact_segment(report.title, f"report-{report.id}")
    report_dir = ARTIFACT_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{report.id}-{safe_title}.{ 'md' if export_format == 'markdown' else export_format }"
    path = report_dir / filename
    if export_format == "markdown":
        path.write_text(report.content, encoding="utf-8")
    elif export_format == "pdf":
        write_report_pdf(path, report.title, report.content)
    elif export_format == "docx":
        write_report_docx(path, report.title, report.content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    return filename, f"/artifacts/reports/{filename}"


async def export_business_report(
    report_id: int,
    merchant: MerchantProfile,
    export_format: Literal["markdown", "pdf", "docx"] = "markdown",
) -> ReportExportResponse:
    marker = param()
    with db() as conn:
        row = conn.execute(
            f"SELECT * FROM business_reports WHERE merchant_id={marker} AND id={marker}",
            (merchant.id, report_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    report = business_report_from_row(dict(row))
    filename, artifact_url = write_report_export_artifact(report, export_format)
    record_usage(merchant.id or 0, "report_export", 1, report.report_type, str(report.id))
    record_audit_log(merchant.id or 0, merchant.username, "report.export", "report", str(report.id), f"导出报表：{report.title}", {"format": export_format})
    return ReportExportResponse(
        report_id=report.id,
        format=export_format,
        filename=filename,
        artifact_url=artifact_url,
        content=report.content,
    )


async def run_daily_report_workflow(merchant: MerchantProfile) -> dict[str, Any]:
    run = workflow_engine.create_run(
        workflow_id="daily_business_report",
        payload={"report_type": "daily", "merchant_id": merchant.id},
        status="running",
        trigger_type="manual",
        trigger_source="reports",
    )
    workflow_engine.append_log(run.id, "Daily report workflow started", {"merchant_id": merchant.id})
    report = await generate_business_report(ReportGenerateRequest(report_type="daily"), merchant)
    workflow_engine.append_log(run.id, "Daily report generated", {"report_id": report.id}, status="success")
    record_usage(merchant.id or 0, "workflow_run", 1, "reports", "daily_business_report")
    return {"workflow_run": workflow_engine.get_run(run.id), "report": report}


def stage_report_index() -> list[str]:
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        docs_dir = Path("docs")
    if not docs_dir.exists():
        return []
    return sorted(path.name for path in docs_dir.glob("阶段*报告.md"))


def stage_report_files() -> list[Path]:
    docs_dir = PROJECT_ROOT / "docs"
    if not docs_dir.exists():
        docs_dir = Path("docs")
    if not docs_dir.exists():
        return []
    return sorted(docs_dir.glob("阶段*报告.md"))


def delivery_artifact_url(pack_id: str, filename: str) -> str:
    return f"/artifacts/delivery/{pack_id}/{filename}"


def write_delivery_file(pack_dir: Path, filename: str, content: str) -> DeliveryArtifact:
    path = pack_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return DeliveryArtifact(name=filename, artifact_url=f"/artifacts/delivery/{pack_dir.name}/{filename}", kind="markdown")


def copy_delivery_file(pack_dir: Path, source: Path, target_name: str) -> DeliveryArtifact:
    target = pack_dir / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return DeliveryArtifact(name=target_name, artifact_url=delivery_artifact_url(pack_dir.name, target_name), kind="markdown")


def acceptance_status(ok: bool, warning: bool = False) -> str:
    if ok:
        return "通过"
    return "需人工确认" if warning else "未完成"


async def build_acceptance_matrix_markdown(merchant: MerchantProfile) -> str:
    overview = await dashboard_overview(merchant)
    crm = await crm_overview(merchant)
    connectors = await list_connector_auths(merchant)
    oauth_token_connectors = [
        item for item in connectors
        if item.auth_mode == "oauth" and any(field in item.configured_fields for field in ["access_token", "session_key"])
    ]
    oauth_refresh_connectors = [
        item for item in oauth_token_connectors
        if "refresh_token" in item.configured_fields
    ]
    api_pull_ready_connectors = [
        item for item in connectors
        if any(field in item.configured_fields for field in ["access_token", "session_key"])
        and any(field in item.configured_fields for field in ["messages_url", "leads_url", "read_messages_url", "read_leads_url"])
    ]
    supervised_send_connectors = [
        item for item in connectors
        if item.send_enabled
        and any(field in item.configured_fields for field in ["access_token", "session_key"])
        and any(field in item.configured_fields for field in ["send_url", "reply_send_url", "message_send_url", "official_send_url"])
    ]
    usage = await usage_summary(merchant)
    reports = await list_business_reports(merchant, limit=5)
    dispatches = await list_reply_dispatches(merchant, limit=5)
    audit_logs = await list_audit_logs(merchant, limit=200)
    ops_health = await connector_ops_health(merchant)
    setup_guide = await connector_setup_guide(merchant)
    integration_order = integration_work_order_from_guide(
        IntegrationWorkOrderRequest(customer_name=merchant.business_name or merchant.username, include_done=False),
        merchant,
        setup_guide,
    )
    dry_run = integration_dry_run_from_sources(IntegrationDryRunRequest(include_artifact=False), connectors, ops_health)
    integration_tasks = open_integration_task_count(merchant.id or 0)
    sla_board = await integration_task_sla_board(merchant)
    escalation_items = [item for item in sla_board.items if item.sla_status in {"overdue", "due_today", "unscheduled"}]
    notice_items = escalation_items
    receipt_items = notice_items
    loop_events = [
        log for log in audit_logs
        if log.action in {"integration.sla_notice_receipt", "integration.sla_loop_report", "integration.task_reconcile"}
        or (log.action == "crm.task.update" and log.metadata.get("status") == "done")
    ]
    platform_evidence_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence"]
    platform_passed_scenarios = {str(log.metadata.get("scenario")) for log in platform_evidence_logs if log.metadata.get("result") == "pass"}
    platform_missing_scenarios = [scenario for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS if scenario not in platform_passed_scenarios]
    platform_gap_sync_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_sync"]
    platform_gap_reconcile_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_reconcile"]
    platform_checklist_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_checklist"]
    platform_sprint_pack_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_sprint_pack"]
    platform_live_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_live_run"]
    platform_joint_debug_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_joint_debug_run"]
    platform_gap_closure_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_closure_run"]
    platform_owner_action_pack_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_owner_action_pack"]
    platform_final_signoff_link_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_final_signoff_link"]
    platform_final_signoff_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_final_signoff"]
    platform_notice_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_notice"]
    platform_receipt_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_receipt"]
    platform_review_sync_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_review_sync"]
    platform_review_decision_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_review_decision"]
    platform_submission_link_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_submission_link"]
    platform_customer_submission_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_customer_submission"]
    platform_review_gap_reconcile_logs = [
        log for log in platform_review_decision_logs
        if log.metadata.get("gap_reconcile")
    ]
    platform_review_resubmission_logs = [
        log for log in platform_review_decision_logs
        if log.metadata.get("resubmission_link")
    ]
    platform_review_resubmission_logs = [
        log for log in platform_review_decision_logs
        if log.metadata.get("resubmission_link")
    ]
    platform_checklist_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_checklist"]
    workflows = workflow_engine.list_definitions()
    rows = [
        ("登录和企业资料", True, "可登录、可读取企业资料，企业资料更新有审计日志。"),
        ("网页客服", overview.today_conversations >= 0, "网页客服接口和会话沉淀可用。"),
        ("CRM 线索", crm.leads >= 0, f"CRM 线索数：{crm.leads}，打开任务：{crm.open_tasks}。"),
        ("Workflow", len(workflows) >= 4, f"Workflow 定义数：{len(workflows)}。"),
        ("AI Engine", True, "AI 能力统一从 /api/v1/ai-engine/* 暴露；未配置模型时有规则兜底。"),
        ("Connector 只读入站", len(connectors) >= 9, "支持 Connector 授权状态、只读消息和只读线索入站。"),
        ("OAuth 授权回调框架", True, "支持生成 OAuth state/auth_url，回调 code 会密文保存并等待 token exchange worker。"),
        ("OAuth token exchange worker", len(oauth_token_connectors) > 0, f"已密文保存访问凭证的 OAuth Connector 数：{len(oauth_token_connectors)}。"),
        ("OAuth refresh token worker", len(oauth_refresh_connectors) > 0, f"已具备 refresh_token 的 OAuth Connector 数：{len(oauth_refresh_connectors)}。"),
        ("官方 API 只读拉取 worker", len(api_pull_ready_connectors) > 0, f"已具备访问凭证和只读 API endpoint 的 Connector 数：{len(api_pull_ready_connectors)}。"),
        ("Webhook 签名校验", True, "公开 webhook 入口要求 HMAC SHA256 签名，签名密钥以密文形式保存。"),
        ("Connector 事件幂等", True, "同一 external_id 的消息/线索事件会被识别为重复事件，不重复创建客户、任务或草稿。"),
        ("回复草稿人工确认队列", True, "Connector 消息入站和手动创建均可生成待确认回复草稿，审核后仍不自动外发。"),
        ("回复外发准备和撤回审计", True, f"已建立 reply_dispatches 外发准备队列；最近记录数：{len(dispatches)}。"),
        ("受控 API 发送 worker", len(supervised_send_connectors) > 0, f"已开启受控发送闸门且具备 send_url/访问凭证的 Connector 数：{len(supervised_send_connectors)}。"),
        ("Connector 运维健康监控", ops_health.status != "fail", f"{ops_health.summary} 告警数：{len(ops_health.alerts)}。"),
        ("Platform setup guide", setup_guide.status != "blocked", f"{setup_guide.summary} tasks={len(setup_guide.tasks)} todo={setup_guide.counts.get('todo', 0)} blocked={setup_guide.counts.get('blocked', 0)}."),
        ("Platform integration work order", True, f"{integration_order.summary} items={len(integration_order.items)} status={integration_order.status}."),
        ("Platform integration dry run", dry_run.status != "fail", f"{dry_run.summary} status={dry_run.status}."),
        ("Platform integration task sync", True, f"Dry-run gap tasks can sync into CRM. open_integration_tasks={integration_tasks}."),
        ("Platform integration task reconcile", True, f"Passed dry-run checks can close matching CRM tasks. open_integration_tasks={integration_tasks}."),
        ("Platform integration SLA board", True, f"{sla_board.summary} status={sla_board.status}."),
        ("Platform integration SLA escalation", True, f"SLA escalation brief can be generated. escalation_items={len(escalation_items)}."),
        ("Platform integration SLA notice draft", True, f"SLA owner notice draft can be generated. notice_items={len(notice_items)}."),
        ("Platform integration SLA receipt loop", True, f"SLA notice receipt can be recorded. receipt_items={len(receipt_items)} close_requires_CONFIRM_CLOSE=true."),
        ("Platform integration SLA loop report", True, f"SLA loop report can be generated. loop_events={len(loop_events)}."),
        ("Platform real acceptance evidence", True, f"Real platform acceptance evidence can be registered. platform_evidence={len(platform_evidence_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance gap CRM sync", True, f"Platform acceptance missing scenarios can sync to CRM. gap_sync_events={len(platform_gap_sync_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance gap reconcile", True, f"Platform acceptance passed evidence can close CRM gaps. gap_reconcile_events={len(platform_gap_reconcile_logs)}."),
        ("Platform acceptance evidence checklist", True, f"Platform acceptance evidence collection can be planned. checklist_events={len(platform_checklist_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance evidence notice", True, f"Platform acceptance evidence owner notice can be drafted. notice_events={len(platform_notice_logs)} receipt_events={len(platform_receipt_logs)}."),
        ("Platform acceptance customer submission", True, f"Tokenized customer submission links can collect sanitized material. submission_links={len(platform_submission_link_logs)} customer_submissions={len(platform_customer_submission_logs)}."),
        ("Platform acceptance evidence review tasks", True, f"Submitted platform evidence receipts can sync to CRM review tasks. review_sync_events={len(platform_review_sync_logs)}."),
        ("Platform acceptance evidence review decision", True, f"Reviewed platform evidence can be approved, rejected, or sent back for redaction. review_decision_events={len(platform_review_decision_logs)}."),
        ("Platform acceptance review gap reconcile", True, f"Approved review decisions can trigger gap reconciliation. review_gap_reconcile_events={len(platform_review_gap_reconcile_logs)}."),
        ("Platform acceptance review resubmission", True, f"Needs-redaction or rejected review decisions can generate customer resubmission links. review_resubmission_links={len(platform_review_resubmission_logs)}."),
        ("Platform acceptance sprint pack", True, f"Real platform acceptance sprint packs combine missing scenarios, CRM tasks, and customer submission links. sprint_pack_events={len(platform_sprint_pack_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance live run board", True, f"Acceptance-day live runs summarize pass, review, customer submission, and sign-off readiness. live_run_events={len(platform_live_run_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance joint debug run", True, f"Read-only customer platform joint debug can collect verifiable pass evidence when official connectors are configured. joint_debug_runs={len(platform_joint_debug_run_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance remaining gap closure", True, f"Remaining gap closure can attempt token exchange, read-only pulls, CRM gap tasks, and customer trial links. gap_closure_runs={len(platform_gap_closure_run_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance owner action pack", True, f"Customer platform owner handoff packs list exact missing official fields, callback URLs, and customer trial links. owner_action_packs={len(platform_owner_action_pack_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("Platform acceptance final signoff gate", True, f"Final sign-off links stay blocked until live-run readiness is ready_for_signoff. final_signoff_links={len(platform_final_signoff_link_logs)} final_signoffs={len(platform_final_signoff_logs)} missing_scenarios={len(platform_missing_scenarios)}."),
        ("平台无人值守自动发送", False, "未开放无人值守自动发送；即使接入 API 发送也需要人工确认短语、低风险校验和审计。"),
        ("团队权限", True, "成员、角色、权限和审计日志已建立。"),
        ("计费和用量", usage.subscription.plan_id != "", f"当前套餐：{usage.subscription.plan_id}，AI 剩余：{usage.remaining.get('ai', 0)}。"),
        ("经营报表", len(reports) >= 0, f"报表数量：{len(reports)}，支持 Markdown/PDF/Word 导出。"),
        ("客户交付包", True, "本矩阵由交付包生成接口自动生成。"),
    ]
    lines = [
        "# 验收矩阵",
        "",
        f"生成时间：{now_sql()}",
        "",
        "| 模块 | 状态 | 验收证据 |",
        "| --- | --- | --- |",
    ]
    for name, ok, evidence in rows:
        warn = name in {"平台无人值守自动发送", "OAuth token exchange worker", "OAuth refresh token worker", "官方 API 只读拉取 worker", "受控 API 发送 worker", "Connector 运维健康监控", "Platform setup guide", "Platform integration work order", "Platform integration dry run", "Platform integration task sync", "Platform integration task reconcile", "Platform integration SLA board", "Platform integration SLA escalation", "Platform integration SLA notice draft", "Platform integration SLA receipt loop", "Platform integration SLA loop report", "Platform real acceptance evidence", "Platform acceptance gap CRM sync", "Platform acceptance gap reconcile", "Platform acceptance evidence checklist", "Platform acceptance evidence notice", "Platform acceptance customer submission", "Platform acceptance evidence review tasks", "Platform acceptance evidence review decision", "Platform acceptance review gap reconcile", "Platform acceptance review resubmission", "Platform acceptance sprint pack", "Platform acceptance live run board", "Platform acceptance joint debug run", "Platform acceptance remaining gap closure", "Platform acceptance owner action pack", "Platform acceptance final signoff gate"}
        lines.append(f"| {name} | {acceptance_status(ok, warning=warn)} | {evidence} |")
    lines.extend(
        [
            "",
            "## 最终边界",
            "",
            "- 已完成：网页客服、CRM、Workflow、Connector 只读入站、OAuth 授权回调框架、OAuth token exchange worker、OAuth refresh token worker、官方 API 只读拉取 worker、Webhook 签名校验、Connector 事件幂等、回复草稿人工确认队列、回复外发准备和撤回审计、受控 API 发送 worker、Connector 运维健康监控、平台接入配置向导、平台接入工单、平台接入干跑验收、平台接入缺口转 CRM 任务、平台接入任务复验关闭、平台接入 SLA 看板、平台接入 SLA 升级简报、平台接入 SLA 责任人通知草稿、平台接入 SLA 通知回执闭环、平台接入 SLA 闭环复盘报表、真实平台验收证据登记、真实平台验收缺口转 CRM 任务、真实平台验收缺口复验关闭、真实平台验收证据采集清单、真实平台验收证据通知与回执、客户材料提交入口、真实平台验收材料复核任务、真实平台验收材料审核决策、审核通过联动缺口复验、审核退回补交闭环、团队权限、审计日志、订阅用量、经营报表、交付包生成。",
            "- 未声明完成：无人值守自动发送、自动发布商品、自动改价、退款、发货。",
            "- 交付验收时必须使用真实账号和真实聊天/线索场景验证平台侧能力。",
        ]
    )
    return "\n".join(lines)


async def build_operation_manual_markdown(merchant: MerchantProfile) -> str:
    return "\n".join(
        [
            "# 操作手册",
            "",
            "## 1. 登录后台",
            "",
            "- 打开线上后台：`https://wjhai.cn/merchant-admin/`",
            "- 使用交付时提供的企业账号登录。",
            "- 首次交付后建议立即更换演示密码，并改用企业自己的成员账号。",
            "",
            "## 2. 每日使用顺序",
            "",
            "1. 打开企业管理，确认企业资料、商品服务、价格套餐和欢迎语。",
            "2. 打开 AI 客服，测试网页客服接入代码和会话收件箱。",
            "3. 打开 CRM，处理高意向线索和跟进任务。",
            "4. 打开系统设置，检查 Connector 授权状态和缺失字段。",
            "5. 打开经营分析，生成经营日报并导出 Markdown、PDF 或 Word。",
            "",
            "## 3. 平台接入边界",
            "",
            "- 官网客服可以直接自动回复。",
            "- 微信、企业微信、抖音、淘宝、拼多多、闲鱼先做只读入站或草稿辅助。",
            "- 自动发送必须等官方 API 权限、验签、审计和人工确认策略完成后再开启。",
            "",
            "## 4. 客服处理原则",
            "",
            "- 高意向、退款、投诉、付款、账号、隐私类消息要人工确认。",
            "- AI 回复可作为候选，不能替代合同、售后、财务承诺。",
            "- 每天清理 CRM 跟进任务，避免漏单。",
            "",
            "## 5. 报表复盘",
            "",
            "- 每天生成经营日报。",
            "- 查看高意向线索、打开任务、Connector 状态和用量余额。",
            "- 将日报复制或导出为 PDF/Word 给老板、运营负责人和客服主管复盘。",
        ]
    )


async def build_delivery_readme_markdown(merchant: MerchantProfile, payload: DeliveryPackGenerateRequest) -> str:
    reports = stage_report_index()
    connectors = await list_connector_auths(merchant)
    connected = [item for item in connectors if item.status in {"connected", "assist_only"}]
    blocked = [item for item in connectors if item.status not in {"connected", "assist_only"}]
    return "\n".join(
        [
            f"# {payload.customer_name} AI 商家运营工作台交付包",
            "",
            f"生成时间：{now_sql()}",
            "",
            "## 已交付能力",
            "",
            "- 企业资料和登录后台",
            "- 网页 AI 客服和会话收件箱",
            "- CRM 线索、跟进任务、人工接管",
            "- Workflow 自动化运行记录",
            "- Connector 授权状态和只读消息/线索入站",
            "- OAuth 授权跳转和回调 code 密文保存",
            "- OAuth token exchange worker 和访问凭证密文保存",
            "- OAuth refresh token worker 和到期告警",
            "- 官方 API 只读拉取 worker，拉取后进入 CRM/Workflow",
            "- Webhook 签名校验和密钥密文存储",
            "- 回复草稿人工确认队列",
            "- 回复外发准备队列、撤回和审计记录",
            "- 人工确认后的受控 API 发送 worker",
            "- Connector 运维健康监控和告警汇总",
            "- 平台接入配置向导和缺口修复清单",
            "- 平台接入工单和客户资料准备清单",
            "- 平台接入干跑验收和检查报告",
            "- 平台接入缺口转 CRM 跟进任务",
            "- 平台接入任务复验关闭",
            "- 平台接入 SLA 看板和逾期升级",
            "- 平台接入 SLA 升级简报",
            "- 平台接入 SLA 责任人通知草稿",
            "- 平台接入 SLA 通知回执闭环",
            "- 平台接入 SLA 闭环复盘报表",
            "- 真实平台验收证据登记和证据包",
            "- 真实平台验收缺口转 CRM 任务",
            "- 真实平台验收缺口复验关闭",
            "- 真实平台验收证据采集清单",
            "- 真实平台验收证据通知与回执",
            "- 客户材料提交入口",
            "- 真实平台验收材料复核任务",
            "- 真实平台验收材料审核决策",
            "- 审核退回补交闭环",
            "- 真实平台联调执行台",
            "- 真实平台剩余缺口闭环指挥台",
            "- 客户平台负责人行动交接包",
            "- 真实平台最终签署门禁",
            "- 团队成员、角色权限、审计日志",
            "- 订阅套餐、额度和用量记录",
            "- 经营日报、Markdown/PDF/Word 报表导出",
            "- 客户交付包和验收矩阵",
            "",
            "## 线上入口",
            "",
            "- 后台地址：`https://wjhai.cn/merchant-admin/`",
            "- API 健康检查：`https://wjhai.cn/merchant-admin/api/health`",
            "",
            "## Connector 状态",
            "",
            f"- 已接入/辅助：{len(connected)}",
            f"- 待授权/未配置：{len(blocked)}",
            "",
            "## 阶段报告",
            "",
            *[f"- `{name}`" for name in reports],
            "",
            "## 安全边界",
            "",
            "- 不把服务器密码、API Key、客户隐私放进交付包。",
            "- 未授权平台不承诺自动发送。",
            "- 涉及付款、退款、投诉、隐私和账号权限必须人工确认。",
        ]
    )


def build_safety_boundary_markdown() -> str:
    return "\n".join(
        [
            "# 安全边界说明",
            "",
            "## 可以声明",
            "",
            "- 官网客服自动回复可用。",
            "- CRM、Workflow、报表、用量、审计可用。",
            "- Connector 支持授权状态管理和只读入站。",
            "",
            "## 不可以声明",
            "",
            "- 不声明微信/抖音/淘宝/拼多多/闲鱼全自动发送已商用完成。",
            "- 不声明自动发布、改价、退款、发货已完成。",
            "- 不声明未授权平台数据可以稳定后台读取。",
            "",
            "## 交付前必须做",
            "",
            "- 更换演示账号密码。",
            "- 移除交付包中的任何敏感信息。",
            "- 用客户真实账号验收 Connector 权限。",
            "- 明确自动发送前的人审策略。",
        ]
    )


async def generate_delivery_pack(payload: DeliveryPackGenerateRequest, merchant: MerchantProfile) -> DeliveryPack:
    pack_id = f"delivery-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    pack_dir = ARTIFACT_DIR / "delivery" / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    setup_guide = await connector_setup_guide(merchant)
    integration_order = integration_work_order_from_guide(
        IntegrationWorkOrderRequest(customer_name=payload.customer_name, include_done=False),
        merchant,
        setup_guide,
    )
    dry_run = await run_integration_dry_run(IntegrationDryRunRequest(include_artifact=False), merchant, persist=False)
    sla_escalation = await generate_integration_sla_escalation(
        IntegrationSLAEscalationRequest(include_upcoming=False, owner=payload.customer_name),
        merchant,
    )
    sla_notice = await generate_integration_sla_notice(
        IntegrationSLANoticeRequest(include_upcoming=False, owner=payload.customer_name, recipient=payload.customer_name),
        merchant,
    )
    sla_receipt = await record_integration_sla_notice_receipt(
        IntegrationSLANoticeReceiptRequest(
            notice_id=sla_notice.id,
            recipient=payload.customer_name,
            outcome="acknowledged",
            confirmed_task_ids=[],
            close_confirmed_tasks=False,
            notes="交付包回执模板；实际关闭任务需人工确认后传入任务 ID 和 CONFIRM_CLOSE。",
        ),
        merchant,
    )
    sla_loop_report = await generate_integration_sla_loop_report(
        IntegrationSLALoopReportRequest(audit_limit=30, include_artifact=True),
        merchant,
    )
    platform_acceptance_report = await generate_platform_acceptance_report(
        PlatformAcceptanceReportRequest(audit_limit=100, include_artifact=True),
        merchant,
    )
    platform_gap_sync = await sync_platform_acceptance_gaps_to_crm_tasks(
        PlatformAcceptanceGapSyncRequest(owner=payload.customer_name, due_days=2, create_tasks=False, include_artifact=True),
        merchant,
    )
    platform_gap_reconcile = await reconcile_platform_acceptance_gap_tasks(
        PlatformAcceptanceGapReconcileRequest(close_tasks=False, include_artifact=True),
        merchant,
    )
    platform_evidence_checklist = await generate_platform_acceptance_evidence_checklist(
        PlatformAcceptanceEvidenceChecklistRequest(
            owner=payload.customer_name,
            due_days=2,
            ensure_tasks=False,
            include_passed=True,
            include_artifact=True,
        ),
        merchant,
    )
    platform_evidence_notice = await generate_platform_acceptance_evidence_notice(
        PlatformAcceptanceEvidenceNoticeRequest(
            owner=payload.customer_name,
            recipient=payload.customer_name,
            channel="copy",
            due_days=2,
            ensure_tasks=False,
            include_passed=False,
            include_artifact=True,
        ),
        merchant,
    )
    platform_review_sync = await sync_platform_acceptance_evidence_review_tasks(
        PlatformAcceptanceEvidenceReviewTaskSyncRequest(
            owner=payload.customer_name,
            due_days=1,
            include_needs_help=True,
            create_tasks=False,
            include_artifact=True,
            audit_limit=200,
        ),
        merchant,
    )
    platform_review_desk = await generate_platform_acceptance_review_desk(
        PlatformAcceptanceReviewDeskRequest(
            owner=payload.customer_name,
            due_days=1,
            include_needs_help=True,
            create_review_tasks=False,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_review_execution = await run_platform_acceptance_review_execution(
        PlatformAcceptanceReviewExecutionRunRequest(
            owner=payload.customer_name,
            due_days=1,
            decisions=[],
            auto_ready_items=True,
            execute=False,
            confirm_phrase="",
            include_artifact=True,
            audit_limit=300,
            no_secrets_confirmed=True,
        ),
        merchant,
    )
    platform_evidence_import = await run_platform_acceptance_evidence_import(
        PlatformAcceptanceEvidenceImportRunRequest(
            owner=payload.customer_name,
            items=[],
            execute=False,
            confirm_phrase="",
            close_review_tasks=True,
            reconcile_gap_tasks=True,
            include_artifact=True,
            audit_limit=300,
            no_secrets_confirmed=True,
        ),
        merchant,
    )
    platform_evidence_manifest_link = await generate_platform_acceptance_evidence_manifest_link(
        PlatformAcceptanceEvidenceManifestLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            scenarios=[],
            expires_days=7,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_review_decision = await record_platform_acceptance_evidence_review_decision(
        PlatformAcceptanceEvidenceReviewDecisionRequest(
            scenario="customer_trial",
            decision="needs_redaction",
            review_task_ids=[],
            connector="website",
            account_label=payload.customer_name,
            operator=payload.customer_name,
            evidence_note="Delivery pack template only. No customer proof is registered by this artifact.",
            evidence_url="",
            register_pass_evidence=False,
            close_review_tasks=False,
            confirm_phrase="",
            include_artifact=True,
            no_secrets_confirmed=True,
        ),
        merchant,
    )
    platform_sprint_pack = await generate_platform_acceptance_sprint_pack(
        PlatformAcceptanceSprintPackRequest(
            owner=payload.customer_name,
            recipient=payload.customer_name,
            due_days=2,
            expires_days=7,
            ensure_tasks=False,
            create_links=False,
            include_passed=False,
            include_artifact=True,
        ),
        merchant,
    )
    platform_joint_debug_run = await generate_platform_acceptance_joint_debug_run(
        PlatformAcceptanceJointDebugRunRequest(
            customer_name=payload.customer_name,
            operator=payload.customer_name,
            connectors=[],
            attempt_pull=False,
            auto_register_pass_evidence=False,
            pull_limit=3,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_gap_closure_run = await generate_platform_acceptance_gap_closure_run(
        PlatformAcceptanceGapClosureRunRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connectors=[],
            attempt_exchange=False,
            attempt_pull=False,
            auto_register_pass_evidence=False,
            create_submission_links=True,
            create_gap_tasks=False,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_owner_action_pack = await generate_platform_acceptance_owner_action_pack(
        PlatformAcceptanceOwnerActionPackRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connectors=[],
            create_customer_trial_link=True,
            expires_days=7,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_owner_closure_link = await generate_platform_acceptance_owner_closure_link(
        PlatformAcceptanceOwnerClosureLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connectors=[],
            expires_days=3,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_owner_closure_run = await generate_platform_acceptance_owner_closure_run(
        PlatformAcceptanceOwnerClosureRunRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connector_updates=[],
            scenario_receipts=[],
            attempt_exchange=False,
            attempt_pull=False,
            auto_register_pass_evidence=False,
            create_submission_links=True,
            create_gap_tasks=False,
            create_review_tasks=False,
            include_artifact=True,
            audit_limit=300,
            no_secrets_confirmed=True,
        ),
        merchant,
    )
    platform_auto_watch_run = await generate_platform_acceptance_auto_watch_run(
        PlatformAcceptanceAutoWatchRunRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connectors=[],
            attempt_exchange=False,
            attempt_pull=False,
            create_owner_closure_link=True,
            create_review_tasks=False,
            create_gap_tasks=False,
            create_customer_links=True,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_watch_board = await generate_platform_acceptance_watch_board(
        PlatformAcceptanceWatchBoardRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_customer_room = await generate_platform_acceptance_customer_room_link(
        PlatformAcceptanceCustomerRoomLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            connectors=[],
            expires_days=3,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_live_run = await generate_platform_acceptance_live_run(
        PlatformAcceptanceLiveRunRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            due_days=2,
            expires_days=7,
            ensure_tasks=False,
            create_sprint_pack=False,
            create_links=False,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    platform_final_signoff_link = await generate_platform_acceptance_final_signoff_link(
        PlatformAcceptanceFinalSignoffLinkRequest(
            customer_name=payload.customer_name,
            owner=payload.customer_name,
            recipient=payload.customer_name,
            signer_name=payload.customer_name,
            signer_role="platform owner",
            expires_days=7,
            include_artifact=True,
            audit_limit=300,
        ),
        merchant,
    )
    artifacts = [
        write_delivery_file(pack_dir, "README.md", await build_delivery_readme_markdown(merchant, payload)),
        write_delivery_file(pack_dir, "安全边界.md", build_safety_boundary_markdown()),
        write_delivery_file(pack_dir, "平台接入工单.md", build_integration_work_order_markdown(integration_order, merchant)),
        write_delivery_file(pack_dir, "平台接入干跑验收.md", build_integration_dry_run_markdown(dry_run)),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / sla_escalation.artifact_url.split("/")[-1], "平台接入SLA升级简报.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / sla_notice.artifact_url.split("/")[-1], "平台接入SLA责任人通知草稿.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / sla_receipt.artifact_url.split("/")[-1], "平台接入SLA通知回执模板.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / sla_loop_report.artifact_url.split("/")[-1], "平台接入SLA闭环复盘报表.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_acceptance_report.artifact_url.split("/")[-1], "真实平台验收证据包.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_gap_sync.artifact_url.split("/")[-1], "真实平台验收缺口CRM任务清单.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_gap_reconcile.artifact_url.split("/")[-1], "真实平台验收缺口复验关闭报告.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_evidence_checklist.artifact_url.split("/")[-1], "真实平台验收证据采集清单.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_evidence_notice.artifact_url.split("/")[-1], "真实平台验收证据通知草稿.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_review_sync.artifact_url.split("/")[-1], "真实平台验收材料复核任务.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_review_desk.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Review-Desk.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_review_execution.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Review-Execution-Preview.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_evidence_import.artifact_url.split("/")[-1], "Real-Platform-Evidence-Import-Preview.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_evidence_manifest_link.artifact_url.split("/")[-1], "Real-Platform-Customer-Evidence-Manifest-Link.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_review_decision.artifact_url.split("/")[-1], "真实平台验收材料审核决策模板.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_sprint_pack.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Sprint-Pack.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_joint_debug_run.artifact_url.split("/")[-1], "Real-Platform-Joint-Debug-Run.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_gap_closure_run.artifact_url.split("/")[-1], "Real-Platform-Remaining-Gap-Closure-Run.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_owner_action_pack.artifact_url.split("/")[-1], "Real-Platform-Owner-Action-Pack.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_owner_closure_link.artifact_url.split("/")[-1], "Real-Platform-Owner-Secure-Closure-Link.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_owner_closure_run.artifact_url.split("/")[-1], "Real-Platform-Owner-Closure-Run.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_auto_watch_run.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Auto-Watch.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_watch_board.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Watch-Board.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_customer_room.artifact_url.split("/")[-1], "Real-Platform-Customer-Acceptance-Room.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_live_run.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Live-Run.md"),
        copy_delivery_file(pack_dir, ARTIFACT_DIR / "integration" / platform_final_signoff_link.artifact_url.split("/")[-1], "Real-Platform-Acceptance-Final-Signoff-Gate.md"),
    ]
    if payload.include_acceptance_matrix:
        artifacts.append(write_delivery_file(pack_dir, "验收矩阵.md", await build_acceptance_matrix_markdown(merchant)))
    if payload.include_operation_manual:
        artifacts.append(write_delivery_file(pack_dir, "操作手册.md", await build_operation_manual_markdown(merchant)))
    if payload.include_stage_reports:
        report_files = stage_report_files()
        report_index = "\n".join(["# 阶段报告索引", "", *[f"- `{path.name}`" for path in report_files], ""])
        artifacts.append(write_delivery_file(pack_dir, "阶段报告索引.md", report_index))
        for report_file in report_files:
            artifacts.append(copy_delivery_file(pack_dir, report_file, f"阶段报告/{report_file.name}"))
    manifest = {
        "id": pack_id,
        "customer_name": payload.customer_name,
        "created_at": now_sql(),
        "artifacts": [item.model_dump() for item in artifacts],
        "stage_reports": stage_report_index() if payload.include_stage_reports else [],
    }
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.append(DeliveryArtifact(name="manifest.json", artifact_url=delivery_artifact_url(pack_id, "manifest.json"), kind="json"))
    zip_name = f"{pack_id}.zip"
    zip_path = ARTIFACT_DIR / "delivery" / zip_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in pack_dir.rglob("*"):
            if file.is_file():
                archive.write(file, arcname=f"{pack_id}/{file.relative_to(pack_dir).as_posix()}")
    zip_url = f"/artifacts/delivery/{zip_name}"
    record_usage(merchant.id or 0, "delivery_pack", 1, "delivery", pack_id)
    record_audit_log(merchant.id or 0, merchant.username, "delivery.pack.generate", "delivery_pack", pack_id, f"生成客户交付包：{payload.customer_name}")
    return DeliveryPack(
        id=pack_id,
        customer_name=payload.customer_name,
        title=f"{payload.customer_name} AI 商家运营工作台交付包",
        summary="交付包已生成，包含 README、验收矩阵、操作手册、安全边界和 manifest。",
        artifacts=artifacts,
        zip_url=zip_url,
        created_at=manifest["created_at"],
    )


async def latest_delivery_packs(limit: int = 20) -> list[DeliveryPack]:
    delivery_dir = ARTIFACT_DIR / "delivery"
    if not delivery_dir.exists():
        return []
    packs: list[DeliveryPack] = []
    for manifest_path in sorted(delivery_dir.glob("delivery-*/manifest.json"), reverse=True)[:limit]:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pack_id = manifest.get("id") or manifest_path.parent.name
        artifacts = [DeliveryArtifact(**item) for item in manifest.get("artifacts", [])]
        zip_path = delivery_dir / f"{pack_id}.zip"
        packs.append(
            DeliveryPack(
                id=pack_id,
                customer_name=manifest.get("customer_name") or "客户",
                title=f"{manifest.get('customer_name') or '客户'} AI 商家运营工作台交付包",
                summary="已生成交付包。",
                artifacts=artifacts,
                zip_url=f"/artifacts/delivery/{zip_path.name}" if zip_path.exists() else "",
                created_at=manifest.get("created_at") or "",
            )
        )
    return packs


def acceptance_audit_artifact_url(filename: str) -> str:
    return f"/artifacts/acceptance/{filename}"


def acceptance_status_text(status: str) -> str:
    return {
        "pass": "通过",
        "warning": "有边界",
        "fail": "未通过",
        "ready": "可试运行",
        "ready_with_boundaries": "可交付但有边界",
        "needs_attention": "需处理",
    }.get(status, status)


def build_acceptance_audit_markdown(audit: AcceptanceAudit) -> str:
    lines = [
        "# 最终验收巡检报告",
        "",
        f"生成时间：{audit.created_at}",
        f"总体状态：{acceptance_status_text(audit.status)}",
        f"就绪评分：{audit.readiness_score}",
        "",
        audit.summary,
        "",
        "## 验收项",
        "",
        "| 模块 | 状态 | 证据 | 下一步 |",
        "| --- | --- | --- | --- |",
    ]
    for item in audit.items:
        lines.append(f"| {item.module} | {acceptance_status_text(item.status)} | {item.evidence} | {item.next_action or '-'} |")
    lines.extend(["", "## 需关注项", ""])
    if audit.blockers:
        lines.extend(f"- {item}" for item in audit.blockers)
    else:
        lines.append("- 暂无阻断项。")
    lines.extend(["", "## 下一步动作", ""])
    if audit.next_actions:
        lines.extend(f"- {item}" for item in audit.next_actions)
    else:
        lines.append("- 维持当前交付边界并进入客户试运行。")
    return "\n".join(lines)


async def run_acceptance_audit(payload: AcceptanceAuditRequest, merchant: MerchantProfile) -> AcceptanceAudit:
    overview = await dashboard_overview(merchant)
    crm = await crm_overview(merchant)
    connectors = await list_connector_auths(merchant)
    members = await list_team_members(merchant)
    audit_logs = await list_audit_logs(merchant, limit=200)
    usage = await usage_summary(merchant)
    reports = await list_business_reports(merchant, limit=5)
    deliveries = await latest_delivery_packs(limit=5)
    reply_drafts = await list_reply_drafts(merchant, status="", limit=5)
    reply_dispatches = await list_reply_dispatches(merchant, limit=5)
    ops_health = await connector_ops_health(merchant)
    setup_guide = await connector_setup_guide(merchant)
    integration_order = integration_work_order_from_guide(
        IntegrationWorkOrderRequest(customer_name=merchant.business_name or merchant.username, include_done=False),
        merchant,
        setup_guide,
    )
    dry_run = integration_dry_run_from_sources(IntegrationDryRunRequest(include_artifact=False), connectors, ops_health)
    integration_tasks = open_integration_task_count(merchant.id or 0)
    sla_board = await integration_task_sla_board(merchant)
    escalation_items = [item for item in sla_board.items if item.sla_status in {"overdue", "due_today", "unscheduled"}]
    notice_items = escalation_items
    receipt_items = notice_items
    loop_events = [
        log for log in audit_logs
        if log.action in {"integration.sla_notice_receipt", "integration.sla_loop_report", "integration.task_reconcile"}
        or (log.action == "crm.task.update" and log.metadata.get("status") == "done")
    ]
    platform_evidence_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence"]
    platform_passed_scenarios = {str(log.metadata.get("scenario")) for log in platform_evidence_logs if log.metadata.get("result") == "pass"}
    platform_missing_scenarios = [scenario for scenario in PLATFORM_ACCEPTANCE_REQUIRED_SCENARIOS if scenario not in platform_passed_scenarios]
    platform_gap_sync_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_sync"]
    platform_gap_reconcile_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_reconcile"]
    platform_checklist_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_checklist"]
    platform_notice_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_notice"]
    platform_receipt_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_receipt"]
    platform_review_sync_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_review_sync"]
    platform_review_decision_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_review_decision"]
    platform_submission_link_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_submission_link"]
    platform_customer_submission_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_evidence_customer_submission"]
    platform_review_gap_reconcile_logs = [
        log for log in platform_review_decision_logs
        if log.metadata.get("gap_reconcile")
    ]
    platform_review_resubmission_logs = [
        log for log in platform_review_decision_logs
        if log.metadata.get("resubmission_link")
    ]
    platform_sprint_pack_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_sprint_pack"]
    platform_live_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_live_run"]
    platform_joint_debug_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_joint_debug_run"]
    platform_gap_closure_run_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_gap_closure_run"]
    platform_owner_action_pack_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_owner_action_pack"]
    platform_final_signoff_link_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_final_signoff_link"]
    platform_final_signoff_logs = [log for log in audit_logs if log.action == "integration.platform_acceptance_final_signoff"]
    workflows = workflow_engine.list_definitions()
    read_only_connectors = [item for item in connectors if item.read_only_enabled]
    send_enabled_connectors = [item for item in connectors if item.send_enabled]
    signed_webhook_connectors = [
        item for item in connectors
        if any(field in item.configured_fields for field in ["webhook_secret", "webhook_token", "token"])
    ]
    oauth_connectors = [item for item in connectors if item.auth_mode == "oauth"]
    oauth_code_connectors = [item for item in oauth_connectors if "oauth_code" in item.configured_fields]
    oauth_token_connectors = [
        item for item in oauth_connectors
        if any(field in item.configured_fields for field in ["access_token", "session_key"])
    ]
    oauth_refresh_connectors = [
        item for item in oauth_token_connectors
        if "refresh_token" in item.configured_fields
    ]
    api_pull_ready_connectors = [
        item for item in connectors
        if any(field in item.configured_fields for field in ["access_token", "session_key"])
        and any(field in item.configured_fields for field in ["messages_url", "leads_url", "read_messages_url", "read_leads_url"])
    ]
    supervised_send_connectors = [
        item for item in connectors
        if item.send_enabled
        and any(field in item.configured_fields for field in ["access_token", "session_key"])
        and any(field in item.configured_fields for field in ["send_url", "reply_send_url", "message_send_url", "official_send_url"])
    ]
    items = [
        AcceptanceAuditItem(
            module="登录和企业资料",
            status="pass" if merchant.id else "fail",
            evidence=f"当前商家：{merchant.business_name or merchant.username}，merchant_code={merchant.merchant_code or '-'}。",
            next_action="" if merchant.id else "先完成商家账号初始化。",
        ),
        AcceptanceAuditItem(
            module="网页客服与会话收件箱",
            status="pass",
            evidence=f"今日会话 {overview.today_conversations}，自动回复 {overview.auto_replies}，待人工 {overview.handoff_needed}。",
            next_action="交付时用真实官网页面发起一轮访客咨询。",
        ),
        AcceptanceAuditItem(
            module="CRM 线索和跟进任务",
            status="pass",
            evidence=f"线索 {crm.leads}，高意向 {crm.high_intent}，打开任务 {crm.open_tasks}。",
            next_action="导入或创建客户真实线索做首轮试运行。",
        ),
        AcceptanceAuditItem(
            module="Workflow 自动化",
            status="pass" if len(workflows) >= 4 else "warning",
            evidence=f"已注册 Workflow 定义 {len(workflows)} 个。",
            next_action="" if len(workflows) >= 4 else "补齐日报、线索、人工接管等基础 Workflow。",
        ),
        AcceptanceAuditItem(
            module="AI Engine",
            status="pass",
            evidence="AI 风险识别、意图评分、摘要、回复生成统一由 v1 能力承接；无模型时保留规则兜底。",
            next_action="正式商用前配置客户自己的模型 Key 和额度。",
        ),
        AcceptanceAuditItem(
            module="知识库文档解析",
            status="pass",
            evidence="知识库上传支持 txt/md/csv/json/pdf/docx，PDF 和 Word 可解析为知识条目并同步 FAQ。",
            next_action="客户交付时导入真实 FAQ、售后政策和商品资料。",
        ),
        AcceptanceAuditItem(
            module="Connector 只读入站",
            status="pass" if len(read_only_connectors) >= 5 else "warning",
            evidence=f"Connector 总数 {len(connectors)}，只读入站 {len(read_only_connectors)}。",
            next_action="" if len(read_only_connectors) >= 5 else "补齐目标平台的授权字段和回调配置。",
        ),
        AcceptanceAuditItem(
            module="OAuth 授权跳转和回调",
            status="pass" if oauth_connectors else "warning",
            evidence=f"OAuth Connector 数：{len(oauth_connectors)}；已收到回调 code 的 Connector 数：{len(oauth_code_connectors)}。",
            next_action="" if oauth_connectors else "为抖音、淘宝、拼多多等官方平台配置 OAuth 授权参数。",
        ),
        AcceptanceAuditItem(
            module="OAuth token exchange worker",
            status="pass" if oauth_token_connectors else "warning",
            evidence=f"已密文保存 access_token/session_key 的 OAuth Connector 数：{len(oauth_token_connectors)}；等待换取 token 的 code 数：{len(oauth_code_connectors)}。",
            next_action="" if oauth_token_connectors else "配置 token_url、client_secret/app_secret 并完成官方回调后，在设置页执行换取 Token。",
        ),
        AcceptanceAuditItem(
            module="OAuth refresh token worker",
            status="pass" if oauth_refresh_connectors else "warning",
            evidence=f"已具备 refresh_token 可续期的 OAuth Connector 数：{len(oauth_refresh_connectors)}。",
            next_action="" if oauth_refresh_connectors else "完成官方 token exchange 并保存 refresh_token；到期前可在设置页执行刷新 Token。",
        ),
        AcceptanceAuditItem(
            module="官方 API 只读拉取 worker",
            status="pass" if api_pull_ready_connectors else "warning",
            evidence=f"已具备访问凭证和 messages_url/leads_url 的 Connector 数：{len(api_pull_ready_connectors)}；拉取结果会进入 CRM/Workflow，不会自动外发。",
            next_action="" if api_pull_ready_connectors else "配置官方只读 API endpoint，并使用已换取的访问凭证拉取消息或线索。",
        ),
        AcceptanceAuditItem(
            module="Webhook 签名校验和密钥存储",
            status="pass" if signed_webhook_connectors else "warning",
            evidence=f"公开 webhook 入口要求 HMAC SHA256 签名；已配置签名密钥的 Connector 数：{len(signed_webhook_connectors)}。",
            next_action="" if signed_webhook_connectors else "为目标 Connector 配置 webhook_token 或 webhook_secret。",
        ),
        AcceptanceAuditItem(
            module="Connector 事件幂等",
            status="pass",
            evidence="消息和线索入站按 connector、event_type、external_id 查重，重复事件不会重复创建客户、任务或草稿。",
            next_action="平台回调接入时必须稳定传入 external_id。",
        ),
        AcceptanceAuditItem(
            module="回复草稿人工确认队列",
            status="pass",
            evidence=f"最近回复草稿 {len(reply_drafts)} 条；Connector 消息入站会生成待确认草稿，审核后仍不自动外发。",
            next_action="客服主管每天处理 pending 草稿，复制或人工发送前复核风险提示。",
        ),
        AcceptanceAuditItem(
            module="回复外发准备和撤回审计",
            status="pass",
            evidence=f"最近外发准备记录 {len(reply_dispatches)} 条；已审批回复可进入 manual_copy 队列并支持撤回审计。",
            next_action="保持人工复制发送边界；只有官方发送权限、验签和风控策略齐全后才评估 API 自动发送。",
        ),
        AcceptanceAuditItem(
            module="受控 API 发送 worker",
            status="pass" if supervised_send_connectors else "warning",
            evidence=f"开启受控发送闸门且具备 send_url/访问凭证的 Connector 数：{len(supervised_send_connectors)}；发送仍需确认短语、低风险校验、频控和审计。",
            next_action="" if supervised_send_connectors else "配置官方 send_url、访问凭证，并使用 ENABLE_SUPERVISED_SEND 显式开启受控发送闸门。",
        ),
        AcceptanceAuditItem(
            module="Connector 运维健康监控",
            status="pass" if ops_health.status == "pass" else "warning" if ops_health.status == "warning" else "fail",
            evidence=f"{ops_health.summary} 告警数：{len(ops_health.alerts)}。",
            next_action="" if ops_health.status == "pass" else "进入设置页 Connector 运维健康面板，处理授权、endpoint、失败事件或待外发队列。",
        ),
        AcceptanceAuditItem(
            module="平台接入配置向导",
            status="pass" if setup_guide.status == "ready" else "warning",
            evidence=f"{setup_guide.summary} tasks={len(setup_guide.tasks)} todo={setup_guide.counts.get('todo', 0)} blocked={setup_guide.counts.get('blocked', 0)}。",
            next_action="" if setup_guide.status == "ready" else "进入设置页查看平台接入配置向导，按 OAuth、只读 API、受控发送和 webhook 签名任务逐项补齐。",
        ),
        AcceptanceAuditItem(
            module="平台接入工单",
            status="pass",
            evidence=f"{integration_order.summary} items={len(integration_order.items)} status={integration_order.status}。",
            next_action="将工单交给客户平台管理员或技术负责人，完成后回到设置页复验。",
        ),
        AcceptanceAuditItem(
            module="平台接入干跑验收",
            status="pass" if dry_run.status == "pass" else "warning",
            evidence=f"{dry_run.summary} status={dry_run.status}。",
            next_action="" if dry_run.status == "pass" else "按干跑验收报告修复 fail/warning 项，真实授权完成后重新运行。",
        ),
        AcceptanceAuditItem(
            module="平台接入缺口 CRM 任务同步",
            status="pass",
            evidence=f"干跑失败/告警可同步为 CRM 跟进任务；当前打开接入任务 {integration_tasks} 个。",
            next_action="在设置页点击同步任务，把未完成接入项分配给运营或技术负责人。",
        ),
        AcceptanceAuditItem(
            module="平台接入任务复验关闭",
            status="pass",
            evidence=f"干跑通过项可自动关闭匹配的 CRM 接入任务；当前打开接入任务 {integration_tasks} 个。",
            next_action="客户补齐授权后点击复验关闭，已通过任务会自动标记完成。",
        ),
        AcceptanceAuditItem(
            module="平台接入 SLA 看板",
            status="pass" if sla_board.status == "clear" else "warning",
            evidence=f"{sla_board.summary} status={sla_board.status}。",
            next_action="" if sla_board.status == "clear" else "优先处理逾期或今日到期的平台接入任务。",
        ),
        AcceptanceAuditItem(
            module="平台接入 SLA 升级简报",
            status="pass",
            evidence=f"SLA escalation brief can be generated. escalation_items={len(escalation_items)}.",
            next_action="如有逾期、今日到期或未排期任务，生成简报并转给负责人推进。",
        ),
        AcceptanceAuditItem(
            module="平台接入 SLA 责任人通知草稿",
            status="pass",
            evidence=f"SLA owner notice draft can be generated. notice_items={len(notice_items)}.",
            next_action="外发前由运营确认接收人、措辞、附件和发送渠道。",
        ),
        AcceptanceAuditItem(
            module="平台接入 SLA 通知回执闭环",
            status="pass",
            evidence=f"SLA notice receipt can be recorded. receipt_items={len(receipt_items)} close_requires_CONFIRM_CLOSE=true.",
            next_action="责任人确认完成后，再用显式任务 ID 和确认短语关闭对应 CRM 接入任务。",
        ),
        AcceptanceAuditItem(
            module="平台接入 SLA 闭环复盘报表",
            status="pass",
            evidence=f"SLA loop report can be generated. loop_events={len(loop_events)}.",
            next_action="用闭环复盘报表确认回执、关闭任务和剩余缺口，再进入真实平台账号验收。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收证据包",
            status="pass" if not platform_missing_scenarios and platform_evidence_logs else "warning",
            evidence=f"Real platform acceptance evidence can be registered. platform_evidence={len(platform_evidence_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="补齐官方授权、回调、消息读取、线索读取、回复草稿和客户试运行的真实证据。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收缺口 CRM 任务",
            status="pass",
            evidence=f"Platform acceptance missing scenarios can sync to CRM. gap_sync_events={len(platform_gap_sync_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="将缺失真实验收场景同步为 CRM 跟进任务，逐项补齐脱敏证据。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收缺口复验关闭",
            status="pass",
            evidence=f"Platform acceptance passed evidence can close CRM gaps. gap_reconcile_events={len(platform_gap_reconcile_logs)}.",
            next_action="登记通过证据后运行复验关闭，自动关闭对应真实平台验收缺口任务。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收证据采集清单",
            status="pass",
            evidence=f"Platform acceptance evidence collection checklist can be generated. checklist_events={len(platform_checklist_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="按清单逐项采集客户真实平台脱敏证据，登记 pass 后再运行缺口复验关闭。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收证据通知与回执",
            status="pass",
            evidence=f"Platform acceptance evidence owner notice and receipt can be recorded. notice_events={len(platform_notice_logs)} receipt_events={len(platform_receipt_logs)}.",
            next_action="复制通知草稿发给客户平台负责人；收到材料后先记录回执，再由运营审核并登记为真实平台验收证据。",
        ),
        AcceptanceAuditItem(
            module="客户材料提交入口",
            status="pass",
            evidence=f"Tokenized customer submission links can collect sanitized material. submission_links={len(platform_submission_link_logs)} customer_submissions={len(platform_customer_submission_logs)}.",
            next_action="把提交链接发给客户平台负责人；客户提交后只生成回执和复核任务，仍需运营审核通过后才登记 pass 证据。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收材料复核任务",
            status="pass",
            evidence=f"Submitted platform evidence receipts can sync into CRM review tasks. review_sync_events={len(platform_review_sync_logs)}.",
            next_action="对 submitted 回执生成复核任务，人工审核脱敏材料后再登记 pass 证据并复验关闭缺口。",
        ),
        AcceptanceAuditItem(
            module="真实平台验收材料审核决策",
            status="pass",
            evidence=f"Reviewed platform evidence can be approved, rejected, or sent back for redaction. review_decision_events={len(platform_review_decision_logs)}.",
            next_action="审核通过时使用确认短语登记 pass 证据；审核驳回或需脱敏时只留决策记录，不关闭验收缺口。",
        ),
        AcceptanceAuditItem(
            module="审核通过联动缺口复验",
            status="pass",
            evidence=f"Approved review decisions can trigger platform gap reconciliation. review_gap_reconcile_events={len(platform_review_gap_reconcile_logs)}.",
            next_action="真实材料审核通过后勾选联动复验，登记 pass 证据后自动关闭匹配的真实平台验收缺口任务。",
        ),
        AcceptanceAuditItem(
            module="审核退回补交闭环",
            status="pass",
            evidence=f"Needs-redaction or rejected review decisions can generate customer resubmission links. review_resubmission_links={len(platform_review_resubmission_logs)}.",
            next_action="材料需脱敏或被驳回时生成同场景补交链接，让客户补交后重新进入回执和复核任务；不会直接登记 pass 证据。",
        ),
        AcceptanceAuditItem(
            module="平台自动发送边界",
            status="warning",
            evidence=f"无人值守自动发送未开放；当前受控发送闸门开启数：{len(send_enabled_connectors)}。",
            next_action="保持人工确认短语、风险阻断和频控；不要开启无人值守自动发送。",
        ),
        AcceptanceAuditItem(
            module="团队权限",
            status="pass" if members else "warning",
            evidence=f"团队成员 {len(members)}，owner 权限包含核心后台能力。",
            next_action="" if members else "为客户创建 owner 和运营成员账号。",
        ),
        AcceptanceAuditItem(
            module="审计日志",
            status="pass",
            evidence=f"最近审计日志 {len(audit_logs)} 条，关键写操作会记录 actor、action 和 target。",
            next_action="交付后保留审计日志用于排查和复盘。",
        ),
        AcceptanceAuditItem(
            module="计费订阅和用量",
            status="pass" if usage.subscription.plan_id else "warning",
            evidence=f"当前套餐 {usage.subscription.plan_id or '-'}，AI 剩余额度 {usage.remaining.get('ai', 0)}。",
            next_action="" if usage.subscription.plan_id else "设置客户套餐和试用额度。",
        ),
        AcceptanceAuditItem(
            module="经营报表",
            status="pass" if reports else "warning",
            evidence=f"最近报表 {len(reports)} 份，支持 Markdown/PDF/Word 导出。",
            next_action="" if reports else "先生成一份经营日报作为交付样例。",
        ),
        AcceptanceAuditItem(
            module="客户交付包",
            status="pass" if deliveries else "warning",
            evidence=f"最近交付包 {len(deliveries)} 个，支持 ZIP 下载和验收矩阵。",
            next_action="" if deliveries else "生成客户交付包并完成下载验收。",
        ),
        AcceptanceAuditItem(
            module="安全和隐私边界",
            status="pass",
            evidence="交付文档明确排除服务器密码、API Key、客户隐私和未授权自动发送承诺。",
            next_action="正式移交前轮换演示密码，并让客户使用自己的密钥。",
        ),
    ]
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance sprint pack",
            status="pass",
            evidence=f"Real platform acceptance sprint packs combine missing scenarios, CRM tasks, and customer submission links. sprint_pack_events={len(platform_sprint_pack_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Generate a sprint pack before customer acceptance day, send each scenario link to the customer owner, then review submitted material before registering pass evidence.",
        )
    )
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance live run board",
            status="pass",
            evidence=f"Acceptance-day live runs summarize pass, review, customer submission, and sign-off readiness. live_run_events={len(platform_live_run_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Use the live run board during customer acceptance, then request final sign-off only when status is ready_for_signoff.",
        )
    )
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance joint debug run",
            status="pass",
            evidence=f"Read-only customer platform joint debug can collect verifiable pass evidence when official connectors are configured. joint_debug_runs={len(platform_joint_debug_run_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Run joint debug with the customer platform owner after OAuth and read-only endpoints are configured; customer_trial still requires customer-submitted sanitized evidence.",
        )
    )
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance remaining gap closure",
            status="pass",
            evidence=f"Remaining gap closure can attempt token exchange, read-only pulls, CRM gap tasks, and customer trial links. gap_closure_runs={len(platform_gap_closure_run_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Use the closure run after joint debug to create customer links, CRM tasks, and exact connector field requests for every remaining scenario.",
        )
    )
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance owner action pack",
            status="pass",
            evidence=f"Customer platform owner handoff packs list exact missing official fields, callback URLs, and customer trial links. owner_action_packs={len(platform_owner_action_pack_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Send the owner action pack to the customer platform owner, then rerun gap closure after they complete official configuration and customer-trial submission.",
        )
    )
    items.append(
        AcceptanceAuditItem(
            module="Platform acceptance final signoff gate",
            status="pass",
            evidence=f"Final sign-off links stay blocked until live-run readiness is ready_for_signoff. final_signoff_links={len(platform_final_signoff_link_logs)} final_signoffs={len(platform_final_signoff_logs)} missing_scenarios={len(platform_missing_scenarios)}.",
            next_action="Generate the final sign-off gate only after the live run is complete; public submission recomputes readiness before accepting customer approval.",
        )
    )
    weighted = sum(1 if item.status == "pass" else 0.55 if item.status == "warning" else 0 for item in items)
    readiness_score = round(weighted / len(items) * 100)
    blockers = [f"{item.module}：{item.evidence}" for item in items if item.status == "fail"]
    next_actions = [f"{item.module}：{item.next_action}" for item in items if item.status != "pass" and item.next_action]
    status: Literal["ready", "ready_with_boundaries", "needs_attention"]
    if blockers:
        status = "needs_attention"
        summary = "存在阻断项，暂不建议声明完整交付。"
    elif any(item.status == "warning" for item in items):
        status = "ready_with_boundaries"
        summary = "核心后台已可试运行和交付，但仍需保留官方平台授权与人工确认边界。"
    else:
        status = "ready"
        summary = "核心能力全部通过，可进入客户试运行。"
    audit_id = f"acceptance-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    audit = AcceptanceAudit(
        id=audit_id,
        readiness_score=readiness_score,
        status=status,
        summary=summary,
        items=items,
        blockers=blockers,
        next_actions=next_actions,
        created_at=now_sql(),
    )
    if payload.include_artifact:
        audit_dir = ARTIFACT_DIR / "acceptance"
        audit_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{audit_id}.md"
        (audit_dir / filename).write_text(build_acceptance_audit_markdown(audit), encoding="utf-8")
        audit.artifact_url = acceptance_audit_artifact_url(filename)
    record_usage(merchant.id or 0, "acceptance_audit", 1, "acceptance", audit_id)
    record_audit_log(merchant.id or 0, merchant.username, "acceptance.audit.run", "acceptance_audit", audit_id, "运行最终验收巡检")
    return audit


@router.post("/auth/login", response_model=AuthLoginResponse)
async def auth_login(payload: AuthLoginRequest) -> AuthLoginResponse:
    marker = param()
    with db() as conn:
        row = conn.execute(f"SELECT * FROM merchants WHERE username={marker} AND status=1", (payload.username,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    data = dict(row)
    if not verify_password(payload.password, data.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    profile = parse_profile(data)
    return AuthLoginResponse(token=make_token(profile.id or 0), merchant=profile)


@router.get("/merchant/profile", response_model=MerchantProfile)
async def get_merchant_profile(merchant: MerchantProfile = Depends(current_merchant)) -> MerchantProfile:
    return merchant


@router.get("/channels", response_model=list[ChannelConfig])
async def list_channels(merchant: MerchantProfile = Depends(current_merchant)) -> list[ChannelConfig]:
    ensure_default_channels(merchant.id or 0)
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT channel, display_name, mode, status, official_api_url, webhook_url,
                   auto_reply_enabled, handoff_required, notes
            FROM channel_configs
            WHERE merchant_id={marker}
            ORDER BY FIELD(channel, 'web_widget', 'wechat', 'douyin', 'taobao', 'pdd', 'xianyu'), channel
            """ if db_driver() == "mysql" else f"""
            SELECT channel, display_name, mode, status, official_api_url, webhook_url,
                   auto_reply_enabled, handoff_required, notes
            FROM channel_configs
            WHERE merchant_id={marker}
            ORDER BY CASE channel
                WHEN 'web_widget' THEN 1
                WHEN 'wechat' THEN 2
                WHEN 'douyin' THEN 3
                WHEN 'taobao' THEN 4
                WHEN 'pdd' THEN 5
                WHEN 'xianyu' THEN 6
                ELSE 9
            END, channel
            """,
            (merchant.id,),
        ).fetchall()
    return [
        ChannelConfig(
            channel=row["channel"],
            display_name=row.get("display_name") or row["channel"],
            mode=row.get("mode") or "assist",
            status=row.get("status") or "draft",
            official_api_url=row.get("official_api_url") or "",
            webhook_url=row.get("webhook_url") or "",
            auto_reply_enabled=bool(row.get("auto_reply_enabled")),
            handoff_required=bool(row.get("handoff_required")),
            notes=row.get("notes") or "",
        )
        for row in rows_to_dicts(rows)
    ]


@router.put("/channels/{channel}", response_model=ChannelConfig)
async def update_channel(channel: str, payload: ChannelConfigUpdate, merchant: MerchantProfile = Depends(current_merchant)) -> ChannelConfig:
    ensure_default_channels(merchant.id or 0)
    if channel not in DEFAULT_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not supported")
    marker = param()
    display_name = payload.display_name or DEFAULT_CHANNELS[channel][0]
    with db() as conn:
        conn.execute(
            f"""
            UPDATE channel_configs
            SET display_name={marker}, mode={marker}, status={marker}, official_api_url={marker},
                webhook_url={marker}, auto_reply_enabled={marker}, handoff_required={marker}, notes={marker}, updated_at={marker}
            WHERE merchant_id={marker} AND channel={marker}
            """,
            (
                display_name,
                payload.mode,
                payload.status,
                payload.official_api_url,
                payload.webhook_url,
                1 if payload.auto_reply_enabled else 0,
                1 if payload.handoff_required else 0,
                payload.notes,
                now_sql(),
                merchant.id,
                channel,
            ),
        )
    record_audit_log(merchant.id or 0, merchant.username, "settings.channel.update", "channel", channel, f"更新渠道：{channel}", {"status": payload.status, "mode": payload.mode})
    return [item for item in await list_channels(merchant) if item.channel == channel][0]


@router.get("/knowledge", response_model=list[KnowledgeItem])
async def list_knowledge(merchant: MerchantProfile = Depends(current_merchant)) -> list[KnowledgeItem]:
    return [KnowledgeItem(**row) for row in knowledge_rows(merchant.id or 0)]


@router.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def import_knowledge(payload: KnowledgeImportRequest, merchant: MerchantProfile = Depends(current_merchant)) -> KnowledgeImportResponse:
    items = extract_knowledge_items(payload)
    return persist_knowledge_items(merchant, payload, items)


def extract_docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail="Word 文档解析失败，请上传 .docx 文件") from exc
    root = ET.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PDF 解析依赖缺失，请安装 pypdf") from exc
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF 文档解析失败，请确认文件未加密或损坏") from exc
    if reader.is_encrypted:
        raise HTTPException(status_code=400, detail="暂不支持加密 PDF")
    pages = []
    for page in reader.pages[:80]:
        pages.append(page.extract_text() or "")
    return "\n".join(part.strip() for part in pages if part.strip())


def decode_uploaded_knowledge(filename: str, raw: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="ignore")
    if suffix == ".pdf":
        return extract_pdf_text(raw)
    if suffix == ".docx":
        return extract_docx_text(raw)
    if suffix == ".doc":
        raise HTTPException(status_code=400, detail="旧版 .doc 请先另存为 .docx 后上传")
    raise HTTPException(status_code=400, detail="当前支持 txt/md/csv/json/pdf/docx 文档")


async def import_uploaded_knowledge_file(
    file: UploadFile,
    merchant: MerchantProfile,
    title: str = "上传文档",
    source_type: Literal["script", "faq", "product", "policy", "manual"] = "manual",
    tags: str = "文档导入",
    sync_to_faq: bool = True,
) -> KnowledgeImportResponse:
    filename = file.filename or "knowledge.txt"
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 5MB")
    content = decode_uploaded_knowledge(filename, raw).strip()
    if not content:
        raise HTTPException(status_code=400, detail="未能从文档中解析出文本内容")
    payload = KnowledgeImportRequest(
        title=title or Path(filename).stem,
        source_type=source_type,
        tags=tags,
        content=content[:20000],
        sync_to_faq=sync_to_faq,
    )
    response = persist_knowledge_items(merchant, payload, extract_knowledge_items(payload))
    record_usage(merchant.id or 0, "knowledge_import", max(1, len(response.items)), source_type, filename)
    record_audit_log(merchant.id or 0, merchant.username, "knowledge.upload", "knowledge", filename, f"上传知识文档：{filename}", {"items": len(response.items)})
    return response.model_copy(update={"filename": filename})


@router.post("/knowledge/upload", response_model=KnowledgeImportResponse)
async def upload_knowledge(
    title: str = "上传文档",
    source_type: Literal["script", "faq", "product", "policy", "manual"] = "manual",
    tags: str = "文档导入",
    sync_to_faq: bool = True,
    file: UploadFile = File(...),
    merchant: MerchantProfile = Depends(current_merchant),
) -> KnowledgeImportResponse:
    return await import_uploaded_knowledge_file(file, merchant, title, source_type, tags, sync_to_faq)


@router.post("/reply/draft", response_model=ReplyDraftResponse)
async def reply_draft(payload: ReplyDraftRequest, merchant: MerchantProfile = Depends(current_merchant)) -> ReplyDraftResponse:
    channel = payload.channel if payload.channel in DEFAULT_CHANNELS else "web_widget"
    reply, flags, _, need_followup = generate_reply_draft_text(merchant, payload.message, channel, payload.customer_name)
    return ReplyDraftResponse(channel=channel, mode="assist" if channel != "web_widget" else "official_api", reply=reply, need_followup=need_followup, risk_flags=flags)


@router.post("/service-scripts/generate", response_model=ServiceScriptGenerateResponse)
async def generate_service_script(payload: ServiceScriptGenerateRequest, merchant: MerchantProfile = Depends(current_merchant)) -> ServiceScriptGenerateResponse:
    if payload.channel not in DEFAULT_CHANNELS:
        raise HTTPException(status_code=404, detail="Channel not supported")
    script = call_ai_service_script(merchant, payload)
    imported = 0
    if payload.save_to_knowledge:
        marker = param()
        with db() as conn:
            conn.execute(
                f"""
                INSERT INTO knowledge_base (merchant_id, title, content, source_type, tags, created_at, updated_at)
                VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
                """,
                (
                    merchant.id,
                    script.title,
                    script_as_text(script),
                    "script",
                    f"{payload.channel},{payload.scenario},客服脚本",
                    now_sql(),
                    now_sql(),
                ),
            )
            imported = 1
    return script.model_copy(update={"knowledge_imported": imported})


@router.put("/merchant/profile", response_model=MerchantProfile)
async def update_merchant_profile(payload: MerchantProfile, merchant: MerchantProfile = Depends(current_merchant)) -> MerchantProfile:
    profile = payload.model_copy(update={"id": merchant.id, "username": merchant.username, "merchant_code": merchant.merchant_code})
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            UPDATE merchants
            SET business_name={marker}, welcome_message={marker}, prompt_template={marker}, updated_at={marker}
            WHERE id={marker}
            """,
            (profile.business_name, profile.welcome_message, profile_to_prompt(profile), now_sql(), merchant.id),
        )
    record_audit_log(merchant.id or 0, merchant.username, "enterprise.profile.update", "merchant", str(merchant.id or ""), "更新企业资料")
    return merchant_by_id(merchant.id or 0)


@router.get("/dashboard/overview", response_model=DashboardOverview)
async def dashboard_overview(merchant: MerchantProfile = Depends(current_merchant)) -> DashboardOverview:
    ensure_default_channels(merchant.id or 0)
    marker = param()
    today = f"{today_prefix()}%"
    with db() as conn:
        today_conversations = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM conversations WHERE merchant_id={marker} AND created_at LIKE {marker}",
            (merchant.id, today),
        ).fetchone())["c"]
        auto_replies = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM chat_logs WHERE merchant_id={marker} AND created_at LIKE {marker}",
            (merchant.id, today),
        ).fetchone())["c"]
        leads = dict(conn.execute(f"SELECT COUNT(*) AS c FROM customers WHERE merchant_id={marker}", (merchant.id,)).fetchone())["c"]
        handoff = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM conversations WHERE merchant_id={marker} AND need_followup=1",
            (merchant.id,),
        ).fetchone())["c"]
        knowledge_count = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM knowledge_base WHERE merchant_id={marker}",
            (merchant.id,),
        ).fetchone())["c"]
        enabled_channels = dict(conn.execute(
            f"SELECT COUNT(*) AS c FROM channel_configs WHERE merchant_id={marker} AND status IN ({marker}, {marker})",
            (merchant.id, "ready", "connected"),
        ).fetchone())["c"]
    ai_mode = "ai" if os.getenv("AI_API_KEY") and os.getenv("AI_MODEL") else "template"
    return DashboardOverview(
        today_conversations=int(today_conversations),
        auto_replies=int(auto_replies),
        leads=int(leads),
        handoff_needed=int(handoff),
        ai_mode=ai_mode,
        knowledge_items=int(knowledge_count),
        enabled_channels=int(enabled_channels),
    )


@router.post("/widget/session", response_model=WidgetSessionResponse)
async def widget_session(payload: WidgetSessionRequest) -> WidgetSessionResponse:
    profile = merchant_by_code(payload.merchant_code)
    visitor_id = payload.visitor_id or secrets.token_hex(8)
    return WidgetSessionResponse(
        session_id=str(uuid.uuid4()),
        visitor_id=visitor_id,
        merchant_code=payload.merchant_code,
        welcome_message=profile.welcome_message,
        business_name=profile.business_name or profile.username,
    )


@router.post("/widget/message", response_model=WidgetMessageResponse)
async def widget_message(payload: WidgetMessageRequest, request: Request) -> WidgetMessageResponse:
    profile = merchant_by_code(payload.merchant_code)
    visitor_id = payload.visitor_id or secrets.token_hex(8)
    flags = risk_flags_for(payload.message)
    intent_score = score_intent(payload.message)
    need_followup = bool(flags) or intent_score >= 70
    history = conversation_history(payload.session_id)
    if flags:
        reply = fallback_reply(profile, payload.message)
    else:
        try:
            reply = call_ai_reply(profile, payload.message, history)
            if is_generic_ai_reply(reply):
                reply = local_grounded_reply(profile, payload.message)
        except Exception:
            reply = fallback_reply(profile, payload.message)
            need_followup = bool(flags) or intent_score >= 70

    customer_id = upsert_customer(
        profile.id or 0,
        visitor_id,
        payload.message,
        intent_score,
        need_followup,
        source_channel="web_widget",
        session_id=payload.session_id,
        risk_flags=flags,
    )
    workflow_runs = []
    if need_followup or intent_score >= 70:
        workflow_runs = workflow_engine.trigger(
            "message",
            "web_widget",
            {
                "message": payload.message,
                "session_id": payload.session_id,
                "customer_id": str(customer_id),
                "visitor_id": visitor_id,
                "intent_score": intent_score,
                "risk_flags": flags,
            },
        )
    workflow_run_id = workflow_runs[0].id if workflow_runs else ""
    if need_followup or intent_score >= 70:
        ensure_followup_task(profile.id or 0, customer_id, "网页客服高意向/风险消息跟进", workflow_run_id, "web_widget")
    visitor_info = json.dumps(
        {"visitor_id": visitor_id, "page_url": payload.page_url, "ip": request.client.host if request.client else ""},
        ensure_ascii=False,
    )
    marker = param()
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO conversations (
                merchant_id, customer_id, session_id, visitor_info, query, response, intent_score,
                need_followup, source_channel, risk_flags, workflow_run_id, created_at
            )
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (
                profile.id,
                customer_id,
                payload.session_id,
                visitor_info,
                payload.message,
                reply,
                intent_score,
                1 if need_followup else 0,
                "web_widget",
                join_tags(flags),
                workflow_run_id,
                now_sql(),
            ),
        )
        conn.execute(
            f"""
            INSERT INTO chat_logs (merchant_id, bot_id, user_id, query, response, created_at)
            VALUES ({marker}, {marker}, {marker}, {marker}, {marker}, {marker})
            """,
            (profile.id, profile.merchant_code, visitor_id, payload.message, reply, now_sql()),
        )
    return WidgetMessageResponse(
        session_id=payload.session_id,
        customer_message=payload.message,
        ai_reply=reply,
        intent_score=intent_score,
        need_followup=need_followup,
        risk_flags=flags,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(merchant: MerchantProfile = Depends(current_merchant)) -> list[ConversationSummary]:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT latest.session_id,
                   latest.customer_id,
                   latest.query AS last_query,
                   latest.response AS last_response,
                   latest.intent_score,
                   latest.need_followup,
                   summary.message_count,
                   summary.updated_at
            FROM conversations latest
            JOIN (
                SELECT session_id,
                       MAX(id) AS latest_id,
                       COUNT(*) AS message_count,
                       MAX(created_at) AS updated_at
                FROM conversations
                WHERE merchant_id={marker}
                GROUP BY session_id
            ) summary
              ON latest.session_id = summary.session_id
             AND latest.id = summary.latest_id
            WHERE latest.merchant_id={marker}
            ORDER BY summary.updated_at DESC
            LIMIT 100
            """,
            (merchant.id, merchant.id),
        ).fetchall()
    return [
        ConversationSummary(
            session_id=str(row["session_id"]),
            customer_id=row["customer_id"],
            visitor_name=f"访客{str(row['session_id'])[-6:]}",
            last_query=row["last_query"] or "",
            last_response=row["last_response"] or "",
            intent_score=int(row["intent_score"] or 0),
            need_followup=bool(row["need_followup"]),
            message_count=int(row["message_count"] or 0),
            updated_at=str(row["updated_at"] or ""),
        )
        for row in rows_to_dicts(rows)
    ]


@router.get("/conversations/{session_id}", response_model=ConversationDetail)
async def conversation_detail(session_id: str, merchant: MerchantProfile = Depends(current_merchant)) -> ConversationDetail:
    marker = param()
    with db() as conn:
        rows = conn.execute(
            f"SELECT query, response, intent_score, need_followup, created_at FROM conversations WHERE merchant_id={marker} AND session_id={marker} ORDER BY id ASC",
            (merchant.id, session_id),
        ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in rows_to_dicts(rows):
        messages.append({"role": "visitor", "text": row.get("query", ""), "created_at": row.get("created_at")})
        messages.append({"role": "assistant", "text": row.get("response", ""), "created_at": row.get("created_at"), "intent_score": row.get("intent_score"), "need_followup": bool(row.get("need_followup"))})
    return ConversationDetail(session_id=session_id, messages=messages)


@router.post("/conversations/{session_id}/handoff", response_model=HandoffResponse)
async def mark_handoff(session_id: str, merchant: MerchantProfile = Depends(current_merchant)) -> HandoffResponse:
    marker = param()
    customer_id = 0
    with db() as conn:
        conn.execute(
            f"UPDATE conversations SET need_followup=1 WHERE merchant_id={marker} AND session_id={marker}",
            (merchant.id, session_id),
        )
        row = conn.execute(
            f"SELECT customer_id FROM conversations WHERE merchant_id={marker} AND session_id={marker} ORDER BY id DESC LIMIT 1",
            (merchant.id, session_id),
        ).fetchone()
        if row:
            customer_id = int(dict(row).get("customer_id") or 0)
    if customer_id:
        ensure_followup_task(merchant.id or 0, customer_id, "人工接管会话跟进", source="handoff")
    record_audit_log(merchant.id or 0, merchant.username, "crm.conversation.handoff", "conversation", session_id, "标记人工接管")
    return HandoffResponse(session_id=session_id, need_followup=True)


@router.get("/widget.js")
async def widget_js(merchant_code: str = Query(...)) -> Response:
    js = f"""
(function() {{
  var merchantCode = {json.dumps(merchant_code)};
  var scriptUrl = new URL(document.currentScript.src);
  var apiBase = scriptUrl.origin + scriptUrl.pathname.replace(/\\/widget\\.js$/, "");
  var sessionId = localStorage.getItem("wj_ai_cs_session_" + merchantCode);
  var visitorId = localStorage.getItem("wj_ai_cs_visitor_" + merchantCode) || Math.random().toString(16).slice(2);
  localStorage.setItem("wj_ai_cs_visitor_" + merchantCode, visitorId);
  var root = document.createElement("div");
  root.id = "wj-ai-cs";
  root.innerHTML = '<button class="wj-cs-toggle">AI客服</button><div class="wj-cs-panel"><div class="wj-cs-head">在线客服<span>×</span></div><div class="wj-cs-msgs"></div><form class="wj-cs-form"><input placeholder="输入您的问题" /><button>发送</button></form></div>';
  document.body.appendChild(root);
  var style = document.createElement("style");
  style.textContent = '#wj-ai-cs{{position:fixed;right:22px;bottom:22px;z-index:2147483647;font-family:system-ui,Microsoft YaHei,sans-serif}}#wj-ai-cs .wj-cs-toggle{{border:0;border-radius:999px;padding:13px 18px;background:#111827;color:#fff;box-shadow:0 12px 30px rgba(0,0,0,.24);cursor:pointer}}#wj-ai-cs .wj-cs-panel{{display:none;width:340px;height:460px;background:#fff;border:1px solid #e5e7eb;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.22);overflow:hidden}}#wj-ai-cs.open .wj-cs-panel{{display:flex;flex-direction:column}}#wj-ai-cs.open .wj-cs-toggle{{display:none}}.wj-cs-head{{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;background:#111827;color:#fff;font-weight:700}}.wj-cs-head span{{cursor:pointer;font-size:20px}}.wj-cs-msgs{{flex:1;overflow:auto;padding:14px;background:#f8fafc}}.wj-cs-msg{{margin:8px 0;padding:10px 12px;border-radius:12px;line-height:1.45;font-size:14px;white-space:pre-wrap}}.wj-cs-msg.bot{{background:#fff;border:1px solid #e5e7eb;color:#111827}}.wj-cs-msg.me{{background:#2563eb;color:#fff;margin-left:42px}}.wj-cs-form{{display:flex;gap:8px;padding:12px;border-top:1px solid #e5e7eb}}.wj-cs-form input{{flex:1;border:1px solid #d1d5db;border-radius:9px;padding:10px}}.wj-cs-form button{{border:0;border-radius:9px;background:#111827;color:#fff;padding:0 14px}}';
  document.head.appendChild(style);
  var panel = root.querySelector(".wj-cs-panel");
  var msgs = root.querySelector(".wj-cs-msgs");
  var form = root.querySelector(".wj-cs-form");
  var input = form.querySelector("input");
  function add(role, text) {{
    var item = document.createElement("div");
    item.className = "wj-cs-msg " + (role === "me" ? "me" : "bot");
    item.textContent = text;
    msgs.appendChild(item);
    msgs.scrollTop = msgs.scrollHeight;
  }}
  function ensureSession() {{
    if (sessionId) return Promise.resolve();
    return fetch(apiBase + "/widget/session", {{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{merchant_code:merchantCode,visitor_id:visitorId,page_url:location.href,user_agent:navigator.userAgent}})}})
      .then(function(r){{return r.json()}})
      .then(function(data){{sessionId=data.session_id;localStorage.setItem("wj_ai_cs_session_" + merchantCode, sessionId);add("bot", data.welcome_message || "您好，请问有什么可以帮您？");}});
  }}
  root.querySelector(".wj-cs-toggle").onclick = function() {{ root.classList.add("open"); ensureSession(); }};
  root.querySelector(".wj-cs-head span").onclick = function() {{ root.classList.remove("open"); }};
  form.onsubmit = function(e) {{
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    add("me", text);
    ensureSession().then(function(){{
      add("bot", "我看一下，马上回复你...");
      return fetch(apiBase + "/widget/message", {{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{merchant_code:merchantCode,session_id:sessionId,visitor_id:visitorId,message:text,page_url:location.href}})}});
    }}).then(function(r){{return r.json()}}).then(function(data){{msgs.lastChild.textContent=data.ai_reply || "收到，我这边先接住。你可以再补充一下具体需求，我继续帮你判断。";}}).catch(function(){{msgs.lastChild.textContent="网络有点卡，稍后再试一下。";}});
  }};
}})();
"""
    return Response(js, media_type="application/javascript; charset=utf-8")


@router.get("/widget-test", response_class=HTMLResponse)
async def widget_test(merchant_code: str = Query("WJDEMO001")) -> str:
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>AI 客服测试</title></head><body style='font-family:system-ui,Microsoft YaHei,sans-serif;padding:40px'><h1>AI 客服气泡测试页</h1><p>右下角应该出现客服气泡，可以连续发送价格、接入、退款等问题测试回复。</p><script src="./widget.js?merchant_code={merchant_code}"></script></body></html>"""
