# 阶段三十四：平台接入 SLA 闭环复盘报表报告

## 目标

把 SLA 看板、通知草稿、回执记录、CRM 任务关闭和审计日志汇总成一份可交付的闭环复盘报表，用于判断平台接入推进是否真正进入可验收状态。

## 已完成

1. 后端新增报表模型
   - `IntegrationSLALoopReportRequest`
   - `IntegrationSLALoopReport`

2. 后端新增接口
   - `POST /api/v1/ops/integration-sla-loop-report`
   - 权限：`settings:write`
   - 输出：当前打开任务、逾期、今日到期、未排期、近期回执数、近期关闭任务数、相关审计事件、Markdown artifact。

3. 审计证据汇总
   - 汇总 `integration.sla_notice_receipt`
   - 汇总 `integration.task_reconcile`
   - 汇总状态为 `done` 的 `crm.task.update`
   - 汇总 SLA 草稿、回执和复盘报表相关事件

4. 前端设置页接入
   - 增加“闭环报表”按钮。
   - 展示复盘状态、近期回执、近期关闭、审计事件数量。
   - 支持打开 Markdown 复盘报表。

5. 交付包和验收纳入
   - 交付包新增 `平台接入SLA闭环复盘报表.md`。
   - 验收矩阵新增 `Platform integration SLA loop report`。
   - 最终验收巡检新增“平台接入 SLA 闭环复盘报表”。

## 安全边界

- 本报表只汇总系统内状态和审计事件，不发送平台消息。
- 不包含真实 token、密钥、验证码或客户隐私。
- 平台侧真实完成度仍需要客户账号、官方授权和真实消息/线索场景验收。

## 验证清单

1. `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`
2. `npm run build`
3. `npm run secret-scan`
4. TestClient 能生成闭环复盘 artifact。
5. 交付包包含 SLA 升级简报、通知草稿、回执模板、闭环复盘报表。
6. 最终验收审计包含 `loop_events=` 证据。
