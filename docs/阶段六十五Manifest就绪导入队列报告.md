# 阶段六十五：Manifest 就绪导入队列

## 目标

阶段六十四让客户可以上传脱敏证据并提交 Manifest。阶段六十五把“客户提交后运营还要手工拼导入 JSON”的环节收口成队列：系统从 Manifest 提交审计中读取结构化 import items，生成可预览、可人工确认导入的队列。

## 新增能力

- 后端新增 `POST /api/v1/ops/platform-acceptance-manifest-import-queue`。
- 新的 Manifest 提交审计元数据保存结构化 `import_items`，用于后续导入队列。
- 队列兼容旧 Manifest 提交记录：旧记录没有结构化 import items 时标记为 `needs_manual_review`。
- 前端新增 `Import queue` 按钮。
- 队列 item 支持直接运行 `Preview import`，也支持在人工确认后运行 `Import evidence`。

## 安全边界

- 队列只准备导入 payload，不自动登记通过证据。
- `Import evidence` 仍要求人工输入 `CONFIRM_PLATFORM_EVIDENCE`。
- 导入仍会跑 URL 预检和密钥文本检查。
- 旧记录没有结构化 import items 时，只能打开报告人工复核。

## 验证记录

- `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py` 通过。
- `VITE_BASE_PATH=/merchant-admin/ npm run build` 通过，生成 `dist/assets/index-CBOaApgG.js`。
- `npm run secret-scan` 通过，未发现明显密钥。
- 本地 TestClient 队列与导入预览冒烟通过：Manifest 提交返回 `preview_ready`；导入队列返回 `ready=1`；队列 item 包含 2 条结构化 `import_items`；使用队列 payload 跑导入预览返回 `ready=2`。
- 生产部署备份：`/opt/backups/merchant-growth-canvas-pre-20260717-082453.tar.gz`。
- 生产健康检查通过：`/merchant-admin/api/v1/health` 返回 `ok`。
- 生产前端资产检查通过：页面引用 `index-CBOaApgG.js`。
- 生产只读冒烟通过：`include_artifact=false`，队列返回 `queue_status=needs_manual_review`、`queue_total=1`、`queue_ready=0`、`queue_needs_manual_review=1`；未创建队列报告产物。
- 生产队列中的旧 Manifest 提交没有结构化 `import_items`，因此正确标记为 `needs_manual_review`。
- 队列调用前后验收报告未变化：`status=partial`，`evidence_total=2`。
- 当前仍缺真实平台验收场景：`official_auth`、`read_message`、`read_lead`、`customer_trial`。
