from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "gpt-tryon-product-images-20260711"
OUT = ROOT / "output" / "tryon-motion-sales-video-20260711"
VIDEO = OUT / "video"

W, H = 1080, 1920
FPS = 20
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


FONT_CACHE: dict[tuple[int, str], ImageFont.FreeTypeFont] = {}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key not in FONT_CACHE:
        path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
        FONT_CACHE[key] = ImageFont.truetype(path, size=size)
    return FONT_CACHE[key]


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def load_cover(path: Path, zoom: float = 1.04) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    scale = max(W / img.width, H / img.height) * zoom
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)


def crop_motion(img: Image.Image, t: float, pan: str) -> Image.Image:
    max_x = max(0, img.width - W)
    max_y = max(0, img.height - H)
    if pan == "left":
        px = 0.70 - 0.24 * t
        py = 0.50 + 0.04 * math.sin(t * math.pi)
    elif pan == "right":
        px = 0.28 + 0.25 * t
        py = 0.50 + 0.04 * math.sin(t * math.pi)
    elif pan == "up":
        px = 0.50
        py = 0.62 - 0.20 * t
    else:
        px = 0.50 + 0.04 * math.sin(t * math.pi * 2)
        py = 0.50
    x = int(max_x * max(0, min(1, px)))
    y = int(max_y * max(0, min(1, py)))
    return img.crop((x, y, x + W, y + H))


