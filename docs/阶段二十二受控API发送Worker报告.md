# 阶段二十二：受控 API 发送 Worker 报告

生成时间：2026-07-16

## 本阶段目标

在阶段二十一已经建立外发准备队列、撤回和审计的基础上，补齐人工确认后的受控 API 发送框架。系统只有在官方 `send_url`、访问凭证和发送闸门都已配置，并且操作人再次确认后，才会向平台发送接口发起请求。

## 已完成内容

- 新增后端模型：
  - `ConnectorSendGateUpdate`
  - `ConnectorSendGateResponse`
  - `ReplyDispatchSendRequest`
- 新增 v1 API：
  - `POST /api/v1/connectors/{connector}/send-gate`
  - `POST /api/v1/reply-dispatches/{dispatch_id}/send`
- 新增受控发送闸门：
  - 开启必须提交确认短语 `ENABLE_SUPERVISED_SEND`
  - 必须配置 `send_url`
  - 必须已有 `access_token` 或 `session_key`
  - 默认频控为每 Connector 每小时 20 条，可配置
- 新增确认发送 worker：
  - 发送必须提交确认短语 `CONFIRM_PLATFORM_SEND`
  - 只从已审批 outbox 快照发送
  - 已撤回记录不能发送
  - 已发送记录不会重复发送
  - 退款、投诉、付款、账号、隐私、合同等风险标记会阻断 API 发送
  - 支持 idempotency key
  - 支持 dry-run 审计
  - 平台响应只保存非敏感 metadata
  - 成功后状态为 `sent`
  - 失败后状态为 `send_failed`
- 前端新增：
  - 设置页 `发送 API` 输入
  - “启用受控发送”按钮
  - outbox “确认 API 发送”按钮
- 最终验收巡检新增“受控 API 发送 worker”。
- 交付包验收矩阵新增“受控 API 发送 worker”。

## 安全边界

- 本阶段仍不开放无人值守自动发送。
- 每条 API 发送都必须由人点击确认，并由后端校验确认短语。
- 高风险草稿不会走 API 发送，只能人工处理。
- 缺少 send endpoint、访问凭证或闸门未开启时，不会伪造发送成功。
- 本阶段不涉及自动发布商品、改价、退款或发货。

## 验收方式

1. 为 Connector 配置 `send_url` 和访问凭证。
2. 调用 `POST /api/v1/connectors/{connector}/send-gate` 并传入 `ENABLE_SUPERVISED_SEND`。
3. 创建回复草稿、审批并进入外发准备队列。
4. 调用 `POST /api/v1/reply-dispatches/{dispatch_id}/send` 并传入 `CONFIRM_PLATFORM_SEND`。
5. 确认低风险回复会 POST 到官方 send endpoint，并更新为 `sent`。
6. 确认高风险回复会更新为 `blocked`，不会调用发送接口。
7. 确认重复发送不会重复调用平台接口。

