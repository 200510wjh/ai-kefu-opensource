import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = "C:/Users/Administrator/Documents/运营";
const OUT_DIR = path.join(ROOT, "outputs", "闲鱼高端AI客服上架包");
const IMG_DIR = path.join(OUT_DIR, "闲鱼商品图-无价格咨询版");
const DATA = path.join(OUT_DIR, "no_price_xianyu_images.data.json");
const PS = path.join(OUT_DIR, "build_no_price_xianyu_images.ps1");
const MD = path.join(OUT_DIR, "无价格咨询版闲鱼上架文案.md");

const cards = [
  {
    file: "01-AI客服诊断方案.png",
    label: "先诊断再搭建",
    title: "AI客服诊断方案",
    sub: "看店铺咨询问题，判断值不值得做AI客服",
    chips: ["高频问题梳理", "知识库建议", "适合/不适合直接说"],
    cta: "发平台 + 类目 + 3个常见问题",
    accent: "0F766E",
    soft: "E8F7F3",
  },
  {
    file: "02-商品知识库整理.png",
    label: "先把回答标准化",
    title: "商品知识库整理",
    sub: "把商品卖点、售后规则、FAQ整理成客服能用的话术",
    chips: ["售前问答", "售后口径", "AI可读资料"],
    cta: "发商品链接，我先看资料能不能整理",
    accent: "2563EB",
    soft: "EAF1FF",
  },
  {
    file: "03-客服话术SOP.png",
    label: "客服提效",
    title: "客服话术SOP",
    sub: "新客服照着回，AI客服也能学，老板不用天天重复教",
    chips: ["咨询话术", "投诉安抚", "转人工边界"],
    cta: "适合生鲜 / 服饰 / 本地生活 / 软件服务",
    accent: "D97706",
    soft: "FFF4DF",
  },
  {
    file: "04-AI客服轻量搭建.png",
    label: "轻量试跑",
    title: "AI客服轻量搭建",
    sub: "先跑高频问题，不追求一步全自动，人工随时接管",
    chips: ["知识库导入", "自动回复草稿", "人工兜底"],
    cta: "先试跑，再决定是否升级完整系统",
    accent: "4F46E5",
    soft: "EEF2FF",
  },
  {
    file: "05-短视频脚本获客包.png",
    label: "抖音账号打法",
    title: "短视频脚本获客包",
    sub: "短视频负责带咨询，客服话术负责接转化",
    chips: ["选题方向", "口播脚本", "私信FAQ"],
    cta: "发产品类目，我先出选题方向",
    accent: "E11D48",
    soft: "FFF0F3",
  },
  {
    file: "06-闲鱼上架优化陪跑.png",
    label: "上架优化",
    title: "闲鱼上架优化陪跑",
    sub: "标题、主图、详情、咨询话术一起改，不盲目上架",
    chips: ["标题优化", "主图重做", "咨询复盘"],
    cta: "看曝光 / 浏览 / 想要 / 咨询再调整",
    accent: "0891B2",
    soft: "E8F8FC",
  },
  {
    file: "07-内容获客客服承接闭环.png",
    label: "完整闭环",
    title: "内容获客 + 客服承接",
    sub: "从抖音/闲鱼引流，到私信咨询，再到客服话术承接",
    chips: ["内容引流", "FAQ承接", "7天复盘"],
    cta: "先拿咨询，再做项目升级",
    accent: "111827",
    soft: "F3F4F6",
  },
];

