import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = "C:/Users/Administrator/Documents/运营";
const OUT_DIR = path.join(ROOT, "outputs", "闲鱼高端AI客服上架包");
const TODAY = "2026-07-12";

const sourceNotes = [
  {
    name: "微信客户与文件证据",
    note: "来自已生成的 AI客服客户扫描台账、成交复制手册和 PPT：Bryce、Daisy、陈-timeless、大头哥、王超，以及王鲜记、Recardify、小危AI电信、AI客服安装包等文件资产。",
  },
  {
    name: "公开行业参考",
    note: "浏览器/电脑插件未能完成闲鱼实扫；本包把公开行业资料作为策略参考，把闲鱼真实竞品数据列为待实扫字段。",
  },
];

const references = [
  ["YuChatAI 闲鱼智能客服助手", "https://chromewebstore.google.com/detail/yuchatai-%E9%97%B2%E9%B1%BC%E6%99%BA%E8%83%BD%E5%AE%A2%E6%9C%8D%E5%8A%A9%E6%89%8B/bfhjhhbpbcpdjdjoadnacipchbdgpkpg", "支持 AI 回复、手动放行、订单通知、商品知识库优化回复，说明闲鱼卖家确实有“辅助回复+人工确认”的需求。"],
  ["XianyuAutoAgent GitHub", "https://github.com/shaxiu/XianyuAutoAgent", "闲鱼 7x24 自动值守、议价、上下文对话，验证“闲鱼AI客服”是明确赛道。"],
  ["AI店小蜜定价报道", "https://www.geekpark.net/news/364035", "平台型 AI 客服按通计费，0.2/0.5 元一通，为高端项目提供成本对比锚点。"],
  ["淘宝开放平台客服面板插件", "https://developer.alibaba.com/docs/doc.htm?articleId=119210&docType=1&treeId=634", "客服接待需要用户、订单、商品、知识库、工单等接待视图，支持我们把卖点从“机器人”升级成“接待系统”。"],
  ["客服知识库搭建流程", "https://www.7x24cc.com/help/innews/6933.html", "知识库要做内容采集、标准化模板、功能验证和迭代，支撑商品知识库+客服SOP的高端服务定位。"],
];

const competitorRows = [
  ["AI客服搭建", "待闲鱼实扫", "低价模板/课程/代搭建/源码", "标题是否写平台+结果；是否承诺自动回复；价格锚点；想要数；首图是否有后台截图", "不要跟 9.9/99 模板竞争，筛出 2999+ 的代搭建卖家对标。"],
  ["抖店AI客服", "待闲鱼实扫", "电商代搭建/插件配置", "是否强调飞鸽、抖店、15秒响应、商品知识库、人工兜底", "优先用王鲜记和 AI客服安装包证据包装。"],
  ["淘宝千牛客服自动回复", "待闲鱼实扫", "千牛插件/店铺客服提效", "是否强调千牛、商品卡、售后、快捷回复、提高响应率", "把“知识库+SOP+插件配置”打成套餐。"],
  ["商品知识库搭建", "待闲鱼实扫", "文档整理/客服SOP/智能体知识库", "是否有表格截图、FAQ数量、流程图、可交付文档", "这是你的高毛利入口，适合不想冒系统风险的客户。"],
  ["客服话术SOP", "待闲鱼实扫", "话术包/行业模板/培训", "是否按行业拆：生鲜、服饰、本地生活、售后投诉", "用王鲜记和 Recardify 做垂直案例。"],
  ["企业微信客服机器人", "待闲鱼实扫", "私域企微/风控辅助", "是否强调低风险、人工接管、只做建议不直发", "专门化解 Bryce 的企微接口风险。"],
  ["扣子智能体搭建", "待闲鱼实扫", "智能体代搭建/课程", "是否强调 Coze、知识库、工作流、交付源码/账号", "不要卖泛智能体，必须落到客服转化。"],
  ["AI内容生产", "待闲鱼实扫", "脚本/图文/视频/月度代运营", "是否按月报价；是否绑定客服转化和商品素材", "承接王鲜记 AI 内容生产报价，作为高端扩展包。"],
];

