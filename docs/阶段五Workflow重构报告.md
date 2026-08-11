# 阶段五 Workflow 重构报告

生成时间：2026-07-16

## 一、阶段目标

本阶段目标是把自动化能力从零散脚本和运行记录，升级为统一的 Workflow 层。

Workflow 统一承接：

- 消息触发
- 线索触发
- 定时任务
- 人工触发

本阶段继续采用兼容式重构，不删除旧接口，不把高风险平台动作改成自动执行。

## 二、本阶段完成内容

### 1. 扩展 `backend/platform/workflow.py`

新增能力：

- Workflow 默认定义注册表
- Workflow 定义列表
- Workflow 事件匹配
- Workflow 条件评估
- Workflow 手动运行
- Workflow 动作执行日志
- Workflow 运行详情查询

新增默认 Workflow：

- `message_high_intent_handoff`：高意向消息转人工跟进
- `lead_intake_next_step`：新线索首轮跟进
- `daily_ops_report`：每日运营检查

当前动作保持确定性和安全边界：

- `score_intent`：关键词意向评分
- `risk_check`：风险识别
- `create_task`：创建跟进任务记录
- `notify_human`：标记需要人工确认
- `update_lead_stage`：标记线索阶段
- `generate_report`：生成摘要
- `run_local_script`：只登记需要本机确认，不绕过本机脚本安全接口

### 2. 新增 `/api/v1/workflows/*` 接口

修改文件：

- `backend/api_v1.py`

新增接口：

- `GET /api/v1/workflows/definitions`
- `GET /api/v1/workflows/runs`
- `GET /api/v1/workflows/runs/{run_id}`
- `POST /api/v1/workflows/events`
- `POST /api/v1/workflows/{workflow_id}/run`

所有接口继续使用第三阶段统一返回格式：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "uuid",
  "elapsed_ms": null
}
```

### 3. 自动化中心接入 Workflow 定义

修改文件：

- `src/main.tsx`

自动化中心现在展示：

- Workflow 定义
- 每个 Workflow 的触发类型、模块、动作数量
- 手动运行按钮
- 本机脚本列表
- Workflow 运行记录

旧本机脚本能力继续保留，并且仍然通过 `/api/local-scripts/*` 的本机访问保护执行。

## 三、安全边界

本阶段不做以下事情：

- 不让前端直接绕过本机保护启动脚本。
- 不自动发送微信、抖音、淘宝、拼多多、闲鱼消息。
- 不自动发布商品、改价、退款或发货。
- 不声明平台官方 API 已全部打通。

涉及平台写入、自动发送、发布和资金相关动作，仍必须走人工确认。

## 四、验证结果

已执行并通过：

- `python -m py_compile backend\main.py backend\api_v1.py backend\platform\workflow.py backend\platform\ai_engine.py backend\platform\api.py backend\platform\security.py`
- `/api/v1/workflows/definitions` TestClient 冒烟
- `/api/v1/workflows/events` TestClient 冒烟
- `/api/v1/workflows/{workflow_id}/run` TestClient 冒烟
- `npm run build`

验证结论：

- Workflow 定义可查询。
- 消息事件可以匹配并触发 Workflow。
- 手动运行可以生成完整运行日志。
- 前端构建通过。
- 旧 Workflow 运行记录和本机脚本入口未破坏。

## 五、仍未完成项

以下内容进入后续阶段：

- Workflow 定义持久化到数据库。
- Workflow 运行日志落库和分页查询。
- Workflow 条件、动作的企业级配置页面。
- 定时任务调度器。
- 线索、会话、知识库、商品中心的真实事件自动投递。
- 将 AI Engine 的模型评分结果替换当前关键词评分。
- 平台 Connector 授权完成后，再接入官方 API 动作。

## 六、是否可以进入第六阶段

可以进入第六阶段：CRM 和线索模型深化。

第六阶段建议目标：

- 统一 Lead / Customer / Conversation 的数据库模型。
- 增加销售阶段、标签、负责人、跟进任务。
- 把网页客服、表单、小程序、手动录入的线索统一进入 CRM。
- 将高意向消息和新线索真实投递到 Workflow。
