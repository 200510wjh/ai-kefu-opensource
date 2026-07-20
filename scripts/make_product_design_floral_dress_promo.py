from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "luxury-floral-dress-promo-20260713" / "source_used.png"
OUT = ROOT / "output" / "product-design-floral-dress-promo-20260719"
VIDEO_DIR = OUT / "video"

W, H, FPS = 1080, 1920, 24
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"


def font(size: int, medium: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_MED if medium else FONT_REG, size=size)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def cover(img: Image.Image, zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    scale = max(W / img.width, H / img.height) * zoom
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    x = int(max(0, resized.width - W) * max(0, min(1, pan_x)))
    y = int(max(0, resized.height - H) * max(0, min(1, pan_y)))
    return resized.crop((x, y, x + W, y + H))


def grade(frame: Image.Image) -> Image.Image:
    frame = ImageEnhance.Contrast(frame).enhance(1.04)
    frame = ImageEnhance.Color(frame).enhance(0.96)
    frame = ImageEnhance.Sharpness(frame).enhance(1.05)
    out = frame.convert("RGBA")
    out.alpha_composite(Image.new("RGBA", (W, H), (255, 244, 232, 18)))
    return out.convert("RGB")


def fade(frame: Image.Image, alpha: float) -> Image.Image:
    cream = Image.new("RGB", (W, H), "#f4efe8")
    return Image.blend(cream, frame, max(0, min(1, alpha)))


def draw_editorial_label(frame: Image.Image, label: str, p: float) -> Image.Image:
    out = frame.convert("RGBA")
    d = ImageDraw.Draw(out)
    a = int(235 * ease(min(1, p * 2.0)))
    d.text((72, 116), label, font=font(28, True), fill=(255, 255, 255, a))
    d.line((72, 160, 360, 160), fill=(255, 255, 255, a), width=2)
    return out.convert("RGB")


def end_card(base: Image.Image, p: float) -> Image.Image:
    frame = cover(base, 1.04 + 0.02 * ease(p), 0.5, 0.50).convert("RGBA")
    veil = Image.new("RGBA", (W, H), (248, 243, 237, int(160 * ease(p))))
    frame.alpha_composite(veil)
    d = ImageDraw.Draw(frame)
    a = int(255 * ease(max(0, (p - 0.18) / 0.56)))
    d.text((W // 2, 780), "NEW ARRIVAL", font=font(58, True), fill=(38, 34, 31, a), anchor="mm")
    d.text((W // 2, 872), "Timeless Elegance", font=font(42), fill=(90, 78, 68, a), anchor="mm")
    d.line((392, 942, 688, 942), fill=(126, 111, 98, a), width=2)
    return frame.convert("RGB")


def scene(base: Image.Image, idx: int, p: float) -> Image.Image:
    q = ease(p)
    if idx == 0:
        frame = cover(base, 1.12, 0.50, 0.90 - 0.60 * q)
        frame = draw_editorial_label(grade(frame), "SLOW DOLLY · FULL SILHOUETTE", p)
    elif idx == 1:
        frame = cover(base, 1.62 + 0.04 * q, 0.50 + 0.03 * math.sin(q * math.pi), 0.34)
        frame = draw_editorial_label(grade(frame), "V-NECKLINE · WAIST TIE", p)
    elif idx == 2:
        frame = cover(base, 2.25 + 0.14 * q, 0.48 + 0.10 * q, 0.47)
        frame = draw_editorial_label(grade(frame), "CHIFFON · FLORAL TEXTURE", p)
    elif idx == 3:
        frame = cover(base, 1.08 + 0.05 * q, 0.57 - 0.12 * q, 0.53)
        frame = draw_editorial_label(grade(frame), "EDITORIAL CAMPAIGN", p)
    else:
        frame = end_card(base, p)
    return frame


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source image not found: {SOURCE}")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source_used.png").write_bytes(SOURCE.read_bytes())

    base = Image.open(SOURCE).convert("RGB")
    durations = [6, 6, 6, 6, 5]
    silent = VIDEO_DIR / "floral-dress-product-design-promo-silent.mp4"
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264", quality=9, macro_block_size=1)
    for idx, duration in enumerate(durations):
        total = duration * FPS
        for i in range(total):
            p = i / max(1, total - 1)
            frame = scene(base, idx, p)
            alpha = min(1.0, i / (FPS * 0.7), (total - 1 - i) / (FPS * 0.7))
            writer.append_data(np.asarray(fade(frame, alpha)))
    writer.close()

    final = VIDEO_DIR / "floral-dress-product-design-promo.mp4"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-i",
            str(silent),
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            str(final),
        ],
        check=True,
        capture_output=True,
    )
    (OUT / "PROMO_NOTES.md").write_text(
        "# Product Design Promo\n\n"
        "- Style: COS / Massimo Dutti / Theory inspired luxury editorial.\n"
        "- Format: vertical 9:16, 24fps.\n"
        "- Source: `source_used.png`.\n"
        "- Motion: slow dolly, waist-detail push, chiffon macro crop, full-body editorial hold, minimalist end card.\n",
        encoding="utf-8",
    )
    print(final)


if __name__ == "__main__":
    main()
