import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = "C:/Users/Administrator/Documents/运营";
const OUT_DIR = path.join(ROOT, "outputs", "闲鱼高端AI客服上架包");
const MD = path.join(OUT_DIR, "发微信版-闲鱼AI客服自动化上架与优化总结.md");
const DOCX = path.join(OUT_DIR, "发微信版-闲鱼AI客服自动化上架与优化总结.docx");
const PS = path.join(OUT_DIR, "build_wechat_summary_doc.ps1");

const content = `# 闲鱼AI客服自动化上架与优化总结（发微信版）

## 1. 总结一句话

我现在最适合在闲鱼卖“高端AI客服落地服务”，不是卖低价模板。核心卖点是：帮商家把商品知识、客服话术、售后规则、人工兜底和AI客服系统跑通，解决回复慢、漏单、客服口径乱、新客服培训慢的问题。

## 2. 先上架的商品

### 商品1：抖店淘宝AI客服搭建

标题：抖店淘宝AI客服搭建 商品知识库话术SOP 7天陪跑交付

价格：2999-9800元

卖点：商品知识库、FAQ、客服话术、平台配置、自动回复、人工接管、7天优化。

适合：抖店、淘宝、飞鸽、千牛等每天有重复咨询的商家。

### 商品2：商品知识库 + 客服话术 SOP

标题：商品知识库搭建 客服话术SOP整理 生鲜服饰售后问答包

价格：1999-6800元

卖点：把老板和老客服的经验整理成标准话术，新客服能直接用，后续也能接AI。

适合：生鲜、服饰、礼品、本地生活、软件类目。

### 商品3：高端AI客服系统 + 知识库 + 7天陪跑

标题：高端AI客服系统搭建 知识库SOP 7天陪跑 人工兜底

价格：9800-19800元

卖点：不是只搭工具，而是把客服流程跑通，包含诊断、配置、试运行、复盘。

适合：已有订单和客服团队，想直接落地提效的商家。

### 商品4：企业微信/私域AI客服辅助

标题：企业微信私域AI客服辅助 知识库问答 人工确认低风险方案

价格：6800-19800元

卖点：AI先生成建议，人工确认后发送，解决企微接口风险和误回复顾虑。

适合：私域、企微、社群、B2B销售线索承接团队。

### 商品5：AI内容生产 + 客服转化包

标题：AI内容生产服务 商品图视频脚本 客服转化话术 月度代运营

价格：7500元/月起

卖点：内容负责引流，客服话术负责承接，把素材生产和成交话术连起来。

适合：需要图文、短视频、脚本、商品卖点和客服转化一起做的商家。

### 筛选入口：199元AI客服诊断

标题：199元AI客服诊断 店铺咨询问题梳理 可抵扣搭建项目款

作用：筛选真实客户，避免9.9低价客户。成交项目后可抵扣。

## 3. 自动化上架准备

闲鱼不建议直接做违规批量自动发布。正确做法是半自动化：

1. 自动生成每个商品的标题、详情页、FAQ、咨询回复。
2. 自动准备首图文案和配图需求。
3. 人工检查后发布，避免错发、违规、夸大承诺。
4. 每天记录曝光、浏览、想要、咨询、成交。
5. 根据数据自动判断要改标题、首图、详情页还是价格。

## 4. 每条商品详情页固定结构

第一屏：你是不是遇到这些问题：客服回复慢、漏单、晚上没人接、售后口径乱、新客服培训慢。

第二屏：我交付什么：知识库、FAQ、话术SOP、平台配置、人工兜底、7天复盘。

第三屏：为什么比模板贵：我卖的是项目交付，不是一个通用模板。

第四屏：适合谁、不适合谁。

第五屏：价格档位、交付周期、常见问题。

最后一句：发我平台+类目+每天咨询量+3个高频问题，我先判断能不能做。

## 5. 优化规则

曝光低：改标题关键词和类目，优先加“抖店、淘宝、千牛、企微、商品知识库、客服SOP”。

浏览高但咨询低：改首图和详情页前三屏，首图要展示交付清单，不要放空泛AI图。

想要多但不咨询：加行动指令，让客户知道发什么信息。

咨询多但不成交：补案例、交付边界、FAQ、价格档位和人工兜底说明。

低价客户太多：把免费咨询改成199诊断抵扣，删除9.9、99元表达。

## 6. 微信客户证据怎么用

王鲜记：最适合复制成商品知识库、客服话术、客服系统、AI内容生产服务。

王超：验证多渠道电商客服承接需求，适合AI客服系统搭建。

Bryce：担心企微风险，所以要卖“辅助模式、人工确认、低风险方案”。

Daisy：已有关键词客服，所以详情页要解释AI和关键词客服的区别。

大头哥：关注SaaS系统和一次性费用，适合卖系统搭建和部署边界清晰的套餐。

陈-timeless：企业级方案可做高端背书，但闲鱼先不要主卖太重的企业集成。

## 7. 7天执行节奏

第1天：发布199诊断、AI客服搭建、知识库SOP三条。

第2天：补高端陪跑包和企微低风险方案。

第3天：看曝光，低曝光商品改标题关键词。

第4天：看浏览和咨询，浏览高咨询低就改首图。

第5天：把客户反复问的问题补进FAQ。

第6天：做基础版、标准版、陪跑版套餐对比。

第7天：保留表现最好的标题和首图，淘汰低质量流量版本。

## 8. 当前已生成文件

文件夹：C:\\Users\\Administrator\\Documents\\运营\\outputs\\闲鱼高端AI客服上架包

包括：上架包Markdown、竞品与商品矩阵Excel、执行手册Word、销售框架PPT、竞品扫描表、商品矩阵、上架文案、7天优化表。
`;

const ps = String.raw`
param([string]$MdPath, [string]$DocxPath)
$ErrorActionPreference = "Stop"
$text = Get-Content -LiteralPath $MdPath -Raw -Encoding UTF8
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Add()
$sel = $word.Selection
foreach ($rawLine in ($text -split [char]10)) {
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
$doc.SaveAs2($DocxPath, 16)
$doc.Close($true)
try { $word.Quit() } catch {}
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
[void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
`;

await fs.mkdir(OUT_DIR, { recursive: true });
await fs.writeFile(MD, content, "utf8");
await fs.writeFile(PS, `\ufeff${ps}`, "utf8");
const result = spawnSync("powershell.exe", [
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  PS,
  "-MdPath",
  MD,
  "-DocxPath",
  DOCX,
], { encoding: "utf8" });

if (result.status !== 0) {
  console.error(result.stdout);
  console.error(result.stderr);
  throw new Error(`Word export failed with status ${result.status}`);
}

console.log(JSON.stringify({ md: MD, docx: DOCX }, null, 2));
