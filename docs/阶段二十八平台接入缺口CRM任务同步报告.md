# 阶段二十八：平台接入缺口 CRM 任务同步报告

## 目标

第 27 阶段已经能运行平台接入干跑验收。本阶段把干跑验收中的 `fail` 和 `warning` 项转成 CRM 跟进任务，让平台授权、endpoint、Webhook 验签、受控发送等缺口进入运营执行队列。

## 已完成能力

1. 新增后端同步模型：
   - `IntegrationTaskSyncRequest`
   - `IntegrationTaskSyncResult`

2. 新增后端接口：
   - `POST /api/v1/ops/integration-task-sync`
   - 默认同步 fail 和 warning。
   - 可通过 `include_warnings=false` 只同步 fail。
   - 可设置负责人和到期天数。

3. 同步规则：
   - `pass` 不生成任务。
   - `fail` 生成高优先级任务。
   - `warning` 生成普通优先级任务。
   - 使用稳定 target id：`integration:<connector>:<check>`。
   - 已存在 open 任务时跳过，避免重复刷任务。

4. 前端系统设置页接入：
   - “平台接入配置向导”面板新增“同步任务”按钮。
   - 同步后展示新增任务数、已存在任务数和干跑状态。
   - 同步后刷新 CRM 任务列表。

5. 验收接入：
   - 验收矩阵新增 `Platform integration task sync`。
   - 最终验收巡检新增“平台接入缺口 CRM 任务同步”。

## 安全边界

- 同步任务不会调用真实平台 API。
- 同步任务不会发送消息、发布商品、改价、退款或发货。
- CRM 任务只记录字段名、检查项和下一步，不包含真实 token 或密钥值。

## 验证清单

1. Python 编译通过。
2. 前端 `npm run build` 通过。
3. TestClient 第一次同步能创建任务。
4. TestClient 第二次同步能跳过已存在 open 任务。
5. 最终验收巡检包含 task sync 证据。
6. secret scan 通过后部署。
