# 阶段十八：OAuth 授权跳转与回调框架报告

生成时间：2026-07-16 21:28:00

## 本阶段目标

补齐抖音、淘宝、拼多多等官方平台接入前必须具备的 OAuth 授权跳转与回调基础设施。系统可以生成授权链接、保存 state、接收回调 code，并以密文形式保存 code；阶段十九已继续补齐 token exchange worker。

## 已完成内容

- 新增 OAuth 状态表：`connector_oauth_states`。
- 新增后端模型：
  - `ConnectorOAuthStartRequest`
  - `ConnectorOAuthStartResponse`
  - `ConnectorOAuthCallbackResponse`
- 新增 v1 API：
  - `POST /api/v1/connectors/{connector}/oauth/start`
  - `GET /api/v1/connectors/{connector}/oauth/callback`
  - `POST /api/v1/connectors/{connector}/oauth/callback`
- OAuth start 会生成：
  - HMAC state
  - 15 分钟过期时间
  - auth_url
  - callback_url
- OAuth callback 会：
  - 校验 state
  - 防止 state 重复使用
  - 校验过期时间
  - 接收 code
  - 将 code 以密文保存为 `oauth_code`
  - 将 Connector 状态置为 `pending_auth`
  - 写入审计日志
- 前端 Connector 设置卡片新增：
  - OAuth 授权地址
  - Client ID
  - scope
  - 生成 OAuth 链接按钮
- 最终验收巡检新增“OAuth 授权跳转和回调”。
- 交付包验收矩阵新增“OAuth 授权回调框架”。

## 安全边界

- 本阶段不伪造官方 access_token。
- 本阶段只保存 OAuth code；token exchange worker 已在阶段十九补齐。
- OAuth code 加密保存，不在前端回显。
- state 只能使用一次，且默认 15 分钟过期。

## 验收方式

1. 配置目标 Connector 的 `authorize_url`、`client_id`、`redirect_uri` 和 `scope`。
2. 调用 `POST /api/v1/connectors/{connector}/oauth/start`。
3. 确认返回 auth_url 和 state。
4. 调用 OAuth callback 并传入 `state` 和 `code`。
5. 确认 Connector `configured_fields` 出现 `oauth_code`。
6. 检查数据库 `config_json` 不包含明文 code。
