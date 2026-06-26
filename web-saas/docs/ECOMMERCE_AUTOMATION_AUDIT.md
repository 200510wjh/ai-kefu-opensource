# 电商自动化集成审计报告

更新时间：2026-06-24

## 结论

最值得做的产品不是单点“短视频生成器”，而是一个面向商家和代理商的 **电商 AI 自动化增长中台**：

```text
商品/店铺输入 -> 商品素材生成 -> 短视频生成 -> AI 客服承接 -> 店铺运营任务 -> 线索/复购跟进
```

你本机已经有可复用资产，核心积木不是从零开始：

- `ecommerce-automation-hub`：商品、订单、库存、自动化任务骨架。
- `ai-kefu-opensource`：多平台 AI 客服 SaaS，FastAPI + 知识库 + Coze API。
- `kouzhi-agent`：桌面客服执行器，PyQt6 + Playwright + SQLite。
- `kouzi-plugins`：多平台插件系统，OAuth、消息中间件、自动回复规则。
- `kouzi-miniapp`：抖音小程序前端，用于账号/规则/消息管理。
- `ai_douyin_video`：已有短视频脚本、口播、分镜和 MP4 成片资产。
- `merchant_ai_app` / `merchant_ai_runtime`：商家 AI 线索采集、页面分析和登录态浏览器采集工具。
- `rent-car-hyperframes`：HyperFrames 视频生成实战项目。
- 当前项目 `Documents/运营`：已部署的商剪增长画布后台。

## 抖音收藏页检查

已通过 Chrome 插件读取当前登录抖音账号的收藏页：

- 账号昵称：`美式.`
- 主页数据：34 个作品，201 关注，324 粉丝，9007 获赞。
- 收藏页入口：`https://www.douyin.com/user/self?showTab=favorite_collection`
- 收藏分类：收藏夹、视频、音乐、合集、短剧。
- 本次读取的是“收藏 > 视频”页首屏内容，足够判断产品方向。

收藏视频显示出的强信号：

- **AI 自动化落地**：你收藏了“真正的 AI 落地，不看 AI 干多少，看人能从中抽出来多少”，说明你要做的是替商家节省人力的流程系统，不只是单点内容生成。
- **跨境/电商自动化**：你收藏了“深圳做跨境电商的都进化到用 AI 自动化干活了吗”，方向应覆盖商品、素材、上架、客服、订单跟进。
- **Codex 批量改商品**：你收藏了“只演示一遍，Codex 开始批量改商品”，这是核心启发：把运营的人工流程录下来，沉淀成可复用 skill/worker。
- **Record/Replay/Skill**：多条视频都在讲 Codex Record Replay、把经验写成 skill，说明产品应该把“商家操作经验”沉淀为自动化任务，而不是每次重新提示。
- **AI 客服后台**：你收藏了“自带 AI 自动回复，零成本搭建独立站客服后台”，应把客服承接放进 MVP，不要后置太久。
- **HyperFrames 视频稳定出片**：你收藏了 HyperFrames 出片 6 步流程，说明短视频模块应该采用脚本、分镜、配音时间轴、素材路径、验收标准的结构化流程。
- **视频工具选型**：你收藏了“图文转视频、视频处理、自动化剪辑、批量生成、真人素材混剪、科普动画”，说明视频产品要做成模板矩阵，而不是单一剪辑器。
- **Codex 接管剪映**：你收藏了“Codex 接管剪映，简单粗剪没问题”，但适用范围是模板化内容，MVP 应优先做模板广告和商品混剪。
- **AI 配音真实感**：你收藏了 AI 配音技巧，视频模块要预留声音/口播风格参数。
- **私有化部署和开源项目**：你收藏了 GitHub 优质项目、开源客服、插件和后端安全内容，变现应包含 SaaS + 私有化部署 + 二开服务。

结论：你的真实兴趣更偏向 **“电商运营自动化 Agent + 内容生成 + 客服承接”**，而不是单纯“AI 剪辑软件”。当前项目要升级成集成后台，短视频只是获客入口和内容生产模块。

### 2026-06-24 Chrome 插件复查

