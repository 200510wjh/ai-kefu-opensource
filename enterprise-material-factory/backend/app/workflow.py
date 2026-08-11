from __future__ import annotations

from .ai_engine import GeneratedArtifact, ai_engine
from .models import Asset, GenerationResult, HistoryEvent, VideoGenerationRequest, WorkflowJob, WorkflowStatus
from .storage import storage
from .store import store


def _asset_from_artifact(tenant_id: str, product_id: str, artifact: GeneratedArtifact) -> Asset:
    url, size = storage.put_bytes(tenant_id, artifact.name, artifact.content, artifact.mime_type)
    return store.add_asset(
        Asset(
            tenant_id=tenant_id,
            product_id=product_id,
            kind=artifact.kind,
            name=artifact.name,
            url=url,
            mime_type=artifact.mime_type,
            size_bytes=size,
            metadata=artifact.metadata,
        )
    )


def run_full_pack(tenant_id: str, actor_id: str, product_id: str, video_request: VideoGenerationRequest | None = None) -> GenerationResult:
    product = store.products[product_id]
    job = store.add_workflow(WorkflowJob(tenant_id=tenant_id, product_id=product_id, workflow_type="full_pack", status=WorkflowStatus.running, progress=5))
    artifacts = [
        ai_engine.generate_main_image(product),
        ai_engine.generate_detail_page(product),
        ai_engine.generate_copy(product),
    ]
    durations = video_request.durations if video_request else [15, 30, 60]
    artifacts.extend(ai_engine.generate_short_video(product, duration) for duration in durations)
    assets = [_asset_from_artifact(tenant_id, product_id, artifact) for artifact in artifacts]
    job.asset_ids = [asset.id for asset in assets]
    job.status = WorkflowStatus.succeeded
    job.progress = 100
    store.save_workflow(job)
    store.add_history(
        HistoryEvent(
            tenant_id=tenant_id,
            actor_id=actor_id,
            entity_type="workflow",
            entity_id=job.id,
            action="full_pack.generated",
            summary=f"Generated full material pack for {product.title}",
            metadata={"product_id": product_id, "asset_ids": job.asset_ids},
        )
    )
    return GenerationResult(workflow_id=job.id, assets=assets, report={"stage": "v1", "durations": durations, "assets": len(assets)})
