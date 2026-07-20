from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "运营计划" / "今日交付包"
PDF_DIR = ROOT / "output" / "pdf"
TMP_DIR = ROOT / "tmp" / "pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

PDF_PATH = OUT_DIR / "AI电商商品图生成与AI客服SaaS项目整理.pdf"
MIRROR_PATH = PDF_DIR / PDF_PATH.name
PREVIEW_PATH = TMP_DIR / "AI电商项目整理_第1页预览.png"


def register_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf"),
    ]
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if not regular or not bold:
        raise RuntimeError("没有找到可用中文字体。")
    pdfmetrics.registerFont(TTFont("CN", str(regular)))
    pdfmetrics.registerFont(TTFont("CNBold", str(bold)))
    return "CN", "CNBold"


FONT, FONT_BOLD = register_fonts()

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        fontName=FONT_BOLD,
        fontSize=25,
        leading=34,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub",
        fontName=FONT,
        fontSize=11.5,
        leading=18,
        textColor=colors.HexColor("#dbeafe"),
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        name="H1CN",
        fontName=FONT_BOLD,
        fontSize=16,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceBefore=8,
        spaceAfter=9,
    )
)
styles.add(
    ParagraphStyle(
        name="H2CN",
        fontName=FONT_BOLD,
        fontSize=11.5,
        leading=17,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=4,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyCN",
        fontName=FONT,
        fontSize=9.2,
        leading=14.5,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="SmallCN",
        fontName=FONT,
        fontSize=7.8,
        leading=11.5,
        textColor=colors.HexColor("#4b5563"),
    )
)


def p(text: str, style: str = "BodyCN") -> Paragraph:
    escaped = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(escaped, styles[style])


def section(title: str) -> Paragraph:
    return p(title, "H1CN")


