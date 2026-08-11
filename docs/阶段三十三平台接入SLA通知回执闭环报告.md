# 阶段三十三：平台接入 SLA 通知回执闭环报告

## 目标

在 Stage32 通知草稿之后，补齐“责任人是否收到、哪些任务已确认、是否关闭 CRM 接入任务”的运营闭环。

## 已完成

1. 后端新增回执模型
   - `IntegrationSLANoticeReceiptRequest`
   - `IntegrationSLANoticeReceipt`

2. 后端新增接口
   - `POST /api/v1/ops/integration-sla-notice-receipt`
   - 权限：`settings:write`
   - 输出：回执状态、确认任务 ID、忽略任务 ID、已关闭 CRM 任务、剩余打开任务、Markdown artifact。

3. CRM 闭环保护
   - 默认只记录回执，不关闭任务。
   - 关闭任务必须同时满足：
     - `close_confirmed_tasks=true`
     - `confirm_phrase=CONFIRM_CLOSE`
     - 任务仍为 open
     - 任务来源为 `integration_dry_run`
   - 关闭动作复用 CRM task 更新能力并写入审计日志。

4. 前端设置页接入
   - 通知草稿生成后可点击“记录回执”。
   - 需要关闭通知涉及任务时，点击“确认关闭”并经过浏览器确认。
   - 回执结果展示已关闭数量、剩余打开数量和回执 artifact。

5. 交付包和验收纳入
   - 交付包新增 `平台接入SLA通知回执模板.md`。
   - 验收矩阵新增 `Platform integration SLA receipt loop`。
   - 最终验收巡检新增“平台接入 SLA 通知回执闭环”。

## 安全边界

- 回执接口不发送平台消息。
- 不自动关闭全部任务；关闭必须由调用方显式传任务 ID 和确认短语。
- 不记录真实 token、密钥、验证码或客户隐私。
- 外发通知、回执确认、任务关闭仍属于人工确认流程。

## 验证清单

1. `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`
2. `npm run build`
3. `npm run secret-scan`
4. TestClient 能记录回执 artifact。
5. TestClient 能用临时 integration task 验证 `CONFIRM_CLOSE` 关闭路径。
6. 交付包包含 SLA 升级简报、通知草稿、回执模板。
7. 最终验收审计包含 `receipt_items=` 证据。
