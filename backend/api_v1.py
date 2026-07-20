from __future__ import annotations

import html
import json
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.customer_service_saas import (
    AcceptanceAuditRequest,
    AuthLoginRequest,
    ChannelConfigUpdate,
    CRMLeadCreate,
    CRMLeadUpdate,
    CRMTaskCreate,
    CRMTaskUpdate,
    ConnectorAuthUpdate,
    ConnectorInboundLeadRequest,
    ConnectorInboundMessageRequest,
    ConnectorOAuthExchangeRequest,
    ConnectorOAuthRefreshRequest,
    ConnectorOAuthStartRequest,
    ConnectorReadPullRequest,
    ConnectorSendGateUpdate,
    DeliveryPackGenerateRequest,
    decode_platform_acceptance_customer_room_token,
    decode_platform_acceptance_evidence_manifest_token,
    decode_platform_acceptance_owner_closure_token,
    decode_platform_acceptance_submission_token,
    decode_platform_acceptance_signoff_token,
    IntegrationDryRunRequest,
    IntegrationSLALoopReportRequest,
    IntegrationSLAEscalationRequest,
    IntegrationSLANoticeRequest,
    IntegrationSLANoticeReceiptRequest,
    IntegrationTaskReconcileRequest,
    IntegrationTaskSyncRequest,
    IntegrationWorkOrderRequest,
    KnowledgeImportRequest,
    MerchantProfile,
    PlatformAcceptanceEvidenceChecklistRequest,
    PlatformAcceptanceEvidenceNoticeRequest,
    PlatformAcceptanceEvidenceCustomerSubmissionRequest,
    PlatformAcceptanceEvidenceReceiptRequest,
    PlatformAcceptanceEvidenceReviewDecisionRequest,
    PlatformAcceptanceEvidenceReviewTaskSyncRequest,
    PlatformAcceptanceEvidenceRequest,
    PlatformAcceptanceEvidenceImportRunRequest,
    PlatformAcceptanceEvidenceUrlPrecheckRequest,
    PlatformAcceptanceEvidenceManifestInboxRequest,
    PlatformAcceptanceEvidenceManifestLinkRequest,
    PlatformAcceptanceEvidenceManifestSubmissionRequest,
    PlatformAcceptanceManifestImportQueueRequest,
    PlatformAcceptanceManifestRecoveryReviewRequest,
    PlatformAcceptanceManifestRecoveryResubmissionRunRequest,
    PlatformAcceptanceManifestResubmissionTrackerRequest,
    PlatformAcceptanceManifestResubmissionReminderRunRequest,
    PlatformAcceptanceFinalClosureRunRequest,
    PlatformAcceptanceManifestFollowupRunRequest,
    PlatformAcceptanceEvidenceSubmissionLinkRequest,
    PlatformAcceptanceAutoWatchRunRequest,
    PlatformAcceptanceWatchBoardRequest,
    PlatformAcceptanceCustomerRoomLinkRequest,
    PlatformAcceptanceCustomerRoomReceiptRequest,
    PlatformAcceptanceReviewDeskRequest,
    PlatformAcceptanceReviewExecutionRunRequest,
    PlatformAcceptanceFinalSignoffLinkRequest,
    PlatformAcceptanceFinalSignoffRequest,
    PlatformAcceptanceGapClosureRunRequest,
    PlatformAcceptanceJointDebugRunRequest,
    PlatformAcceptanceLiveRunRequest,
    PlatformAcceptanceOwnerActionPackRequest,
    PlatformAcceptanceOwnerClosureLinkRequest,
    PlatformAcceptanceOwnerClosureSubmissionRequest,
    PlatformAcceptanceOwnerClosureRunRequest,
    PlatformAcceptanceSprintPackRequest,
    PlatformAcceptanceGapReconcileRequest,
    PlatformAcceptanceGapSyncRequest,
    PlatformAcceptanceReportRequest,
    ReportGenerateRequest,
    ReplyDraftQueueCreateRequest,
    ReplyDraftReviewRequest,
    ReplyDispatchCreateRequest,
    ReplyDispatchRevokeRequest,
    ReplyDispatchSendRequest,
    SubscriptionUpdate,
    TeamMemberCreate,
    TeamMemberUpdate,
    auth_login,
    conversation_detail,
    current_subscription,
    create_team_member,
    create_crm_lead,
    create_crm_task,
    create_reply_draft_queue,
    create_reply_dispatch,
    confirm_reply_dispatch_send,
    connector_ops_health,
    connector_setup_guide,
    crm_overview,
    dashboard_overview,
    generate_business_report,
    generate_delivery_pack,
    generate_integration_sla_escalation,
    generate_integration_sla_loop_report,
    generate_integration_sla_notice,
    generate_integration_work_order,
    generate_platform_acceptance_report,
    generate_platform_acceptance_evidence_checklist,
    generate_platform_acceptance_evidence_notice,
    generate_platform_acceptance_evidence_submission_link,
    generate_platform_acceptance_auto_watch_run,
    generate_platform_acceptance_watch_board,
    generate_platform_acceptance_customer_room_link,
    generate_platform_acceptance_evidence_manifest_inbox,
    generate_platform_acceptance_evidence_manifest_link,
    generate_platform_acceptance_manifest_import_queue,
    review_platform_acceptance_manifest_recovery,
    run_platform_acceptance_manifest_recovery_resubmission,
    generate_platform_acceptance_manifest_resubmission_tracker,
    generate_platform_acceptance_manifest_resubmission_reminder_run,
    generate_platform_acceptance_final_closure_run,
    generate_platform_acceptance_manifest_followup_run,
    generate_platform_acceptance_review_desk,
    generate_platform_acceptance_final_signoff_link,
    generate_platform_acceptance_gap_closure_run,
    generate_platform_acceptance_joint_debug_run,
    generate_platform_acceptance_live_run,
    generate_platform_acceptance_owner_action_pack,
    generate_platform_acceptance_owner_closure_link,
    generate_platform_acceptance_owner_closure_run,
    generate_platform_acceptance_sprint_pack,
    export_business_report,
    import_knowledge,
    integration_task_sla_board,
    ingest_connector_lead,
    ingest_connector_message,
    import_uploaded_knowledge_file,
    list_channels,
    list_conversations,
    list_connector_auths,
    list_connector_events,
    list_crm_leads,
    list_crm_tasks,
    list_reply_drafts,
    list_reply_dispatches,
    list_audit_logs,
    list_billing_plans,
    list_business_reports,
    list_knowledge,
    list_team_members,
    latest_delivery_packs,
    list_usage_records,
    mark_handoff,
    merchant_by_code,
    pull_connector_read_api,
    record_integration_sla_notice_receipt,
    record_platform_acceptance_evidence_receipt,
    record_platform_acceptance_evidence_review_decision,
    record_platform_acceptance_evidence,
    record_usage,
    reconcile_integration_tasks,
    refresh_connector_oauth_token,
    reconcile_platform_acceptance_gap_tasks,
    review_reply_draft,
    revoke_reply_dispatch,
    run_integration_dry_run,
    run_acceptance_audit,
    run_platform_acceptance_evidence_url_precheck,
    sync_integration_gaps_to_crm_tasks,
    sync_platform_acceptance_evidence_review_tasks,
    sync_platform_acceptance_gaps_to_crm_tasks,
    submit_platform_acceptance_evidence_material,
    submit_platform_acceptance_owner_closure,
    submit_platform_acceptance_customer_room_receipt,
    submit_platform_acceptance_evidence_manifest,
    submit_platform_acceptance_final_signoff,
    store_platform_acceptance_evidence_manifest_upload,
    exchange_connector_oauth_token,
    start_connector_oauth,
    handle_connector_oauth_callback,
    update_crm_lead,
    update_crm_task,
    update_connector_auth,
    update_connector_send_gate,
    update_channel,
    update_merchant_profile,
    update_subscription,
    update_team_member,
    verify_connector_webhook_signature,
    usage_summary,
    run_daily_report_workflow,
    run_platform_acceptance_evidence_import,
    run_platform_acceptance_review_execution,
)
from backend.desktop_agent import (
    DesktopAgentActionResultRequest,
    DesktopAgentEventRequest,
    DesktopAgentPauseRequest,
    DesktopAgentSessionRequest,
    desktop_agent_logs,
    desktop_agent_state,
    ingest_desktop_agent_event,
    record_desktop_agent_action_result,
    register_desktop_agent_session,
    update_desktop_agent_pause,
)
from backend.platform.api import success_response
from backend.platform.ai_engine import default_ai_engine
from backend.platform.cache import runtime_cache
from backend.platform.connectors import list_connectors
from backend.platform.security import AuthContext, require_auth, require_permission
from backend.platform.workflow import WorkflowTriggerType, workflow_engine


