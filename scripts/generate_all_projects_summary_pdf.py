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
for directory in (OUT_DIR, PDF_DIR, TMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)

PDF_PATH = OUT_DIR / "本次对话全部项目总整理.pdf"
MIRROR_PATH = PDF_DIR / PDF_PATH.name
PREVIEW_PATH = TMP_DIR / "本次对话全部项目总整理_第1页预览.png"
ALL_PREVIEW_PATH = TMP_DIR / "本次对话全部项目总整理_全部页面预览.png"


def register_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    regular = next((item for item in regular_candidates if item.exists()), None)
    bold = next((item for item in bold_candidates if item.exists()), None)
    if not regular or not bold:
        raise RuntimeError("没有找到可用中文字体。")
    pdfmetrics.registerFont(TTFont("CN", str(regular)))
    pdfmetrics.registerFont(TTFont("CNBold", str(bold)))
    return "CN", "CNBold"


FONT, FONT_BOLD = register_fonts()
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", fontName=FONT_BOLD, fontSize=24, leading=32, textColor=colors.white, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="CoverSub", fontName=FONT, fontSize=11.5, leading=18, textColor=colors.HexColor("#dbeafe"), alignment=TA_CENTER))
styles.add(ParagraphStyle(name="H1CN", fontName=FONT_BOLD, fontSize=15.5, leading=22, textColor=colors.HexColor("#111827"), spaceBefore=8, spaceAfter=8))
styles.add(ParagraphStyle(name="H2CN", fontName=FONT_BOLD, fontSize=10.8, leading=16, textColor=colors.HexColor("#1d4ed8"), spaceAfter=3))
styles.add(ParagraphStyle(name="BodyCN", fontName=FONT, fontSize=8.7, leading=13.8, textColor=colors.HexColor("#1f2937"), spaceAfter=2))
styles.add(ParagraphStyle(name="SmallCN", fontName=FONT, fontSize=7.6, leading=11.2, textColor=colors.HexColor("#4b5563")))
styles.add(ParagraphStyle(name="WarnCN", fontName=FONT_BOLD, fontSize=8.7, leading=13.8, textColor=colors.HexColor("#b45309"), spaceAfter=2))


def p(text: object, style: str = "BodyCN") -> Paragraph:
    value = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(value, styles[style])


def section(title: str) -> Paragraph:
    return p(title, "H1CN")


