from __future__ import annotations

import json
from dataclasses import dataclass

from .models import AssetKind, Product


@dataclass
class GeneratedArtifact:
    kind: AssetKind
    name: str
    content: bytes
    mime_type: str
    metadata: dict


class AIEngine:
    """Single integration point for all model providers.

    V1 ships with deterministic adapters so workflows are testable. Real OpenAI,
    MiniMax, HeyGen, or internal model providers should be added behind this
    interface instead of leaking into product/workflow modules.
    """

    def generate_main_image(self, product: Product) -> GeneratedArtifact:
        points = " / ".join(product.selling_points[:3]) or "Premium product visual"
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1350'>
<rect width='1080' height='1350' fill='#f7f5f0'/>
<rect x='80' y='80' width='920' height='1190' rx='34' fill='#fff' stroke='#ddd5ca'/>
<text x='120' y='180' font-size='56' font-family='Arial' fill='#1f2933'>{product.title}</text>
<text x='120' y='252' font-size='32' font-family='Arial' fill='#6b7280'>{product.category}</text>
<circle cx='540' cy='640' r='260' fill='#ebe3d7'/>
<text x='540' y='650' text-anchor='middle' font-size='42' font-family='Arial' fill='#443c35'>MAIN IMAGE</text>
<text x='120' y='1120' font-size='34' font-family='Arial' fill='#2f2a26'>{points}</text>
</svg>"""
        return GeneratedArtifact(AssetKind.main_image, "main-image.svg", svg.encode("utf-8"), "image/svg+xml", {"engine": "deterministic"})

    def generate_detail_page(self, product: Product) -> GeneratedArtifact:
        sections = [{"title": point, "body": f"{point} - ready for platform-specific layout."} for point in product.selling_points]
        html = f"""<!doctype html><html><body>
<h1>{product.title}</h1>
<p>{product.description}</p>
<section>{''.join(f'<h2>{s["title"]}</h2><p>{s["body"]}</p>' for s in sections)}</section>
</body></html>"""
        return GeneratedArtifact(AssetKind.detail_page, "detail-page.html", html.encode("utf-8"), "text/html", {"sections": sections})

    def generate_copy(self, product: Product) -> GeneratedArtifact:
        payload = {
            "titles": [
                f"{product.title}｜一图看懂核心卖点",
                f"{product.title} 上新，适合多平台投放",
                f"{product.title} 企业级素材包",
            ],
            "selling_copy": f"{product.title}，{product.description or '围绕核心卖点生成多平台转化文案。'}",
            "platform_versions": {platform: f"{product.title} - {platform} version" for platform in product.target_platforms},
        }
        return GeneratedArtifact(AssetKind.copy, "copy.json", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", payload)

    def generate_short_video(self, product: Product, duration: int) -> GeneratedArtifact:
        storyboard = {
            "duration": duration,
            "format": "9:16",
            "subtitle": True,
            "voiceover": True,
            "bgm": True,
            "scenes": [
                {"time": "0-3s", "visual": "Hero product hook", "caption": product.title},
                {"time": "3-10s", "visual": "Main selling points", "caption": " / ".join(product.selling_points[:2])},
                {"time": "final", "visual": "CTA and platform export", "caption": "NEW ARRIVAL"},
            ],
        }
        data = json.dumps(storyboard, ensure_ascii=False, indent=2).encode("utf-8")
        return GeneratedArtifact(AssetKind.short_video, f"short-video-{duration}s.json", data, "application/json", storyboard)


ai_engine = AIEngine()