const products = [
  {
    id: "P1",
    name: "电商AI客服系统搭建",
    price: "2999-9800",
    target: "抖店、淘宝、飞鸽、千牛、拼多多等有高频咨询的商家",
    title: "抖店淘宝AI客服搭建 商品知识库话术SOP 7天陪跑交付",
    subtitle: "把高频问题、商品知识、售后话术接进 AI 客服，人工可随时接管。",
    proof: "AI客服安装包、王鲜记客服系统、王超多渠道咨询场景",
    image: "首图放“平台+知识库+自动回复+人工兜底”四格截图；第二张放交付清单；第三张放流程图。",
    category: "高端代搭建",
    detail: [
      "适合每天有重复咨询、客服响应慢、商品问题多、售后口径不统一的商家。",
      "交付包括：商品知识库整理、FAQ问答表、客服话术SOP、平台接入配置、常见问题自动回复、人工接管规则、7天跟跑优化。",
      "先从 10-30 个高频问题跑起来，不承诺替代全部人工，先解决漏回复、慢回复、口径不一致。",
      "如果你已有客服团队，本服务也可以做辅助模式：AI 先给建议，人工确认再发。",
    ],
    faq: [
      ["能不能全自动？", "可以按风险分级。简单问题自动接，价格/投诉/异常订单转人工。"],
      ["多久交付？", "基础版 3-5 天，高级版 7-10 天，取决于商品资料完整度。"],
      ["需要给你账号吗？", "正式接入前先做资料诊断；涉及账号权限时，只拿必要权限并可远程陪你操作。"],
    ],
    opener: "你发我：店铺平台+商品类目+每天大概咨询量。我先判断适合做自动回复、辅助回复，还是只做知识库SOP。",
  },
  {
    id: "P2",
    name: "商品知识库 + 客服话术 SOP",
    price: "1999-6800",
    target: "生鲜、服饰、礼品、本地生活、软件类目商家",
    title: "商品知识库搭建 客服话术SOP整理 生鲜服饰售后问答包",
    subtitle: "先把客服回答标准化，再接 AI 才不乱答。",
    proof: "王鲜记产品知识+客服话术、Recardify智能客服配置方案",
    image: "首图放知识库表格样张；第二张放售前/售后/投诉/复购四类话术；第三张放行业案例。",
    category: "知识库高毛利服务",
    detail: [
      "适合商品多、客服回答不统一、新客服培训慢、售后容易扯皮的商家。",
      "交付包括：商品资料结构化、售前问答、售后赔付口径、投诉升级、复购优惠、禁用话术、AI可读知识库。",
      "可以独立使用，也可以作为后续 AI 客服系统搭建的第一步。",
      "高端价值在于把老板脑子里的经验变成可复制客服资产。",
    ],
    faq: [
      ["我没有现成资料能做吗？", "能做，但需要你提供商品链接、常见问题、售后规则，我会帮你整理成结构化表。"],
      ["可以按行业做吗？", "可以，生鲜、服饰、礼品、软件类最适合先做。"],
      ["能不能给客服培训用？", "可以，交付版会包含新人培训口径和禁用话术。"],
    ],
    opener: "你发我一个商品链接或类目，我给你判断这个类目最该先整理哪 20 个客服问题。",
  },
  {
    id: "P3",
    name: "AI客服系统 + 知识库 + 7天陪跑",
    price: "9800-19800",
    target: "已有稳定订单和客服团队，希望直接落地提效的商家",
    title: "高端AI客服系统搭建 知识库SOP 7天陪跑 人工兜底",
    subtitle: "不是卖软件，是帮商家把客服流程跑通。",
    proof: "王鲜记完整交付链路、小程序使用指南、客户高意向提醒",
    image: "首图放高端项目交付路线图；第二张放 7 天陪跑日历；第三张放数据复盘表。",
    category: "高端项目包",
    detail: [
      "适合老板不想自己研究工具，希望有人把系统、话术、知识库和复盘一起做完。",
      "交付包括：诊断、知识库、客服SOP、AI客服配置、人工接管策略、试运行、数据复盘、二次优化。",
      "7 天陪跑每天看咨询问题，修正 AI 回答，补充高频知识点。",
      "项目边界清晰：不承诺代替全部客服，不做违规自动化，不碰平台风控红线。",
    ],
    faq: [
      ["为什么比别人贵？", "便宜的是模板或课程，这个是交付项目：资料整理、配置、试运行、复盘都包含。"],
      ["能不能先试？", "可以先做 199 元诊断，成交项目后抵扣。"],
      ["没有技术人员能用吗？", "可以，目标是让客服和老板能运营，不要求你会技术。"],
    ],
    opener: "你现在最头疼的是回复慢、客服口径乱、售后多，还是晚上没人接？我先按你的场景拆方案。",
  },
  {
    id: "P4",
    name: "企业微信/私域 AI 客服辅助",
    price: "6800-19800",
    target: "私域、企微、社群、B2B 销售线索承接团队",
    title: "企业微信私域AI客服辅助 知识库问答 人工确认低风险方案",
    subtitle: "针对担心接口和风控的客户，主打辅助建议与人工确认。",
    proof: "Bryce 风险顾虑、小危AI电信方案、企微/WhatsApp/App/工单集成思路",
    image: "首图放“AI建议-人工确认-客户回复”流程；第二张放风险边界；第三张放适用场景。",
    category: "低风险私域方案",
    detail: [
      "适合已有客服或销售团队，但线索多、知识散、回复标准不统一的私域团队。",
      "优先做辅助模式：AI 生成建议答案，人工确认后发送，降低接口和误回复风险。",
      "交付包括：私域话术库、客户意图分类、高意向提醒、人工接管规则、敏感问题转人工。",
      "卖点不是全自动，而是让团队回复更快、更稳、更可复制。",
    ],
    faq: [
      ["会不会封号？", "默认不做高风险直发，先做辅助建议和人工确认。具体接入方式要按你现有工具评估。"],
      ["适合销售吗？", "适合，尤其是产品问题多、客户跟进周期长的团队。"],
      ["能接多个渠道吗？", "可以做方案设计，具体落地按企业微信、网页、表单、工单等渠道拆分。"],
    ],
    opener: "你先不用给账号，发我你们客服/销售最常被问的 10 个问题，我判断适合做辅助还是自动。",
  },
  {
    id: "P5",
    name: "AI内容生产 + 客服转化包",
    price: "7500/月起",
    target: "需要持续图文、短视频、商品素材和客服转化联动的商家",
    title: "AI内容生产服务 商品图视频脚本 客服转化话术 月度代运营",
    subtitle: "把内容生产和客服成交口径连起来，不只做图文视频。",
    proof: "王鲜记AI内容生产报价单：首月 7500/9500/16000，后续月费 6500/8500/14000",
    image: "首图放月度交付清单；第二张放脚本-图片-视频-客服话术链路；第三张放套餐对比。",
    category: "月度高端服务",
    detail: [
      "适合有产品但缺内容、缺脚本、缺客服转化口径的商家。",
      "交付包括：卖点拆解、短视频脚本、商品图提示词、客服转化话术、复购话术、月度素材计划。",
      "内容不是孤立生产，要反哺客服：客户问什么，内容就补什么；内容引来咨询，客服话术接得住。",
      "适合与 AI 客服系统包组合销售，提高客单价和续费。",
    ],
    faq: [
      ["只做图片视频吗？", "不只做素材，会同时整理卖点和客服转化话术。"],
      ["一个月交付多少？", "按套餐定，建议先从 10 条短视频脚本+1000 张图生产能力规划起。"],
      ["能和客服系统一起做吗？", "可以，内容负责引流，客服负责承接，组合效果更好。"],
    ],
    opener: "你发我产品类目和客单价，我先判断适合做内容引流、客服转化，还是两者一起做。",
  },
  {
    id: "P0",
    name: "199元 AI客服诊断方案",
    price: "199，可抵扣项目款",
    target: "不知道能不能做、预算未明确、但有真实店铺问题的客户",
    title: "199元AI客服诊断 店铺咨询问题梳理 可抵扣搭建项目款",
    subtitle: "不是低价服务，是筛选高质量客户的入口。",
    proof: "用于解决 Daisy 的价值感知不足和陈-timeless 的跟进停滞",
    image: "首图放诊断报告样张；第二张放 3 个结论：能不能做、先做什么、预算区间。",
    category: "筛选入口",
    detail: [
      "适合想了解 AI 客服是否适合自己店铺，但不想一上来做大项目的商家。",
      "交付一页诊断：当前客服问题、适合自动化的问题、不能自动化的问题、建议套餐和预算。",
      "诊断费在 7 天内成交搭建项目可抵扣。",
      "避免 9.9 低端客户，用 199 筛出愿意为方案付费的人。",
    ],
    faq: [
      ["为什么诊断也收费？", "因为会看你的真实类目、问题和资料，给的是可执行判断，不是泛泛建议。"],
      ["诊断后必须买项目吗？", "不用，适合就继续，不适合会直接说不建议做。"],
      ["需要提供什么？", "平台、类目、商品链接、常见问题、每天咨询量。"],
    ],
    opener: "你发平台+类目+3个最常见客服问题，我先判断值不值得做诊断。",
  },
];

