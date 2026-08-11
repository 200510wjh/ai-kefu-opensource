# 开源项目适配路线

当前主产品是“商家 AI 客服 SaaS”：网页气泡自动回复、知识库导入、客服脚本生成、渠道草稿和会话收件箱。

## 先不整套替换

Chatwoot、Tiledesk、LibreChat、Dify 都很强，但直接塞进当前项目会把产品主线变重。第一阶段建议只做适配层：

- 当前项目继续负责商家后台、知识库、脚本、套餐和线索。
- 第三方开源项目负责特定能力，例如工单、多渠道收件箱、RAG 文档检索或聊天机器人流程。

## 推荐适配顺序

### 1. Chatwoot

用途：完整客服收件箱、多渠道会话、团队坐席。

适配方式：

- 增加 `CHATWOOT_BASE_URL` 和 `CHATWOOT_API_TOKEN`。
- 把本系统的高意向会话同步到 Chatwoot contact/conversation。
- 先单向同步，不直接自动发送第三方平台消息。

参考：Chatwoot 是开源自托管客服平台，适合管理多渠道客户对话。

### 2. Tiledesk

用途：聊天机器人流程、低代码客服流程、自动化节点。

适配方式：

- 把本系统生成的客服脚本转成 Tiledesk bot 流程草稿。
- 先导出 JSON/Markdown，后续再接 Tiledesk API。

参考：Tiledesk 有 MIT 许可的 chatbot/server/design studio 相关项目。

### 3. LibreChat RAG API

用途：文件知识库、文档切分、向量检索。

适配方式：

- 当前 `knowledge_base` 先继续存结构化话术。
- 后续新增 `documents` 和 `document_chunks`。
- 接 LibreChat/RAG API 或自建 FastAPI + pgvector 检索服务。

### 4. Dify

用途：复杂工作流、知识库检索、AI 应用编排。

适配方式：

- 把“生成回复草稿”和“生成客服脚本”变成 Dify workflow 的 HTTP 调用。
- 注意 Dify 是带附加条件的开源许可证，商用 SaaS 前要确认许可证边界。

## 当前已经具备的适配点

- `GET /api/channels`
- `PUT /api/channels/{channel}`
- `GET /api/knowledge`
- `POST /api/knowledge/import`
- `POST /api/reply/draft`
- `POST /api/service-scripts/generate`

## 下一步建议

优先做 Chatwoot 单向同步适配器：

1. 商家配置 Chatwoot 地址和 Token。
2. 本系统会话标记“需人工接管”时，同步到 Chatwoot。
3. Chatwoot 里由真人坐席处理。
4. 等微信、抖音、淘宝、拼多多官方 API 权限齐了，再做自动发送。
