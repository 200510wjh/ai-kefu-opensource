import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "C:/Users/Administrator/Documents/运营/outputs/AI客服客户洞察与成交复制PPT.pptx";
const QA_DIR = "C:/Users/Administrator/Documents/运营/work/ai_customer_replay/qa";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
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

function addRect(slide, position, fill, line = "slate-200") {
  return slide.shapes.add({
    geometry: "roundRect",
    position,
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: "rounded-md",
  });
}

function title(slide, text, kicker) {
  if (kicker) {
    addText(slide, kicker, { left: 72, top: 46, width: 640, height: 26 }, {
      fontSize: 14,
      bold: true,
      color: "teal-700",
    });
  }
  addText(slide, text, { left: 72, top: 82, width: 980, height: 58 }, {
    fontSize: 38,
    bold: true,
    color: "slate-950",
  });
}

function footer(slide, n) {
  addText(slide, String(n).padStart(2, "0"), { left: 1160, top: 650, width: 48, height: 24 }, {
    fontSize: 14,
    bold: true,
    color: "slate-400",
  });
}

function bulletBlock(slide, items, left, top, width, gap = 54) {
  items.forEach((item, i) => {
    slide.shapes.add({
      geometry: "ellipse",
      position: { left, top: top + i * gap + 8, width: 12, height: 12 },
      fill: i % 2 === 0 ? "teal-600" : "amber-500",
      line: { style: "solid", fill: "none", width: 0 },
    });
    addText(slide, item, { left: left + 28, top: top + i * gap, width, height: 42 }, {
      fontSize: 21,
      color: "slate-800",
    });
  });
}