def wrap(text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if not current or f.getbbox(trial)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_caption(draw: ImageDraw.ImageDraw, y: int, title: str, subtitle: str, theme: str, progress: float):
    x1, x2 = 58, 1022
    slide = int((1 - ease(min(1, progress * 1.8))) * 90)
    y1 = y + slide
    y2 = y1 + 246
    fill = (14, 25, 30, 226) if theme == "blue" else (14, 14, 16, 228)
    accent = "#9ed9e8" if theme == "blue" else "#e0d2c1"
    draw.rounded_rectangle((x1, y1, x2, y2), radius=36, fill=fill)
    draw.rectangle((x1 + 34, y1 + 30, x1 + 44, y2 - 30), fill=accent)
    tf = font(50, "bold")
    sf = font(32, "medium")
    yy = y1 + 30
    for line in wrap(title, tf, 820):
        draw.text((x1 + 70, yy), line, font=tf, fill="#ffffff")
        yy += 62
    yy += 8
    for line in wrap(subtitle, sf, 820):
        draw.text((x1 + 70, yy), line, font=sf, fill="#f0f8fa" if theme == "blue" else "#f7f3ee")
        yy += 44


def draw_tag(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, theme: str, progress: float):
    local = ease(min(1, max(0, progress)))
    x = x + int((1 - local) * 70)
    f = font(28, "bold")
    bbox = draw.textbbox((0, 0), label, font=f)
    w = bbox[2] - bbox[0] + 42
    fill = (255, 255, 255, int(210 * local))
    outline = (207, 225, 230, int(255 * local)) if theme == "blue" else (220, 214, 208, int(255 * local))
    draw.rounded_rectangle((x, y, x + w, y + 58), radius=29, fill=fill, outline=outline, width=2)
    draw.text((x + 21, y + 12), label, font=f, fill="#315d72" if theme == "blue" else "#383838")


def draw_light_sweep(base: Image.Image, progress: float):
    if not 0.18 < progress < 0.72:
        return
    sweep = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    d = ImageDraw.Draw(sweep)
    x = int(-260 + (W + 520) * ((progress - 0.18) / 0.54))
    d.polygon([(x, 0), (x + 130, 0), (x - 250, H), (x - 380, H)], fill=(255, 255, 255, 46))
    base.alpha_composite(sweep)


def scene_frame(bg: Image.Image, scene_no: int, p: float, title: str, subtitle: str, tags: list[str], theme: str, pan: str) -> Image.Image:
    frame = crop_motion(bg, ease(p), pan).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    top_alpha = int(40 + 20 * math.sin(p * math.pi))
    bottom_alpha = 92 if theme == "blue" else 104
    d.rectangle((0, 0, W, 260), fill=(248, 252, 252, top_alpha))
    d.rectangle((0, 1260, W, H), fill=(0, 0, 0, bottom_alpha))
    d.rounded_rectangle((58, 58, 330, 118), radius=30, fill=(255, 255, 255, 222), outline=(219, 230, 232, 255))
    d.text((86, 72), f"LOOK {scene_no:02d}", font=font(28, "bold"), fill="#315d72" if theme == "blue" else "#333333")
    draw_caption(d, 1424, title, subtitle, theme, p)
    for i, tag in enumerate(tags):
        draw_tag(d, 72 + i * 250, 1280, tag, theme, p - i * 0.08)
    bar_w = int(916 * min(1, p))
    d.rounded_rectangle((82, 1818, 998, 1832), radius=7, fill=(255, 255, 255, 145))
    d.rounded_rectangle((82, 1818, 82 + bar_w, 1832), radius=7, fill=(111, 177, 194, 255) if theme == "blue" else (222, 210, 194, 255))
    frame.alpha_composite(overlay)
    draw_light_sweep(frame, p)
    return frame.convert("RGB")


def write_script_files():
    srt = """1
00:00:00,000 --> 00:00:04,000
夏天上班想清爽又显气质，先看这套蓝白通勤

2
00:00:04,000 --> 00:00:10,000
浅雾蓝上衣配白色直筒裤，干净、利落、不沉闷

3
00:00:10,000 --> 00:00:16,000
圆领短袖加收腰线条，日常上班穿很精神

4
00:00:16,000 --> 00:00:21,000
白裤修饰腿型，整套拍照也很清爽

5
00:00:21,000 --> 00:00:26,000
想要成熟稳重一点，就看这套黑色气质套裙

6
00:00:26,000 --> 00:00:30,000
喜欢这种通勤穿搭，点橱窗或者直播间看同款
"""
    (OUT / "subtitles.srt").write_text(srt, encoding="utf-8")
    md = """# 模特试穿带货视频口播

夏天上班想清爽又显气质，先看这套蓝白通勤。
浅雾蓝上衣配白色直筒裤，干净、利落、不沉闷。
圆领短袖加收腰线条，日常上班穿很精神。
白裤修饰腿型，整套拍照也很清爽。
想要成熟稳重一点，就看这套黑色气质套裙。
喜欢这种通勤穿搭，点橱窗或者直播间看同款。
"""
    (OUT / "script.md").write_text(md, encoding="utf-8")


def synth_voice(text_value: str, wav_path: Path) -> bool:
    ps = f"""
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Rate = 2
$speak.Volume = 100
$speak.SetOutputToWaveFile('{str(wav_path)}')
$speak.Speak('{text_value.replace("'", "''")}')
$speak.Dispose()
"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True, text=True)
        return wav_path.exists()
    except Exception:
        return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    write_script_files()
    sources = {
        "blue_full": load_cover(SRC / "01_模特试穿_蓝衣白裤全身.png", 1.03),
        "blue_detail": load_cover(SRC / "02_模特试穿_蓝衣白裤细节.png", 1.05),
        "black_full": load_cover(SRC / "03_模特试穿_黑色套裙全身.png", 1.03),
        "black_detail": load_cover(SRC / "04_模特试穿_黑色套裙细节.png", 1.05),
    }
    scenes = [
        (4.0, sources["blue_full"], "蓝白通勤，一眼清爽", "夏天上班想有气质，先看这一套", ["清爽", "通勤", "显气质"], "blue", "up"),
        (6.0, sources["blue_full"], "浅雾蓝 + 白色直筒裤", "颜色干净，版型利落，日常不沉闷", ["蓝白套装", "利落", "好搭"], "blue", "left"),
        (6.0, sources["blue_detail"], "圆领短袖，腰线更精神", "上身线条收得住，通勤穿不松垮", ["圆领", "收腰", "显精神"], "blue", "right"),
        (5.0, sources["blue_detail"], "白裤修饰腿型", "直筒线条更干净，拍照也清爽", ["直筒", "垂顺", "修饰腿型"], "blue", "up"),
        (5.0, sources["black_full"], "黑色套裙，更稳重", "成熟通勤、见客户、正式场景都合适", ["黑色套裙", "稳重", "显瘦"], "black", "left"),
        (4.0, sources["black_detail"], "喜欢就点橱窗看同款", "直播间活动信息可后续替换", ["同款", "橱窗", "直播间"], "black", "right"),
    ]
    silent = VIDEO / "tryon-motion-sales-video-silent.mp4"
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264", quality=8, macro_block_size=1)
    for idx, (duration, bg, title, subtitle, tags, theme, pan) in enumerate(scenes, start=1):
        frames = int(duration * FPS)
        for i in range(frames):
            writer.append_data(np.asarray(scene_frame(bg, idx, i / max(1, frames - 1), title, subtitle, tags, theme, pan)))
    writer.close()

    narration = (
        "夏天上班想清爽又显气质，先看这套蓝白通勤。"
        "浅雾蓝上衣配白色直筒裤，干净、利落、不沉闷。"
        "圆领短袖加收腰线条，日常上班穿很精神。"
        "白裤修饰腿型，整套拍照也很清爽。"
        "想要成熟稳重一点，就看这套黑色气质套裙。"
        "喜欢这种通勤穿搭，点橱窗或者直播间看同款。"
    )
    final = VIDEO / "tryon-motion-sales-video.mp4"
    wav = VIDEO / "voiceover.wav"
    if synth_voice(narration, wav):
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(silent),
                "-i",
                str(wav),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(final),
            ],
            check=True,
            capture_output=True,
        )
    else:
        final.write_bytes(silent.read_bytes())
    print(final)


if __name__ == "__main__":
    main()
