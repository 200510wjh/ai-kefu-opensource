# 阶段三十一：平台接入 SLA 升级简报报告

## 目标

第 30 阶段已经有平台接入 SLA 看板。本阶段继续补齐可执行升级材料：运营负责人可以一键生成 Markdown 简报，把逾期、今日到期、未排期的平台接入任务转给客户平台管理员或技术负责人推进。

## 已完成能力

1. 新增后端模型：
   - `IntegrationSLAEscalationRequest`
   - `IntegrationSLAEscalation`

2. 新增后端接口：
   - `POST /api/v1/ops/integration-sla-escalation`
   - 默认纳入逾期、今日到期、未排期任务。
   - 可通过 `include_upcoming=true` 纳入未来到期任务。

3. 新增 Markdown artifact：
   - 生成目录：`/artifacts/integration/`
   - 内容包括 SLA 总览、需要升级的任务、推进建议和安全边界。

4. 前端系统设置页接入：
   - “平台接入配置向导”面板新增“升级简报”按钮。
   - 生成后自动打开 Markdown 简报。
   - 页面展示最近简报任务数和状态。

5. 交付与验收接入：
   - 客户交付包自动包含 `平台接入SLA升级简报.md`。
   - 验收矩阵新增 `Platform integration SLA escalation`。
   - 最终验收巡检新增“平台接入 SLA 升级简报”。

## 安全边界

- 简报不包含真实密钥、token 或客户隐私内容。
- 简报不调用平台 API。
- 简报不发送消息、不发布商品、不改价、不退款、不发货。

## 验证清单

1. Python 编译通过。
2. 前端 `npm run build` 通过。
3. TestClient 能生成 SLA 升级简报 artifact。
4. 交付包包含 SLA 升级简报。
5. 最终验收巡检包含 SLA escalation 证据。
6. secret scan 通过后部署。
