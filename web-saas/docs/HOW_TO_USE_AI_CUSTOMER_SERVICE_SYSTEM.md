# AI 客服 SaaS 使用说明

## 1. 后台入口

线上后台：

```text
https://wjhai.cn/merchant-admin/
```

默认测试账号以实际服务器数据库为准。本地开发通常是：

```text
admin / admin123
```

后台不是单页演示，当前分成这些板块：

- 商家大脑：看会话、自动回复、线索、知识库数量。
- 客服脚本：生成开场、跟进、异议处理、收口话术。
- 渠道接入：网页客服、微信、抖音、淘宝/千牛、拼多多。
- 知识库导入：导入 FAQ、价格、售后、商品资料。
- 会话收件箱：查看真实会话和 AI 回复。
- 桌面自动客服：微信/抖音/千牛/拼多多桌面助手说明和命令。
- 网页气泡：生成网站接入代码。

## 2. 先导入知识库

后台方式：

1. 登录后台。
2. 打开“知识库导入”。
3. 填商家资料、产品、价格、优惠、售后政策。
4. 上传 txt/md/csv/json 文档。
5. 点导入，刷新后能看到知识条目。

桌面助手本地文件方式：

```text
docs/examples/merchant_knowledge.example.txt
```

把客户的 FAQ、价格、售后、禁用承诺写进去。

## 3. 网页客服怎么用

打开“网页气泡”，复制 script 代码放到客户网站。

测试页：

```text
https://wjhai.cn/merchant-admin/api/widget-test?merchant_code=WJDEMO001
```

访客发消息后，后台“会话收件箱”能看到记录。

## 4. 微信/抖音/淘宝/拼多多桌面自动客服

先自动准备平台，不要直接猜有没有窗口。双击项目根目录里的：

```text
自动准备客服平台.bat
```

它会自动查找微信、抖音、千牛、拼多多客户端或快捷方式，能启动就尝试启动，并生成中文报告：

```text
data/desktop-listener/platform-prepare-report.md
```

准备完成后，进入真实客服聊天页，再验收真实平台。双击项目根目录里的：

```text
验收真实平台.bat
```

它会用中文告诉你：

- 哪个平台没打开。
- 哪个平台只读到窗口壳文字。
- 哪个平台只是剪贴板兜底。
- 哪个平台真的从窗口读到了聊天内容。

验收通过后，再双击：

```text
启动AI自动客服.bat
```

打开后按这个顺序操作：

1. 先打开微信、抖音、千牛或拼多多客服窗口。
2. 回到“AI 自动客服监听器”，点“刷新窗口”。
3. 在列表里选中真实客服聊天窗口。
4. 平台会自动识别；没识别时手动选微信/抖音/淘宝/拼多多。
5. 选择知识库文件，默认是 `docs/examples/merchant_knowledge.example.txt`。
6. 默认勾选“生成后自动粘贴到输入框”，不会自动发送。
7. 点“开始自动监听”。

前期不要急着勾“自动按 Enter 发送”。先确认粘贴出来的话术像真人、没有乱承诺，再开启自动发送。

