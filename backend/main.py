from __future__ import annotations

import asyncio
import base64
import html
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.api_v1 import router as api_v1_router
from backend.customer_service_saas import router as customer_service_saas_router
from backend.internal_growth.api import router as internal_growth_router
from backend.internal_growth.scheduler import maybe_start_scheduler
from backend.platform.api import http_exception_handler, request_context_middleware, unhandled_exception_handler
from backend.platform.ai_engine import default_ai_engine
from backend.platform.connectors import ConnectorResult, list_connectors
from backend.platform.workflow import WorkflowRun, workflow_engine
from scripts.commerce_daily_report import DEFAULT_INPUT as COMMERCE_DAILY_SAMPLE
from scripts.commerce_daily_report import build_report as build_commerce_daily_report
from scripts.commerce_daily_report import load_payload as load_commerce_daily_payload
from scripts.commerce_daily_report import write_report as write_commerce_daily_report


def default_data_dir() -> Path:
    configured = os.getenv("MERCHANT_AUTO_CUT_DATA_DIR")
    if configured:
        return Path(configured)
    try:
        if shutil.disk_usage(Path.cwd()).free > 10 * 1024 * 1024:
            return Path("data")
    except OSError:
        pass
    return Path("D:/merchant-auto-cut-data")


DATA_DIR = default_data_dir()
ARTIFACT_DIR = DATA_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("MERCHANT_AUTO_CUT_DB_PATH", str(DATA_DIR / "merchant_growth.sqlite3")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_LOCK = threading.Lock()


VideoType = Literal["product_seed", "local_promo", "ecommerce"]
CustomerSegment = Literal["local_merchant", "ecommerce_seller", "agency_developer"]
GenerationKind = Literal["short_video", "product_image", "detail_page", "customer_service"]
TaskStatus = Literal["queued", "running", "done", "failed"]
LeadSource = Literal["douyin", "github", "website", "manual"]


class MerchantBrief(BaseModel):
    industry: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    selling_points: str = Field(min_length=1)
    platform: str = "抖音"
    video_type: VideoType = "product_seed"
    segment: CustomerSegment = "local_merchant"
    generation_kind: GenerationKind = "short_video"
    style: str = "clean"
    budget_mode: str = "balanced"
    audience: str = "新客"
    call_to_action: str = "立即咨询"


class Scene(BaseModel):
    id: str
    title: str
    caption: str
    visual: str
    duration: float
    accent: str


class ScriptVariant(BaseModel):
    id: str
    name: str
    hook: str
    voiceover: str
    scenes: list[Scene]
    estimated_cost: float


class Project(BaseModel):
    id: str
    name: str
    segment: CustomerSegment
    brief: MerchantBrief
    created_at: str


class Asset(BaseModel):
    id: str
    project_id: str
    name: str
    kind: Literal["image", "video", "logo", "music", "document"]
    url: str | None = None
    created_at: str


class Lead(BaseModel):
    id: str
    source: LeadSource
    industry: str
    business_name: str
    contact: str
    need: str
    status: Literal["new", "contacted", "trial", "paid"] = "new"
    created_at: str


class LeadCreate(BaseModel):
    source: LeadSource = "douyin"
    industry: str = Field(min_length=1)
    business_name: str = Field(min_length=1)
    contact: str = Field(min_length=1)
    need: str = Field(min_length=1)


class CustomerNeedIntake(BaseModel):
    source: LeadSource = "douyin"
    business_name: str = Field(default="待确认商家", min_length=1)
    contact: str = "待补充"
    industry: str = "本地商家"
    product_name: str = "商家增长方案"
    need_text: str = Field(min_length=1)
    platform: str = "抖音"
    generation_kind: GenerationKind = "customer_service"
    video_type: VideoType = "local_promo"
    segment: CustomerSegment = "local_merchant"
    audience: str = "潜在客户"
    call_to_action: str = "私信领取方案"
    budget: str = "待确认"
    assets: list[str] = []
    customer_message: str | None = None
    metadata: dict[str, Any] = {}


class CustomerNeedIntakeResponse(BaseModel):
    intake_id: str
    lead: Lead
    project: Project
    brief: MerchantBrief
    scripts: list[ScriptVariant]
    reply_analysis: ReplyAssistantResponse
    next_actions: list[str]


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price_monthly: int
    generation_quota: int
    target: str
    features: list[str]


class RenderRequest(BaseModel):
    brief: MerchantBrief
    script: ScriptVariant
    generation_kind: GenerationKind = "short_video"
    variant_count: int = Field(default=1, ge=1, le=5)


class ImageGenerationRequest(BaseModel):
    brief: MerchantBrief
    image_kind: Literal["main_image", "scene_image", "detail_image"] = "main_image"
    prompt: str | None = None


class ImageGenerationResponse(BaseModel):
    mode: Literal["image", "prompt"]
    provider: str
    model: str | None
    prompt: str
    image_url: str | None = None
    artifact_url: str | None = None
    error: str | None = None
    next_action: str


class RenderTask(BaseModel):
    id: str
    generation_kind: GenerationKind
    status: TaskStatus
    progress: int
    message: str
    created_at: str
    updated_at: str
    cost: float
    artifact_url: str | None = None
    error: str | None = None


class ContentIdea(BaseModel):
    day: int
    title: str
    format: str
    target: CustomerSegment
    metric: str


class EcosystemModule(BaseModel):
    id: str
    name: str
    channel: str
    purpose: str
    status: Literal["ready", "planned", "manual"]
    next_action: str


class AdminOverview(BaseModel):
    projects: int
    leads: int
    active_tasks: int
    paid_pipeline: int
    conversion_loop: list[str]


class ProviderStatus(BaseModel):
    provider: str
    model: str | None
    configured: bool
    mode: Literal["ai", "template"]
    notes: list[str]


class MediaPluginStatus(BaseModel):
    id: str
    name: str
    role: str
    runtime: Literal["local", "server", "external_api", "manual"]
    status: Literal["ready", "configured", "needs_config", "planned"]
    configured: bool
    actions: list[str]
    required_env: list[str]
    next_action: str


class DiagnosticCheck(BaseModel):
    id: str
    name: str
    status: Literal["pass", "warn", "fail"]
    message: str
    next_action: str


class SystemDiagnostics(BaseModel):
    status: Literal["pass", "warn", "fail"]
    summary: str
    checks: list[DiagnosticCheck]


class LocalScriptInfo(BaseModel):
    id: str
    name: str
    description: str
    risk: Literal["safe", "desktop", "long_running"]
    enabled: bool
    command_preview: str


class LocalScriptRun(BaseModel):
    run_id: str
    script_id: str
    workflow_run_id: str | None = None
    status: Literal["queued", "running", "done", "failed"]
    started_at: str
    finished_at: str | None = None
    returncode: int | None = None
    log: str = ""
    log_path: str = ""


class PlatformConnector(BaseModel):
    id: str
    name: str
    mode: Literal["browser", "api", "manual"]
    status: Literal["ready", "needs_login", "planned"]
    capabilities: list[str]
    guardrail: str


class EcommerceProduct(BaseModel):
    id: str
    name: str
    category: str
    sku: str
    price: float
    stock: int
    safety_stock: int
    status: Literal["draft", "active", "paused"]
    next_action: str


class EcommerceOrder(BaseModel):
    id: str
    platform: str
    order_no: str
    customer: str
    product_name: str
    amount: float
    status: str
    exception: str = ""


class AutomationJob(BaseModel):
    id: str
    platform: str
    action: str
    mode: Literal["read_only", "draft_only", "requires_confirmation"]
    status: Literal["ready", "queued", "running", "done", "blocked"]
    product_name: str = ""
    notes: str


class EcommerceSnapshot(BaseModel):
    platforms: list[PlatformConnector]
    products: list[EcommerceProduct]
    orders: list[EcommerceOrder]
    automation_jobs: list[AutomationJob]
    stats: dict[str, float | int]
    recommended_flow: list[str]


class EcommerceDailyReportResponse(BaseModel):
    source: Literal["sample", "uploaded", "mcp"]
    date: str
    report: str
    artifact_url: str
    next_action: str


class EcommerceListingDraftRequest(BaseModel):
    product_name: str = Field(min_length=1)
    category: str = Field(default="电商商品")
    platform: Literal["douyin", "taobao", "pdd", "xianyu", "xiaohongshu"] = "douyin"
    price: str = "待定"
    sku_options: str = "标准款"
    stock: str = "待确认"
    selling_points: str = Field(min_length=1)
    audience: str = "抖音电商用户"
    shipping: str = "按店铺实际承诺填写"
    after_sales: str = "按平台售后规则执行"
    visual_style: str = "蓝紫霓虹科技风"


class EcommerceListingDraftResponse(BaseModel):
    draft_id: str
    platform: str
    product_name: str
    titles: list[str]
    short_title: str
    selling_points: list[str]
    main_image_prompts: list[str]
    detail_sections: list[str]
    sku_table: list[dict[str, str]]
    listing_fields: dict[str, str]
    customer_faq: list[dict[str, str]]
    risk_checks: list[str]
    publish_boundary: Literal["save_draft_only"]
    next_action: str


class ProductMediaPackRequest(BaseModel):
    product_name: str = Field(min_length=1)
    category: str = "电商商品"
    platform: Literal["douyin", "taobao", "pdd", "xianyu", "xiaohongshu"] = "douyin"
    price: str = "129.00"
    selling_points: str = Field(min_length=1)
    audience: str = "电商用户"
    visual_style: str = "蓝紫霓虹科技风"
    call_to_action: str = "保存上架草稿"
    product_image_data_url: str | None = None
    render_video: bool = True


class ProductMediaPackResponse(BaseModel):
    pack_id: str
    product_name: str
    main_image_url: str
    detail_image_url: str
    video_preview_url: str
    video_url: str | None = None
    video_status: Literal["rendered", "needs_ffmpeg", "failed"]
    listing_draft: EcommerceListingDraftResponse
    scenes: list[dict[str, str]]
    test_checklist: list[str]
    next_action: str


class ManagedOpsPlanRequest(BaseModel):
    product_name: str = Field(min_length=1)
    category: str = "电商商品"
    platform: Literal["douyin", "taobao", "pdd", "xianyu", "xiaohongshu"] = "douyin"
    price: str = "待定"
    selling_points: str = Field(min_length=1)
    audience: str = "电商用户"
    launch_goal: str = "7天内完成首批商品上架和客服承接"
    monthly_budget: str = "3000-10000"
    service_level: Literal["starter", "growth", "managed"] = "growth"
    pack_id: str | None = None


class ManagedOpsTask(BaseModel):
    day: str
    owner: Literal["ai", "operator", "merchant"]
    task: str
    output: str
    confirmation_required: bool


class ManagedOpsPlanResponse(BaseModel):
    plan_id: str
    product_name: str
    platform: str
    positioning: str
    sellable_offer: str
    price_packages: list[dict[str, str]]
    launch_tasks: list[ManagedOpsTask]
    publishing_queue: list[dict[str, str]]
    customer_service_flow: list[str]
    risk_boundaries: list[str]
    closing_script: str
    next_action: str


class CustomerServicePlaybook(BaseModel):
    welcome: str
    qualification_questions: list[str]
    objections: list[str]
    closing: str
    follow_up: str


class CustomerServiceLine(BaseModel):
    stage: str
    goal: str
    message: str
    operator_note: str


class ScriptCustomerServiceKit(BaseModel):
    headline: str
    script_name: str
    hook: str
    opening_messages: list[CustomerServiceLine]
    qualification_flow: list[CustomerServiceLine]
    objection_handling: list[CustomerServiceLine]
    closing_messages: list[CustomerServiceLine]
    follow_up_plan: list[str]
    handoff_checklist: list[str]


class HyperFramesRenderPlan(BaseModel):
    template: str
    aspect_ratio: str
    duration_seconds: float
    design_tokens: dict[str, str]
    scenes: list[dict[str, Any]]
    acceptance_checks: list[str]


class ReplyAssistantRequest(BaseModel):
    channel: Literal["wechat", "wechat_work", "douyin_dm", "taobao", "pdd", "xianyu", "customer_service", "dating"] = "wechat"
    scenario: str = "商家私信转化"
    conversation: str = Field(min_length=1)
    goal: str = "自然回复并推进下一步"
    tone: Literal["warm", "professional", "playful", "high_eq"] = "high_eq"
    recipient_profile: str = ""


class ReplyCandidate(BaseModel):
    label: str
    text: str
    why: str


class ServiceInsight(BaseModel):
    stage: str
    intent: str
    lead_score: int
    temperature: Literal["cold", "warm", "hot"]
    urgency: str
    budget_signal: str
    missing_info: list[str]
    next_best_action: str
    should_handoff: bool


class LeadCaptureSuggestion(BaseModel):
    business_name: str
    contact_hint: str
    need_summary: str
    tags: list[str]


class ReplyAssistantResponse(BaseModel):
    intent_summary: str
    risk_flags: list[str]
    service_insight: ServiceInsight
    candidates: list[ReplyCandidate]
    follow_up_plan: list[str]
    lead_capture: LeadCaptureSuggestion
    safety_note: str


class ParsedChatMessage(BaseModel):
    speaker: Literal["me", "customer", "system"]
    text: str
    index: int


class ConversationContext(BaseModel):
    conversation_type: Literal["private", "group", "unknown"] = "unknown"
    mention_me: bool = False
    reply_mode: Literal["auto", "draft_only", "ignore", "handoff"] = "draft_only"
    confidence: int = 50
    reason: str = ""


class ChatReplyAgentRequest(BaseModel):
    channel: Literal["wechat", "wechat_work", "douyin_dm", "taobao", "pdd", "xianyu", "customer_service"] = "wechat"
    ocr_text: str = Field(min_length=1)
    window_title: str = ""
    merchant_profile: str = "商家增长顾问"
    reply_goal: str = "自然回复并推进下一步"
    auto_send: bool = False
    my_aliases: list[str] = []
    group_reply_mode: Literal["ignore", "draft_on_mention", "draft_on_keyword"] = "draft_on_mention"
    allow_group_auto_reply: bool = False


class ChatReplyAgentResponse(BaseModel):
    conversation_id: str
    channel: str
    conversation_context: ConversationContext
    parsed_messages: list[ParsedChatMessage]
    pending_customer_messages: list[str]
    should_reply: bool
    should_handoff: bool
    automation_mode: Literal["copy_only", "api_ready", "blocked"]
    recommended_reply: str
    reply_analysis: ReplyAssistantResponse
    next_actions: list[str]


app = FastAPI(title="Merchant Growth Canvas API")
app.middleware("http")(request_context_middleware)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_DIR)), name="artifacts")
app.include_router(customer_service_saas_router)
app.include_router(api_v1_router)
app.include_router(internal_growth_router)


@app.on_event("startup")
async def start_internal_growth_scheduler() -> None:
    maybe_start_scheduler()

LOCAL_SCRIPT_RUNS: dict[str, LocalScriptRun] = {}
LOCAL_SCRIPT_WORKFLOW_RUNS: dict[str, str] = {}
LOCAL_SCRIPT_LOG_DIR = DATA_DIR / "local-script-runs"
LOCAL_SCRIPT_LOG_DIR.mkdir(parents=True, exist_ok=True)


def local_python() -> str:
    bundled = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    return str(bundled) if bundled.exists() else sys.executable


def local_script_catalog() -> dict[str, dict[str, Any]]:
    py = local_python()
    return {
        "start_assistant": {
            "name": "启动桌面 AI 客服",
            "description": "打开可视化启动器，选择微信/企业微信/抖音/千牛/拼多多/闲鱼真实聊天窗口后开始监听。",
            "risk": "desktop",
            "mode": "spawn",
            "cmd": [py, "scripts/desktop_listener_launcher.py"],
        },
        "start_auto_send": {
            "name": "全自动监听并发送",
            "description": "持续监听真实客服聊天窗口，AI 生成回复后自动粘贴并按 Enter 发送；请只在自己的客服账号和真实聊天页使用。",
            "risk": "desktop",
            "mode": "spawn",
            "cmd": [
                py,
                "scripts/desktop_auto_reply_listener.py",
                "--platform",
                "auto",
                "--source",
                "auto",
                "--paste",
                "--send",
                "--confirm-send",
                "我确认发送",
                "--min-send-gap-seconds",
                "20",
            ],
        },
        "reply_once_clipboard": {
            "name": "剪贴板单次生成回复",
            "description": "读取当前剪贴板里的聊天记录，调用线上 AI 客服，生成回复并复制回剪贴板；默认不发送。",
            "risk": "desktop",
            "mode": "run",
            "timeout": 90,
            "cmd": [py, "scripts/desktop_reply_assistant.py", "--platform", "wechat", "--json"],
        },
        "desktop_diagnostics": {
            "name": "桌面读取诊断",
            "description": "检测当前窗口、UIA 文本、OCR、剪贴板、可见平台窗口，判断脚本能不能读到真实聊天。",
            "risk": "desktop",
            "mode": "run",
            "timeout": 120,
            "cmd": [py, "scripts/desktop_diagnostics.py", "--source", "auto"],
        },
        "reply_e2e": {
            "name": "多平台回复 E2E 验收",
            "description": "用固定聊天样例测试微信、企业微信、抖音、淘宝、拼多多、闲鱼的回复生成质量。",
            "risk": "safe",
            "mode": "run",
            "timeout": 180,
            "cmd": [py, "scripts/desktop_reply_e2e_acceptance.py"],
        },
        "today_check": {
            "name": "今日脚本验收",
            "description": "编译检查、需求扫描、交付包生成，并写入中文报告。真实平台另点单独按钮验收。",
            "risk": "long_running",
            "mode": "run",
            "timeout": 360,
            "cmd": [py, "scripts/today_ops_check.py", "--skip-acceptance"],
        },
        "build_pack": {
            "name": "生成运营交付包",
            "description": "生成 PPT、Excel、PDF、客服脚本库、需求雷达和操作说明。",
            "risk": "safe",
            "mode": "run",
            "timeout": 180,
            "cmd": [py, "scripts/build_ops_delivery_pack.py"],
        },
        "demand_scan": {
            "name": "扫描文件找需求",
            "description": "扫描本项目和运营资料，生成需求雷达报告、CSV 和 JSON。",
            "risk": "safe",
            "mode": "run",
            "timeout": 180,
            "cmd": [py, "scripts/local_demand_radar.py"],
        },
        "real_platforms": {
            "name": "验收真实平台窗口",
            "description": "检查微信/企业微信/抖音/千牛/拼多多/闲鱼是否打开到真实客服聊天页，并判断可读取方式。",
            "risk": "desktop",
            "mode": "run",
            "timeout": 240,
            "cmd": [py, "scripts/desktop_real_platform_acceptance.py", "--soft"],
        },
        "open_pack": {
            "name": "打开今日交付包",
            "description": "在资源管理器打开 PPT、Excel、PDF 所在文件夹。",
            "risk": "safe",
            "mode": "open_folder",
            "path": "运营计划/今日交付包",
            "cmd": ["open", "运营计划/今日交付包"],
        },
    }


