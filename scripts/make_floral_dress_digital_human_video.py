from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "output" / "exact-floral-dress-20260712"
OUT = ROOT / "output" / "floral-dress-digital-human-20260712"
VIDEO = OUT / "video"

W, H, FPS = 1080, 1920, 24
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
    t = max(0, min(1, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def gradient() -> Image.Image:
    img = Image.new("RGB", (W, H), "#f6f3ee")
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.25 + (y / H) * 0.75
            r = int(249 * (1 - t) + 228 * t)
            g = int(247 * (1 - t) + 224 * t)
            b = int(242 * (1 - t) + 219 * t)
            px[x, y] = (r, g, b)
    return img.convert("RGBA")


def cover(img: Image.Image, size: tuple[int, int], zoom=1.0, pan_y=0.5) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height) * zoom
    im = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    x = max(0, (im.width - w) // 2)
    y = int(max(0, im.height - h) * pan_y)
    return im.crop((x, y, x + w, y + h))


def fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    im = img.copy()
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return im


def soften_presenter(img: Image.Image) -> Image.Image:
    # No background removal: crop/feather into a presenter card so it looks intentional.
    img = cover(img.convert("RGBA"), (580, 880), zoom=1.08, pan_y=0.25)
    img = ImageEnhance.Sharpness(img).enhance(1.08)
    mask = Image.new("L", img.size, 255)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, img.width, img.height), radius=42, fill=255)
    fade = Image.new("L", img.size, 0)
    fd = ImageDraw.Draw(fade)
    fd.rounded_rectangle((0, 0, img.width, img.height), radius=42, fill=255)
    img.putalpha(fade)
    return img


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


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_caption(draw: ImageDraw.ImageDraw, title: str, subtitle: str):
    rounded(draw, (62, 1470, 1018, 1718), 36, (30, 28, 27, 230))
    draw.rectangle((98, 1504, 108, 1684), fill="#e8d7c6")
    tf, sf = font(48, "bold"), font(31, "medium")
    y = 1502
    for line in wrap(title, tf, 820):
        draw.text((132, y), line, font=tf, fill="#ffffff")
        y += 61
    y += 8
    for line in wrap(subtitle, sf, 820):
        draw.text((132, y), line, font=sf, fill="#f4ede5")
        y += 42


def draw_tag(draw: ImageDraw.ImageDraw, x: int, y: int, value: str):
    f = font(27, "bold")
    w = draw.textbbox((0, 0), value, font=f)[2] + 44
    rounded(draw, (x, y, x + w, y + 58), 29, (255, 255, 255, 224), (224, 216, 207, 255), 2)
    draw.text((x + 22, y + 12), value, font=f, fill="#423a35")
    return x + w + 12


def scene_frame(product: Image.Image, presenter: Image.Image, p: float, scene_idx: int, title: str, subtitle: str, tags: list[str], mode: str) -> Image.Image:
    base = gradient()
    d = ImageDraw.Draw(base)
    d.ellipse((-260, 1120, 520, 2040), fill=(218, 204, 190, 98))
    d.ellipse((780, -170, 1240, 340), fill=(225, 230, 227, 120))
    d.rounded_rectangle((52, 54, 1028, 128), radius=37, fill=(255, 255, 255, 216), outline=(224, 218, 210, 255), width=2)
    d.text((92, 72), "数字人讲解 · 原图保真商品", font=font(30, "bold"), fill="#3b3430")
    d.text((760, 74), f"SCENE {scene_idx:02d}", font=font(28, "medium"), fill="#766b62")

    if mode == "hero":
        prod_box = (420, 180, 1030, 1390)
        prod = cover(product, (prod_box[2] - prod_box[0], prod_box[3] - prod_box[1]), zoom=1.02 + 0.03 * ease(p), pan_y=0.45)
        rounded(d, prod_box, 40, (255, 255, 255, 210), (223, 217, 210, 255), 2)
        base.alpha_composite(prod.convert("RGBA"), (prod_box[0], prod_box[1]))
        pres = presenter.resize((470, 714), Image.Resampling.LANCZOS)
        rounded(d, (58, 470, 404, 1180), 40, (255, 255, 255, 220), (224, 218, 210, 255), 2)
        base.alpha_composite(cover(pres, (346, 690), 1.0, 0.18), (58, 490))
    elif mode == "detail":
        prod = cover(product, (900, 1060), zoom=1.0 + 0.04 * ease(p), pan_y=0.4)
        rounded(d, (90, 174, 990, 1234), 40, (255, 255, 255, 220), (223, 217, 210, 255), 2)
        base.alpha_composite(prod.convert("RGBA"), (90, 174))
        pres = presenter.resize((260, 395), Image.Resampling.LANCZOS)
        rounded(d, (740, 1008, 1018, 1390), 36, (255, 255, 255, 226), (224, 218, 210, 255), 2)
        base.alpha_composite(cover(pres, (250, 362), 1.0, 0.18), (754, 1022))
    else:
        prod = cover(product, (760, 1190), zoom=1.05, pan_y=0.5)
        base.alpha_composite(prod.convert("RGBA"), (160, 180))
        pres = presenter.resize((300, 456), Image.Resampling.LANCZOS)
        base.alpha_composite(cover(pres, (290, 432), 1.0, 0.18), (74, 900))

    x = 72
    for tag in tags:
        x = draw_tag(d, x, 1360, tag)
    draw_caption(d, title, subtitle)
    d.rounded_rectangle((88, 1802, 992, 1816), radius=7, fill=(255, 255, 255, 154))
    d.rounded_rectangle((88, 1802, 88 + int(904 * p), 1816), radius=7, fill=(89, 76, 67, 255))
    return base.convert("RGB")