如果窗口文字读不到，先安装 OCR：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_desktop_ocr.ps1
```

另一个启动入口：

```text
双击 scripts/start_desktop_auto_listener.bat
```

开发/排查时也可以命令打开同一个启动器：

```powershell
npm run desktop:launcher
```

旧版配置命令：

```powershell
npm run desktop:auto
```

如果你不想让脚本跟着前台窗口变化，可以锁定窗口标题：

```powershell
npm run desktop:listen -- --platform wechat --target-title "微信|WeChat|企业微信" --source auto --paste
```

千牛示例：

```powershell
npm run desktop:listen -- --platform taobao --target-title "千牛|淘宝|旺旺|Qianniu" --source auto --paste
```

使用方式：

1. 打开平台客服窗口。
2. 用启动器锁定这个窗口。
3. 读取顺序：UIA 控件文字 -> OCR 截图 -> 剪贴板兜底。
4. 生成回复后默认粘贴到输入框。
5. 默认不按 Enter，需要人工确认。
6. 粘贴后会进入最小间隔冷却，避免把自己刚粘贴的候选回复再次读进去循环生成。

桌面助手会保存最近几轮本地历史到：

```text
data/desktop-listener/history.jsonl
```

下一次生成回复时，会把同一平台的最近历史一起带给 AI，用来避免重复问、接住上一轮上下文。默认最多读取 8 条，可在启动配置里改 `history_limit`。

真正自动发送：

```powershell
npm run desktop:listen -- --platform auto --source auto --paste --send --confirm-send "我确认发送"
```

## 5. 诊断怎么跑

如果不知道为什么读不到窗口，先双击：

```text
scripts/start_desktop_diagnostics.bat
```

或者命令：

```powershell
npm run desktop:diagnose
```

诊断指定窗口：

```powershell
npm run desktop:diagnose -- --platform wechat --target-title "微信|WeChat|企业微信"
```

诊断会输出：

- 当前前台窗口标题。
- 是否识别成微信/抖音/淘宝/拼多多。
- UIA 读到的内容。
- OCR 读到的内容。
- 剪贴板内容。
- 截图文件路径。

截图默认保存到：

```text
data/desktop-listener/diagnostics-window.png
```

## 6. 验收标准

- 后台能打开，登录后不是单页，而是多个 SaaS 板块。
- 知识库能导入，刷新后仍能看到。
- 网页客服能创建会话、自动回复、落库。
- 桌面助手打开后，能识别微信/抖音/千牛/拼多多窗口。
- 启动器不会把普通浏览器窗口误标成客服窗口。
- `npm run desktop:diagnose` 能显示 UIA/OCR/剪贴板读取结果。
- `npm run desktop:prepare` 能自动发现/尝试启动已安装客服平台，并生成中文巡检报告。
- `npm run desktop:auto` 能生成回复并粘贴。
- 默认不自动发送，防止误发；确认后才允许按 Enter。

一键验收命令：

```powershell
npm run acceptance:check
```

它会检查：

- 文档和配置文件是否存在。
- Python 后端和桌面脚本是否能编译。
- 前端 SaaS 是否能构建。
- 线上 `/api/health` 是否正常。
- 微信、抖音、淘宝、拼多多四个平台回复接口是否都能返回。
- 桌面诊断脚本是否能读取当前窗口、OCR、剪贴板状态。
- 桌面历史是否会进入下一轮回复提示词。

核心回复链路演练：

```powershell
npm run acceptance:reply-e2e
```

它不替代真实平台窗口验收，只证明“示例聊天 + 本地知识库 + 四个平台渠道 + AI 回复 + 禁用承诺检查”这条链路是通的。

桌面真实平台验收仍要打开对应窗口。这个命令会逐个平台检查可见窗口和读取结果：

```powershell
npm run acceptance:real-platforms
```

如果没有打开某个平台，会看到：

```text
missing_window
```

这不是代码坏了，而是说明当前机器没有可验收的真实平台窗口。打开微信、抖音、千牛、拼多多客服聊天窗口后再跑。

如果看到：

```text
clipboard_fallback_only
```

说明找到了窗口，但没有真正从窗口文字或 OCR 里读到聊天内容，只用了剪贴板兜底。这种情况不能算“打开窗口就能回”，需要把窗口切到真实聊天页，或安装/调整 OCR。

如果自动监听器打印：

```text
not_chat_like
```

说明它读到的是窗口标题、按钮、内部路径等壳文字，不像客户聊天内容。系统会跳过，不会调用 AI，也不会粘贴回复；把平台切到真实聊天页后再试。

默认自动监听不会再用剪贴板兜底。只有你在启动器里勾选“允许剪贴板兜底”，或命令里显式加：

```powershell
--allow-clipboard-fallback
```

它才会在窗口读取失败时使用剪贴板。这个模式只适合排查，不算真正“打开窗口自动读取消息”。

只验收其中一个平台：

```powershell
npm run acceptance:real-platforms -- --platforms wechat
```

验收通过后，再打开启动器做最后一步端到端测试：

```text
启动AI自动客服.bat
```

## 7. 当前边界

- 没有官方 API 权限时，微信/抖音/淘宝/拼多多不能保证后台无人值守读取所有私信。
- 桌面助手依赖当前前台窗口，适合人工盯屏提效。
- 如果某个平台 UIA 读不到，就依赖 OCR；OCR 需要 Tesseract 和中文语言包。
- 如果平台更新 UI，可能要重新调窗口识别或 OCR 截图范围。
