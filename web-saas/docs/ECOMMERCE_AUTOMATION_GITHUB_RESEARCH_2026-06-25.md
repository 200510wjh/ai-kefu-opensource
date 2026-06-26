# 国内电商/TikTok Shop 自动化 GitHub 选型

日期：2026-06-25

## 结论

有，且可以接到当前 `商剪增长画布` 项目里。但建议先按安全等级分层：

```text
只读数据/采集 -> 商品与素材草稿 -> 客服候选回复 -> ERP/订单中台 -> 人工确认执行
```

不要第一步就做自动发布、自动改价、自动退款、自动发货。当前项目最适合先做：

```text
商品档案 -> 标题/卖点/主图/详情页/短视频脚本 -> 平台草稿任务 -> 客服候选回复 -> 线索跟进
```

## 最推荐先接的项目

### 1. `TonyWang-hub/mcp-cn-commerce`

- 链接：<https://github.com/TonyWang-hub/mcp-cn-commerce>
- 定位：中国电商平台 MCP 连接器。
- 覆盖：巨量引擎、抖店、京东、淘宝、拼多多等经营数据。
- 语言：Python。
- 许可证：MIT。
- 适合当前项目：非常适合。

为什么推荐：

- 它的定位不是“模拟点击”，而是让 AI agent 读取商家经营数据。
- 正好契合当前系统的“平台连接器状态页”和“只读/草稿/需确认/禁止自动执行”安全分层。
- 可优先接成只读数据 worker，用于读取订单、商品、库存、售后、广告表现。

接入方式：

- 第一阶段只读，不写平台数据。
- 在当前后端新增 `PlatformConnector` 和 `PlatformReadTask`。
- 使用它的 MCP/平台思路映射到当前 `/api/ecommerce/automation-snapshot`。

风险：

- 项目较新，star 少。
- 要依赖各平台开放平台凭证。

### 2. `zeasin/qihang-ecom-erp-open`

- 链接：<https://github.com/zeasin/qihang-ecom-erp-open>
- 定位：电商 ERP/业务中台底座。
- 覆盖：淘宝、京东、拼多多、抖店、微信小店、快手、小红书。
- 技术栈：SpringCloud + Vue。
- 许可证：AGPL-3.0。
- 适合当前项目：适合参考模型，不建议直接并入。

为什么推荐：

- 它覆盖商品、订单、售后、库存、电子面单等完整 ERP 流程。
- 对“国内电商自动化到底有哪些对象”很有参考价值。
- 有 OpenAPI/CLI 供 AI 调用的方向，和你想做的 AI 中台接近。

接入方式：

- 不整包搬进当前项目。
- 抽数据模型：商品、订单、售后、库存、发货、店铺参数。
- 当前项目只做轻量版任务队列和草稿任务。

风险：

- AGPL-3.0，商业闭源使用要谨慎。
- 系统很大，直接集成会拖慢 MVP。

### 3. `cs-lazy-tools/ChatGPT-On-CS`

- 链接：<https://github.com/cs-lazy-tools/ChatGPT-On-CS>
- 定位：多平台 AI 客服工具。
- 覆盖：微信、拼多多、千牛、抖音企业号、抖音、抖店、小红书等。
- 语言：TypeScript。
- 许可证：AGPL-3.0，商业使用需看授权。
- 适合当前项目：适合参考客服和多平台消息结构。

为什么推荐：

- 和你已有的 `ai-kefu-opensource`、`kouzi-plugins` 方向一致。
- 支持的平台非常贴近国内商家。
- 可参考“多平台消息 -> 知识库 -> 候选回复”的结构。

接入方式：

- 当前系统先做“候选回复”，不自动发送。
- 抽象 `CustomerConversation`、`ReplySuggestion`、`ReplyRule`。
- 未来再考虑平台消息接入。

风险：

- AGPL-3.0 和商业授权问题。
- 自动回复容易踩平台风控，必须保留人工确认。

### 4. `tiktok/ttspc-server-sample` + `tiktok/ttspc-react-sample`

- 服务端示例：<https://github.com/tiktok/ttspc-server-sample>
- 前端示例：<https://github.com/tiktok/ttspc-react-sample>
- 定位：TikTok Shop API sample app 和 middleware server。
- 技术栈：TypeScript / Express / React。
- 许可证：MIT。
- 适合当前项目：适合做 TikTok Shop 官方 API 接入参考。

为什么推荐：

- 官方 sample，适合学习授权、middleware server 和前端管理页的边界。
- 如果后面做跨境/TikTok Shop，这比非官方爬虫更稳。

接入方式：

- 单独做 `tiktok_shop_adapter`。
- 先实现授权状态、商品/订单只读。
- 不在当前 MVP 里优先做，除非你明确要做跨境。

风险：

- TikTok Shop API 权限和地区要求要单独申请。
- 和国内抖店不是一套接口。

## 可参考但不建议直接并入

### 5. `iMactool/jinritemai`