router = APIRouter(prefix="/api/v1", tags=["api-v1"])


class AIRiskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class AIIntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class AISummaryRequest(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)


class AIReplyRequest(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=12000)
    message: str = Field(min_length=1, max_length=5000)
    history: list[dict[str, str]] = Field(default_factory=list)
    fallback_text: str = ""


class AIStructuredContextRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowEventRequest(BaseModel):
    trigger_type: WorkflowTriggerType
    source: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowManualRunRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


def ai_engine_status_payload() -> dict[str, Any]:
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL")
    base_url = os.getenv("AI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    image_key = os.getenv("IMAGE_API_KEY") or api_key
    image_model = os.getenv("IMAGE_MODEL")
    return {
        "chat": {
            "configured": bool(api_key and model),
            "provider": os.getenv("AI_PROVIDER", "openai-compatible"),
            "model": model,
            "base_url_configured": bool(base_url),
        },
        "image": {
            "configured": bool(image_key and image_model),
            "provider": os.getenv("IMAGE_PROVIDER", os.getenv("AI_PROVIDER", "openai-compatible")),
            "model": image_model,
        },
    }


@router.get("/health")
async def v1_health(request: Request):
    return success_response({"status": "ok", "api_version": "v1"}, request)


@router.post("/auth/login")
async def v1_auth_login(payload: AuthLoginRequest, request: Request):
    return success_response(await auth_login(payload), request)


@router.get("/enterprise/profile")
async def v1_enterprise_profile(request: Request, context: AuthContext = Depends(require_permission("enterprise:read"))):
    return success_response(context.merchant, request)


@router.put("/enterprise/profile")
async def v1_update_enterprise_profile(
    payload: MerchantProfile,
    request: Request,
    context: AuthContext = Depends(require_permission("enterprise:write")),
):
    return success_response(await update_merchant_profile(payload, context.merchant), request)


@router.get("/team/members")
async def v1_team_members(request: Request, context: AuthContext = Depends(require_permission("enterprise:read"))):
    return success_response(await list_team_members(context.merchant), request)


@router.post("/team/members")
async def v1_create_team_member(
    payload: TeamMemberCreate,
    request: Request,
    context: AuthContext = Depends(require_permission("team:write")),
):
    return success_response(await create_team_member(payload, context.merchant), request)


@router.patch("/team/members/{member_id}")
async def v1_update_team_member(
    member_id: int,
    payload: TeamMemberUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("team:write")),
):
    return success_response(await update_team_member(member_id, payload, context.merchant), request)


@router.get("/audit/logs")
async def v1_audit_logs(
    request: Request,
    limit: int = 100,
    context: AuthContext = Depends(require_permission("audit:read")),
):
    return success_response(await list_audit_logs(context.merchant, limit=limit), request)


@router.get("/billing/plans")
async def v1_billing_plans(request: Request, context: AuthContext = Depends(require_permission("billing:read"))):
    return success_response(await list_billing_plans(), request)


@router.get("/billing/subscription")
async def v1_billing_subscription(request: Request, context: AuthContext = Depends(require_permission("billing:read"))):
    return success_response(await current_subscription(context.merchant), request)


@router.put("/billing/subscription")
async def v1_update_billing_subscription(
    payload: SubscriptionUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("billing:write")),
):
    return success_response(await update_subscription(payload, context.merchant), request)


@router.get("/billing/usage")
async def v1_billing_usage(request: Request, context: AuthContext = Depends(require_permission("billing:read"))):
    return success_response(await usage_summary(context.merchant), request)


@router.get("/billing/usage/records")
async def v1_billing_usage_records(
    request: Request,
    limit: int = 100,
    context: AuthContext = Depends(require_permission("billing:read")),
):
    return success_response(await list_usage_records(context.merchant, limit=limit), request)


@router.get("/reports")
async def v1_reports(
    request: Request,
    report_type: str = "",
    limit: int = 50,
    context: AuthContext = Depends(require_permission("reports:read")),
):
    return success_response(await list_business_reports(context.merchant, report_type=report_type, limit=limit), request)


@router.post("/reports/generate")
async def v1_generate_report(
    payload: ReportGenerateRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("reports:write")),
):
    return success_response(await generate_business_report(payload, context.merchant), request)


@router.post("/reports/daily/run")
async def v1_run_daily_report_workflow(request: Request, context: AuthContext = Depends(require_permission("reports:write"))):
    return success_response(await run_daily_report_workflow(context.merchant), request)


@router.get("/reports/{report_id}/export")
async def v1_export_report(
    report_id: int,
    request: Request,
    format: Literal["markdown", "pdf", "docx"] = Query("markdown"),
    context: AuthContext = Depends(require_permission("reports:read")),
):
    return success_response(await export_business_report(report_id, context.merchant, format), request)


@router.get("/delivery/packs")
async def v1_delivery_packs(
    request: Request,
    limit: int = 20,
    context: AuthContext = Depends(require_permission("delivery:read")),
):
    return success_response(await latest_delivery_packs(limit=limit), request)


@router.post("/delivery/packs")
async def v1_generate_delivery_pack(
    payload: DeliveryPackGenerateRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("delivery:write")),
):
    return success_response(await generate_delivery_pack(payload, context.merchant), request)


@router.post("/ops/integration-work-order")
async def v1_generate_integration_work_order(
    payload: IntegrationWorkOrderRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_integration_work_order(payload, context.merchant), request)


@router.post("/ops/integration-dry-run")
async def v1_run_integration_dry_run(
    payload: IntegrationDryRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await run_integration_dry_run(payload, context.merchant), request)


@router.post("/ops/integration-task-sync")
async def v1_sync_integration_tasks(
    payload: IntegrationTaskSyncRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await sync_integration_gaps_to_crm_tasks(payload, context.merchant), request)


@router.post("/ops/integration-task-reconcile")
async def v1_reconcile_integration_tasks(
    payload: IntegrationTaskReconcileRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await reconcile_integration_tasks(payload, context.merchant), request)


@router.get("/ops/integration-task-sla")
async def v1_integration_task_sla(
    request: Request,
    context: AuthContext = Depends(require_permission("audit:read")),
):
    return success_response(await integration_task_sla_board(context.merchant), request)


@router.post("/ops/integration-sla-escalation")
async def v1_generate_integration_sla_escalation(
    payload: IntegrationSLAEscalationRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_integration_sla_escalation(payload, context.merchant), request)


@router.post("/ops/integration-sla-notice")
async def v1_generate_integration_sla_notice(
    payload: IntegrationSLANoticeRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_integration_sla_notice(payload, context.merchant), request)


@router.post("/ops/integration-sla-notice-receipt")
async def v1_record_integration_sla_notice_receipt(
    payload: IntegrationSLANoticeReceiptRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await record_integration_sla_notice_receipt(payload, context.merchant), request)


