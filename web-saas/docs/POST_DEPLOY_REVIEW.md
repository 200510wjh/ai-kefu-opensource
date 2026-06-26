# 上线后自查与问题排查总结

更新时间：2026-06-24

## 当前结论

当前线上主入口：

- `https://wjhai.cn/merchant-admin/`
- `https://hupannongchang.com/merchant-admin/`

当前版本已经从普通后台升级为：

- 顶部导航 SaaS 应用壳。
- 首页 HyperFrames 作品集主视觉。
- 内容工厂、电商自动化、私信客服、线索增长、作品与渲染等独立板块。
- 微信/抖音/客服候选回复助手。
- HyperFrames showreel 独立页面：`/merchant-admin/hyperframes-portfolio.html`

## 最新验证结果

已验证：

- 线上 HTML 使用 `/merchant-admin/assets/...` 资源路径。
- JS bundle 包含 `novaShell`、`novaTopbar`、`novaHero`。
- JS bundle 引用了 `hyperframes-portfolio.html`。
- CSS 包含 `hyperPortfolioShell` 和 `novaAppCard:hover`。
- HyperFrames HTML 包含：
  - `data-composition-id="merchant-portfolio"`
  - `gsap.timeline`
  - `window.__timelines`
  - `floating-note`
  - `stats-row`
- `/merchant-admin/api/health` 返回 `ok`。
- `/merchant-admin/api/reply-assistant` 能返回 3 条候选回复。

## 已遇到的问题和处理

### 1. 页面不像 SaaS，只是一个长页面

问题：

- 早期版本把内容都堆在一个页面，虽然功能多，但不像完整产品。

处理：

- 改成顶部导航 SaaS 结构。
- 拆成：首页总控、内容工厂、电商自动化、私信客服、线索增长、作品与渲染。
- 首页不再放表单，改成产品主视觉和模块入口。

### 2. 视觉不够像 VibeCoding 作品集

问题：

- 普通深色后台仍然像管理系统，不像抖音里展示的作品集网站。

处理：

- 新增 `DESIGN.md` 定义黑金霓虹、VibeCoding、HyperFrames showreel 风格。
- 新增 `public/hyperframes-portfolio.html`。
- 首页第一屏嵌入 HyperFrames showreel。
- 加入 GSAP 动效、浮动标签、动态统计、分镜式展示。

### 3. HyperFrames 不能只做皮肤

问题：

- 只改 React/CSS 不能算真正用 HyperFrames。

处理：

- 新增独立 HTML composition。
- 使用 `data-composition-id`、`data-start`、`data-duration`、`data-width`、`data-height`。
- 使用 `window.__timelines` 注册 GSAP timeline。

### 4. `/merchant-admin/` 子路径资源容易错

问题：

- 普通 `npm run build` 会使用 `/` 作为资源路径，部署到 `/merchant-admin/` 后资源可能 404。

处理：

- 生产部署必须使用：

```powershell
$env:VITE_BASE_PATH='/merchant-admin/'; npm run build; Remove-Item Env:VITE_BASE_PATH
```

验证：

- 线上 HTML 当前资源路径为 `/merchant-admin/assets/...`。

### 5. `wjhai.cn` 根路径已有项目

问题：

- `wjhai.cn/` 原本是世界杯比分智能体，不能直接覆盖。

处理：

- 保留根路径。
- 只在 Nginx 中新增 `/merchant-admin/` 代理到 `127.0.0.1:8004`。

### 6. Nginx 配置时 PowerShell 插值破坏 `$host`

问题：

- 远程写 Nginx 配置时，PowerShell 把 `$host` 等变量提前替换，导致 Nginx 配置错误。

处理：

- 使用反引号转义 `$`，确保写入 Nginx 的是 `$host`、`$remote_addr` 等原始变量。
- 每次修改后必须执行：

```bash
nginx -t && systemctl reload nginx
```

### 7. C 盘空间不足

