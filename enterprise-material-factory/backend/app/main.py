from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .auth import SessionDep, login
from .config import get_settings
from .models import (
    Asset,
    AssetKind,
    DashboardStats,
    GenerationResult,
    HistoryEvent,
    LoginRequest,
    Product,
    ProductCreate,
    ProductUpdate,
    VideoGenerationRequest,
)
from .storage import storage
from .store import store
from .workflow import run_full_pack


settings = get_settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/api/v1/auth/login")
def auth_login(payload: LoginRequest):
    return login(payload)


@app.get("/api/v1/stats", response_model=DashboardStats)
def stats(session=SessionDep) -> DashboardStats:
    return store.stats(session.tenant.id)


@app.post("/api/v1/products", response_model=Product)
def create_product(payload: ProductCreate, session=SessionDep) -> Product:
    product = store.create_product(session.tenant.id, payload)
    store.add_history(
        HistoryEvent(
            tenant_id=session.tenant.id,
            actor_id=session.user.id,
            entity_type="product",
            entity_id=product.id,
            action="product.created",
            summary=f"Created product {product.title}",
        )
    )
    return product


@app.get("/api/v1/products", response_model=list[Product])
def list_products(session=SessionDep) -> list[Product]:
    return store.list_products(session.tenant.id)


@app.get("/api/v1/products/{product_id}", response_model=Product)
def get_product(product_id: str, session=SessionDep) -> Product:
    product = store.products.get(product_id)
    if not product or product.tenant_id != session.tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.patch("/api/v1/products/{product_id}", response_model=Product)
def update_product(product_id: str, payload: ProductUpdate, session=SessionDep) -> Product:
    product = get_product(product_id, session)
    updated = store.update_product(product.id, payload)
    store.add_history(
        HistoryEvent(
            tenant_id=session.tenant.id,
            actor_id=session.user.id,
            entity_type="product",
            entity_id=product.id,
            action="product.updated",
            summary=f"Updated product {updated.title}",
        )
    )
    return updated


@app.post("/api/v1/products/{product_id}/uploads", response_model=Asset)
async def upload_product_image(product_id: str, file: UploadFile = File(...), session=SessionDep) -> Asset:
    product = get_product(product_id, session)
    content = await file.read()
    url, size = storage.put_bytes(session.tenant.id, file.filename or "upload.bin", content, file.content_type or "application/octet-stream")
    asset = store.add_asset(
        Asset(
            tenant_id=session.tenant.id,
            product_id=product.id,
            kind=AssetKind.upload,
            name=file.filename or "upload.bin",
            url=url,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=size,
        )
    )
    if not product.hero_asset_id:
        store.update_product(product.id, ProductUpdate(hero_asset_id=asset.id))
    store.add_history(
        HistoryEvent(
            tenant_id=session.tenant.id,
            actor_id=session.user.id,
            entity_type="asset",
            entity_id=asset.id,
            action="asset.uploaded",
            summary=f"Uploaded {asset.name}",
            metadata={"product_id": product.id},
        )
    )
    return asset


@app.get("/api/v1/assets", response_model=list[Asset])
def list_assets(product_id: str | None = None, session=SessionDep) -> list[Asset]:
    return store.list_assets(session.tenant.id, product_id)


@app.post("/api/v1/workflows/full-pack", response_model=GenerationResult)
def generate_full_pack(payload: VideoGenerationRequest, session=SessionDep) -> GenerationResult:
    product = get_product(payload.product_id, session)
    return run_full_pack(session.tenant.id, session.user.id, product.id, payload)


@app.get("/api/v1/history", response_model=list[HistoryEvent])
def list_history(product_id: str | None = None, session=SessionDep) -> list[HistoryEvent]:
    return store.list_history(session.tenant.id, product_id)
