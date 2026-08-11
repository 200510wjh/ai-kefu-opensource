# 阶段六 CRM 线索模型深化报告

生成时间：2026-07-16

## 一、阶段目标

本阶段目标是把线索、客户、会话和跟进任务沉淀到统一 CRM 后端，避免“会话是一套、线索是一套、自动化又是一套”。

本阶段继续保持兼容式重构：

- 旧 `/api/conversations` 继续可用。
- 旧 `/api/leads` 继续保留。
- 新 CRM 能力统一走 `/api/v1/crm/*`。

## 二、本阶段完成内容

### 1. 扩展客服 SQLite 表结构

修改文件：

- `backend/customer_service_saas.py`

新增/补充字段：

- `customers.source_channel`
- `customers.sales_stage`
- `customers.owner`
- `customers.contact`
- `customers.notes`
- `customers.next_followup_at`
- `customers.last_session_id`
- `customers.workflow_run_id`
- `conversations.source_channel`
- `conversations.risk_flags`
- `conversations.workflow_run_id`

新增表：

- `crm_tasks`

用于保存线索、客户、会话的人工跟进任务。

### 2. 新增 CRM 后端模型和函数

新增模型：

- `CRMLead`
- `CRMLeadCreate`
- `CRMLeadUpdate`
- `CRMTask`
- `CRMTaskCreate`
- `CRMTaskUpdate`
- `CRMOverview`

新增能力：

- CRM 线索列表
- 手动创建 CRM 线索
- 更新线索阶段、负责人、标签、备注
- CRM 跟进任务列表
- 创建/更新跟进任务
- CRM 概览统计

### 3. 新增 `/api/v1/crm/*` 接口

修改文件：

- `backend/api_v1.py`
- `backend/platform/security.py`

新增接口：

- `GET /api/v1/crm/overview`
- `GET /api/v1/crm/leads`
- `POST /api/v1/crm/leads`
- `PATCH /api/v1/crm/leads/{customer_id}`
- `GET /api/v1/crm/tasks`
- `POST /api/v1/crm/tasks`
- `PATCH /api/v1/crm/tasks/{task_id}`

新增权限：

- `crm:write`

当前 owner 默认拥有该权限。

### 4. 会话和 Workflow 打通

网页客服消息进入后：

- 更新或创建 CRM 客户/线索记录。
- 写入来源、销售阶段、标签、最近会话。
- 高意向或风险消息会触发 `message_high_intent_handoff` Workflow。
- 自动创建 CRM 跟进任务。

人工接管会话时：

- 标记会话需要人工跟进。
- 自动创建 CRM 跟进任务。

手动创建 CRM 线索时：

- 自动计算意向分。
- 触发 `lead_intake_next_step` Workflow。
- 高意向线索自动生成跟进任务。

### 5. 前端 CRM 最小接入

修改文件：

- `src/main.tsx`

已接入：

- CRM 概览
- CRM 线索列表
- CRM 跟进任务
- 获客中心优先展示 v1 CRM 线索

## 三、安全边界

本阶段仍不自动发送平台消息，不自动发布商品，不自动改价，不自动退款。

CRM 跟进任务只是把需要人工处理的事项显式化，真正对外动作仍由人确认。

## 四、验证结果

已执行并通过：

- `python -m py_compile backend\main.py backend\api_v1.py backend\customer_service_saas.py backend\platform\workflow.py backend\platform\security.py backend\modules\models.py`
- `/api/v1/crm/overview` TestClient 冒烟
- `/api/v1/crm/leads` TestClient 冒烟
- `POST /api/v1/crm/leads` TestClient 冒烟
- `PATCH /api/v1/crm/leads/{customer_id}` TestClient 冒烟
- `/api/v1/crm/tasks` TestClient 冒烟
- 网页客服高意向消息触发 Workflow 和 CRM 任务冒烟
- `npm run build`
- `npm run secret-scan`

## 五、仍未完成项

后续阶段继续做：

- CRM 线索详情页和编辑表单。
- 负责人、角色、团队成员数据库化。
- 跟进任务完成/延期的前端操作。
- CRM 数据分页、筛选、搜索。
- 将旧 `/api/leads` 数据迁移进 CRM 表。
- 将小程序、表单、平台 Connector 的线索统一写入 `/api/v1/crm/leads`。
- Workflow 运行日志持久化到数据库。

## 六、是否可以进入第七阶段

可以进入第七阶段：Connector 授权和平台消息接入。

建议第七阶段目标：

- 为微信、企业微信、抖音、淘宝、拼多多、闲鱼建立 Connector 凭证模型。
- 每个平台先接只读消息/线索同步，不做自动发送。
- 所有外部线索统一进入 `/api/v1/crm/leads`。
- 所有待回复消息统一进入 Workflow，再决定草稿、人工确认或忽略。