const md = `# 无价格咨询版闲鱼上架文案

## 设计调整

这版图片不在首图标价格。闲鱼首图只做三件事：

1. 让客户知道你解决什么问题。
2. 让客户知道适合谁。
3. 让客户知道第一句该发什么。

价格放详情页套餐里，先把咨询拉进来。

## 建议先上架的标题

### 商品1

AI客服诊断方案 店铺咨询问题梳理 商品知识库建议

### 商品2

商品知识库整理 客服话术SOP 售前售后FAQ标准化

### 商品3

AI客服轻量搭建 商品知识库自动回复草稿 人工兜底

### 商品4

短视频脚本获客包 抖音选题口播脚本 私信FAQ承接

### 商品5

闲鱼商品上架优化 主图标题详情咨询话术 7天陪跑

## 详情页价格放法

不要在首图放价格。详情页里写：

- 诊断/单品整理：适合先试一下。
- 轻量搭建：适合已有咨询但客服接不住。
- 陪跑项目：适合有真实流量，想把内容和客服一起跑起来。

客户问价时再根据类目、商品数量、平台和咨询量报价。
`;

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
  $shape.TextFrame.MarginLeft = 0
  $shape.TextFrame.MarginRight = 0
  $shape.TextFrame.MarginTop = 0
  $shape.TextFrame.MarginBottom = 0
  return $shape
}

function AddRect($slide, [single]$x, [single]$y, [single]$w, [single]$h, [string]$fill, [string]$line) {
  $shape = $slide.Shapes.AddShape(1, $x, $y, $w, $h)
  $shape.Fill.ForeColor.RGB = RGBFromHex $fill
  $shape.Line.ForeColor.RGB = RGBFromHex $line
  return $shape
}

function AddOval($slide, [single]$x, [single]$y, [single]$w, [single]$h, [string]$fill) {
  $shape = $slide.Shapes.AddShape(9, $x, $y, $w, $h)
  $shape.Fill.ForeColor.RGB = RGBFromHex $fill
  $shape.Line.ForeColor.RGB = RGBFromHex $fill
  return $shape
}

foreach ($card in $data.cards) {
  $slide = $deck.Slides.Add($deck.Slides.Count + 1, 12)
  $accent = [string]$card.accent
  $soft = [string]$card.soft

  AddRect $slide 0 0 1080 1080 "FAFAF7" "FAFAF7" | Out-Null
  AddRect $slide 62 58 956 56 $soft $soft | Out-Null
  AddText $slide "小危AI商家增长" 82 72 260 28 20 $true $accent | Out-Null
  AddText $slide ([string]$card.label) 712 72 280 28 20 $true "374151" | Out-Null

  AddText $slide ([string]$card.title) 72 178 900 112 60 $true "111827" | Out-Null
  AddText $slide ([string]$card.sub) 76 314 860 76 30 $false "374151" | Out-Null

  AddRect $slide 72 458 936 250 "FFFFFF" "E5E7EB" | Out-Null
  AddText $slide "交付重点" 108 492 180 34 24 $true $accent | Out-Null
  $y = 548
  foreach ($chip in $card.chips) {
    AddOval $slide 112 ($y + 8) 18 18 $accent | Out-Null
    AddText $slide ([string]$chip) 154 $y 760 42 34 $true "111827" | Out-Null
    $y += 58
  }

  AddRect $slide 72 792 936 120 $accent $accent | Out-Null
  AddText $slide "咨询时直接发：" 110 820 230 34 25 $false "FFFFFF" | Out-Null
  AddText $slide ([string]$card.cta) 110 858 830 44 32 $true "FFFFFF" | Out-Null

  AddText $slide "先小单验证 · 人工确认 · 不乱自动发布" 76 980 650 30 22 $false "6B7280" | Out-Null
}

for ($i = 1; $i -le $deck.Slides.Count; $i++) {
  $file = Join-Path $ImageDir ([string]$data.cards[$i - 1].file)
  $deck.Slides.Item($i).Export($file, "PNG", 1080, 1080)
}
$deck.SaveAs((Join-Path $ImageDir "闲鱼无价格咨询版商品图源文件.pptx"), 24)
$deck.Close()
try { $ppt.Quit() } catch {}
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($deck)
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)
Write-Output "no-price-images-ready"
`;

await fs.mkdir(IMG_DIR, { recursive: true });
await fs.writeFile(MD, md, "utf8");
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
  throw new Error(`No price image export failed with status ${result.status}`);
}

const files = await fs.readdir(IMG_DIR);
console.log(JSON.stringify({ markdown: MD, imageDir: IMG_DIR, files }, null, 2));