def require_local_request(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    allowed = {"127.0.0.1", "::1", "localhost"}
    forwarded_remote = any(ip and ip not in allowed for ip in [forwarded_for, real_ip])
    if (forwarded_remote or client_host not in allowed) and os.getenv("ALLOW_REMOTE_LOCAL_SCRIPTS") != "1":
        raise HTTPException(
            status_code=403,
            detail="Local script control is only available from this computer. Open http://127.0.0.1:5173/ or set ALLOW_REMOTE_LOCAL_SCRIPTS=1.",
        )


def read_log(path: Path, limit: int = 12000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def finish_run(run_id: str, patch: dict[str, Any]) -> None:
    current = LOCAL_SCRIPT_RUNS[run_id]
    LOCAL_SCRIPT_RUNS[run_id] = current.model_copy(update=patch)
    workflow_run_id = LOCAL_SCRIPT_WORKFLOW_RUNS.get(run_id)
    if workflow_run_id:
        status = patch.get("status")
        workflow_status = "success" if status == "done" else "failed" if status == "failed" else None
        workflow_engine.append_log(
            workflow_run_id,
            f"Local script {current.script_id} finished",
            {"script_run_id": run_id, "returncode": patch.get("returncode")},
            status=workflow_status,
        )


def execute_local_script(run_id: str, script_id: str, spec: dict[str, Any], log_path: Path) -> None:
    cwd = Path.cwd()
    try:
        if spec["mode"] == "open_folder":
            folder = (cwd / spec["path"]).resolve()
            if not folder.exists():
                raise RuntimeError(f"Folder not found: {folder}")
            os.startfile(str(folder))  # type: ignore[attr-defined]
            log_path.write_text(f"Opened folder: {folder}\n", encoding="utf-8")
            finish_run(run_id, {"status": "done", "finished_at": now_iso(), "returncode": 0, "log": read_log(log_path)})
            return

        cmd = [str(item) for item in spec["cmd"]]
        if spec["mode"] == "spawn":
            with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
                process = subprocess.Popen(cmd, cwd=cwd, stdout=log_file, stderr=subprocess.STDOUT)
                log_file.write(f"Started process pid={process.pid}\n")
            finish_run(run_id, {"status": "done", "finished_at": now_iso(), "returncode": 0, "log": read_log(log_path)})
            return

        completed = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(spec.get("timeout", 180)),
            check=False,
        )
        log_path.write_text((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""), encoding="utf-8", errors="replace")
        finish_run(
            run_id,
            {
                "status": "done" if completed.returncode == 0 else "failed",
                "finished_at": now_iso(),
                "returncode": completed.returncode,
                "log": read_log(log_path),
            },
        )
    except Exception as exc:
        log_path.write_text(str(exc), encoding="utf-8", errors="replace")
        finish_run(run_id, {"status": "failed", "finished_at": now_iso(), "returncode": -1, "log": read_log(log_path)})


@app.get("/api/local-scripts", response_model=list[LocalScriptInfo])
async def list_local_scripts(request: Request) -> list[LocalScriptInfo]:
    require_local_request(request)
    catalog = local_script_catalog()
    return [
        LocalScriptInfo(
            id=script_id,
            name=spec["name"],
            description=spec["description"],
            risk=spec["risk"],
            enabled=True,
            command_preview=" ".join(str(item) for item in spec["cmd"]),
        )
        for script_id, spec in catalog.items()
    ]


@app.post("/api/local-scripts/{script_id}/run", response_model=LocalScriptRun)
async def run_local_script(script_id: str, request: Request) -> LocalScriptRun:
    require_local_request(request)
    catalog = local_script_catalog()
    if script_id not in catalog:
        raise HTTPException(status_code=404, detail="Unknown local script")
    run_id = str(uuid.uuid4())
    workflow_run = workflow_engine.create_run(
        workflow_id=f"local_script:{script_id}",
        payload={"script_id": script_id, "risk": catalog[script_id].get("risk")},
        status="running",
    )
    LOCAL_SCRIPT_WORKFLOW_RUNS[run_id] = workflow_run.id
    log_path = LOCAL_SCRIPT_LOG_DIR / f"{run_id}-{script_id}.log"
    run = LocalScriptRun(
        run_id=run_id,
        script_id=script_id,
        workflow_run_id=workflow_run.id,
        status="running",
        started_at=now_iso(),
        log_path=str(log_path),
    )
    workflow_engine.append_log(workflow_run.id, "Local script started", {"script_id": script_id})
    LOCAL_SCRIPT_RUNS[run_id] = run
    thread = threading.Thread(target=execute_local_script, args=(run_id, script_id, catalog[script_id], log_path), daemon=True)
    thread.start()
    return run


@app.get("/api/local-scripts/runs/{run_id}", response_model=LocalScriptRun)
async def get_local_script_run(run_id: str, request: Request) -> LocalScriptRun:
    require_local_request(request)
    if run_id not in LOCAL_SCRIPT_RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    run = LOCAL_SCRIPT_RUNS[run_id]
    log_path = Path(run.log_path)
    return run.model_copy(update={"log": read_log(log_path)})


@app.get("/script-console")
async def script_console_page() -> FileResponse:
    console_path = ARTIFACT_DIR / "script-console.html"
    console_path.write_text(
        """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI脚本控制台</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, "Microsoft YaHei", system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; color: #f8fafc; background: radial-gradient(circle at 20% 20%, rgba(34,211,238,.18), transparent 30%), radial-gradient(circle at 80% 10%, rgba(255,61,154,.18), transparent 34%), #050816; }
    main { width: min(1180px, calc(100% - 36px)); margin: 0 auto; padding: 28px 0 42px; }
    header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-end; margin-bottom: 22px; }
    h1 { margin: 0; font-size: clamp(28px, 4vw, 48px); }
    p { color: #94a3b8; line-height: 1.7; }
    .badge { color: #050816; background: linear-gradient(135deg, #22d3ee, #facc15); padding: 8px 12px; border-radius: 999px; font-weight: 900; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .card, .log { border: 1px solid rgba(148,163,184,.22); background: rgba(15,23,42,.72); border-radius: 14px; padding: 16px; box-shadow: 0 22px 70px rgba(0,0,0,.25); }
    .card { display: grid; gap: 12px; }
    .card h2 { margin: 0; font-size: 18px; }
    .card small { color: #94a3b8; min-height: 44px; }
    button, a.button { border: 0; border-radius: 10px; min-height: 42px; padding: 0 14px; color: #050816; font-weight: 900; background: linear-gradient(135deg, #22d3ee, #facc15); cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
    button:disabled { cursor: wait; filter: grayscale(.6); opacity: .7; }
    .risk { width: fit-content; border: 1px solid rgba(148,163,184,.28); border-radius: 999px; padding: 4px 9px; color: #cbd5e1; font-size: 12px; }
    .log { margin-top: 16px; }
    .logTop { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    pre { white-space: pre-wrap; overflow: auto; min-height: 260px; max-height: 52vh; margin: 12px 0 0; padding: 14px; border-radius: 10px; color: #bbf7d0; background: rgba(0,0,0,.48); }
    .warn { border-color: rgba(250,204,21,.34); color: #fde68a; background: rgba(250,204,21,.08); padding: 12px; border-radius: 12px; }
    @media (max-width: 900px) { header { display: grid; } .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <span class="badge">LOCAL ONLY</span>
        <h1>AI脚本控制台</h1>
        <p>在这台电脑本地运行脚本：启动客服、生成交付包、扫描需求、验收平台。线上网页不能直接控制你电脑里的微信/抖音窗口。</p>
      </div>
      <a class="button" href="/admin" target="_blank">打开AI客服后台</a>
    </header>
    <section class="warn">先打开真实聊天页，再点“验收真实平台窗口”或“启动桌面AI客服”。抖音首页、淘宝普通页面、微信多开外壳都不算客服聊天页。</section>
    <section id="grid" class="grid" style="margin-top:16px"></section>
    <section class="log">
      <div class="logTop">
        <strong id="logTitle">运行日志</strong>
        <button onclick="clearLog()">清空日志</button>
      </div>
      <pre id="log">等待操作...</pre>
    </section>
  </main>
  <script>
    const grid = document.getElementById("grid");
    const logEl = document.getElementById("log");
    const logTitle = document.getElementById("logTitle");
    let polling = null;
    function setLog(text) { logEl.textContent = text || ""; }
    function clearLog() { setLog("等待操作..."); logTitle.textContent = "运行日志"; }
    async function loadScripts() {
      try {
        const res = await fetch("/api/local-scripts");
        if (!res.ok) throw new Error(await res.text());
        const scripts = await res.json();
        grid.innerHTML = scripts.map(item => `
          <article class="card">
            <span class="risk">${item.risk}</span>
            <h2>${item.name}</h2>
            <small>${item.description}</small>
            <button data-id="${item.id}">开始</button>
          </article>
        `).join("");
        grid.querySelectorAll("button[data-id]").forEach(btn => btn.addEventListener("click", () => runScript(btn.dataset.id, btn)));
      } catch (error) {
        grid.innerHTML = "";
        setLog("控制台不可用：" + String(error) + "\\n请确认是从本机 http://127.0.0.1:8000/script-console 打开。");
      }
    }
    async function runScript(id, button) {
      if (polling) clearInterval(polling);
      button.disabled = true;
      setLog("正在启动脚本...");
      try {
        const res = await fetch(`/api/local-scripts/${id}/run`, {method: "POST"});
        if (!res.ok) throw new Error(await res.text());
        const run = await res.json();
        logTitle.textContent = `运行日志：${id}`;
        await pollRun(run.run_id, button);
        polling = setInterval(() => pollRun(run.run_id, button), 1600);
      } catch (error) {
        button.disabled = false;
        setLog("启动失败：" + String(error));
      }
    }
    async function pollRun(runId, button) {
      const res = await fetch(`/api/local-scripts/runs/${runId}`);
      const run = await res.json();
      setLog(`[${run.status}] returncode=${run.returncode ?? ""}\\nlog=${run.log_path}\\n\\n${run.log || ""}`);
      if (run.status === "done" || run.status === "failed") {
        if (polling) clearInterval(polling);
        polling = null;
        button.disabled = false;
      }
    }
    loadScripts();
  </script>
</body>
</html>""",
        encoding="utf-8",
    )
    return FileResponse(console_path)

tasks: dict[str, RenderTask] = {}
projects: dict[str, Project] = {}
assets: dict[str, Asset] = {}
leads: dict[str, Lead] = {}

subscription_plans = [
    SubscriptionPlan(
        id="starter",
        name="Starter",
        price_monthly=99,
        generation_quota=30,
        target="个体商家和单店老板",
        features=["短视频画布", "30 次生成", "作品下载", "抖音线索表单模板"],
    ),
    SubscriptionPlan(
        id="pro",
        name="Pro",
        price_monthly=299,
        generation_quota=150,
        target="电商卖家和多门店运营",
        features=["短视频/主图/详情图", "150 次生成", "批量任务", "客服话术生成"],
    ),
    SubscriptionPlan(
        id="agency",
        name="Agency",
        price_monthly=999,
        generation_quota=800,
        target="AI 代理商和技术服务商",
        features=["团队账号", "模板库", "私有化部署咨询", "API 调用额度"],
    ),
]


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_persistent_store() -> None:
    with DB_LOCK, db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_records (
                kind TEXT NOT NULL,
                id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (kind, id)
            )
            """
        )
        conn.commit()


def save_record(kind: str, record_id: str, payload: BaseModel | dict[str, Any]) -> None:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    timestamp = now_iso()
    with DB_LOCK, db_connect() as conn:
        conn.execute(
            """
            INSERT INTO app_records (kind, id, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (kind, record_id, json.dumps(data, ensure_ascii=False), timestamp, timestamp),
        )
        conn.commit()


def load_record_map(kind: str, model_cls: type[BaseModel]) -> dict[str, Any]:
    init_persistent_store()
    with DB_LOCK, db_connect() as conn:
        rows = conn.execute("SELECT id, payload FROM app_records WHERE kind = ?", (kind,)).fetchall()

    loaded: dict[str, Any] = {}
    for row in rows:
        try:
            loaded[row["id"]] = model_cls.model_validate(json.loads(row["payload"]))
        except (json.JSONDecodeError, ValueError):
            continue
    return loaded


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


init_persistent_store()
tasks.update(load_record_map("task", RenderTask))
projects.update(load_record_map("project", Project))
assets.update(load_record_map("asset", Asset))
leads.update(load_record_map("lead", Lead))


def detect_git_remote() -> bool:
    git_config = Path(".git/config")
    if not git_config.exists():
        return False
    try:
        return "[remote " in git_config.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def detect_hyperframes_page() -> bool:
    candidates = [
        Path("public/hyperframes-portfolio.html"),
        Path("dist/hyperframes-portfolio.html"),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            content = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if 'data-composition-id="merchant-portfolio"' in content and "window.__timelines" in content:
            return True
    return False


def detect_videocut_skills() -> bool:
    skill_root = Path.home() / ".codex" / "skills" / "chengfeng-videocut-skills"
    return (
        (skill_root / "剪口播" / "SKILL.md").exists()
        and (skill_root / "口播成片" / "SKILL.md").exists()
    )


def media_plugin_stack() -> list[MediaPluginStatus]:
    has_hyperframes = detect_hyperframes_page()
    has_videocut = detect_videocut_skills()
    has_ffmpeg = shutil.which("ffmpeg") is not None
    has_volcengine = bool(os.getenv("VOLCENGINE_API_KEY"))
    remotion_worker = os.getenv("REMOTION_RENDER_URL")
    heygen_key = os.getenv("HEYGEN_API_KEY")
    heygen_avatar = os.getenv("HEYGEN_AVATAR_ID")
    return [
        MediaPluginStatus(
            id="videocut-skills",
            name="口播剪辑 Skills",
            role="把口播录屏转成可审核素材包、分镜页、时间线预览和 1080x1440 竖屏成片。",
            runtime="local",
            status="configured" if has_videocut and has_ffmpeg and has_volcengine else "needs_config",
            configured=has_videocut and has_ffmpeg and has_volcengine,
            actions=["剪口播", "生成字幕", "分镜预览", "导出竖屏 MP4"],
            required_env=["VOLCENGINE_API_KEY"],
            next_action="已安装并具备运行条件，可用 Codex 新会话触发剪口播/口播成片。" if has_videocut and has_ffmpeg and has_volcengine else "Skills 已安装；还需要 FFmpeg 命令可用，并在 ~/.codex/skills/chengfeng-videocut-skills/.env 配置 VOLCENGINE_API_KEY。",
        ),
        MediaPluginStatus(
            id="hyperframes",
            name="HyperFrames",
            role="HTML/GSAP showreel、动态字幕、9:16 模板包装和 render-plan JSON。",
            runtime="local",
            status="ready" if has_hyperframes else "needs_config",
            configured=has_hyperframes,
            actions=["展示作品集", "生成模板计划", "导出给渲染 worker"],
            required_env=[],
            next_action="把 render-plan 接到 HyperFrames CLI/worker，输出可下载 MP4。" if has_hyperframes else "补齐 public/hyperframes-portfolio.html。",
        ),
        MediaPluginStatus(
            id="remotion",
            name="Remotion",
            role="React 程序化视频、批量变体、品牌模板、1080x1920 MP4 渲染。",
            runtime="server",
            status="configured" if remotion_worker else "planned",
            configured=bool(remotion_worker),
            actions=["接收 scenes JSON", "渲染单帧预览", "异步输出 MP4", "批量生成版本"],
            required_env=["REMOTION_RENDER_URL"],
            next_action="已检测到 Remotion worker 地址，可把 /api/render 切到真实渲染。" if remotion_worker else "下一步创建 Remotion composition 和 render worker，再配置 REMOTION_RENDER_URL。",
        ),
        MediaPluginStatus(
            id="heygen",
            name="HeyGen",
            role="数字人口播、商家真人讲解、产品演示、销售跟进视频。",
            runtime="external_api",
            status="configured" if heygen_key and heygen_avatar else "needs_config",
            configured=bool(heygen_key and heygen_avatar),
            actions=["生成数字人口播", "绑定脚本文案", "返回视频任务状态", "沉淀到作品库"],
            required_env=["HEYGEN_API_KEY", "HEYGEN_AVATAR_ID"],
            next_action="已检测到 HeyGen 配置，可新增数字人任务接口。" if heygen_key and heygen_avatar else "需要在服务器配置 HeyGen API Key 和 Avatar ID；当前先保留接口位。",
        ),
        MediaPluginStatus(
            id="fireflies",
            name="Fireflies",
            role="会议纪要、商家需求提取、自动生成 brief。",
            runtime="external_api",
            status="planned",
            configured=False,
            actions=["导入会议纪要", "提取需求", "转成商家 brief"],
            required_env=["FIREFLIES_API_KEY"],
            next_action="当前没有可调用插件；先用文本粘贴替代，后续接会议转写 API。",
        ),
    ]


def build_diagnostics() -> SystemDiagnostics:
    checks: list[DiagnosticCheck] = []
    provider = ai_provider_status()
    active_tasks = len([task for task in tasks.values() if task.status in {"queued", "running"}])

    try:
        disk_usage = shutil.disk_usage(DATA_DIR)
        free_gb = disk_usage.free / 1024 / 1024 / 1024
        data_status: Literal["pass", "warn", "fail"] = "pass" if free_gb >= 1 else "warn"
        data_message = f"数据目录可写，剩余约 {free_gb:.1f}GB。"
    except OSError:
        data_status = "fail"
        data_message = "数据目录不可用或无法读取磁盘空间。"

    checks.append(
        DiagnosticCheck(
            id="data-dir",
            name="数据目录",
            status=data_status,
            message=data_message,
            next_action="视频渲染前建议保证服务器和本机都有 5GB 以上可用空间。",
        )
    )
    checks.append(
        DiagnosticCheck(
            id="ai-provider",
            name="AI 生成",
            status="pass" if provider.mode == "ai" else "warn",
            message=f"{provider.provider} 当前为 {provider.mode} 模式。",
            next_action="模板模式可演示流程；正式生成更好内容需要保持 AI Key 可用并记录成本。",
        )
    )
    checks.append(
        DiagnosticCheck(
            id="hyperframes",
            name="HyperFrames 展示页",
            status="pass" if detect_hyperframes_page() else "warn",
            message="已检测到 merchant-portfolio composition。" if detect_hyperframes_page() else "未检测到完整 HyperFrames composition 文件。",
            next_action="下一步把 render-plan JSON 接到真实 HyperFrames CLI/worker 输出 MP4。",
        )
    )
    checks.append(
        DiagnosticCheck(
            id="github",
            name="GitHub 仓库",
            status="pass" if detect_git_remote() else "warn",
            message="当前项目已配置 GitHub remote。" if detect_git_remote() else "当前项目未配置 GitHub remote，只是参考了开源仓库。",
            next_action="公开前创建仓库、补截图、跑密钥扫描，再 push 第一版。",
        )
    )
    checks.append(
        DiagnosticCheck(
            id="fireflies",
            name="Fireflies 会议纪要",
            status="warn",
            message="当前 Codex 会话没有可用 Fireflies 插件。",
            next_action="先用文字粘贴方式沉淀商家需求；后续可接会议转写 API 或安装可用插件。",
        )
    )
    checks.append(
        DiagnosticCheck(
            id="render-queue",
            name="渲染任务队列",
            status="pass",
            message=f"当前活跃任务 {active_tasks} 个，队列接口可用。",
            next_action="MVP 阶段是模拟任务；生产阶段需要 Redis/Celery 和失败重试。",
        )
    )

    if any(check.status == "fail" for check in checks):
        overall: Literal["pass", "warn", "fail"] = "fail"
    elif any(check.status == "warn" for check in checks):
        overall = "warn"
    else:
        overall = "pass"

    return SystemDiagnostics(
        status=overall,
        summary="核心演示功能可用；GitHub 发布、Fireflies 接入和真实视频渲染仍是下一阶段。",
        checks=checks,
    )


def sample_ecommerce_store() -> dict[str, Any]:
    external = Path("C:/Users/Administrator/ecommerce-automation-hub/data/store.json")
    if external.exists():
        try:
            return json.loads(external.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "platforms": [
            {
                "id": "douyin-shop",
                "name": "抖店",
                "mode": "browser",
                "status": "needs_login",
                "capabilities": ["products", "orders", "messages", "inventory"],
            },
            {
                "id": "taobao",
                "name": "淘宝千牛",
                "mode": "browser",
                "status": "planned",
                "capabilities": ["products", "orders", "messages"],
            },
        ],
        "products": [
            {
                "id": "prd_demo_1",
                "name": "夏日青提冰茶",
                "category": "新式茶饮",
                "sku": "GREEN-GRAPE-001",
                "price": 19.9,
                "stock": 88,
                "safetyStock": 20,
                "status": "draft",
            }
        ],
        "orders": [],
        "automationJobs": [
            {
                "id": "job_demo",
                "platform": "抖店",
                "action": "create_listing_draft",
                "mode": "draft_only",
                "status": "ready",
                "productName": "夏日青提冰茶",
                "notes": "只创建商品草稿，最终发布需要人工确认。",
            }
        ],
    }


def ecommerce_stats(store: dict[str, Any]) -> dict[str, int | float]:
    products = store.get("products", [])
    orders = store.get("orders", [])
    return {
        "total_products": len(products),
        "active_products": len([item for item in products if item.get("status") == "active"]),
        "low_stock": len([item for item in products if int(item.get("stock", 0)) <= int(item.get("safetyStock", 0))]),
        "pending_orders": len([item for item in orders if item.get("status") == "pending"]),
        "queued_jobs": len([item for item in store.get("automationJobs", []) if item.get("status") in {"ready", "queued"}]),
    }


def reply_style_label(tone: str) -> str:
    return {
        "warm": "温和真诚",
        "professional": "专业可信",
        "playful": "轻松幽默",
        "high_eq": "高情商自然",
    }.get(tone, "高情商自然")


def contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def build_service_insight(payload: ReplyAssistantRequest, risk_flags: list[str]) -> tuple[ServiceInsight, LeadCaptureSuggestion]:
    text = payload.conversation
    lowered = text.lower()
    score = 38
    tags: list[str] = []

    if contains_any(text, ["多少钱", "价格", "报价", "套餐", "费用", "预算", "贵", "便宜"]):
        score += 18
        tags.append("价格敏感")
    if contains_any(text, ["怎么做", "能不能", "可以吗", "效果", "案例", "样例", "试用", "演示"]):
        score += 16
        tags.append("需要方案")
    if contains_any(text, ["微信", "电话", "手机号", "联系", "预约", "到店", "发我", "加你"]):
        score += 20
        tags.append("可留资")
    if contains_any(text, ["今天", "现在", "马上", "急", "尽快", "本周", "明天"]):
        score += 12
        tags.append("高时效")
    if contains_any(text, ["退款", "投诉", "差评", "骗子", "不满意"]):
        score -= 8
        tags.append("售后风险")
    if contains_any(lowered, ["ai", "saas", "api", "部署", "系统", "自动化"]):
        score += 8
        tags.append("系统型需求")

    score = max(0, min(100, score))
    if score >= 72:
        temperature: Literal["cold", "warm", "hot"] = "hot"
    elif score >= 48:
        temperature = "warm"
    else:
        temperature = "cold"

    if "售后风险" in tags:
        stage = "售后/异议处理"
        intent = "对方可能不满或担心风险，需要先安抚并转人工确认。"
    elif contains_any(text, ["多少钱", "价格", "报价", "套餐", "预算"]):
        stage = "报价比较"
        intent = "对方已经进入价格判断，需要给清晰方案和低门槛试用。"
    elif contains_any(text, ["案例", "样例", "演示", "效果", "试用"]):
        stage = "方案验证"
        intent = "对方想看真实效果，适合发案例并索要素材做小样。"
    elif contains_any(text, ["微信", "电话", "联系", "预约", "加你"]):
        stage = "留资推进"
        intent = "对方有进一步沟通意愿，应快速收联系方式并约下一步。"
    else:
        stage = "首次咨询"
        intent = "对方还在试探，需要先确认场景和目标，不要急着成交。"

    missing_info: list[str] = []
    if not contains_any(text, ["行业", "店", "商品", "产品", "门店", "品牌"]):
        missing_info.append("行业/门店/商品")
    if not contains_any(text, ["预算", "多少钱", "价格", "套餐", "费用"]):
        missing_info.append("预算范围")
    if not contains_any(text, ["今天", "明天", "本周", "什么时候", "时间", "尽快"]):
        missing_info.append("期望交付时间")
    if not contains_any(text, ["微信", "电话", "手机号", "联系", "预约"]):
        missing_info.append("联系方式")
    if not missing_info:
        missing_info.append("已具备基础线索信息")

    urgency = "高" if "高时效" in tags else "中" if temperature != "cold" else "低"
    budget_signal = "已触发价格/套餐讨论" if "价格敏感" in tags else "未明确预算"
    should_handoff = "售后风险" in tags or score >= 78 or any("敏感词" in flag for flag in risk_flags)
    next_best_action = (
        "先人工接管安抚，再确认订单/退款/投诉事实。"
        if "售后风险" in tags
        else "发一个低门槛样例方案，同时收集联系方式和素材。"
        if temperature == "hot"
        else "先问 2 个关键问题：行业/商品是什么、想解决什么转化问题。"
        if temperature == "warm"
        else "用一句自然回复降低防备，再给一个可选方向。"
    )

    business_name = "待确认商家"
    for marker in ["店", "公司", "品牌", "馆", "餐厅", "茶饮"]:
        if marker in text:
            business_name = "聊天中提到的商家"
            break

    if not tags:
        tags = ["待培育"]

    return (
        ServiceInsight(
            stage=stage,
            intent=intent,
            lead_score=score,
            temperature=temperature,
            urgency=urgency,
            budget_signal=budget_signal,
            missing_info=missing_info,
            next_best_action=next_best_action,
            should_handoff=should_handoff,
        ),
        LeadCaptureSuggestion(
            business_name=business_name,
            contact_hint="从聊天中提取；未出现时下一句优先索要微信/手机号。",
            need_summary=f"{payload.scenario}｜目标：{payload.goal}",
            tags=tags,
        ),
    )


def build_reply_assistant_response(payload: ReplyAssistantRequest) -> ReplyAssistantResponse:
    conversation = " ".join(payload.conversation.replace("\r", "\n").split())
    clipped = conversation[:120]
    channel_label = {
        "wechat": "微信",
        "wechat_work": "企业微信",
        "douyin_dm": "抖音私信",
        "taobao": "淘宝/千牛",
        "pdd": "拼多多",
        "xianyu": "闲鱼",
        "customer_service": "客服会话",
        "dating": "关系沟通",
    }[payload.channel]
    style = reply_style_label(payload.tone)
    risk_flags: list[str] = []
    sensitive_terms = ["转账", "银行卡", "密码", "验证码", "退款", "投诉", "发票", "地址", "手机号"]
    for term in sensitive_terms:
        if term in payload.conversation:
            risk_flags.append(f"包含敏感词：{term}，发送前需要人工确认。")
    if not risk_flags:
        risk_flags.append("未发现明显高风险词，但仍建议人工确认后发送。")

    service_insight, lead_capture = build_service_insight(payload, risk_flags)

    if payload.channel == "customer_service":
        candidates = [
            ReplyCandidate(
                label="先确认需求",
                text=f"您好，我看到了您的问题。我先确认一下：您现在主要想解决的是「{payload.goal}」对吗？如果是，我先按您的行业和素材情况给一个最省事的落地方案。",
                why="先复述需求，再进入诊断，不像机器人硬推。",
            ),
            ReplyCandidate(
                label="收集信息",
                text=f"这个能做，但我需要先确认 3 个点：您是什么行业/产品、现在主要缺流量还是缺转化、有没有现成图片或视频素材？确认后我按{payload.scenario}给您出一版小样。",
                why="把对话推进到可执行信息，不只生成漂亮话。",
            ),
            ReplyCandidate(
                label="促成下一步",
                text="如果方便，您先留一个微信或手机号，我把小样和报价发您。您看效果合适再继续，不合适我也会直接告诉您哪里不建议花钱。",
                why="明确收线索，同时降低客户决策压力。",
            ),
        ]
    elif payload.channel == "dating":
        candidates = [
            ReplyCandidate(
                label="自然回应",
                text=f"哈哈我懂你的意思。其实我刚刚也在想怎么回更自然一点，看到你这句我反而觉得挺真实的。{payload.goal}",
                why="不硬撩，先接住对方情绪。",
            ),
            ReplyCandidate(
                label="轻松推进",
                text="你这句话有点意思，我先记下了。那我也认真问一句：如果换成你，你会希望对方怎么接这个话题？",
                why="把尴尬话题变成互动。",
            ),
            ReplyCandidate(
                label="高情商留白",
                text="我不想回得太套路，所以简单说：我愿意继续了解你，但也希望我们都舒服一点，慢慢来就好。",
                why="表达态度，同时不压迫对方。",
            ),
        ]
    else:
        candidates = [
            ReplyCandidate(
                label=f"{style}版",
                text=f"收到，我大概明白你的意思了。关于{payload.scenario}，我先确认一下：你现在最想要的是{payload.goal}，对吗？如果是，我可以按你的情况给一版具体方案。",
                why="复述目标，显得认真且不冒进。",
            ),
            ReplyCandidate(
                label="推进成交版",
                text="这个可以做。我建议先不直接买套餐，你把商品/门店信息和现有素材发我，我先出一版小样；你觉得能用，再继续做完整版本。",
                why="先用小样建立信任，适合商家成交。",
            ),
            ReplyCandidate(
                label="低压力版",
                text="不用急着决定，你可以先把情况发我，我帮你判断适不适合做。适合我给方案，不适合我也会直接说，避免你白花钱。",
                why="降低对方防备，适合私信留资。",
            ),
        ]

    return ReplyAssistantResponse(
        intent_summary=f"{channel_label}场景中，对方大概率在等待你围绕“{payload.scenario}”给出明确回应。聊天片段：{clipped}",
        risk_flags=risk_flags,
        service_insight=service_insight,
        candidates=candidates,
        follow_up_plan=[
            "立即回复：先接住对方情绪或需求，不要上来就推销。",
            "2 小时后：如果未回复，补一个轻量问题或案例截图。",
            "24 小时后：给一次明确下一步，比如预约、试用、小样例或领取资料。",
        ],
        lead_capture=lead_capture,
        safety_note="本助手只生成候选回复，不自动发送。涉及钱款、隐私、退款、投诉、账号权限时必须人工确认。",
    )


def call_openai_compatible_reply_assistant(payload: ReplyAssistantRequest) -> ReplyAssistantResponse:
    ai_engine = default_ai_engine(DATA_DIR)
    if not ai_engine.is_chat_configured():
        raise ValueError("AI provider is not configured")

    fallback = build_reply_assistant_response(payload)
    prompt = f"""
你是一个做商家私域/抖音私信/微信客服成交的 AI 客服主管。
请根据真实聊天内容，生成“不傻、不油、不乱承诺”的客服回复。

渠道：{payload.channel}
场景：{payload.scenario}
目标：{payload.goal}
语气：{payload.tone}
客户画像：{payload.recipient_profile}

聊天记录：
{payload.conversation}

必须遵守：
1. 不要承诺 guaranteed 效果、退款、价格、发票、账号权限，除非聊天里明确出现。
2. 涉及钱款、隐私、退款、投诉、账号权限时，要提醒人工确认。
3. 回复要像真人客服，短一点，具体一点，能推进下一步。
4. 不要只说“您好，请问有什么可以帮您”，要接住客户当前问题。
5. 如果信息不足，先问 1-2 个关键问题，再引导发素材/联系方式/预约。
6. 只返回 JSON，不要 Markdown，不要解释。

JSON 格式：
{{
  "intent_summary": "一句话总结客户真正想要什么",
  "risk_flags": ["风险或注意事项"],
  "candidates": [
    {{"label": "自然确认版", "text": "可直接复制发送的回复", "why": "为什么这么回"}},
    {{"label": "推进成交版", "text": "可直接复制发送的回复", "why": "为什么这么回"}},
    {{"label": "低压力版", "text": "可直接复制发送的回复", "why": "为什么这么回"}}
  ],
  "follow_up_plan": ["立即怎么做", "如果没回怎么跟", "下一步怎么收口"]
}}
"""
    parsed = ai_engine.complete_json(
        system_prompt="你只输出可解析 JSON。你是谨慎、懂成交、懂平台风险的中文客服主管。",
        user_prompt=prompt,
        temperature=float(os.getenv("AI_TEMPERATURE", "0.75")),
        timeout=float(os.getenv("AI_TIMEOUT", "35")),
    )

    candidates: list[ReplyCandidate] = []
    for idx, raw in enumerate(parsed.get("candidates", [])[:3], start=1):
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        candidates.append(
            ReplyCandidate(
                label=str(raw.get("label", f"AI 候选 {idx}")).strip()[:24],
                text=text[:420],
                why=str(raw.get("why", "由 AI 根据当前聊天上下文生成。")).strip()[:160],
            )
        )
    if len(candidates) < 2:
        raise ValueError("AI reply response did not contain enough candidates")

    risk_flags = [str(item).strip() for item in parsed.get("risk_flags", []) if str(item).strip()]
    follow_up_plan = [str(item).strip() for item in parsed.get("follow_up_plan", []) if str(item).strip()]

    return ReplyAssistantResponse(
        intent_summary=str(parsed.get("intent_summary", fallback.intent_summary)).strip()[:360],
        risk_flags=risk_flags or fallback.risk_flags,
        service_insight=fallback.service_insight,
        candidates=candidates,
        follow_up_plan=follow_up_plan[:4] or fallback.follow_up_plan,
        lead_capture=fallback.lead_capture,
        safety_note="AI 已接入，但仍只生成候选回复；涉及钱款、隐私、退款、投诉、账号权限时必须人工确认。",
    )


async def resolve_reply_assistant_response(payload: ReplyAssistantRequest) -> ReplyAssistantResponse:
    status = ai_provider_status()
    if status.mode == "ai":
        try:
            return await asyncio.to_thread(call_openai_compatible_reply_assistant, payload)
        except Exception:
            return build_reply_assistant_response(payload)
    return build_reply_assistant_response(payload)


def normalize_chat_line(line: str) -> ParsedChatMessage | None:
    clean = line.strip().strip("-").strip()
    if not clean:
        return None

    speaker: Literal["me", "customer", "system"] = "customer"
    text = clean
    prefixes: list[tuple[str, Literal["me", "customer", "system"]]] = [
        ("[我]", "me"),
        ("我:", "me"),
        ("我：", "me"),
        ("自己:", "me"),
        ("自己：", "me"),
        ("[对方]", "customer"),
        ("对方:", "customer"),
        ("对方：", "customer"),
        ("客户:", "customer"),
        ("客户：", "customer"),
        ("用户:", "customer"),
        ("用户：", "customer"),
        ("顾客:", "customer"),
        ("顾客：", "customer"),
        ("系统:", "system"),
        ("系统：", "system"),
    ]
    for prefix, detected in prefixes:
        if clean.startswith(prefix):
            speaker = detected
            text = clean[len(prefix) :].strip()
            break

    if not text:
        return None
    return ParsedChatMessage(speaker=speaker, text=text, index=0)


def parse_chat_messages(raw_text: str) -> list[ParsedChatMessage]:
    messages: list[ParsedChatMessage] = []
    buffered_text = ""
    buffered_speaker: Literal["me", "customer", "system"] | None = None

    for line in raw_text.replace("\r\n", "\n").split("\n"):
        clean = line.strip().strip("-").strip()
        parsed = normalize_chat_line(line)
        if parsed is None:
            continue
        has_explicit_prefix = parsed.text != clean
        if has_explicit_prefix:
            if buffered_text and buffered_speaker:
                messages.append(ParsedChatMessage(speaker=buffered_speaker, text=buffered_text.strip(), index=len(messages)))
            buffered_speaker = parsed.speaker
            buffered_text = parsed.text
        elif buffered_text and buffered_speaker:
            buffered_text = f"{buffered_text}\n{parsed.text}"
        else:
            buffered_speaker = parsed.speaker
            buffered_text = parsed.text

    if buffered_text and buffered_speaker:
        messages.append(ParsedChatMessage(speaker=buffered_speaker, text=buffered_text.strip(), index=len(messages)))
    return messages


def get_pending_customer_messages(messages: list[ParsedChatMessage]) -> list[str]:
    last_me_index = -1
    for message in messages:
        if message.speaker == "me":
            last_me_index = message.index
    return [message.text for message in messages if message.speaker == "customer" and message.index > last_me_index]


GROUP_CONTEXT_MARKERS = [
    "群",
    "群聊",
    "群公告",
    "群成员",
    "微信群",
    "群名称",
    "交流群",
    "客户群",
    "全部成员",
    "@所有人",
    "Group",
    "Members",
]

BUSINESS_REPLY_KEYWORDS = [
    "客服",
    "老板",
    "在吗",
    "你好",
    "您好",
    "价格",
    "多少钱",
    "优惠",
    "下单",
    "购买",
    "发货",
    "物流",
    "售后",
    "退款",
    "投诉",
    "订单",
    "预约",
    "地址",
    "电话",
    "微信",
    "链接",
    "怎么用",
]


def classify_conversation_context(payload: ChatReplyAgentRequest, messages: list[ParsedChatMessage]) -> ConversationContext:
    raw_text = payload.ocr_text or ""
    title = payload.window_title or ""
    combined = f"{title}\n{raw_text}"
    aliases = [item.strip() for item in payload.my_aliases if item.strip()]
    mention_tokens = ["@我", "@客服", "@老板", *[f"@{alias}" for alias in aliases], *aliases]

    title_lower = title.lower()
    marker_hits = [marker for marker in GROUP_CONTEXT_MARKERS if marker.lower() in combined.lower()]
    title_group_hit = "群" in title or "group" in title_lower or "群" in raw_text[:80]
    speaker_lines = re.findall(r"(?m)^[\w\u4e00-\u9fa5 ._-]{1,20}[：:]\s*\S+", raw_text)
    speaker_names = {
        line.split(":", 1)[0].split("：", 1)[0].strip()
        for line in speaker_lines
        if line.strip()
    }
    customer_speaker_count = len([name for name in speaker_names if name and name not in {"我", "me", "客服", "系统"}])
    looks_group = bool(title_group_hit or marker_hits or customer_speaker_count >= 3)
    mention_me = any(token and token in combined for token in mention_tokens)
    has_business_keyword = any(keyword in combined for keyword in BUSINESS_REPLY_KEYWORDS)

    high_risk = any(keyword in combined for keyword in ["退款", "投诉", "发票", "付款", "隐私", "账号", "差评", "法律", "赔偿"])
    if high_risk:
        return ConversationContext(
            conversation_type="group" if looks_group else "private",
            mention_me=mention_me,
            reply_mode="handoff",
            confidence=90,
            reason="检测到退款、投诉、付款、隐私或账号等高风险内容，必须人工确认。",
        )

    if looks_group:
        if payload.group_reply_mode == "ignore":
            return ConversationContext(
                conversation_type="group",
                mention_me=mention_me,
                reply_mode="ignore",
                confidence=86,
                reason="当前像群聊，策略设置为群消息不回复。",
            )
        if mention_me:
            return ConversationContext(
                conversation_type="group",
                mention_me=True,
                reply_mode="draft_only",
                confidence=88,
                reason="当前像群聊且有人提到你，只生成草稿，避免群内误发。",
            )
        if payload.group_reply_mode == "draft_on_keyword" and has_business_keyword:
            return ConversationContext(
                conversation_type="group",
                mention_me=False,
                reply_mode="draft_only",
                confidence=76,
                reason="当前像群聊且出现业务关键词，只生成草稿，等待人工确认。",
            )
        return ConversationContext(
            conversation_type="group",
            mention_me=False,
            reply_mode="ignore",
            confidence=82,
            reason="当前像群聊但没有 @你 或明确接待信号，先不回复。",
        )

    if payload.channel == "customer_service":
        return ConversationContext(
            conversation_type="private",
            mention_me=mention_me,
            reply_mode="auto",
            confidence=88,
            reason="自有网页客服会话，可由系统自动回复并落库。",
        )

    return ConversationContext(
        conversation_type="private",
        mention_me=mention_me,
        reply_mode="draft_only",
        confidence=72,
        reason="当前按私聊处理；桌面平台默认只生成或粘贴草稿，发送前人工确认。",
    )


def split_selling_points(brief: MerchantBrief) -> list[str]:
    return [item.strip() for item in brief.selling_points.replace("，", ",").split(",") if item.strip()]


def brief_from_intake(payload: CustomerNeedIntake) -> MerchantBrief:
    selling_points = payload.need_text
    if payload.budget and payload.budget != "待确认":
        selling_points = f"{selling_points}；预算：{payload.budget}"
    if payload.assets:
        selling_points = f"{selling_points}；已有素材：{len(payload.assets)} 个"
    return MerchantBrief(
        industry=payload.industry or "本地商家",
        product_name=payload.product_name or payload.business_name or "商家增长方案",
        selling_points=selling_points,
        platform=payload.platform or "抖音",
        video_type=payload.video_type,
        segment=payload.segment,
        generation_kind=payload.generation_kind,
        style="成交导向",
        budget_mode="balanced",
        audience=payload.audience or "潜在客户",
        call_to_action=payload.call_to_action or "私信领取方案",
    )


def build_script_customer_service_kit(brief: MerchantBrief, script: ScriptVariant) -> ScriptCustomerServiceKit:
    points = split_selling_points(brief)
    primary = points[0] if points else "核心卖点"
    secondary = points[1] if len(points) > 1 else "真实效果"
    third = points[2] if len(points) > 2 else brief.call_to_action
    platform_label = brief.platform or "抖音"
    scene_summary = " / ".join(scene.title for scene in script.scenes[:3])
    target = brief.audience or "潜在客户"

    return ScriptCustomerServiceKit(
        headline=f"{brief.product_name}：短视频脚本 + {platform_label}私信客服闭环",
        script_name=script.name,
        hook=script.hook,
        opening_messages=[
            CustomerServiceLine(
                stage="私信进线",
                goal="承接看完视频后的第一句话",
                message=f"您好，我看到您刚在了解{brief.product_name}。如果您是想解决「{primary}」，我可以先按您的情况判断适不适合。",
                operator_note="不要一上来报价，先承接视频 hook，降低防备。",
            ),
            CustomerServiceLine(
                stage="评论区引导",
                goal="把评论用户引到私信或表单",
                message=f"想要{brief.call_to_action}的，可以私信我发「方案」，我按{target}给你发一版简单说明。",
                operator_note="评论区只做轻承诺，具体需求放到私信确认。",
            ),
        ],
        qualification_flow=[
            CustomerServiceLine(
                stage="需求确认",
                goal="判断客户是否匹配",
                message=f"您主要关注的是{primary}，还是更想了解{secondary}？我好按重点给您推荐。",
                operator_note="二选一问题比开放问题更容易得到回复。",
            ),
            CustomerServiceLine(
                stage="场景确认",
                goal="拿到可成交上下文",
                message=f"您是自己用、给店铺/团队用，还是想先看{brief.product_name}的真实案例？",
                operator_note="为后续案例、价格、预约三种路径分流。",
            ),
            CustomerServiceLine(
                stage="素材/到店条件",
                goal="推进到可交付动作",
                message="您方便发一下现在的素材/店铺/商品链接吗？我先帮您判断最快能做出哪一种效果。",
                operator_note="适合 SaaS 试用、代做案例和私有化咨询。",
            ),
        ],
        objection_handling=[
            CustomerServiceLine(
                stage="担心效果",
                goal="用脚本分镜建立信任",
                message=f"您可以先看这条视频的结构：{scene_summary}。我们不是随机生成，而是按卖点、场景和转化动作来做。",
                operator_note="把视频脚本变成可信解释，不要空喊 AI 很强。",
            ),
            CustomerServiceLine(
                stage="嫌麻烦",
                goal="降低操作门槛",
                message=f"不用您会剪辑，您只要给一句需求或商品链接，我这边先出脚本、分镜和客服话术，确认后再继续生成素材。",
                operator_note="强调老板发需求即可，不要求对方懂工具。",
            ),
            CustomerServiceLine(
                stage="嫌贵/犹豫",
                goal="用低成本试用推进",
                message=f"可以先不做完整套餐。我先给您做一个{brief.product_name}小样例，能看到效果再决定是否继续。",
                operator_note="MVP 阶段最适合用免费小样换真实需求。",
            ),
        ],
        closing_messages=[
            CustomerServiceLine(
                stage="轻成交",
                goal="收联系方式和素材",
                message=f"如果您要试一下，我现在可以帮您走「{brief.call_to_action}」。您发商品/门店资料，我先出一版脚本和客服话术。",
                operator_note="成交动作要具体，避免只说“了解一下”。",
            ),
            CustomerServiceLine(
                stage="预约/表单",
                goal="进入线索池",
                message="我给您留一个试用名额。您把行业、联系方式、想生成的内容类型发我，我按顺序排。",
                operator_note="没有 CRM 前，至少收行业、联系方式、需求类型。",
            ),
        ],
        follow_up_plan=[
            "0 分钟：立即回复，复述客户需求，不直接硬推。",
            "2 小时：未回复则补一条案例或脚本截图。",
            "24 小时：发一次明确小样邀请或优惠提醒。",
            "3 天：进入复购/二次触达，推荐主图、详情图或客服话术升级。",
        ],
        handoff_checklist=[
            "发送前人工确认，尤其涉及价格、退款、隐私、承诺效果时。",
            "每条短视频都要对应一套私信开场、异议处理和成交 CTA。",
            "先做脚本客服闭环，再接真实 MP4 渲染和平台发布。",
            "线索必须沉淀到系统，不要只停留在抖音私信里。",
        ],
    )


def make_scene(scene_id: int, title: str, caption: str, visual: str, accent: str) -> Scene:
    return Scene(
        id=f"scene-{scene_id}",
        title=title,
        caption=caption,
        visual=visual,
        duration=3.2 if scene_id == 1 else 3.8,
        accent=accent,
    )


def scenes_for(brief: MerchantBrief, angle: str) -> list[Scene]:
    points = [p.strip() for p in brief.selling_points.replace("，", ",").split(",") if p.strip()]
    primary = points[0] if points else "解决日常使用痛点"
    secondary = points[1] if len(points) > 1 else "提升体验和效率"

    if brief.generation_kind == "product_image":
        return [
            make_scene(1, "主图构图", f"{brief.product_name}：{primary}", "主体居中、卖点标签、平台安全边距", "#5167f6"),
            make_scene(2, "场景卖点图", secondary, "使用场景、对比元素、信任背书", "#18a999"),
            make_scene(3, "促销收口图", brief.call_to_action, "优惠角标、价格区、行动按钮", "#ff8a3d"),
        ]
    if brief.generation_kind == "detail_page":
        return [
            make_scene(1, "详情页首屏", f"{brief.product_name}解决{primary}", "首屏大图、核心利益点、品牌承诺", "#2f8f83"),
            make_scene(2, "参数和证明", secondary, "参数模块、买家评价、使用步骤", "#f4b942"),
            make_scene(3, "转化模块", brief.call_to_action, "FAQ、保障、下单按钮", "#e4572e"),
        ]
    if brief.generation_kind == "customer_service":
        return [
            make_scene(1, "欢迎语", f"您好，关于{brief.product_name}我可以马上帮您", "客服开场、需求确认、语气友好", "#1f7a8c"),
            make_scene(2, "异议处理", f"如果担心{primary}，可以这样解释", "价格/效果/物流/预约异议话术", "#5167f6"),
            make_scene(3, "成交收口", brief.call_to_action, "优惠提醒、下一步引导、留资确认", "#f2c14e"),
        ]
    if brief.video_type == "local_promo":
        return [
            make_scene(1, "附近的人正在找", f"{brief.industry}新选择：{brief.product_name}", "门店外观、服务动作、真实顾客", "#f05d5e"),
            make_scene(2, "为什么选这家", primary, "店内细节、招牌服务、员工操作", "#2f8f83"),
            make_scene(3, "今天就能体验", f"{secondary}，{brief.call_to_action}", "优惠信息、地图定位、预约入口", "#f4b942"),
        ]
    if brief.video_type == "ecommerce":
        return [
            make_scene(1, "刷到就别错过", f"{brief.product_name}把{primary}做简单", "产品大图、包装、使用前后对比", "#5167f6"),
            make_scene(2, "三秒看懂亮点", secondary, "手持演示、局部特写、卖点贴纸", "#18a999"),
            make_scene(3, "现在下单更划算", brief.call_to_action, "价格标签、库存提示、下单按钮", "#ff8a3d"),
        ]
    return [
        make_scene(1, f"{angle}痛点开场", f"还在为{primary}头疼？", "强 hook 文案、问题场景、快速推近", "#e4572e"),
        make_scene(2, f"{brief.product_name}出现", f"{brief.product_name}帮你{secondary}", "产品展示、核心功能、字幕强调", "#1f7a8c"),
        make_scene(3, "行动转化", f"{brief.audience}现在{brief.call_to_action}", "口播收束、权益提示、二维码/按钮", "#f2c14e"),
    ]


def fallback_scripts_for(brief: MerchantBrief) -> list[ScriptVariant]:
    angle_map = {
        "local_merchant": ["同城转化", "痛点共鸣", "门店信任", "限时活动", "顾客证言"],
        "ecommerce_seller": ["爆款主图", "测评种草", "卖点拆解", "详情页转化", "客服催单"],
        "agency_developer": ["开源演示", "私有部署", "代理商交付", "API 场景", "模板商业化"],
    }
    variants: list[ScriptVariant] = []
    for idx, angle in enumerate(angle_map[brief.segment], start=1):
        scenes = scenes_for(brief, angle)
        variants.append(
            ScriptVariant(
                id=f"script-{idx}",
                name=f"{angle}版",
                hook=scenes[0].caption,
                voiceover=" ".join(scene.caption for scene in scenes),
                scenes=scenes,
                estimated_cost=round(0.8 + idx * 0.18 + random.random() * 0.12, 2),
            )
        )
    return variants


def ai_provider_status() -> ProviderStatus:
    provider = os.getenv("AI_PROVIDER", "template")
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AI_MODEL")
    configured = bool(api_key and model)
    return ProviderStatus(
        provider=provider,
        model=model,
        configured=configured,
        mode="ai" if configured and provider != "template" else "template",
        notes=[
            "支持 OpenAI-compatible /v1/chat/completions",
            "没有配置 AI_API_KEY 和 AI_MODEL 时自动回退模板",
        ],
    )


def normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def image_provider_config() -> tuple[str, str | None, str | None, str]:
    provider = os.getenv("IMAGE_PROVIDER") or ("minimax" if os.getenv("MINIMAX_CN_API_KEY") else "openai_compatible")
    if provider.lower() == "minimax":
        api_key = os.getenv("IMAGE_API_KEY") or os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_CN_API_KEY")
        model = os.getenv("IMAGE_MODEL") or "image-01"
        base_url = (os.getenv("IMAGE_BASE_URL") or os.getenv("MINIMAX_IMAGE_BASE_URL") or "https://api.minimax.io/v1").rstrip("/")
        return provider, api_key, model, base_url
    api_key = os.getenv("IMAGE_API_KEY") or os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("IMAGE_MODEL") or os.getenv("AI_IMAGE_MODEL")
    if not model and "api2d" not in (os.getenv("IMAGE_BASE_URL") or os.getenv("AI_BASE_URL", "")).lower():
        model = "gpt-image-1"
    if model and model.lower() in {"api2d-default", "default", "none"}:
        model = None
    base_url = normalize_openai_base_url(os.getenv("IMAGE_BASE_URL") or os.getenv("AI_BASE_URL", "https://api.openai.com/v1"))
    return provider, api_key, model, base_url


def image_kind_label(image_kind: str) -> str:
    return {
        "main_image": "电商主图",
        "scene_image": "商品场景图",
        "detail_image": "详情页卖点图",
    }[image_kind]


def build_image_prompt(payload: ImageGenerationRequest) -> str:
    brief = payload.brief
    kind = image_kind_label(payload.image_kind)
    prompt = payload.prompt.strip() if payload.prompt else ""
    if prompt:
        return prompt
    layout_rule = {
        "main_image": "单张电商主图，主体居中，背景干净，有清晰卖点标签，保留平台安全边距，不要杂乱文字。",
        "scene_image": "真实使用场景图，产品在自然场景中出现，画面高级、有生活感，突出使用前后差异。",
        "detail_image": "详情页卖点图，一张图解释一个核心卖点，包含标题区、产品特写区、对比/证明区和行动引导区。",
    }[payload.image_kind]
    return (
        f"为中国电商/抖音商家生成一张{kind}。"
        f"行业：{brief.industry}。产品/门店/方案：{brief.product_name}。"
        f"核心卖点：{brief.selling_points}。目标人群：{brief.audience}。"
        f"转化动作：{brief.call_to_action}。"
        f"视觉要求：{layout_rule}"
        "风格：商业广告级、干净、高质感、适合手机端浏览、不要低清、不要畸形文字、不要夸张假货感。"
    )


def save_b64_image(b64_json: str, suffix: str = "png") -> str:
    image_id = str(uuid.uuid4())
    artifact_name = f"{image_id}.{suffix}"
    artifact_path = ARTIFACT_DIR / artifact_name
    artifact_path.write_bytes(base64.b64decode(b64_json))
    return f"/artifacts/{artifact_name}"


def save_image_bytes(data: bytes, suffix: str = "png") -> str:
    image_id = str(uuid.uuid4())
    artifact_name = f"{image_id}.{suffix}"
    artifact_path = ARTIFACT_DIR / artifact_name
    artifact_path.write_bytes(data)
    return f"/artifacts/{artifact_name}"


def download_image_artifact(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=float(os.getenv("IMAGE_DOWNLOAD_TIMEOUT", "45"))) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read()
        suffix = "jpg" if "jpeg" in content_type or url.lower().split("?")[0].endswith((".jpg", ".jpeg")) else "png"
        return save_image_bytes(raw, suffix)
    except Exception:
        return None


def call_minimax_image(payload: ImageGenerationRequest, api_key: str, model: str | None, base_url: str) -> ImageGenerationResponse:
    prompt = build_image_prompt(payload)[:1500]
    body = {
        "model": model or "image-01",
        "prompt": prompt,
        "aspect_ratio": os.getenv("IMAGE_ASPECT_RATIO", "9:16"),
        "response_format": os.getenv("MINIMAX_IMAGE_RESPONSE_FORMAT", "url"),
        "n": 1,
        "prompt_optimizer": os.getenv("MINIMAX_PROMPT_OPTIMIZER", "true").lower() not in {"0", "false", "no"},
    }
    request = urllib.request.Request(
        f"{base_url}/image_generation",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("IMAGE_TIMEOUT", "120"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    base_resp = data.get("base_resp") or {}
    if int(base_resp.get("status_code", 0) or 0) != 0:
        raise ValueError(base_resp.get("status_msg") or "MiniMax image generation failed")
    image_urls = ((data.get("data") or {}).get("image_urls") or [])
    image_url = image_urls[0] if image_urls else None
    b64_items = ((data.get("data") or {}).get("images") or (data.get("data") or {}).get("image_base64") or [])
    artifact_url = None
    if image_url:
        artifact_url = download_image_artifact(str(image_url))
    elif b64_items:
        first = b64_items[0] if isinstance(b64_items, list) else b64_items
        artifact_url = save_b64_image(str(first))
    if not image_url and not artifact_url:
        raise ValueError("MiniMax returned no image url or base64 image")
    return ImageGenerationResponse(
        mode="image",
        provider="minimax",
        model=model or "image-01",
        prompt=prompt,
        image_url=str(image_url) if image_url else None,
        artifact_url=artifact_url,
        next_action="MiniMax 图片已生成并保存到本地 artifacts，可继续生成详情图、场景图和视频预览。",
    )


def call_openai_compatible_image(payload: ImageGenerationRequest) -> ImageGenerationResponse:
    provider, api_key, model, base_url = image_provider_config()
    prompt = build_image_prompt(payload)
    if not api_key:
        return ImageGenerationResponse(
            mode="prompt",
            provider=provider,
            model=model,
            prompt=prompt,
            next_action="图片模型未配置，先复制 prompt 到 302.AI、扣子工作流或图片模型里生成。",
        )
    if provider.lower() == "minimax":
        return call_minimax_image(payload, api_key, model, base_url)

    result = default_ai_engine(DATA_DIR).generate_image(prompt)
    if not result.image_url and not result.artifact_url:
        raise ValueError("Image provider returned no url or b64_json")
    return ImageGenerationResponse(
        mode="image",
        provider=provider,
        model=model,
        prompt=prompt,
        image_url=result.image_url,
        artifact_url=result.artifact_url,
        next_action="图片已生成，可下载、换提示词重生成，或进入主图/详情图排版。",
    )


def parse_ai_json(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def normalize_ai_text(text: str, brief: MerchantBrief) -> str:
    normalized = text
    if "餐" not in brief.industry and "食" not in brief.industry:
        for forbidden in ["美食", "外卖", "餐厅", "吃饭"]:
            normalized = normalized.replace(forbidden, brief.product_name)
    return normalized


def has_brief_keyword(text: str, brief: MerchantBrief) -> bool:
    keywords = [
        brief.product_name,
        brief.industry,
        brief.product_name[:2],
        brief.industry[:2],
    ]
    return any(keyword and keyword in text for keyword in keywords)


def validate_ai_scripts(payload: dict, brief: MerchantBrief) -> list[ScriptVariant]:
    raw_variants = payload.get("scripts", [])
    variants: list[ScriptVariant] = []
    for idx, raw in enumerate(raw_variants[:5], start=1):
        raw_scenes = raw.get("scenes", [])[:4]
        scenes = [
            Scene(
                id=f"ai-scene-{idx}-{scene_idx}",
                title=normalize_ai_text(str(scene.get("title", f"分镜 {scene_idx}")), brief)[:32],
                caption=normalize_ai_text(str(scene.get("caption", "")), brief)[:90],
                visual=normalize_ai_text(str(scene.get("visual", "")), brief)[:120],
                duration=float(scene.get("duration", 3.5)),
                accent=str(scene.get("accent", ["#f05d5e", "#2f8f83", "#5167f6", "#f2c14e"][scene_idx % 4])),
            )
            for scene_idx, scene in enumerate(raw_scenes, start=1)
        ]
        if len(scenes) < 3:
            continue
        name = normalize_ai_text(str(raw.get("name", f"AI 创意 {idx}")), brief)[:32]
        hook = normalize_ai_text(str(raw.get("hook", scenes[0].caption)), brief)[:90]
        if not has_brief_keyword(f"{name}{hook}", brief):
            name = f"{brief.product_name}{name}"[:32]
            hook = f"{brief.product_name}：{hook}"[:90]
        variants.append(
            ScriptVariant(
                id=f"ai-script-{idx}",
                name=name,
                hook=hook,
                voiceover=normalize_ai_text(str(raw.get("voiceover", " ".join(scene.caption for scene in scenes))), brief)[:500],
                scenes=scenes,
                estimated_cost=round(float(raw.get("estimated_cost", 1.2 + idx * 0.25)), 2),
            )
        )
    if not variants:
        raise ValueError("AI response did not contain valid scripts")
    return variants


def call_openai_compatible(brief: MerchantBrief) -> list[ScriptVariant]:
    ai_engine = default_ai_engine(DATA_DIR)
    if not ai_engine.is_chat_configured():
        raise ValueError("AI provider is not configured")

    generation_label = {
        "short_video": "抖音短视频脚本和 9:16 分镜",
        "product_image": "电商主图和场景图创意",
        "detail_page": "商品详情页结构",
        "customer_service": "客服成交话术",
    }[brief.generation_kind]
    segment_label = {
        "local_merchant": "本地商家",
        "ecommerce_seller": "电商卖家",
        "agency_developer": "AI 代理商/开发者",
    }[brief.segment]
    prompt = f"""
你是中国抖音/小红书/电商增长创意总监。请为商家生成更有网感、更具体、更能成交的内容方案。

客户类型：{segment_label}
生成类型：{generation_label}
行业：{brief.industry}
产品/门店/方案：{brief.product_name}
卖点：{brief.selling_points}
平台：{brief.platform}
目标人群：{brief.audience}
转化动作：{brief.call_to_action}

要求：
1. 输出 5 个差异明显的创意版本，不要普通，不要空泛。
2. 每个版本 3-4 个分镜，caption 要能直接上屏，visual 要具体到镜头/构图/素材。
3. 本地商家要偏同城、门店信任、优惠转化；电商要偏主图卖点、详情页转化、客服逼单；代理商要偏开源、私有化、交付赚钱。
4. 严禁改行业、改产品、改品类；必须围绕“{brief.industry}”和“{brief.product_name}”。
5. 每个版本 name 或 hook 必须出现“{brief.product_name}”或“{brief.industry}”中的至少一个关键词。
6. 如果行业不是餐饮，不得出现“美食、外卖、餐厅、吃饭”等无关词。
7. 只返回 JSON，不要解释。

JSON 格式：
{{
  "scripts": [
    {{
      "name": "版本名",
      "hook": "开头钩子",
      "voiceover": "完整口播/文案",
      "estimated_cost": 1.2,
      "scenes": [
        {{"title": "分镜名", "caption": "上屏文案", "visual": "镜头/画面/素材说明", "duration": 3.5, "accent": "#f05d5e"}}
      ]
    }}
  ]
}}
"""
    parsed = ai_engine.complete_json(
        system_prompt="你只输出可解析 JSON。",
        user_prompt=prompt,
        temperature=float(os.getenv("AI_TEMPERATURE", "0.85")),
        timeout=float(os.getenv("AI_TIMEOUT", "35")),
    )
    return validate_ai_scripts(parsed, brief)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "data_dir": str(DATA_DIR), "db_path": str(DB_PATH)}


@app.get("/api/providers", response_model=ProviderStatus)
async def provider_status() -> ProviderStatus:
    return ai_provider_status()


@app.get("/api/ai-engine/status", response_model=ProviderStatus)
async def ai_engine_status() -> ProviderStatus:
    return ai_provider_status()


@app.get("/api/connectors", response_model=list[ConnectorResult])
async def connector_statuses() -> list[ConnectorResult]:
    return list_connectors()


@app.get("/api/workflows/runs", response_model=list[WorkflowRun])
async def workflow_runs() -> list[WorkflowRun]:
    return sorted(workflow_engine.runs.values(), key=lambda item: item.created_at, reverse=True)


@app.get("/api/system/diagnostics", response_model=SystemDiagnostics)
async def system_diagnostics() -> SystemDiagnostics:
    return build_diagnostics()


@app.get("/api/integrations/media-stack", response_model=list[MediaPluginStatus])
async def integrations_media_stack() -> list[MediaPluginStatus]:
    return media_plugin_stack()


@app.post("/api/scripts", response_model=list[ScriptVariant])
async def generate_scripts(brief: MerchantBrief) -> list[ScriptVariant]:
    status = ai_provider_status()
    if status.mode == "ai":
        try:
            return await asyncio.to_thread(call_openai_compatible, brief)
        except Exception:
            return fallback_scripts_for(brief)
    return fallback_scripts_for(brief)


@app.post("/api/projects", response_model=Project)
async def create_project(brief: MerchantBrief) -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        name=f"{brief.product_name} - {brief.platform}",
        segment=brief.segment,
        brief=brief,
        created_at=now_iso(),
    )
    projects[project.id] = project
    save_record("project", project.id, project)
    return project


@app.get("/api/projects", response_model=list[Project])
async def list_projects() -> list[Project]:
    return sorted(projects.values(), key=lambda item: item.created_at, reverse=True)


@app.get("/api/assets", response_model=list[Asset])
async def list_assets() -> list[Asset]:
    return sorted(assets.values(), key=lambda item: item.created_at, reverse=True)


@app.post("/api/leads", response_model=Lead)
async def create_lead(payload: LeadCreate) -> Lead:
    lead = Lead(id=str(uuid.uuid4()), created_at=now_iso(), **payload.model_dump())
    leads[lead.id] = lead
    save_record("lead", lead.id, lead)
    return lead


@app.post("/api/intake/customer-need", response_model=CustomerNeedIntakeResponse)
async def intake_customer_need(payload: CustomerNeedIntake) -> CustomerNeedIntakeResponse:
    brief = brief_from_intake(payload)
    lead = Lead(
        id=str(uuid.uuid4()),
        source=payload.source,
        industry=brief.industry,
        business_name=payload.business_name,
        contact=payload.contact or "待补充",
        need=payload.need_text,
        created_at=now_iso(),
    )
    leads[lead.id] = lead
    save_record("lead", lead.id, lead)

    project = Project(
        id=str(uuid.uuid4()),
        name=f"{brief.product_name} - {brief.platform}",
        segment=brief.segment,
        brief=brief,
        created_at=now_iso(),
    )
    projects[project.id] = project
    save_record("project", project.id, project)

    scripts = fallback_scripts_for(brief)
    reply_analysis = build_reply_assistant_response(
        ReplyAssistantRequest(
            channel="douyin_dm" if payload.source == "douyin" else "customer_service",
            scenario=f"{brief.platform}客户需求接入",
            conversation=payload.customer_message or payload.need_text,
            goal=brief.call_to_action,
            tone="high_eq",
            recipient_profile=payload.business_name,
        )
    )
    return CustomerNeedIntakeResponse(
        intake_id=str(uuid.uuid4()),
        lead=lead,
        project=project,
        brief=brief,
        scripts=scripts,
        reply_analysis=reply_analysis,
        next_actions=[
            "客服先按 reply_analysis.next_best_action 回复客户。",
            "运营从 scripts 里选一个方向生成短视频/主图/详情页。",
            "销售在 leads 里跟进联系方式和试用状态。",
            "如果来自抖音小程序或表单，下一步把 source、contact、need_text 字段直连到这个接口。",
        ],
    )


@app.get("/api/leads", response_model=list[Lead])
async def list_leads() -> list[Lead]:
    return sorted(leads.values(), key=lambda item: item.created_at, reverse=True)


@app.get("/api/subscriptions", response_model=list[SubscriptionPlan])
async def list_subscriptions() -> list[SubscriptionPlan]:
    return subscription_plans


@app.get("/api/admin/overview", response_model=AdminOverview)
async def admin_overview() -> AdminOverview:
    active_tasks = len([task for task in tasks.values() if task.status in {"queued", "running"}])
    paid_pipeline = len([lead for lead in leads.values() if lead.status in {"trial", "paid"}])
    return AdminOverview(
        projects=len(projects),
        leads=len(leads),
        active_tasks=active_tasks,
        paid_pipeline=paid_pipeline,
        conversion_loop=["抖音内容", "企业号线索", "AI 生成素材", "客服跟进", "SaaS 订阅/私有化"],
    )


@app.get("/api/ecosystem", response_model=list[EcosystemModule])
async def bytedance_ecosystem() -> list[EcosystemModule]:
    return [
        EcosystemModule(
            id="douyin",
            name="抖音同城/企业号",
            channel="流量入口",
            purpose="发布案例短视频，承接私信、表单和预约线索",
            status="manual",
            next_action="先用企业号主页、线索表单和私信跑通转化",
        ),
        EcosystemModule(
            id="ocean-engine",
            name="巨量引擎",
            channel="投放放大",
            purpose="用跑通的 demo 素材做小预算投放测试",
            status="planned",
            next_action="等自然流量验证话术后再投 100-300 元/天",
        ),
        EcosystemModule(
            id="jianying",
            name="剪映/CapCut",
            channel="编辑交付",
            purpose="把生成分镜导出为人工可继续剪辑的脚本和素材清单",
            status="planned",
            next_action="增加剪映脚本导出格式和字幕 SRT",
        ),
        EcosystemModule(
            id="feishu",
            name="飞书多维表格",
            channel="运营中台",
            purpose="沉淀商家、线索、内容日历和交付状态",
            status="planned",
            next_action="后续把 Lead/Project 同步到飞书表格",
        ),
        EcosystemModule(
            id="volcengine",
            name="火山引擎",
            channel="AI 能力",
            purpose="接入语音、图像、视频、内容审核和对象存储",
            status="planned",
            next_action="先保留 Provider Adapter，等付费验证后再接入",
        ),
        EcosystemModule(
            id="heygen-remotion-hyperframes",
            name="HeyGen / Remotion / HyperFrames",
            channel="高级生成",
            purpose="用于数字人口播、模板化视频渲染和动画包装",
            status="planned",
            next_action="当前保留生成适配器位置，第二阶段接真实渲染",
        ),
    ]


@app.get("/api/ecommerce/automation-snapshot", response_model=EcommerceSnapshot)
async def ecommerce_automation_snapshot() -> EcommerceSnapshot:
    store = sample_ecommerce_store()
    platforms = [
        PlatformConnector(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            mode=item.get("mode", "browser") if item.get("mode") in {"browser", "api", "manual"} else "browser",
            status=item.get("status", "planned") if item.get("status") in {"ready", "needs_login", "planned"} else "planned",
            capabilities=[str(capability) for capability in item.get("capabilities", [])],
            guardrail="默认只读或草稿模式，发布、改价、退款、发货必须人工确认。",
        )
        for item in store.get("platforms", [])
    ]
    products = [
        EcommerceProduct(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            category=str(item.get("category", "")),
            sku=str(item.get("sku", "")),
            price=float(item.get("price", 0)),
            stock=int(item.get("stock", 0)),
            safety_stock=int(item.get("safetyStock", 0)),
            status=item.get("status", "draft") if item.get("status") in {"draft", "active", "paused"} else "draft",
            next_action="生成主图/详情图/短视频后进入平台草稿",
        )
        for item in store.get("products", [])
    ]
    orders = [
        EcommerceOrder(
            id=str(item.get("id", "")),
            platform=str(item.get("platform", "")),
            order_no=str(item.get("orderNo", "")),
            customer=str(item.get("customer", "")),
            product_name=str(item.get("productName", "")),
            amount=float(item.get("amount", 0)),
            status=str(item.get("status", "")),
            exception=str(item.get("exception", "")),
        )
        for item in store.get("orders", [])
    ]
    jobs = [
        AutomationJob(
            id=str(item.get("id", "")),
            platform=str(item.get("platform", "")),
            action=str(item.get("action", "")),
            mode=item.get("mode", "read_only")
            if item.get("mode") in {"read_only", "draft_only", "requires_confirmation"}
            else "read_only",
            status=item.get("status", "ready") if item.get("status") in {"ready", "queued", "running", "done", "blocked"} else "ready",
            product_name=str(item.get("productName", "")),
            notes=str(item.get("notes", "等待人工确认。")),
        )
        for item in store.get("automationJobs", [])
    ]
    return EcommerceSnapshot(
        platforms=platforms,
        products=products,
        orders=orders,
        automation_jobs=jobs,
        stats=ecommerce_stats(store),
        recommended_flow=[
            "录入商品档案",
            "生成主图/详情图/短视频",
            "创建平台草稿",
            "AI 客服准备异议话术",
            "人工确认发布或回复",
        ],
    )


@app.get("/api/ecommerce/snapshot", response_model=EcommerceSnapshot)
async def ecommerce_snapshot_alias() -> EcommerceSnapshot:
    return await ecommerce_automation_snapshot()


def build_ecommerce_listing_draft(payload: EcommerceListingDraftRequest) -> EcommerceListingDraftResponse:
    points = [item.strip() for item in re.split(r"[,，\n/]+", payload.selling_points) if item.strip()]
    if not points:
        points = ["核心卖点清晰", "适合平台转化", "可批量生成素材"]
    primary = points[0]
    secondary = points[1] if len(points) > 1 else "提升下单转化"
    platform_name = {
        "douyin": "抖音小店",
        "taobao": "淘宝",
        "pdd": "拼多多",
        "xianyu": "闲鱼",
        "xiaohongshu": "小红书店铺",
    }[payload.platform]
    product_name = payload.product_name.strip()
    titles = [
        f"{product_name} {primary} {payload.category}",
        f"{product_name} {secondary} 现货可拍",
        f"{payload.audience}适用 {product_name} {primary}",
    ]
    detail_sections = [
        f"首屏大图：{product_name} + {primary} + 价格/活动入口",
        f"痛点场景：展示{payload.audience}为什么需要这个商品",
        f"卖点证明：{'; '.join(points[:5])}",
        "规格参数：SKU、尺寸、材质、适用场景、发货说明",
        "信任收口：售后承诺、评价截图、下单提醒，最终发布前人工确认",
    ]
    main_image_prompts = [
        f"竖版9:16电商主图，{payload.visual_style}，商品为{product_name}，主体居中，蓝紫发光商业海报质感，大标题写“{primary}”，副标题写“{payload.price}”，画面包含商品卡片、价格标签、平台上架草稿按钮，高清，适合抖音封面。",
        f"商品详情页长图首屏，{payload.visual_style}，{product_name}真实产品展示，包含3个卖点模块：{'; '.join(points[:3])}，视觉高级、干净、转化感强，移动端安全边距。",
        f"批量上架功能宣传图，展示上传商品资料、AI生成图片、生成标题卖点、保存平台草稿四步流程，风格参考赛博霓虹电商SaaS后台。",
    ]
    sku_table = [
        {"sku": item.strip(), "price": payload.price, "stock": payload.stock}
        for item in re.split(r"[,，/]+", payload.sku_options)
        if item.strip()
    ]
    if not sku_table:
        sku_table = [{"sku": "标准款", "price": payload.price, "stock": payload.stock}]
    listing_fields = {
        "platform": platform_name,
        "category": payload.category,
        "title": titles[0],
        "short_title": f"{product_name} {primary}"[:30],
        "price": payload.price,
        "shipping": payload.shipping,
        "after_sales": payload.after_sales,
        "description": "。".join(detail_sections),
    }
    response = EcommerceListingDraftResponse(
        draft_id=str(uuid.uuid4()),
        platform=platform_name,
        product_name=product_name,
        titles=titles,
        short_title=listing_fields["short_title"],
        selling_points=points,
        main_image_prompts=main_image_prompts,
        detail_sections=detail_sections,
        sku_table=sku_table,
        listing_fields=listing_fields,
        customer_faq=[
            {"question": "这个适合我吗？", "answer": f"如果您主要关注{primary}，这款{product_name}可以优先看；具体规格和使用场景建议再确认一下。"},
            {"question": "多久发货？", "answer": payload.shipping},
            {"question": "售后怎么处理？", "answer": payload.after_sales},
        ],
        risk_checks=[
            "只生成商品草稿，不自动发布。",
            "价格、库存、售后、发货承诺必须由商家最终确认。",
            "避免绝对化用语：第一、最强、永久有效、保证治愈、100%成交等。",
            "涉及功效、食品、化妆品、医疗、金融等类目时，必须补齐资质和平台审核材料。",
        ],
        publish_boundary="save_draft_only",
        next_action="把主图提示词交给图片模型生成图片，再把 listing_fields 填入平台草稿，最终发布前人工确认。",
    )
    save_record("ecommerce_listing_draft", response.draft_id, {"request": payload.model_dump(), "response": response.model_dump()})
    return response


@app.post("/api/ecommerce/listing-draft", response_model=EcommerceListingDraftResponse)
async def ecommerce_listing_draft(payload: EcommerceListingDraftRequest) -> EcommerceListingDraftResponse:
    return build_ecommerce_listing_draft(payload)


def split_points_text(text: str) -> list[str]:
    points = [item.strip() for item in re.split(r"[,，/、\n]+", text) if item.strip()]
    return points or ["核心卖点清晰", "适合平台转化", "可批量生成素材"]


def write_artifact(filename: str, content: str | bytes, binary: bool = False) -> str:
    path = ARTIFACT_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    else:
        path.write_text(content if isinstance(content, str) else content.decode("utf-8"), encoding="utf-8")
    return f"/artifacts/{filename}"


def find_chinese_font(size: int, bold: bool = True):
    from PIL import ImageFont  # type: ignore

    linux_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansSC-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        *linux_candidates,
    ]
    font_roots = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]
    patterns = ["*NotoSansCJK*", "*NotoSansSC*", "*SourceHanSans*", "*DroidSansFallback*", "*wqy*", "*uming*", "*ukai*"]
    for root in font_roots:
        if root.exists():
            for pattern in patterns:
                candidates.extend(str(path) for path in root.rglob(pattern) if path.suffix.lower() in {".ttf", ".ttc", ".otf"})
    for font in candidates:
        path = Path(font)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def vertical_gradient(size: tuple[int, int], colors: list[tuple[int, int, int]]) -> Any:
    from PIL import Image, ImageDraw  # type: ignore

    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    if len(colors) < 2:
        colors = [colors[0], colors[0]]
    segments = len(colors) - 1
    for y in range(height):
        pos = y / max(1, height - 1)
        idx = min(segments - 1, int(pos * segments))
        local = pos * segments - idx
        c1, c2 = colors[idx], colors[idx + 1]
        color = tuple(int(c1[channel] + (c2[channel] - c1[channel]) * local) for channel in range(3))
        draw.line((0, y, width, y), fill=color)
    return image


def draw_center_text(draw: Any, xy: tuple[int, int], text: str, font: Any, fill: tuple[int, int, int], stroke: int = 0, stroke_fill: tuple[int, int, int] = (0, 0, 0)) -> None:
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1]), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def draw_wrapped_text(draw: Any, xy: tuple[int, int], text: str, font: Any, fill: tuple[int, int, int], max_chars: int, line_height: int, max_lines: int = 3) -> None:
    lines: list[str] = []
    line = ""
    for char in text:
        line += char
        if len(line) >= max_chars:
            lines.append(line)
            line = ""
    if line:
        lines.append(line)
    for idx, line in enumerate(lines[:max_lines]):
        draw.text((xy[0], xy[1] + idx * line_height), line, font=font, fill=fill)


