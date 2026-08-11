import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = "C:/Users/Administrator/Documents/运营";
const OUT_DIR = path.join(ROOT, "outputs", "闲鱼高端AI客服上架包");
const IMG_DIR = path.join(OUT_DIR, "闲鱼商品图");
const MD = path.join(OUT_DIR, "抖音短视频与闲鱼AI客服上架整合策略.md");
const DATA = path.join(OUT_DIR, "douyin_xianyu_listing_images.data.json");
const PS = path.join(OUT_DIR, "build_douyin_xianyu_listing_images.ps1");

const cards = [
  {
    file: "01-抖店淘宝AI客服搭建.png",
    tag: "闲鱼高端服务",
    title: "抖店淘宝AI客服搭建",
    subtitle: "商品知识库 + 自动回复 + 人工兜底",
    price: "2999-9800",
    bullets: ["高频问题先接住", "客服话术统一", "7天陪跑优化"],
    footer: "发平台+类目+咨询量，我先判断方案",
    accent: "00A6A6",
  },
  {
    file: "02-商品知识库客服SOP.png",
    tag: "可单独成交",
    title: "商品知识库 / 客服SOP",
    subtitle: "把老板经验整理成AI可用话术",
    price: "1999-6800",
    bullets: ["售前FAQ", "售后赔付口径", "新人客服培训"],
    footer: "适合生鲜、服饰、礼品、本地生活",
    accent: "2F80ED",
  },
  {
    file: "03-高端AI客服陪跑包.png",
    tag: "高客单项目",
    title: "AI客服系统 + 7天陪跑",
    subtitle: "不是卖软件，是把客服流程跑通",
    price: "9800-19800",
    bullets: ["诊断+配置", "试运行+复盘", "人工接管策略"],
    footer: "适合已有订单和客服团队的商家",
    accent: "D4A017",
  },
  {
    file: "04-企微私域AI客服辅助.png",
    tag: "低风险方案",
    title: "企微私域AI客服辅助",
    subtitle: "AI先给建议，人工确认后发送",
    price: "6800-19800",
    bullets: ["不碰高风险直发", "高意向提醒", "敏感问题转人工"],
    footer: "解决已有客服团队但回复不稳定的问题",
    accent: "7C3AED",
  },
  {
    file: "05-AI内容生产客服转化.png",
    tag: "月度服务",
    title: "AI内容生产 + 客服转化",
    subtitle: "脚本、图片、视频、客服话术一起做",
    price: "7500/月起",
    bullets: ["短视频脚本", "商品图提示词", "转化话术库"],
    footer: "内容引流，客服承接，提高续费空间",
    accent: "16A34A",
  },
  {
    file: "06-抖音短视频获客AI客服承接.png",
    tag: "抖音账号打法",
    title: "抖音短视频获客 + AI客服承接",
    subtitle: "短视频带咨询，客服系统接转化",
    price: "2999-12800",
    bullets: ["每周30条标题", "10条口播脚本", "私信/评论FAQ承接"],
    footer: "从选题到话术，形成获客闭环",
    accent: "F43F5E",
  },
  {
    file: "07-自动化上架优化流程.png",
    tag: "上架优化流程",
    title: "半自动化上架，不盲目乱发",
    subtitle: "AI生成草稿，人工确认发布",
    price: "7天复盘",
    bullets: ["标题/详情/FAQ自动生成", "主图批量出图", "曝光-浏览-想要-咨询复盘"],
    footer: "发布、改价、发消息都保留人工确认",
    accent: "0F766E",
  },
];

const strategy = `# 抖音短视频与闲鱼AI客服上架整合策略

## 核心理解

你的项目文件夹里已经有一条完整商业链路：商品资料 -> AI商品上架草稿 -> 标题/卖点/SKU/详情页 -> 口播脚本 -> 口播视频剪辑 -> 抖音/小红书商品种草素材 -> 客服承接 -> 线索跟进。

这说明你不应该只在闲鱼卖“AI客服搭建”，也不应该只卖“短视频剪辑”。更好的高端卖法是：

**短视频负责带来咨询，AI客服负责接住咨询，商品知识库负责让回复不乱，7天陪跑负责把数据跑起来。**

## 从文件夹里提取到的产品证据

- \`docs/VIDEOCUT_SKILLS_INSTALL_2026-06-25.md\`：已有 299/499/999/2999 元包装，但更偏低价素材包。
- \`docs/REMOTION_AI_STARTUP_DOUYIN_VIDEO_2026-06-25.md\`：已有 45-55 秒抖音口播结构、三步法、案例和系列模板。
- \`docs/IMPLEMENTATION_DESIGN_2026-06-25.md\`：明确设计了“商品/门店档案 -> 素材生成 -> 短视频分镜 -> 客服候选回复 -> 平台草稿任务 -> 线索跟进”。
- \`output/tryon-*-sales-video-20260711/script.md\`：已有服装带货口播样本，说明能围绕商品生成短视频卖点。

## 新增闲鱼商品

### 抖音短视频获客 + AI客服承接包

标题：抖音短视频获客AI客服承接 商品脚本私信话术自动化方案

价格：2999-12800 元

卖点：

- 每周 30 条标题方向。
- 10 条口播脚本。
- 商品卖点和短视频分镜。
- 私信/评论高频问题 FAQ。
- AI客服候选回复。
- 人工确认与7天复盘。

详情页核心话术：

你不是缺一条视频，你缺的是从“视频引流”到“客户咨询”再到“客服接住”的整套链路。这个服务不是单纯剪辑，而是把商品档案、短视频脚本、客服FAQ和私信承接连在一起，让客户来了之后有人接、有话术接、能复盘优化。

## 上架安全边界

只做半自动化上架：

- 自动生成标题、详情页、FAQ、图片、话术。
- 人工确认后再发布闲鱼商品。
- 不自动改价。
- 不自动群发私信。
- 不自动绕过平台风控。

## 已生成商品图

图片目录：\`C:\\Users\\Administrator\\Documents\\运营\\outputs\\闲鱼高端AI客服上架包\\闲鱼商品图\`

共 7 张方图，可用于闲鱼商品首图/详情图。`;