@router.post("/ops/integration-sla-loop-report")
async def v1_generate_integration_sla_loop_report(
    payload: IntegrationSLALoopReportRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_integration_sla_loop_report(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence")
async def v1_record_platform_acceptance_evidence(
    payload: PlatformAcceptanceEvidenceRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await record_platform_acceptance_evidence(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-import")
async def v1_run_platform_acceptance_evidence_import(
    payload: PlatformAcceptanceEvidenceImportRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await run_platform_acceptance_evidence_import(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-url-precheck")
async def v1_run_platform_acceptance_evidence_url_precheck(
    payload: PlatformAcceptanceEvidenceUrlPrecheckRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await run_platform_acceptance_evidence_url_precheck(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-manifest-link")
async def v1_generate_platform_acceptance_evidence_manifest_link(
    payload: PlatformAcceptanceEvidenceManifestLinkRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_evidence_manifest_link(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-manifest-inbox")
async def v1_generate_platform_acceptance_evidence_manifest_inbox(
    payload: PlatformAcceptanceEvidenceManifestInboxRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_evidence_manifest_inbox(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-import-queue")
async def v1_generate_platform_acceptance_manifest_import_queue(
    payload: PlatformAcceptanceManifestImportQueueRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_manifest_import_queue(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-recovery-review")
async def v1_review_platform_acceptance_manifest_recovery(
    payload: PlatformAcceptanceManifestRecoveryReviewRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await review_platform_acceptance_manifest_recovery(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-recovery-resubmission")
async def v1_run_platform_acceptance_manifest_recovery_resubmission(
    payload: PlatformAcceptanceManifestRecoveryResubmissionRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await run_platform_acceptance_manifest_recovery_resubmission(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-resubmission-tracker")
async def v1_generate_platform_acceptance_manifest_resubmission_tracker(
    payload: PlatformAcceptanceManifestResubmissionTrackerRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_manifest_resubmission_tracker(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-resubmission-reminder")
async def v1_generate_platform_acceptance_manifest_resubmission_reminder_run(
    payload: PlatformAcceptanceManifestResubmissionReminderRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_manifest_resubmission_reminder_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-manifest-followup-run")
async def v1_generate_platform_acceptance_manifest_followup_run(
    payload: PlatformAcceptanceManifestFollowupRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_manifest_followup_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-report")
async def v1_generate_platform_acceptance_report(
    payload: PlatformAcceptanceReportRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_report(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-gap-sync")
async def v1_sync_platform_acceptance_gaps(
    payload: PlatformAcceptanceGapSyncRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await sync_platform_acceptance_gaps_to_crm_tasks(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-gap-reconcile")
async def v1_reconcile_platform_acceptance_gaps(
    payload: PlatformAcceptanceGapReconcileRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await reconcile_platform_acceptance_gap_tasks(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-checklist")
async def v1_generate_platform_acceptance_evidence_checklist(
    payload: PlatformAcceptanceEvidenceChecklistRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_evidence_checklist(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-notice")
async def v1_generate_platform_acceptance_evidence_notice(
    payload: PlatformAcceptanceEvidenceNoticeRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_evidence_notice(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-submission-link")
async def v1_generate_platform_acceptance_evidence_submission_link(
    payload: PlatformAcceptanceEvidenceSubmissionLinkRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_evidence_submission_link(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-sprint-pack")
async def v1_generate_platform_acceptance_sprint_pack(
    payload: PlatformAcceptanceSprintPackRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_sprint_pack(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-live-run")
async def v1_generate_platform_acceptance_live_run(
    payload: PlatformAcceptanceLiveRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_live_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-joint-debug-run")
async def v1_generate_platform_acceptance_joint_debug_run(
    payload: PlatformAcceptanceJointDebugRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_joint_debug_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-gap-closure-run")
async def v1_generate_platform_acceptance_gap_closure_run(
    payload: PlatformAcceptanceGapClosureRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_gap_closure_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-owner-action-pack")
async def v1_generate_platform_acceptance_owner_action_pack(
    payload: PlatformAcceptanceOwnerActionPackRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_owner_action_pack(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-owner-closure-link")
async def v1_generate_platform_acceptance_owner_closure_link(
    payload: PlatformAcceptanceOwnerClosureLinkRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_owner_closure_link(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-owner-closure-run")
async def v1_generate_platform_acceptance_owner_closure_run(
    payload: PlatformAcceptanceOwnerClosureRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_owner_closure_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-auto-watch-run")
async def v1_generate_platform_acceptance_auto_watch_run(
    payload: PlatformAcceptanceAutoWatchRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_auto_watch_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-final-closure-run")
async def v1_generate_platform_acceptance_final_closure_run(
    payload: PlatformAcceptanceFinalClosureRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_final_closure_run(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-watch-board")
async def v1_generate_platform_acceptance_watch_board(
    payload: PlatformAcceptanceWatchBoardRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_watch_board(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-customer-room-link")
async def v1_generate_platform_acceptance_customer_room_link(
    payload: PlatformAcceptanceCustomerRoomLinkRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_customer_room_link(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-final-signoff-link")
async def v1_generate_platform_acceptance_final_signoff_link(
    payload: PlatformAcceptanceFinalSignoffLinkRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_final_signoff_link(payload, context.merchant), request)


@router.get("/public/platform-acceptance-customer-room", response_class=HTMLResponse)
async def v1_platform_acceptance_customer_room(token: str = ""):
    if not token:
        return HTMLResponse("<h1>Missing customer room token</h1>", status_code=400)
    try:
        data = decode_platform_acceptance_customer_room_token(token)
    except HTTPException as exc:
        detail = html.escape(str(exc.detail))
        return HTMLResponse(f"<h1>Customer room unavailable</h1><p>{detail}</p>", status_code=exc.status_code)
    customer_name = html.escape(str(data.get("customer_name") or "customer"))
    recipient = html.escape(str(data.get("recipient") or "customer platform owner"))
    owner = html.escape(str(data.get("owner") or "operations reviewer"))
    evidence_status = html.escape(str(data.get("evidence_status") or "unknown"))
    final_gate_status = html.escape(str(data.get("final_gate_status") or "blocked"))
    expires_at = html.escape(str(data.get("expires_at") or ""))
    scenarios = data.get("missing_scenarios") or []
    token_json = json.dumps(token)
    scenarios_json = json.dumps([str(scenario) for scenario in scenarios])
    scenario_items = "\n".join(f"<li>{html.escape(str(scenario))}</li>" for scenario in scenarios) or "<li>none</li>"
    evidence_url = html.escape(str(data.get("evidence_submission_url") or ""))
    closure_url = html.escape(str(data.get("owner_closure_url") or ""))
    signoff_url = html.escape(str(data.get("final_signoff_url") or ""))
    watch_url = html.escape(str(data.get("watch_board_url") or ""))
    signoff_button = (
        f'<a class="button primary" href="{signoff_url}" target="_blank" rel="noopener noreferrer">Open final sign-off</a>'
        if signoff_url
        else '<span class="button disabled">Final sign-off blocked</span>'
    )
    watch_button = (
        f'<a class="button" href="{watch_url}" target="_blank" rel="noopener noreferrer">Open watch board</a>'
        if watch_url
        else '<span class="button disabled">Watch board unavailable</span>'
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Acceptance Room</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #14171f; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 32px 18px; }}
    section {{ background: #fff; border: 1px solid #dde1e7; border-radius: 8px; padding: 20px; margin: 16px 0; }}
    .meta, .notice {{ color: #4d5665; }}
    .notice {{ border-left: 4px solid #1769e0; padding: 10px 12px; background: #eef5ff; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .tile {{ border: 1px solid #e1e5eb; border-radius: 8px; padding: 14px; }}
    .tile strong {{ display: block; margin-bottom: 6px; }}
    .button {{ display: inline-flex; align-items: center; justify-content: center; margin: 6px 6px 0 0; border-radius: 6px; padding: 10px 12px; background: #1769e0; color: #fff; text-decoration: none; font-weight: 700; }}
    .button.primary {{ background: #0c7a43; }}
    .button.disabled {{ background: #c1c7d0; color: #323946; }}
    form {{ display: grid; gap: 14px; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #c8ced8; border-radius: 6px; padding: 10px 12px; font: inherit; }}
    textarea {{ min-height: 110px; resize: vertical; }}
    button {{ width: fit-content; border: 0; border-radius: 6px; background: #1769e0; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #101724; color: #dce7ff; border-radius: 6px; padding: 12px; }}
    code {{ word-break: break-all; }}
  </style>
</head>
<body>
  <main>
    <h1>Real Platform Acceptance Room</h1>
    <p class="meta">Customer: {customer_name} · Recipient: {recipient} · Owner: {owner} · Expires: {expires_at}</p>
    <p class="notice">Use the links below for platform acceptance only. Do not send passwords, tokens, cookies, verification codes, raw signatures, session keys, or API secrets in chat, screenshots, documents, or email bodies.</p>
    <section>
      <h2>Current Status</h2>
      <div class="grid">
        <div class="tile"><strong>Evidence status</strong><span>{evidence_status}</span></div>
        <div class="tile"><strong>Final gate</strong><span>{final_gate_status}</span></div>
        <div class="tile"><strong>Missing scenarios</strong><span>{len(scenarios)}</span></div>
      </div>
      <ul>{scenario_items}</ul>
    </section>
    <section>
      <h2>Actions</h2>
      <a class="button" href="{evidence_url}" target="_blank" rel="noopener noreferrer">Submit sanitized evidence</a>
      <a class="button" href="{closure_url}" target="_blank" rel="noopener noreferrer">Submit secure platform config</a>
      {signoff_button}
      {watch_button}
    </section>
    <section>
      <h2>Room Receipt</h2>
      <form id="receipt-form">
        <div class="grid">
          <label>Submitter<input id="submitter" required value="{recipient}" /></label>
          <label>Outcome
            <select id="outcome">
              <option value="acknowledged">Acknowledged</option>
              <option value="submitted">Submitted material</option>
              <option value="needs_help">Needs help</option>
            </select>
          </label>
        </div>
        <label>Sanitized note<textarea id="notes" placeholder="Confirm what you reviewed or what help you need. Do not include secrets or private customer data."></textarea></label>
        <label><span><input id="confirm" type="checkbox" required /> I confirm this receipt contains no passwords, tokens, cookies, verification codes, raw signatures, session keys, API secrets, or private customer data.</span></label>
        <button type="submit">Record receipt</button>
      </form>
      <pre id="receipt-result">Waiting for customer receipt.</pre>
    </section>
    <section>
      <h2>Boundaries</h2>
      <p>Submitting material does not automatically pass final acceptance. Operations must review sanitized evidence, and the server will recompute the final gate before sign-off is accepted.</p>
    </section>
  </main>
  <script>
    const roomToken = {token_json};
    const missingScenarios = {scenarios_json};
    const receiptResult = document.getElementById('receipt-result');
    const read = (id) => document.getElementById(id).value.trim();
    document.getElementById('receipt-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const outcome = read('outcome');
      const notes = read('notes') || 'Acceptance room receipt recorded.';
      const scenario_receipts = missingScenarios.map((scenario) => ({{
        scenario,
        outcome,
        note: notes,
        evidence_url: ''
      }}));
      const payload = {{
        token: roomToken,
        submitter: read('submitter'),
        outcome,
        scenario_receipts,
        notes,
        include_artifact: true,
        create_review_tasks: true,
        no_secrets_confirmed: document.getElementById('confirm').checked
      }};
      receiptResult.textContent = 'Recording receipt...';
      const response = await fetch(window.location.pathname.replace('platform-acceptance-customer-room', 'platform-acceptance-customer-room-receipt'), {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const body = await response.json();
      if (!response.ok || !body.ok) {{
        receiptResult.textContent = 'Blocked or failed: ' + JSON.stringify(body, null, 2);
        return;
      }}
      const data = body.data;
      receiptResult.textContent = 'Recorded: ' + data.id + '\\nStatus: ' + data.status + '\\nOutcome: ' + data.outcome + '\\nReview sync: ' + (data.review_sync ? data.review_sync.id : 'not needed');
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/public/platform-acceptance-customer-room-receipt")
async def v1_submit_platform_acceptance_customer_room_receipt(
    payload: PlatformAcceptanceCustomerRoomReceiptRequest,
    request: Request,
):
    return success_response(await submit_platform_acceptance_customer_room_receipt(payload), request)


@router.get("/public/platform-acceptance-evidence-manifest", response_class=HTMLResponse)
async def v1_platform_acceptance_evidence_manifest_form(token: str = ""):
    if not token:
        return HTMLResponse("<h1>Missing evidence manifest token</h1>", status_code=400)
    try:
        data = decode_platform_acceptance_evidence_manifest_token(token)
    except HTTPException as exc:
        detail = html.escape(str(exc.detail))
        return HTMLResponse(f"<h1>Evidence manifest unavailable</h1><p>{detail}</p>", status_code=exc.status_code)
    token_json = json.dumps(token)
    scenarios = data.get("scenarios") or []
    scenarios_json = json.dumps([str(scenario) for scenario in scenarios])
    customer_name = html.escape(str(data.get("customer_name") or "customer"))
    recipient = html.escape(str(data.get("recipient") or "customer platform owner"))
    owner = html.escape(str(data.get("owner") or "operations reviewer"))
    expires_at = html.escape(str(data.get("expires_at") or ""))
    scenario_fields = "\n".join(
        f"""
        <section class="scenario" data-scenario="{html.escape(str(scenario))}">
          <h2>{html.escape(str(scenario))}</h2>
          <label>Sanitized evidence URL<input class="evidence-url" placeholder="https://..." /></label>
          <label>Or upload sanitized evidence file<input class="evidence-file" type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.md,.json,.csv,.docx,image/png,image/jpeg,image/webp,application/pdf,text/plain,text/markdown,application/json,text/csv,application/vnd.openxmlformats-officedocument.wordprocessingml.document" /></label>
          <button class="upload-button" type="button">Upload file for this scenario</button>
          <small class="upload-status">No file uploaded.</small>
          <label>Sanitized note<textarea class="evidence-note" placeholder="Describe what this proof shows. Do not include secrets or private customer data."></textarea></label>
        </section>
        """
        for scenario in scenarios
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Evidence Manifest</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #14171f; }}
    main {{ max-width: 860px; margin: 0 auto; padding: 32px 18px; }}
    .notice {{ border-left: 4px solid #1769e0; padding: 10px 12px; background: #eef5ff; color: #4d5665; }}
    form, .scenario {{ display: grid; gap: 14px; }}
    .scenario {{ background: #fff; border: 1px solid #dde1e7; border-radius: 8px; padding: 18px; margin: 16px 0; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #c8ced8; border-radius: 6px; padding: 10px 12px; font: inherit; }}
    textarea {{ min-height: 92px; resize: vertical; }}
    button {{ width: fit-content; border: 0; border-radius: 6px; background: #1769e0; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    button.secondary {{ background: #39465d; }}
    small {{ color: #4d5665; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #101724; color: #dce7ff; border-radius: 6px; padding: 12px; }}
    .meta {{ color: #4d5665; }}
  </style>
</head>
<body>
  <main>
    <h1>Real Platform Evidence Manifest</h1>
    <p class="meta">Customer: {customer_name} · Recipient: {recipient} · Owner: {owner} · Expires: {expires_at}</p>
    <p class="notice">Submit only sanitized customer-controlled evidence URLs. Do not include passwords, tokens, cookies, verification codes, raw signatures, session keys, API secrets, or private customer data. This form creates an import preview and review tasks; it does not pass final acceptance.</p>
    <form id="manifest-form">
      <label>Submitter<input id="submitter" required value="{recipient}" /></label>
      {scenario_fields}
      <label>General note<textarea id="notes" placeholder="Optional sanitized context for operations."></textarea></label>
      <label><span><input id="confirm" type="checkbox" required /> I confirm the URLs and notes contain no secrets or private customer data.</span></label>
      <button type="submit">Submit evidence manifest</button>
    </form>
    <pre id="result">Waiting for sanitized evidence URLs for {len(scenarios)} scenario(s).</pre>
  </main>
  <script>
    const signedCode = {token_json};
    const scenarioNames = {scenarios_json};
    const result = document.getElementById('result');
    const read = (root, selector) => root.querySelector(selector).value.trim();
    document.querySelectorAll('.upload-button').forEach((button) => {{
      button.addEventListener('click', async () => {{
        const section = button.closest('.scenario');
        const fileInput = section.querySelector('.evidence-file');
        const status = section.querySelector('.upload-status');
        const file = fileInput.files && fileInput.files[0];
        if (!file) {{
          status.textContent = 'Choose a sanitized file first.';
          return;
        }}
        const form = new FormData();
        form.append('token', signedCode);
        form.append('scenario', section.dataset.scenario);
        form.append('submitter', document.getElementById('submitter').value.trim() || 'customer platform owner');
        form.append('evidence_note', read(section, '.evidence-note'));
        form.append('no_secrets_confirmed', document.getElementById('confirm').checked ? 'true' : 'false');
        form.append('file', file);
        status.textContent = 'Uploading sanitized file...';
        const response = await fetch(window.location.pathname.replace('platform-acceptance-evidence-manifest', 'platform-acceptance-evidence-manifest-upload'), {{
          method: 'POST',
          body: form
        }});
        const body = await response.json();
        if (!response.ok || !body.ok) {{
          status.textContent = 'Upload blocked or failed: ' + JSON.stringify(body);
          return;
        }}
        section.querySelector('.evidence-url').value = body.data.evidence_url;
        status.textContent = 'Uploaded: ' + body.data.filename + ' (' + body.data.size_bytes + ' bytes). URL filled above.';
      }});
    }});
    document.getElementById('manifest-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const submitter = document.getElementById('submitter').value.trim();
      const items = Array.from(document.querySelectorAll('.scenario')).map((section) => {{
        const scenario = section.dataset.scenario;
        return {{
          scenario,
          connector: 'website',
          account_label: 'customer platform account',
          operator: submitter || 'customer platform owner',
          evidence_note: read(section, '.evidence-note'),
          evidence_url: read(section, '.evidence-url'),
          review_task_ids: []
        }};
      }});
      const payload = {{
        submitter,
        items,
        notes: document.getElementById('notes').value.trim(),
        include_artifact: true,
        create_review_tasks: true,
        no_secrets_confirmed: document.getElementById('confirm').checked
      }};
      payload['token'] = signedCode;
      result.textContent = 'Submitting manifest preview...';
      const response = await fetch(window.location.pathname, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const body = await response.json();
      if (!response.ok || !body.ok) {{
        result.textContent = 'Blocked or failed: ' + JSON.stringify(body, null, 2);
        return;
      }}
      const data = body.data;
      result.textContent = 'Recorded: ' + data.id + '\\nStatus: ' + data.status + '\\nReady: ' + data.ready + '\\nBlocked: ' + data.blocked + '\\nMissing: ' + data.missing_scenarios.join(', ');
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/public/platform-acceptance-evidence-manifest-upload")
async def v1_upload_platform_acceptance_evidence_manifest_file(
    request: Request,
    token: str = Form(...),
    scenario: str = Form(...),
    submitter: str = Form("customer platform owner"),
    evidence_note: str = Form(""),
    no_secrets_confirmed: bool = Form(True),
    file: UploadFile = File(...),
):
    return success_response(
        await store_platform_acceptance_evidence_manifest_upload(
            token=token,
            scenario=scenario,
            submitter=submitter,
            evidence_note=evidence_note,
            no_secrets_confirmed=no_secrets_confirmed,
            file=file,
        ),
        request,
    )


@router.post("/public/platform-acceptance-evidence-manifest")
async def v1_submit_platform_acceptance_evidence_manifest(
    payload: PlatformAcceptanceEvidenceManifestSubmissionRequest,
    request: Request,
):
    return success_response(await submit_platform_acceptance_evidence_manifest(payload), request)


@router.get("/public/platform-acceptance-final-signoff", response_class=HTMLResponse)
async def v1_platform_acceptance_final_signoff_form(signed_code: str = Query(default="", alias="token")):
    if not signed_code:
        return HTMLResponse("<h1>Missing sign-off token</h1>", status_code=400)
    try:
        data = decode_platform_acceptance_signoff_token(signed_code)
    except HTTPException as exc:
        detail = html.escape(str(exc.detail))
        return HTMLResponse(f"<h1>Sign-off link unavailable</h1><p>{detail}</p>", status_code=exc.status_code)
    signed_code_json = json.dumps(signed_code)
    signer_name = html.escape(str(data.get("signer_name") or "customer platform owner"))
    signer_role = html.escape(str(data.get("signer_role") or "platform owner"))
    customer_name = html.escape(str(data.get("customer_name") or "customer"))
    expires_at = html.escape(str(data.get("expires_at") or ""))
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Final Acceptance Sign-off</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #14171f; }}
    main {{ max-width: 720px; margin: 0 auto; padding: 32px 18px; }}
    form {{ display: grid; gap: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; padding: 20px; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #c8ced8; border-radius: 6px; padding: 10px 12px; font: inherit; }}
    textarea {{ min-height: 120px; resize: vertical; }}
    button {{ width: fit-content; border: 0; border-radius: 6px; background: #1769e0; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    .meta, .notice, pre {{ color: #4d5665; }}
    .notice {{ border-left: 4px solid #1769e0; padding: 10px 12px; background: #eef5ff; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #101724; color: #dce7ff; border-radius: 6px; padding: 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>Final Acceptance Sign-off</h1>
    <p class="meta">Customer: {customer_name} · Expires: {expires_at}</p>
    <p class="notice">This page accepts final sign-off only after the server recomputes live-run readiness as ready_for_signoff. Do not enter passwords, tokens, cookies, verification codes, signatures, or API secrets.</p>
    <form id="signoff-form">
      <label>Signer name<input id="signer_name" required value="{signer_name}" /></label>
      <label>Signer role<input id="signer_role" required value="{signer_role}" /></label>
      <label>Decision
        <select id="decision">
          <option value="accepted">Accepted</option>
          <option value="needs_changes">Needs changes</option>
        </select>
      </label>
      <label>Notes<textarea id="notes" placeholder="Sanitized final acceptance note only"></textarea></label>
      <label><span><input id="confirm" type="checkbox" required /> I confirm this sign-off contains no passwords, tokens, cookies, verification codes, signatures, or API secrets.</span></label>
      <button type="submit">Submit sign-off</button>
    </form>
    <pre id="result">Waiting for sign-off.</pre>
  </main>
  <script>
    const signedCode = {signed_code_json};
    const result = document.getElementById('result');
    document.getElementById('signoff-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const payload = {{
        token: signedCode,
        signer_name: document.getElementById('signer_name').value,
        signer_role: document.getElementById('signer_role').value,
        decision: document.getElementById('decision').value,
        notes: document.getElementById('notes').value,
        include_artifact: true,
        no_secrets_confirmed: document.getElementById('confirm').checked
      }};
      result.textContent = 'Submitting...';
      const response = await fetch(window.location.pathname, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const body = await response.json();
      if (!response.ok || !body.ok) {{
        result.textContent = 'Blocked or failed: ' + JSON.stringify(body, null, 2);
        return;
      }}
      result.textContent = 'Recorded: ' + body.data.id + '\\nStatus: ' + body.data.status + '\\nLive run: ' + body.data.live_run_id;
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/public/platform-acceptance-final-signoff")
async def v1_submit_platform_acceptance_final_signoff(
    payload: PlatformAcceptanceFinalSignoffRequest,
    request: Request,
):
    return success_response(await submit_platform_acceptance_final_signoff(payload), request)


@router.get("/public/platform-acceptance-owner-closure", response_class=HTMLResponse)
async def v1_platform_acceptance_owner_closure_form(token: str = ""):
    if not token:
        return HTMLResponse("<h1>Missing owner closure token</h1>", status_code=400)
    try:
        data = decode_platform_acceptance_owner_closure_token(token)
    except HTTPException as exc:
        detail = html.escape(str(exc.detail))
        return HTMLResponse(f"<h1>Owner closure link unavailable</h1><p>{detail}</p>", status_code=exc.status_code)
    token_json = json.dumps(token)
    connectors = data.get("connectors") or ["douyin", "douyin_dm", "wechat_work", "taobao", "pdd", "api"]
    connector_options = "\n".join(
        f"<option value=\"{html.escape(str(connector))}\">{html.escape(str(connector))}</option>"
        for connector in connectors
    )
    customer_name = html.escape(str(data.get("customer_name") or "customer"))
    recipient = html.escape(str(data.get("recipient") or "customer platform owner"))
    expires_at = html.escape(str(data.get("expires_at") or ""))
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Secure Platform Closure</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #14171f; }}
    main {{ max-width: 820px; margin: 0 auto; padding: 32px 18px; }}
    form {{ display: grid; gap: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; padding: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #c8ced8; border-radius: 6px; padding: 10px 12px; font: inherit; }}
    textarea {{ min-height: 110px; resize: vertical; }}
    button {{ width: fit-content; border: 0; border-radius: 6px; background: #1769e0; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    .meta, .notice, pre {{ color: #4d5665; }}
    .notice {{ border-left: 4px solid #1769e0; padding: 10px 12px; background: #eef5ff; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #101724; color: #dce7ff; border-radius: 6px; padding: 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>Secure Platform Closure</h1>
    <p class="meta">Customer: {customer_name} · Recipient: {recipient} · Expires: {expires_at}</p>
    <p class="notice">Enter official platform fields only on this HTTPS form. Secret values are encrypted by the server and are not written to reports. Do not paste secrets into chat, screenshots, documents, or email bodies.</p>
    <form id="closure-form">
      <div class="grid">
        <label>Connector<select id="connector">{connector_options}</select></label>
        <label>Auth mode<select id="auth_mode"><option value="oauth">oauth</option><option value="webhook">webhook</option><option value="api_key">api_key</option><option value="manual">manual</option></select></label>
        <label>Account label<input id="account_name" value="{customer_name}" /></label>
        <label>Authorize URL<input id="authorize_url" placeholder="https://..." /></label>
        <label>Token URL<input id="token_url" placeholder="https://..." /></label>
        <label>Client ID / Key<input id="client_id" /></label>
        <label>Messages URL<input id="messages_url" placeholder="https://..." /></label>
        <label>Leads URL<input id="leads_url" placeholder="https://..." /></label>
      </div>
      <div class="grid">
        <label>Client secret<input id="client_secret" type="password" autocomplete="off" /></label>
        <label>App secret<input id="app_secret" type="password" autocomplete="off" /></label>
        <label>Access token<input id="access_token" type="password" autocomplete="off" /></label>
        <label>Session key<input id="session_key" type="password" autocomplete="off" /></label>
        <label>Webhook token<input id="webhook_token" type="password" autocomplete="off" /></label>
        <label>OAuth code<input id="oauth_code" type="password" autocomplete="off" /></label>
        <label>API key<input id="api_key" type="password" autocomplete="off" /></label>
      </div>
      <label>Sanitized customer trial evidence URL<input id="trial_url" placeholder="https://..." /></label>
      <label>Sanitized note<textarea id="notes" placeholder="Describe what the submitted material proves. Do not include secrets or private customer data."></textarea></label>
      <label><span><input id="confirm" type="checkbox" required /> I confirm notes and evidence links contain no passwords, tokens, cookies, verification codes, raw signatures, API secrets, session keys, or private customer data.</span></label>
      <button type="submit">Submit and recheck</button>
    </form>
    <pre id="result">Waiting for secure closure submission.</pre>
  </main>
  <script>
    const token = {token_json};
    const result = document.getElementById('result');
    const read = (id) => document.getElementById(id).value.trim();
    const putIf = (target, key, value) => {{ if (value) target[key] = value; }};
    document.getElementById('closure-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const nonsecret = {{}};
      putIf(nonsecret, 'authorize_url', read('authorize_url'));
      putIf(nonsecret, 'token_url', read('token_url'));
      putIf(nonsecret, 'client_id', read('client_id'));
      putIf(nonsecret, 'client_key', read('client_id'));
      putIf(nonsecret, 'messages_url', read('messages_url'));
      putIf(nonsecret, 'leads_url', read('leads_url'));
      const secrets = {{}};
      for (const key of ['client_secret', 'app_secret', 'access_token', 'session_key', 'webhook_token', 'oauth_code', 'api_key']) {{
        putIf(secrets, key, read(key));
      }}
      const trialUrl = read('trial_url');
      const notes = read('notes') || 'Secure owner closure submission.';
      const scenario_receipts = trialUrl ? [{{
        scenario: 'customer_trial',
        outcome: 'submitted',
        note: notes,
        evidence_url: trialUrl
      }}] : [];
      const payload = {{
        token,
        connector_update: {{
          connector: read('connector'),
          status: 'pending_auth',
          auth_mode: read('auth_mode'),
          account_name: read('account_name'),
          callback_url: '',
          nonsecret_config: nonsecret,
          secret_fields: secrets,
          read_only_enabled: true,
          notes: 'Submitted through secure owner closure form'
        }},
        scenario_receipts,
        receipt_outcome: scenario_receipts.length ? 'submitted' : 'acknowledged',
        notes,
        attempt_exchange: true,
        attempt_pull: true,
        create_submission_links: true,
        create_gap_tasks: true,
        create_review_tasks: true,
        include_artifact: true,
        no_secrets_confirmed: document.getElementById('confirm').checked
      }};
      result.textContent = 'Submitting and rechecking...';
      const response = await fetch(window.location.pathname, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const body = await response.json();
      if (!response.ok || !body.ok) {{
        result.textContent = 'Blocked or failed: ' + JSON.stringify(body, null, 2);
        return;
      }}
      const data = body.data;
      result.textContent = 'Recorded: ' + data.id + '\\nStatus: ' + data.status + '\\nMissing after: ' + data.missing_after.join(', ') + '\\nFinal gate: ' + (data.final_gate ? data.final_gate.status : 'unknown');
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/public/platform-acceptance-owner-closure")
async def v1_submit_platform_acceptance_owner_closure(
    payload: PlatformAcceptanceOwnerClosureSubmissionRequest,
    request: Request,
):
    return success_response(await submit_platform_acceptance_owner_closure(payload), request)


@router.get("/public/platform-acceptance-evidence-submission", response_class=HTMLResponse)
async def v1_platform_acceptance_evidence_submission_form(token: str = ""):
    if not token:
        return HTMLResponse("<h1>Missing submission token</h1>", status_code=400)
    data = decode_platform_acceptance_submission_token(token)
    scenarios = data.get("scenarios") or []
    scenario_options = "\n".join(
        f"<option value=\"{html.escape(str(scenario))}\">{html.escape(str(scenario))}</option>"
        for scenario in scenarios
    )
    token_json = json.dumps(token)
    scenarios_json = json.dumps(scenarios)
    recipient = html.escape(str(data.get("recipient") or "customer platform owner"))
    expires_at = html.escape(str(data.get("expires_at") or ""))
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>平台验收材料提交</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #14171f; }}
    main {{ max-width: 720px; margin: 0 auto; padding: 32px 18px; }}
    form {{ display: grid; gap: 14px; background: #fff; border: 1px solid #dde1e7; border-radius: 8px; padding: 20px; }}
    label {{ display: grid; gap: 6px; font-weight: 650; }}
    input, select, textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #c8ced8; border-radius: 6px; padding: 10px 12px; font: inherit; }}
    textarea {{ min-height: 120px; resize: vertical; }}
    button {{ width: fit-content; border: 0; border-radius: 6px; background: #1769e0; color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    .meta, .notice, pre {{ color: #4d5665; }}
    .notice {{ border-left: 4px solid #1769e0; padding: 10px 12px; background: #eef5ff; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #101724; color: #dce7ff; border-radius: 6px; padding: 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>平台验收材料提交</h1>
    <p class="meta">接收人：{recipient} · 过期时间：{expires_at}</p>
    <p class="notice">只提交脱敏后的截图链接、录屏链接、工单链接或说明。不要填写密码、token、cookie、验证码、签名密钥或 API secret。</p>
    <form id="submission-form">
      <label>提交人 <input id="submitter" required value="{recipient}" /></label>
      <label>验收场景 <select id="scenario" required>{scenario_options}</select></label>
      <label>提交结果
        <select id="outcome">
          <option value="submitted">已提交材料</option>
          <option value="needs_help">需要协助</option>
          <option value="acknowledged">已收到通知</option>
        </select>
      </label>
      <label>脱敏说明 <textarea id="note" required placeholder="说明材料证明了什么，不要包含任何密钥或验证码"></textarea></label>
      <label>材料链接 <input id="evidence_url" placeholder="https://..." /></label>
      <label><span><input id="confirm" type="checkbox" required /> 我确认内容不包含密码、token、cookie、验证码、签名密钥或 API secret</span></label>
      <button type="submit">提交材料</button>
    </form>
    <pre id="result">等待提交。可提交场景：{html.escape(", ".join(str(item) for item in scenarios))}</pre>
  </main>
  <script>
    const token = {token_json};
    const scenarios = {scenarios_json};
    const result = document.getElementById('result');
    document.getElementById('submission-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      const outcome = document.getElementById('outcome').value;
      const payload = {{
        token,
        submitter: document.getElementById('submitter').value,
        outcome,
        scenario_receipts: [{{
          scenario: document.getElementById('scenario').value,
          outcome,
          note: document.getElementById('note').value,
          evidence_url: document.getElementById('evidence_url').value
        }}],
        notes: document.getElementById('note').value,
        include_artifact: true,
        no_secrets_confirmed: document.getElementById('confirm').checked
      }};
      result.textContent = '提交中...';
      const response = await fetch(window.location.pathname, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const body = await response.json();
      if (!response.ok || !body.ok) {{
        result.textContent = '提交失败：' + JSON.stringify(body, null, 2);
        return;
      }}
      result.textContent = '提交成功。回执：' + body.data.receipt.id + '\\n复核任务新增：' + body.data.review_sync.created;
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@router.post("/public/platform-acceptance-evidence-submission")
async def v1_submit_platform_acceptance_evidence_material(
    payload: PlatformAcceptanceEvidenceCustomerSubmissionRequest,
    request: Request,
):
    return success_response(await submit_platform_acceptance_evidence_material(payload), request)


@router.post("/ops/platform-acceptance-evidence-receipt")
async def v1_record_platform_acceptance_evidence_receipt(
    payload: PlatformAcceptanceEvidenceReceiptRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await record_platform_acceptance_evidence_receipt(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-review-sync")
async def v1_sync_platform_acceptance_evidence_review_tasks(
    payload: PlatformAcceptanceEvidenceReviewTaskSyncRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await sync_platform_acceptance_evidence_review_tasks(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-review-desk")
async def v1_generate_platform_acceptance_review_desk(
    payload: PlatformAcceptanceReviewDeskRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await generate_platform_acceptance_review_desk(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-review-execution")
async def v1_run_platform_acceptance_review_execution(
    payload: PlatformAcceptanceReviewExecutionRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await run_platform_acceptance_review_execution(payload, context.merchant), request)


@router.post("/ops/platform-acceptance-evidence-review-decision")
async def v1_record_platform_acceptance_evidence_review_decision(
    payload: PlatformAcceptanceEvidenceReviewDecisionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await record_platform_acceptance_evidence_review_decision(payload, context.merchant), request)


@router.post("/acceptance/audit")
async def v1_run_acceptance_audit(
    payload: AcceptanceAuditRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("acceptance:run")),
):
    return success_response(await run_acceptance_audit(payload, context.merchant), request)


@router.get("/enterprise/dashboard")
async def v1_dashboard(request: Request, context: AuthContext = Depends(require_auth)):
    return success_response(await dashboard_overview(context.merchant), request)


@router.get("/crm/conversations")
async def v1_conversations(request: Request, context: AuthContext = Depends(require_permission("crm:read"))):
    return success_response(await list_conversations(context.merchant), request)


@router.get("/crm/conversations/{session_id}")
async def v1_conversation_detail(session_id: str, request: Request, context: AuthContext = Depends(require_permission("crm:read"))):
    return success_response(await conversation_detail(session_id, context.merchant), request)


@router.post("/crm/conversations/{session_id}/handoff")
async def v1_handoff(session_id: str, request: Request, context: AuthContext = Depends(require_permission("crm:read"))):
    return success_response(await mark_handoff(session_id, context.merchant), request)


@router.get("/crm/overview")
async def v1_crm_overview(request: Request, context: AuthContext = Depends(require_permission("crm:read"))):
    return success_response(await crm_overview(context.merchant), request)


@router.get("/crm/leads")
async def v1_crm_leads(
    request: Request,
    stage: str = "",
    owner: str = "",
    context: AuthContext = Depends(require_permission("crm:read")),
):
    return success_response(await list_crm_leads(context.merchant, stage=stage, owner=owner), request)


@router.post("/crm/leads")
async def v1_create_crm_lead(
    payload: CRMLeadCreate,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await create_crm_lead(payload, context.merchant), request)


@router.patch("/crm/leads/{customer_id}")
async def v1_update_crm_lead(
    customer_id: int,
    payload: CRMLeadUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await update_crm_lead(customer_id, payload, context.merchant), request)


@router.get("/crm/tasks")
async def v1_crm_tasks(
    request: Request,
    status: str = "open",
    context: AuthContext = Depends(require_permission("crm:read")),
):
    return success_response(await list_crm_tasks(context.merchant, status=status), request)


@router.post("/crm/tasks")
async def v1_create_crm_task(
    payload: CRMTaskCreate,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await create_crm_task(payload, context.merchant), request)


@router.patch("/crm/tasks/{task_id}")
async def v1_update_crm_task(
    task_id: int,
    payload: CRMTaskUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await update_crm_task(task_id, payload, context.merchant), request)


@router.get("/reply-drafts")
async def v1_reply_drafts(
    request: Request,
    status: str = "pending",
    connector: str = "",
    limit: int = 50,
    context: AuthContext = Depends(require_permission("crm:read")),
):
    return success_response(await list_reply_drafts(context.merchant, status=status, connector=connector, limit=limit), request)


@router.post("/reply-drafts")
async def v1_create_reply_draft(
    payload: ReplyDraftQueueCreateRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await create_reply_draft_queue(payload, context.merchant), request)


@router.patch("/reply-drafts/{draft_id}/review")
async def v1_review_reply_draft(
    draft_id: int,
    payload: ReplyDraftReviewRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await review_reply_draft(draft_id, payload, context.merchant), request)


@router.get("/reply-dispatches")
async def v1_reply_dispatches(
    request: Request,
    status: str = "",
    limit: int = Query(50, ge=1, le=100),
    context: AuthContext = Depends(require_permission("crm:read")),
):
    return success_response(await list_reply_dispatches(context.merchant, status=status, limit=limit), request)


@router.post("/reply-drafts/{draft_id}/dispatch")
async def v1_create_reply_dispatch(
    draft_id: int,
    payload: ReplyDispatchCreateRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await create_reply_dispatch(draft_id, payload, context.merchant), request)


@router.post("/reply-dispatches/{dispatch_id}/revoke")
async def v1_revoke_reply_dispatch(
    dispatch_id: int,
    payload: ReplyDispatchRevokeRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await revoke_reply_dispatch(dispatch_id, payload, context.merchant), request)


@router.post("/reply-dispatches/{dispatch_id}/send")
async def v1_send_reply_dispatch(
    dispatch_id: int,
    payload: ReplyDispatchSendRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await confirm_reply_dispatch_send(dispatch_id, payload, context.merchant), request)


@router.get("/knowledge/items")
async def v1_knowledge_items(request: Request, context: AuthContext = Depends(require_permission("enterprise:read"))):
    return success_response(await list_knowledge(context.merchant), request)


@router.post("/knowledge/import")
async def v1_knowledge_import(
    payload: KnowledgeImportRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("knowledge:write")),
):
    return success_response(await import_knowledge(payload, context.merchant), request)


@router.post("/knowledge/upload")
async def v1_knowledge_upload(
    request: Request,
    title: str = "上传文档",
    source_type: Literal["script", "faq", "product", "policy", "manual"] = "manual",
    tags: str = "文档导入",
    sync_to_faq: bool = True,
    file: UploadFile = File(...),
    context: AuthContext = Depends(require_permission("knowledge:write")),
):
    return success_response(
        await import_uploaded_knowledge_file(file, context.merchant, title, source_type, tags, sync_to_faq),
        request,
    )


@router.get("/settings/channels")
async def v1_channels(request: Request, context: AuthContext = Depends(require_permission("enterprise:read"))):
    return success_response(await list_channels(context.merchant), request)


@router.put("/settings/channels/{channel}")
async def v1_update_channel(
    channel: str,
    payload: ChannelConfigUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await update_channel(channel, payload, context.merchant), request)


@router.get("/connectors")
async def v1_connectors(request: Request):
    cache_key = "connector_statuses"
    cached = runtime_cache.get(cache_key)
    data = cached if cached is not None else runtime_cache.set(cache_key, list_connectors(), ttl_seconds=15)
    return success_response(data, request)


@router.get("/connectors/auth")
async def v1_connector_auths(request: Request, context: AuthContext = Depends(require_permission("settings:write"))):
    return success_response(await list_connector_auths(context.merchant), request)


@router.put("/connectors/{connector}/auth")
async def v1_update_connector_auth(
    connector: str,
    payload: ConnectorAuthUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await update_connector_auth(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/send-gate")
async def v1_update_connector_send_gate(
    connector: str,
    payload: ConnectorSendGateUpdate,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await update_connector_send_gate(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/oauth/start")
async def v1_start_connector_oauth(
    connector: str,
    payload: ConnectorOAuthStartRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await start_connector_oauth(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/oauth/exchange")
async def v1_exchange_connector_oauth(
    connector: str,
    payload: ConnectorOAuthExchangeRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await exchange_connector_oauth_token(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/oauth/refresh")
async def v1_refresh_connector_oauth(
    connector: str,
    payload: ConnectorOAuthRefreshRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("settings:write")),
):
    return success_response(await refresh_connector_oauth_token(connector, payload, context.merchant), request)


@router.get("/connectors/{connector}/oauth/callback")
async def v1_connector_oauth_callback_get(connector: str, request: Request, state: str = "", code: str = ""):
    return success_response(
        await handle_connector_oauth_callback(connector, state, code, dict(request.query_params)),
        request,
    )


@router.post("/connectors/{connector}/oauth/callback")
async def v1_connector_oauth_callback_post(connector: str, request: Request):
    data = dict(request.query_params)
    try:
        body = await request.json()
        if isinstance(body, dict):
            data.update(body)
    except Exception:
        pass
    return success_response(
        await handle_connector_oauth_callback(connector, str(data.get("state") or ""), str(data.get("code") or ""), data),
        request,
    )


@router.get("/connectors/events")
async def v1_connector_events(
    request: Request,
    connector: str = "",
    context: AuthContext = Depends(require_permission("crm:read")),
):
    return success_response(await list_connector_events(context.merchant, connector=connector), request)


@router.get("/ops/connector-health")
async def v1_connector_ops_health(
    request: Request,
    context: AuthContext = Depends(require_permission("audit:read")),
):
    return success_response(await connector_ops_health(context.merchant), request)


@router.get("/ops/setup-guide")
async def v1_connector_setup_guide(
    request: Request,
    context: AuthContext = Depends(require_permission("audit:read")),
):
    return success_response(await connector_setup_guide(context.merchant), request)


@router.post("/connectors/{connector}/messages/read")
async def v1_connector_read_message(
    connector: str,
    payload: ConnectorInboundMessageRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await ingest_connector_message(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/leads/read")
async def v1_connector_read_lead(
    connector: str,
    payload: ConnectorInboundLeadRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await ingest_connector_lead(connector, payload, context.merchant), request)


@router.post("/connectors/{connector}/api/pull")
async def v1_connector_api_pull(
    connector: str,
    payload: ConnectorReadPullRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("crm:write")),
):
    return success_response(await pull_connector_read_api(connector, payload, context.merchant), request)


def webhook_signature_headers(request: Request) -> tuple[str, str]:
    signature = (
        request.headers.get("x-webhook-signature")
        or request.headers.get("x-signature")
        or request.headers.get("x-hub-signature-256")
        or ""
    )
    timestamp = request.headers.get("x-webhook-timestamp") or request.headers.get("x-timestamp") or ""
    return signature, timestamp


async def webhook_payload_and_merchant(request: Request, merchant_code: str = ""):
    raw_body = await request.body()
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    code = merchant_code or request.headers.get("x-merchant-code") or str(data.get("merchant_code") or "")
    if not code:
        raise HTTPException(status_code=400, detail="Missing merchant_code")
    return raw_body, data, merchant_by_code(code)


@router.post("/webhooks/{connector}/messages")
async def v1_connector_webhook_message(connector: str, request: Request, merchant_code: str = ""):
    raw_body, data, merchant = await webhook_payload_and_merchant(request, merchant_code)
    signature, timestamp = webhook_signature_headers(request)
    verify_connector_webhook_signature(merchant, connector, raw_body, signature, timestamp)
    payload = ConnectorInboundMessageRequest.model_validate(data)
    return success_response(await ingest_connector_message(connector, payload, merchant), request)


@router.post("/webhooks/{connector}/leads")
async def v1_connector_webhook_lead(connector: str, request: Request, merchant_code: str = ""):
    raw_body, data, merchant = await webhook_payload_and_merchant(request, merchant_code)
    signature, timestamp = webhook_signature_headers(request)
    verify_connector_webhook_signature(merchant, connector, raw_body, signature, timestamp)
    payload = ConnectorInboundLeadRequest.model_validate(data)
    return success_response(await ingest_connector_lead(connector, payload, merchant), request)


@router.post("/desktop-agent/sessions")
async def v1_desktop_agent_session(
    payload: DesktopAgentSessionRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    return success_response(await register_desktop_agent_session(payload, context.merchant), request)


@router.post("/desktop-agent/events")
async def v1_desktop_agent_event(
    payload: DesktopAgentEventRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    return success_response(await ingest_desktop_agent_event(payload, context.merchant), request)


@router.post("/desktop-agent/actions/{action_id}/result")
async def v1_desktop_agent_action_result(
    action_id: str,
    payload: DesktopAgentActionResultRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    return success_response(await record_desktop_agent_action_result(action_id, payload, context.merchant), request)


@router.post("/desktop-agent/pause")
async def v1_desktop_agent_pause(
    payload: DesktopAgentPauseRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    return success_response(await update_desktop_agent_pause(payload, context.merchant), request)


@router.get("/desktop-agent/state")
async def v1_desktop_agent_state(request: Request, context: AuthContext = Depends(require_permission("automation:run"))):
    return success_response(await desktop_agent_state(context.merchant), request)


@router.get("/desktop-agent/logs")
async def v1_desktop_agent_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    context: AuthContext = Depends(require_permission("automation:run")),
):
    return success_response(await desktop_agent_logs(context.merchant, limit=limit), request)


@router.get("/workflows/runs")
async def v1_workflow_runs(request: Request, context: AuthContext = Depends(require_permission("automation:run"))):
    return success_response(workflow_engine.list_runs(), request)


@router.get("/workflows/definitions")
async def v1_workflow_definitions(request: Request, context: AuthContext = Depends(require_permission("automation:run"))):
    return success_response(workflow_engine.list_definitions(), request)


@router.get("/workflows/runs/{run_id}")
async def v1_workflow_run_detail(run_id: str, request: Request, context: AuthContext = Depends(require_permission("automation:run"))):
    run = workflow_engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return success_response(run, request)


@router.post("/workflows/events")
async def v1_workflow_event(
    payload: WorkflowEventRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    runs = workflow_engine.trigger(payload.trigger_type, payload.source, payload.payload)
    if runs:
        record_usage(context.merchant.id or 0, "workflow_run", len(runs), payload.source, payload.trigger_type, {"workflow_ids": [run.workflow_id for run in runs]})
    return success_response({"matched": len(runs), "runs": runs}, request)


@router.post("/workflows/{workflow_id}/run")
async def v1_workflow_manual_run(
    workflow_id: str,
    payload: WorkflowManualRunRequest,
    request: Request,
    context: AuthContext = Depends(require_permission("automation:run")),
):
    try:
        run = workflow_engine.run_manual(workflow_id, payload.payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Workflow definition not found") from None
    record_usage(context.merchant.id or 0, "workflow_run", 1, "manual", workflow_id)
    return success_response(run, request)


@router.get("/ai-engine/status")
async def v1_ai_engine_status(request: Request, context: AuthContext = Depends(require_auth)):
    return success_response(ai_engine_status_payload(), request)


@router.post("/ai-engine/risk")
async def v1_ai_risk(payload: AIRiskRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().assess_risk(payload.text)
    record_usage(context.merchant.id or 0, "ai_risk", 1, "api_v1", "risk")
    return success_response(result, request)


@router.post("/ai-engine/intent-score")
async def v1_ai_intent_score(payload: AIIntentRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().score_intent(payload.text)
    record_usage(context.merchant.id or 0, "ai_intent_score", 1, "api_v1", "intent-score")
    return success_response(result, request)


@router.post("/ai-engine/conversation-summary")
async def v1_ai_conversation_summary(payload: AISummaryRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().summarize_conversation(payload.messages)
    record_usage(context.merchant.id or 0, "ai_summary", 1, "api_v1", "conversation-summary")
    return success_response(result, request)


@router.post("/ai-engine/reply")
async def v1_ai_reply(payload: AIReplyRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().generate_reply(
        system_prompt=payload.system_prompt,
        user_message=payload.message,
        history=payload.history,
        fallback_text=payload.fallback_text,
    )
    record_usage(context.merchant.id or 0, "ai_reply", 1, "api_v1", "reply")
    return success_response(result, request)


@router.post("/ai-engine/script")
async def v1_ai_script(payload: AIStructuredContextRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().generate_script(payload.context)
    record_usage(context.merchant.id or 0, "ai_script", 1, "api_v1", "script")
    return success_response(result, request)


@router.post("/ai-engine/product-copy")
async def v1_ai_product_copy(payload: AIStructuredContextRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().generate_product_copy(payload.context)
    record_usage(context.merchant.id or 0, "ai_product_copy", 1, "api_v1", "product-copy")
    return success_response(result, request)


@router.post("/ai-engine/prompt")
async def v1_ai_prompt(payload: AIStructuredContextRequest, request: Request, context: AuthContext = Depends(require_auth)):
    result = default_ai_engine().generate_prompt(payload.context)
    record_usage(context.merchant.id or 0, "ai_prompt", 1, "api_v1", "prompt")
    return success_response(result, request)
