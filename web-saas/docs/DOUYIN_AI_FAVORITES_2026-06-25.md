# 抖音 AI 收藏分析与本地项目接入建议

日期：2026-06-25

## 本次读取情况

已使用 Chrome 读取当前登录抖音账号 `美式.` 的收藏页：

- 页面：`https://www.douyin.com/user/self?from_tab_name=main&showSubTab=video&showTab=favorite_collection`
- 位置：`收藏 > 视频`
- 读取方式：只读 DOM 快照，不执行点赞、取消收藏、私信、发布等动作。
- 限制：抖音收藏页较重，首屏读取成功；继续滚动时浏览器会话超时，所以本报告基于首屏高置信样本，并结合仓库已有审计文档。

## 首屏强相关收藏样本

- `用Codex + HyperFrames搞定你的口播剪辑 #ai剪辑 #hyperframes`
- `把所有Agent拉进一个群... #codex #claude #cursor #TRAE #vibecoding`
- `卡帕西刚引爆的 LLM Wiki 学习潮 #Karpathy #Claude #Obsidian #第二大脑`
- `我终于实现了AI自动化剪视频，公开下10分钟工作流 #Claudecode #Codex #剪辑 #AI #自媒体`
- `花 5 分钟用 codex 剪辑了一条 40s 的科普视频 #ai #codex #vibecoding`
- `真正的 AI 落地，不看 AI 干多少，看人能从中抽出来多少 #ai自动化 #github优质项目 #一人公司`
- `现在深圳做跨境电商的都进化到用AI自动化干活了吗 #跨境电商 #AI`
- `只演示一遍，Codex开始批量改商品...让Codex直接学我的抖店商品草稿编辑流程 #Codex #Replay #Record #RPA`
- `盘点一周AI大事...Codex开放第三方模型接入...动作生成模型...语音合成模型`

## 主题判断

你的 AI 收藏不是泛泛追热点，主题非常集中：

1. **Codex + 操作自动化**
   - 关注点不是“AI 写一段文案”，而是让 AI 接管一段真实运营流程。
   - 关键概念是 Record/Replay、把人工演示沉淀成 skill、让重复活变成 worker。

2. **电商运营自动化**
   - 收藏里出现跨境电商、抖店商品草稿、批量改商品。
   - 产品方向应覆盖商品资料、标题、主图、详情页、价格库存、上架草稿、客服承接。

3. **短视频生产线**
   - Codex + HyperFrames、AI 剪辑、口播剪辑、科普视频，都指向“结构化出片流水线”。
   - 视频模块不应只是一个剪辑按钮，而应包含脚本、分镜、字幕、配音时间轴、素材路径和验收标准。

4. **多 Agent 与知识系统**
   - 多 Agent 进群、LLM Wiki、Obsidian 第二大脑，说明你需要把经验、案例、流程、平台规则变成可复用知识库。

5. **开源与私有化**
   - GitHub 优质项目、一人公司、私有化部署是变现线索。
   - 适合做“开源核心 + 私有部署/模板/平台适配收费”，而不是只做封闭小工具。

## 对当前仓库的产品结论

当前 `商剪增长画布` 不应该收缩成“AI 剪辑软件”。更准确的定位是：

```text
商家 AI 运营中台：
商品/门店输入 -> 素材生成 -> 短视频生成 -> 客服承接 -> 平台草稿 -> 线索跟进
```

短视频是获客入口和交付物之一，真正的价值是把商家的重复运营动作流程化、结构化、可复用。

## 本地项目可接入优先级

### P0：先接入当前后台的数据结构

1. `C:\Users\Administrator\ecommerce-automation-hub`
   - 可复用：商品、库存、订单、平台连接器、自动化任务队列。
   - 接入方式：把模型思想并入当前 FastAPI，不整包合并 Node 服务。
   - 对应当前模块：`/api/ecommerce/automation-snapshot`。

2. `C:\Users\Administrator\merchant_ai_app`
   - 可复用：线索、跟进、报价、交付、页面采集 CSV 模板。
   - 接入方式：迁移成 Lead/FollowUp/Quote/Delivery 数据模型。
   - 对应当前模块：线索增长 CRM。

