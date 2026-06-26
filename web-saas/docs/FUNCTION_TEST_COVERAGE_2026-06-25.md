# 功能测试与覆盖清单

日期：2026-06-25

这份文档记录当前我改过/新增过的主要文件、怎么测试、哪些是假按钮/临时数据/未覆盖情况。后续继续开发时，必须更新这份清单或同类验收文档。

## 本次重点记忆

- 按钮能点不代表功能完成。必须说明背后有没有 API、有没有数据库、有没有持久化。
- 页面有数据不代表是真数据。必须说明是 demo、sample、fallback、内存数据，还是数据库真实数据。
- 显示登录/订阅/连接成功必须有真实账号、会话、权限、订单、订阅、用量记录和后台可见记录。
- 商家 SaaS 需要后台数据库。建议上阿里云 RDS PostgreSQL/MySQL 或同级托管数据库。
- 管理员后台必须能看到商家、店铺连接、登录账号、订阅、用量、线索、任务、产物、失败原因和成本。

## 改过/新增的主要文件

### 电商日报自动化

- `data/ecommerce_daily_sample.json`
- `scripts/commerce_daily_report.py`
- `data/artifacts/commerce_reports/ai-commerce-daily-report-2026-06-25.md`
- `run_daily_report.bat`
- `docs/AUTOMATED_COMMERCE_DAILY_REPORT.md`
- `backend/main.py`
- `package.json`

功能：

- 本地读取 sample JSON。
- 自动计算 GMV、订单、客单价、退款率、热销商品、库存预警、差评原因。
- 输出 Markdown 日报。
- 后端新增 `POST /api/ecommerce/daily-report`。

已测试：

```bash
npm run auto:daily-report
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m py_compile scripts\commerce_daily_report.py backend\main.py
```

结果：

- 命令通过。
- 日报文件成功生成。
- Python 编译通过。

未覆盖：

- 没接真实抖店/淘宝/京东/拼多多 API。
- 没接 `mcp-cn-commerce` 的真实数据流。
- 没有定时任务。
- 没有商家账号隔离。
- 没有数据库持久化日报记录。

假/临时数据：

- `data/ecommerce_daily_sample.json` 是 sample 数据。
- API 返回 `source="sample"`。

### 商品上架 Codex 插件

- `codex-plugins-marketplace/.agents/plugins/marketplace.json`
- `codex-plugins-marketplace/plugins/merchant-listing-automation/.codex-plugin/plugin.json`
- `codex-plugins-marketplace/plugins/merchant-listing-automation/README.md`
- `codex-plugins-marketplace/plugins/merchant-listing-automation/skills/ecommerce-listing-draft/SKILL.md`
- `C:\Users\Administrator\.codex\config.toml`

功能：

- 新建本地 Codex 插件市场。
- 新建 `Merchant Listing Automation` 插件。
- 定义“商品资料 -> 上架草稿 -> 人工确认”的 skill 规则。

已测试：

```bash
codex plugin marketplace add C:\Users\Administrator\Documents\运营\codex-plugins-marketplace
codex plugin marketplace --help
```

结果：

- 本地 marketplace 添加成功。
- 配置已启用 `merchant-listing-automation@merchant-codex-plugins`。

未覆盖：

- 当前会话不会热加载新插件，需要重启 Codex 或新开会话。
- 插件本身只是 operator workflow，不是 SaaS 前端功能。
- 没有真正自动打开抖店后台填字段。
- 没有平台发布/保存草稿 API。

安全边界：

- 只能生成草稿。
- 发布、改价、改库存、退款、发货、发消息都必须人工确认。

### Ceeon videocut-skills

- `external/videocut-skills-ceeon/`
- `C:\Users\Administrator\.codex\skills\ceeon-videocut-skills`
- `docs/CEEON_VIDEOCUT_FRONTEND_2026-06-25.md`
- `docs/VIDEOCUT_SKILLS_INSTALL_2026-06-25.md`

功能：

- 删除了之前不满意的 `chengfeng-videocut-skills` 安装目录。
- 拉取用户指定的 `Ceeon/videocut-skills`。
- 安装为 `ceeon-videocut-skills`。
- 修改 skill 名称以区分来源：
  - `ceeon-videocut-skills:剪口播`
  - `ceeon-videocut-skills:口播成片`
  - `ceeon-videocut-skills:自进化`

已测试：

```bash
Test-Path C:\Users\Administrator\.codex\skills\ceeon-videocut-skills
```

结果：

- 新目录存在。
- 旧 `chengfeng-videocut-skills` 目录已删除。

未覆盖：

- 没有真实跑 FFmpeg。
- 没有真实跑火山转写。
- 没有真实生成审核页。
- 没有真实导出 MP4。
- 没有测试 sample 视频。

### VideoCut 前端工作台

- `videocut-workbench/index.html`
- `videocut-workbench/README.md`