const ps = String.raw`
param([string]$DataPath, [string]$ImageDir)
$ErrorActionPreference = "Stop"
$data = Get-Content -LiteralPath $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $ImageDir | Out-Null

$ppt = New-Object -ComObject PowerPoint.Application
$deck = $ppt.Presentations.Add()
$deck.PageSetup.SlideWidth = 1080
$deck.PageSetup.SlideHeight = 1080

function RGBFromHex([string]$hex) {
  $r = [Convert]::ToInt32($hex.Substring(0,2), 16)
  $g = [Convert]::ToInt32($hex.Substring(2,2), 16)
  $b = [Convert]::ToInt32($hex.Substring(4,2), 16)
  return $r + ($g * 256) + ($b * 65536)
}

function AddText($slide, [string]$text, [single]$x, [single]$y, [single]$w, [single]$h, [int]$size, [bool]$bold, [string]$color) {
  $shape = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
  $shape.TextFrame.TextRange.Text = $text
  $shape.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
  $shape.TextFrame.TextRange.Font.Size = $size
  $shape.TextFrame.TextRange.Font.Bold = $(if ($bold) { -1 } else { 0 })
  $shape.TextFrame.TextRange.Font.Color.RGB = RGBFromHex $color
  $shape.TextFrame.WordWrap = -1
  return $shape
}

function AddRect($slide, [single]$x, [single]$y, [single]$w, [single]$h, [string]$fill, [string]$line) {
  $shape = $slide.Shapes.AddShape(1, $x, $y, $w, $h)
  $shape.Fill.ForeColor.RGB = RGBFromHex $fill
  $shape.Line.ForeColor.RGB = RGBFromHex $line
  return $shape
}

foreach ($card in $data.cards) {
  $slide = $deck.Slides.Add($deck.Slides.Count + 1, 12)
  $bg = AddRect $slide 0 0 1080 1080 "F7F8FA" "F7F8FA"
  $accent = [string]$card.accent
  AddRect $slide 0 0 1080 74 $accent $accent | Out-Null
  AddText $slide $card.tag 64 22 520 36 24 $true "FFFFFF" | Out-Null
  AddText $slide "小危AI商家增长" 760 22 260 36 22 $true "FFFFFF" | Out-Null

  AddText $slide $card.title 64 140 880 116 58 $true "111827" | Out-Null
  AddText $slide $card.subtitle 68 270 880 48 28 $false "374151" | Out-Null

  AddRect $slide 64 360 392 166 "111827" "111827" | Out-Null
  AddText $slide "建议价格" 96 390 180 34 24 $false "D1D5DB" | Out-Null
  AddText $slide ("¥ " + [string]$card.price) 96 430 320 58 42 $true "FFFFFF" | Out-Null

  AddRect $slide 496 360 500 166 "FFFFFF" "E5E7EB" | Out-Null
  AddText $slide "适合商家" 528 390 200 34 24 $true $accent | Out-Null
  AddText $slide "有真实商品、有咨询、有客服或老板愿意配合" 528 432 400 64 26 $false "111827" | Out-Null

  $y = 585
  foreach ($bullet in $card.bullets) {
    AddRect $slide 72 $y 20 20 $accent $accent | Out-Null
    AddText $slide ([string]$bullet) 116 ($y - 10) 820 44 32 $true "111827" | Out-Null
    $y += 94
  }

  AddRect $slide 64 930 952 76 "FFFFFF" "D1D5DB" | Out-Null
  AddText $slide ([string]$card.footer) 92 950 900 38 28 $true "111827" | Out-Null
}

for ($i = 1; $i -le $deck.Slides.Count; $i++) {
  $file = Join-Path $ImageDir ([string]$data.cards[$i - 1].file)
  $deck.Slides.Item($i).Export($file, "PNG", 1080, 1080)
}
$deck.SaveAs((Join-Path $ImageDir "闲鱼商品图源文件.pptx"), 24)
$deck.Close()
try { $ppt.Quit() } catch {}
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($deck)
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)
Write-Output "images-ready"
`;

await fs.mkdir(IMG_DIR, { recursive: true });
await fs.writeFile(MD, strategy, "utf8");
await fs.writeFile(DATA, JSON.stringify({ cards }, null, 2), "utf8");
await fs.writeFile(PS, `\ufeff${ps}`, "utf8");

const result = spawnSync("powershell.exe", [
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  PS,
  "-DataPath",
  DATA,
  "-ImageDir",
  IMG_DIR,
], { encoding: "utf8" });

if (result.status !== 0) {
  console.error(result.stdout);
  console.error(result.stderr);
  throw new Error(`Image export failed with status ${result.status}`);
}

const files = await fs.readdir(IMG_DIR);
console.log(JSON.stringify({ markdown: MD, imageDir: IMG_DIR, files }, null, 2));