def product_thumb_image(payload: ProductMediaPackRequest, size: tuple[int, int], color: tuple[int, int, int], label: str):
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageOps  # type: ignore

    if payload.product_image_data_url and payload.product_image_data_url.startswith("data:image/"):
        try:
            raw = payload.product_image_data_url.split(",", 1)[1]
            image = Image.open(BytesIO(base64.b64decode(raw))).convert("RGB")
            return ImageOps.fit(image, size)
        except Exception:
            pass
    card = vertical_gradient(size, [(245, 243, 255), color, (24, 30, 84)])
    draw = ImageDraw.Draw(card)
    w, h = size
    draw.ellipse((w * 0.24, h * 0.12, w * 0.76, h * 0.52), fill=(230, 244, 255))
    draw.rounded_rectangle((w * 0.39, h * 0.2, w * 0.61, h * 0.78), radius=30, fill=(255, 255, 255))
    draw.rounded_rectangle((w * 0.43, h * 0.14, w * 0.57, h * 0.26), radius=16, fill=(205, 224, 255))
    draw.text((18, h - 42), label[:8], font=find_chinese_font(24), fill=(255, 255, 255))
    return card


def draw_neon_card(draw: Any, box: tuple[int, int, int, int], outline: tuple[int, int, int], fill: tuple[int, int, int] = (18, 24, 62)) -> None:
    x1, y1, x2, y2 = box
    for offset, alpha in [(10, 45), (5, 80), (0, 255)]:
        color = tuple(min(255, int(channel + (255 - channel) * (1 - alpha / 255))) for channel in outline)
        draw.rounded_rectangle((x1 - offset, y1 - offset, x2 + offset, y2 + offset), radius=34 + offset, outline=color, width=2)
    draw.rounded_rectangle(box, radius=30, fill=fill, outline=outline, width=2)