- 链接：<https://github.com/iMactool/jinritemai>
- 定位：抖店开放平台 SDK。
- 语言：PHP。
- 适合：看抖店接口封装方式。
- 不建议直接并入：当前项目是 Python + React，语言栈不匹配；许可证信息不清晰。

### 6. `NanmiCoder/MediaCrawler`

- 链接：<https://github.com/NanmiCoder/MediaCrawler>
- 定位：小红书、抖音、快手、B 站、微博、贴吧、知乎等内容/评论采集。
- 适合：做竞品内容、评论、爆款分析。
- 不建议直接接到商家后台核心流程：它偏采集/爬虫，平台风控和合规风险较高。

### 7. `Evil0ctal/Douyin_TikTok_Download_API`

- 链接：<https://github.com/Evil0ctal/Douyin_TikTok_Download_API>
- 定位：抖音、TikTok、快手、Bilibili 数据解析和下载 API。
- 许可证：Apache-2.0。
- 适合：内容素材采集、视频链接解析、竞品素材下载。
- 不建议作为电商自动化主链路：它不是店铺/订单/商品 API。

### 8. `JeremyDong22/taobao_mcp`

- 链接：<https://github.com/JeremyDong22/taobao_mcp>
- 定位：淘宝/天猫商品信息抓取 MCP。
- 适合：商品调研、竞品分析、价格对比。
- 风险：偏 scraping，不适合做商家后台正式自动化。

### 9. `liuliang520530/taoke-mcp`

- 链接：<https://github.com/liuliang520530/taoke-mcp>
- 定位：淘宝客、京东客、多多客 MCP，偏转链接和搜索。
- 适合：淘客/导购场景。
- 当前项目优先级：低，除非要做分销/带货链接。

### 10. `witty-suckerpunch492/daihuo-jianshou`

- 链接：<https://github.com/witty-suckerpunch492/daihuo-jianshou>
- 定位：上传商品图，AI 生成电商带货短视频。
- 适合：参考商品图到短视频的产品流程。
- 风险：许可证不清晰；先只参考交互和流程。

## 选型排序

### 第一优先级：现在就能服务当前项目

1. `TonyWang-hub/mcp-cn-commerce`
2. `zeasin/qihang-ecom-erp-open`，只参考模型
3. `cs-lazy-tools/ChatGPT-On-CS`，只参考客服结构

### 第二优先级：内容/视频/竞品分析

4. `Evil0ctal/Douyin_TikTok_Download_API`
5. `NanmiCoder/MediaCrawler`
6. `witty-suckerpunch492/daihuo-jianshou`

### 第三优先级：跨境/TikTok Shop

7. `tiktok/ttspc-server-sample`
8. `tiktok/ttspc-react-sample`
9. `tiktok/tiktok-business-api-sdk`

## 对当前仓库的建议接法

### 阶段 1：国内电商只读连接器

新增：

```text
PlatformConnector
PlatformCredentialStatus
PlatformReadTask
MerchantSnapshot
```

页面展示：

- 抖店：只读/待授权。
- 淘宝：只读/待授权。
- 京东：只读/待授权。
- 拼多多：只读/待授权。
- TikTok Shop：规划中。

后端接口：

```text
GET /api/platform-connectors
GET /api/platform-snapshots
POST /api/platform-read-tasks
```

### 阶段 2：商品草稿任务

新增：

```text
ProductDraftTask
ListingFieldMapping
ProductPublishChecklist
```

能力：

- 标题生成。
- 卖点生成。
- 主图 prompt。
- 详情页结构。
- 短视频脚本。
- 草稿字段映射。

安全：

- 不自动发布。
- 不自动改价。
- 不自动退款。
- 不自动发货。

### 阶段 3：客服候选回复

参考 `ChatGPT-On-CS` 和本地 `ai-kefu-opensource`：

```text
Conversation
ReplySuggestion
ReplyRule
KnowledgeBaseEntry
```

能力：

- 粘贴私信。
- AI 识别意图。
- 生成 3 条候选回复。
- 一键转线索跟进。

### 阶段 4：TikTok Shop adapter

参考官方 sample：

```text
TikTokShopAuth
TikTokShopProductRead
TikTokShopOrderRead
```

只在你明确要做跨境/TK 店铺时启动。

## 安全分级

```text
read_only              读商品、订单、库存、评论、广告数据
draft_only             生成标题、素材、草稿字段、候选回复
requires_confirmation  创建平台草稿、复制回复、同步库存建议
blocked                发布、改价、退款、发货、自动群发
```

## 推荐下一步

先把 `mcp-cn-commerce` 的平台连接器概念并入当前系统，不实际接真实账号也可以：

1. 后端新增平台连接器 mock 数据。
2. 前端新增“国内电商连接器”面板。
3. 每个平台显示能力、授权状态、安全等级。
4. 商品档案页可以生成“抖店/淘宝/京东/拼多多草稿任务”。

这样能最快把“TK/国内电商自动化”的产品形态展示出来，同时不碰高风险自动执行。

