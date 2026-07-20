from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\bcda05138fbdcb6f124702627776b16d\4920a88853b61abb329eb3a6267dbb8c.jpg")
OUT = ROOT / "output" / "exact-floral-dress-20260712"

FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
    return ImageFont.truetype(path, size=size)


def enhance(img: Image.Image) -> Image.Image:
    # Conservative corrections only. No redraw, no changed garment pixels beyond global photo tuning.
    img = ImageEnhance.Brightness(img).enhance(1.04)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Sharpness(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.03)
    return img


def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill: str, weight: str = "regular", anchor=None):
    draw.text(xy, text, font=font(size, weight), fill=fill, anchor=anchor)


def wrap_text(text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines, current = [], ""
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


def blur_bg_card(source: Image.Image, crop_box: tuple[int, int, int, int], canvas_size: tuple[int, int]) -> Image.Image:
    crop = source.crop(crop_box)
    bg = crop.resize(canvas_size, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(18))
    overlay = Image.new("RGBA", canvas_size, (246, 244, 240, 188))
    return Image.alpha_composite(bg.convert("RGBA"), overlay)


def paste_cover(base: Image.Image, img: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    scale = max(bw / img.width, bh / img.height)
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    cx = (resized.width - bw) // 2
    cy = (resized.height - bh) // 2
    crop = resized.crop((cx, cy, cx + bw, cy + bh))
    base.alpha_composite(crop.convert("RGBA"), (x1, y1))


def save_exact_enhanced(source: Image.Image):
    img = enhance(source)
    # Normalize to 1080x1920 without stretching by adding a 1px soft edge.
    canvas = Image.new("RGB", (1080, 1920), (242, 240, 236))
    canvas.paste(img, (0, 0))
    canvas.save(OUT / "01_原图保真增强版.png", quality=96)


def save_main(source: Image.Image):
    img = enhance(source)
    canvas = blur_bg_card(img, (35, 0, 970, 1919), (1080, 1920))
    d = ImageDraw.Draw(canvas)

    # Keep the full garment from the original photo. Background is softened, garment pixels stay from source crop.
    garment = img.crop((70, 0, 930, 1919)).resize((860, 1919), Image.Resampling.LANCZOS).convert("RGBA")
    shadow = Image.new("RGBA", garment.size, (0, 0, 0, 0))
    mask = garment.convert("L").filter(ImageFilter.GaussianBlur(24))
    shadow.putalpha(mask.point(lambda p: 46 if p > 18 else 0))
    canvas.alpha_composite(shadow, (125, 22))
    canvas.alpha_composite(garment, (110, 0))

    rounded_rect(d, (54, 62, 1026, 192), 36, (255, 255, 255, 226), (222, 218, 211, 255), 2)
    draw_text(d, (92, 88), "花纹连衣裙 · 原图保真主图", 42, "#262321", "bold")
    draw_text(d, (94, 142), "不重绘衣服，花纹和版型来自原始照片", 26, "#665f59", "medium")

    rounded_rect(d, (70, 1708, 1010, 1842), 34, (30, 28, 27, 216))
    draw_text(d, (112, 1734), "真实商品图精修", 36, "#ffffff", "bold")
    draw_text(d, (112, 1782), "轻透短袖 / 满版花纹 / 侧系带细节", 28, "#f0ebe5", "medium")
    canvas.convert("RGB").save(OUT / "02_花纹连衣裙_保真主图.png", quality=96)


def detail_card(canvas: Image.Image, source: Image.Image, box, crop_box, title: str, note: str):
    d = ImageDraw.Draw(canvas)
    rounded_rect(d, box, 30, (255, 255, 255, 236), (220, 217, 211, 255), 2)
    x1, y1, x2, y2 = box
    visual_box = (x1 + 18, y1 + 18, x2 - 18, y1 + 338)
    paste_cover(canvas, source.crop(crop_box).convert("RGBA"), visual_box)
    # Soft top border over the raw photo crop.
    d.rounded_rectangle(visual_box, radius=22, outline=(230, 226, 220, 255), width=2)
    draw_text(d, (x1 + 28, y2 - 104), title, 32, "#25221f", "bold")
    draw_text(d, (x1 + 28, y2 - 58), note, 24, "#69615a", "medium")


def save_detail(source: Image.Image):
    img = enhance(source)
    canvas = Image.new("RGBA", (1080, 1440), (246, 244, 240, 255))
    d = ImageDraw.Draw(canvas)
    d.ellipse((-210, 980, 460, 1580), fill=(226, 218, 208, 105))
    d.ellipse((780, -180, 1260, 330), fill=(230, 235, 232, 130))
    draw_text(d, (70, 58), "花纹连衣裙 · 保真详情", 52, "#262321", "bold")
    draw_text(d, (74, 126), "详情图全部截取原图，不改衣服花纹", 28, "#6a625c", "medium")

    detail_card(canvas, img, (70, 210, 520, 610), (280, 40, 775, 420), "圆领与肩部", "领口、肩线和花纹保持原样")
    detail_card(canvas, img, (560, 210, 1010, 610), (70, 170, 330, 530), "轻透短袖", "袖部透感来自原始照片")
    detail_card(canvas, img, (70, 660, 520, 1060), (585, 520, 900, 1030), "侧系带细节", "右侧系带和裙身层次保留")
    detail_card(canvas, img, (560, 660, 1010, 1060), (215, 360, 760, 1030), "满版花纹", "白灰花线纹理不重绘")

    rounded_rect(d, (70, 1152, 1010, 1334), 34, (34, 31, 29, 230))
    draw_text(d, (112, 1184), "可用于：商品详情页 / 短视频卖点页", 34, "#ffffff", "bold")
    f = font(28, "medium")
    y = 1234
    for line in wrap_text("说明：为了严格一致，本图没有把衣服重新生成到模特身上，只做原图保真裁切和排版。", f, 820):
        d.text((112, y), line, font=f, fill="#f2ece4")
        y += 40
    canvas.convert("RGB").save(OUT / "03_花纹连衣裙_保真详情图.png", quality=96)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SRC).convert("RGB")
    save_exact_enhanced(source)
    save_main(source)
    save_detail(source)
    print(OUT)


if __name__ == "__main__":
    main()
