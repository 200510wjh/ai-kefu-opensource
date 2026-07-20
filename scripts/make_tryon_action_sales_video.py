from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "gpt-tryon-action-images-20260711"
OUT = ROOT / "output" / "tryon-action-sales-video-20260711"
VIDEO = OUT / "video"

W, H, FPS = 1080, 1920, 24
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, weight: str = "regular"):
    path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
    return ImageFont.truetype(path, size=size)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def cover(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    scale = max(W / img.width, H / img.height) * 1.03
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def blend_pose(a: Image.Image, b: Image.Image, p: float) -> Image.Image:
    # Alternate between two pose images so the model visibly changes stance.
    cycle = (p * 3.2) % 1.0
    if cycle < 0.42:
        alpha = 0
    elif cycle < 0.58:
        alpha = ease((cycle - 0.42) / 0.16)
    else:
        alpha = 1
    base = Image.blend(a, b, alpha)
    zoom = 1.0 + 0.018 * math.sin(p * math.pi)
    nw, nh = int(W * zoom), int(H * zoom)
    frame = base.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (nw - W) // 2 + int(10 * math.sin(p * math.pi * 2))
    y = (nh - H) // 2
    return frame.crop((x, y, x + W, y + H))


def wrap(text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if not cur or f.getbbox(trial)[2] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def overlay(frame: Image.Image, title: str, sub: str, tags: list[str], theme: str, p: float) -> Image.Image:
    out = frame.convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    d.rectangle((0, 0, W, 260), fill=(255, 255, 255, 34))
    d.rectangle((0, 1260, W, H), fill=(0, 0, 0, 95))
    d.rounded_rectangle((60, 70, 360, 132), 31, fill=(255, 255, 255, 218))
    d.text((90, 84), "试穿实拍感", font=font(28, "bold"), fill="#315d72" if theme == "blue" else "#333333")

    x1, y1, x2, y2 = 58, 1430, 1022, 1702
    d.rounded_rectangle((x1, y1, x2, y2), 36, fill=(12, 22, 28, 226) if theme == "blue" else (12, 12, 14, 228))
    d.rectangle((x1 + 32, y1 + 32, x1 + 42, y2 - 32), fill="#a8ddec" if theme == "blue" else "#e3d3bf")
    tf, sf = font(52, "bold"), font(32, "medium")
    yy = y1 + 32
    for line in wrap(title, tf, 830):
        d.text((x1 + 70, yy), line, font=tf, fill="#ffffff")
        yy += 64
    yy += 8
    for line in wrap(sub, sf, 830):
        d.text((x1 + 70, yy), line, font=sf, fill="#f3fbfc")
        yy += 43

    tag_x = 72
    for tag in tags:
        f = font(28, "bold")
        w = d.textbbox((0, 0), tag, font=f)[2] + 42
        d.rounded_rectangle((tag_x, 1290, tag_x + w, 1348), 29, fill=(255, 255, 255, 218))
        d.text((tag_x + 21, 1302), tag, font=f, fill="#315d72" if theme == "blue" else "#333333")
        tag_x += w + 14

    sweep_x = int(-260 + (W + 520) * ((p * 1.7) % 1.0))
    d.polygon([(sweep_x, 0), (sweep_x + 110, 0), (sweep_x - 260, H), (sweep_x - 370, H)], fill=(255, 255, 255, 34))
    out.alpha_composite(shade)
    return out.convert("RGB")


def synth_voice(text: str, wav: Path) -> bool:
    ps = f"""
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Rate = 2
$speak.Volume = 100
$speak.SetOutputToWaveFile('{str(wav)}')
$speak.Speak('{text.replace("'", "''")}')
$speak.Dispose()
"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, text=True)
        return wav.exists()
    except Exception:
        return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    blue_a = cover(SRC / "01_蓝衣白裤_走步.png")
    blue_b = cover(SRC / "02_蓝衣白裤_侧身整理.png")
    black_a = cover(SRC / "03_黑色套裙_走步.png")
    black_b = cover(SRC / "04_黑色套裙_侧身整理.png")

    scenes = [
        (8, blue_a, blue_b, "蓝白通勤，穿上更清爽", "走步展示整体比例，日常上班很利落", ["走步", "清爽", "通勤"], "blue"),
        (7, blue_b, blue_a, "圆领短袖，腰线收得住", "侧身看版型，不松垮也不沉闷", ["收腰", "显精神", "好搭"], "blue"),
        (7, black_a, black_b, "黑色套裙，更稳重", "成熟通勤、见客户，气场更足", ["黑色", "显瘦", "稳重"], "black"),
        (8, black_b, black_a, "细节精致，点橱窗看同款", "腰侧点缀和裙摆层次，正式场景也能穿", ["细节", "同款", "直播间"], "black"),
    ]

    writer = imageio.get_writer(VIDEO / "tryon-action-sales-video-silent.mp4", fps=FPS, codec="libx264", quality=8, macro_block_size=1)
    for dur, a, b, title, sub, tags, theme in scenes:
        frames = dur * FPS
        for i in range(frames):
            p = i / max(1, frames - 1)
            frame = blend_pose(a, b, p)
            writer.append_data(np.asarray(overlay(frame, title, sub, tags, theme, p)))
    writer.close()

    script = "夏天上班想清爽又显气质，先看这套蓝白通勤。走步展示整体比例，浅雾蓝上衣配白色直筒裤，干净利落不沉闷。侧身看腰线，圆领短袖加收身版型，日常上班穿很精神。想要成熟稳重一点，就看这套黑色气质套裙。黑色显瘦，正式场景也拿得住。喜欢这种通勤穿搭，点橱窗或者直播间看同款。"
    (OUT / "script.md").write_text(script, encoding="utf-8")
    wav = VIDEO / "voiceover.wav"
    final = VIDEO / "tryon-action-sales-video.mp4"
    if synth_voice(script, wav):
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ffmpeg, "-y", "-i", str(VIDEO / "tryon-action-sales-video-silent.mp4"), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", str(final)], check=True, capture_output=True)
    else:
        final.write_bytes((VIDEO / "tryon-action-sales-video-silent.mp4").read_bytes())
    print(final)


if __name__ == "__main__":
    main()
