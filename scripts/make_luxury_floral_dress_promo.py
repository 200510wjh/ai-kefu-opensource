from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\Users\Administrator\.codex\generated_images\019f1c3a-fcdb-73d1-9751-3fc7f49a2857\ig_03167578552341ac016a5335192dd08199ac2ef7a3ac1c730a.png")
OUT = ROOT / "output" / "luxury-floral-dress-promo-20260713"
VIDEO = OUT / "video"

W, H, FPS = 1080, 1920, 24
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"


def font(size: int, med: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_MED if med else FONT_REG, size=size)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def cover(img: Image.Image, zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    scale = max(W / img.width, H / img.height) * zoom
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    max_x = max(0, resized.width - W)
    max_y = max(0, resized.height - H)
    x = int(max_x * max(0, min(1, pan_x)))
    y = int(max_y * max(0, min(1, pan_y)))
    return resized.crop((x, y, x + W, y + H))


def fade(frame: Image.Image, alpha: float) -> Image.Image:
    if alpha >= 1:
        return frame
    cream = Image.new("RGB", (W, H), "#f5f0ea")
    return Image.blend(cream, frame, alpha)


def add_grade(frame: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (255, 244, 232, 22))
    out = frame.convert("RGBA")
    out.alpha_composite(overlay)
    vignette = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vignette)
    d.ellipse((-260, -180, W + 260, H + 180), fill=190)
    vignette = vignette.filter(ImageFilter.GaussianBlur(90))
    dark = Image.new("RGBA", (W, H), (34, 24, 18, 34))
    out = Image.composite(out, Image.alpha_composite(out, dark), vignette)
    return out.convert("RGB")


def title_frame(base: Image.Image, p: float) -> Image.Image:
    frame = cover(base, 1.05 + 0.02 * ease(p), 0.5, 0.5).convert("RGBA")
    veil = Image.new("RGBA", (W, H), (248, 243, 237, int(155 * ease(p))))
    frame.alpha_composite(veil)
    d = ImageDraw.Draw(frame)
    a = int(255 * ease(max(0, (p - 0.18) / 0.55)))
    d.text((W // 2, 780), "NEW ARRIVAL", font=font(54, True), fill=(38, 34, 31, a), anchor="mm")
    d.text((W // 2, 870), "Timeless Elegance", font=font(42), fill=(86, 76, 68, a), anchor="mm")
    d.line((390, 932, 690, 932), fill=(126, 111, 98, a), width=2)
    return frame.convert("RGB")


def frame_for(base: Image.Image, scene: int, p: float) -> Image.Image:
    q = ease(p)
    if scene == 0:
        # Feet-to-head upward reveal.
        img = cover(base, 1.15, 0.5, 0.90 - 0.62 * q)
    elif scene == 1:
        # V-neck, transparent sleeves and waist tie.
        img = cover(base, 1.72, 0.5 + 0.05 * math.sin(q * math.pi), 0.34)
    elif scene == 2:
        # Macro textile feel: slow push over print and chiffon texture.
        img = cover(base, 2.22 + 0.11 * q, 0.48 + 0.11 * q, 0.48)
    elif scene == 3:
        # Full-body fashion campaign shot.
        img = cover(base, 1.02 + 0.05 * q, 0.52 - 0.08 * q, 0.52)
    else:
        return title_frame(base, p)
    img = add_grade(img)
    d = ImageDraw.Draw(img)
    # Minimal editorial markers, no salesy captions.
    if scene in {1, 2}:
        text = "CHIFFON TEXTURE" if scene == 2 else "WAIST TIE · V-NECKLINE"
        d.text((76, 128), text, font=font(28, True), fill=(255, 255, 255))
        d.line((76, 174, 330, 174), fill=(255, 255, 255), width=2)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    base = Image.open(SRC).convert("RGB")
    (OUT / "source_used.png").write_bytes(SRC.read_bytes())

    scenes = [6, 6, 6, 6, 5]
    silent = VIDEO / "luxury-floral-dress-promo-silent.mp4"
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264", quality=9, macro_block_size=1)
    for scene_idx, duration in enumerate(scenes):
        total = duration * FPS
        for i in range(total):
            p = i / max(1, total - 1)
            f = frame_for(base, scene_idx, p)
            # Soft fade in/out per scene.
            alpha = min(1, i / (FPS * 0.7), (total - 1 - i) / (FPS * 0.7))
            writer.append_data(np.asarray(fade(f, alpha)))
    writer.close()

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Create a quiet luxury-style audio bed from silence so players show an audio track.
    final = VIDEO / "luxury-floral-dress-promo.mp4"
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
    print(final)


if __name__ == "__main__":
    main()
