from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "product-main-detail-20260711"

SRC_BLACK = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\1a08602c399ad98bf4469c5b59b80c35.jpg")
SRC_BLUE = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\eab45fb8ee534a6e04208cc735cbcfd6.jpg")
SRC_PANTS = Path(r"D:\xwechat_files\wxid_x74btth050jk22_cf27\temp\RWTemp\2026-07\e47af3e8168f02efc7393a48458ca1cd\3a7dbb7e430ed2611e8765e5b5de2bdd.jpg")

FONT_REG = r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"
FONT_MED = r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
FONT_BOLD = r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = {"regular": FONT_REG, "medium": FONT_MED, "bold": FONT_BOLD}[weight]
    return ImageFont.truetype(path, size=size)


def cutout(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    data = []
    for r, g, b, a in img.getdata():
        if r > 244 and g > 244 and b > 244:
            data.append((255, 255, 255, 0))
        elif r > 235 and g > 235 and b > 235:
            data.append((r, g, b, int(a * 0.35)))
        else:
            data.append((r, g, b, a))
    img.putdata(data)
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def resize_fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    out = img.copy()
    out.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return out


def soft_shadow(base: Image.Image, item: Image.Image, pos: tuple[int, int], blur: int = 26, alpha: int = 70):
    shadow = Image.new("RGBA", item.size, (0, 0, 0, 0))
    mask = item.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    shadow.putalpha(mask.point(lambda p: min(alpha, p)))
    base.alpha_composite(shadow, (pos[0] + 14, pos[1] + 20))
    base.alpha_composite(item, pos)


def gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = color
    return img.convert("RGBA")


def draw_text(draw: ImageDraw.ImageDraw, xy, value: str, size: int, fill: str, weight: str = "regular", anchor=None):
    draw.text(xy, value, font=font(size, weight), fill=fill, anchor=anchor)


def rounded(draw: ImageDraw.ImageDraw, xy, r: int, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, fill="#f4fbfc", text_fill="#315d72", outline="#d6e7eb"):
    f = font(26, "medium")
    box = draw.textbbox((0, 0), value, font=f)
    w = box[2] - box[0] + 34
    h = 50
    rounded(draw, (x, y, x + w, y + h), 25, fill, outline)
    draw.text((x + 17, y + 9), value, font=f, fill=text_fill)
    return x + w + 12


def source_crop(path: Path, box: tuple[int, int, int, int], size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB").crop(box)
    img = img.resize(size, Image.Resampling.LANCZOS)
    return img.convert("RGBA")


def paste_card(base: Image.Image, img: Image.Image, box: tuple[int, int, int, int], label: str, note: str):
    d = ImageDraw.Draw(base)
    x1, y1, x2, y2 = box
    rounded(d, box, 32, "#ffffff", "#d9e5e7", 2)
    inner = img.copy()
    mask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, inner.width, inner.height), 24, fill=255)
    clipped = Image.new("RGBA", inner.size, (255, 255, 255, 0))
    clipped.alpha_composite(inner)
    clipped.putalpha(mask)
    base.alpha_composite(clipped, (x1 + 18, y1 + 18))
    draw_text(d, (x1 + 28, y2 - 98), label, 34, "#18252c", "bold")
    draw_text(d, (x1 + 28, y2 - 52), note, 24, "#607079", "medium")


def blue_white_main(blue: Image.Image, pants: Image.Image):
    canvas = gradient((1080, 1080), (250, 253, 253), (236, 244, 245))
    d = ImageDraw.Draw(canvas)
    d.ellipse((-170, 650, 480, 1210), fill="#d9edf280")
    d.ellipse((760, -180, 1240, 360), fill="#efdfc980")
    draw_text(d, (76, 72), "蓝衣白裤通勤套装", 54, "#18252c", "bold")
    draw_text(d, (78, 140), "清爽浅蓝 + 利落白裤", 30, "#607079", "medium")
    x = 78
    for label in ["上班通勤", "干净显气质", "套装搭配"]:
        x = pill(d, x, 188, label)

    top = resize_fit(blue, 470, 430)
    trouser = resize_fit(pants, 470, 720)
    soft_shadow(canvas, top, (126, 362), 18, 58)
    soft_shadow(canvas, trouser, (574, 290), 20, 58)

    rounded(d, (74, 914, 1006, 1018), 30, "#ffffffd8", "#dae8ea", 2)
    draw_text(d, (112, 938), "一套解决夏季通勤穿搭", 34, "#1f3138", "bold")
    draw_text(d, (112, 982), "不写价格信息，适合后续直播间/橱窗复用", 22, "#6a7a82", "medium")
    canvas.convert("RGB").save(OUT / "01_蓝衣白裤_主图.png", quality=96)


