# AI 客服 SaaS 验收矩阵

这份矩阵把原始目标拆成可验收项。不要用“看起来能用”代替验收命令。

## 验收命令

```powershell
npm run acceptance:check
```

证明系统基础能力：SaaS、知识库、网页客服、四个平台回复接口、历史上下文、回复链路演练、构建和脚本编译。

```powershell
npm run acceptance:reply-e2e
```

证明核心客服引擎：示例聊天 + 本地知识库 + 微信/抖音/淘宝/拼多多渠道 + AI 回复 + 禁用承诺检查。

```powershell
npm run acceptance:real-platforms
```

证明真实桌面读取：必须先打开微信、抖音、千牛、拼多多真实客服聊天窗口。没有真实窗口时不能算完成。

## 目标对照

| 目标 | 当前实现 | 验收证据 |
| --- | --- | --- |
| 自动化读取消息 | 桌面监听器支持 UIA/OCR 读取指定窗口；默认不靠剪贴板兜底 | `npm run acceptance:real-platforms`，状态必须是 `ok` |
| 加上之前的内容 | 本地历史写入 `data/desktop-listener/history.jsonl`，下一轮自动带入同平台上下文 | `npm run acceptance:check` 的 `desktop_history_context` |
| 自动回复 | API 回复引擎返回 `should_reply` 和推荐回复，启动器可自动粘贴 | `platform_reply_api`、`reply_e2e`、真实窗口通过后启动器粘贴 |
| 导入知识库 | SaaS 后台可导入 FAQ/商品/政策；桌面端可读取本地知识库文件 | `saas_core_flow`、`reply_e2e` |
| 页面不是单页演示 | 后台包含商家大脑、客服脚本、渠道接入、知识库、收件箱、桌面客服、网页气泡 | 前端构建 + 页面源码 + 线上后台 |
| 微信/抖音/淘宝/拼多多渠道 | 回复接口和桌面窗口识别都覆盖四个平台 | `platform_reply_api`、`launcher_platform_guess`、`acceptance:real-platforms` |
| 不乱发送 | 默认只粘贴，不按 Enter；自动发送必须确认短语 | 监听器参数校验和使用说明 |
| 不把窗口壳当聊天 | 过滤 `CefView`、窗口按钮、内部路径等壳文字 | `chat_text_filter`、`not_chat_like`、真实平台验收状态 |
| 客服回复不傻不乱承诺 | 回复链路检查禁用“保证准时/无条件退款/私下收款”等承诺 | `acceptance:reply-e2e` |
| 如何使用说明 | 使用说明、桌面助手说明、验收矩阵三份文档 | `docs_exist` |

## 状态解释

- `ok`：该项通过。
- `missing_window`：没有打开对应平台真实客服窗口。
- `clipboard_fallback_only`：剪贴板里有文本，但窗口本身没读到聊天，不算自动读取。
- `read_failed`：找到窗口，但 UIA/OCR 都没读到可用聊天内容。
- `not_chat_like`：读到的是窗口壳文字，系统会跳过，不调用 AI。

## 最终完成条件

以下三类都通过，才算完成原目标：

1. `npm run acceptance:check` 通过。
2. `npm run acceptance:reply-e2e` 通过。
3. 打开微信、抖音、千牛、拼多多真实聊天页后，`npm run acceptance:real-platforms` 严格通过。

