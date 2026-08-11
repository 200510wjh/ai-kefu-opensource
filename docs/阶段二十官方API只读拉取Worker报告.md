# 阶段二十：官方 API 只读拉取 Worker 报告

生成时间：2026-07-16

## 本阶段目标

在 OAuth token exchange worker 已经能密文保存访问凭证后，补齐官方平台 API 只读拉取能力。系统可以用 `access_token` 或 `session_key` 拉取平台消息/线索，并把结果接入既有 CRM、Workflow、Connector 幂等和回复草稿人工确认队列。

## 已完成内容

- 新增后端模型：
  - `ConnectorReadPullRequest`
  - `ConnectorReadPullResponse`
- 新增 v1 API：
  - `POST /api/v1/connectors/{connector}/api/pull`
- 新增只读 API worker：
  - 支持 `messages` 和 `leads` 两种资源
  - 支持 `messages_url` / `read_messages_url` / `message_api_url`
  - 支持 `leads_url` / `read_leads_url` / `lead_api_url`
  - 默认用 `Authorization: Bearer <access_token>` 发起 GET
  - 当凭证是 `session_key` 时默认使用 query 参数
  - 支持 `read_api_auth_mode`、`read_api_auth_header`、`read_api_token_param` 覆盖认证方式
  - 支持 `extra_params` 和 `limit`
- 数据入站复用原有链路：
  - 消息进入 `ingest_connector_message`
  - 线索进入 `ingest_connector_lead`
  - 继续复用 external_id 幂等
  - 继续触发 CRM、Workflow、跟进任务和回复草稿队列
- 前端系统设置页新增：
  - 消息只读 API endpoint 输入
  - 线索只读 API endpoint 输入
  - “拉取消息”按钮
  - “拉取线索”按钮
- 最终验收巡检新增“官方 API 只读拉取 worker”。
- 交付包验收矩阵新增“官方 API 只读拉取 worker”。

## 安全边界

- 本阶段只读拉取，不自动发送平台消息。
- 不自动发布商品、改价、退款或发货。
- 访问凭证不进入日志、审计摘要或前端响应。
- 缺少 endpoint 或访问凭证时返回 `setup_required`，不会伪造平台数据。
- 官方 API 返回异常时返回 `failed`，不会写入 CRM。

## 验收方式

1. 配置目标 Connector 的 `messages_url` 或 `leads_url`。
2. 确认 Connector 已通过阶段十九保存 `access_token` 或 `session_key`。
3. 调用 `POST /api/v1/connectors/{connector}/api/pull`。
4. 确认返回 `pulled`，并包含 `imported`、`duplicates`、`skipped` 计数。
5. 确认消息或线索进入 CRM/Workflow。
6. 重复拉取同一 external_id，确认不会重复创建客户、任务或草稿。