const evidenceRows = [
  ["王超", "微信群/抖音/淘宝/公众号多渠道咨询", "客户问六月黄、螃蟹等高频商品问题，客服助理自动卡片承接", "证明电商多渠道客服承接是刚需", "P1/P3"],
  ["王鲜记", "生鲜商品知识+客服话术+客服系统+内容报价", "有商品知识、售后赔付、投诉升级、复购券、AI内容生产报价", "最适合复制成商品知识库、客服SOP和高端陪跑", "P1/P2/P3/P5"],
  ["Recardify", "服饰顾问型智能客服", "人设、尺码、推荐、回收、推荐好友、老客话术", "说明垂直行业话术能卖出差异化", "P2/P3"],
  ["Bryce", "企微接口风险/已有客服团队", "担心企业微信接口风险，已有客服团队", "必须提供辅助模式、人工确认、低风险方案", "P4"],
  ["Daisy", "已有关键词客服，不理解 AI 增量", "认为现有关键词客服够用", "详情页必须解释 AI 与关键词客服区别，用诊断展示价值", "P0/P2"],
  ["大头哥", "SaaS系统嵌入/一次性费用敏感", "希望系统做出来可以装，价格降了很多", "适合作为技术型客户，强调部署边界和费用档位", "P1/P3"],
  ["陈-timeless", "电信行业企业级智能客服", "VOS、WhatsApp、App SDK、工单、知识图谱等方案线索", "企业级方案可做高端背书，但闲鱼先不主卖过重集成", "P4"],
];

