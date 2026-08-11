import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline/promises";
import { pathToFileURL } from "node:url";
import { stdin as input, stdout as output } from "node:process";
import { spawnSync } from "node:child_process";

const WORKSPACE = path.resolve("C:/Users/Administrator/Documents/运营");
const DEFAULT_ROOT = path.join(WORKSPACE, "outputs", "闲鱼AI客服一键生成");
const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, "$1");

const productTemplates = [
  {
    id: "P0",
    name: "AI客服诊断方案",
    role: "低门槛咨询入口",
    price: "199，可抵扣后续项目款",
    accent: "0F766E",
    promise: "先看店铺咨询问题，再判断值不值得做AI客服。",
    deliverables: ["1页诊断结论", "高频问题梳理", "适合/不适合自动化判断", "后续预算建议"],
    target: "预算未明确、担心踩坑、但有真实店铺问题的客户",
  },
  {
    id: "P1",
    name: "商品知识库 + 客服话术SOP",
    role: "高毛利基础服务",
    price: "999-6800",
    accent: "2563EB",
    promise: "把老板和老客服的经验整理成新人、AI都能使用的标准资料。",
    deliverables: ["售前FAQ", "售后赔付口径", "投诉升级边界", "禁用话术提醒"],
    target: "商品多、售后规则多、客服口径不统一的商家",
  },
  {
    id: "P2",
    name: "AI客服轻量搭建",
    role: "主推成交服务",
    price: "1999-9800",
    accent: "4F46E5",
    promise: "先跑高频问题，不追求一步全自动，人工随时接管。",
    deliverables: ["知识库导入", "自动回复草稿", "人工兜底规则", "3-7天试运行优化"],
    target: "每天有重复咨询、想减少漏回和慢回的店铺",
  },
  {
    id: "P3",
    name: "闲鱼上架优化陪跑",
    role: "平台运营服务",
    price: "1999-6800",
    accent: "0891B2",
    promise: "标题、主图、详情、咨询话术一起改，不盲目乱发。",
    deliverables: ["5条上架草稿", "7张商品图数据", "咨询FAQ", "7天曝光/浏览/想要/咨询复盘"],
    target: "想在闲鱼测试AI服务售卖，但缺少成体系上架素材的人",
  },
  {
    id: "P4",
    name: "内容获客 + 客服承接闭环",
    role: "高客单扩展包",
    price: "2999-12800",
    accent: "E11D48",
    promise: "短视频负责带咨询，客服话术负责接转化。",
    deliverables: ["选题方向", "口播脚本", "私信FAQ", "内容到客服的转化话术"],
    target: "需要抖音、小红书、闲鱼联动获客的商家",
  },
];

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const raw = argv[i];
    const item = raw.startsWith("--") ? raw.slice(2) : raw;
    const eq = item.indexOf("=");
    if (eq === -1) {
      const next = argv[i + 1];
      if (raw.startsWith("--") && next && !next.startsWith("--")) {
        args[item] = next;
        i += 1;
      } else {
        args[item] = true;
      }
    } else {
      args[item.slice(0, eq)] = item.slice(eq + 1);
    }
  }
  return args;
}

