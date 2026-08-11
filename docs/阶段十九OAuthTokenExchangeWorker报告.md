# 阶段十九：OAuth Token Exchange Worker 报告

生成时间：2026-07-16

## 本阶段目标

在阶段十八已经完成 OAuth 授权跳转、state 校验和回调 code 密文保存的基础上，补齐后端 token exchange worker。系统只有在配置了真实 `token_url`、client id、client credential，并收到官方回调 code 后，才会向官方 token endpoint 发起换取访问凭证请求。

## 已完成内容

- 新增后端模型：
  - `ConnectorOAuthExchangeRequest`
  - `ConnectorOAuthExchangeResponse`
- 新增 v1 API：
  - `POST /api/v1/connectors/{connector}/oauth/exchange`
- 新增通用 token exchange worker：
  - 读取 `token_url` / `oauth_token_url`
  - 读取 `client_id` / `client_key` / `app_key`
  - 读取密文保存的 `client_secret` / `app_secret`
  - 读取密文保存的 `oauth_code`
  - 以 `application/x-www-form-urlencoded` POST 到官方 token endpoint
  - 支持按 Connector 配置覆盖参数名，如 `client_id_param`、`client_secret_param`、`code_param`
  - 支持 `token_extra_params` / `oauth_token_extra_params`
- token 响应处理：
  - 成功时密文保存 `access_token`
  - 如有返回，密文保存 `refresh_token`
  - 如有返回，密文保存 `session_key`
  - 成功后移除一次性 `oauth_code`
  - 保存 `oauth_token_exchanged_at`、`oauth_token_expires_at`、响应字段名和非敏感 metadata
  - Connector 状态更新为 `connected`
  - 写入审计日志、Connector 事件和用量记录
- 前端系统设置页新增：
  - OAuth Client Secret 输入
  - Token Endpoint 输入
  - “换取 Token”按钮
- 最终验收巡检新增“OAuth token exchange worker”。
- 交付包验收矩阵新增“OAuth token exchange worker”。

## 安全边界

- 不伪造官方 `access_token`。
- 不在前端回显 `client_secret`、`access_token`、`refresh_token`、`session_key` 或 `oauth_code`。
- token endpoint 缺失、回调 code 缺失或官方响应未包含访问凭证时，只返回 `setup_required` 或 `failed`，不会把 Connector 标为成功。
- 自动发送仍未开启；本阶段只为后续官方只读 API worker 准备访问凭证。

## 验收方式

1. 配置 OAuth Connector 的授权参数和 token endpoint。
2. 生成 OAuth 授权链接。
3. 完成 callback，让 Connector 出现 `oauth_code` 字段。
4. 调用 `POST /api/v1/connectors/{connector}/oauth/exchange`。
5. 确认成功后 Connector 出现 `access_token` 或 `session_key` 字段。
6. 检查数据库 `config_json` 不包含明文 code、client credential 或 token。