function makeDeck() {
  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    addText(s, "AI客服客户洞察与成交复制", { left: 72, top: 110, width: 790, height: 118 }, {
      fontSize: 54,
      bold: true,
      color: "slate-950",
    });
    addText(s, "从微信客户标签中找到已成交规律、未成交阻力和下一批可复制产品", { left: 76, top: 252, width: 740, height: 72 }, {
      fontSize: 24,
      color: "slate-600",
    });
    addRect(s, { left: 892, top: 88, width: 292, height: 492 }, "white", "slate-200");
    addText(s, "已读取部分微信证据", { left: 930, top: 132, width: 230, height: 32 }, {
      fontSize: 23,
      bold: true,
      color: "teal-700",
    });
    bulletBlock(s, ["Bryce / Daisy", "陈-timeless", "王超群案例", "待续读 jack / Torre"], 932, 210, 210, 70);
    footer(s, 1);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "微信里看到的客户可以先分成四类", "客户池整理");
    const labels = [
      ["已验证", "王超群里客服助理已在承接商品咨询。", "teal-600"],
      ["跟进中", "陈-timeless 因出差和时间断点停住。", "blue-600"],
      ["被替代", "Daisy 已有关键词客服，认为够用。", "amber-500"],
      ["有风险顾虑", "Bryce 担心企微接口关闭和已有客服团队。", "rose-500"],
    ];
    labels.forEach(([h, b, c], i) => {
      const left = 82 + i * 290;
      addRect(s, { left, top: 218, width: 244, height: 250 }, "slate-50", "slate-200");
      s.shapes.add({ geometry: "rect", position: { left, top: 218, width: 244, height: 8 }, fill: c, line: { style: "solid", fill: "none", width: 0 } });
      addText(s, h, { left: left + 22, top: 258, width: 190, height: 36 }, { fontSize: 28, bold: true, color: "slate-950" });
      addText(s, b, { left: left + 22, top: 318, width: 198, height: 96 }, { fontSize: 19, color: "slate-700" });
    });
    addText(s, "核心不是继续泛聊 AI，而是针对每类阻力给不同产品包。", { left: 118, top: 548, width: 980, height: 38 }, { fontSize: 24, bold: true, color: "slate-800" });
    footer(s, 2);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "王超群证明：客户买的是“有人先接住咨询”", "已验证场景");
    bulletBlock(s, [
      "群名/备注含抖音、淘宝、微信公众号 ai客服。",
      "客户问“六月黄有吗”“有螃蟹吗？@客服助理”。",
      "客服助理自动发名片并提示点击发起咨询。",
      "可复制到生鲜、本地生活、服装、团购等高频问答场景。",
    ], 110, 200, 920, 72);
    addRect(s, { left: 892, top: 178, width: 246, height: 350 }, "white", "teal-100");
    addText(s, "产品核心", { left: 926, top: 216, width: 180, height: 32 }, { fontSize: 25, bold: true, color: "teal-800" });
    addText(s, "商品问答\n名片承接\n人工接管\n线索留存", { left: 932, top: 282, width: 170, height: 168 }, { fontSize: 28, bold: true, color: "slate-900" });
    footer(s, 3);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "没成交不是因为不需要 AI，而是没证明增量价值", "流失复盘");
    const rows = [
      ["Bryce", "担心企微接口关闭，且已有客服团队"],
      ["Daisy", "关键词客服已能解决问题，AI价值不明显"],
      ["陈-timeless", "出差后断点，需要轻量跟进材料"],
      ["曹智腾", "已有 AI客服方案提纲，需补成交状态"],
      ["jack/Torre", "搜索命中但还没展开，需继续读取"],
    ];
    rows.forEach(([a, b], i) => {
      const top = 178 + i * 76;
      addText(s, a, { left: 116, top, width: 190, height: 40 }, { fontSize: 24, bold: true, color: "slate-950" });
      s.shapes.add({ geometry: "rect", position: { left: 318, top: top + 17, width: 72, height: 3 }, fill: "amber-500", line: { style: "solid", fill: "none", width: 0 } });
      addText(s, b, { left: 422, top, width: 640, height: 42 }, { fontSize: 23, color: "slate-750" });
    });
    footer(s, 4);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "产品要从“AI能力”包装成“场景结果”", "产品复制");
    const cards = [
      ["客服助理启动包", "知识库、模糊问法、多轮追问、人工转接", "替代关键词客服盲区"],
      ["多渠道电商包", "抖音/淘宝/公众号/微信群商品问答和名片承接", "复制王超群场景"],
      ["低风险辅助包", "网页客服、桌面辅助回复、人工确认、接口预案", "回应企微接口顾虑"],
    ];
    cards.forEach(([h, body, tag], i) => {
      const left = 92 + i * 370;
      addRect(s, { left, top: 200, width: 318, height: 292 }, "white", "slate-200");
      addText(s, h, { left: left + 26, top: 238, width: 260, height: 34 }, { fontSize: 25, bold: true, color: "slate-950" });
      addText(s, body, { left: left + 26, top: 304, width: 252, height: 90 }, { fontSize: 19, color: "slate-700" });
      addText(s, tag, { left: left + 26, top: 424, width: 250, height: 34 }, { fontSize: 21, bold: true, color: i === 0 ? "teal-700" : i === 1 ? "blue-700" : "amber-700" });
    });
    footer(s, 5);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "微信文件里已经沉淀出更多可复制客户资产", "客户资产地图");
    const rows = [
      ["陈-timeless", "电信行业AI客服方案：VOS、WhatsApp、App、工单、TTS/ASR"],
      ["小危AI电信PPT", "10页成熟售前材料，含报价、ROI、分阶段交付"],
      ["王鲜记", "商品知识+客服话术、客服系统、内容生产报价单"],
      ["Recardify", "智能客服配置方案，偏部署配置和渠道接入"],
      ["佰社区", "AI超级员工，偏客服+运营助理组合"],
    ];
    rows.forEach(([name, desc], i) => {
      const top = 174 + i * 76;
      addText(s, name, { left: 104, top, width: 230, height: 34 }, { fontSize: 23, bold: true, color: "slate-950" });
      addRect(s, { left: 356, top: top - 8, width: 690, height: 54 }, i % 2 === 0 ? "slate-50" : "teal-50", "slate-200");
      addText(s, desc, { left: 382, top: top + 2, width: 640, height: 34 }, { fontSize: 20, color: "slate-750" });
    });
    footer(s, 6);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "复制顺序：先卖交付确定性，再卖复杂集成", "下次买/卖什么");
    const cards = [
      ["1", "王鲜记型商品知识库包", "最快成交：资料清楚、场景高频、能马上交付。"],
      ["2", "王超型多渠道客服助理", "有真实群聊场景，适合做样板案例。"],
      ["3", "Daisy型关键词升级包", "用对比演示证明AI比关键词系统多做了什么。"],
      ["4", "陈-timeless型企业集成包", "客单价高，但要分阶段试点，别一口吃成大系统。"],
    ];
    cards.forEach(([num, h, b], i) => {
      const left = 82 + (i % 2) * 540;
      const top = 188 + Math.floor(i / 2) * 172;
      addRect(s, { left, top, width: 466, height: 130 }, "white", "slate-200");
      s.shapes.add({ geometry: "ellipse", position: { left: left + 24, top: top + 32, width: 54, height: 54 }, fill: i < 2 ? "teal-600" : "amber-500", line: { style: "solid", fill: "none", width: 0 } });
      addText(s, num, { left: left + 42, top: top + 43, width: 20, height: 24 }, { fontSize: 20, bold: true, color: "white" });
      addText(s, h, { left: left + 104, top: top + 28, width: 318, height: 30 }, { fontSize: 23, bold: true, color: "slate-950" });
      addText(s, b, { left: left + 104, top: top + 68, width: 318, height: 42 }, { fontSize: 18, color: "slate-700" });
    });
    footer(s, 7);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "white";
    title(s, "下一次销售先确认损失，再演示解决方案", "销售动作");
    const steps = [
      "问原话：现在客服最重复、最漏单的问题是什么？",
      "算损失：每天多少咨询没有及时接住？",
      "演场景：用客户行业问题现场跑一遍AI客服。",
      "给套餐：从启动包开始，让客户先验证一个场景。",
      "做复盘：7天后用数据推动续费、增购或转介绍。",
    ];
    steps.forEach((step, i) => {
      const top = 176 + i * 78;
      s.shapes.add({ geometry: "ellipse", position: { left: 98, top, width: 42, height: 42 }, fill: "slate-900", line: { style: "solid", fill: "none", width: 0 } });
      addText(s, String(i + 1), { left: 111, top: top + 7, width: 18, height: 24 }, { fontSize: 18, bold: true, color: "white" });
      addText(s, step, { left: 166, top: top + 2, width: 870, height: 42 }, { fontSize: 24, color: "slate-800" });
    });
    footer(s, 8);
  }

  {
    const s = deck.slides.add();
    s.background.fill = "slate-50";
    title(s, "补齐真实微信资料后，结论会从模板变成可执行清单", "下一步");
    addRect(s, { left: 92, top: 194, width: 1010, height: 294 }, "white", "slate-200");
    bulletBlock(s, [
      "每个 ai / ai客服 标签客户的备注、行业、需求原话和成交状态。",
      "已成交客户的付款、交付、复购和转介绍信息。",
      "未成交客户停留环节：价格、信任、需求不急、决策链或产品不匹配。",
      "你已经发过的案例、报价、演示和售后承诺。",
    ], 136, 246, 860, 58);
    addText(s, "最终输出：客户分层名单、优先跟进名单、产品包定价建议、复购/转介绍话术。", { left: 122, top: 548, width: 960, height: 38 }, { fontSize: 24, bold: true, color: "teal-800" });
    footer(s, 9);
  }

  return deck;
}

async function main() {
  await fs.mkdir(QA_DIR, { recursive: true });
  const deck = makeDeck();
  for (const [index, slide] of deck.slides.items.entries()) {
    const png = await deck.export({ slide, format: "png", scale: 1 });
    await writeBlob(`${QA_DIR}/slide-${String(index + 1).padStart(2, "0")}.png`, png);
  }
  const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
  await writeBlob(`${QA_DIR}/montage.webp`, montage);
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(OUT);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