def render_boom_materials_png(payload: ProductMediaPackRequest, variant: Literal["main", "detail", "scene"]) -> bytes:
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFilter  # type: ignore

    width, height = 1080, 1920
    points = split_points_text(payload.selling_points)
    title = "爆款素材批量生成" if variant == "main" else ("AI商品图自动生成" if variant == "detail" else "多场景投放图片")
    subtitle = "一份商品资料，生成多套投放图片" if variant == "main" else f"{payload.product_name} 主图 / 详情图 / 上架资料"
    bg = vertical_gradient((width, height), [(2, 5, 22), (15, 19, 72), (43, 12, 92), (4, 10, 32)]).convert("RGBA")
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-120, 50, 420, 590), fill=(74, 144, 255, 46))
    g.ellipse((660, 240, 1280, 880), fill=(211, 55, 255, 50))
    g.ellipse((120, 1180, 1020, 1990), fill=(37, 99, 235, 45))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(34)))
    draw = ImageDraw.Draw(bg)

    font_huge = find_chinese_font(92)
    font_title = find_chinese_font(46)
    font_mid = find_chinese_font(31)
    font_small = find_chinese_font(22)
    font_tiny = find_chinese_font(18)

    draw_center_text(draw, (width // 2, 82), "AI电商 | 智能创作 · 一键上架", font_mid, (235, 243, 255), 1, (70, 30, 180))
    draw_center_text(draw, (width // 2, 175), title, font_huge, (255, 255, 255), 3, (150, 50, 255))
    draw.rounded_rectangle((170, 310, 910, 388), radius=39, fill=(88, 54, 220), outline=(121, 229, 255), width=2)
    draw_center_text(draw, (width // 2, 326), subtitle, font_title, (255, 255, 255), 1, (20, 24, 80))

    feature_y = 458
    features = [("批量上传商品", "支持多种格式"), ("AI智能生成", "多风格多尺寸"), ("多场景适配", "主图/场景/海报"), ("高效出图", "节省时间成本")]
    for idx, (name, desc) in enumerate(features):
        x = 100 + idx * 235
        draw.rounded_rectangle((x, feature_y, x + 190, feature_y + 86), radius=24, fill=(16, 23, 68), outline=(120, 95, 255), width=2)
        draw.ellipse((x + 18, feature_y + 18, x + 68, feature_y + 68), fill=(93, 42, 220), outline=(130, 230, 255), width=2)
        draw.text((x + 80, feature_y + 18), name, font=font_small, fill=(255, 255, 255))
        draw.text((x + 80, feature_y + 50), desc, font=font_tiny, fill=(183, 202, 255))

    draw_neon_card(draw, (38, 620, 1042, 1004), (120, 170, 255), (18, 24, 72))
    draw.text((76, 655), "批量上传商品资料", font=font_title, fill=(255, 255, 255))
    draw.rounded_rectangle((78, 735, 248, 930), radius=20, fill=(30, 34, 92), outline=(160, 178, 255), width=2)
    draw_center_text(draw, (163, 800), "☁", find_chinese_font(62), (255, 255, 255))
    draw_center_text(draw, (163, 872), "点击或拖拽上传", font_small, (255, 255, 255))
    colors = [(75, 108, 255), (236, 72, 153), (56, 189, 248), (167, 139, 250), (248, 113, 113)]
    labels = [payload.product_name, "商品2.jpg", "商品3.jpg", "商品4.jpg", "商品5.jpg"]
    for idx in range(5):
        x = 275 + idx * 144
        thumb = product_thumb_image(payload, (126, 150), colors[idx], labels[idx])
        bg.alpha_composite(thumb.convert("RGBA"), (x, 735))
        draw.rounded_rectangle((x, 735, x + 126, 930), radius=18, outline=(123, 156, 255), width=2)
        draw.text((x + 12, 898), labels[idx][:8], font=font_tiny, fill=(255, 255, 255))
        draw.ellipse((x + 98, 746, x + 122, 770), fill=(139, 92, 246))
        draw_center_text(draw, (x + 110, 746), "✓", font_tiny, (255, 255, 255))

    draw.rounded_rectangle((385, 1032, 695, 1105), radius=36, fill=(89, 35, 210), outline=(126, 246, 195), width=3)
    draw_center_text(draw, (540, 1050), "AI 智能生成中...", font_title, (255, 255, 255), 1, (40, 10, 100))

    draw_neon_card(draw, (38, 1142, 1042, 1740), (190, 80, 255), (16, 20, 63))
    draw.text((76, 1184), "生成多套投放图片", font=font_title, fill=(255, 255, 255))
    rows = [
        ("主图", "吸引点击", ["科技风", "极简风", "炫彩风", "3D渲染风"]),
        ("场景图", "增强代入感", ["办公场景", "生活场景", "直播场景", "学习场景"]),
        ("卖点海报", "突出卖点", points[:4] or ["核心卖点"]),
        ("活动图", "促销转化", ["限时秒杀", "618大促", "直播专享", "品牌特卖"]),
    ]
    y = 1262
    for row_idx, (row_name, row_desc, row_cards) in enumerate(rows):
        draw.rounded_rectangle((75, y, 190, y + 108), radius=18, fill=(35, 28, 92), outline=(109, 90, 255), width=2)
        draw_center_text(draw, (132, y + 24), row_name, font_small, (255, 255, 255))
        draw_center_text(draw, (132, y + 65), row_desc, font_tiny, (184, 197, 255))
        for idx, card_name in enumerate(row_cards[:5]):
            x = 215 + idx * 154
            card = product_thumb_image(payload, (132, 108), colors[(row_idx + idx) % len(colors)], card_name)
            bg.alpha_composite(card.convert("RGBA"), (x, y))
            draw.rounded_rectangle((x, y, x + 132, y + 108), radius=18, outline=(99, 179, 255), width=2)
            draw.rectangle((x, y + 72, x + 132, y + 108), fill=(10, 15, 45))
            draw_center_text(draw, (x + 66, y + 80), card_name[:7], font_tiny, (255, 255, 255))
        draw.rounded_rectangle((985 - 84, y, 985, y + 108), radius=18, fill=(22, 26, 74), outline=(114, 112, 255), width=2)
        draw_center_text(draw, (943, y + 25), "+", find_chinese_font(32), (220, 230, 255))
        draw_center_text(draw, (943, y + 72), "更多", font_tiny, (210, 220, 255))
        y += 126

    draw.rounded_rectangle((118, 1804, 962, 1888), radius=42, fill=(12, 18, 58), outline=(154, 132, 255), width=2)
    platforms = [("淘宝", (255, 107, 0)), ("拼多多", (235, 35, 46)), ("抖音小店", (15, 23, 42)), ("闲鱼", (250, 204, 21))]
    draw.text((170, 1830), "适合", font=font_title, fill=(255, 255, 255))
    x = 300
    for name, color in platforms:
        draw.rounded_rectangle((x, 1820, x + 92, 1878), radius=18, fill=color)
        draw_center_text(draw, (x + 46, 1832), name[:3], font_small, (255, 255, 255))
        x += 150

    output = BytesIO()
    bg.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


def product_photo_block(data_url: str | None, x: int, y: int, w: int, h: int) -> str:
    if data_url and data_url.startswith("data:image/"):
        return (
            f'<image href="{html.escape(data_url, quote=True)}" x="{x}" y="{y}" width="{w}" height="{h}" '
            'preserveAspectRatio="xMidYMid slice" clip-path="url(#photoClip)" />'
        )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="52" fill="url(#productGrad)" opacity="0.98"/>'
        f'<circle cx="{x + w * 0.52:.0f}" cy="{y + h * 0.34:.0f}" r="145" fill="#e0f2fe" opacity="0.45"/>'
        f'<circle cx="{x + w * 0.64:.0f}" cy="{y + h * 0.48:.0f}" r="86" fill="#a5f3fc" opacity="0.38"/>'
        f'<ellipse cx="{x + w * 0.5:.0f}" cy="{y + h * 0.82:.0f}" rx="180" ry="38" fill="#020617" opacity="0.28"/>'
        f'<rect x="{x + w * 0.39:.0f}" y="{y + h * 0.2:.0f}" width="142" height="330" rx="42" fill="#ffffff" opacity="0.96"/>'
        f'<rect x="{x + w * 0.435:.0f}" y="{y + h * 0.15:.0f}" width="82" height="72" rx="22" fill="#dbeafe"/>'
        f'<rect x="{x + w * 0.43:.0f}" y="{y + h * 0.42:.0f}" width="90" height="96" rx="18" fill="#bfdbfe" opacity="0.78"/>'
    )


def svg_text_lines(text: str, x: int, y: int, size: int, width: int, line_height: int, fill: str = "#fff", weight: int = 800) -> str:
    escaped = html.escape(text)
    chunks: list[str] = []
    line = ""
    max_chars = max(6, width // max(size, 1))
    for char in escaped:
        line += char
        if len(line) >= max_chars:
            chunks.append(line)
            line = ""
    if line:
        chunks.append(line)
    return "".join(
        f'<text x="{x}" y="{y + idx * line_height}" fill="{fill}" font-size="{size}" '
        f'font-family="Microsoft YaHei, PingFang SC, sans-serif" font-weight="{weight}">{chunk}</text>'
        for idx, chunk in enumerate(chunks[:3])
    )


def build_main_image_svg(payload: ProductMediaPackRequest) -> str:
    points = split_points_text(payload.selling_points)
    safe_name = html.escape(payload.product_name)
    safe_price = html.escape(payload.price)
    point_1 = html.escape(points[0])
    point_2 = html.escape(points[1] if len(points) > 1 else payload.call_to_action)
    point_3 = html.escape(points[2] if len(points) > 2 else payload.audience)
    photo = product_photo_block(payload.product_image_data_url, 250, 510, 580, 580)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#020617"/><stop offset="0.43" stop-color="#0f1c4f"/><stop offset="1" stop-color="#4c0d6e"/></linearGradient>
  <linearGradient id="band" x1="0" x2="1"><stop offset="0" stop-color="#7c3aed"/><stop offset="0.55" stop-color="#2563eb"/><stop offset="1" stop-color="#06b6d4"/></linearGradient>
  <linearGradient id="productGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e0f2fe"/><stop offset="0.48" stop-color="#7dd3fc"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>
  <filter id="glow"><feGaussianBlur stdDeviation="9" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="shadow"><feDropShadow dx="0" dy="28" stdDeviation="24" flood-color="#000" flood-opacity="0.42"/></filter>
  <clipPath id="photoClip"><rect x="250" y="510" width="580" height="580" rx="52"/></clipPath>
</defs>
<rect width="1080" height="1920" fill="url(#bg)"/>
<circle cx="210" cy="260" r="240" fill="#2563eb" opacity="0.18"/>
<circle cx="900" cy="560" r="300" fill="#ec4899" opacity="0.16"/>
<path d="M70 410 C310 150 790 150 1010 390" fill="none" stroke="#a78bfa" stroke-width="5" opacity="0.82"/>
<path d="M110 1485 C330 1280 742 1286 985 1480" fill="none" stroke="#38bdf8" stroke-width="7" opacity="0.52"/>
<rect x="120" y="70" width="840" height="76" rx="38" fill="#07101f" stroke="#bfdbfe" stroke-width="2" opacity="0.88"/>
<text x="540" y="119" fill="#fff" font-size="34" font-family="Microsoft YaHei, sans-serif" text-anchor="middle" font-weight="800">AI电商 · 主图 / 详情图 / 短视频 · 一键交付</text>
<text x="94" y="270" fill="#fff" font-size="88" font-family="Microsoft YaHei, sans-serif" font-weight="950" filter="url(#glow)">爆款商品图</text>
<text x="94" y="365" fill="#dbeafe" font-size="72" font-family="Microsoft YaHei, sans-serif" font-weight="950">自动生成</text>
<rect x="94" y="410" width="430" height="62" rx="31" fill="url(#band)"/>
<text x="310" y="452" fill="#fff" font-size="30" font-family="Microsoft YaHei, sans-serif" text-anchor="middle" font-weight="900">{point_1}</text>
<g filter="url(#shadow)">{photo}</g>
<g transform="translate(120 1082)">
  <rect width="840" height="224" rx="34" fill="#071226" stroke="#60a5fa" opacity="0.94"/>
  <text x="44" y="64" fill="#93c5fd" font-size="28" font-family="Microsoft YaHei, sans-serif" font-weight="800">商品卖点卡</text>
  <text x="44" y="124" fill="#fff" font-size="44" font-family="Microsoft YaHei, sans-serif" font-weight="950">{safe_name}</text>
  <text x="44" y="178" fill="#bfdbfe" font-size="30" font-family="Microsoft YaHei, sans-serif">{point_1} · {point_2}</text>
  <text x="794" y="160" fill="#fef08a" font-size="62" font-family="Microsoft YaHei, sans-serif" text-anchor="end" font-weight="950">¥{safe_price}</text>
</g>
<g transform="translate(120 1352)">
  <rect width="250" height="150" rx="28" fill="#111827" stroke="#8b5cf6"/>
  <text x="125" y="62" fill="#fff" font-size="30" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-weight="900">主图</text>
  <text x="125" y="108" fill="#a5b4fc" font-size="22" text-anchor="middle" font-family="Microsoft YaHei, sans-serif">点击率包装</text>
  <rect x="294" width="250" height="150" rx="28" fill="#111827" stroke="#06b6d4"/>
  <text x="419" y="62" fill="#fff" font-size="30" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-weight="900">详情</text>
  <text x="419" y="108" fill="#67e8f9" font-size="22" text-anchor="middle" font-family="Microsoft YaHei, sans-serif">卖点证明</text>
  <rect x="588" width="250" height="150" rx="28" fill="#111827" stroke="#f472b6"/>
  <text x="713" y="62" fill="#fff" font-size="30" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-weight="900">短视频</text>
  <text x="713" y="108" fill="#f9a8d4" font-size="22" text-anchor="middle" font-family="Microsoft YaHei, sans-serif">脚本封面</text>
</g>
<g transform="translate(120 1572)">
  <rect width="840" height="210" rx="34" fill="#0b1220" stroke="#334155"/>
  <text x="42" y="58" fill="#fff" font-size="38" font-family="Microsoft YaHei, sans-serif" font-weight="950">适合人群：{html.escape(payload.audience)}</text>
  <text x="42" y="116" fill="#bfdbfe" font-size="28" font-family="Microsoft YaHei, sans-serif">卖点补充：{point_3}</text>
  <text x="42" y="170" fill="#fef08a" font-size="30" font-family="Microsoft YaHei, sans-serif" font-weight="900">{html.escape(payload.call_to_action)}</text>
</g>
</svg>"""


def build_detail_image_svg(payload: ProductMediaPackRequest) -> str:
    points = split_points_text(payload.selling_points)
    rows = "".join(
        f'<g transform="translate(92 {470 + idx * 190})"><rect width="896" height="150" rx="30" fill="#0f172a" stroke="#334155"/>'
        f'<circle cx="74" cy="75" r="42" fill="url(#badge{idx % 3})"/>'
        f'<text x="74" y="86" fill="#020617" font-size="30" font-family="Microsoft YaHei, sans-serif" text-anchor="middle" font-weight="950">{idx + 1}</text>'
        f'<text x="145" y="62" fill="#7dd3fc" font-size="26" font-family="Microsoft YaHei, sans-serif" font-weight="800">核心卖点</text>'
        f'{svg_text_lines(point, 145, 108, 34, 700, 42, "#fff", 900)}</g>'
        for idx, point in enumerate(points[:5])
    )
    safe_name = html.escape(payload.product_name)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#07111f"/><stop offset="0.56" stop-color="#172554"/><stop offset="1" stop-color="#3b0764"/></linearGradient>
  <linearGradient id="badge0" x1="0" x2="1"><stop offset="0" stop-color="#86f3c7"/><stop offset="1" stop-color="#67e8f9"/></linearGradient>
  <linearGradient id="badge1" x1="0" x2="1"><stop offset="0" stop-color="#fef08a"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
  <linearGradient id="badge2" x1="0" x2="1"><stop offset="0" stop-color="#a78bfa"/><stop offset="1" stop-color="#60a5fa"/></linearGradient>
  <filter id="shadow"><feDropShadow dx="0" dy="22" stdDeviation="18" flood-color="#000" flood-opacity="0.34"/></filter>
</defs>
<rect width="1080" height="1920" fill="url(#bg)"/>
<circle cx="110" cy="130" r="190" fill="#2563eb" opacity="0.18"/>
<circle cx="940" cy="320" r="260" fill="#ec4899" opacity="0.14"/>
<rect x="82" y="80" width="916" height="300" rx="42" fill="#020617" opacity="0.64" stroke="#334155" filter="url(#shadow)"/>
<text x="122" y="152" fill="#93c5fd" font-size="32" font-family="Microsoft YaHei, sans-serif" font-weight="900">DETAIL PAGE / 商品详情长图</text>
<text x="122" y="248" fill="#fff" font-size="74" font-family="Microsoft YaHei, sans-serif" font-weight="950">{safe_name}</text>
<text x="122" y="316" fill="#dbeafe" font-size="31" font-family="Microsoft YaHei, sans-serif">{html.escape(payload.category)} · {html.escape(payload.audience)} · ¥{html.escape(payload.price)}</text>
{rows}
<g transform="translate(92 1478)">
  <rect width="896" height="280" rx="38" fill="#172554" stroke="#60a5fa"/>
  <text x="44" y="72" fill="#fff" font-size="42" font-family="Microsoft YaHei, sans-serif" font-weight="950">发布前确认</text>
  <text x="44" y="132" fill="#bfdbfe" font-size="29" font-family="Microsoft YaHei, sans-serif">价格、库存、发货、售后由商家最终确认</text>
  <text x="44" y="190" fill="#bfdbfe" font-size="29" font-family="Microsoft YaHei, sans-serif">不自动发布商品，只生成平台草稿资料</text>
  <text x="44" y="248" fill="#fef08a" font-size="32" font-family="Microsoft YaHei, sans-serif" font-weight="900">{html.escape(payload.call_to_action)}</text>
</g>
</svg>"""


def build_scene_image_svg(payload: ProductMediaPackRequest) -> str:
    points = split_points_text(payload.selling_points)
    primary = html.escape(points[0])
    secondary = html.escape(points[1] if len(points) > 1 else payload.audience)
    photo = product_photo_block(payload.product_image_data_url, 128, 390, 824, 620)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#04111d"/><stop offset="0.5" stop-color="#0f766e"/><stop offset="1" stop-color="#172554"/></linearGradient>
  <linearGradient id="productGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ecfeff"/><stop offset="0.54" stop-color="#67e8f9"/><stop offset="1" stop-color="#60a5fa"/></linearGradient>
  <clipPath id="photoClip"><rect x="128" y="390" width="824" height="620" rx="58"/></clipPath>
  <filter id="shadow"><feDropShadow dx="0" dy="28" stdDeviation="24" flood-color="#000" flood-opacity="0.36"/></filter>
</defs>
<rect width="1080" height="1920" fill="url(#bg)"/>
<circle cx="170" cy="260" r="210" fill="#ccfbf1" opacity="0.14"/>
<circle cx="890" cy="1120" r="310" fill="#93c5fd" opacity="0.16"/>
<text x="90" y="145" fill="#ccfbf1" font-size="34" font-family="Microsoft YaHei, sans-serif" font-weight="900">SCENE SELLING CARD</text>
<text x="90" y="260" fill="#fff" font-size="82" font-family="Microsoft YaHei, sans-serif" font-weight="950">{html.escape(payload.product_name)}</text>
<text x="90" y="332" fill="#d1fae5" font-size="34" font-family="Microsoft YaHei, sans-serif">{primary} · {secondary}</text>
<g filter="url(#shadow)">{photo}</g>
<g transform="translate(90 1085)">
  <rect width="900" height="292" rx="42" fill="#031018" opacity="0.76" stroke="#5eead4"/>
  <text x="52" y="78" fill="#5eead4" font-size="30" font-family="Microsoft YaHei, sans-serif" font-weight="900">为什么要买</text>
  <text x="52" y="148" fill="#fff" font-size="48" font-family="Microsoft YaHei, sans-serif" font-weight="950">{primary}</text>
  <text x="52" y="214" fill="#ccfbf1" font-size="32" font-family="Microsoft YaHei, sans-serif">{html.escape(payload.audience)} 更容易理解的场景化卖点</text>
</g>
<g transform="translate(90 1435)">
  <rect width="420" height="150" rx="30" fill="#022c22" stroke="#34d399"/>
  <text x="40" y="62" fill="#fff" font-size="34" font-family="Microsoft YaHei, sans-serif" font-weight="900">使用场景</text>
  <text x="40" y="112" fill="#a7f3d0" font-size="26" font-family="Microsoft YaHei, sans-serif">{html.escape(payload.category)}</text>
  <rect x="480" width="420" height="150" rx="30" fill="#0f172a" stroke="#60a5fa"/>
  <text x="520" y="62" fill="#fff" font-size="34" font-family="Microsoft YaHei, sans-serif" font-weight="900">转化动作</text>
  <text x="520" y="112" fill="#bfdbfe" font-size="26" font-family="Microsoft YaHei, sans-serif">{html.escape(payload.call_to_action)}</text>
</g>
</svg>"""


def product_media_brief(payload: ProductMediaPackRequest) -> MerchantBrief:
    return MerchantBrief(
        industry=payload.category,
        product_name=payload.product_name,
        selling_points=payload.selling_points,
        platform=payload.platform,
        video_type="ecommerce",
        segment="ecommerce_seller",
        generation_kind="product_image",
        style=payload.visual_style,
        audience=payload.audience,
        call_to_action=payload.call_to_action,
    )


def product_image_prompt(payload: ProductMediaPackRequest, image_kind: Literal["main_image", "scene_image", "detail_image"]) -> str:
    points = "、".join(split_points_text(payload.selling_points)[:5])
    base = (
        f"产品：{payload.product_name}；类目：{payload.category}；价格：{payload.price}；"
        f"卖点：{points}；目标人群：{payload.audience}；视觉风格：{payload.visual_style}。"
    )
    if image_kind == "main_image":
        return (
            "生成一张商业级中国电商商品主图，9:16竖版海报，真实商品广告质感，主体清晰居中，"
            "包含价格标签、核心卖点、平台安全边距、强转化按钮感；不要乱码，不要小字堆叠，不要廉价PPT风。"
            + base
        )
    if image_kind == "detail_image":
        return (
            "生成一张商业级商品详情页长图首屏，9:16竖版，包含产品特写、3个卖点模块、适用人群、发布前信任背书，"
            "版式高级、留白清楚、手机端可读；不要医疗夸大承诺，不要乱码。"
            + base
        )
    return (
        "生成一张商品场景卖点图，9:16竖版，产品在真实使用场景里出现，生活感和广告质感兼具，"
        "突出购买理由、适用人群和转化动作；不要杂乱文字，不要低清。"
        + base
    )


def try_product_image_api(payload: ProductMediaPackRequest, image_kind: Literal["main_image", "scene_image", "detail_image"]) -> str | None:
    if os.getenv("PRODUCT_MEDIA_USE_IMAGE_API", "1").lower() in {"0", "false", "no"}:
        return None
    _, api_key, _, _ = image_provider_config()
    if not api_key:
        return None
    try:
        result = call_openai_compatible_image(
            ImageGenerationRequest(
                brief=product_media_brief(payload),
                image_kind=image_kind,
                prompt=product_image_prompt(payload, image_kind),
            )
        )
        if result.mode == "image":
            return result.artifact_url or result.image_url
    except Exception:
        return None
    return None


def build_video_preview_html(payload: ProductMediaPackRequest, main_url: str, detail_url: str) -> str:
    name = html.escape(payload.product_name)
    return f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{name} 商品短视频预览</title>
<style>
body{{margin:0;background:#050816;color:white;font-family:Microsoft YaHei,Arial,sans-serif;display:grid;place-items:center;min-height:100vh}}
.phone{{width:360px;height:640px;border-radius:28px;overflow:hidden;background:#08111f;box-shadow:0 0 60px #2563eb;position:relative}}
.scene{{position:absolute;inset:0;display:grid;place-items:center;animation:fade 9s infinite;opacity:0}}
.scene:nth-child(1){{animation-delay:0s}}.scene:nth-child(2){{animation-delay:3s}}.scene:nth-child(3){{animation-delay:6s}}
img{{width:100%;height:100%;object-fit:cover}}.text{{position:absolute;left:24px;right:24px;bottom:36px;background:rgba(0,0,0,.55);padding:18px;border-radius:18px;font-size:24px;font-weight:900}}
@keyframes fade{{0%,30%{{opacity:1;transform:scale(1)}}33%,100%{{opacity:0;transform:scale(1.04)}}}}
</style><div class="phone">
<div class="scene"><img src="{main_url}"><div class="text">{name} 主图自动生成</div></div>
<div class="scene"><img src="{detail_url}"><div class="text">详情图卖点自动排版</div></div>
<div class="scene"><img src="{main_url}"><div class="text">上架草稿人工确认发布</div></div>
</div></html>"""


def find_ffmpeg_binary() -> str | None:
    candidates = [
        os.getenv("FFMPEG_BINARY"),
        shutil.which("ffmpeg"),
        r"C:\Users\Administrator\rent-car-hyperframes\tools\ffmpeg\ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def render_product_mp4(pack_id: str, payload: ProductMediaPackRequest) -> tuple[str | None, str]:
    ffmpeg = find_ffmpeg_binary()
    if ffmpeg:
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore

            frame_dir = ARTIFACT_DIR / "product_media" / f"{pack_id}_frames"
            frame_dir.mkdir(parents=True, exist_ok=True)
            output_name = f"product_media/{pack_id}_video.mp4"
            output_path = ARTIFACT_DIR / output_name
            width, height, fps, seconds = 720, 1280, 15, 6
            font_big = find_chinese_font(54)
            font_mid = find_chinese_font(34)
            points = split_points_text(payload.selling_points)
            scenes = [
                (payload.product_name, points[0], (17, 24, 75)),
                ("详情图自动排版", " / ".join(points[:3]), (12, 54, 92)),
                ("保存上架草稿", payload.call_to_action, (68, 22, 112)),
            ]
            for frame_idx in range(fps * seconds):
                scene = scenes[min(len(scenes) - 1, frame_idx // (fps * 2))]
                progress = (frame_idx % (fps * 2)) / (fps * 2)
                offset = int(36 * (1 - progress))
                img = Image.new("RGB", (width, height), scene[2])
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle((70, 170 + offset, 650, 720 + offset), radius=42, fill=(220, 238, 255), outline=(96, 165, 250), width=6)
                draw.ellipse((250, 300 + offset, 470, 520 + offset), fill=(125, 211, 252))
                draw.rounded_rectangle((280, 360 + offset, 440, 640 + offset), radius=36, fill=(255, 255, 255))
                draw.rounded_rectangle((56, 790, 664, 1040), radius=34, fill=(8, 18, 38))
                draw.text((86, 830), scene[0], fill=(255, 255, 255), font=font_big)
                draw.text((86, 920), scene[1], fill=(191, 219, 254), font=font_mid)
                draw.text((86, 995), f"¥{payload.price}", fill=(254, 240, 138), font=font_mid)
                draw.text((86, 1136), "AI生成主图 / 详情图 / 上架草稿", fill=(147, 197, 253), font=font_mid)
                img.save(frame_dir / f"frame_{frame_idx:03d}.png")
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-framerate",
                    str(fps),
                    "-i",
                    str(frame_dir / "frame_%03d.png"),
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if output_path.exists() and output_path.stat().st_size > 1024:
                shutil.rmtree(frame_dir, ignore_errors=True)
                return f"/artifacts/{output_name}", "rendered"
        except Exception:
            pass

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None, "needs_ffmpeg"

    output_name = f"product_media/{pack_id}_video.mp4"
    output_path = ARTIFACT_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps, seconds = 720, 1280, 15, 6
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        return None, "needs_ffmpeg"
    font_big = find_chinese_font(54)
    font_mid = find_chinese_font(34)
    points = split_points_text(payload.selling_points)
    scenes = [
        (payload.product_name, points[0], (17, 24, 75)),
        ("详情图自动排版", " / ".join(points[:3]), (12, 54, 92)),
        ("保存上架草稿", payload.call_to_action, (68, 22, 112)),
    ]
    for frame_idx in range(fps * seconds):
        scene = scenes[min(len(scenes) - 1, frame_idx // (fps * 2))]
        img = Image.new("RGB", (width, height), scene[2])
        draw = ImageDraw.Draw(img)
        progress = (frame_idx % (fps * 2)) / (fps * 2)
        offset = int(30 * (1 - progress))
        draw.rounded_rectangle((70, 170 + offset, 650, 720 + offset), radius=42, fill=(220, 238, 255), outline=(96, 165, 250), width=6)
        draw.ellipse((250, 300 + offset, 470, 520 + offset), fill=(125, 211, 252))
        draw.rounded_rectangle((280, 360 + offset, 440, 640 + offset), radius=36, fill=(255, 255, 255))
        draw.rounded_rectangle((56, 790, 664, 1040), radius=34, fill=(8, 18, 38))
        draw.text((86, 830), scene[0], fill=(255, 255, 255), font=font_big)
        draw.text((86, 920), scene[1], fill=(191, 219, 254), font=font_mid)
        draw.text((86, 995), f"¥{payload.price}", fill=(254, 240, 138), font=font_mid)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        writer.write(frame)
    writer.release()
    return f"/artifacts/{output_name}", "rendered"


@app.post("/api/product-media/pack", response_model=ProductMediaPackResponse)
async def product_media_pack(payload: ProductMediaPackRequest) -> ProductMediaPackResponse:
    pack_id = str(uuid.uuid4())
    main_name = f"product_media/{pack_id}_main.png"
    detail_name = f"product_media/{pack_id}_detail.png"
    scene_name = f"product_media/{pack_id}_scene.png"
    main_url = await asyncio.to_thread(try_product_image_api, payload, "main_image")
    if not main_url:
        main_url = write_artifact(main_name, render_boom_materials_png(payload, "main"), binary=True)
    detail_url = await asyncio.to_thread(try_product_image_api, payload, "detail_image")
    if not detail_url:
        detail_url = write_artifact(detail_name, render_boom_materials_png(payload, "detail"), binary=True)
    scene_url = await asyncio.to_thread(try_product_image_api, payload, "scene_image")
    if not scene_url:
        scene_url = write_artifact(scene_name, render_boom_materials_png(payload, "scene"), binary=True)
    preview_url = write_artifact(f"product_media/{pack_id}_video_preview.html", build_video_preview_html(payload, main_url, detail_url))
    video_url, video_status_raw = await asyncio.to_thread(render_product_mp4, pack_id, payload)
    video_status: Literal["rendered", "needs_ffmpeg", "failed"] = "rendered" if video_status_raw == "rendered" else "needs_ffmpeg"
    listing = build_ecommerce_listing_draft(
        EcommerceListingDraftRequest(
            product_name=payload.product_name,
            category=payload.category,
            platform=payload.platform,
            price=payload.price,
            selling_points=payload.selling_points,
            audience=payload.audience,
            visual_style=payload.visual_style,
        )
    )
    scenes = [
        {"title": "商品主图", "visual": "点击率包装：主体、价格、核心卖点和转化按钮", "asset_url": main_url},
        {"title": "详情图", "visual": "详情页首屏：卖点拆解、适用人群、发布前确认", "asset_url": detail_url},
        {"title": "场景卖点图", "visual": "真实使用场景：购买理由、适用人群和转化动作", "asset_url": scene_url},
        {"title": "商品短视频", "visual": "主图 -> 详情卖点 -> 上架草稿三段式", "asset_url": video_url or preview_url},
    ]
    return ProductMediaPackResponse(
        pack_id=pack_id,
        product_name=payload.product_name,
        main_image_url=main_url,
        detail_image_url=detail_url,
        video_preview_url=preview_url,
        video_url=video_url,
        video_status=video_status,
        listing_draft=listing,
        scenes=scenes,
        test_checklist=[
            "主图可打开且有商品名、价格、卖点和转化按钮。",
            "详情图可打开且有卖点结构和人工确认提示。",
            "场景卖点图可打开且有购买理由和适用人群。",
            "视频预览 HTML 可打开；有视频运行时则生成 MP4。",
            "上架草稿 publish_boundary 必须是 save_draft_only。",
        ],
        next_action="若已配置可用图片生成 API 会优先真实出图；API 不可用时使用高级 PNG 海报引擎直接生成。最终发布仍需商家确认价格、库存、资质和售后。",
    )


@app.post("/api/ecommerce/managed-ops-plan", response_model=ManagedOpsPlanResponse)
async def managed_ops_plan(payload: ManagedOpsPlanRequest) -> ManagedOpsPlanResponse:
    points = split_points_text(payload.selling_points)
    primary = points[0]
    platform_name = {
        "douyin": "抖音小店",
        "taobao": "淘宝",
        "pdd": "拼多多",
        "xianyu": "闲鱼",
        "xiaohongshu": "小红书店铺",
    }[payload.platform]
    plan_id = str(uuid.uuid4())
    product_name = payload.product_name.strip()
    offer_name = {
        "starter": "AI 商品上架启动包",
        "growth": "AI 店铺运营增长包",
        "managed": "AI 店铺运营托管包",
    }[payload.service_level]
    publishing_queue = [
        {
            "status": "draft_ready",
            "item": f"{product_name} 标题/短标题/卖点",
            "next_operator_action": "复制到平台草稿并检查类目、品牌、规格。",
        },
        {
            "status": "asset_ready",
            "item": f"{product_name} 主图、详情图、短视频预览",
            "next_operator_action": "人工确认不侵权、不虚假宣传，再上传到素材中心。",
        },
        {
            "status": "service_ready",
            "item": f"{product_name} 客服 FAQ 和异议处理",
            "next_operator_action": "导入知识库，先用草稿模式辅助回复。",
        },
    ]
    launch_tasks = [
        ManagedOpsTask(day="D1", owner="merchant", task="提交商品资料、授权边界、价格库存发货规则", output="商品档案和风险信息", confirmation_required=True),
        ManagedOpsTask(day="D1", owner="ai", task="生成标题、卖点、详情结构、主图/详情图/短视频草稿", output="上架素材包", confirmation_required=False),
        ManagedOpsTask(day="D2", owner="operator", task=f"创建{platform_name}商品草稿并做平台字段校验", output="平台草稿链接或截图", confirmation_required=True),
        ManagedOpsTask(day="D3", owner="operator", task="导入客服 FAQ，设置常见问题回复和人工接管词", output="客服承接 SOP", confirmation_required=True),
        ManagedOpsTask(day="D4-D7", owner="ai", task="根据曝光、点击、咨询和转化生成复盘建议", output="优化清单和下一批商品建议", confirmation_required=False),
    ]
    response = ManagedOpsPlanResponse(
        plan_id=plan_id,
        product_name=product_name,
        platform=platform_name,
        positioning=f"面向{payload.audience}，主打“{primary}”的{payload.category}上架和客服承接方案。",
        sellable_offer=f"{offer_name}：商家给商品资料，系统生成上架素材、平台草稿、客服话术和7天复盘计划，人工确认后发布。",
        price_packages=[
            {"name": "启动包", "price": "299-599/批", "scope": "10个商品上架素材、标题卖点、客服 FAQ，不含持续运营。"},
            {"name": "增长包", "price": "999-1999/月", "scope": "每周素材更新、客服话术优化、线索复盘、低效商品优化建议。"},
            {"name": "托管包", "price": "3000+/月", "scope": "商品上新计划、素材制作、客服承接、周报复盘，发布/改价/退款仍需商家确认。"},
        ],
        launch_tasks=launch_tasks,
        publishing_queue=publishing_queue,
        customer_service_flow=[
            "客户咨询先由 AI 判断意向、预算、疑虑和是否需要人工接管。",
            "常规问题生成候选回复，客服人工确认后发送。",
            "高意向客户进入线索表，2小时、24小时、3天分层跟进。",
            "投诉、退款、账号、承诺、医疗功效、隐私数据问题直接转人工。",
        ],
        risk_boundaries=[
            "系统只创建草稿和候选回复，不绕过平台规则自动发布、改价、退款或发货。",
            "商品图片、品牌、功效、资质、价格、库存、发货承诺必须由商家最终确认。",
            "禁止盗图铺货、虚假评价、刷单、无授权私信骚扰和抓取个人联系方式。",
            "涉及食品、化妆品、医疗、金融等敏感类目时，先补齐资质再发布。",
        ],
        closing_script=(
            f"老板，您不用先招运营。先给我{product_name}这类商品资料，"
            f"我用 AI 帮您做一批{platform_name}上架素材、客服话术和7天跟进复盘。"
            "发布前您确认价格库存和合规内容，跑通后再按月托管。"
        ),
        next_action="把这份方案连同商品媒体包发给试点商家，先收一单启动包，再按月升级增长包。",
    )
    save_record("managed_ops_plan", plan_id, {"request": payload.model_dump(), "response": response.model_dump()})
    return response


@app.post("/api/ecommerce/daily-report", response_model=EcommerceDailyReportResponse)
async def ecommerce_daily_report() -> EcommerceDailyReportResponse:
    payload = load_commerce_daily_payload(COMMERCE_DAILY_SAMPLE)
    report = build_commerce_daily_report(payload)
    report_date = str(payload.get("date", datetime.now().strftime("%Y-%m-%d")))
    output_path = write_commerce_daily_report(report, ARTIFACT_DIR / "commerce_reports", report_date)
    return EcommerceDailyReportResponse(
        source="sample",
        date=report_date,
        report=report,
        artifact_url=f"/artifacts/commerce_reports/{output_path.name}",
        next_action="本地自动化已跑通。下一步把数据源从 sample JSON 换成 mcp-cn-commerce 的抖店/京东/淘宝 API 只读数据。",
    )


@app.post("/api/ecommerce/customer-service-playbook", response_model=CustomerServicePlaybook)
async def customer_service_playbook(brief: MerchantBrief) -> CustomerServicePlaybook:
    points = split_selling_points(brief)
    primary = points[0] if points else "核心卖点"
    secondary = points[1] if len(points) > 1 else "使用效果"
    return CustomerServicePlaybook(
        welcome=f"您好，我看到您在了解{brief.product_name}，我可以直接帮您判断是否适合。",
        qualification_questions=[
            f"您主要是想解决{primary}，还是更关注价格/发货/到店体验？",
            f"您准备自己用、送人，还是给店铺/团队批量采购？",
            "您希望今天下单/预约，还是先看一个更详细的案例？",
        ],
        objections=[
            f"如果客户担心效果：先强调{brief.product_name}的{primary}，再给使用场景和真实反馈。",
            f"如果客户嫌贵：把价格拆成一次使用成本，并强调{secondary}和售后保障。",
            "如果客户犹豫：给限时优惠、库存/档期提醒，但不要制造虚假稀缺。",
        ],
        closing=f"如果合适，我现在可以帮您走{brief.call_to_action}，也可以先发一份使用/到店说明给您。",
        follow_up="未成交客户 2 小时后发案例，24 小时后发优惠提醒，3 天后进入复购/二次触达列表。",
    )


@app.post("/api/workflow/script-customer-service", response_model=ScriptCustomerServiceKit)
async def script_customer_service(request: RenderRequest) -> ScriptCustomerServiceKit:
    return build_script_customer_service_kit(request.brief, request.script)


@app.post("/api/images/generate", response_model=ImageGenerationResponse)
async def generate_image(payload: ImageGenerationRequest) -> ImageGenerationResponse:
    prompt = build_image_prompt(payload)
    try:
        return await asyncio.to_thread(call_openai_compatible_image, payload)
    except urllib.error.HTTPError as exc:
        provider, _, model, _ = image_provider_config()
        try:
            error_detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            error_detail = str(exc)
        return ImageGenerationResponse(
            mode="prompt",
            provider=provider,
            model=model,
            prompt=prompt,
            error=error_detail[:600],
            next_action="图片接口返回错误，已保留 prompt；通常需要检查账户余额、模型参数、尺寸或 key 权限。",
        )
    except Exception as exc:
        provider, _, model, _ = image_provider_config()
        return ImageGenerationResponse(
            mode="prompt",
            provider=provider,
            model=model,
            prompt=prompt,
            error=str(exc),
            next_action="图片接口调用失败，已保留 prompt；检查 IMAGE_BASE_URL、IMAGE_MODEL、IMAGE_API_KEY 后重试。",
        )


@app.post("/api/reply-assistant", response_model=ReplyAssistantResponse)
async def reply_assistant(payload: ReplyAssistantRequest) -> ReplyAssistantResponse:
    return await resolve_reply_assistant_response(payload)


@app.post("/api/customer-service/chat-reply-agent", response_model=ChatReplyAgentResponse)
async def chat_reply_agent(payload: ChatReplyAgentRequest) -> ChatReplyAgentResponse:
    messages = parse_chat_messages(payload.ocr_text)
    pending_messages = get_pending_customer_messages(messages)
    context = classify_conversation_context(payload, messages)
    should_reply = bool(pending_messages) and context.reply_mode in {"auto", "draft_only"}
    conversation_for_ai = "\n".join(f"{message.speaker}: {message.text}" for message in messages)
    if pending_messages:
        conversation_for_ai = f"{conversation_for_ai}\n待回复客户消息：{' / '.join(pending_messages)}"
    conversation_for_ai = (
        f"会话类型：{context.conversation_type}\n"
        f"处理模式：{context.reply_mode}\n"
        f"判断原因：{context.reason}\n"
        f"{conversation_for_ai or payload.ocr_text}"
    )

    analysis = await resolve_reply_assistant_response(
        ReplyAssistantRequest(
            channel=payload.channel,
            scenario="桌面客服自动回复",
            conversation=conversation_for_ai or payload.ocr_text,
            goal=payload.reply_goal,
            tone="high_eq",
            recipient_profile=payload.merchant_profile,
        )
    )
    should_handoff = analysis.service_insight.should_handoff or context.reply_mode == "handoff" or not should_reply
    automation_mode: Literal["copy_only", "api_ready", "blocked"] = "copy_only"
    next_actions = [
        "把当前聊天截图或复制文本传入 ocr_text。",
        "系统只生成候选回复，发送前必须人工确认。",
        "接企业微信/微信客服/抖音私信/淘宝/拼多多/闲鱼官方 API 后，才能从 copy_only 升级为 api_ready。",
    ]
    if payload.auto_send:
        automation_mode = "blocked"
        next_actions.insert(1, "当前没有已授权的官方发送 API，不能直接自动发消息，避免误发和封号。")
    if context.reply_mode == "ignore":
        next_actions.insert(0, context.reason)
    if context.reply_mode == "handoff":
        next_actions.insert(0, context.reason)
    if not should_reply:
        next_actions.insert(0, "没有检测到最后一轮未回复客户消息，建议先不发送。")

    response = ChatReplyAgentResponse(
        conversation_id=str(uuid.uuid4()),
        channel=payload.channel,
        conversation_context=context,
        parsed_messages=messages,
        pending_customer_messages=pending_messages,
        should_reply=should_reply,
        should_handoff=should_handoff,
        automation_mode=automation_mode,
        recommended_reply="" if context.reply_mode == "ignore" else analysis.candidates[0].text,
        reply_analysis=analysis,
        next_actions=next_actions,
    )
    save_record("chat_reply_agent", response.conversation_id, {"request": payload.model_dump(mode="json"), "response": response.model_dump(mode="json")})
    return response


@app.post("/api/hyperframes/render-plan", response_model=HyperFramesRenderPlan)
async def hyperframes_render_plan(request: RenderRequest) -> HyperFramesRenderPlan:
    scenes = []
    cursor = 0.0
    for index, scene in enumerate(request.script.scenes, start=1):
        scenes.append(
            {
                "id": scene.id,
                "start": round(cursor, 2),
                "duration": scene.duration,
                "layout": "vertical-product-card" if request.generation_kind != "customer_service" else "chat-proof-card",
                "headline": scene.caption,
                "visual": scene.visual,
                "caption": request.brief.call_to_action if index == len(request.script.scenes) else scene.title,
                "animation": "gsap.from y=48 opacity=0, then caption bar wipe",
            }
        )
        cursor += scene.duration
    return HyperFramesRenderPlan(
        template="merchant-ecommerce-9x16",
        aspect_ratio="9:16",
        duration_seconds=round(cursor, 2),
        design_tokens={
            "background": "#F5F7F9",
            "ink": "#17202A",
            "accent": "#0F8B8D",
            "cta": "#D8A84F",
            "font": "Microsoft YaHei UI",
        },
        scenes=scenes,
        acceptance_checks=[
            "1080x1920 画面无黑屏",
            "标题、字幕、CTA 不重叠",
            "每个分镜有明确商品/门店/客服视觉",
            "自动发布、改价、退款不在视频生成流程内触发",
            "导出的 JSON 可交给 HyperFrames HTML 模板渲染",
        ],
    )


@app.get("/api/gtm/content-calendar", response_model=list[ContentIdea])
async def content_calendar() -> list[ContentIdea]:
    return [
        ContentIdea(day=1, title="我用 AI 给奶茶店 30 秒做完短视频方案", format="屏幕录制 + 前后对比", target="local_merchant", metric="私信"),
        ContentIdea(day=2, title="老板发一句需求，自动出抖音分镜", format="需求输入到画布演示", target="local_merchant", metric="主页访问"),
        ContentIdea(day=3, title="电商主图、详情图、短视频一套生成", format="三联屏演示", target="ecommerce_seller", metric="试用注册"),
        ContentIdea(day=4, title="开源一个商家 AI 营销画布", format="GitHub 项目介绍", target="agency_developer", metric="Star 和部署咨询"),
        ContentIdea(day=5, title="客服话术从素材和卖点自动生成", format="私信成交场景", target="ecommerce_seller", metric="表单线索"),
    ]


@app.post("/api/render", response_model=RenderTask)
async def create_render(request: RenderRequest) -> RenderTask:
    task_id = str(uuid.uuid4())
    timestamp = now_iso()
    task = RenderTask(
        id=task_id,
        generation_kind=request.generation_kind,
        status="queued",
        progress=0,
        message="已加入生成队列",
        created_at=timestamp,
        updated_at=timestamp,
        cost=round(request.script.estimated_cost * request.variant_count, 2),
    )
    tasks[task_id] = task
    save_record("task", task.id, task)
    asyncio.create_task(run_render(task_id, request))
    return task


@app.get("/api/tasks", response_model=list[RenderTask])
async def list_tasks() -> list[RenderTask]:
    return sorted(tasks.values(), key=lambda item: item.created_at, reverse=True)


@app.get("/api/tasks/{task_id}", response_model=RenderTask)
async def get_task(task_id: str) -> RenderTask:
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


async def run_render(task_id: str, request: RenderRequest) -> None:
    try:
        labels = {
            "short_video": "9:16 短视频画布",
            "product_image": "主图素材包",
            "detail_page": "详情页结构",
            "customer_service": "客服话术库",
        }
        steps = [
            (15, "分析商家需求"),
            (35, "整理脚本和素材结构"),
            (60, f"生成{labels[request.generation_kind]}"),
            (82, "准备下载作品"),
            (100, "生成完成"),
        ]
        for progress, message in steps:
            await asyncio.sleep(0.7)
            task = tasks[task_id]
            tasks[task_id] = task.model_copy(
                update={
                    "status": "running" if progress < 100 else "done",
                    "progress": progress,
                    "message": message,
                    "updated_at": now_iso(),
                }
            )
            save_record("task", task_id, tasks[task_id])

        artifact_name = f"{task_id}.json"
        artifact_path = ARTIFACT_DIR / artifact_name
        artifact_path.write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "brief": request.brief.model_dump(),
                    "script": request.script.model_dump(),
                    "generation_kind": request.generation_kind,
                    "render_adapter": "storyboard-json-placeholder",
                    "next_adapter": "ffmpeg | remotion | hyperframes | image-generation | customer-service-rag",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        task = tasks[task_id]
        tasks[task_id] = task.model_copy(update={"artifact_url": f"/artifacts/{artifact_name}", "updated_at": now_iso()})
        save_record("task", task_id, tasks[task_id])
    except Exception as exc:
        task = tasks[task_id]
        tasks[task_id] = task.model_copy(
            update={"status": "failed", "message": "生成失败", "error": str(exc), "updated_at": now_iso()}
        )
        save_record("task", task_id, tasks[task_id])


DIST_DIR = Path("dist")


def frontend_file_response(path: Path, *, no_cache: bool = False) -> FileResponse:
    headers = {}
    if no_cache:
        headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        headers["Pragma"] = "no-cache"
        headers["Expires"] = "0"
    return FileResponse(path, headers=headers)


@app.api_route("/admin", methods=["GET", "HEAD"])
async def admin_page() -> FileResponse:
    index_file = DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend has not been built. Run npm run build first.")
    return frontend_file_response(index_file, no_cache=True)


@app.api_route("/{path:path}", methods=["GET", "HEAD"])
async def spa_fallback(path: str) -> FileResponse:
    if path.startswith(("api/", "api")):
        raise HTTPException(status_code=405, detail="Method Not Allowed")
    requested = DIST_DIR / path
    if requested.is_file():
        return frontend_file_response(requested)
    if path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Frontend asset not found. Refresh the page to load the latest build.")
    if path.startswith("downloads/"):
        raise HTTPException(status_code=404, detail="Download not found.")
    index_file = DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend has not been built. Run npm run build first.")
    return frontend_file_response(index_file, no_cache=True)
