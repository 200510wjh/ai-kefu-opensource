# 商家 AI 运营中台开工前设计稿

日期：2026-06-25

## 设计目标

先把当前 `商剪增长画布` 从“能生成脚本的 SaaS 原型”升级成“能演示完整商家运营闭环的中台”。第一版不追求全自动发布，也不直接整合所有本地项目，而是把最能卖钱、最能演示、最安全的链路跑通：

```text
商品/门店档案 -> 素材生成 -> 短视频分镜 -> 客服候选回复 -> 平台草稿任务 -> 线索跟进
```

这版设计来自三类依据：

- 抖音收藏页：Codex、HyperFrames、AI 剪辑、电商自动化、Record/Replay、GitHub skills。
- 本地项目：`ecommerce-automation-hub`、`merchant_ai_app`、`ai-kefu-opensource`、`kouzi-plugins`、`ai_douyin_video`、`merchant_ai_runtime`。
- 当前仓库：FastAPI 后端、React/Vite 前端、AI Provider、图片 prompt、HyperFrames render-plan、线索 CRM 已有雏形。

## 产品定位

产品名暂定：**商剪增长中台**。

一句话：

> 给商家和 AI 代理商用的电商运营自动化工作台，把商品、短视频、客服、平台草稿和线索跟进串成一个可控流程。

不做：

- 不做全自动发抖音。
- 不做未经确认的自动私信。
- 不做自动改价、退款、发货。
- 不在 MVP 阶段整包嵌入 Chatwoot、n8n、Remotion、扣子插件系统。

先做：

- 商品档案结构化。
- 主图/详情图/短视频/客服话术统一从商品档案生成。
- 平台动作只生成草稿任务和操作清单。
- 所有高风险动作进入“人工确认”状态。

## 第一版用户界面

### 1. 首页总控

目的：让用户一眼知道当前系统能做什么、哪些插件/平台已接好、哪些还在规划。

展示：

- 今日商品档案数。
- 已生成素材数。
- 待确认平台任务数。
- 新线索数。
- AI Provider 状态。
- 媒体插件状态：HyperFrames、Remotion、HeyGen。
- 平台插件状态：抖音、淘宝、企微、闲鱼。

操作：

- 新建商品档案。
- 查看待确认任务。
- 查看线索。

### 2. 商品档案

目的：替代零散输入框，成为所有生成动作的统一输入。

字段：

- 商品/门店名。
- 行业/类目。
- 平台：抖音、淘宝、京东、拼多多、小红书、视频号。
- 目标人群。
- 核心卖点。
- 价格/规格/库存。
- 素材链接或图片说明。
- 禁用词/风险点。
- 转化动作：私信、表单、到店、下单、预约。

生成出口：

- 主图 prompt。
- 详情页结构。
- 抖音短视频脚本。
- 客服 FAQ。
- 平台草稿任务。

### 3. 素材工厂

目的：把商品档案变成商家能复制走的素材。

内容：

- 主图 prompt。
- 场景图 prompt。
- 详情页段落结构。
- 卖点贴纸文案。
- 平台标题和短描述。

第一版交付方式：

- 先输出 prompt 和 JSON。
- 如果图片接口可用，再输出图片 URL。
- 保留下载结果。

### 4. 短视频工厂

目的：把收藏页里的 `Codex + HyperFrames` 方向落成产品。

输入：

- 商品档案。
- 视频平台。
- 口播风格。
- 时长：15 秒、30 秒、60 秒。
- 转化目标。

输出：

- 5 个选题方向。
- 每个方向 3-5 个分镜。
- 口播稿。
- 字幕。
- BGM/配音风格建议。
- HyperFrames render-plan。
- 验收清单。

第一版不直接真实渲染 MP4，先保持：

- JSON 交付。
- HTML/HyperFrames 预览。
- 后续接 Remotion 或 HyperFrames worker。

### 5. 客服承接

目的：把视频和商品生成后的流量接住。

