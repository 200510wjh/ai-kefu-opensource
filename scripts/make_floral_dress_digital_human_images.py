from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "output" / "exact-floral-dress-20260712"
PRESENTER = ROOT / "output" / "floral-dress-digital-human-20260712" / "digital-human-presenter.png"
OUT = ROOT / "output" / "floral-dress-digital-human-images-20260713"

W, H = 1080, 1920
FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
    return ImageFont.truetype(path, size=size)


def bg() -> Image.Image:
    img = Image.new("RGB", (W, H), "#f7f4ee")
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.25 + (y / H) * 0.75
            r = int(249 * (1 - t) + 228 * t)
            g = int(247 * (1 - t) + 224 * t)
            b = int(242 * (1 - t) + 219 * t)
            px[x, y] = (r, g, b)
    return img.convert("RGBA")


def cover(img: Image.Image, size: tuple[int, int], zoom: float = 1.0, pan_y: float = 0.5) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height) * zoom
    resized = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    x = max(0, (resized.width - w) // 2)
    y = int(max(0, resized.height - h) * pan_y)
    return resized.crop((x, y, x + w, y + h))


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy, value: str, size: int, fill: str, weight: str = "regular"):
    draw.text(xy, value, font=font(size, weight), fill=fill)


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


def paste_presenter(canvas: Image.Image, presenter: Image.Image, box: tuple[int, int, int, int]):
    x1, y1, x2, y2 = box
    card_w, card_h = x2 - x1, y2 - y1
    d = ImageDraw.Draw(canvas)
    rounded(d, box, 42, (255, 255, 255, 222), (222, 216, 208, 255), 2)
    cropped = cover(presenter, (card_w - 24, card_h - 24), 1.04, 0.18)
    mask = Image.new("L", cropped.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cropped.width, cropped.height), radius=34, fill=255)
    cropped.putalpha(mask)
    canvas.alpha_composite(cropped, (x1 + 12, y1 + 12))


def product_card(canvas: Image.Image, product: Image.Image, box: tuple[int, int, int, int], pan_y: float = 0.47):
    x1, y1, x2, y2 = box
    d = ImageDraw.Draw(canvas)
    shadow = Image.new("RGBA", (x2 - x1, y2 - y1), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((0, 0, shadow.width, shadow.height), 44, fill=(0, 0, 0, 42))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    canvas.alpha_composite(shadow, (x1 + 10, y1 + 22))
    rounded(d, box, 44, (255, 255, 255, 236), (222, 216, 208, 255), 2)
    cropped = cover(product, (x2 - x1 - 28, y2 - y1 - 28), 1.01, pan_y)
    mask = Image.new("L", cropped.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cropped.width, cropped.height), 34, fill=255)
    cropped.putalpha(mask)
    canvas.alpha_composite(cropped, (x1 + 14, y1 + 14))


def badge(draw: ImageDraw.ImageDraw, x: int, y: int, value: str):
    f = font(27, "bold")
    w = draw.textbbox((0, 0), value, font=f)[2] + 44
    rounded(draw, (x, y, x + w, y + 56), 28, (255, 255, 255, 226), (224, 216, 207, 255), 2)
    draw.text((x + 22, y + 11), value, font=f, fill="#423a35")
    return x + w + 12


def hero_image(product: Image.Image, presenter: Image.Image):
    canvas = bg()
    d = ImageDraw.Draw(canvas)
    d.ellipse((-260, 1240, 500, 2050), fill=(215, 202, 188, 92))
    d.ellipse((760, -180, 1260, 380), fill=(226, 232, 228, 124))

    rounded(d, (56, 56, 1024, 184), 38, (255, 255, 255, 228), (224, 218, 210, 255), 2)
    text(d, (96, 82), "数字人讲解 · 花纹连衣裙", 43, "#29231f", "bold")
    text(d, (98, 136), "衣服保真：花纹和版型来自原图", 26, "#6a625c", "medium")

    product_card(canvas, product, (414, 210, 1022, 1398), 0.46)
    paste_presenter(canvas, presenter, (58, 522, 398, 1168))

    x = 70
    for item in ["原图保真", "满版花纹", "轻透短袖"]:
        x = badge(d, x, 1288, item)

    rounded(d, (58, 1464, 1022, 1728), 38, (31, 28, 26, 232))
    d.rectangle((96, 1500, 106, 1690), fill="#e8d7c6")
    text(d, (132, 1502), "这条花裙不重绘衣服", 48, "#ffffff", "bold")
    f = font(31, "medium")
    y = 1570
    for line in wrap("商品主体直接使用原照片，保留深色底、白灰花线、轻透袖和右侧系带。", f, 820):
        d.text((132, y), line, font=f, fill="#f4ede5")
        y += 42
    canvas.convert("RGB").save(OUT / "01_数字人花裙带货主图_保真.png", quality=96)


def detail_image(detail: Image.Image, presenter: Image.Image):
    canvas = bg()
    d = ImageDraw.Draw(canvas)
    d.ellipse((-220, 1120, 480, 2020), fill=(215, 202, 188, 86))
    text(d, (72, 68), "数字人讲解详情图", 52, "#29231f", "bold")
    text(d, (76, 138), "细节全部来自原图裁切，不改变衣服花纹", 28, "#6a625c", "medium")

    product_card(canvas, detail, (72, 218, 1008, 1228), 0.45)
    paste_presenter(canvas, presenter, (728, 982, 1018, 1398))

    x = 82
    for item in ["圆领肩线", "轻透袖", "侧系带", "满版花纹"]:
        x = badge(d, x, 1276, item)

    rounded(d, (64, 1484, 1016, 1742), 38, (31, 28, 26, 232))
    text(d, (104, 1524), "适合先发客户确认", 44, "#ffffff", "bold")
    f = font(30, "medium")
    y = 1588
    for line in wrap("这版不是重新生成试穿图，所以衣服不会跑样；后续如果要真人试穿，需接受花纹可能无法百分百一致。", f, 820):
        d.text((104, y), line, font=f, fill="#f4ede5")
        y += 42
    canvas.convert("RGB").save(OUT / "02_数字人花裙详情讲解图_保真.png", quality=96)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    product = Image.open(PRODUCT_DIR / "02_花纹连衣裙_保真主图.png").convert("RGBA")
    detail = Image.open(PRODUCT_DIR / "03_花纹连衣裙_保真详情图.png").convert("RGBA")
    presenter = Image.open(PRESENTER).convert("RGBA")
    presenter = ImageEnhance.Sharpness(presenter).enhance(1.08)
    hero_image(product, presenter)
    detail_image(detail, presenter)
    print(OUT)


if __name__ == "__main__":
    main()
