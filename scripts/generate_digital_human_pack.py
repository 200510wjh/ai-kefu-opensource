from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "digital-human-blue-white-20260711"
ASSETS = OUT / "assets"
VIDEO = OUT / "video"

SRC_BLACK = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\1a08602c399ad98bf4469c5b59b80c35.jpg")
SRC_BLUE = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\eab45fb8ee534a6e04208cc735cbcfd6.jpg")
SRC_PANTS = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\3a7dbb7e430ed2611e8765e5b5de2bdd.jpg")

W, H = 1080, 1920
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, bold: bool = False, med: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_MED if med else FONT_REG
    return ImageFont.truetype(path, size=size)


def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, size=48, fill="#1d2430", bold=False, med=False, anchor=None, align="left", max_width=None):
    f = font(size, bold=bold, med=med)
    if max_width:
        lines = wrap_text(value, f, max_width)
        y = xy[1]
        for line in lines:
            draw.text((xy[0], y), line, font=f, fill=fill, anchor=anchor, align=align)
            y += int(size * 1.3)
        return y
    draw.text(xy, value, font=f, fill=fill, anchor=anchor, align=align)
    return xy[1] + size


def wrap_text(value: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines, current = [], ""
    for ch in value:
        trial = current + ch
        if f.getbbox(trial)[2] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def bg() -> Image.Image:
    img = Image.new("RGB", (W, H), "#f8fbfc")
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.45 + (y / H) * 0.55
            r = int(248 * (1 - t) + 230 * t)
            g = int(251 * (1 - t) + 244 * t)
            b = int(252 * (1 - t) + 241 * t)
            px[x, y] = (r, g, b)
    return img


def cutout(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    datas = img.getdata()
    new = []
    for r, g, b, a in datas:
        if r > 242 and g > 242 and b > 242:
            new.append((255, 255, 255, 0))
        else:
            new.append((r, g, b, a))
    img.putdata(new)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    return img


def fit(im: Image.Image, box_w: int, box_h: int) -> Image.Image:
    out = im.copy()
    out.thumbnail((box_w, box_h), Image.Resampling.LANCZOS)
    return out


def shadow_paste(base: Image.Image, im: Image.Image, xy: tuple[int, int], blur=28, alpha=90):
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    mask = im.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    shadow.putalpha(mask.point(lambda p: min(alpha, p)))
    sx, sy = xy[0] + 18, xy[1] + 24
    base.alpha_composite(shadow, (sx, sy))
    base.alpha_composite(im, xy)


def pill(draw, xy, value, fill="#ffffff", fg="#315d72", outline="#d9e8ec"):
    f = font(30, med=True)
    pad_x, pad_y = 24, 12
    box = f.getbbox(value)
    w, h = box[2] - box[0] + pad_x * 2, box[3] - box[1] + pad_y * 2 + 4
    rounded_rect(draw, (xy[0], xy[1], xy[0] + w, xy[1] + h), 24, fill, outline)
    draw.text((xy[0] + pad_x, xy[1] + pad_y - 2), value, font=f, fill=fg)


def save_card(name: str, title: str, subtitle: str, products: list[tuple[Image.Image, tuple[int, int], tuple[int, int]]], bullets: list[str], palette="#b9d8e8"):
    canvas = bg().convert("RGBA")
    d = ImageDraw.Draw(canvas)
    d.ellipse((-240, -180, 420, 480), fill=palette + "80")
    d.ellipse((720, 1280, 1280, 1900), fill="#e7d9c680")
    text(d, (76, 96), title, 74, "#1b2931", bold=True, max_width=880)
    text(d, (80, 258), subtitle, 34, "#52626d", med=True, max_width=820)
    for src, pos, size in products:
        im = fit(src, *size)
        shadow_paste(canvas, im, pos)
    panel_y = 1450
    rounded_rect(d, (72, panel_y, 1008, 1810), 42, "#ffffffdd", "#dce8ea", 2)
    y = panel_y + 46
    for b in bullets:
        d.ellipse((116, y + 16, 132, y + 32), fill="#75a9bb")
        text(d, (154, y), b, 36, "#263640", med=True, max_width=760)
        y += 78
    canvas.convert("RGB").save(ASSETS / name, quality=96)


def create_avatar() -> Image.Image:
    img = Image.new("RGBA", (420, 760), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((118, 34, 302, 218), fill="#f0c8ad")
    d.pieslice((90, 12, 330, 238), 180, 360, fill="#463d3b")
    d.rectangle((110, 116, 310, 158), fill="#463d3b")
    d.ellipse((162, 125, 176, 139), fill="#2b2828")
    d.ellipse((244, 125, 258, 139), fill="#2b2828")
    d.arc((186, 128, 236, 178), 20, 160, fill="#ad7662", width=3)
    d.arc((172, 156, 250, 202), 20, 160, fill="#b64d57", width=4)
    d.polygon([(210, 214), (92, 710), (330, 710)], fill="#bedbea")
    d.polygon([(92, 710), (38, 746), (382, 746), (330, 710)], fill="#f7f7f2")
    d.line((155, 352, 265, 352), fill="#ffffff", width=6)
    d.ellipse((184, 244, 236, 296), fill="#f0c8ad")
    return img


def product_frame(bg_path: Path, title: str, subtitle: str, t: float, caption: str) -> Image.Image:
    canvas = bg().convert("RGBA")
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, H), fill="#f7fbfb")
    d.ellipse((-260 + int(30 * math.sin(t)), 1060, 520, 1850), fill="#d9edf280")
    d.ellipse((670, -160, 1270, 460), fill="#f0dfc980")
    avatar = create_avatar()
    avatar = avatar.resize((330, 596), Image.Resampling.LANCZOS)
    canvas.alpha_composite(avatar, (678, 410))
    rounded_rect(d, (58, 82, 1022, 246), 36, "#ffffffdd", "#d9e9ec", 2)
    text(d, (96, 110), title, 48, "#17242b", bold=True, max_width=700)
    text(d, (96, 178), subtitle, 28, "#5a6870", med=True, max_width=720)
    prod = Image.open(bg_path).convert("RGBA")
    prod = fit(prod, 590, 900)
    shadow_paste(canvas, prod, (82, 390 + int(10 * math.sin(t * 2))), 18, 80)
    rounded_rect(d, (76, 1512, 1004, 1696), 34, "#17242bea", None)
    text(d, (114, 1540), caption, 44, "#ffffff", bold=True, max_width=850)
    pill(d, (114, 1722), "清爽", "#ffffff", "#315d72")
    pill(d, (250, 1722), "通勤", "#ffffff", "#315d72")
    pill(d, (386, 1722), "气质套装", "#ffffff", "#315d72")
    return canvas.convert("RGB")


def write_text_files():
    script = """# 数字人口播脚本：蓝衣白裤通勤套装

主播人设：轻熟女装店主，亲和、专业、利落。

完整口播：
夏天上班想穿得清爽又有气质，看这一套。
这件浅蓝色上衣，圆领短袖很干净，腰线这里做了收身剪裁，穿上不会显得松垮。
下面搭白色直筒长裤，视觉上更利落，也更显腿直。
浅蓝配白色，整套看起来很清爽，通勤、见客户、日常约会都能穿。
喜欢这种不用费力就显气质的搭配，点橱窗或者直播间看同款。

剪辑提示：
- 0-3 秒：数字人半身出镜，左侧展示套装主图。
- 3-12 秒：切上衣详情图，字幕突出“圆领短袖 / 腰线剪裁 / 清爽浅蓝”。
- 12-21 秒：切白裤详情图，字幕突出“直筒利落 / 修饰腿型 / 浅蓝配白”。
- 21-27 秒：切通勤场景图，强调上班、见客户、约会。
- 27-30 秒：收尾 CTA 图，保留橱窗/直播间活动口径。
"""
    (OUT / "script-and-shotlist.md").write_text(script, encoding="utf-8")

    srt = """1
00:00:00,000 --> 00:00:03,000
夏天上班想穿得清爽又有气质，看这一套

2
00:00:03,000 --> 00:00:12,000
浅蓝色上衣，圆领短袖很干净，腰线剪裁不松垮

3
00:00:12,000 --> 00:00:21,000
搭白色直筒长裤，更利落，也更显腿直

4
00:00:21,000 --> 00:00:27,000
通勤、见客户、日常约会都能穿

5
00:00:27,000 --> 00:00:30,000
喜欢这套，点橱窗或者直播间看同款
"""
    (OUT / "subtitles.srt").write_text(srt, encoding="utf-8")

    prompt = """# 数字人工具生成提示词

画幅：9:16 竖屏，1080x1920，约 30 秒。

数字人：30-38 岁轻熟女装店主，干净自然妆，浅色通勤上衣，半身或三分之二身出镜，普通话，语速中快，亲和但不夸张。

画面：左侧或背景轮播商品图，右侧数字人口播。使用 `assets/01_blue_white_main.png`、`assets/02_blue_top_detail.png`、`assets/03_white_pants_detail.png`、`assets/04_commute_scene.png`、`assets/05_cta.png`。

口播：使用 `script-and-shotlist.md` 中“完整口播”。

字幕：使用 `subtitles.srt`，重点词加粗或高亮：清爽、通勤、显腿直、气质、同款。

注意：不要添加未确认价格、面料成分、品牌授权、尺码或库存信息。
"""
    (OUT / "digital-human-prompt.md").write_text(prompt, encoding="utf-8")


def write_preview_html():
    html = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>蓝衣白裤数字人带货视频预览</title>
<style>
  body { margin: 0; background: #101820; display: grid; place-items: center; min-height: 100vh; font-family: "Noto Sans SC", "Microsoft YaHei", sans-serif; }
  .stage { width: min(100vw, 56.25vh); aspect-ratio: 9 / 16; position: relative; overflow: hidden; background: #f7fbfb; box-shadow: 0 24px 90px rgba(0,0,0,.36); }
  .scene { position: absolute; inset: 0; opacity: 0; animation: show 30s linear infinite; }
  .scene img { width: 100%; height: 100%; object-fit: cover; }
  .s1 { animation-delay: 0s; }
  .s2 { animation-delay: 3s; }
  .s3 { animation-delay: 12s; }
  .s4 { animation-delay: 21s; }
  .s5 { animation-delay: 27s; }
  @keyframes show {
    0%, 10% { opacity: 1; transform: scale(1); }
    12%, 100% { opacity: 0; transform: scale(1.025); }
  }
  .caption { position: absolute; left: 6%; right: 6%; bottom: 8%; color: #fff; background: rgba(23,36,43,.92); border-radius: 20px; padding: 18px 22px; font-size: clamp(18px, 4vw, 38px); font-weight: 800; line-height: 1.25; letter-spacing: 0; }
  .tag { position: absolute; top: 4%; left: 6%; color: #315d72; background: rgba(255,255,255,.86); border: 1px solid #d9e9ec; padding: 10px 16px; border-radius: 999px; font-weight: 700; }
</style>
</head>
<body>
  <main class="stage">
    <div class="scene s1"><img src="assets/01_blue_white_main.png"><div class="tag">0-3s</div><div class="caption">夏天上班想穿得清爽又有气质，看这一套</div></div>
    <div class="scene s2"><img src="assets/02_blue_top_detail.png"><div class="tag">3-12s</div><div class="caption">圆领短袖很干净，腰线剪裁不松垮</div></div>
    <div class="scene s3"><img src="assets/03_white_pants_detail.png"><div class="tag">12-21s</div><div class="caption">白色直筒长裤，更利落，也更显腿直</div></div>
    <div class="scene s4"><img src="assets/04_commute_scene.png"><div class="tag">21-27s</div><div class="caption">通勤、见客户、日常约会都能穿</div></div>
    <div class="scene s5"><img src="assets/05_cta.png"><div class="tag">27-30s</div><div class="caption">喜欢这套，点橱窗或者直播间看同款</div></div>
  </main>
</body>
</html>
"""
    (OUT / "preview.html").write_text(html, encoding="utf-8")


def synth_voice(text_value: str, wav_path: Path):
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


def render_video():
    scenes = [
        (0, 3, ASSETS / "01_blue_white_main.png", "夏天上班想穿得清爽又有气质，看这一套"),
        (3, 12, ASSETS / "02_blue_top_detail.png", "圆领短袖很干净，腰线剪裁不松垮"),
        (12, 21, ASSETS / "03_white_pants_detail.png", "白色直筒长裤，更利落，也更显腿直"),
        (21, 27, ASSETS / "04_commute_scene.png", "通勤、见客户、日常约会都能穿"),
        (27, 30, ASSETS / "05_cta.png", "喜欢这套，点橱窗或者直播间看同款"),
    ]
    silent = VIDEO / "blue-white-digital-human-preview-silent.mp4"
    concat = VIDEO / "concat.txt"
    lines = []
    rendered = []
    for idx, scene in enumerate(scenes, start=1):
        frame_path = VIDEO / f"scene_{idx:02d}.png"
        img = product_frame(scene[2], "轻熟女装店主推荐", "蓝衣白裤通勤套装 / 30 秒口播预览", 0, scene[3])
        img.save(frame_path, quality=96)
        rendered.append(frame_path)
        lines.append(f"file '{frame_path.as_posix()}'")
        lines.append(f"duration {scene[1] - scene[0]}")
    lines.append(f"file '{rendered[-1].as_posix()}'")
    concat.write_text("\n".join(lines), encoding="utf-8")

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
            "30",
            "-c:v",
            "libx264",
            str(silent),
        ],
        check=True,
        capture_output=True,
    )

    narration = "夏天上班想穿得清爽又有气质，看这一套。这件浅蓝色上衣，圆领短袖很干净，腰线这里做了收身剪裁，穿上不会显得松垮。下面搭白色直筒长裤，视觉上更利落，也更显腿直。浅蓝配白色，整套看起来很清爽，通勤、见客户、日常约会都能穿。喜欢这种不用费力就显气质的搭配，点橱窗或者直播间看同款。"
    wav = VIDEO / "narration.wav"
    final = VIDEO / "blue-white-digital-human-preview.mp4"
    if synth_voice(narration, wav):
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


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    VIDEO.mkdir(parents=True, exist_ok=True)
    black = cutout(SRC_BLACK)
    blue = cutout(SRC_BLUE)
    pants = cutout(SRC_PANTS)

    save_card(
        "01_blue_white_main.png",
        "蓝衣白裤通勤套装",
        "清爽浅蓝 + 利落白裤，上班不沉闷",
        [(blue, (92, 370), (455, 470)), (pants, (500, 330), (440, 840))],
        ["浅蓝上衣提亮气色", "白色直筒裤修饰腿型", "通勤 / 见客户 / 日常都适合"],
    )
    save_card(
        "02_blue_top_detail.png",
        "浅蓝上衣细节",
        "圆领短袖，腰线剪裁更显利落",
        [(blue, (205, 360), (670, 720))],
        ["清爽浅蓝色，不挑日常场景", "圆领短袖，干净耐看", "腰线剪裁，避免松垮"],
    )
    save_card(
        "03_white_pants_detail.png",
        "白色长裤细节",
        "直筒线条，搭浅蓝上衣更干净",
        [(pants, (295, 285), (520, 930))],
        ["白色视觉清爽", "直筒裤型更利落", "搭配浅蓝上衣显气质"],
    )
    save_card(
        "04_commute_scene.png",
        "一套解决通勤穿搭",
        "上班、见客户、日常约会都能穿",
        [(blue, (75, 430), (420, 460)), (pants, (515, 370), (430, 820))],
        ["不用费力搭配", "清爽但不随意", "镜头里干净显气质"],
        palette="#dbe8d4",
    )
    save_card(
        "05_cta.png",
        "喜欢这套，点橱窗看同款",
        "直播间 / 橱窗有活动，按需替换价格信息",
        [(blue, (105, 420), (395, 420)), (pants, (542, 360), (395, 780))],
        ["蓝衣白裤套装", "30 秒数字人口播", "不写未确认价格，方便后续复用"],
        palette="#eadbc7",
    )
    save_card(
        "06_black_dress_main.png",
        "黑色气质套裙主图",
        "V 领短袖 + 半裙线条，稳重显瘦",
        [(black, (205, 260), (670, 1010))],
        ["黑色更显稳重", "V 领拉长颈部线条", "适合成熟通勤场景"],
        palette="#d6d7db",
    )
    save_card(
        "07_black_dress_detail.png",
        "黑色套裙详情图",
        "袖口轻透、腰侧点缀、裙摆层次",
        [(black, (250, 330), (590, 900))],
        ["轻透袖口，减少沉闷感", "腰侧珍珠点缀增加精致感", "下摆层次更有气质"],
        palette="#d6d7db",
    )
    write_text_files()
    write_preview_html()
    render_video()
    print(OUT)


if __name__ == "__main__":
    main()
