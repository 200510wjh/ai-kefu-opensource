# 先看这个：AI 客服系统怎么用

这套系统分两层：

- SaaS 后台：管理商家资料、知识库、网页客服、会话收件箱。
- 桌面助手：读取微信、抖音、千牛、拼多多客服窗口，生成并粘贴回复。

## 1. 打开后台

线上后台：

```text
https://wjhai.cn/merchant-admin/
```

后台不是单页演示，包含：

- 商家大脑
- 客服脚本
- 渠道接入
- 知识库导入
- 会话收件箱
- 桌面自动客服
- 网页气泡

## 2. 先导入知识库

后台导入：

1. 打开“知识库导入”。
2. 填商家介绍、商品服务、价格、优惠、售后政策。
3. 上传 txt/md/csv/json 文档。
4. 保存后刷新，确认知识条目还在。

桌面助手本地知识库：

```text
docs/examples/merchant_knowledge.example.txt
```

## 3. 先验收，再自动监听

第一步，双击：

```text
验收真实平台.bat
```

它会告诉你：

- `ok`：真实聊天内容读到了。
- `missing_window`：平台窗口没打开。
- `clipboard_fallback_only`：只是剪贴板兜底，不算自动读取。
- `read_failed`：窗口找到了，但 UIA/OCR 没读到聊天。
- `not_chat_like`：读到的是窗口壳文字，不会触发 AI。

第二步，全部通过后双击：

```text
启动AI自动客服.bat
```

使用顺序：

1. 打开真实客服聊天页。
2. 点“刷新窗口”。
3. 选中对应聊天窗口。
4. 默认只自动粘贴，不自动发送。
5. 确认回复没问题后，再考虑自动发送。

## 4. 三个验收命令

基础验收：

```powershell
npm run acceptance:check
```

核心回复链路：

```powershell
npm run acceptance:reply-e2e
```

真实平台窗口：

```powershell
npm run acceptance:real-platforms
```

## 5. 最终完成条件

必须同时满足：

1. `npm run acceptance:check` 通过。
2. `npm run acceptance:reply-e2e` 通过。
3. 打开微信、抖音、千牛、拼多多真实聊天页后，`npm run acceptance:real-platforms` 严格通过。

完整矩阵见：

```text
docs/ACCEPTANCE_MATRIX.md
```