3. `C:\Users\Administrator\ai_douyin_video`
   - 可复用：`make_storyboard.py`、`compose_video.py`、口播文案、MP4 成片。
   - 接入方式：抽成短视频模板和验收样例，先不直接并入渲染链路。
   - 对应当前模块：短视频工厂、HyperFrames/Remotion 出片。

### P1：做客服闭环

4. `C:\Users\Administrator\ai-kefu-opensource`
   - 可复用：多平台客服、知识库、AI 回复、统计接口。
   - 接入方式：先复制知识库和客服接口设计，不直接整合完整 SaaS。
   - 对应当前模块：私信客服、商品 FAQ、候选回复。

5. `C:\Users\Administrator\kouzi-plugins`
   - 可复用：`IPlugin`、`PluginManager`、`MessageBroker`、关键词/Coze 混合回复。
   - 接入方式：作为平台插件层的设计参考，先落“插件状态 + 规则 + 消息队列”接口。
   - 当前可识别插件：`douyin`、`taobao`、`wecom`、`xianyu`。

### P2：再做本地执行器

6. `C:\Users\Administrator\kouzhi-agent`
   - 可复用：PyQt6、Playwright、SQLite、本地平台执行器。
   - 接入方式：作为浏览器自动化 worker，不直接让线上后台执行高风险动作。
   - 安全边界：发布、改价、退款、发货都必须人工确认。

7. `C:\Users\Administrator\merchant_ai_runtime`
   - 可复用：公开页面采集、登录态页面采集。
   - 接入方式：作为只读采集 worker，帮助分析店铺/商品/竞品页面。

8. `C:\Users\Administrator\rent-car-hyperframes`
   - 可复用：HyperFrames 实战模板、`hyperframes.json`、渲染样例。
   - 接入方式：作为商品短视频模板样板，复制设计和验收标准。

## 插件/开源仓库取舍

当前仓库里已经记录的开源参考是合理的：

- `302ai/302_ecom_image_generator`：参考商品主图、场景图、详情图生成。
- `pkp666/product-ai-listing-studio`：参考商品档案和平台字段映射。
- `leosssvip-dot/remotion-ad-video-skill`：参考商品 URL 到广告视频的流程。
- `remotion-dev/remotion`：第二阶段做批量视频渲染。
- `chatwoot/chatwoot`：后续有客服团队协作需求再接。
- `enescingoz/awesome-n8n-templates`：参考自动化流程，不建议一开始嵌入 n8n。
- `nexscope-ai/eCommerce-Skills`：参考如何把电商经验写成 markdown skills。

## 下一步落地建议

1. 新增 `merchant-workflow-replay` 概念
   - 输入：人工演示步骤、目标平台、操作对象、风险等级。
   - 输出：可回放步骤 JSON、人工确认节点、worker 任务。

2. 强化商品档案
   - 增加平台字段映射：抖店、淘宝、京东、拼多多。
   - 让主图、详情图、短视频、客服话术都从同一个商品档案生成。

3. 做轻量插件状态页
   - 展示平台连接器：抖音、淘宝、企微、闲鱼。
   - 展示状态：未授权、已授权、只读、草稿模式、需人工确认。

4. 做客服候选回复，不自动发送
   - 接 `ai-kefu-opensource` 与 `kouzi-plugins` 的规则思想。
   - 所有私信回复先生成候选，最后由人工确认发送。

5. 视频模块走结构化出片
   - 当前先保留 HyperFrames render-plan。
   - 下一步把 `ai_douyin_video` 的分镜与 `rent-car-hyperframes` 的模板验收标准合并。

## 抖音内容选题建议

- `我用 Codex + HyperFrames 给商家自动剪一条口播视频`
- `只演示一遍，让 AI 学会改商品草稿`
- `老板一句话，自动生成主图、详情页、短视频和客服话术`
- `AI 客服不是自动乱回，是先生成候选回复给人确认`
- `商家运营经验怎么变成一个可复用 skill`
- `为什么 AI 剪辑工具不值钱，值钱的是完整运营流水线`

