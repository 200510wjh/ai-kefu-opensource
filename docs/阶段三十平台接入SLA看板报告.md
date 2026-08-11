# 阶段三十：平台接入 SLA 看板报告

## 目标

第 28、29 阶段已经把平台接入缺口变成 CRM 任务，并能复验关闭已通过项。本阶段补齐运营 SLA 看板，让负责人能看到接入任务的逾期、今日到期、未排期、负责人和平台分布。

## 已完成能力

1. 新增后端 SLA 模型：
   - `IntegrationTaskSLAItem`
   - `IntegrationTaskSLABoard`

2. 新增后端接口：
   - `GET /api/v1/ops/integration-task-sla`
   - 只读取 `source=integration_dry_run` 的 open CRM 任务。
   - 按 `due_at` 计算 `overdue`、`due_today`、`upcoming`、`unscheduled`。
   - 输出按 Connector 和 owner 的统计。

3. 前端系统设置页接入：
   - “平台接入配置向导”面板显示 SLA 数量。
   - 展示前 5 条需要优先看的接入任务。

4. 验收接入：
   - 验收矩阵新增 `Platform integration SLA board`。
   - 最终验收巡检新增“平台接入 SLA 看板”。

## 安全边界

- SLA 看板只读取 CRM 任务，不调用真实平台 API。
- 不发送消息、不发布商品、不改价、不退款、不发货。
- 不包含真实密钥、token 或客户隐私内容。

## 验证清单

1. Python 编译通过。
2. 前端 `npm run build` 通过。
3. TestClient 能读取 SLA 看板。
4. 最终验收巡检包含 SLA board 证据。
5. secret scan 通过后部署。