def write_script_files():
    script = """# 花纹连衣裙数字人带货脚本

这条花纹连衣裙，我给大家看原图保真款。
它是深色底的满版花纹，花线比较清楚，上身会比纯色更有层次。
袖子这里有轻透感，夏天穿不会显得太闷。
右侧还有系带细节，能让裙身多一点收束感。
这版视频里的商品图没有重绘衣服，花纹和版型都来自原始照片。
喜欢这种成熟、耐看、有细节的连衣裙，可以点橱窗或者直播间看同款。
"""
    (OUT / "script.md").write_text(script, encoding="utf-8")
    srt = """1
00:00:00,000 --> 00:00:05,000
这条花纹连衣裙，我给大家看原图保真款

2
00:00:05,000 --> 00:00:11,000
深色底满版花纹，花线清楚，更有层次

3
00:00:11,000 --> 00:00:17,000
袖子有轻透感，夏天穿不会显得太闷

4
00:00:17,000 --> 00:00:23,000
右侧系带细节，让裙身多一点收束感

5
00:00:23,000 --> 00:00:30,000
商品图没有重绘衣服，喜欢就点橱窗看同款
"""
    (OUT / "subtitles.srt").write_text(srt, encoding="utf-8")


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
    write_script_files()
    presenter = soften_presenter(Image.open(OUT / "digital-human-presenter.png"))
    main_img = Image.open(PRODUCT_DIR / "02_花纹连衣裙_保真主图.png").convert("RGBA")
    detail_img = Image.open(PRODUCT_DIR / "03_花纹连衣裙_保真详情图.png").convert("RGBA")
    original_img = Image.open(PRODUCT_DIR / "01_原图保真增强版.png").convert("RGBA")
    scenes = [
        (5, main_img, "原图保真花纹连衣裙", "不重绘衣服，花纹和版型来自原始照片", ["保真", "花纹", "连衣裙"], "hero"),
        (6, original_img, "深色底满版花纹", "花线清楚，整体比纯色更有层次", ["深色底", "满版花纹", "耐看"], "hero"),
        (6, detail_img, "轻透短袖细节", "袖部透感和肩线都保留原图", ["轻透袖", "圆领", "真实细节"], "detail"),
        (6, detail_img, "右侧系带细节", "让裙身多一点收束感和设计感", ["系带", "层次", "设计感"], "detail"),
        (7, main_img, "喜欢就点橱窗看同款", "成熟、耐看、有细节，适合日常通勤", ["同款", "直播间", "橱窗"], "cta"),
    ]
    silent = VIDEO / "floral-dress-digital-human-silent.mp4"
    concat = VIDEO / "concat.txt"
    concat_lines: list[str] = []
    scene_paths: list[Path] = []
    for idx, (duration, product, title, subtitle, tags, mode) in enumerate(scenes, start=1):
        scene_path = VIDEO / f"scene_{idx:02d}.png"
        scene_frame(product, presenter, 0.92, idx, title, subtitle, tags, mode).save(scene_path, quality=96)
        scene_paths.append(scene_path)
        concat_lines.append(f"file '{scene_path.as_posix()}'")
        concat_lines.append(f"duration {duration}")
    concat_lines.append(f"file '{scene_paths[-1].as_posix()}'")
    concat.write_text("\n".join(concat_lines), encoding="utf-8")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-vf",
            "scale=1080:1920,format=yuv420p",
            "-r",
            str(FPS),
            "-c:v",
            "libx264",
            str(silent),
        ],
        check=True,
        capture_output=True,
    )

    voice = (
        "这条花纹连衣裙，我给大家看原图保真款。"
        "它是深色底的满版花纹，花线比较清楚，上身会比纯色更有层次。"
        "袖子这里有轻透感，夏天穿不会显得太闷。"
        "右侧还有系带细节，能让裙身多一点收束感。"
        "这版视频里的商品图没有重绘衣服，花纹和版型都来自原始照片。"
        "喜欢这种成熟、耐看、有细节的连衣裙，可以点橱窗或者直播间看同款。"
    )
    wav = VIDEO / "voiceover.wav"
    final = VIDEO / "floral-dress-digital-human.mp4"
    if synth_voice(voice, wav):
        subprocess.run(
            [ffmpeg, "-y", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", str(final)],
            check=True,
            capture_output=True,
        )
    else:
        final.write_bytes(silent.read_bytes())
    print(final)


if __name__ == "__main__":
    main()
