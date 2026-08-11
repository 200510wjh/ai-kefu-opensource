# 阶段四 AI Engine 重构报告

生成时间：2026-07-16

## 一、阶段目标

本阶段目标是完成 AI Engine 深化，让业务模块不再各自散落实现 AI 能力。

本阶段围绕既定产品“AI 商家运营工作台”，不新增产品方向，只沉淀统一 AI 能力：

- 回复
- 意向评分
- 风险识别
- 对话总结
- 脚本生成
- 商品文案
- Prompt 生成

## 二、本阶段完成内容

### 1. 扩展 `backend/platform/ai_engine.py`

新增统一能力模型：

- `RiskAssessmentResult`
- `IntentScoreResult`
- `ConversationSummaryResult`
- `AITextResult`

新增统一能力方法：

- `AIEngine.assess_risk`
- `AIEngine.score_intent`
- `AIEngine.generate_reply`
- `AIEngine.summarize_conversation`
- `AIEngine.generate_script`
- `AIEngine.generate_product_copy`
- `AIEngine.generate_prompt`

这些方法都支持在未配置模型时使用规则兜底，避免系统因为 AI Key 或模型配置问题完全不可用。

### 2. 客服路径接入 AI Engine

修改文件：

- `backend/customer_service_saas.py`

已将客服路径中的核心能力覆盖为 AI Engine 调用：

- `risk_flags_for` -> `AIEngine.assess_risk`
- `score_intent` -> `AIEngine.score_intent`
- `call_ai_reply` -> `AIEngine.generate_reply`

保留原接口名，避免破坏旧路由和旧调用方。

### 3. 新增 `/api/v1/ai-engine/*` 能力接口

修改文件：

- `backend/api_v1.py`

新增统一接口：

- `POST /api/v1/ai-engine/risk`
- `POST /api/v1/ai-engine/intent-score`
- `POST /api/v1/ai-engine/conversation-summary`
- `POST /api/v1/ai-engine/reply`
- `POST /api/v1/ai-engine/script`
- `POST /api/v1/ai-engine/product-copy`
- `POST /api/v1/ai-engine/prompt`

所有接口都使用第三阶段确定的统一返回格式：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "uuid",
  "elapsed_ms": null
}
```

## 三、能力边界

### 回复

统一入口：`AIEngine.generate_reply`

使用方式：

- 如果 AI 已配置：调用模型生成自然回复。
- 如果 AI 未配置：返回业务传入的 fallback 文案。
- 如果 AI 回复过于机械：客服模块回退到本地成交型话术。

### 意向评分

统一入口：`AIEngine.score_intent`

当前基于关键词和风险因素计算 0-95 分，后续可以升级为模型评分，但业务层无需改接口。

### 风险识别

统一入口：`AIEngine.assess_risk`

当前识别：

- 退款 / 售后
- 投诉 / 差评
- 付款 / 资金
- 账号 / 权限
- 隐私信息
- 发票 / 合同

风险命中后返回 `need_followup=true`。

### 对话总结

统一入口：`AIEngine.summarize_conversation`

AI 配置可用时使用模型总结；未配置时使用最近一轮消息生成简要兜底。

### 脚本生成

统一入口：`AIEngine.generate_script`

返回结构化 JSON：

- `title`
- `opening`
- `steps`
- `objection_replies`
- `closing`

### 商品文案

统一入口：`AIEngine.generate_product_copy`

返回结构化 JSON：

- `title`
- `short_title`
- `selling_points`
- `detail_sections`
- `customer_faq`

### Prompt 生成

统一入口：`AIEngine.generate_prompt`

返回：

- `prompt`
- `negative_prompt`

## 四、验证结果

已执行并通过：

- `python -m py_compile backend\main.py backend\api_v1.py backend\customer_service_saas.py backend\platform\api.py backend\platform\cache.py backend\platform\security.py backend\platform\ai_engine.py backend\platform\connectors.py backend\platform\workflow.py backend\modules\models.py`
- `npm run build`
- `npm run secret-scan`
- TestClient AI Engine 冒烟：
  - `/api/v1/ai-engine/risk`
  - `/api/v1/ai-engine/intent-score`
  - `/api/v1/ai-engine/conversation-summary`
  - `/api/v1/ai-engine/reply`
  - `/api/v1/ai-engine/script`
  - `/api/v1/ai-engine/product-copy`
  - `/api/v1/ai-engine/prompt`

验证结论：

- 后端编译通过。
- 前端构建通过。
- 密钥扫描通过。
- AI Engine 所有新增能力接口可用。
- 未配置模型时也能返回规则兜底结果。

## 五、仍未完成的 AI 迁移项

以下能力仍需后续渐进迁移：

- `backend/main.py` 中部分旧回复助手逻辑仍保留自己的结构化 Prompt。
- MiniMax 图片生成仍有专用 Provider 逻辑，后续应做成 AI Engine 图片 Provider Adapter。
- 商品媒体工厂的部分本地绘图模板仍是规则生成，不属于模型能力，暂不强行迁移。
- 前端还没有全面改用 `/api/v1/ai-engine/*`，当前主要是后端统一出口完成。

## 六、是否可以进入第五阶段

可以进入第五阶段：Workflow。

第五阶段建议继续保持兼容式重构：

- 建立触发、条件、动作、运行日志的统一接口。
- 支持消息触发、线索触发、定时任务和人工触发。
- 先复用现有本机脚本和客服事件，不做可视化拖拽页面。
- 为未来拖拽工作流预留数据结构和 API。

