# 阶段六十六：旧 Manifest 提交恢复复核包报告

## 目标

把阶段六十五中只能进入人工复核的旧版 Manifest 提交，升级为可恢复、可预览、可追踪的复核包。

旧提交没有结构化 `import_items`，但多数保留了导入预览 artifact。阶段六十六从本地 artifact 安全解析 `ready` 行，恢复为导入预览 payload，并继续禁止直接导入真实 pass 证据。

## 已完成

- 后端 Manifest import queue 新增 `recovered_for_review` 状态。
- 队列项新增 `source` 和 `recovered` 字段，区分 `metadata`、`artifact`、`manual` 来源。
- 队列汇总新增 `recovered` 计数和 `recovered` 队列状态。
- 新增 artifact 路径约束，只允许读取 `data/artifacts` 下的本地 Markdown/TXT 报告。
- 新增旧导入预览表解析：只恢复 `ready` 状态且带 http(s) 证据链接的必需验收场景。
- 前端 Import queue 面板展示 recovered 计数和 item 来源。
- 前端恢复项只允许 `Preview import`，`Import evidence` 继续要求 `ready_to_import`。

## 本地验证

- `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`：通过
- `npm run build`：通过
- `npm run secret-scan`：通过，未发现明显密钥
- `VITE_BASE_PATH=/merchant-admin/ npm run build`：通过
- TestClient 旧提交恢复冒烟：通过

冒烟结果：

```json
{
  "queue_status": "recovered",
  "recovered": 1,
  "item_status": "recovered_for_review",
  "source": "artifact",
  "preview_ready": 1,
  "preview_imported": 0
}
```

## 安全边界

- 队列恢复不会注册 pass evidence。
- `recovered_for_review` 只能进入预览导入，不能直接执行证据导入。
- 最终导入仍必须由 `ready_to_import` 的结构化 Manifest 项触发，并输入 `CONFIRM_PLATFORM_EVIDENCE`。
- URL 安全预检仍阻断 localhost、内网、placeholder、非 HTTPS 和不安全跳转。
- 阶段六十六不改变当前真实平台验收结论；客户仍需提交真实、脱敏、可复核的平台证据。

## 生产部署记录

- 状态：已部署
- 生产 URL：https://wjhai.cn/merchant-admin/
- 远端备份：`/opt/backups/merchant-growth-canvas-pre-20260717-084608.tar.gz`
- 前端资产：`/merchant-admin/assets/index-BxFRRSfd.js`
- 服务健康：`/api/v1/health` 返回 `ok`

生产队列冒烟：

```json
{
  "queue_status": "recovered",
  "queue_total": 1,
  "queue_ready": 0,
  "queue_recovered": 1,
  "queue_needs_customer": 0,
  "queue_needs_manual_review": 0,
  "queue_item_statuses": ["recovered_for_review"],
  "queue_item_sources": ["artifact"],
  "queue_item_import_items": [1]
}
```

生产恢复预览冒烟：

```json
{
  "preview_status": "preview",
  "preview_ready": 1,
  "preview_imported": 0,
  "preview_evidence_registered": 0
}
```

验收报告对比：

```json
{
  "before_status": "partial",
  "before_evidence_total": 2,
  "before_missing": ["official_auth", "read_message", "read_lead", "customer_trial"],
  "after_status": "partial",
  "after_evidence_total": 2,
  "after_missing": ["official_auth", "read_message", "read_lead", "customer_trial"],
  "unchanged": {
    "status": true,
    "evidence_total": true,
    "missing": true
  }
}
```

结论：阶段六十六完成。旧 Manifest 提交已经从人工不可执行状态恢复为可预览复核包，但真实平台验收仍未完成，仍缺 `official_auth`、`read_message`、`read_lead`、`customer_trial` 四类客户真实证据。
