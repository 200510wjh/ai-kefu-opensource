from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import shutil
import sqlite3
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.customer_service_saas import router as customer_service_saas_router
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
    channel: Literal["wechat", "douyin_dm", "customer_service", "dating"] = "wechat"
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


class ChatReplyAgentRequest(BaseModel):
    channel: Literal["wechat", "douyin_dm", "customer_service"] = "wechat"
    ocr_text: str = Field(min_length=1)
    merchant_profile: str = "商家增长顾问"
    reply_goal: str = "自然回复并推进下一步"
    auto_send: bool = False


class ChatReplyAgentResponse(BaseModel):
    conversation_id: str
    channel: str
    parsed_messages: list[ParsedChatMessage]
    pending_customer_messages: list[str]
    should_reply: bool
    should_handoff: bool
    automation_mode: Literal["copy_only", "api_ready", "blocked"]
    recommended_reply: str
    reply_analysis: ReplyAssistantResponse
    next_actions: list[str]


app = FastAPI(title="Merchant Growth Canvas API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_DIR)), name="artifacts")
app.include_router(customer_service_saas_router)

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
        "douyin_dm": "抖音私信",
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
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AI_MODEL")
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key or not model:
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
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只输出可解析 JSON。你是谨慎、懂成交、懂平台风险的中文客服主管。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.75")),
        "response_format": {"type": "json_object"},
    }
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("AI_TIMEOUT", "35"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    parsed = parse_ai_json(content)

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
    provider = os.getenv("IMAGE_PROVIDER", "openai_compatible")
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

    body: dict[str, Any] = {
        "prompt": prompt,
        "size": os.getenv("IMAGE_SIZE", "1024x1024"),
        "n": 1,
    }
    if model:
        body["model"] = model
    quality = os.getenv("IMAGE_QUALITY")
    if quality:
        body["quality"] = quality
    response_format = os.getenv("IMAGE_RESPONSE_FORMAT")
    if response_format:
        body["response_format"] = response_format

    request = urllib.request.Request(
        f"{base_url}/images/generations",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("IMAGE_TIMEOUT", "80"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    first = (data.get("data") or [{}])[0]
    image_url = first.get("url")
    artifact_url = None
    if first.get("b64_json"):
        artifact_url = save_b64_image(str(first["b64_json"]))
    if not image_url and not artifact_url:
        raise ValueError("Image provider returned no url or b64_json")
    return ImageGenerationResponse(
        mode="image",
        provider=provider,
        model=model,
        prompt=prompt,
        image_url=image_url,
        artifact_url=artifact_url,
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
    api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AI_MODEL")
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not api_key or not model:
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
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只输出可解析 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.85")),
        "response_format": {"type": "json_object"},
    }
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(os.getenv("AI_TIMEOUT", "35"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return validate_ai_scripts(parse_ai_json(content), brief)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "data_dir": str(DATA_DIR), "db_path": str(DB_PATH)}


@app.get("/api/providers", response_model=ProviderStatus)
async def provider_status() -> ProviderStatus:
    return ai_provider_status()


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
    should_reply = bool(pending_messages)
    conversation_for_ai = "\n".join(f"{message.speaker}: {message.text}" for message in messages)
    if pending_messages:
        conversation_for_ai = f"{conversation_for_ai}\n待回复客户消息：{' / '.join(pending_messages)}"

    analysis = await resolve_reply_assistant_response(
        ReplyAssistantRequest(
            channel=payload.channel,
            scenario=f"{payload.merchant_profile}客服自动回复",
            conversation=conversation_for_ai or payload.ocr_text,
            goal=payload.reply_goal,
            tone="high_eq",
            recipient_profile=payload.merchant_profile,
        )
    )
    should_handoff = analysis.service_insight.should_handoff or not should_reply
    automation_mode: Literal["copy_only", "api_ready", "blocked"] = "copy_only"
    next_actions = [
        "把当前聊天截图或复制文本传入 ocr_text。",
        "系统只生成候选回复，发送前必须人工确认。",
        "接企业微信/微信客服/抖音私信官方 API 后，才能从 copy_only 升级为 api_ready。",
    ]
    if payload.auto_send:
        automation_mode = "blocked"
        next_actions.insert(1, "当前没有已授权的官方发送 API，不能直接自动发消息，避免误发和封号。")
    if not should_reply:
        next_actions.insert(0, "没有检测到最后一轮未回复客户消息，建议先不发送。")

    response = ChatReplyAgentResponse(
        conversation_id=str(uuid.uuid4()),
        channel=payload.channel,
        parsed_messages=messages,
        pending_customer_messages=pending_messages,
        should_reply=should_reply,
        should_handoff=should_handoff,
        automation_mode=automation_mode,
        recommended_reply=analysis.candidates[0].text,
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


@app.get("/admin")
async def admin_page() -> FileResponse:
    index_file = DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend has not been built. Run npm run build first.")
    return FileResponse(index_file)


@app.get("/{path:path}")
async def spa_fallback(path: str) -> FileResponse:
    requested = DIST_DIR / path
    if requested.is_file():
        return FileResponse(requested)
    index_file = DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend has not been built. Run npm run build first.")
    return FileResponse(index_file)
