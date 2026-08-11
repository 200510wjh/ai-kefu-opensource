# 通用 AI 客服 SaaS

本版本把主产品收敛为通用 AI 客服，不再把图片、视频、插件市场放在主流程。

## 线上入口

- 后台：`https://wjhai.cn/merchant-admin/`
- 测试商户：`ai_kefu_demo`
- 测试密码：`admin123`
- 测试商户码：`WJAIKF001`

## 核心接口

```text
POST /api/auth/login
GET  /api/merchant/profile
PUT  /api/merchant/profile
GET  /api/dashboard/overview
POST /api/widget/session
POST /api/widget/message
GET  /api/conversations
GET  /api/conversations/{session_id}
POST /api/conversations/{session_id}/handoff
GET  /api/widget.js?merchant_code=WJAIKF001
GET  /api/widget-test?merchant_code=WJAIKF001
```

## 数据存储

服务器使用现有 MySQL：

```text
Database: ai_saas
Tables: merchants, customers, conversations, chat_logs
```

本地开发默认使用 SQLite：

```text
data/customer_service.sqlite3
```

## 嵌入代码

客户网站放入：

```html
<script src="https://wjhai.cn/merchant-admin/api/widget.js?merchant_code=WJAIKF001"></script>
```

## 验收标准

- 商户能登录后台。
- 商户资料能保存。
- 测试页右下角能出现客服气泡。
- 访客发消息后，AI 自动回复。
- 后台会话收件箱能看到消息和回复。
- 会话写入 MySQL，服务重启后不丢。

## 当前边界

- 全自动回复只发生在自有网页客服气泡。
- 不模拟微信/抖音私信发送。
- 知识库第一版来自商家资料表单和 FAQ，不做 PDF/RAG。
- 图片和视频模块已从主流程移除，后续作为独立模块再做。