def bullets(items: list[str]) -> Table:
    table = Table([[p("•"), p(item)] for item in items], colWidths=[6 * mm, 169 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return table


def kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table([[p(k, "H2CN"), p(v)] for k, v in rows], colWidths=[42 * mm, 133 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#bfdbfe")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbeafe")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(18 * mm, 10 * mm, "AI电商商品图生成与AI客服SaaS项目整理")
    canvas.drawRightString(192 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build_story() -> list:
    story: list = []

    cover = Table(
        [
            [p("AI电商商品图生成与AI客服SaaS项目整理", "CoverTitle")],
            [p("当前进度、使用方法、部署状态、测试结果、销售包装与下一步路线", "CoverSub")],
            [p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 交付目录：运营计划/今日交付包", "CoverSub")],
        ],
        colWidths=[176 * mm],
    )
    cover.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#08111f")),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (0, 0), 42),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.append(cover)
    story.append(Spacer(1, 8 * mm))
    story.append(
        kv_table(
            [
                ("主产品", "AI商品图生成抖音小程序 + AI客服SaaS后台"),
                ("产品定位", "给电商商家生成主图提示词、详情页结构、商品标题、SKU草稿、客服FAQ，并沉淀到AI客服和线索承接。"),
                ("线上后台", "https://wjhai.cn/merchant-admin/"),
                ("小程序目录", str(ROOT / "douyin-miniapp")),
                ("交付包", str(OUT_DIR / "AI商品图生成抖音小程序.zip")),
                ("安全说明", "本PDF不记录服务器SSH密码、API Key、平台账号密码。对外出售前必须更换演示账号密码。"),
            ]
        )
    )
    story.append(PageBreak())

    story.append(section("1. 当前已经完成"))
    story.append(
        bullets(
            [
                "AI客服SaaS后台已部署到 wjhai.cn/merchant-admin，可登录查看总览、知识库、会话、渠道、网页气泡和桌面辅助入口。",
                "桌面客服辅助脚本已支持微信、企业微信、抖音、淘宝/千牛、拼多多、闲鱼的“识别窗口 + 生成候选回复”路线。默认不自动发送，避免误发和平台风控。",
                "抖音小程序主流程已改成“AI商品图自动生成”：填写商品资料后生成标题、主图/详情图提示词、SKU、FAQ和上架草稿。",
                "后端新增 POST /api/ecommerce/listing-draft，线上接口已测试返回 200。",
                "结果页新增“生成真实主图”按钮，会请求 /api/images/generate；图片模型未配置时返回提示词，不假装出图。",
                "已经生成一批电商自动化宣传图，可用于抖音封面、朋友圈、闲鱼服务商品图和销售页素材。",
            ]
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        kv_table(
            [
                ("后台演示账号", "ai_kefu_demo / admin123（对外销售前请改密码）"),
                ("线上接口", "https://wjhai.cn/merchant-admin/api"),
                ("新增核心接口", "POST /ecommerce/listing-draft；POST /images/generate"),
                ("小程序交付包", str(OUT_DIR / "AI商品图生成抖音小程序.zip")),
            ]
        )
    )

    story.append(section("2. AI商品图小程序怎么使用"))
    story.append(
        bullets(
            [
                f"打开抖音开发者工具，导入目录：{ROOT / 'douyin-miniapp'}。",
                "在首页选择样例：美妆精华、电商零食、手机壳，或手动填写商品名、类目、平台、价格、SKU、卖点、目标客户、库存、发货、售后。",
                "点击“立即生成图片和上架草稿”。",
                "结果页查看商品标题草稿、主图提示词、详情页结构、SKU表、客服FAQ、风险检查。",
                "点击“复制整套上架资料”，可发给运营、美工，或粘贴到抖店/淘宝/拼多多后台草稿中。",
                "点击“生成真实主图”，如果服务器图片模型配置完成，会返回图片；未配置时保留提示词。",
            ]
        )
    )
    story.append(PageBreak())

    story.append(section("3. AI客服SaaS怎么使用"))
    story.append(
        bullets(
            [
                "打开 https://wjhai.cn/merchant-admin/，使用演示账号登录。",
                "进入商家资料/知识库，导入商家介绍、产品服务、价格、优惠、营业时间、联系方式、FAQ和售后政策。",
                "进入客服脚本，按渠道和场景生成开场、报价、异议处理、收口留资话术。",
                "进入网页气泡，复制 script 嵌入客户网站，即可做自有网页客服自动回复。",
                "进入桌面自动客服，在本机运行脚本，打开真实聊天窗口后生成候选回复。",
                "后台会话收件箱可查看真实访客消息、AI回复、意向分和人工接管标记。",
            ]
        )
    )

    story.append(section("4. 服务器和部署状态"))
    story.append(
        kv_table(
            [
                ("域名", "https://wjhai.cn/merchant-admin/"),
                ("后端服务", "uvicorn backend.main:app --host 127.0.0.1 --port 8004"),
                ("部署目录", "/opt/merchant-growth-canvas"),
                ("数据库/数据目录", "/opt/merchant-growth-canvas/data"),
                ("Nginx代理", "https://wjhai.cn/merchant-admin/ -> 127.0.0.1:8004"),
                ("安全", "公网禁止触发 /api/local-scripts，本机脚本只能在 127.0.0.1 环境执行。"),
            ]
        )
    )

    story.append(section("5. 已测试项目"))
    story.append(
        bullets(
            [
                "python -m py_compile backend/main.py：通过。",
                "python scripts/validate_miniapp.py：通过。",
                "node --check douyin-miniapp/utils/api.js、pages/index/index.js、pages/result/result.js：通过。",
                "线上 POST https://wjhai.cn/merchant-admin/api/ecommerce/listing-draft：返回 200。",
                "线上后台此前已验证：登录接口、dashboard overview、渠道列表、静态资源和首页均可访问。",
            ]
        )
    )
    story.append(PageBreak())

    story.append(section("6. 电商图片成果和卖点"))
    story.append(
        bullets(
            [
                "卖点不要只说“生成图片”，要说“上传商品资料后，生成主图、详情图、标题、SKU、FAQ和上架草稿”。",
                "第一版最适合卖给闲鱼、淘宝、拼多多、抖音小店商家，主打省美工、省运营、批量上新、快速测品。",
                "对客户承诺边界：先生成草稿和素材，最终发布、价格、库存、售后由商家确认。",
                "可用宣传图主题：AI商品图自动生成、详情页自动排版、多平台一键上架、爆款素材批量生成、从图片到商品上架。",
            ]
        )
    )

    story.append(section("7. 可以马上卖的产品包装"))
    story.append(
        kv_table(
            [
                ("99-299元", "单品AI上架资料包：标题、卖点、主图提示词、详情页结构、客服FAQ。"),
                ("399-999元", "10个商品批量上新草稿包：适合闲鱼/拼多多/抖店小商家。"),
                ("999-2999元", "商家AI客服 + 商品上架草稿系统部署：含后台、知识库、网页气泡、培训。"),
                ("2999-9999元", "私有化部署/代理商版本：部署到客户服务器，改品牌、改模板、培训使用。"),
            ]
        )
    )

    story.append(section("8. 闲鱼/抖音获客话术"))
    story.append(
        bullets(
            [
                "闲鱼标题：AI商品图生成系统部署｜主图详情图标题SKU一键生成｜适合抖店淘宝拼多多。",
                "短视频选题：老板发一个商品，AI自动生成主图、详情图和上架资料。",
                "短视频选题：不会做电商图？我做了一个能生成上架草稿的小程序。",
                "私信承接：你发商品名、价格、卖点和平台，我先免费给你生成一版上架草稿，看能不能用。",
            ]
        )
    )
    story.append(PageBreak())

    story.append(section("9. 当前未覆盖和风险"))
    story.append(
        bullets(
            [
                "真实图片生成依赖 IMAGE_API_KEY / IMAGE_BASE_URL / IMAGE_MODEL 等服务器配置；未配置时只能返回提示词。",
                "小程序还没有做真实商品图片上传到对象存储，当前以填写商品资料为主。",
                "还没有接抖音小店官方商品发布API；自动发布必须拿到官方权限后再做。",
                "桌面自动客服目前是辅助生成候选回复，不建议做未经授权的全自动发送。",
                "根项目Git状态较乱，很多文件未跟踪；公开到GitHub前必须清理密钥、整理README、补LICENSE和.env.example。",
                "对外销售前必须更换演示账号密码，不要把服务器密码、API Key、客户资料放进交付包。",
            ]
        )
    )

    story.append(section("10. 下一步建议"))
    story.append(
        bullets(
            [
                "第一优先：配置图片模型，让“生成真实主图”真正返回图片文件。",
                "第二优先：小程序加图片选择和上传，商品图可以传到服务器对象存储。",
                "第三优先：做商品历史库，让每个商家能保存自己的商品草稿。",
                "第四优先：补用户协议、隐私政策、类目说明，提交抖音小程序体验版。",
                "第五优先：做一个对外演示页，把“AI客服 + 商品图生成 + 上架草稿”包装成可订阅SaaS。",
            ]
        )
    )

    story.append(section("11. 文件位置"))
    story.append(
        kv_table(
            [
                ("小程序源码", str(ROOT / "douyin-miniapp")),
                ("小程序说明", str(ROOT / "douyin-miniapp" / "README.md")),
                ("小程序交付包", str(OUT_DIR / "AI商品图生成抖音小程序.zip")),
                ("本PDF", str(PDF_PATH)),
                ("镜像PDF", str(MIRROR_PATH)),
            ]
        )
    )
    return story


def render_first_page() -> None:
    pdf = pdfium.PdfDocument(str(PDF_PATH))
    page = pdf[0]
    bitmap = page.render(scale=1.5).to_pil()
    bitmap.save(PREVIEW_PATH)
    pdf.close()


def validate_pdf() -> None:
    reader = PdfReader(str(PDF_PATH))
    text_sample = "\n".join((page.extract_text() or "") for page in reader.pages[:2])
    required = ["AI电商商品图生成", "AI客服SaaS", "wjhai.cn", "douyin-miniapp"]
    missing = [item for item in required if item not in text_sample]
    if missing:
        raise RuntimeError(f"PDF文本校验缺失：{missing}")
    if len(reader.pages) < 5:
        raise RuntimeError("PDF页数异常。")


def main() -> None:
    if PDF_PATH.exists():
        PDF_PATH.unlink()
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="AI电商商品图生成与AI客服SaaS项目整理",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    shutil.copyfile(PDF_PATH, MIRROR_PATH)
    validate_pdf()
    render_first_page()
    reader = PdfReader(str(PDF_PATH))
    print(PDF_PATH)
    print(MIRROR_PATH)
    print(PREVIEW_PATH)
    print(f"pages={len(reader.pages)}")


if __name__ == "__main__":
    main()