def blue_white_detail():
    canvas = gradient((1080, 1440), (249, 253, 253), (235, 244, 246))
    d = ImageDraw.Draw(canvas)
    draw_text(d, (70, 62), "蓝衣白裤 · 详情卖点", 56, "#18252c", "bold")
    draw_text(d, (74, 134), "用原商品图做细节拆解，信息更清楚", 28, "#61717a", "medium")

    crops = [
        (source_crop(SRC_BLUE, (130, 45, 675, 325), (440, 300)), (70, 220, 530, 610), "圆领短袖", "简洁领口，日常好搭"),
        (source_crop(SRC_BLUE, (110, 300, 710, 690), (440, 300)), (550, 220, 1010, 610), "腰线剪裁", "线条向内收，版型利落"),
        (source_crop(SRC_PANTS, (105, 30, 690, 290), (440, 300)), (70, 660, 530, 1050), "腰头细节", "腰部装饰，视觉更完整"),
        (source_crop(SRC_PANTS, (150, 255, 650, 760), (440, 300)), (550, 660, 1010, 1050), "直筒裤型", "纵向线条，搭配更清爽"),
    ]
    for img, box, label, note in crops:
        paste_card(canvas, img, box, label, note)

    rounded(d, (70, 1132, 1010, 1342), 34, "#17252ce8")
    draw_text(d, (112, 1174), "推荐话术", 34, "#ffffff", "bold")
    draw_text(d, (112, 1226), "浅蓝上衣提亮气色，白色直筒裤让整体更干净，通勤、见客户、日常约会都能穿。", 30, "#eef8fa", "medium")
    canvas.convert("RGB").save(OUT / "02_蓝衣白裤_详情图.png", quality=96)


def black_main(black: Image.Image):
    canvas = gradient((1080, 1080), (250, 250, 250), (237, 238, 240))
    d = ImageDraw.Draw(canvas)
    d.ellipse((-160, 620, 480, 1210), fill="#dedfe480")
    d.ellipse((760, -160, 1240, 340), fill="#eee0d280")
    draw_text(d, (76, 72), "黑色气质套裙", 58, "#18191b", "bold")
    draw_text(d, (78, 146), "V 领短袖 · 腰侧点缀 · 半裙层次", 30, "#60636a", "medium")
    x = 78
    for label in ["成熟通勤", "稳重显气质", "套裙单品"]:
        x = pill(d, x, 194, label, "#ffffff", "#34373d", "#dedfe4")
    dress = resize_fit(black, 620, 720)
    soft_shadow(canvas, dress, ((1080 - dress.width) // 2, 270), 22, 72)
    rounded(d, (86, 916, 994, 1018), 30, "#ffffffe0", "#dedfe4", 2)
    draw_text(d, (124, 941), "适合成熟通勤、门店展示、直播间封面", 32, "#202226", "bold")
    draw_text(d, (124, 982), "基于原商品图重排，不编造价格/材质", 22, "#6a6d73", "medium")
    canvas.convert("RGB").save(OUT / "03_黑色套裙_主图.png", quality=96)


def black_detail():
    canvas = gradient((1080, 1440), (250, 250, 250), (237, 238, 240))
    d = ImageDraw.Draw(canvas)
    draw_text(d, (70, 62), "黑色套裙 · 详情卖点", 56, "#18191b", "bold")
    draw_text(d, (74, 134), "突出领口、袖口、腰侧点缀和裙摆层次", 28, "#62656b", "medium")
    crops = [
        (source_crop(SRC_BLACK, (390, 80, 850, 360), (440, 300)), (70, 220, 530, 610), "V 领设计", "拉开颈部留白，视觉更轻盈"),
        (source_crop(SRC_BLACK, (305, 150, 960, 505), (440, 300)), (550, 220, 1010, 610), "轻透袖口", "黑色不沉闷，层次更明显"),
        (source_crop(SRC_BLACK, (520, 430, 850, 705), (440, 300)), (70, 660, 530, 1050), "腰侧点缀", "小面积亮点，增加精致感"),
        (source_crop(SRC_BLACK, (360, 820, 910, 1210), (440, 300)), (550, 660, 1010, 1050), "裙摆层次", "下摆轻透，走动更有线条"),
    ]
    for img, box, label, note in crops:
        paste_card(canvas, img, box, label, note)

    rounded(d, (70, 1132, 1010, 1342), 34, "#17181ce8")
    draw_text(d, (112, 1174), "推荐话术", 34, "#ffffff", "bold")
    draw_text(d, (112, 1226), "黑色套裙稳重耐看，V 领和轻透袖口减少沉闷感，腰侧点缀让整体更精致。", 30, "#f5f5f5", "medium")
    canvas.convert("RGB").save(OUT / "04_黑色套裙_详情图.png", quality=96)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    blue = cutout(SRC_BLUE)
    pants = cutout(SRC_PANTS)
    black = cutout(SRC_BLACK)
    blue_white_main(blue, pants)
    blue_white_detail()
    black_main(black)
    black_detail()
    print(OUT)


if __name__ == "__main__":
    main()
