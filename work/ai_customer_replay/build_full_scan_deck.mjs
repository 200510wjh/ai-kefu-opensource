import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "C:/Users/Administrator/Documents/运营/outputs/AI客服客户洞察与成交复制PPT.pptx";
const QA_DIR = "C:/Users/Administrator/Documents/运营/work/ai_customer_replay/qa_full";

async function bytes(value) {
  if (value?.arrayBuffer) return new Uint8Array(await value.arrayBuffer());
  if (value instanceof Uint8Array) return value;
  if (value?.buffer) return new Uint8Array(value.buffer);
  return new Uint8Array(value);
}

function addText(slide, text, position, style = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    fontFace: "Microsoft YaHei",
    fontSize: style.fontSize ?? 20,
    bold: style.bold ?? false,
    color: style.color ?? "slate-800",
  };
  return box;
}

function rect(slide, position, fill = "white", line = "slate-200") {
  return slide.shapes.add({
    geometry: "roundRect",
    position,
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: "rounded-sm",
  });
}

function title(slide, kicker, text) {
  addText(slide, kicker, { left: 72, top: 44, width: 640, height: 24 }, {
    fontSize: 14,
    bold: true,
    color: "teal-700",
  });
  addText(slide, text, { left: 72, top: 78, width: 980, height: 64 }, {
    fontSize: 36,
    bold: true,
    color: "slate-950",
  });
}

function footer(slide, n) {
  addText(slide, String(n).padStart(2, "0"), { left: 1164, top: 650, width: 42, height: 22 }, {
    fontSize: 13,
    bold: true,
    color: "slate-400",
  });
}

function bullets(slide, items, left, top, width, gap = 54, color = "teal-600") {
  items.forEach((item, i) => {
    slide.shapes.add({
      geometry: "ellipse",
      position: { left, top: top + i * gap + 9, width: 10, height: 10 },
      fill: i % 2 === 0 ? color : "amber-500",
      line: { style: "solid", fill: "none", width: 0 },
    });
    addText(slide, item, { left: left + 26, top: top + i * gap, width, height: 42 }, {
      fontSize: 20,
      color: "slate-800",
    });
  });
}