def bullets(items: list[str]) -> Table:
    table = Table([[p("•"), p(item)] for item in items], colWidths=[5 * mm, 170 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return table


def table(rows: list[list[object]], col_widths: list[float], header: bool = False) -> Table:
    data = [[p(cell, "H2CN" if header and row_index == 0 else "BodyCN") for cell in row] for row_index, row in enumerate(rows)]
    result = Table(data, colWidths=col_widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#bfdbfe")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbeafe")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")))
    result.setStyle(TableStyle(style))
    return result


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(18 * mm, 10 * mm, "本次对话全部项目总整理")
    canvas.drawRightString(192 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def file_exists(path: str) -> str:
    return "存在" if (ROOT / path).exists() else "未找到"


def build_story() -> list:
    story: list = []
    cover = Table(
        [
            [p("本次对话全部项目总整理", "CoverTitle")],
            [p("AI客服、桌面辅助、电商商品图、小程序、短视频画布、开源获客、服务器部署、运营交付", "CoverSub")],
            [p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 工作目录：{ROOT}", "CoverSub")],
        ],
        colWidths=[176 * mm],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#08111f")),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (0, 0), 40),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(cover)
    story.append(Spacer(1, 8 * mm))
    story.append(table([
        ["总方向", "先把能商用、能收钱、能演示的AI客服和电商商品图生成做出来，再扩展到短视频、平台API、小程序订阅和私有化部署。"],
        ["当前主产品", "通用AI客服SaaS + 电商商品图/上架草稿小程序。"],
        ["线上后台", "https://wjhai.cn/merchant-admin/"],
        ["演示账号", "ai_kefu_demo / admin123（对外销售前必须改密码）。"],
        ["重要安全", "本PDF不写服务器密码、API Key、平台账号密码。桌面脚本默认候选回复/草稿，不做未经授权的自动发送。"],
    ], [35 * mm, 140 * mm]))
    story.append(PageBreak())

    story.append(section("1. 所有项目总览"))
    story.append(table([
        ["项目", "定位", "当前状态", "主要路径/入口"],
        ["AI客服SaaS后台", "商家知识库、网页客服气泡、会话收件箱、渠道配置、客服脚本。", "已部署，可登录测试。", "https://wjhai.cn/merchant-admin/；backend/customer_service_saas.py；src/main.tsx"],
        ["桌面AI客服辅助", "微信、企业微信、抖音、淘宝/千牛、拼多多、闲鱼窗口候选回复。", "脚本已做，默认不自动发送。", "scripts/desktop_auto_reply_listener.py；启动AI自动客服.bat"],
        ["AI商品图小程序", "商品资料 -> 主图提示词 -> 详情页结构 -> SKU/FAQ -> 上架草稿。", "已改成电商图主流程，接口已上线。", "douyin-miniapp；/api/ecommerce/listing-draft"],
        ["商家短视频画布", "商家需求生成脚本、分镜、9:16短视频/图片/详情页结构。", "保留旧能力，当前不作为主流程。", "backend/main.py；docs/IMPLEMENTATION_DESIGN_2026-06-25.md"],
        ["Remotion/HyperFrames/HeyGen方向", "后续做品牌模板、动态图文混剪、数字人口播、程序化视频。", "规划/适配器位置保留，未作为MVP验收。", "docs/API_PROVIDERS.md；docs/OPEN_SOURCE_ECOMMERCE_STACK.md"],
        ["电商自动化经营中台", "商品、订单、库存、日报、平台草稿、安全执行任务。", "有样例日报和自动化快照骨架。", "scripts/commerce_daily_report.py；/api/ecommerce/daily-report"],
        ["Codex本地插件/Skills", "把商家增长和商品上架经验打包成Codex可引用技能。", "本地已有skill包和插件市场目录。", "codex-plugins-marketplace/plugins；merchant-growth-saas-skill.zip"],
        ["开源/GitHub获客", "用开源仓库做获客入口，卖部署、二开、模板库和API额度。", "有发布目录，曾因凭据未完成push。", "data/github-publish/ai-kefu-opensource"],
        ["运营交付包", "PPT、PDF、Excel、话术、SOP、验收报告。", "已有今日交付包。", "运营计划/今日交付包"],
        ["抖音/闲鱼获客", "短视频内容矩阵、闲鱼服务商品、私信/表单承接。", "方案已整理，需日更执行。", "docs/GTM.md；运营计划/今日交付包"],
    ], [28 * mm, 50 * mm, 43 * mm, 54 * mm], header=True))

    story.append(section("2. AI客服SaaS后台"))
    story.append(bullets([
        "目标：商家导入资料和FAQ后，AI根据知识库自动回复自有网页客服会话；桌面平台先生成候选回复。",
        "后台板块：总览、商家资料/知识库、客服脚本、渠道接入、会话收件箱、桌面自动客服、网页气泡。",
        "核心接口：/api/auth/login、/api/merchant/profile、/api/knowledge/import、/api/widget/session、/api/widget/message、/api/conversations。",
        "线上地址：https://wjhai.cn/merchant-admin/；演示账号 ai_kefu_demo / admin123。",
        "安全边界：微信/抖音/淘宝/拼多多/闲鱼等平台不做绕过风控的自动私信发送；拿到官方API权限后再升级自动化。",
    ]))
    story.append(PageBreak())

    story.append(section("3. 桌面AI客服辅助脚本"))
    story.append(bullets([
        "支持平台：微信、企业微信、抖音、淘宝/千牛、拼多多、闲鱼。",
        "使用方式：先打开真实客服聊天窗口，再运行“启动AI自动客服.bat”或脚本启动器，选择窗口后监听。",
        "当前模式：读取窗口文本/OCR上下文，生成候选回复并可粘贴；默认不按Enter自动发送。",
        "群聊/私聊策略：能识别群消息、私聊和高风险关键词；群聊默认更谨慎，高风险内容标记人工接管。",
        "验收脚本：scripts/desktop_real_platform_acceptance.py、scripts/desktop_reply_e2e_acceptance.py、scripts/acceptance_check.py。",
    ]))

    story.append(section("4. AI商品图生成抖音小程序"))
    story.append(bullets([
        "定位：像你给的参考图那样，做“AI商品图自动生成，主图/详情图/上架资料一键完成”的小程序。",
        "首页功能：选择样例或填写商品名、类目、平台、价格、SKU、卖点、目标客户、库存、发货、售后、视觉风格。",
        "结果页功能：商品标题、主图/详情图提示词、详情页结构、SKU、客服FAQ、风险检查、一键复制整套上架资料、生成真实主图。",
        "线上接口：POST https://wjhai.cn/merchant-admin/api/ecommerce/listing-draft 已返回200。",
        "交付包：运营计划/今日交付包/AI商品图生成抖音小程序.zip。",
        "未覆盖：真实商品图片上传、对象存储、抖音小店官方发布API、商家账号体系和订阅额度。",
    ]))

    story.append(section("5. 短视频画布和视频生成方向"))
    story.append(bullets([
        "最早方向：商家输入需求、商品链接或文字描述，上传素材，系统自动生成9:16营销短视频。",
        "技术路线：先参考OpenShorts/FastAPI/React/FFmpeg能力；后续抽象渲染服务，可换Remotion、HyperFrames、FFmpeg或模型。",
        "当前状态：不是主产品主流程，保留在后续模块；已在文档里沉淀短视频画布、脚本、分镜、HyperFrames渲染计划。",
        "适合售卖：商品短视频模板、口播视频成片、主图详情图+短视频一套素材包。",
    ]))
    story.append(PageBreak())

    story.append(section("6. 电商自动化经营中台"))
    story.append(bullets([
        "目标：从商品档案出发，生成素材、上架草稿、客服FAQ，再扩展到订单、库存、售后、日报。",
        "已存在能力：电商日报脚本、自动化快照接口、商品/订单/库存样例结构、商品上架草稿skill。",
        "安全边界：只读数据、生成草稿、人工确认；不自动改价格、不自动改库存、不自动退款、不自动发布。",
        "下一步：对接合法平台API或商家导出的订单/商品CSV，先做日报和异常提醒，再做草稿填充。",
    ]))

    story.append(section("7. 抖音小程序上架方向"))
    story.append(bullets([
        "当前建议：公司执照下来前，先做体验版、演示版、服务交付，不急着承诺完整交易闭环。",
        "建议类目：企业服务、效率办公、营销服务、商家经营工具。",
        "审核说明：本小程序为商家电商素材和上架草稿生成工具，不自动发布商品，不承诺收益，最终发布由商家确认。",
        "需要补齐：隐私政策、用户协议、合法域名、主体认证、类目材料、体验版录屏。",
    ]))

    story.append(section("8. 开源/GitHub和插件市场"))
    story.append(bullets([
        "你的仓库：200510wjh/ai-kefu-opensource。",
        "本地发布目录：data/github-publish/ai-kefu-opensource；曾处于 ahead 状态，但因GitHub凭据未完成push。",
        "开源获客策略：核心演示开源，卖私有化部署、二开、模板库、API额度和培训。",
        "Codex本地插件：merchant-growth-saas-skill、ecommerce-listing-draft 已在本地插件市场目录，适合自己复用；对客户交付建议用SaaS账号、部署包或小程序，不建议直接卖Codex插件。",
        "公开前必须做：密钥扫描、README重写、LICENSE、.env.example、截图、演示视频、部署文档。",
    ]))

    story.append(section("9. 运营交付物"))
    story.append(table([
        ["交付物", "路径", "状态"],
        ["AI全自动化运营落地方案PPT", "运营计划/今日交付包/AI全自动化运营落地方案.pptx", file_exists("运营计划/今日交付包/AI全自动化运营落地方案.pptx")],
        ["AI客服商用操作手册PDF", "运营计划/今日交付包/AI客服商用操作手册.pdf", file_exists("运营计划/今日交付包/AI客服商用操作手册.pdf")],
        ["客户线索与需求运营表", "运营计划/今日交付包/客户线索与需求运营表.xlsx", file_exists("运营计划/今日交付包/客户线索与需求运营表.xlsx")],
        ["AI商品图小程序包", "运营计划/今日交付包/AI商品图生成抖音小程序.zip", file_exists("运营计划/今日交付包/AI商品图生成抖音小程序.zip")],
        ["本次全项目总整理PDF", str(PDF_PATH), "本次生成"],
    ], [42 * mm, 98 * mm, 35 * mm], header=True))
    story.append(PageBreak())

    story.append(section("10. 当前能卖什么"))
    story.append(table([
        ["产品", "交付内容", "建议价格"],
        ["AI客服部署服务", "后台部署、知识库导入、网页气泡、基础培训。", "299-999元/次"],
        ["AI客服话术包", "行业FAQ、售前售后、异议处理、留资话术。", "99-299元/套"],
        ["桌面客服辅助配置", "微信/企业微信/闲鱼/淘宝等候选回复脚本配置。", "399-1999元/配置"],
        ["单品上架资料包", "标题、卖点、主图提示词、详情页结构、SKU、FAQ。", "99-299元/商品"],
        ["批量上新草稿包", "10个商品资料包和主图提示词。", "399-999元/批"],
        ["私有化部署", "服务器部署、改品牌、模板、培训和维护。", "1999-9999元起"],
    ], [35 * mm, 95 * mm, 45 * mm], header=True))

    story.append(section("11. 抖音/闲鱼获客打法"))
    story.append(bullets([
        "抖音内容：每天发“老板发一个商品，AI生成主图详情页和上架草稿”的屏幕录制。",
        "闲鱼商品：上架“AI商品图生成系统部署”“AI客服系统部署”“电商上架资料批量生成”。",
        "私信承接：让客户发商品名、价格、卖点和平台，先免费生成一版草稿作为钩子。",
        "不要承诺：全自动引流、保证成交、自动私信陌生人、绕过平台风控。",
        "公司执照未下来前：卖内测名额、部署服务、素材代做、话术整理，不急着做完整小程序支付订阅。",
    ]))

    story.append(section("12. 测试和验收"))
    story.append(bullets([
        "本地小程序静态校验：python scripts/validate_miniapp.py 通过。",
        "后端编译：python -m py_compile backend/main.py 通过。",
        "小程序JS语法：node --check utils/api.js、pages/index/index.js、pages/result/result.js 通过。",
        "线上商品草稿接口：/api/ecommerce/listing-draft 返回200。",
        "此前线上后台已验证：页面、静态资源、登录、dashboard、渠道列表可访问。",
    ]))

    story.append(section("13. 未覆盖和风险总表"))
    story.append(bullets([
        "图片模型：需要配置 IMAGE_API_KEY / IMAGE_BASE_URL / IMAGE_MODEL，否则只能返回提示词。",
        "小程序：还缺图片上传、对象存储、用户协议、隐私政策、主体认证和体验版提交。",
        "客服：自有网页气泡可自动回复；第三方平台需要官方API权限或人工确认。",
        "电商平台：还未接抖音小店/淘宝/拼多多官方商品发布API，当前只生成草稿。",
        "GitHub：公开前必须清理密钥、修复中文乱码、整理README、补.env.example和截图。",
        "账号安全：对外销售前更换演示账号密码，不把服务器密码和API Key放进任何交付包。",
        "合规：涉及医疗、食品、功效、美妆、金融等类目要补平台资质和审核材料。",
    ]))
    story.append(PageBreak())

    story.append(section("14. 下一步路线"))
    story.append(table([
        ["优先级", "任务", "目的"],
        ["P0", "配置图片生成模型，让“生成真实主图”返回图片。", "让电商图功能从提示词升级为真出图。"],
        ["P0", "修复前端中文乱码，统一产品名和导航。", "提高客户演示可信度。"],
        ["P1", "小程序增加图片选择、上传和商品历史库。", "让商家能保存商品档案和生成记录。"],
        ["P1", "补隐私政策、用户协议、审核说明，提交抖音体验版。", "准备上架和对外测试。"],
        ["P1", "整理GitHub开源仓库并推送。", "做开源获客入口。"],
        ["P2", "接官方平台API：企业微信客服、抖音小店、淘宝/拼多多。", "从候选回复/草稿升级为授权自动化。"],
        ["P2", "接Remotion/HyperFrames模板。", "做商品短视频和动态图文混剪。"],
        ["P2", "做订阅/额度/订单后台。", "形成SaaS收费闭环。"],
    ], [20 * mm, 95 * mm, 60 * mm], header=True))

    story.append(section("15. 关键文件位置"))
    story.append(table([
        ["内容", "路径"],
        ["AI客服后端", "backend/customer_service_saas.py；backend/main.py"],
        ["前端后台", "src/main.tsx；src/styles.css"],
        ["小程序", "douyin-miniapp"],
        ["桌面脚本", "scripts/desktop_auto_reply_listener.py；scripts/desktop_listener_launcher.py"],
        ["电商日报", "scripts/commerce_daily_report.py"],
        ["运营计划", "运营计划"],
        ["今日交付包", "运营计划/今日交付包"],
        ["PDF输出", str(PDF_PATH)],
    ], [40 * mm, 135 * mm], header=True))
    return story


def validate_pdf() -> None:
    reader = PdfReader(str(PDF_PATH))
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
    required = ["所有项目总览", "AI客服SaaS", "AI商品图", "桌面AI客服", "短视频画布"]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"PDF文本校验缺失：{missing}")
    if len(reader.pages) < 6:
        raise RuntimeError("PDF页数异常，可能内容未写入完整。")


def render_previews() -> None:
    pdf = pdfium.PdfDocument(str(PDF_PATH))
    first = pdf[0].render(scale=1.5).to_pil()
    first.save(PREVIEW_PATH)

    thumbs = []
    for index in range(len(pdf)):
        thumbs.append(pdf[index].render(scale=0.35).to_pil().convert("RGB"))
    from PIL import Image, ImageOps

    max_w = max(item.width for item in thumbs)
    max_h = max(item.height for item in thumbs)
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * max_w + 40, rows * max_h + 40), "white")
    for index, image in enumerate(thumbs):
        bordered = ImageOps.expand(image, border=6, fill="#cbd5e1")
        x = 20 + (index % cols) * max_w
        y = 20 + (index // cols) * max_h
        sheet.paste(bordered, (x, y))
    sheet.save(ALL_PREVIEW_PATH)
    pdf.close()


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
        title="本次对话全部项目总整理",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    shutil.copyfile(PDF_PATH, MIRROR_PATH)
    validate_pdf()
    render_previews()
    reader = PdfReader(str(PDF_PATH))
    print(PDF_PATH)
    print(MIRROR_PATH)
    print(PREVIEW_PATH)
    print(ALL_PREVIEW_PATH)
    print(f"pages={len(reader.pages)}")


if __name__ == "__main__":
    main()
