# 桌面客服辅助脚本使用说明

这个版本先不做网页客服，主线改成桌面辅助脚本，支持微信、抖音、淘宝/千牛、拼多多。

## 能做什么

- 读取你复制的聊天记录，生成一条“不傻、不油、不乱承诺”的客服回复。
- 把回复复制到剪贴板。
- 可选：自动粘贴到当前聊天输入框。
- 可选：在你明确确认后，粘贴后按 Enter 发送。

## 不能直接做什么

- 不是输入一个微信/抖音/淘宝链接就能后台监听。
- 没有官方 API 权限时，不能稳定地在后台读取所有私信。
- 不建议无人值守自动群发、自动改价、自动退款、自动提交付款或隐私信息。

真正稳定的后台接入，需要各平台官方接口或商家后台授权。桌面脚本第一版适合你自己盯着客服窗口，用来提速。

## 自动监听：不用复制聊天内容

推荐先用自动准备器。双击项目根目录：

```text
自动准备客服平台.bat
```

它会自动查找微信、企业微信、抖音、千牛、拼多多客户端或快捷方式；找不到窗口时会尝试启动已安装的平台，并生成报告：

```text
data/desktop-listener/platform-prepare-report.md
```

准备器不会发送消息，只负责帮你把平台窗口准备好。平台打开后，需要你进入真实客服聊天页。

然后用图形化验收器。双击项目根目录：

```text
验收真实平台.bat
```

它会用中文解释每个平台的状态。全部通过后，再用图形化启动器。双击项目根目录：

```text
启动AI自动客服.bat
```

启动器会做这些事：

- 列出当前打开的窗口。
- 对微信、抖音、千牛、拼多多窗口打标。
- 让你选择平台、读取方式和知识库文件。
- 点“开始自动监听”后持续读取消息、生成回复、粘贴候选回复。
- 默认不按 Enter 发送。

脚本目录里也有同样的入口：

```text
scripts/start_desktop_auto_listener.bat
```

使用顺序：

1. 打开微信、抖音、千牛或拼多多客服窗口，停留在聊天页。
2. 双击启动器。
3. 点“刷新窗口”。
4. 选中真实客服窗口。
5. 点“开始自动监听”。

商家知识库先改这个文件：

```text
docs/examples/merchant_knowledge.example.txt
```

启动配置在这里：

```text
scripts/desktop_listener.config.example.json
```

命令版：

```powershell
npm run desktop:launcher
```

旧版配置命令：

```powershell
npm run desktop:auto
```

绑定指定窗口，不跟着前台变化：

```powershell
npm run desktop:listen -- --platform wechat --target-title "微信|WeChat|企业微信" --source auto --paste
```

淘宝/千牛：

```powershell
npm run desktop:listen -- --platform taobao --target-title "千牛|淘宝|旺旺|Qianniu" --source auto --paste
```

默认行为：

- 自动读当前客服窗口，不需要你复制聊天记录。
- 读取顺序是：UI Automation 控件文字 -> OCR 截图识别 -> 剪贴板兜底。
- 自动把本地知识库一起交给 AI。
- 自动生成回复。
- 自动粘贴候选回复到当前输入框。
- 不会自动按 Enter 发送。
- 粘贴后会冷却一段时间，避免把自己粘贴的候选回复当成新客户消息继续生成。
- 默认不会用剪贴板兜底；只有启动器里勾选“允许剪贴板兜底”或命令加 `--allow-clipboard-fallback` 才会启用。
- 会把最近几轮本地历史写入 `data/desktop-listener/history.jsonl`，下一轮回复会自动带上同平台历史上下文。
- 如果 Windows 没让目标客服窗口切到前台，系统会只复制回复到剪贴板，不会粘贴或发送到错误窗口。

真要自动发送，需要显式确认：

```powershell
npm run desktop:listen -- --platform auto --source uia --paste --send --confirm-send "我确认发送"
```

如果某个平台窗口读不到文字，说明客户端控件不开放给 Windows UI Automation。当前脚本已经有 OCR 截图兜底，但本机必须安装 Tesseract OCR 程序，并且最好带中文语言包 `chi_sim`。

自动准备平台的命令行方式：

```powershell
npm run desktop:prepare -- --launch
```

OCR 环境变量：

```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:DESKTOP_OCR_LANG="chi_sim+eng"
```

配置里已经会把最新窗口截图保存到：

```text
data/desktop-listener/latest-window.png
```

如果 OCR 没装，脚本会明确提示 `Tesseract OCR executable not found`，不会假装已经识别。