const optimizationRows = [
  ["第1天", "发布 P0/P1/P2 三条", "先跑诊断、系统搭建、知识库三个入口", "曝光、浏览、想要、咨询", "标题必须含 AI客服/平台/交付物；首图展示交付清单。"],
  ["第2天", "补 P3/P4", "拉高客单价，覆盖已有客服团队和企微风险客户", "咨询质量、客户预算", "详情页前 3 屏突出高端交付和人工兜底。"],
  ["第3天", "根据曝光改标题", "曝光低说明关键词不对", "曝光 < 100 的商品", "替换为平台词：抖店/淘宝/千牛/企微/知识库。"],
  ["第4天", "根据浏览改首图", "浏览高但咨询低说明首图或价格锚点弱", "浏览/咨询比", "首图改成结果型：少漏单、快回复、客服SOP。"],
  ["第5天", "整理咨询问题进 FAQ", "咨询多不成交说明顾虑没提前化解", "客户反复问的问题", "补充账号权限、封号风险、交付周期、售后维护。"],
  ["第6天", "做套餐对比图", "高端成交需要让客户理解贵在哪里", "P1/P3/P5 的咨询", "基础版/标准版/陪跑版三档，不和低价模板比较。"],
  ["第7天", "复盘保留胜出版本", "保留高点击高咨询标题和首图", "曝光-浏览-想要-咨询-成交", "淘汰低质流量标题，沉淀高频问题到知识库。"],
];

