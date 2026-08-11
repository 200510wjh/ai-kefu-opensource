# 阶段三十二：平台接入 SLA 责任人通知草稿报告

## 目标

把 Stage31 的 SLA 升级项转成可复制、可交付、可审计的责任人通知草稿，帮助运营继续推进平台授权、回调地址、endpoint 和签名材料补齐。

## 已完成

1. 后端新增通知草稿模型
   - `IntegrationSLANoticeRequest`
   - `IntegrationSLANotice`

2. 后端新增接口
   - `POST /api/v1/ops/integration-sla-notice`
   - 权限：`settings:write`
   - 输出：通知主题、可复制草稿、涉及 SLA 任务、Markdown artifact。

3. 前端新增设置页入口
   - 在“平台接入配置向导”增加“通知草稿”按钮。
   - 生成后可打开 Markdown，也可复制通知正文。

4. 交付包和验收纳入
   - 交付包新增 `平台接入SLA责任人通知草稿.md`。
   - 验收矩阵新增 `Platform integration SLA notice draft`。
   - 最终验收巡检新增“平台接入 SLA 责任人通知草稿”。

## 安全边界

- 该阶段只生成人工确认草稿，不自动发送企业微信、钉钉、邮件或平台消息。
- 草稿不包含真实 token、密钥、验证码或客户隐私数据。
- 外发前必须由运营确认接收人、措辞、附件和发送渠道。

## 验证清单

1. `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`
2. `npm run build`
3. `npm run secret-scan`
4. TestClient 调用 `/api/v1/ops/integration-sla-notice` 能生成 artifact。
5. 交付包包含通知草稿。
6. 最终验收审计包含 `notice_items=` 证据。