输入：

- 商品档案。
- 客户私信。
- 客户标签：新客、比价、售后、代理商、批发。
- 目标：留资、预约、成交、解释、安抚。

输出：

- 意图摘要。
- 风险提醒。
- 3 条候选回复。
- 下一步追问。
- 是否需要人工介入。

安全规则：

- 只生成候选回复。
- 不自动发送。
- 不读取或提交敏感信息。

### 6. 平台插件与草稿任务

目的：把 `kouzi-plugins` 的插件思想轻量化接进当前后台。

展示平台：

- 抖音企业号。
- 抖店。
- 淘宝/天猫。
- 京东。
- 拼多多。
- 企业微信。
- 闲鱼。

每个平台显示：

- 连接状态：未配置、需登录、只读、草稿模式、已授权。
- 支持能力：读取商品、读取消息、创建草稿、回复建议、库存检查。
- 风险级别：只读、草稿、需确认、禁止自动执行。

第一版任务类型：

- 创建商品草稿。
- 生成标题/卖点。
- 生成回复候选。
- 库存预警。
- 订单异常提示。

禁止自动执行：

- 最终发布。
- 改价。
- 退款。
- 发货。
- 群发私信。

### 7. 线索 CRM

目的：把抖音私信、表单、微信客户、GitHub 部署咨询都沉淀下来。

字段：

- 来源：抖音、GitHub、微信、网站、手动。
- 商家名。
- 联系方式。
- 行业。
- 需求。
- 意向等级。
- 推荐套餐。
- 首轮回复。
- 跟进状态。
- 下次跟进时间。

输出：

- 首轮私信。
- 报价建议。
- 跟进计划。
- 交付清单。

## 后端设计

### 新增核心模型

```text
ProductProfile
PlatformDraft
PluginConnector
CustomerConversation
ReplySuggestion
WorkflowReplay
FollowUp
Quote
Delivery
```

### 推荐接口

```text
GET  /api/products
POST /api/products
GET  /api/products/{id}
PUT  /api/products/{id}

POST /api/products/{id}/generate-assets
POST /api/products/{id}/generate-video-plan
POST /api/products/{id}/generate-service-kit

GET  /api/platform-connectors
POST /api/platform-tasks
GET  /api/platform-tasks
POST /api/platform-tasks/{id}/confirm

POST /api/reply-suggestions
GET  /api/reply-rules
POST /api/reply-rules

GET  /api/crm/follow-ups
POST /api/crm/follow-ups
POST /api/crm/quotes
POST /api/crm/deliveries

POST /api/workflows/replay
GET  /api/workflows/replay
```

### 存储策略

MVP 继续使用本地 JSON/内存结构，保持部署简单。需要稳定后再迁移 SQLite 或 Postgres。

建议分目录：

```text
data/products.json
data/platform_tasks.json
data/plugin_connectors.json
data/reply_rules.json
data/followups.json
data/workflows.json
data/artifacts/
```

## 前端设计

当前 React 单文件已经比较大，第一版尽量少拆，但新增功能建议按组件分组：

```text
ProductProfilePanel
AssetFactoryPanel
VideoFactoryPanel
ReplySuggestionPanel
PluginConnectorPanel
PlatformTaskPanel
LeadCrmPanel
WorkflowReplayPanel
```

导航建议：

- 总控
- 商品档案
- 素材工厂
- 短视频
- 客服承接
- 平台任务
- 线索 CRM
- 作品库

## 本地项目接入方式

### `ecommerce-automation-hub`

只抽模型和演示数据：

- `Product`
- `Inventory`
- `Order`
- `AutomationJob`
- `PlatformConnector`

不合并 Node 服务。

### `merchant_ai_app`

迁移 CSV 概念：

- 线索。
- 跟进。
- 报价。
- 交付。
- 页面采集结果。

### `ai-kefu-opensource`

参考客服结构：

- 店铺。
- 知识库。
- FAQ。
- 平台消息。
- 统计。