function slug(text) {
  return String(text || "pack")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .slice(0, 48) || "pack";
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

async function loadJson(file) {
  return JSON.parse(await fs.readFile(path.resolve(file), "utf8"));
}

async function collectInput(args) {
  const fromFile = args.input ? await loadJson(args.input) : {};
  const cfg = {
    platform: args.platform || fromFile.platform,
    category: args.category || fromFile.category,
    priceBand: args["price-band"] || args.priceBand || fromFile.priceBand,
    outputName: args.output || fromFile.outputName || "闲鱼AI客服上架包",
    variant: args.variant || fromFile.variant || "consult_first",
    customerEvidence: fromFile.customerEvidence || [],
  };

  if (args.evidence) {
    cfg.customerEvidence = String(args.evidence).split("|").map((s) => s.trim()).filter(Boolean);
  }

  const missing = ["platform", "category", "priceBand"].filter((key) => !cfg[key]);
  if (missing.length && !args["no-prompt"]) {
    const rl = readline.createInterface({ input, output });
    cfg.platform ||= await rl.question("平台：");
    cfg.category ||= await rl.question("类目：");
    cfg.priceBand ||= await rl.question("价格带：");
    if (!cfg.customerEvidence.length) {
      const evidence = await rl.question("客户证据（多条用 | 分隔）：");
      cfg.customerEvidence = evidence.split("|").map((s) => s.trim()).filter(Boolean);
    }
    await rl.close();
  }

  for (const key of ["platform", "category", "priceBand"]) {
    if (!cfg[key]) throw new Error(`缺少必填项：${key}`);
  }
  if (!cfg.customerEvidence.length) cfg.customerEvidence = ["暂无客户证据，请补充真实聊天记录、成交截图或交付案例。"];
  return cfg;
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(headers, rows) {
  return [headers, ...rows].map((row) => row.map(csvEscape).join(",")).join("\r\n");
}

function makeProducts(cfg) {
  return productTemplates.map((p) => ({
    ...p,
    platform: cfg.platform,
    category: cfg.category,
    price: p.id === "P0" ? p.price : blendPrice(p.price, cfg.priceBand),
    title: titleFor(p, cfg),
    opener: openerFor(p, cfg),
    detail: detailFor(p, cfg),
    faq: faqFor(p, cfg),
  }));
}

function blendPrice(base, priceBand) {
  if (!priceBand) return base;
  return base.includes("起") || base.includes("-") ? `${base}；可按${priceBand}拆档` : `${base}；${priceBand}`;
}

function titleFor(p, cfg) {
  const prefix = cfg.platform === "闲鱼" ? "" : `${cfg.platform}`;
  const category = cfg.category.split(/[\/,，、]/)[0].trim();
  const map = {
    P0: `${prefix}${category}诊断 店铺咨询问题梳理 AI客服方案判断`,
    P1: `${prefix}${category}商品知识库整理 客服话术SOP 售前售后FAQ`,
    P2: `${prefix}${category}AI客服轻量搭建 商品知识库自动回复 人工兜底`,
    P3: `${prefix}${category}上架优化 主图标题详情咨询话术 7天陪跑`,
    P4: `${prefix}${category}内容获客客服承接 短视频脚本私信FAQ闭环`,
  };
  return map[p.id];
}

function openerFor(p, cfg) {
  if (p.id === "P0") return `你发我：${cfg.platform}+${cfg.category}+3个最常见客服问题，我先判断值不值得做AI客服。`;
  if (p.id === "P1") return `你发我一个商品链接或类目，我先判断这个类目最该整理哪20个客服问题。`;
  if (p.id === "P2") return `你发我：平台、类目、每天咨询量、客服最常被问的问题，我先拆轻量搭建方案。`;
  if (p.id === "P3") return `你发我现有标题/主图/详情和曝光数据，我判断先改标题、主图还是咨询话术。`;
  return `你发我产品类目和客单价，我先判断适合内容引流、客服承接，还是两者一起做。`;
}

function detailFor(p, cfg) {
  return [
    `适合${p.target}。当前输入平台为「${cfg.platform}」，类目为「${cfg.category}」。`,
    `交付包括：${p.deliverables.join("、")}。`,
    `价格带参考：${p.price}。先用小单验证真实问题，再升级成项目交付。`,
    "边界说清楚：不承诺替代全部人工，不做违规自动化，不绕平台风控；默认保留人工确认和兜底。",
  ];
}

function faqFor(p) {
  return [
    ["多久能交付？", p.id === "P0" ? "诊断通常1天内给结论，项目类按资料完整度分3-7天试跑。" : "资料齐全时3-7天可以跑出第一版，后续按咨询反馈优化。"],
    ["需要给账号吗？", "先不需要。先做资料诊断和话术整理，涉及平台配置时只拿必要权限，并保留人工确认。"],
    ["为什么不直接全自动？", "客服场景有价格、投诉、异常订单等高风险问题，先分级处理更稳。简单问题自动接，复杂问题转人工。"],
  ];
}

function makeEvidenceRows(cfg) {
  return cfg.customerEvidence.map((item, index) => {
    const [name, rest] = item.includes("：") ? item.split(/：(.+)/) : [`证据${index + 1}`, item];
    return [name.trim(), rest.trim(), inferEvidenceUse(rest), inferProducts(rest)];
  });
}

function inferEvidenceUse(text) {
  if (/风险|企微|接口|人工确认/.test(text)) return "用于强调低风险、辅助建议、人工确认边界。";
  if (/内容|脚本|视频|获客/.test(text)) return "用于证明内容获客和客服承接可以组合销售。";
  if (/知识库|SOP|售后|FAQ|话术/.test(text)) return "用于证明知识库、客服SOP和售后口径有真实价值。";
  return "用于增强详情页信任感，证明服务来自真实客户问题。";
}

function inferProducts(text) {
  const ids = [];
  if (/诊断|判断|不理解|预算/.test(text)) ids.push("P0");
  if (/知识库|SOP|售后|FAQ|话术/.test(text)) ids.push("P1");
  if (/客服|自动|搭建|咨询/.test(text)) ids.push("P2");
  if (/闲鱼|上架|主图|标题/.test(text)) ids.push("P3");
  if (/内容|脚本|视频|获客/.test(text)) ids.push("P4");
  return ids.length ? ids.join("/") : "P0/P1/P2";
}

function makeCards(products) {
  return products.map((p, i) => ({
    file: `${String(i + 1).padStart(2, "0")}-${p.name.replace(/[\\/:*?"<>|+]/g, "")}.png`,
    label: p.role,
    title: p.name,
    subtitle: p.promise,
    chips: p.deliverables.slice(0, 3),
    cta: p.opener,
    accent: p.accent,
    soft: "F8FAFC",
  }));
}

function markdownPack(cfg, products, evidenceRows) {
  return `# ${cfg.outputName}

生成时间：${new Date().toLocaleString("zh-CN")}

## 输入摘要

- 平台：${cfg.platform}
- 类目：${cfg.category}
- 价格带：${cfg.priceBand}
- 生成策略：先用诊断/小单拿咨询，再升级知识库、轻量搭建、上架陪跑和内容承接。

## 上架商品矩阵

${products.map((p) => `### ${p.id} ${p.name}

标题：${p.title}

建议价格：${p.price}

一句话卖点：${p.promise}

适合客户：${p.target}

交付清单：
${p.deliverables.map((item) => `- ${item}`).join("\n")}

详情页文案：
${p.detail.map((item) => `- ${item}`).join("\n")}

FAQ：
${p.faq.map(([q, a]) => `- Q：${q}\n  A：${a}`).join("\n")}

咨询开场：${p.opener}
`).join("\n---\n\n")}

## 客户证据怎么用

${evidenceRows.map((row) => `- ${row[0]}：${row[1]}；用法：${row[2]}；对应商品：${row[3]}`).join("\n")}

## 详情页固定结构

1. 痛点：回复慢、漏单、客服口径乱、售后难统一、新客服培训慢。
2. 交付：知识库、FAQ、客服SOP、AI回复草稿、人工兜底、数据复盘。
3. 边界：不承诺替代全部人工，不做违规自动化，不绕平台风控。
4. 行动：让客户发平台、类目、每天咨询量、3个高频问题。

## 7天优化节奏

- 第1天：发布P0/P1/P2，先跑诊断、知识库、轻量搭建三个入口。
- 第2天：补P3/P4，拉高客单价并覆盖闲鱼上架和内容获客需求。
- 第3天：看曝光，低曝光改平台词、类目词、交付词。
- 第4天：看浏览/咨询比，浏览高咨询低就改主图和详情页前三屏。
- 第5天：把客户反复问的问题补进FAQ。
- 第6天：做基础版、标准版、陪跑版三档对比。
- 第7天：保留高点击标题和主图，淘汰低质量流量版本。
`;
}

function manualMarkdown(cfg, products) {
  return `# ${cfg.outputName}执行手册

## 一键生成后先看哪里

先看 docs/闲鱼上架文案.md，确认标题、价格带、详情页边界；再看 data/商品图数据.json，确认每张图的标题、卖点和行动指令；最后看 office/ 里的Word、Excel和PPT是否需要发给合作方。

## 发布顺序

1. 先发${products[0].name}，用低门槛问题收集真实咨询。
2. 再发${products[1].name}和${products[2].name}，承接有明确店铺问题的客户。
3. 最后发${products[3].name}和${products[4].name}，提升客单价。

## 每次重新生成需要填什么

- 平台：例如闲鱼、抖音、小红书。
- 类目：例如生鲜电商、服饰、礼品、本地生活。
- 价格带：例如199诊断、999轻量、2999项目。
- 客户证据：真实聊天、成交截图、交付结果、客户顾虑。

## 风险边界

所有发布、改价、私信和账号授权都保留人工确认。脚本只生成素材，不自动登录平台、不自动发布、不自动群发。`;
}

function wechatMarkdown(cfg, products, evidenceRows) {
  return `# 发微信版-${cfg.outputName}汇总

这次已经把「${cfg.platform} / ${cfg.category} / ${cfg.priceBand}」整理成可重复生成的上架包。

核心打法：不卖空泛AI，卖能落地的客服流程。先用诊断和小单拿咨询，再升级到知识库、AI客服轻量搭建、闲鱼上架陪跑、内容获客客服承接。

先上架这几条：

${products.map((p) => `- ${p.name}：${p.price}。${p.promise}`).join("\n")}

客户证据用法：

${evidenceRows.map((row) => `- ${row[0]}：${row[2]}`).join("\n")}

下次只需要改输入文件里的平台、类目、价格带、客户证据，再运行一键脚本即可重新生成。`;
}

function officePs() {
  return String.raw`
param([string]$DataPath, [string]$OutDir)
$ErrorActionPreference = "Stop"
$data = Get-Content -LiteralPath $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "office") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "images") | Out-Null

function Release-Com($obj) {
  if ($null -ne $obj) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
}

function RgbFromHex([string]$hex) {
  $r = [Convert]::ToInt32($hex.Substring(0,2), 16)
  $g = [Convert]::ToInt32($hex.Substring(2,2), 16)
  $b = [Convert]::ToInt32($hex.Substring(4,2), 16)
  return $r + ($g * 256) + ($b * 65536)
}

try {
  $excel = New-Object -ComObject Excel.Application
  $excel.Visible = $false
  $excel.DisplayAlerts = $false
  $wb = $excel.Workbooks.Add()
  while ($wb.Worksheets.Count -lt 3) { [void]$wb.Worksheets.Add() }
  $tables = @(
    @("商品矩阵", $data.productsHeaders, $data.productsRows),
    @("上架文案", $data.listingHeaders, $data.listingRows),
    @("客户证据", $data.evidenceHeaders, $data.evidenceRows)
  )
  for ($si = 0; $si -lt $tables.Count; $si++) {
    $ws = $wb.Worksheets.Item($si + 1)
    $ws.Name = $tables[$si][0]
    $headers = $tables[$si][1]
    $rows = $tables[$si][2]
    for ($c = 0; $c -lt $headers.Count; $c++) {
      $cell = $ws.Cells.Item(1, $c + 1)
      $cell.Value2 = [string]$headers[$c]
      $cell.Font.Bold = $true
      $cell.Interior.Color = 0x111827
      $cell.Font.Color = 0xFFFFFF
    }
    for ($r = 0; $r -lt $rows.Count; $r++) {
      $row = $rows[$r]
      for ($c = 0; $c -lt $row.Count; $c++) {
        $ws.Cells.Item($r + 2, $c + 1).Value2 = [string]$row[$c]
      }
    }
    $ws.Columns.AutoFit() | Out-Null
  }
  $wb.SaveAs((Join-Path $OutDir "office\闲鱼AI客服商品矩阵.xlsx"), 51)
  $wb.Close($true)
  $excel.Quit()
  Release-Com $wb
  Release-Com $excel
} catch {
  Write-Warning ("Excel export skipped: " + $_.Exception.Message)
}

try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  foreach ($docItem in $data.wordDocs) {
    $doc = $word.Documents.Add()
    $sel = $word.Selection
    foreach ($rawLine in ([string]$docItem.content -split [char]10)) {
      $line = $rawLine.TrimEnd([char]13)
      if ($line.StartsWith("# ")) {
        $sel.Font.Name = "Microsoft YaHei"; $sel.Font.Size = 20; $sel.Font.Bold = 1
        $sel.TypeText($line.Substring(2)); $sel.TypeParagraph()
      } elseif ($line.StartsWith("## ")) {
        $sel.Font.Name = "Microsoft YaHei"; $sel.Font.Size = 15; $sel.Font.Bold = 1
        $sel.TypeText($line.Substring(3)); $sel.TypeParagraph()
      } elseif ($line.StartsWith("### ")) {
        $sel.Font.Name = "Microsoft YaHei"; $sel.Font.Size = 12; $sel.Font.Bold = 1
        $sel.TypeText($line.Substring(4)); $sel.TypeParagraph()
      } elseif ($line.Trim().Length -eq 0) {
        $sel.TypeParagraph()
      } else {
        $sel.Font.Name = "Microsoft YaHei"; $sel.Font.Size = 10.5; $sel.Font.Bold = 0
        $sel.TypeText($line); $sel.TypeParagraph()
      }
    }
    $doc.SaveAs2((Join-Path $OutDir ("office\" + [string]$docItem.file)), 16)
    $doc.Close($true)
    Release-Com $doc
  }
  $word.Quit()
  Release-Com $word
} catch {
  Write-Warning ("Word export skipped: " + $_.Exception.Message)
}

try {
  $ppt = New-Object -ComObject PowerPoint.Application
  $deck = $ppt.Presentations.Add()
  $deck.PageSetup.SlideWidth = 1080
  $deck.PageSetup.SlideHeight = 1080
  foreach ($card in $data.cards) {
    $slide = $deck.Slides.Add($deck.Slides.Count + 1, 12)
    $accent = [string]$card.accent
    $bg = $slide.Shapes.AddShape(1, 0, 0, 1080, 1080)
    $bg.Fill.ForeColor.RGB = RgbFromHex "FAFAF7"
    $bg.Line.ForeColor.RGB = RgbFromHex "FAFAF7"
    $bar = $slide.Shapes.AddShape(1, 0, 0, 1080, 82)
    $bar.Fill.ForeColor.RGB = RgbFromHex $accent
    $bar.Line.ForeColor.RGB = RgbFromHex $accent

    $label = $slide.Shapes.AddTextbox(1, 64, 24, 430, 36)
    $label.TextFrame.TextRange.Text = [string]$card.label
    $label.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
    $label.TextFrame.TextRange.Font.Size = 24
    $label.TextFrame.TextRange.Font.Bold = -1
    $label.TextFrame.TextRange.Font.Color.RGB = RgbFromHex "FFFFFF"

    $title = $slide.Shapes.AddTextbox(1, 64, 150, 900, 96)
    $title.TextFrame.TextRange.Text = [string]$card.title
    $title.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
    $title.TextFrame.TextRange.Font.Size = 54
    $title.TextFrame.TextRange.Font.Bold = -1
    $title.TextFrame.TextRange.Font.Color.RGB = RgbFromHex "111827"

    $subtitle = $slide.Shapes.AddTextbox(1, 68, 270, 900, 72)
    $subtitle.TextFrame.TextRange.Text = [string]$card.subtitle
    $subtitle.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
    $subtitle.TextFrame.TextRange.Font.Size = 30
    $subtitle.TextFrame.TextRange.Font.Color.RGB = RgbFromHex "374151"

    $y = 438
    foreach ($chip in $card.chips) {
      $dot = $slide.Shapes.AddShape(9, 76, $y + 12, 22, 22)
      $dot.Fill.ForeColor.RGB = RgbFromHex $accent
      $dot.Line.ForeColor.RGB = RgbFromHex $accent
      $txt = $slide.Shapes.AddTextbox(1, 124, $y, 820, 50)
      $txt.TextFrame.TextRange.Text = [string]$chip
      $txt.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
      $txt.TextFrame.TextRange.Font.Size = 34
      $txt.TextFrame.TextRange.Font.Bold = -1
      $txt.TextFrame.TextRange.Font.Color.RGB = RgbFromHex "111827"
      $y += 92
    }

    $ctaBox = $slide.Shapes.AddShape(1, 64, 890, 952, 96)
    $ctaBox.Fill.ForeColor.RGB = RgbFromHex $accent
    $ctaBox.Line.ForeColor.RGB = RgbFromHex $accent
    $cta = $slide.Shapes.AddTextbox(1, 96, 914, 880, 42)
    $cta.TextFrame.TextRange.Text = [string]$card.cta
    $cta.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
    $cta.TextFrame.TextRange.Font.Size = 28
    $cta.TextFrame.TextRange.Font.Bold = -1
    $cta.TextFrame.TextRange.Font.Color.RGB = RgbFromHex "FFFFFF"
  }

  for ($i = 1; $i -le $deck.Slides.Count; $i++) {
    $file = Join-Path $OutDir ("images\" + [string]$data.cards[$i - 1].file)
    $deck.Slides.Item($i).Export($file, "PNG", 1080, 1080)
  }
  $deck.SaveAs((Join-Path $OutDir "office\闲鱼商品图源文件.pptx"), 24)
  $deck.Close()
  $ppt.Quit()
  Release-Com $deck
  Release-Com $ppt
} catch {
  Write-Warning ("PowerPoint image export skipped: " + $_.Exception.Message)
}
`;
}

async function writePack(cfg, args) {
  const products = makeProducts(cfg);
  const evidenceRows = makeEvidenceRows(cfg);
  const cards = makeCards(products);
  const outDir = path.resolve(args["out-dir"] || path.join(DEFAULT_ROOT, `${timestamp()}-${slug(cfg.platform)}-${slug(cfg.category)}`));

  const dirs = ["docs", "data", "images", "office", "scripts"].map((dir) => path.join(outDir, dir));
  await Promise.all(dirs.map((dir) => fs.mkdir(dir, { recursive: true })));

  const productsHeaders = ["ID", "商品", "定位", "价格带", "标题", "一句话卖点", "目标客户", "交付清单", "咨询开场"];
  const productsRows = products.map((p) => [p.id, p.name, p.role, p.price, p.title, p.promise, p.target, p.deliverables.join("\n"), p.opener]);
  const listingHeaders = ["ID", "标题", "价格", "详情页文案", "FAQ", "咨询回复"];
  const listingRows = products.map((p) => [p.id, p.title, p.price, p.detail.join("\n"), p.faq.map(([q, a]) => `Q：${q}\nA：${a}`).join("\n"), p.opener]);
  const evidenceHeaders = ["证据来源", "证据内容", "上架用法", "对应商品"];

  const packMd = markdownPack(cfg, products, evidenceRows);
  const manualMd = manualMarkdown(cfg, products);
  const wechatMd = wechatMarkdown(cfg, products, evidenceRows);
  const data = {
    input: cfg,
    productsHeaders,
    productsRows,
    listingHeaders,
    listingRows,
    evidenceHeaders,
    evidenceRows,
    cards,
    wordDocs: [
      { file: "闲鱼AI客服上架执行手册.docx", content: manualMd },
      { file: "发微信版-闲鱼AI客服上架汇总.docx", content: wechatMd },
    ],
  };

  await fs.writeFile(path.join(outDir, "README.md"), readme(outDir), "utf8");
  await fs.writeFile(path.join(outDir, "docs", "闲鱼上架文案.md"), packMd, "utf8");
  await fs.writeFile(path.join(outDir, "docs", "执行手册.md"), manualMd, "utf8");
  await fs.writeFile(path.join(outDir, "docs", "微信汇总.md"), wechatMd, "utf8");
  await fs.writeFile(path.join(outDir, "data", "input.json"), JSON.stringify(cfg, null, 2), "utf8");
  await fs.writeFile(path.join(outDir, "data", "商品矩阵.csv"), toCsv(productsHeaders, productsRows), "utf8");
  await fs.writeFile(path.join(outDir, "data", "闲鱼上架文案.csv"), toCsv(listingHeaders, listingRows), "utf8");
  await fs.writeFile(path.join(outDir, "data", "客户证据映射.csv"), toCsv(evidenceHeaders, evidenceRows), "utf8");
  await fs.writeFile(path.join(outDir, "data", "商品图数据.json"), JSON.stringify({ cards }, null, 2), "utf8");
  await fs.writeFile(path.join(outDir, "data", "generator.data.json"), JSON.stringify(data, null, 2), "utf8");
  await fs.writeFile(path.join(outDir, "scripts", "export_office_and_images.ps1"), `\ufeff${officePs()}`, "utf8");

  if (!args["skip-office"]) {
    const ps = spawnSync("powershell.exe", [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      path.join(outDir, "scripts", "export_office_and_images.ps1"),
      "-DataPath",
      path.join(outDir, "data", "generator.data.json"),
      "-OutDir",
      outDir,
    ], { encoding: "utf8" });
    if (ps.status !== 0) {
      await fs.writeFile(path.join(outDir, "office", "office_export_error.log"), `${ps.stdout}\n${ps.stderr}`, "utf8");
      console.warn("Office/PPT导出失败，已写入 office/office_export_error.log；Markdown/CSV/JSON 已生成。");
    }
  }

  return { outDir, products: products.length, cards: cards.length };
}

function readme(outDir) {
  return `# 闲鱼AI客服一键生成结果

目录：${outDir}

- docs/：闲鱼上架文案、执行手册、微信汇总。
- data/：可复用输入、CSV表格、商品图数据JSON。
- images/：PowerPoint导出的闲鱼商品图PNG。
- office/：Word、Excel、PPT源文件。
- scripts/：本次导出的Office和图片生成脚本。
`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(`用法：
node work/xianyu_ai_service/generate_xianyu_pack.mjs --input work/xianyu_ai_service/xianyu_pack_input.example.json
node work/xianyu_ai_service/generate_xianyu_pack.mjs --platform=闲鱼 --category=生鲜AI客服 --price-band=199诊断,999轻量 --evidence="王鲜记：知识库和售后话术|Bryce：担心企微风险"

可选：
--out-dir=outputs/xxx
--skip-office 只生成 Markdown/CSV/JSON，不调用 Office 导出图片和 docx/xlsx/pptx
`);
    return;
  }
  const cfg = await collectInput(args);
  const result = await writePack(cfg, args);
  console.log(JSON.stringify(result, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exit(1);
  });
}