本次按用户要求再次使用 Chrome 插件接管已打开的抖音收藏页，确认当前页：

- 页签标题：`美式.的抖音 - 抖音`
- 当前 URL：`https://www.douyin.com/user/self?from_tab_name=main&showSubTab=video&showTab=favorite_collection`
- 当前选中：`收藏 > 视频`
- 页面搜索框里显示过：`codex前端`
- 本次 Chrome DOM 快照成功读取到首屏约 30 条强相关收藏；后续滚动/结构化批量提取时抖音页面过重导致浏览器会话超时，因此本次结论基于首屏高置信样本。

本次实际读取到的强相关收藏样本：

- `我终于实现了AI自动化剪视频，公开下10分钟工作流 #Claudecode #Codex #剪辑 #AI #自媒体`
- `花 5 分钟用 codex 剪辑了一条 40s 的科普视频 #ai #codex #vibecoding`
- `真正的 AI 落地，不看 AI 干多少，看人能从中抽出来多少 #ai自动化 #github优质项目 #一人公司`
- `现在深圳做跨境电商的都进化到用AI自动化干活了吗 #跨境电商 #AI`
- `只演示一遍，Codex开始批量改商品...让Codex直接学我的抖店商品草稿编辑流程 #Codex #Replay #Record #RPA`
- `Codex化身Ai学徒将经验写成skill...Record Replay`
- `自带 AI 自动回复，零成本搭建独立站客服后台...私有化部署，客户数据完全自持`
- `Codex做视频...图文转视频、视频处理、自动化剪辑、批量生成、真人素材混剪、科普动画`
- `HyperFrames 出片不稳定？问题大多在这 6 步...脚本、分镜、配音时间轴、素材路径和验收标准`
- `codex的正确打开方式！4天从0到1做一个自动回复app`
- `AI 配音没感情？3 步调出演员级真实感`
- `Vibe Coding安全：后端安全闭坑指南`
- `你的AI工具箱里缺了什么？工具不值钱，值钱的是用工具解决问题的系统`
- `Codex开发网站的零基础终极教学`
- `Codex 两大插件消失？一条命令修复`
- `让ai直接操作你的各种软件`
- `Codex的前端审美终于有救了 新插件Product Design把产品审美拉满`
- `让Codex提效10倍，必装的3类skills...Github上高星skills整理`
- `Codex一键配置国产大模型，完整使用插件功能`

复查后的产品判断：

- 收藏不是随机娱乐内容，主题非常集中：`Codex + 自动化 + 电商运营 + 视频生成 + 客服 + 私有化部署 + skills/插件 + 安全`。
- 当前 SaaS 应继续走“商家 AI 运营中台”，不是只做一个剪辑页面。
- 最优 MVP 顺序：
  1. 商品/门店需求录入。
  2. 自动生成脚本、分镜、主图/详情图、客服话术。
  3. HyperFrames/Remotion 模板化出片。
  4. 抖音私信/表单线索承接。
  5. 把商家重复操作沉淀成可回放的 task/skill。
- 抖音内容定位可以直接对齐收藏主题：`我用 Codex 给商家自动剪视频`、`老板一句话生成商品草稿和短视频`、`AI 客服后台私有化部署`、`HyperFrames 稳定出片 6 步`、`商家运营经验变成自动化 skill`。

## GitHub/开源复查

本轮开源检索确认：不要只复制一个短视频项目，应该把成熟开源能力拆成可替换模块。