第一版只做候选回复，不做自动回复。

### `kouzi-plugins`

参考插件抽象：

- `IPlugin`
- `PluginManager`
- `MessageBroker`
- `AutoReplyService`

当前仓库先实现状态和任务，不加载外部插件代码。

### `ai_douyin_video`

提取：

- 分镜结构。
- 口播文案。
- 剪映建议。
- 成片验收标准。

### `merchant_ai_runtime`

后续作为只读采集 worker：

- 公开页面采集。
- 登录态页面采集。
- 竞品页面分析。

## GitHub/开源路线

当前仓库没有 remote。公开前需要：

1. 跑 `python scripts/secret_scan.py`。
2. 补 README 截图和演示说明。
3. 确认 `.env.example` 不含真实 key。
4. 把定位写成“商家 AI 运营中台”，不要写成普通剪辑器。

开源参考的接入顺序：

1. `product-ai-listing-studio`：商品字段和平台字段映射。
2. `302_ecom_image_generator`：商品图和场景图生成思路。
3. `remotion-ad-video-skill`：广告视频生成流程。
4. `Chatwoot` / `Enthusiast`：客服知识库和工作流。
5. `eCommerce-Skills`：把运营经验沉淀成 skill。

## 安全边界

系统所有自动化动作分 4 级：

```text
read_only              只读分析
draft_only             只创建草稿
requires_confirmation  必须人工确认
blocked                禁止自动执行
```

默认规则：

- 读取收藏页、店铺页、商品页：`read_only`
- 生成商品标题、图片 prompt、视频脚本：`draft_only`
- 创建平台草稿、候选回复：`requires_confirmation`
- 发布、改价、退款、发货、群发消息：`blocked`

## 实施顺序

### 第 1 步：商品档案和平台任务

目标：让系统从“输入 brief”升级为“管理商品档案”。

改动：

- 后端新增 ProductProfile、PlatformTask。
- 前端新增商品档案页。
- 平台任务页展示草稿和确认状态。

验收：

- 能创建商品档案。
- 能基于商品档案生成素材/视频/客服。
- 能创建平台草稿任务。

### 第 2 步：插件状态页

目标：把抖音、淘宝、企微、闲鱼等作为连接器展示出来。

改动：

- 后端新增 `/api/platform-connectors`。
- 前端新增连接器状态面板。
- 显示每个平台的能力和安全等级。

验收：

- 页面能解释当前哪些平台是手动、只读、草稿或规划中。

### 第 3 步：客服与线索增强

目标：把候选回复和 CRM 串起来。

改动：

- 新增回复规则。
- 新增 FollowUp/Quote/Delivery。
- 私信候选回复可以一键转线索跟进。

验收：

- 粘贴私信后生成 3 条候选回复。
- 能保存为线索和跟进计划。

### 第 4 步：短视频模板增强

目标：把 HyperFrames render-plan 变成更接近真实出片的结构。

改动：

- 增加口播风格、字幕、配音、素材路径字段。
- 参考 `ai_douyin_video` 和 `rent-car-hyperframes` 增加验收清单。

验收：

- 生成的 JSON 可以交给 HyperFrames/Remotion worker。

### 第 5 步：Workflow Replay 原型

目标：回应收藏页里的 Record/Replay 核心兴趣。

改动：

- 新增人工演示步骤录入。
- 输出流程 JSON。
- 标记人工确认节点。

验收：

- 能把“改商品草稿”的步骤写成可复用流程。

## 开工条件

建议先实现第 1 步和第 2 步，因为它们最稳、最能提升产品骨架，也不会碰到高风险平台自动化。

第一轮代码改动范围建议控制在：

- `backend/main.py`
- `src/main.tsx`
- `src/styles.css`
- `docs/POST_DEPLOY_REVIEW.md` 或新增验收记录

第一轮验证：

```powershell
npm run build
python -m compileall backend
python scripts/secret_scan.py
```