问题：

- Codex 目标状态写入失败，提示磁盘空间不足。
- 构建、缓存、浏览器插件运行也容易受影响。

处理：

- 清理 npm cache、Temp、浏览器 cache、Codex 临时目录。
- 当前剩余空间约 1.9GB。

后续建议：

- 定期保持 C 盘至少 5GB 可用。
- 大文件、视频、node_modules 尽量放 D 盘。

### 8. Chrome 插件运行缓存被清理后短期不可用

问题：

- 清理 `.cache` 后，Chrome 插件工具出现 `failed to write kernel assets`。

处理：

- 后续清理缓存要更谨慎，不要直接删整个运行时目录。
- 页面验证优先用 HTTP 资源和接口验证，浏览器截图作为补充。

### 9. 中文在 PowerShell 中偶尔显示乱码

问题：

- PowerShell 管道传中文到 Python/HTTP 时，可能出现问号或乱码。

处理：

- 接口真实 UTF-8 正常。
- 测试中文请求时可使用 Unicode escape 或直接从浏览器验证。

### 10. 敏感信息暴露风险

问题：

- 用户曾在聊天中提供服务器密码和 API Key。
- 服务器 systemd override 中存在 AI API Key 环境变量。

处理：

- 回复中不复述密钥。
- 本地运行 `python scripts/secret_scan.py`，未发现明显密钥进入仓库。

后续建议：

- 把服务器密钥定期轮换。
- 不要把真实 `.env`、systemd override、部署包提交到公开仓库。

## 当前残留风险

- 现在仍是 MVP，用户、权限、数据库、计费还没有完整生产级实现。
- AI 生成接口仍依赖外部 API 稳定性。
- 回复助手只生成候选，不应自动发送。
- HyperFrames showreel 是展示级 composition，后续若要批量渲染 MP4，需要接 HyperFrames CLI 或渲染 worker。
- Remotion 当前是页面中的 v1.5 渲染规格和产品路线，还没有独立 Remotion composition 工程。
- 当前本地仓库没有 GitHub remote，已参考开源项目，但还没有 fork/推送为公开仓库。
- C 盘空间仍偏低，建议继续释放到 5GB 以上。

## 2026-06-24 二次页面优化记录

用户追问：

- 页面还要继续优化。
- 抖音打法没有在页面里总结。
- 是否用了 GitHub 仓库。
- 用 Remotion 做出片路线。

处理：

- 首页新增 `Douyin GTM` 看板，展示 30 天抖音验证节奏：每天 3 条 demo、爆款标题模板、企业号主页承接、GitHub 开源引流。
- 首页新增 `GitHub / Open Source` 看板，明确当前项目没有 GitHub remote，同时列出已参考的仓库：
  - `302ai/302_ecom_image_generator`
  - `chatwoot/chatwoot`
  - `leosssvip-dot/remotion-ad-video-skill`
  - `remotion-dev/remotion`
- 线索增长页复用抖音增长看板，让获客打法不只停留在文档里。
- 作品与渲染页新增 `Remotion v1.5 接入规格`：
  - `1080 x 1920 · 30fps`
  - `9-18 秒`
  - `brief + scenes + brand tokens`
  - `useCurrentFrame`
- 已用 `/merchant-admin/` 子路径重新构建并部署到 `https://wjhai.cn/merchant-admin/`。

验证：

- SaaS 首页：`200`
- 健康接口：`/merchant-admin/api/health` 返回 `ok`
- 新构建资源：
  - JS：`/merchant-admin/assets/index-qXlZQ65d.js`
  - CSS：`/merchant-admin/assets/index-C5DC5Qv4.css`
- 构建产物已包含：
  - `抖音引流不是只发视频`
  - `当前项目还没有连接 GitHub remote`
  - `Remotion v1.5 接入规格`

## 2026-06-24 三次功能自检优化记录

用户追问：