const metricsRows = [
  ["曝光低", "标题关键词/类目错", "换平台词+交付词：抖店AI客服、千牛自动回复、商品知识库", "24小时"],
  ["浏览高咨询低", "首图不够具体或价格吓退", "首图改交付清单；详情前 3 屏解释适合谁/不适合谁", "24小时"],
  ["想要多不咨询", "行动指令弱", "加一句：发平台+类目+每天咨询量，我判断能不能做", "12小时"],
  ["咨询多不成交", "信任和边界不足", "补案例、流程、交付物、售后维护、风险边界", "48小时"],
  ["低价客户太多", "入口太低端", "把免费咨询改 199 诊断抵扣，删除 9.9/99 表述", "立即"],
];

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(headers, rows) {
  return [headers, ...rows].map((row) => row.map(csvEscape).join(",")).join("\r\n");
}

function productRows() {
  return products.map((p) => [
    p.id,
    p.name,
    p.price,
    p.category,
    p.target,
    p.title,
    p.subtitle,
    p.proof,
    p.image,
    p.opener,
  ]);
}

function listingRows() {
  return products.filter((p) => p.id !== "P0").map((p) => [
    p.id,
    p.title,
    p.price,
    p.image,
    p.detail.join("\n"),
    p.faq.map(([q, a]) => `Q: ${q} A: ${a}`).join("\n"),
    p.opener,
  ]);
}

function md() {
  const productSections = products.map((p) => `## ${p.id} ${p.name}

**建议价格**：${p.price}

**闲鱼标题**：${p.title}

**一句话卖点**：${p.subtitle}

**适合客户**：${p.target}

**证据来源**：${p.proof}

**首图/配图方向**：${p.image}

**详情页文案**

${p.detail.map((item) => `- ${item}`).join("\n")}

**FAQ**

${p.faq.map(([q, a]) => `- ${q}：${a}`).join("\n")}

**咨询开场回复**

${p.opener}
`).join("\n---\n\n");

  return `# 闲鱼高端 AI 客服上架包

生成日期：${TODAY}

## 先说结论

你现在不适合在闲鱼主卖 9.9、99 元的低价 AI 模板。你手里真正值钱的是“商家客服交付能力”：商品知识库、客服话术 SOP、AI 客服配置、人工兜底、7 天陪跑、内容生产和转化承接。

闲鱼上应该用高端项目的包装方式卖：先用 199 元诊断筛选客户，再引导到 2999-19800 的搭建和陪跑服务。客户买的不是“AI”，而是“少漏单、回复更稳、客服口径统一、新客服更快上手、晚上也有人先接住”。

## 当前限制

Chrome 专用通道未连接成功，电脑插件在 Chrome 页面读取时因无法确认当前 URL 被安全策略截停，所以本次没有伪造闲鱼实时竞品数据。已经把“竞品扫描表”做成可实扫模板，并结合公开资料和你微信里的真实客户证据完成上架包。

## 产品矩阵

${products.map((p) => `- ${p.id} ${p.name}：${p.price}，主打 ${p.category}`).join("\n")}

## 5 条主推上架文案

${productSections}

## 竞品实扫方法

每个关键词至少看前 10-20 个商品：AI客服搭建、抖店AI客服、淘宝千牛客服自动回复、商品知识库搭建、客服话术SOP、企业微信客服机器人、扣子智能体搭建、AI内容生产。

记录标题、价格、想要数、图片风格、卖点、交付物、是否课程/源码/代搭建/陪跑、评论问答、咨询引导。不要只看低价，重点找 2999 元以上的高端代搭建卖家，看他们如何证明交付能力。

## 详情页固定结构

1. 你是不是遇到这些问题：回复慢、漏单、客服口径乱、售后难统一、新客服培训慢。
2. 我交付什么：知识库、FAQ、话术 SOP、系统配置、人工兜底、7 天复盘。
3. 适合谁：有真实咨询、有商品资料、有客服或老板愿意配合。
4. 不适合谁：想 9.9 买全自动躺赚、完全不提供资料、要求违规群发或绕平台风控。
5. 为什么贵：不是模板，是项目交付；不是只搭工具，是把客服流程跑通。
6. 怎么开始：发平台+类目+每天咨询量+3个高频问题，我先判断方案。

## 7 天优化节奏

${optimizationRows.map((r) => `- ${r[0]}：${r[1]}。${r[4]}`).join("\n")}

## 外部参考

${references.map(([name, url, note]) => `- [${name}](${url})：${note}`).join("\n")}
`;
}

