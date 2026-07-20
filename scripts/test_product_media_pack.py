from __future__ import annotations

import json
import base64
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.main import ARTIFACT_DIR, app, find_ffmpeg_binary

REPORT_DIR = ROOT / "运营计划" / "今日交付包" / "商品媒体工厂测试"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    sample_photo = REPORT_DIR / "商品实拍样图.png"
    if not sample_photo.exists():
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (900, 1200), "#e0f2fe")
        draw = ImageDraw.Draw(img)
        font_path = Path(r"C:\Windows\Fonts\msyhbd.ttc")
        font_big = ImageFont.truetype(str(font_path), 64) if font_path.exists() else ImageFont.load_default()
        font_mid = ImageFont.truetype(str(font_path), 36) if font_path.exists() else ImageFont.load_default()
        draw.ellipse((260, 170, 640, 550), fill="#7dd3fc")
        draw.rounded_rectangle((330, 300, 570, 900), radius=70, fill="#ffffff", outline="#60a5fa", width=8)
        draw.rounded_rectangle((380, 210, 520, 330), radius=38, fill="#bfdbfe", outline="#60a5fa", width=6)
        draw.text((236, 965), "补水保湿精华液", fill="#0f172a", font=font_big)
        draw.text((310, 1050), "商品实拍测试图", fill="#2563eb", font=font_mid)
        img.save(sample_photo)
    data_url = "data:image/png;base64," + base64.b64encode(sample_photo.read_bytes()).decode("ascii")

    client = TestClient(app)
    payload = {
        "product_name": "补水保湿精华液",
        "category": "美妆护肤",
        "platform": "douyin",
        "price": "129.00",
        "selling_points": "深层补水,清爽不粘,敏感肌可用,熬夜急救",
        "audience": "18-35岁护肤用户",
        "visual_style": "蓝紫霓虹科技风",
        "render_video": True,
        "product_image_data_url": data_url,
    }
    response = client.post("/api/product-media/pack", json=payload)
    response.raise_for_status()
    data = response.json()
    (REPORT_DIR / "product_media_pack_response.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    frame_path = REPORT_DIR / "商品短视频首帧.png"
    ffmpeg = find_ffmpeg_binary()
    if ffmpeg and data.get("video_url"):
        video_path = ARTIFACT_DIR / data["video_url"].replace("/artifacts/", "")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_path), "-frames:v", "1", str(frame_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    summary = {
        "status": "passed",
        "sample_photo": str(sample_photo),
        "main_image": str(ARTIFACT_DIR / data["main_image_url"].replace("/artifacts/", "")),
        "detail_image": str(ARTIFACT_DIR / data["detail_image_url"].replace("/artifacts/", "")),
        "video_preview": str(ARTIFACT_DIR / data["video_preview_url"].replace("/artifacts/", "")),
        "video": str(ARTIFACT_DIR / data["video_url"].replace("/artifacts/", "")) if data.get("video_url") else "",
        "video_status": data["video_status"],
        "first_frame": str(frame_path) if frame_path.exists() else "",
        "publish_boundary": data["listing_draft"]["publish_boundary"],
    }
    (REPORT_DIR / "测试摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