- 继续优化功能。
- 确认功能是不是正常。
- 希望结合 Fireflies、HyperFrames、GitHub。

处理：

- 新增后端接口：`GET /api/system/diagnostics`
- 首页新增 `功能自检` 看板，直接展示：
  - 数据目录
  - AI 生成
  - HyperFrames 展示页
  - GitHub 仓库
  - Fireflies 会议纪要
  - 渲染任务队列
- Fireflies 当前不可用：本会话没有可用 Fireflies 插件，工具搜索和可安装插件列表都没有找到 Fireflies。页面已明确显示为 `warn`，建议先用文字粘贴方式沉淀商家需求。
- GitHub 当前仍是 `warn`：本地没有 GitHub remote，已经参考开源仓库，但还没发布自己的公开仓库。
- HyperFrames 当前为 `pass`：服务器检测到 `merchant-portfolio` composition 和 `window.__timelines`。
- 新增本地烟测脚本：`scripts/smoke_test.py`

线上烟测结果：

```json
{
  "health": "ok",
  "diagnostics": "warn",
  "providers": "ai",
  "scripts": {
    "count": 5,
    "scenes": 3
  },
  "hyperframes": "merchant-ecommerce-9x16",
  "reply_candidates": 3,
  "render": {
    "status": "done",
    "progress": 100,
    "artifact": true
  }
}
```

结论：

- 核心演示链路正常：页面、后端、AI 脚本、客服回复、HyperFrames 出片计划、模拟渲染任务都可用。
- 系统总状态是 `warn`，不是故障；原因是 GitHub remote、Fireflies 插件、真实 MP4 渲染 worker 还没接入。

## 2026-06-24 四次脚本客服闭环优化记录

用户确认：

- 可以不把视频、客服、电商自动化拆开做。
- 功能要先完整。
- 第一阶段优先用“脚本 + 客服”把成交闭环跑通。

处理：

- 新增后端模型：
  - `CustomerServiceLine`
  - `ScriptCustomerServiceKit`
- 新增接口：`POST /api/workflow/script-customer-service`
- 该接口输入当前商家需求和选中的脚本，输出：
  - 私信开场话术
  - 评论区引导话术
  - 需求筛选问题
  - 异议处理话术
  - 成交收口话术
  - 跟进节奏
  - 人工确认清单
- 内容工厂页面新增 `Scripted Customer Service` 模块，展示“短视频脚本如何接私信成交”。
- 烟测脚本 `scripts/smoke_test.py` 已加入脚本客服接口检查。

线上烟测结果：

```json
{
  "health": "ok",
  "diagnostics": "warn",
  "providers": "ai",
  "scripts": {
    "count": 5,
    "scenes": 3
  },
  "hyperframes": "merchant-ecommerce-9x16",
  "script_customer_service": {
    "opening": 2,
    "qualification": 3,
    "objections": 3,
    "closing": 2
  },
  "reply_candidates": 3,
  "render": {
    "status": "done",
    "progress": 100,
    "artifact": true
  }
}
```

页面资源验证：

- JS：`/merchant-admin/assets/index-Bnzm43CJ.js`
- CSS：`/merchant-admin/assets/index-C9dYa_-p.css`
- 构建产物包含：
  - `Scripted Customer Service`
  - `先用脚本客服跑通成交`
  - `scriptServicePanel`

结论：

- 当前第一阶段不做完整剪映式编辑器。
- 先把 `需求 -> 脚本 -> 分镜 -> 客服话术 -> 私信成交 -> 线索沉淀` 跑通。
- 视频生成继续保留 HyperFrames/Remotion 适配器，但成交闭环先靠脚本客服完成。

## 2026-06-24 五次图片生成/API2D 接入记录

用户提供：

- API2D 风格 key。
- 图片接口域名：`https://oa.api2d.net`

处理：