function dataJson() {
  return {
    today: TODAY,
    sourceNotes,
    references,
    competitor: {
      headers: ["关键词", "实扫状态", "可能竞品类型", "需要记录", "你的优化动作"],
      rows: competitorRows,
    },
    products: {
      headers: ["ID", "产品", "建议价格", "定位", "目标客户", "闲鱼标题", "一句话卖点", "证据来源", "图片方向", "咨询开场"],
      rows: productRows(),
    },
    listings: {
      headers: ["ID", "标题", "价格", "图片方向", "详情页文案", "FAQ", "咨询回复"],
      rows: listingRows(),
    },
    evidence: {
      headers: ["客户/资产", "场景", "证据", "复制结论", "对应产品"],
      rows: evidenceRows,
    },
    optimization: {
      headers: ["日期", "动作", "目的", "观察指标", "调整规则"],
      rows: optimizationRows,
    },
    metrics: {
      headers: ["现象", "判断", "动作", "观察周期"],
      rows: metricsRows,
    },
    slides: [
      ["闲鱼高端AI客服上架策略", "主打高端服务，不做低价模板内卷", ["199诊断筛选真实客户", "2999-19800项目交付", "卖客服流程跑通，不卖空泛AI"]],
      ["为什么能卖高端", "你已有的不是素材，而是交付证据", ["王鲜记：知识库、话术、系统、内容报价完整", "王超：多渠道客服承接已验证", "Bryce/Daisy：未成交顾虑可提前写进详情页"]],
      ["产品矩阵", "从诊断到项目再到月度续费", products.slice(0, 5).map((p) => `${p.name}：${p.price}`)],
      ["主推商品1", products[0].title, products[0].detail],
      ["主推商品2", products[1].title, products[1].detail],
      ["高端成交包", products[2].title, products[2].detail],
      ["低风险企微方案", products[3].title, products[3].detail],
      ["内容生产扩展", products[4].title, products[4].detail],
      ["详情页优化", "前3屏必须解决信任、价值和行动", ["首图展示交付物，不放空泛AI图", "写清适合谁/不适合谁", "用人工兜底化解风控和误回复顾虑"]],
      ["7天数据复盘", "用曝光-浏览-想要-咨询-成交定位问题", ["曝光低改关键词", "浏览高咨询低改首图和前3屏", "咨询多不成交补FAQ和案例"]],
    ],
  };
}