功能：

- 静态前端任务台。
- 可填写项目名、任务类型、画幅、视频路径、口播稿、素材路径。
- 自动生成任务 JSON。
- 自动生成给 Codex skill 的执行提示词。
- 可复制提示词。
- 可下载任务 JSON。

怎么测试：

1. 双击打开 `videocut-workbench/index.html`。
2. 修改项目名、视频路径、口播稿。
3. 看任务 JSON 是否同步变化。
4. 点“复制执行提示词”，确认剪贴板有内容。
5. 点“下载任务 JSON”，确认浏览器下载 JSON。

假按钮/临时状态：

- “复制执行提示词”是真按钮，只复制文本。
- “下载任务 JSON”是真按钮，只下载本地 JSON。
- 页面不会上传视频。
- 页面不会调用后端。
- 页面不会跑 FFmpeg。
- 页面不会生成审核页。
- 页面不会导出 MP4。
- 刷新后输入内容会丢失，因为没有 localStorage 和数据库。

### Product Kit 静态销售包

- `product-kit/index.html`
- `product-kit/README.md`
- `product-kit/sample-daily-report.md`
- `product-kit/customer-intake.md`
- `product-kit/sales-script.md`
- `product-kit/delivery-sop.md`
- `product-kit.zip`

功能：

- 静态销售演示页。
- 静态样例日报。
- 静态客户资料表和销售话术。

怎么测试：

1. 双击 `product-kit/index.html`。
2. 点击顶部链接，确认跳转到页面锚点或本地 Markdown 文件。

假/临时内容：

- 所有价格、日报、客户数据都是样例。
- 没有表单提交。
- 没有支付。
- 没有登录。
- 没有数据库。
- 没有真实客户数据保存。

### Remotion 创业视频

- `videos/ai-startup-remotion/`
- `videos/ai-startup-remotion/out/ai-startup-workflow-douyin.mp4`

功能：

- 已生成 1080x1920 抖音视频 MP4。

已测试：

- `npm run lint` 在该 Remotion 项目通过。
- 渲染过 still frames 和最终 MP4。
- ffprobe 确认约 51.05 秒、1080x1920、30fps、H.264/AAC。

未覆盖：

- 没接到主 SaaS 的作品库。
- 没有云端渲染任务队列。
- 没有用户上传素材后自动生成视频。

## 主前端当前风险

文件：

- `src/main.tsx`
- `backend/main.py`

已知情况：

- 主前端 build 通过。
- 很多页面有 fallback/demo 数据。
- 线索、项目、任务、资产存储在后端内存字典里，重启丢失。
- 套餐是静态数组，不是真订阅。
- `/api/render` 是模拟进度，最后写 JSON，不生成真实 MP4。
- 图片接口缺 key 或失败时会回退 prompt，不一定产出真实图片。
- 插件市场页面更像状态面板，不是真正安装插件的用户界面。

已测试：

```bash
npm run build
```

结果：

- TypeScript + Vite build 通过。

未覆盖：

- 没有 Playwright 全流程点击测试。
- 没有后端启动后的 API 集成测试。
- 没有刷新/重启后的持久化测试。
- 没有多商家权限隔离测试。

## 后台数据库需求

需要上数据库。可以用阿里云 RDS PostgreSQL 或 MySQL。

最小表：

- `users`
- `merchants`
- `merchant_members`
- `merchant_store_connections`
- `projects`
- `assets`
- `leads`
- `conversations`
- `messages`
- `generation_jobs`
- `listing_drafts`
- `daily_reports`
- `artifacts`
- `subscriptions`
- `orders`
- `usage_records`
- `api_keys`
- `plugin_configs`
- `audit_logs`
- `admin_events`

管理员后台必须看到：

- 商家列表
- 商家登录账号
- 店铺连接状态
- 订阅状态
- 付款订单
- 用量记录
- 线索
- 生成任务
- 失败原因
- 成本
- 产物下载地址
- 操作日志

## 下一步优先级

1. 上数据库：阿里云 RDS PostgreSQL/MySQL。
2. 做真实登录：用户、商家、管理员、session/JWT。
3. 做真实订阅：套餐、订单、有效期、额度、用量。
4. 改造 leads/projects/tasks/assets，从内存改数据库。
5. 给每个按钮补真实 API、错误提示、loading、成功状态。
6. 接对象存储 OSS：图片、视频、日报、任务 JSON 都要有真实文件地址。
7. 做商家店铺连接：先只读，保存授权状态和失败原因。
8. 做后台管理页：你能看到所有商家、订阅、任务、产物和成本。
9. 再接 VideoCut 后端 runner：上传视频、审核页、FFmpeg、转写、导出 MP4。
10. 最后做自动填商品草稿：Chrome/电脑插件填后台，只保存草稿，发布前人工确认。

