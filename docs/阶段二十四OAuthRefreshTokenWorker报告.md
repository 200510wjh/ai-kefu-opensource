# 阶段二十四：OAuth Refresh Token Worker 报告

生成时间：2026-07-16

## 本阶段目标

补齐 OAuth 访问凭证续期能力，避免真实平台接入后 `access_token` 或 `session_key` 到期导致只读拉取、受控发送和运维监控静默失效。

## 已完成内容

- 新增后端模型：
  - `ConnectorOAuthRefreshRequest`
  - `ConnectorOAuthRefreshResponse`
- 新增 v1 API：
  - `POST /api/v1/connectors/{connector}/oauth/refresh`
- 新增 refresh token worker：
  - 读取 `token_url` / `oauth_token_url`
  - 读取 `client_id` / `client_key` / `app_key`
  - 读取密文保存的 `client_secret` / `app_secret`
  - 读取密文保存的 `refresh_token`
  - 以 `grant_type=refresh_token` 调用官方 token endpoint
  - 支持 `refresh_token_param`、`refresh_grant_type`、`refresh_extra_params`
  - 成功后密文更新 `access_token`
  - 如平台返回新的 `refresh_token`，同步密文替换
  - 如平台返回 `session_key`，同步密文保存
  - 更新 `oauth_token_refreshed_at`、`oauth_token_expires_at`、响应字段名和非敏感 metadata
  - 写入 Connector 事件、用量记录和审计日志
- 前端系统设置页新增：
  - “刷新 Token”按钮
- Connector 运维健康监控增强：
  - 已有访问凭证但缺少 `refresh_token` 时给出告警
  - token 过期或 7 天内到期时继续给出告警
- 最终验收巡检新增“OAuth refresh token worker”。
- 交付包验收矩阵新增“OAuth refresh token worker”。

## 安全边界

- 不伪造官方 refresh 成功。
- 不在前端、审计摘要或健康面板中回显 access token、refresh token、session key 或 client secret。
- 缺少 `refresh_token`、`token_url` 或 client credential 时返回 `setup_required`。
- 官方 refresh 响应未包含访问凭证时返回 `failed`，不会覆盖原有凭证。

## 验收方式

1. 完成 OAuth token exchange 并保存 `refresh_token`。
2. 调用 `POST /api/v1/connectors/{connector}/oauth/refresh`。
3. 确认响应为 `refreshed`。
4. 确认 `configured_fields` 包含 `access_token` 和 `refresh_token`。
5. 检查数据库 `config_json` 不包含任何明文 token。
6. 检查健康面板能识别 token 到期和缺少 refresh token 的状态。

