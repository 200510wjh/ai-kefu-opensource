# 阶段七 Connector 授权与只读接入报告

生成时间：2026-07-16

## 一、阶段目标

本阶段目标是把平台接入从“静态注册表”推进到“可保存授权状态、可接收只读消息/线索、可进入 CRM 和 Workflow”。

本阶段明确不做自动发送：

- 不自动发微信消息。
- 不自动发抖音私信。
- 不自动发淘宝/拼多多/闲鱼消息。
- 不自动发布商品、改价、退款或发货。

## 二、本阶段完成内容

### 1. Connector 授权模型

修改文件：

- `backend/customer_service_saas.py`

新增模型：

- `ConnectorAuthUpdate`
- `ConnectorAuthView`
- `ConnectorInboundMessageRequest`
- `ConnectorInboundLeadRequest`
- `ConnectorIngestResponse`
- `ConnectorEvent`

新增 Connector 目录：

- 官网客服
- 开放 API
- 微信
- 企业微信客服
- 抖音企业号/小店
- 抖音私信
- 淘宝/千牛
- 拼多多
- 闲鱼

每个 Connector 显示：

- 授权方式
- 状态
- 只读/草稿/需确认安全等级
- 能力列表
- 所需字段
- 已配置字段
- 缺失字段

### 2. 新增数据表

新增表：

- `connector_credentials`
- `connector_events`

凭证处理原则：

- 当前不返回任何明文密钥。
- 前端/接口提交的 secret 字段只记录“已配置字段名”。
- 真实自动调用平台 API 之前，需要再接入加密存储或环境变量密钥管理。

### 3. 新增 `/api/v1/connectors/*` 接口

新增接口：

- `GET /api/v1/connectors/auth`
- `PUT /api/v1/connectors/{connector}/auth`
- `GET /api/v1/connectors/events`
- `POST /api/v1/connectors/{connector}/messages/read`
- `POST /api/v1/connectors/{connector}/leads/read`

### 4. 只读消息/线索进入 CRM 和 Workflow

只读消息入站会：

- 创建/更新 CRM 客户线索。
- 写入会话表。
- 计算意向分和风险标记。
- 触发 `message_high_intent_handoff` Workflow。
- 高意向或风险消息自动创建 CRM 跟进任务。
- 写入 `connector_events`。

只读线索入站会：

- 创建 CRM 线索。
- 触发 `lead_intake_next_step` Workflow。
- 写入 `connector_events`。

### 5. 前端系统设置页接入

修改文件：

- `src/main.tsx`

系统设置页现在展示：

- Connector 注册表
- 平台授权和只读入站状态
- 每个平台缺失字段
- 安全等级
- 能力边界

## 三、安全边界

本阶段仍然只读。

即便接口提交 `send_enabled=true`，后端也会强制保持 `send_enabled=false`。自动发送必须等后续阶段完成：

- 官方权限确认
- 回调验签
- 消息幂等
- 人工确认策略
- 审计日志
- 平台风控边界

## 四、验证结果

已执行并通过：

- `python -m py_compile backend\main.py backend\api_v1.py backend\customer_service_saas.py backend\platform\connectors.py backend\platform\workflow.py backend\platform\security.py`
- `GET /api/v1/connectors/auth` TestClient 冒烟
- `PUT /api/v1/connectors/{connector}/auth` TestClient 冒烟
- `POST /api/v1/connectors/{connector}/messages/read` TestClient 冒烟
- `POST /api/v1/connectors/{connector}/leads/read` TestClient 冒烟
- `GET /api/v1/connectors/events` TestClient 冒烟
- `npm run build`
- `npm run secret-scan`

## 五、仍未完成项

后续阶段继续做：

- Webhook 签名校验（已在阶段十七补齐）。
- OAuth 授权跳转和回调（已在阶段十八补齐）。
- OAuth token exchange worker（已在阶段十九补齐）。
- OAuth refresh token worker（已在阶段二十四补齐）。
- 加密密钥存储（已在阶段十七补齐）。
- 官方平台 API 只读拉取 worker（已在阶段二十补齐）。
- Connector 事件幂等去重（已在阶段十六补齐）。
- 平台消息草稿和人工确认队列（已在阶段十五补齐）。
- 自动发送的审计、撤回和风控策略（阶段二十一已补齐外发前准备、撤回和审计框架；阶段二十二已补齐人工确认后的受控 API 发送 worker；无人值守自动发送仍未开启）。

## 六、是否可以进入第八阶段

可以进入第八阶段：团队成员、角色、权限和审计日志。

第八阶段建议目标：

- 建立企业成员表。
- 建立角色和权限表。
- 所有写操作进入审计日志。
- 区分老板、运营负责人、客服主管、客服坐席。
- 前端根据权限隐藏或禁用高风险操作。
