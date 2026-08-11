# 阶段十七：Webhook 签名校验与密钥加密存储报告

生成时间：2026-07-16 21:12:00

## 本阶段目标

补齐 Connector 真实接入前必须具备的安全入口：公开 webhook 不再依赖后台 Bearer token，而是使用商家编码和 HMAC SHA256 签名校验；Connector 密钥不再只记录“已配置”，而是以密文形式保存。

## 已完成内容

- 新增 Connector 密钥密文封装：
  - `encrypt_connector_secret`
  - `decrypt_connector_secret`
  - `connector_secret_value`
- Connector 授权保存时，`secret_fields` 会加密写入 `config_json.secret_fields_encrypted`。
- Connector 列表仍只暴露 `configured_fields`，不会回显明文密钥。
- 新增公开 webhook 入口：
  - `POST /api/v1/webhooks/{connector}/messages`
  - `POST /api/v1/webhooks/{connector}/leads`
- 新增 HMAC SHA256 签名校验：
  - 支持 `X-Webhook-Signature`
  - 支持 `X-Signature`
  - 支持 `X-Hub-Signature-256`
  - 支持 `sha256=<hex>` 形式
  - 支持 `X-Webhook-Timestamp` 或 `X-Timestamp`
- 前端 Connector 设置卡片新增：
  - 公开 webhook 地址展示
  - Webhook 签名密钥录入
  - 加密保存按钮
- 最终验收巡检新增“Webhook 签名校验和密钥存储”。
- 客户交付包验收矩阵新增“Webhook 签名校验”。

## 签名规则

不带时间戳时：

```text
hex = HMAC_SHA256(secret, raw_body)
```

带时间戳时：

```text
hex = HMAC_SHA256(secret, timestamp + "." + raw_body)
```

时间戳有效窗口为 10 分钟。

## 安全边界

- 密钥不在前端回显。
- 数据库只保存密文和 MAC。
- 公开 webhook 必须配置签名密钥后才可通过校验。
- 本阶段仍不开放平台自动发送，只做签名保护后的只读入站。

## 验收方式

1. 登录后台，在系统设置中为目标 Connector 保存 Webhook 签名密钥。
2. 用相同密钥对原始 JSON body 计算 HMAC SHA256。
3. 调用 `POST /api/v1/webhooks/{connector}/messages?merchant_code=...`。
4. 签名正确时返回 200，并进入 CRM/Workflow/草稿队列。
5. 签名错误时返回 401。
6. 检查数据库 `config_json` 中不存在明文密钥。
