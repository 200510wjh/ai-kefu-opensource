# 可沉淀为 Skill 的模块

这些 skill 不是马上全做，而是按商业闭环优先级逐步沉淀。每个 skill 都应有清晰输入、输出和可验证结果。

## P0：先做，直接服务当前产品

### 0. `merchant-workflow-replay`

用途：把商家或运营人员的一次人工操作，整理成可复用的自动化流程。

输入：

- 人工演示步骤。
- 目标平台：抖店/淘宝/京东/拼多多/美团。
- 操作对象：商品草稿、订单、客服消息、素材上传。
- 风险等级：只读/草稿/需人工确认/禁止自动执行。

输出：

- 流程步骤 JSON。
- 可执行检查清单。
- 需要人工确认的节点。
- 可交给本地 worker 或浏览器自动化执行的任务。

来自抖音收藏页的依据：

- “只演示一遍，Codex 开始批量改商品”。
- “Record Replay / 把经验转成 skill”。
- “让 AI 直接操作各种软件”。

可接入项目：

- `kouzhi-agent`
- `kouzi-plugins`
- `ecommerce-automation-hub`
- 当前 `商剪增长画布`

### 1. `ecommerce-product-intake`

用途：把商品链接、商品图、卖点文本整理成结构化商品档案。

输入：

- 商品链接或商品标题。
- 商品图片。
- 价格、规格、目标人群。
- 当前卖点。

输出：

- 标准商品档案 JSON。
- 核心卖点。
- 禁用词/风险词。
- 可生成素材清单。

可接入项目：

- `merchant_ai_app`
- 当前 `商剪增长画布`
- `ecommerce-automation-hub`

### 2. `ecommerce-visual-pack`

用途：生成主图、场景图、详情页图的提示词和任务清单。

输入：

- 商品档案。
- 平台：淘宝/抖店/拼多多/小红书。
- 风格：高转化、品牌感、低价促销、礼盒、节日。

输出：

- 主图 prompt。
- 详情图结构。
- 场景图 prompt。
- 图片生成任务。

参考：

- 302 AI E-commerce Scene Image Generator。

### 3. `short-video-storyboard`

用途：生成抖音/小红书短视频脚本和分镜。

输入：

- 商品档案。
- 平台。
- 目标人群。
- 转化动作。

输出：

- 5 个选题方向。
- 每个方向 3-5 个分镜。
- 口播文案。
- 字幕。
- CTA。

可接入项目：

- 当前 `商剪增长画布`
- `ai_douyin_video`

### 4. `hyperframes-ad-render`

用途：把分镜 JSON 转成 HyperFrames HTML 视频模板。

输入：

- storyboard JSON。
- 商品图/Logo/背景音乐。
- 品牌色/字体。

输出：

- HyperFrames `index.html`。
- 预览链接。
- 可渲染 MP4 的素材目录。

参考：

- `rent-car-hyperframes`
- HyperFrames skill。

### 5. `ai-customer-service-reply`

用途：根据商品知识库生成客服建议回复。

输入：

- 用户消息。
- 商品 FAQ。
- 订单/物流状态。
- 店铺规则。

输出：

- 建议回复。
- 是否需要人工介入。
- 推荐优惠/成交动作。

可接入项目：

- `ai-kefu-opensource`
- `kouzhi-agent`
- `kouzi-plugins`

## P1：形成系统壁垒

### 6. `platform-plugin-evaluator`

用途：评估平台插件接入难度和风险。

输入：

- 平台名称。
- 可用 API/OAuth/后台页面。
- 目标动作。

输出：

- 官方 API 路线。
- 浏览器自动化路线。
- 风险动作清单。
- 人工确认边界。

可接入项目：

- `kouzi-plugins`
- `kouzhi-agent`

### 7. `store-ops-automation`

用途：生成商品上架草稿、库存同步、订单异常处理任务。

输入：

- 商品档案。
- 当前库存。
- 订单列表。
- 平台连接状态。

输出：

- 自动化任务队列。
- 人工确认清单。
- 异常订单提醒。

可接入项目：

- `ecommerce-automation-hub`

### 8. `merchant-lead-crm`

用途：把抖音私信、表单、微信客户、店铺链接转成可跟进商机。

输入：

- 商家名称。
- 店铺链接。
- 当前问题。
- 联系方式。

输出：

- 客户评分。
- 首轮私信。
- 推荐服务包。
- 报价区间。
- 跟进计划。

可接入项目：

- `merchant_ai_app`

## P2：增长和开源获客

### 9. `douyin-content-research`

用途：分析抖音收藏/爆款视频，提取可复制模板。

输入：

- 抖音视频链接列表或收藏页可见内容。
- 视频标题/字幕/评论。

输出：

- 选题类型。
- 开头钩子。
- 镜头结构。
- 成交 CTA。
- 可复用模板。

当前限制：

- 这次没有可用浏览器点击工具，也没有读取到收藏页详情。
- 需要用户打开收藏页或提供链接列表后继续。

### 10. `github-clone-evaluator`

用途：评估 GitHub 开源项目能否复制和集成。

输入：

- GitHub URL。
- 目标业务模块。

输出：

- 许可证风险。
- 技术栈。
- 可复用模块。
- 集成成本。
- 替代方案。

参考：

- 302 电商图生成。
- Open AI UGC。
- AdGen。
- Chatwoot。

### 11. `merchant-saas-deploy`

用途：一键部署当前商家 SaaS 到服务器。

输入：

- 服务器 SSH 信息。
- 域名。
- 目标端口。
- 环境变量。

输出：

- systemd 服务。
- Nginx 路由。
- 健康检查。
- 回滚说明。

已在当前项目中验证：

- `/opt/merchant-growth-canvas`
- `merchant-growth-canvas.service`
- `/merchant-admin/`