function makeDeck() {
  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    addText(s, "AI客服客户洞察与成交复制", { left: 72, top: 112, width: 760, height: 120 }, {
      fontSize: 52,
      bold: true,
      color: "slate-950",
    });
    addText(s, "微信通讯录管理 + 聊天窗口 + 本地微信文件扫描版", { left: 76, top: 252, width: 720, height: 44 }, {
      fontSize: 24,
      color: "slate-600",
    });
    rect(s, { left: 868, top: 100, width: 294, height: 414 }, "white");
    addText(s, "这次补扫", { left: 908, top: 144, width: 210, height: 30 }, {
      fontSize: 26,
      bold: true,
      color: "teal-700",
    });
    bullets(s, [
      "ai客服 / ai客户",
      "客户 / 客服",
      "saas / 抖店",
      "企业微 / 公众号",
      "淘宝 / 抖音 / 系统",
    ], 908, 204, 210, 54);
    footer(s, 1);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "扫描结论", "相关客户不是少，是分散在不同备注词里");
    const cards = [
      ["已验证证据", "Bryce、Daisy、陈-timeless、大头哥、王超", "聊天或文件里已经看到明确需求/阻力"],
      ["通讯录证据", "木木、大魔王、魁星Ai备...、我来依旧、三w、Mr.C、岁月留痕", "需要逐一补聊天原文"],
      ["文件资产", "王鲜记、Recardify、佰社区、小危AI电信PPT", "可以直接沉淀成产品包"],
    ];
    cards.forEach(([h, names, desc], i) => {
      const left = 88 + i * 370;
      rect(s, { left, top: 202, width: 318, height: 280 }, i === 0 ? "teal-50" : "slate-50");
      addText(s, h, { left: left + 26, top: 236, width: 250, height: 34 }, {
        fontSize: 26,
        bold: true,
        color: "slate-950",
      });
      addText(s, names, { left: left + 26, top: 300, width: 252, height: 82 }, {
        fontSize: 19,
        color: "slate-800",
      });
      addText(s, desc, { left: left + 26, top: 410, width: 252, height: 42 }, {
        fontSize: 18,
        bold: true,
        color: i === 0 ? "teal-700" : "amber-700",
      });
    });
    footer(s, 2);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "已成交/已验证", "先复制王超和王鲜记这类小产品包");
    bullets(s, [
      "王超：抖音、淘宝、公众号、微信群咨询，客服助理已能自动承接。",
      "王鲜记：商品知识、客服话术、客服系统、AI内容生产报价，交付资产最完整。",
      "这类客户买的不是“大AI”，而是少漏单、快回复、商品问题有人先接住。",
      "复制方向：商品知识库 + FAQ + 客服话术 + 自动承接 + 7天复盘。",
    ], 112, 190, 820, 70);
    rect(s, { left: 930, top: 188, width: 210, height: 300 }, "white", "teal-100");
    addText(s, "先卖这个", { left: 962, top: 224, width: 150, height: 30 }, {
      fontSize: 25,
      bold: true,
      color: "teal-800",
    });
    addText(s, "商品知识库\n客服话术\n自动承接\n复盘续费", { left: 962, top: 288, width: 150, height: 150 }, {
      fontSize: 25,
      bold: true,
      color: "slate-950",
    });
    footer(s, 3);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "没成交原因", "大多数不是拒绝AI，而是卡在4个阻力");
    const rows = [
      ["接口风险", "Bryce", "怕企微接口关闭，已有客服团队"],
      ["已有替代", "Daisy", "关键词客服已经能解决一部分问题"],
      ["价格部署", "大头哥", "想装进已有系统，但对一次性费用敏感"],
      ["时间断点", "陈-timeless", "出差后中断，需要轻量复盘推进"],
    ];
    rows.forEach(([factor, customer, why], i) => {
      const top = 178 + i * 86;
      rect(s, { left: 96, top, width: 980, height: 58 }, i % 2 === 0 ? "slate-50" : "teal-50");
      addText(s, factor, { left: 124, top: top + 12, width: 160, height: 26 }, {
        fontSize: 23,
        bold: true,
        color: "slate-950",
      });
      addText(s, customer, { left: 308, top: top + 12, width: 150, height: 26 }, {
        fontSize: 22,
        bold: true,
        color: "teal-700",
      });
      addText(s, why, { left: 488, top: top + 12, width: 520, height: 26 }, {
        fontSize: 21,
        color: "slate-800",
      });
    });
    footer(s, 4);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "客户分层", "下一轮跟进按产品包分，而不是按昵称分");
    const groups = [
      ["电商客服", "王超 / 三w / 岁月留痕 / 王鲜记", "多渠道客服包"],
      ["企业微信", "Bryce / Mr.C / 我是超人", "低风险辅助包"],
      ["已有系统", "大头哥 / Daisy", "升级或嵌入包"],
      ["企业大单", "陈-timeless / 小危AI电信方案", "分阶段集成包"],
      ["待判定", "木木 / 大魔王 / 魁星Ai备... / 我来依旧 / Li.", "先补需求原话"],
    ];
    groups.forEach(([name, customers, product], i) => {
      const top = 168 + i * 78;
      addText(s, name, { left: 94, top, width: 150, height: 30 }, {
        fontSize: 24,
        bold: true,
        color: "slate-950",
      });
      addText(s, customers, { left: 282, top, width: 500, height: 30 }, {
        fontSize: 21,
        color: "slate-800",
      });
      rect(s, { left: 832, top: top - 4, width: 244, height: 40 }, "white", "teal-200");
      addText(s, product, { left: 856, top: top + 6, width: 198, height: 22 }, {
        fontSize: 18,
        bold: true,
        color: "teal-800",
      });
    });
    footer(s, 5);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "下次直接卖什么", "推荐从4个可复制产品开始");
    const products = [
      ["P0", "商品知识库+客服话术包", "最快成交，交付边界清楚"],
      ["P0", "多渠道电商客服包", "复用王超群场景，卖少漏单"],
      ["P1", "低风险企微辅助包", "解决Bryce/Mr.C的接口顾虑"],
      ["P1", "SaaS系统嵌入包", "对应大头哥已有系统需求"],
    ];
    products.forEach(([p, h, b], i) => {
      const left = 92 + (i % 2) * 540;
      const top = 188 + Math.floor(i / 2) * 166;
      rect(s, { left, top, width: 464, height: 124 }, "slate-50");
      addText(s, p, { left: left + 24, top: top + 30, width: 58, height: 28 }, {
        fontSize: 24,
        bold: true,
        color: i < 2 ? "teal-700" : "amber-700",
      });
      addText(s, h, { left: left + 96, top: top + 28, width: 320, height: 30 }, {
        fontSize: 23,
        bold: true,
        color: "slate-950",
      });
      addText(s, b, { left: left + 96, top: top + 68, width: 320, height: 28 }, {
        fontSize: 19,
        color: "slate-700",
      });
    });
    footer(s, 6);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "销售话术", "先确认损失，再演示同类场景");
    bullets(s, [
      "你们现在每天最多人问的10个问题是什么？有没有晚上或忙的时候接不住？",
      "我先不做大系统，先把这10个高频问题做成能接住咨询的小包。",
      "如果你已有关键词客服，我给你演示3个关键词接不住但AI能接住的问题。",
      "如果你担心企微接口，我们先做辅助回复和人工确认，不依赖高风险接口。",
      "7天后看咨询量、漏单、人工接管比例，再决定续费或扩渠道。",
    ], 112, 174, 900, 62);
    footer(s, 7);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "还需要补看的客户", "这些不是忽略，而是证据级别要标清");
    bullets(s, [
      "jack / Torre / 小危：搜索记录出现AI客服相关，但主微信窗口卡空白，需下次继续打开。",
      "木木 / 大魔王 / 魁星Ai备... / 我来依旧 / 张口就来：通讯录或AI备注有线索，需补行业和聊天原话。",
      "Li. / m.one / 章扬腾：客户标签存在，但AI客服需求未验证，暂不放主推名单。",
      "每个客户只补四项：需求原话、发过的方案/报价、对方最后一句、当前成交状态。",
    ], 112, 194, 900, 66, "rose-500");
    addText(s, "结论：先卖可交付的小包，边成交边补台账。", { left: 136, top: 548, width: 860, height: 36 }, {
      fontSize: 26,
      bold: true,
      color: "teal-800",
    });
    footer(s, 8);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "标签入口核验", "没有独立AI标签，AI线索主要藏在备注里");
    const rows = [
      ["看见的标签", "无标签、爱人、大人、1、老板、一队、客户、不能看的人"],
      ["客户标签", "客户 (19)，已逐屏核验成员"],
      ["未发现", "独立 ai客服 / ai客户 / AI客服 标签"],
      ["补漏方式", "必须继续用备注关键词：ai客服、ai客户、Ai备、saas、抖店、企业微"],
    ];
    rows.forEach(([h, b], i) => {
      const top = 178 + i * 86;
      rect(s, { left: 96, top, width: 960, height: 58 }, i % 2 === 0 ? "slate-50" : "teal-50");
      addText(s, h, { left: 126, top: top + 12, width: 170, height: 28 }, {
        fontSize: 23,
        bold: true,
        color: "slate-950",
      });
      addText(s, b, { left: 326, top: top + 12, width: 660, height: 28 }, {
        fontSize: 21,
        color: i === 2 ? "rose-700" : "slate-800",
        bold: i === 2,
      });
    });
    footer(s, 9);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "微信文件证据", "已经有一批能直接复制成交的交付资产");
    const assets = [
      ["王鲜记", "客服话术表+客服系统ZIP+内容生产报价", "最优先复制"],
      ["AI客服ZIP", "月卡198/年卡980/店群1380/Ultra2880+知识库模板", "低价引流"],
      ["Recardify", "服饰顾问人设+新老客户话术+Demo¥999", "低价试单"],
      ["小危AI", "企业微信/WhatsApp/App/电话/工单全渠道", "中大客户售前"],
      ["股东协议", "列出王鲜记、1688 AI客服、新能源AI客服等项目池", "公司化资产"],
    ];
    assets.forEach(([name, evidence, use], i) => {
      const top = 168 + i * 78;
      rect(s, { left: 92, top, width: 984, height: 58 }, i % 2 === 0 ? "white" : "teal-50");
      addText(s, name, { left: 122, top: top + 12, width: 130, height: 26 }, {
        fontSize: 23,
        bold: true,
        color: "slate-950",
      });
      addText(s, evidence, { left: 278, top: top + 12, width: 560, height: 26 }, {
        fontSize: 20,
        color: "slate-800",
      });
      addText(s, use, { left: 878, top: top + 12, width: 150, height: 26 }, {
        fontSize: 20,
        bold: true,
        color: i < 2 ? "teal-800" : "amber-700",
      });
    });
    addText(s, "结论：先用198/980这类低价SaaS成交，再加卖知识库、话术配置和代运营。", { left: 112, top: 572, width: 940, height: 34 }, {
      fontSize: 23,
      bold: true,
      color: "teal-800",
    });
    footer(s, 10);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "本次交付物怎么用", "PPT讲方向，Word看判断，Excel做跟进");
    const rows = [
      ["PPT", "看客户分层、未成交原因、下次先卖什么产品包", "给自己复盘或讲给团队听"],
      ["Word", "看完整证据、客户台账、文件资产、产品复制逻辑", "做销售策略和产品包装"],
      ["Excel", "按证据级别/优先级/推荐产品包筛选客户", "每天跟进客户时直接用"],
    ];
    rows.forEach(([name, desc, use], i) => {
      const top = 190 + i * 112;
      rect(s, { left: 106, top, width: 930, height: 78 }, i === 2 ? "teal-50" : "slate-50");
      addText(s, name, { left: 142, top: top + 22, width: 100, height: 28 }, {
        fontSize: 26,
        bold: true,
        color: i === 2 ? "teal-800" : "slate-950",
      });
      addText(s, desc, { left: 278, top: top + 15, width: 430, height: 34 }, {
        fontSize: 20,
        color: "slate-800",
      });
      addText(s, use, { left: 748, top: top + 15, width: 230, height: 34 }, {
        fontSize: 20,
        bold: true,
        color: "amber-700",
      });
    });
    addText(s, "Excel文件名：AI客服客户扫描台账.xlsx", { left: 132, top: 566, width: 760, height: 32 }, {
      fontSize: 24,
      bold: true,
      color: "teal-800",
    });
    footer(s, 11);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "完成度审计", "哪些已经证实，哪些还需要聊天窗口恢复后补");
    const rows = [
      ["已完成", "客户(19)标签全量核验；AI关键词补扫；无独立AI标签确认"],
      ["已完成", "19个本地文件证据抽取；王鲜记/AI客服ZIP/Recardify/小危AI已沉淀产品包"],
      ["已完成", "DOCX、PPTX、XLSX三份交付物生成并验证"],
      ["部分完成", "Bryce、Daisy、陈-timeless、大头哥、王超有聊天/场景证据"],
      ["未完全验证", "木木、大魔王、魁星Ai备...、三w、郑文凯等仍需主微信聊天原文"],
    ];
    rows.forEach(([state, evidence], i) => {
      const top = 168 + i * 76;
      rect(s, { left: 94, top, width: 970, height: 56 }, state === "未完全验证" ? "rose-50" : i % 2 ? "white" : "teal-50");
      addText(s, state, { left: 124, top: top + 13, width: 150, height: 26 }, {
        fontSize: 22,
        bold: true,
        color: state === "未完全验证" ? "rose-700" : state === "部分完成" ? "amber-700" : "teal-800",
      });
      addText(s, evidence, { left: 306, top: top + 13, width: 700, height: 26 }, {
        fontSize: 20,
        color: "slate-800",
      });
    });
    addText(s, "原则：不把标签证据伪装成聊天结论；没有付款/聊天原文的客户，继续标为待补证据。", { left: 116, top: 572, width: 900, height: 32 }, {
      fontSize: 22,
      bold: true,
      color: "slate-900",
    });
    footer(s, 12);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "客户标签19人核验", "这页来自左侧标签 客户 (19)，不是搜索框猜测");
    const cols = [
      ["Bryce", "陈-timeless", "Daisy", "大魔王", "大头哥"],
      ["呼啦啦", "魁星Ai备...", "Li.", "m.one", "Mr.C"],
      ["木木", "曹扬腾", "三w", "岁月留痕", "王超"],
      ["我来依旧", "我是超人", "真棒", "郑文凯", ""],
    ];
    cols.forEach((items, c) => {
      const left = 92 + c * 270;
      rect(s, { left, top: 180, width: 230, height: 312 }, c === 0 ? "teal-50" : "white");
      items.filter(Boolean).forEach((name, i) => {
        addText(s, name, { left: left + 24, top: 214 + i * 50, width: 170, height: 28 }, {
          fontSize: 22,
          bold: /Bryce|陈-timeless|Daisy|大头哥|王超|魁星/.test(name),
          color: /Bryce|陈-timeless|Daisy|大头哥|王超|魁星/.test(name) ? "teal-800" : "slate-800",
        });
      });
    });
    addText(s, "额外注意：张口就来有 ai客... 备注，但搜索结果未显示客户标签，所以单独列为AI备注待判定，不混入客户(19)。", { left: 112, top: 548, width: 930, height: 42 }, {
      fontSize: 22,
      bold: true,
      color: "rose-700",
    });
    footer(s, 13);
  }

  return deck;
}

async function main() {
  await fs.mkdir(QA_DIR, { recursive: true });
  const deck = makeDeck();
  for (const [index, slide] of deck.slides.items.entries()) {
    const png = await slide.export("png");
    await fs.writeFile(`${QA_DIR}/slide-${String(index + 1).padStart(2, "0")}.png`, await bytes(png));
  }
  const file = await PresentationFile.exportPptx(deck);
  await file.save(OUT);
  console.log(OUT);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