一键安装 OCR：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_desktop_ocr.ps1
```

诊断当前窗口读取情况：

```powershell
npm run desktop:diagnose
```

诊断结果会告诉你：

- 当前前台窗口标题
- 是否识别成微信/抖音/淘宝/拼多多
- UIA 读到了什么
- OCR 读到了什么
- 剪贴板兜底读到了什么
- 截图保存到了哪里

## 真实平台验收

普通验收：

```powershell
npm run acceptance:check
```

核心回复链路演练：

```powershell
npm run acceptance:reply-e2e
```

它不需要打开真实窗口，只验证示例聊天、知识库和四个平台回复接口都能跑通。

真实平台验收：

```powershell
npm run acceptance:real-platforms
```

运行前必须先打开这些窗口：

- 微信或企业微信客服聊天窗口。
- 抖音私信或巨量线索窗口。
- 千牛、淘宝或旺旺客服窗口。
- 拼多多商家客服窗口。

结果含义：

- `ok`：找到了窗口，并且自动读取模式能读到内容。
- `missing_window`：当前机器没打开对应平台窗口。
- `clipboard_fallback_only`：找到了窗口，但 UIA/OCR 没读到足够聊天内容，只用了剪贴板兜底；这不算真正自动读取。
- `read_failed`：找到了窗口，但 UIA/OCR/剪贴板都没读到可用内容，需要先跑 `npm run desktop:diagnose` 看原因。
- `not_chat_like`：监听器读到的是窗口标题、按钮、内部路径等壳文字，会自动跳过，不会调用 AI 或粘贴回复。

只验收微信：

```powershell
npm run acceptance:real-platforms -- --platforms wechat
```

兜底命令：

```powershell
npm run desktop:listen -- --platform auto --source clipboard --paste --knowledge-file docs/examples/merchant_knowledge.example.txt
```

## 单次回复：兜底测试方式

先打开微信、抖音私信、千牛或拼多多客服窗口，复制一段聊天记录。

微信：

```powershell
npm run desktop:reply -- --platform wechat
```

抖音：

```powershell
npm run desktop:reply -- --platform douyin
```

淘宝/千牛：

```powershell
npm run desktop:reply -- --platform taobao
```

拼多多：

```powershell
npm run desktop:reply -- --platform pdd
```

脚本会打印推荐回复，并复制到剪贴板。你确认没问题后，自己按 Ctrl+V 粘贴发送。

## 自动粘贴到输入框

运行命令后，马上点到目标聊天输入框，脚本默认等 3 秒再粘贴。

```powershell
npm run desktop:reply -- --platform wechat --paste
```

这只粘贴，不会发送。

## 明确确认后自动发送

只有你传确认短语，脚本才会按 Enter。

```powershell
npm run desktop:reply -- --platform wechat --paste --send --confirm-send "我确认发送"
```

淘宝/千牛和拼多多同理，把 `wechat` 换成 `taobao` 或 `pdd`。

## 监听模式

剪贴板监听最稳：你每复制一段新聊天，它就生成回复。

```powershell
npm run desktop:listen -- --platform wechat --source clipboard
```

自动粘贴：

```powershell
npm run desktop:listen -- --platform taobao --source clipboard --paste
```

尝试读取当前窗口控件文字：

```powershell
npm run desktop:listen -- --platform pdd --source uia --paste
```

`uia` 模式依赖 Windows 控件可读性，不同客户端可能不稳定。如果读取不到，就用 `clipboard` 模式。

## 商家知识怎么传

临时测试可以直接把商家信息放到命令里：

```powershell
npm run desktop:reply -- --platform wechat --merchant-profile "鲜花店，主卖同城鲜花配送，99元起，2小时内可送，不能承诺一定准点，只能承诺尽力安排。"
```

后续要做成长期使用，就把商家知识库整理成文件或数据库，再让脚本启动时读取。

## 四个平台的定位

- `wechat`：微信、企业微信私域客服。
- `douyin`：抖音私信、线索咨询。
- `taobao`：淘宝、千牛、旺旺客服。
- `pdd`：拼多多商家客服。

## 推荐工作流

1. 先用 `desktop:reply` 单次测试，确认回复质量。
2. 再用 `--paste`，确认粘贴位置稳定。
3. 最后才考虑 `--send`，并保留人工盯屏。
4. 真要卖给客户，优先卖“辅助回复 + 知识库 + 人工确认”，不要一开始承诺全自动无人值守。