const psScript = String.raw`
param([string]$JsonPath, [string]$OutDir)
$ErrorActionPreference = "Stop"
$data = Get-Content -LiteralPath $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Release-Com($obj) {
  if ($null -ne $obj) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
}

$xlsx = Join-Path $OutDir "闲鱼高端AI客服竞品与商品矩阵.xlsx"
$docx = Join-Path $OutDir "闲鱼高端AI客服上架执行手册.docx"
$pptx = Join-Path $OutDir "闲鱼高端AI客服销售框架PPT.pptx"

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Add()
while ($wb.Worksheets.Count -lt 6) { [void]$wb.Worksheets.Add() }
$sheets = @(
  @("竞品扫描表", $data.competitor.headers, $data.competitor.rows),
  @("商品矩阵", $data.products.headers, $data.products.rows),
  @("上架文案", $data.listings.headers, $data.listings.rows),
  @("成交证据映射", $data.evidence.headers, $data.evidence.rows),
  @("7天优化表", $data.optimization.headers, $data.optimization.rows),
  @("指标判断表", $data.metrics.headers, $data.metrics.rows)
)
for ($si = 0; $si -lt $sheets.Count; $si++) {
  $ws = $wb.Worksheets.Item($si + 1)
  $ws.Name = $sheets[$si][0]
  $headers = $sheets[$si][1]
  $rows = $sheets[$si][2]
  for ($c = 0; $c -lt $headers.Count; $c++) {
    $cell = $ws.Cells.Item(1, $c + 1)
    $cell.Value2 = [string]$headers[$c]
    $cell.Font.Bold = $true
    $cell.Interior.Color = 0x784D1F
    $cell.Font.Color = 0xFFFFFF
  }
  for ($r = 0; $r -lt $rows.Count; $r++) {
    $row = $rows[$r]
    for ($c = 0; $c -lt $row.Count; $c++) {
      $ws.Cells.Item($r + 2, $c + 1).Value2 = [string]$row[$c]
    }
  }
  $ws.Columns.AutoFit() | Out-Null
  $ws.Rows.Item(1).AutoFilter() | Out-Null
}
$wb.SaveAs($xlsx, 51)
$wb.Close($true)
$excel.Quit()
Release-Com $wb
Release-Com $excel

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Add()
$sel = $word.Selection
function Add-Line([string]$text, [int]$size = 11, [bool]$bold = $false) {
  $sel.Font.Name = "Microsoft YaHei"
  $sel.Font.Size = $size
  $sel.Font.Bold = $(if ($bold) { 1 } else { 0 })
  $sel.TypeText($text)
  $sel.TypeParagraph()
}
Add-Line "闲鱼高端AI客服上架执行手册" 20 $true
Add-Line ("生成日期：" + $data.today) 10 $false
Add-Line "一、核心判断" 15 $true
Add-Line "主打高端服务，不做9.9低价模板内卷。用199元诊断筛选客户，再承接2999-19800元的AI客服搭建、知识库SOP、7天陪跑和内容转化服务。" 11 $false
Add-Line "二、产品矩阵" 15 $true
foreach ($row in $data.products.rows) {
  Add-Line (($row[0] + " " + $row[1] + "｜" + $row[2] + "｜" + $row[5])) 11 $true
  Add-Line ("目标客户：" + $row[4]) 10 $false
  Add-Line ("咨询开场：" + $row[9]) 10 $false
}
Add-Line "三、上架详情页结构" 15 $true
Add-Line "痛点：回复慢、漏单、客服口径乱、售后难统一、新客服培训慢。" 11 $false
Add-Line "交付：知识库、FAQ、话术SOP、平台配置、人工兜底、7天复盘。" 11 $false
Add-Line "边界：不承诺替代全部人工，不做违规自动化，不碰平台风控红线。" 11 $false
Add-Line "行动：发平台+类目+每天咨询量+3个高频问题，我先判断能不能做。" 11 $false
Add-Line "四、竞品扫描说明" 15 $true
foreach ($row in $data.competitor.rows) {
  Add-Line (($row[0] + "：" + $row[3] + "。优化：" + $row[4])) 10 $false
}
Add-Line "五、7天优化节奏" 15 $true
foreach ($row in $data.optimization.rows) {
  Add-Line (($row[0] + "｜" + $row[1] + "｜" + $row[4])) 10 $false
}
Add-Line "六、外部参考" 15 $true
foreach ($row in $data.references) {
  Add-Line (($row[0] + "：" + $row[2] + " " + $row[1])) 9 $false
}
$doc.SaveAs2($docx, 16)
$doc.Close($true)
$word.Quit()
Release-Com $doc
Release-Com $word

$ppt = New-Object -ComObject PowerPoint.Application
$presentation = $ppt.Presentations.Add()
foreach ($slideData in $data.slides) {
  $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, 12)
  $title = $slide.Shapes.AddTextbox(1, 48, 36, 860, 54)
  $title.TextFrame.TextRange.Text = [string]$slideData[0]
  $title.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
  $title.TextFrame.TextRange.Font.Size = 30
  $title.TextFrame.TextRange.Font.Bold = $true
  $subtitle = $slide.Shapes.AddTextbox(1, 52, 94, 860, 38)
  $subtitle.TextFrame.TextRange.Text = [string]$slideData[1]
  $subtitle.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
  $subtitle.TextFrame.TextRange.Font.Size = 17
  $subtitle.TextFrame.TextRange.Font.Color.RGB = 0x666666
  $items = $slideData[2]
  for ($i = 0; $i -lt $items.Count; $i++) {
    $box = $slide.Shapes.AddTextbox(1, 76, 165 + ($i * 70), 820, 56)
    $box.TextFrame.TextRange.Text = ("· " + [string]$items[$i])
    $box.TextFrame.TextRange.Font.Name = "Microsoft YaHei"
    $box.TextFrame.TextRange.Font.Size = 18
  }
}
$presentation.SaveAs($pptx, 24)
$presentation.Close()
$ppt.Quit()
Release-Com $presentation
Release-Com $ppt
`;

