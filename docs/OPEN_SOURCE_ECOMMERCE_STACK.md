# 电商自动化开源项目清单

更新时间：2026-06-24

## 先用哪几个

### 1. 商品图/场景图

- 仓库：<https://github.com/302ai/302_ecom_image_generator>
- 用途：上传产品图或模特图，结合场景描述生成电商可用商品图，也可生成场景图视频。
- 怎么用：接到当前后台的“主图/详情图”模块，先做 prompt 和任务结构，后面再接真实图片模型。

### 2. 商品 listing 工作台

- 仓库：<https://github.com/pkp666/product-ai-listing-studio>
- 用途：商品文案、平台字段映射、图片生成、卖货视频 workflow。
- 怎么用：参考它的产品档案和 marketplace field mapping，补当前系统的商品字段、平台字段、发布草稿结构。

### 3. 程序化广告视频

- 仓库：<https://github.com/leosssvip-dot/remotion-ad-video-skill>
- 用途：从 URL 生成可编辑广告视频项目，可选 Remotion 或 HyperFrames 渲染。
- 怎么用：和当前 `/api/hyperframes/render-plan` 对齐，把分镜 JSON 转成真实 HTML/CSS/GSAP 或 Remotion composition。

### 4. 视频渲染底座

- 仓库：<https://github.com/remotion-dev/remotion>
- 用途：用 React 程序化生成 MP4，适合批量模板视频。
- 怎么用：第二阶段用于品牌模板、商品混剪、批量变体。商业 SaaS 需再次确认 Remotion 许可。

### 5. AI 客服/会话后台

- 仓库：<https://github.com/chatwoot/chatwoot>
- 用途：开源客服会话后台。
- 怎么用：当前系统先做轻量客服话术和线索承接，不建议马上整合完整 Chatwoot；后续有真实客服需求再接。

### 6. 电商 Agent 工作流

- 仓库：<https://github.com/upsidelab/enthusiast>
- 用途：面向客服、内容生成、知识库自动化的 agentic workflow 工具包。
- 怎么用：参考 RAG、工作流编排、评估和防幻觉结构，做 AI 客服知识库。

### 7. 自动化模板库

- 仓库：<https://github.com/enescingoz/awesome-n8n-templates>
- 用途：大量 n8n 自动化模板，覆盖客服、CRM、表格、消息、OpenAI 等。
- 怎么用：参考“线索 -> 表格 -> 私信/邮件 -> 客服跟进”的流程，不要一开始把 n8n 嵌进主系统。

### 8. 电商 Skills

- 仓库：<https://github.com/nexscope-ai/eCommerce-Skills>
- 用途：把电商运营经验写成可被 AI 读取的 markdown skills。
- 怎么用：参考它的 skill 组织方式，沉淀自己的 `merchant-workflow-replay`、`ecommerce-product-intake`、`ecommerce-visual-pack`。

## 最推荐的复制顺序

1. 复制思想，不整包复制：先参考 `product-ai-listing-studio` 的商品字段和平台字段。
2. 接主图详情图：参考 `302_ecom_image_generator`。
3. 接视频模板：参考 `remotion-ad-video-skill`，优先 HyperFrames，后续 Remotion。
4. 接客服知识库：参考 `Chatwoot` 和 `Enthusiast`。
5. 接自动化流程：参考 `awesome-n8n-templates`，只抽流程，不引入复杂依赖。

## 当前产品对应关系

- 当前 `电商自动化工作台` -> 商品 listing + 平台草稿 + 人工确认。
- 当前 `AI 客服承接` -> Chatwoot/Enthusiast 的轻量前置版。
- 当前 `HyperFrames 出片计划` -> remotion-ad-video-skill 的 HTML/GSAP 路线。
- 当前 `Skill 候选文档` -> eCommerce-Skills 的本地化版本。
