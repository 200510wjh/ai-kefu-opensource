# 阶段十六：Connector 事件幂等与重复回调保护报告

生成时间：2026-07-16 20:56:00

## 本阶段目标

补齐 Connector 只读入站后的重复事件保护，避免平台重试、重复 webhook 或人工重复提交导致重复客户、重复任务、重复回复草稿。

## 已完成内容

- 新增 Connector 事件查重函数：`find_connector_event`。
- 新增回复草稿按 external_id 查重函数：`find_reply_draft_by_external`。
- 消息入站幂等：
  - 同一商家、同一 Connector、同一 `external_id` 的 message 事件再次进入时直接返回已存在结果。
  - 不重复创建客户。
  - 不重复创建 CRM 跟进任务。
  - 不重复创建回复草稿。
- 线索入站幂等：
  - 同一商家、同一 Connector、同一 `external_id` 的 lead 事件再次进入时直接忽略。
  - 不重复创建 CRM 线索。
- 交付包验收矩阵新增“Connector 事件幂等”。
- 最终验收巡检新增“Connector 事件幂等”。

## 安全边界

- 幂等依赖平台侧提供稳定的 `external_id`。
- 如果平台没有稳定事件 ID，需要在接入层用平台消息 ID、发送人 ID、时间窗口和文本摘要组合生成业务幂等键。
- 幂等保护只阻止重复入站，不代表已经开启平台自动发送。

## 验收方式

1. 调用 `POST /api/v1/connectors/{connector}/messages/read` 提交一条带 `external_id` 的消息。
2. 再次用同一个 `external_id` 提交。
3. 确认第二次返回“重复消息事件已按 external_id 幂等忽略”。
4. 查询 `GET /api/v1/reply-drafts?status=pending`，确认没有重复草稿。
5. 对线索入站重复执行同样检查。