await fs.mkdir(OUT_DIR, { recursive: true });
const dataPath = path.join(OUT_DIR, "xianyu_ai_service_pack.data.json");
await fs.writeFile(dataPath, JSON.stringify(dataJson(), null, 2), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服上架包.md"), md(), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服竞品扫描表.csv"), toCsv(["关键词", "实扫状态", "可能竞品类型", "需要记录", "你的优化动作"], competitorRows), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服商品矩阵.csv"), toCsv(["ID", "产品", "建议价格", "定位", "目标客户", "闲鱼标题", "一句话卖点", "证据来源", "图片方向", "咨询开场"], productRows()), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服上架文案.csv"), toCsv(["ID", "标题", "价格", "图片方向", "详情页文案", "FAQ", "咨询回复"], listingRows()), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服7天优化表.csv"), toCsv(["日期", "动作", "目的", "观察指标", "调整规则"], optimizationRows), "utf8");
await fs.writeFile(path.join(OUT_DIR, "闲鱼高端AI客服成交证据映射.csv"), toCsv(["客户/资产", "场景", "证据", "复制结论", "对应产品"], evidenceRows), "utf8");

const psPath = path.join(OUT_DIR, "build_office_outputs.ps1");
await fs.writeFile(psPath, `\ufeff${psScript}`, "utf8");
const result = spawnSync("powershell.exe", [
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  psPath,
  "-JsonPath",
  dataPath,
  "-OutDir",
  OUT_DIR,
], { encoding: "utf8" });

if (result.status !== 0) {
  console.error(result.stdout);
  console.error(result.stderr);
  throw new Error(`Office export failed with status ${result.status}`);
}

const files = await fs.readdir(OUT_DIR);
console.log(JSON.stringify({ outDir: OUT_DIR, files }, null, 2));
