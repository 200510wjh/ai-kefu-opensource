# AI客服和生成 API 怎么接

## AI客服是不是要接 API

正式卖给客户时，要接。

现在系统里可以先用规则和模板跑通流程，但要做到“不傻的回复”，最终要接大模型 API。

## 推荐接法

后端统一用 OpenAI-compatible 方式。

也就是说，不管你用官方 OpenAI、API2D、其他中转，都走类似配置：

```text
AI_BASE_URL
AI_API_KEY
AI_MODEL
```

## 官方 API 怎么接

配置：

```text
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的官方Key
AI_MODEL=gpt-4.1-mini 或其他可用模型
```

优点：

- 稳定
- 质量好
- 适合正式 SaaS

缺点：

- 成本要算清楚
- 国内服务器访问可能需要网络条件

## API2D 怎么接

如果 API2D 支持 OpenAI-compatible 接口，就配置：

```text
AI_BASE_URL=https://oa.api2d.net/v1
AI_API_KEY=你的API2D Key
AI_MODEL=你要用的模型
```

注意：

- 具体 base URL 和模型名要以 API2D 后台文档为准。
- 不要把真实 Key 写进 GitHub。
- Key 放服务器环境变量，不放前端。

## AI客服接口应该做什么

不是只返回一段回复。

必须返回：

- 客户阶段
- 意向分
- 冷/暖/热线索
- 缺失信息
- 风险提示
- 下一步动作
- 候选回复
- 是否建议人工接管
- 线索保存建议

## 客户需求 API

所有外部入口都接这里：

```text
POST /api/intake/customer-need
```

来源包括：

- 抖音小程序表单
- 抖音企业号线索
- 网页表单
- 企业微信
- 人工录入
- 客户发来的商品链接

这个 API 负责把需求变成：

```text
线索 + 项目 + brief + 脚本 + AI客服分析
```
# 2026-06-26 API2D 接入记录

AI 客服可以接 API2D 这种 GPT 中转站，只要它兼容 OpenAI `/v1/chat/completions`。

当前服务器已配置：

```text
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://oa.api2d.net
AI_MODEL=gpt-4o-mini
```

真实 Key 没有写进仓库，放在服务器 systemd drop-in：

```text
/etc/systemd/system/merchant-growth-canvas.service.d/30-ai-provider.conf
```

线上验证：

```text
GET  https://wjhai.cn/merchant-admin/api/providers
POST https://wjhai.cn/merchant-admin/api/customer-service/chat-reply-agent
```

验证结果：

- `/api/providers` 返回 `configured=true`、`mode=ai`。
- `/api/customer-service/chat-reply-agent` 能返回 AI 生成的候选回复。
- `safety_note` 会显示：AI 已接入，但仍只生成候选回复。

注意：

- Key 不要写进前端。
- Key 不要提交 GitHub。
- 客服自动发送仍然需要人工确认或官方 API 权限。
- API2D 只解决“回复更聪明”，不解决“读取微信/抖音消息”和“官方自动发送”权限。

