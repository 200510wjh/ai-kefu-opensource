# 阶段七十：客户重提 SLA 催办任务包报告

## 目标

阶段六十九已经能持续追踪客户 Manifest 重提状态。阶段七十新增催办任务包，把 `waiting_customer`、`ready_for_review`、`needs_fix`、`stale`、`missing_link` 等 tracker 项转成可预览、可去重、可落 CRM 的运营任务。

## 已完成

- 新增 `POST /api/v1/ops/platform-acceptance-manifest-resubmission-reminder`。
- 支持 `create_tasks=false` 预览模式：只生成 artifact 和催办草稿，不创建 CRM 任务。
- 支持 `create_tasks=true` 执行模式：为客户重提项创建 CRM 任务。
- 使用 `source=platform_acceptance_manifest_resubmission` 和稳定 `target_id` 去重，重复执行复用 open 任务。
- 前端新增 `Reminder preview` 与 `Create reminder tasks` 两个操作。
- 前端新增催办任务结果面板，显示 total、created、existing、blocked，并支持打开 artifact、复制草稿、跳转任务区。

## 本地验证

- `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`：通过
- `npm run build`：通过
- `npm run secret-scan`：通过，未发现明显密钥
- `VITE_BASE_PATH=/merchant-admin/ npm run build`：通过
- TestClient 催办任务包冒烟：通过

冒烟结果：

```json
{
  "report_before_status": "blocked",
  "report_before_evidence_total": 0,
  "resubmission_status": "executed",
  "resubmission_requested": 1,
  "tracker_status": "ready_for_review",
  "tracker_total": 1,
  "tracker_item_statuses": ["ready_for_review"],
  "preview_status": "preview",
  "preview_total": 1,
  "preview_created": 0,
  "created_status": "created",
  "created_created": 1,
  "created_existing": 0,
  "repeat_status": "created",
  "repeat_created": 0,
  "repeat_existing": 1,
  "report_after_status": "blocked",
  "report_after_evidence_total": 0
}
```

## 安全边界

- 催办任务包只创建 CRM 任务和人工审核草稿，不发送客户消息。
- 不自动审批、不自动导入、不自动登记 pass evidence。
- 最终证据导入仍必须经过人工审核、URL 预检和 `CONFIRM_PLATFORM_EVIDENCE`。
- artifact 和最终汇报不暴露签名 Manifest URL 或 token。

## 生产部署记录

- 状态：已部署
- 生产 URL：https://wjhai.cn/merchant-admin/
- 远端备份：
  - `/opt/backups/merchant-growth-canvas-pre-20260717-101608.tar.gz`
  - `/opt/backups/merchant-growth-canvas-pre-20260717-102550.tar.gz`
- 前端资产：`/merchant-admin/assets/index-CkXNLDPW.js`
- 服务健康：`/api/v1/health` 返回 `ok`

线上催办任务包冒烟：

```json
{
  "health": "ok",
  "tracker": {
    "status": "waiting_customer",
    "total": 1,
    "waiting_customer": 1,
    "item_statuses": ["waiting_customer"]
  },
  "preview": {
    "status": "preview",
    "total": 1,
    "created": 0,
    "existing": 0,
    "blocked": 0
  },
  "created": {
    "status": "created",
    "total": 1,
    "created": 1,
    "existing": 0,
    "blocked": 0,
    "task_ids": [67],
    "task_target_lengths": [46],
    "artifact_url": "/artifacts/integration/platform-manifest-resubmission-reminder-20260718-025306-5b34e1.md"
  },
  "repeat": {
    "created": 0,
    "existing": 1,
    "blocked": 0
  }
}
```

线上验收报告对比：

```json
{
  "before_status": "partial",
  "before_evidence_total": 4,
  "before_missing": ["official_auth", "read_message", "read_lead", "customer_trial"],
  "after_status": "partial",
  "after_evidence_total": 4,
  "after_missing": ["official_auth", "read_message", "read_lead", "customer_trial"],
  "unchanged": {
    "status": true,
    "evidence_total": true,
    "missing": true
  }
}
```

生产问题修复：

- 首次部署后线上 MySQL 暴露 `crm_tasks.target_id` 长度限制。
- 已将 Manifest 重提催办任务 target id 改为稳定短 hash，线上任务 target id 长度为 46，低于 80 字符限制。

结论：阶段七十完成。客户重提 SLA 催办已能在生产创建 CRM 任务并去重；真实平台验收仍未完成，仍缺 `official_auth`、`read_message`、`read_lead`、`customer_trial` 四类真实证据。
