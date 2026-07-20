from __future__ import annotations

import math
import subprocess
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "gpt-premium-product-images-20260711"
OUT = ROOT / "output" / "gpt-product-sales-video-20260711"
VIDEO = OUT / "video"

W, H = 1080, 1920
FPS = 24
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
    return ImageFont.truetype(path, size=size)


def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, t)))


def wrap(value: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in value:
        trial = current + ch
        if not current or f.getbbox(trial)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_text_box(draw: ImageDraw.ImageDraw, box, title: str, subtitle: str, theme: str = "blue"):
    x1, y1, x2, y2 = box
    fill = (16, 28, 34, 232) if theme == "blue" else (18, 18, 20, 232)
    accent = "#9ed6e5" if theme == "blue" else "#dfd7cd"
    draw.rounded_rectangle(box, radius=34, fill=fill)
    draw.rectangle((x1 + 34, y1 + 30, x1 + 44, y2 - 30), fill=accent)
    title_font = font(52, "bold")
    sub_font = font(34, "medium")
    y = y1 + 28
    for line in wrap(title, title_font, x2 - x1 - 104):
        draw.text((x1 + 70, y), line, font=title_font, fill="#ffffff")
        y += 66
    y += 6
    for line in wrap(subtitle, sub_font, x2 - x1 - 104):
        draw.text((x1 + 70, y), line, font=sub_font, fill="#eef8fa" if theme == "blue" else "#f5f2ee")
        y += 46


def cover_image(img: Image.Image, target: tuple[int, int], zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    tw, th = target
    scale = max(tw / img.width, th / img.height) * zoom
    nw, nh = int(img.width * scale), int(img.height * scale)
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    max_x = max(0, nw - tw)
    max_y = max(0, nh - th)
    x = int(max_x * pan_x)
    y = int(max_y * pan_y)
    return resized.crop((x, y, x + tw, y + th))


def fit_image(img: Image.Image, max_w: int, max_h: int, zoom: float) -> Image.Image:
    scale = min(max_w / img.width, max_h / img.height) * zoom
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)


def scene_frame(src: Image.Image, scene_index: int, local: float, dur: float, title: str, subtitle: str, theme: str) -> Image.Image:
    p = ease(local / dur)
    bg = cover_image(src, (W, H), 1.1 + 0.05 * p, 0.5, 0.5).filter(ImageFilter.GaussianBlur(18))
    veil = Image.new("RGBA", (W, H), (246, 250, 250, 190) if theme == "blue" else (246, 245, 242, 186))
    base = Image.alpha_composite(bg.convert("RGBA"), veil)
    d = ImageDraw.Draw(base)

    d.ellipse((-230, 1300, 520, 2050), fill=(191, 225, 235, 80) if theme == "blue" else (210, 205, 202, 76))
    d.ellipse((780, -170, 1240, 330), fill=(236, 222, 202, 86))

    hero = fit_image(src, 900, 1200, 1.0 + 0.025 * p)
    x = (W - hero.width) // 2 + int((p - 0.5) * 18)
    y = 168 + int(math.sin(p * math.pi) * -10)
    shadow = Image.new("RGBA", hero.size, (0, 0, 0, 0))
    mask = Image.new("L", hero.size, 190).filter(ImageFilter.GaussianBlur(30))
    shadow.putalpha(mask.point(lambda a: min(58, a)))
    base.alpha_composite(shadow, (x + 10, y + 24))
    base.alpha_composite(hero, (x, y))

    badge_fill = (255, 255, 255, 224)
    d.rounded_rectangle((72, 70, 386, 128), radius=29, fill=badge_fill, outline=(218, 230, 233, 255))
    d.text((98, 82), f"LOOK {scene_index:02d} / 30s", font=font(26, "bold"), fill="#385867" if theme == "blue" else "#444444")

    draw_text_box(d, (66, 1440, 1014, 1708), title, subtitle, theme)
    progress = int((scene_index / 6) * 900)
    d.rounded_rectangle((90, 1766, 990, 1778), radius=6, fill=(255, 255, 255, 180))
    d.rounded_rectangle((90, 1766, 90 + progress, 1778), radius=6, fill=(102, 168, 188, 255) if theme == "blue" else (46, 46, 48, 255))
    d.text((90, 1804), "橱窗 / 直播间看同款", font=font(30, "medium"), fill="#273941" if theme == "blue" else "#303033")
    return base.convert("RGB")


def write_srt():
    srt = """1
00:00:00,000 --> 00:00:04,000
夏天上班想穿得清爽又有气质，看这一套

2
00:00:04,000 --> 00:00:11,000
浅雾蓝上衣搭白色直筒裤，干净又利落

3
00:00:11,000 --> 00:00:17,000
圆领短袖、收腰剪裁，通勤不沉闷

4
00:00:17,000 --> 00:00:22,000
白色裤型修饰腿线，蓝白配色很显气质

5
00:00:22,000 --> 00:00:27,000
还有黑色气质套裙，成熟稳重更适合正式场景

6
00:00:27,000 --> 00:00:30,000
喜欢这种不用费力的穿搭，点橱窗看同款
"""
    (OUT / "subtitles.srt").write_text(srt, encoding="utf-8")


def write_script():
    md = """# 带货视频口播脚本

夏天上班想穿得清爽又有气质，看这一套。
浅雾蓝上衣搭白色直筒裤，颜色干净，版型也很利落。
圆领短袖不挑人，腰线这里做了收身感，通勤穿不会显得松垮。
下身白色直筒裤能修饰腿线，蓝白配色看起来更清爽，也更显气质。
如果想要更稳重一点，还有这套黑色气质套裙，成熟通勤、见客户都合适。
喜欢这种不用费力就能穿出精神感的搭配，点橱窗或者直播间看同款。

说明：未写具体价格、材质、尺码和品牌名，方便后续替换成真实商品信息。
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
    write_srt()
    write_script()

    imgs = {
        "blue_main": Image.open(SRC / "01_GPT优质版_蓝衣白裤主图.png").convert("RGBA"),
        "blue_detail": Image.open(SRC / "02_GPT优质版_蓝衣白裤详情图.png").convert("RGBA"),
        "black_main": Image.open(SRC / "03_GPT优质版_黑色套裙主图.png").convert("RGBA"),
        "black_detail": Image.open(SRC / "04_GPT优质版_黑色套裙详情图.png").convert("RGBA"),
    }

    scenes = [
        (4.0, imgs["blue_main"], "夏天通勤想清爽一点", "浅雾蓝 + 白色直筒裤，一套就很干净", "blue"),
        (7.0, imgs["blue_main"], "蓝白套装不费力", "上班、见客户、日常约会都能穿", "blue"),
        (6.0, imgs["blue_detail"], "圆领短袖 / 收腰剪裁", "细节更利落，通勤穿不显松垮", "blue"),
        (5.0, imgs["blue_detail"], "白色直筒裤修饰腿线", "蓝白配色清爽，也更显气质", "blue"),
        (5.0, imgs["black_main"], "还有黑色气质套裙", "成熟稳重，正式场景也拿得住", "black"),
        (3.0, imgs["black_detail"], "喜欢就点橱窗看同款", "直播间活动信息可后续替换", "black"),
    ]

    silent = VIDEO / "gpt-product-sales-video-silent.mp4"
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264", quality=8, macro_block_size=16)
    scene_index = 1
    for dur, src, title, subtitle, theme in scenes:
        total = int(dur * FPS)
        for i in range(total):
            frame = scene_frame(src, scene_index, i / FPS, dur, title, subtitle, theme)
            writer.append_data(np.asarray(frame))
        scene_index += 1
    writer.close()

    narration = (
        "夏天上班想穿得清爽又有气质，看这一套。"
        "浅雾蓝上衣搭白色直筒裤，颜色干净，版型也很利落。"
        "圆领短袖不挑人，腰线这里做了收身感，通勤穿不会显得松垮。"
        "下身白色直筒裤能修饰腿线，蓝白配色看起来更清爽，也更显气质。"
        "如果想要更稳重一点，还有这套黑色气质套裙，成熟通勤、见客户都合适。"
        "喜欢这种不用费力就能穿出精神感的搭配，点橱窗或者直播间看同款。"
    )
    wav = VIDEO / "voiceover.wav"
    final = VIDEO / "gpt-product-sales-video.mp4"
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
