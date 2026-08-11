import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = "C:/Users/Administrator/Documents/运营";
const OUT_DIR = path.join(ROOT, "outputs", "闲鱼高端AI客服上架包");
const IMG_DIR = path.join(OUT_DIR, "闲鱼商品图-低门槛版");
const MD = path.join(OUT_DIR, "低门槛版闲鱼上架文案.md");
const DATA = path.join(OUT_DIR, "low_price_xianyu_images.data.json");
const PS = path.join(OUT_DIR, "build_low_price_xianyu_images.ps1");

const cards = [
  {
    file: "01-199元AI客服诊断.png",
    tag: "先低价试单",
    title: "AI客服诊断方案",
    subtitle: "看店铺问题，判断能不能做AI客服",
    price: "199",
    bullets: ["1页诊断报告", "找出20个高频问题", "成交项目可抵扣"],
    footer: "发平台+类目+3个常见问题",
    accent: "0EA5E9",
  },
  {
    file: "02-299元商品知识库.png",
    tag: "单品起步",
    title: "商品知识库整理",
    subtitle: "把商品卖点整理成客服能用的话术",
    price: "299起",
    bullets: ["售前问答", "售后口径", "AI可读知识库"],
    footer: "适合先整理1个商品/服务",
    accent: "10B981",
  },
  {
    file: "03-599元客服话术SOP.png",
    tag: "客服提效",
    title: "客服话术SOP",
    subtitle: "新客服照着回，AI客服也能学",
    price: "599起",
    bullets: ["30条FAQ", "售后赔付话术", "禁用话术提醒"],
    footer: "生鲜/服饰/本地生活都能做",
    accent: "F59E0B",
  },
  {
    file: "04-999元AI客服轻量搭建.png",
    tag: "轻量搭建",
    title: "AI客服轻量搭建",
    subtitle: "先跑高频问题，不追求一步全自动",
    price: "999起",
    bullets: ["知识库导入", "自动回复草稿", "人工接管规则"],
    footer: "先试跑，再决定是否升级",
    accent: "6366F1",
  },
  {
    file: "05-999元短视频脚本获客包.png",
    tag: "抖音获客",
    title: "短视频脚本获客包",
    subtitle: "商品选题、口播脚本、私信承接一起做",
    price: "999起",
    bullets: ["30条标题", "10条口播脚本", "私信FAQ承接"],
    footer: "短视频带咨询，客服接转化",
    accent: "F43F5E",
  },
  {
    file: "06-1999元上架优化陪跑.png",
    tag: "7天陪跑",
    title: "闲鱼上架优化陪跑",
    subtitle: "标题、主图、详情、咨询话术一起优化",
    price: "1999起",
    bullets: ["5条商品草稿", "7张主图", "7天数据复盘"],
    footer: "看曝光、浏览、想要、咨询再改",
    accent: "14B8A6",
  },
  {
    file: "07-套餐升级路径.png",
    tag: "低价入口",
    title: "先低价成交，再升级",
    subtitle: "199诊断 -> 999搭建 -> 1999陪跑",
    price: "199起",
    bullets: ["不做9.9低质流量", "先拿咨询", "再做项目升级"],
    footer: "闲鱼先要有人问，再谈高客单",
    accent: "111827",
  },
];

const copy = `# 低门槛版闲鱼上架文案

## 调整逻辑

原版价格适合高端客户，但闲鱼第一眼容易觉得贵。低门槛版改成“先成交小单，再升级项目”：

- 199元：AI客服诊断。
- 299元起：单品商品知识库。
- 599元起：客服话术SOP。
- 999元起：AI客服轻量搭建。
- 999元起：抖音短视频脚本获客包。
- 1999元起：闲鱼上架优化7天陪跑。

## 主推标题

### 标题1

199元AI客服诊断 店铺客服问题梳理 可抵扣搭建项目

### 标题2

AI客服轻量搭建 商品知识库客服话术 自动回复草稿999起

### 标题3

抖音短视频脚本获客包 30条标题10条口播私信承接999起

### 标题4

闲鱼商品上架优化 主图标题详情咨询话术 7天陪跑1999起

## 详情页开头

不是一上来让你花几千上系统。先用低成本把店铺客服问题、商品知识库、短视频脚本和咨询承接跑起来。

你发我：平台、类目、商品链接、每天咨询量、客户最常问的3个问题。我先判断你适合做199诊断、999轻量搭建，还是1999陪跑。

## 升级路径

先做199诊断，确认有价值后升级999轻量搭建；如果已经有咨询量，再升级1999上架/客服/短视频7天陪跑。
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
  $accent = [string]$card.accent
  AddRect $slide 0 0 1080 1080 "FFFDF8" "FFFDF8" | Out-Null
  AddRect $slide 0 0 1080 82 $accent $accent | Out-Null
  AddText $slide $card.tag 64 24 430 36 24 $true "FFFFFF" | Out-Null
  AddText $slide "小危AI" 848 24 170 36 24 $true "FFFFFF" | Out-Null

  AddText $slide $card.title 64 140 900 104 56 $true "111827" | Out-Null
  AddText $slide $card.subtitle 68 258 900 48 28 $false "4B5563" | Out-Null

  AddRect $slide 64 352 952 178 "111827" "111827" | Out-Null
  AddText $slide "低门槛试单价" 98 386 260 34 26 $false "D1D5DB" | Out-Null
  AddText $slide ("¥ " + [string]$card.price) 98 426 500 68 54 $true "FFFFFF" | Out-Null
  AddText $slide "先小单验证，再升级项目" 662 430 300 44 26 $true "FDE68A" | Out-Null

  $y = 606
  foreach ($bullet in $card.bullets) {
    AddRect $slide 72 $y 22 22 $accent $accent | Out-Null
    AddText $slide ([string]$bullet) 122 ($y - 12) 820 48 34 $true "111827" | Out-Null
    $y += 92
  }

  AddRect $slide 64 928 952 78 "FFFFFF" "E5E7EB" | Out-Null
  AddText $slide ([string]$card.footer) 96 948 890 38 28 $true "111827" | Out-Null
}

for ($i = 1; $i -le $deck.Slides.Count; $i++) {
  $file = Join-Path $ImageDir ([string]$data.cards[$i - 1].file)
  $deck.Slides.Item($i).Export($file, "PNG", 1080, 1080)
}
$deck.SaveAs((Join-Path $ImageDir "闲鱼低门槛版商品图源文件.pptx"), 24)
$deck.Close()
try { $ppt.Quit() } catch {}
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($deck)
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)
Write-Output "low-price-images-ready"
`;

await fs.mkdir(IMG_DIR, { recursive: true });
await fs.writeFile(MD, copy, "utf8");
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
  throw new Error(`Low price image export failed with status ${result.status}`);
}

const files = await fs.readdir(IMG_DIR);
console.log(JSON.stringify({ markdown: MD, imageDir: IMG_DIR, files }, null, 2));
