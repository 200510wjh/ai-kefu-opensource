# 阶段三十六：真实平台验收缺口 CRM 任务同步报告

## 目标

把 Stage35 证据包里的缺失真实平台验收场景，自动转成 CRM 跟进任务，避免“知道缺口但没人推进”。

## 已完成

1. 后端新增同步模型
   - `PlatformAcceptanceGapSyncRequest`
   - `PlatformAcceptanceGapSyncResult`

2. 后端新增接口
   - `POST /api/v1/ops/platform-acceptance-gap-sync`
   - 权限：`settings:write`
   - 输出：缺失场景、新增任务数、已存在任务数、CRM 任务列表、Markdown artifact。

3. 缺口任务去重
   - 任务来源：`platform_acceptance_gap`
   - 任务 ID：`platform_acceptance:{scenario}`
   - 若同一场景已有 open 任务，不重复创建。

4. 交付包和验收纳入
   - 交付包新增 `真实平台验收缺口CRM任务清单.md`。
   - 验收矩阵新增 `Platform acceptance gap CRM sync`。
   - 最终验收巡检新增“真实平台验收缺口 CRM 任务”。

5. 前端设置页接入
   - 新增“缺口任务”按钮。
   - 展示缺口场景、新增任务、已存在任务和清单 artifact。

## 安全边界

- 本阶段只创建 CRM 跟进任务，不伪造真实平台证据。
- 任务里不写入平台密码、token、cookie、验证码或密钥。
- 真实完成仍需客户账号、官方授权、真实消息/线索和脱敏证据证明。

## 验证清单

1. `python -m py_compile backend/customer_service_saas.py backend/api_v1.py backend/main.py`
2. `npm run build`
3. `npm run secret-scan`
4. TestClient 能把缺失场景同步为 CRM 任务。
5. 第二次同步不会重复创建任务。
6. 交付包包含 `真实平台验收缺口CRM任务清单.md`。
7. 最终验收审计包含 `gap_sync_events=` 证据。
