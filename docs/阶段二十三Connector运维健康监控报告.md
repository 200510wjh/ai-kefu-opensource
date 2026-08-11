# 阶段二十三：Connector 运维健康监控报告

生成时间：2026-07-16

## 本阶段目标

补齐 Connector 接入后的运维监控能力，让运营负责人能看到授权、访问凭证、只读 API endpoint、受控发送闸门、失败事件和外发队列状态，避免平台接入后静默失败。

## 已完成内容

- 新增后端模型：
  - `ConnectorHealthItem`
  - `ConnectorHealthOverview`
- 新增 v1 API：
  - `GET /api/v1/ops/connector-health`
- 健康聚合覆盖：
  - Connector 授权状态
  - OAuth token 是否存在
  - OAuth token 是否已过期或 7 天内到期
  - 只读 `messages_url` / `leads_url` 是否配置
  - 受控发送闸门是否与 `send_url`、访问凭证一致
  - 最近 Connector auth/API 失败次数
  - 待外发 outbox 数
  - 发送失败 outbox 数
- 前端系统设置页新增：
  - Connector 运维健康总览
  - 全局告警摘要
  - 每个 Connector 的健康状态、待处理数、失败数、token 到期时间和下一步动作
- 最终验收巡检新增“Connector 运维健康监控”。
- 交付包验收矩阵新增“Connector 运维健康监控”。

## 安全边界

- 健康面板只展示字段名、状态和计数，不展示 access token、session key、client secret 或 webhook key。
- 健康面板不会触发任何平台发送。
- 对外发和发送失败的提示只用于人工处理和审计，不代表无人值守自动发送已经开启。

## 验收方式

1. 登录后台并调用 `GET /api/v1/ops/connector-health`。
2. 确认每个 Connector 都返回健康状态。
3. 配置或缺失 OAuth token、read endpoint、send endpoint 时，健康面板能给出对应告警。
4. 创建外发准备记录或发送失败记录后，健康面板能反映待处理/失败数量。
5. 运行最终验收巡检，确认出现“Connector 运维健康监控”项目。

