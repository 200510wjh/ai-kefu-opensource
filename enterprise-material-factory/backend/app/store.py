from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import (
    Asset,
    DashboardStats,
    HistoryEvent,
    Product,
    ProductCreate,
    ProductUpdate,
    Template,
    Tenant,
    User,
    UserRole,
    VersionRecord,
    WorkflowJob,
    now_iso,
)


@dataclass
class InMemoryStore:
    tenants: dict[str, Tenant] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    products: dict[str, Product] = field(default_factory=dict)
    assets: dict[str, Asset] = field(default_factory=dict)
    versions: dict[str, VersionRecord] = field(default_factory=dict)
    history: dict[str, HistoryEvent] = field(default_factory=dict)
    workflows: dict[str, WorkflowJob] = field(default_factory=dict)
    templates: dict[str, Template] = field(default_factory=dict)

    def seed_demo(self) -> None:
        if self.tenants:
            return
        tenant = Tenant(slug="demo", name="Demo Enterprise")
        user = User(tenant_id=tenant.id, email="owner@example.com", name="Factory Owner", role=UserRole.owner)
        self.tenants[tenant.id] = tenant
        self.users[user.id] = user

    def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        return next((item for item in self.tenants.values() if item.slug == slug), None)

    def get_user_by_email(self, tenant_id: str, email: str) -> User | None:
        return next((item for item in self.users.values() if item.tenant_id == tenant_id and item.email == email), None)

    def create_product(self, tenant_id: str, payload: ProductCreate) -> Product:
        product = Product(tenant_id=tenant_id, **payload.model_dump())
        self.products[product.id] = product
        return product

    def update_product(self, product_id: str, payload: ProductUpdate) -> Product:
        product = self.products[product_id]
        data = product.model_dump()
        for key, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                data[key] = value
        data["updated_at"] = now_iso()
        updated = Product(**data)
        self.products[product_id] = updated
        return updated

    def list_products(self, tenant_id: str) -> list[Product]:
        return sorted([p for p in self.products.values() if p.tenant_id == tenant_id], key=lambda p: p.updated_at, reverse=True)

    def add_asset(self, asset: Asset) -> Asset:
        existing_versions = [a.version for a in self.assets.values() if a.product_id == asset.product_id and a.kind == asset.kind]
        asset.version = max(existing_versions, default=0) + 1
        self.assets[asset.id] = asset
        if asset.product_id:
            version = VersionRecord(
                tenant_id=asset.tenant_id,
                product_id=asset.product_id,
                asset_id=asset.id,
                version=asset.version,
                change_note=f"Generated {asset.kind.value}",
            )
            self.versions[version.id] = version
        return asset

    def list_assets(self, tenant_id: str, product_id: str | None = None) -> list[Asset]:
        items: Iterable[Asset] = self.assets.values()
        if product_id:
            items = [a for a in items if a.product_id == product_id]
        return sorted([a for a in items if a.tenant_id == tenant_id], key=lambda a: a.created_at, reverse=True)

    def add_history(self, event: HistoryEvent) -> HistoryEvent:
        self.history[event.id] = event
        return event

    def list_history(self, tenant_id: str, product_id: str | None = None) -> list[HistoryEvent]:
        events = [h for h in self.history.values() if h.tenant_id == tenant_id]
        if product_id:
            events = [h for h in events if h.entity_id == product_id or h.metadata.get("product_id") == product_id]
        return sorted(events, key=lambda h: h.created_at, reverse=True)

    def add_workflow(self, job: WorkflowJob) -> WorkflowJob:
        self.workflows[job.id] = job
        return job

    def save_workflow(self, job: WorkflowJob) -> WorkflowJob:
        job.updated_at = now_iso()
        self.workflows[job.id] = job
        return job

    def stats(self, tenant_id: str) -> DashboardStats:
        assets = [a for a in self.assets.values() if a.tenant_id == tenant_id]
        workflows = [w for w in self.workflows.values() if w.tenant_id == tenant_id]
        return DashboardStats(
            products=len([p for p in self.products.values() if p.tenant_id == tenant_id]),
            assets=len(assets),
            workflows=len(workflows),
            videos=len([a for a in assets if a.kind.value == "short_video"]),
            conversion_ready_assets=len([a for a in assets if a.kind.value in {"main_image", "detail_page", "copy", "short_video"}]),
        )


store = InMemoryStore()
store.seed_demo()