- 新增后端接口：`POST /api/images/generate`
- 新增图片生成适配器：
  - 支持 `IMAGE_PROVIDER`
  - 支持 `IMAGE_BASE_URL`
  - 支持 `IMAGE_MODEL`
  - 支持 `IMAGE_API_KEY`
  - 支持 `IMAGE_SIZE`
  - 支持 `IMAGE_RESPONSE_FORMAT`
- 内容工厂新增 `Product Image` 面板：
  - 主图
  - 场景图
  - 详情图
  - 有图则预览图片
  - 无图则显示可复制 prompt 和错误原因
- `.env.example` 新增图片生成配置。
- `scripts/smoke_test.py` 新增图片接口检查。

线上测试结果：

- 页面资源已包含 `主图/场景图/详情图生成`
- 页面资源已包含 `imageGenerationPanel`
- 健康接口正常：`/api/health` 返回 `ok`
- 图片接口能正常返回结构化结果，不会导致页面崩溃。

API2D 实测结果：

- 不传模型时，API2D 默认落到 `dall-e-2`，返回：`The model 'dall-e-2' does not exist.`
- 指定 `dall-e-3` 时，返回：`The model 'dall-e-3' does not exist.`
- 指定 `gpt-image-1` 时，返回：`Model must be dall-e-2 or dall-e-3, your model is gpt-image-1`

结论：

- 当前系统已经具备图片生成接口和页面入口。
- 当前 API2D key/账号在该图片接口上没有可用图片模型，暂时不能真实出图。
- 系统会自动 fallback 到 prompt 模式，商家主图/详情图 prompt 仍可复制到 302.AI、扣子工作流或其他图片模型生成。
- 下一步要真实出图，需要确认 API2D 账号是否开通图片模型，或换用支持图片生成的 OpenAI/302.AI/火山/通义万相接口。

## 2026-06-24 六次网页版 SaaS 首页设计调整

用户提醒：

- 这是网页版吗？
- 做出来前要想清楚为什么这样设计。
- 不好的地方自己改。
- 希望使用 HyperFrames、HeyGen、Fireflies、Remotion 这些插件/能力。

设计判断：

- 之前首页第一屏是 HyperFrames showreel，视觉上好看，但更像展示页，不像能马上使用的 SaaS 后台。
- 真正商家后台第一屏应该先回答：我要从哪里开始、现在系统状态如何、下一步做什么。
- 因此首页应该优先展示工作台和主流程，视觉 showreel 应该下移为作品展示。

调整：

- 首页第一屏改成 `Web SaaS Command Center`。
- 主标题改为：`商家从一句需求开始，先跑通脚本和客服成交。`
- 新增 `Primary Workflow`：
  - 创建需求
  - 生成脚本
  - 客服承接
  - 线索沉淀
- HyperFrames showreel 下移到后面，并缩小高度，变成作品展示，不再抢工作台入口。
- 新增 `AI Media Stack` 插件栈说明：
  - `HyperFrames`：HTML/GSAP 视频模板、作品展示、动态字幕和 9:16 出片计划。
  - `Remotion`：React 程序化视频、批量变体、品牌模板和 MP4 渲染 worker。
  - `HeyGen`：数字人口播、商家讲解、产品演示真人版。
  - `Fireflies`：商家会议纪要、需求提取、自动生成 brief。

插件状态：

- HyperFrames：已实际用于 showreel 和 render-plan。
- Remotion：已保留 v1.5 接入规格，后续接真实 composition/worker。
- HeyGen：当前会话没有暴露可直接调用的生成工具，先做产品接口位和数字人口播模块规划。
- Fireflies：当前会话搜索不到可用插件，先用文字粘贴/会议纪要导入替代。

线上验证：

- 首页资源：`/merchant-admin/assets/index-xNySfCsW.js`
- CSS 资源：`/merchant-admin/assets/index-DlBi-Mes.css`
- 构建产物已包含：
  - `商家从一句需求开始`
  - `Primary Workflow`
  - `作品展示放在后面`
  - `AI Media Stack`
  - `HeyGen`
  - `Fireflies`
