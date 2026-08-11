from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class UserRole(str, Enum):
    owner = "owner"
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str = "demo"


class AuthSession(BaseModel):
    token: str
    user: "User"
    tenant: "Tenant"


class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tenant"))
    slug: str
    name: str
    locale: str = "zh-CN"
    created_at: str = Field(default_factory=now_iso)


class User(BaseModel):
    id: str = Field(default_factory=lambda: new_id("user"))
    tenant_id: str
    email: str
    name: str
    role: UserRole = UserRole.owner
    created_at: str = Field(default_factory=now_iso)


class ProductStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ProductCreate(BaseModel):
    title: str
    category: str = "fashion"
    brand: str | None = None
    description: str = ""
    selling_points: list[str] = Field(default_factory=list)
    target_platforms: list[str] = Field(default_factory=lambda: ["douyin", "taobao"])


class ProductUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    brand: str | None = None
    description: str | None = None
    selling_points: list[str] | None = None
    target_platforms: list[str] | None = None
    hero_asset_id: str | None = None
    status: ProductStatus | None = None


class Product(ProductCreate):
    id: str = Field(default_factory=lambda: new_id("prod"))
    tenant_id: str
    status: ProductStatus = ProductStatus.draft
    hero_asset_id: str | None = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class AssetKind(str, Enum):
    upload = "upload"
    main_image = "main_image"
    detail_page = "detail_page"
    copy = "copy"
    short_video = "short_video"
    export = "export"


class Asset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    tenant_id: str
    product_id: str | None = None
    kind: AssetKind
    name: str
    url: str
    mime_type: str
    size_bytes: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: str = Field(default_factory=now_iso)


class VersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ver"))
    tenant_id: str
    product_id: str
    asset_id: str
    version: int
    change_note: str
    created_at: str = Field(default_factory=now_iso)


class HistoryEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("hist"))
    tenant_id: str
    actor_id: str
    entity_type: Literal["product", "asset", "workflow", "template", "export"]
    entity_id: str
    action: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class GenerationRequest(BaseModel):
    product_id: str
    source_asset_id: str | None = None
    template_id: str | None = None
    platforms: list[str] = Field(default_factory=lambda: ["douyin"])
    locale: str = "zh-CN"


class VideoGenerationRequest(GenerationRequest):
    durations: list[int] = Field(default_factory=lambda: [15, 30, 60])
    include_subtitles: bool = True
    include_voiceover: bool = True
    include_bgm: bool = True


class GenerationResult(BaseModel):
    workflow_id: str
    assets: list[Asset]
    report: dict[str, Any]


class WorkflowStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class WorkflowJob(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wf"))
    tenant_id: str
    product_id: str
    workflow_type: Literal["main_image", "detail_page", "copy", "short_video", "full_pack"]
    status: WorkflowStatus = WorkflowStatus.queued
    progress: int = 0
    params: dict[str, Any] = Field(default_factory=dict)
    asset_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Template(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tpl"))
    tenant_id: str
    name: str
    template_type: Literal["main_image", "detail_page", "copy", "short_video"]
    platform: str = "generic"
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class DashboardStats(BaseModel):
    products: int
    assets: int
    workflows: int
    videos: int
    conversion_ready_assets: int


AuthSession.model_rebuild()