- 商品图/场景图：[`302ai/302_ecom_image_generator`](https://github.com/302ai/302_ecom_image_generator) 适合作为“一键主图/场景图”的参考。
- 客服承接：[`chatwoot/chatwoot`](https://github.com/chatwoot/chatwoot) 适合作为开源客服/会话后台参考，但当前项目先做轻量客服话术和线索承接。
- 程序化广告视频：[`leosssvip-dot/remotion-ad-video-skill`](https://github.com/leosssvip-dot/remotion-ad-video-skill) 的方向和你收藏的 HyperFrames/Remotion 视频一致：从 URL/商品信息生成可编辑广告视频。
- 开源视频引擎：[`itsjwill/vanta`](https://github.com/itsjwill/vanta)、[`gyoridavid/short-video-maker`](https://github.com/gyoridavid/short-video-maker) 可作为后续字幕、TTS、背景视频、Remotion pipeline 的参考。
- 商品 listing 工作台：[`pkp666/product-ai-listing-studio`](https://github.com/pkp666/product-ai-listing-studio) 和你想做的“商品文案、平台字段、图片、卖货视频”很接近。
- 低代码自动化模板：[`enescingoz/awesome-n8n-templates`](https://github.com/enescingoz/awesome-n8n-templates) 可作为客服/订单/线索自动化流程参考。

取舍建议：

- MVP 不直接整合 Chatwoot、n8n、Remotion 全套，先保留适配器和数据结构。
- 先把“商品档案 -> 素材/视频/客服话术 -> 平台草稿 -> 人工确认”跑通。
- 开源仓库公开时主打“商家电商自动化中台”，不要把卖点写成普通 AI 剪辑器。

## 本地项目资产

### 1. `C:\Users\Administrator\ecommerce-automation-hub`

定位：京东 + 美团电商自动化中台 MVP。

已具备：

- 平台连接状态。
- 商品与库存管理。
- 低库存预警。
- 统一订单视图。
- 商品草稿上架任务。
- 库存同步任务。
- 本地 JSON 持久化。

适合并入当前后台为：**店铺运营中台模块**。

建议抽象：

- `Product`
- `Inventory`
- `Order`
- `AutomationJob`
- `PlatformConnector`

### 2. `C:\Users\Administrator\ai-kefu-opensource`

定位：多平台 AI 客服 SaaS。

已具备：

- 抖店、淘宝千牛、快手、拼多多平台概念。
- 店铺管理。
- 知识库。
- AI 自动回复。
- 数据统计。
- FastAPI + JSON 存储。

适合并入当前后台为：**AI 客服 SaaS 模块**。

建议先复制数据模型和接口设计，不直接整包合并。

### 3. `C:\Users\Administrator\kouzhi-agent`

定位：桌面版 AI 客服/平台执行器。

已具备：

- PyQt6 桌面 UI。
- Playwright 浏览器自动化。
- SQLite 数据库。
- 抖店、淘宝、扣子 API、消息处理服务。

适合作为：**本地执行器/浏览器自动化 worker**。

高风险动作必须保持人工确认：

- 自动发布商品。
- 自动改价。
- 自动退款。
- 自动发货回填。

### 4. `C:\Users\Administrator\kouzi-plugins`

定位：扣子智能体多平台插件系统。

已具备：

- 抖音、淘宝、京东、拼多多插件设计。
- OAuth 授权。
- 消息中间件。
- 自动回复规则。
- SaaS 后台结构。
- Node.js + TypeScript + Express + SQLite/JWT。

适合并入为：**平台插件层**。

建议先提取接口规范：

- `IPlugin`
- `PluginManager`
- `MessageBroker`
- `AutoReplyService`

### 5. `C:\Users\Administrator\kouzi-miniapp`

定位：抖音小程序 UI。

已具备页面：

- 首页统计看板。
- 账号管理。
- 回复规则配置。
- 消息记录。

适合做：**抖音小程序端入口**，连接主后台 API。

### 6. `C:\Users\Administrator\ai_douyin_video`

定位：AI 创业/抖音短视频生成实验。

已具备：

- `make_storyboard.py`
- `compose_video.py`
- 口播文案与剪映建议。
- MP3 口播。
- MP4 成片。

适合抽象成：**短视频分镜和合成模板参考**。

### 7. `C:\Users\Administrator\merchant_ai_app`

定位：商家 AI 线索采集/分析小后台。

已具备：

- CSV 模板：线索、跟进、报价、交付、页面采集结果。
- 静态采集、Playwright 采集、登录态浏览器采集入口。
- 快捷 prompt：客户分析、首轮私信、商品优化。

适合并入为：**商家获客 CRM + 线索分析模块**。

### 8. `C:\Users\Administrator\merchant_ai_runtime`

定位：浏览器采集运行时。

已具备：

- public page collector。
- authenticated browser launcher。
- authenticated page collector。

适合做：**平台/店铺页面采集 worker**。

### 9. `C:\Users\Administrator\rent-car-hyperframes`

定位：HyperFrames 视频生成实战。

已具备：

- `DESIGN.md`
- `hyperframes.json`
- `index.html`
- `ffmpeg-render.exe`
- `rent-car-promo.mp4`

适合做：**商品短视频渲染模板样板**。

## GitHub/开源参考

- [302 AI E-commerce Scene Image Generator](https://github.com/302ai/302_ecom_image_generator)：电商场景图/视频生成，适合作为商品主图、场景图、详情图生成参考。
- [Open AI UGC](https://github.com/Anil-matcha/Open-AI-UGC)：UGC 视频广告生成，适合作为真人口播/UGC 广告方向参考。
- [AdGen](https://github.com/Rakshath66/AdGen)：商品 URL 到 GPT 脚本和 Remotion 视频广告，适合作为“商品链接生成短视频”的参考。
- [Chatwoot](https://github.com/chatwoot/chatwoot)：开源客服/会话平台，适合作为客服会话、收件箱、工单、团队协作参考。
- [Remotion](https://github.com/remotion-dev/remotion)：React 程序化视频生成，适合作为视频渲染引擎参考。
- [Open Generative AI](https://github.com/anil-matcha/open-generative-ai)：图片、视频、多模型生成工作室，适合作为多模型创意工厂参考。

## 推荐产品形态

产品名可暂定：**商剪电商自动化中台**。

板块：

1. **商品素材工厂**
   - 商品图片上传/链接解析。
   - 主图、卖点图、详情页图、场景图。
   - 抠图、背景、场景、文案贴纸。

2. **短视频工厂**
   - 抖音/小红书/视频号脚本。
   - 分镜、字幕、口播、BGM、CTA。
   - HyperFrames/Remotion 模板渲染。

3. **AI 客服**
   - 商品知识库。
   - FAQ。
   - 售前逼单话术。
   - 售后安抚话术。
   - 多平台消息接入。

4. **店铺运营中台**
   - 商品草稿。
   - 库存预警。
   - 订单异常。
   - 自动化任务队列。
   - 高风险动作人工确认。

5. **获客 CRM**
   - 抖音线索。
   - 私信跟进。
   - 微信客户。
   - 报价、交付、复购。

## 优先级

### 第一阶段：可演示、能卖钱

目标：让商家看到输入商品信息后，系统能产出真实可用素材。

1. 合并当前 `商剪增长画布` + `ecommerce-automation-hub` 的商品/库存/任务模型。
2. 把 `merchant_ai_app` 的线索、报价、跟进 CSV 模板迁移成后台数据模型。
3. 接入 AI Provider 生成商品主图/详情页/短视频脚本。
4. 做一个 HyperFrames 商品短视频模板。
5. 保持下载 JSON/HTML/MP4 的交付模式。

### 第二阶段：客服闭环

1. 接入 `ai-kefu-opensource` 的知识库和客服接口结构。
2. 抽出客服话术生成和 FAQ 检索。
3. 接入 `kouzi-plugins` 的插件架构设计。
4. 先做“客服建议回复”，不做自动发送。

### 第三阶段：平台自动化

1. 使用 `kouzhi-agent` / `merchant_ai_runtime` 做浏览器自动化 worker。
2. 先实现商品草稿、库存同步建议、订单异常识别。
3. 发布、退款、改价、发货等动作必须人工确认。

## 商业化路线

1. **SaaS 订阅**
   - Starter：99 元/月，30 次生成。
   - Pro：299 元/月，150 次生成。
   - Agency：999 元/月，团队账号 + 模板库 + 私有部署咨询。

2. **代运营交付**
   - 199-499 元：商品素材包。
   - 499-999 元：短视频 + 图文 + 客服话术包。
   - 1999+ 元：店铺自动化诊断 + 私有部署。

3. **开源获客**
   - 开源核心画布和 demo 模板。
   - 收费项放在部署、模板、平台适配、客服插件、私有化。