- 烟测通过，核心功能未回退。

## 下次开发优先级

1. 接商品链接解析和商品档案。
2. 接主图/详情图真实生成 API。
3. 把 HyperFrames showreel 变成可配置模板。
4. 接作品渲染队列和下载 MP4。
5. 做用户登录、商户空间、额度计费。
6. 做线索 CRM 和客服知识库。
7. 做安全审计：密钥、日志、权限、自动化确认节点。

## 部署命令备忘

本地构建：

```powershell
npm run build
python scripts\secret_scan.py
python -m compileall backend
```

生产子路径构建：

```powershell
$env:VITE_BASE_PATH='/merchant-admin/'; npm run build; Remove-Item Env:VITE_BASE_PATH
```

服务器服务：

```bash
systemctl status merchant-growth-canvas.service
systemctl restart merchant-growth-canvas.service
```

Nginx：

```bash
nginx -t
systemctl reload nginx
```

## 2026-06-24 七次空入口与默认演示数据修复

用户反馈：
- 有些需求入口点进去是空的，不清楚是不是还需要额外插件或配置。

排查结论：
- 不是必须缺插件。
- 主要原因是前端有些模块只渲染接口返回的数据；当接口慢、失败、或还没有真实业务数据时，会显示成空板块。
- 空白风险集中在：电商自动化、SaaS 套餐、作品库、HyperFrames/Remotion 出片计划。

修复：
- 新增前端默认 SaaS 套餐：Starter、Pro、Agency。
- 新增默认电商自动化数据：抖音企业号、小红书店铺、淘宝/天猫商品连接器。
- 新增默认商品草稿和安全执行任务，页面即使没有真实平台账号也能看到完整流程。
- 新增默认 HyperFrames 9:16 渲染计划；接口返回真实计划后自动覆盖。
- 作品库空状态改成可操作状态，直接提供“生成 3 个版本”按钮。
- 新增兜底提示样式和说明文字，避免用户误以为系统坏了。

验证：
- `npm run build` 通过。
- 部署后刷新 `https://wjhai.cn/merchant-admin/` 验证所有导航入口都有内容。

## 2026-06-24 八次 Remotion / HeyGen 媒体插件栈接入

用户反馈：
- Remotion、HeyGen 这些插件应该接进系统里，而不是只写在规划里。

判断：
- Remotion 适合做真实的视频渲染 worker：React composition、1080x1920、批量变体、MP4 输出。
- HeyGen 适合做数字人口播视频：商家讲解、产品介绍、销售跟进视频。
- Codex 会话里的插件能力不能直接等同于线上 SaaS 的运行时能力；线上系统仍需要后端适配器、API key、任务状态、成本记录和人工确认。

已实现：
- 新增后端模型 `MediaPluginStatus`。
- 新增接口 `GET /api/integrations/media-stack`。
- 后端会检测：
  - HyperFrames showreel 是否存在。
  - `REMOTION_RENDER_URL` 是否配置。
  - `HEYGEN_API_KEY` 和 `HEYGEN_AVATAR_ID` 是否配置。
  - Fireflies 暂时作为规划项。
- 首页 `AI Media Stack` 改成接口驱动，不再是静态文字。
- 插件状态支持：
  - `ready`
  - `configured`
  - `needs_config`
  - `planned`
- 前端新增状态卡片样式，能显示下一步动作。

线上验证：
- `GET /merchant-admin/api/integrations/media-stack` 正常返回 4 个插件。
- 当前状态：
  - HyperFrames：ready。
  - Remotion：planned，等待 `REMOTION_RENDER_URL`。
  - HeyGen：needs_config，等待 `HEYGEN_API_KEY` 和 `HEYGEN_AVATAR_ID`。
  - Fireflies：planned。
- `python scripts\smoke_test.py https://wjhai.cn/merchant-admin` 通过。
