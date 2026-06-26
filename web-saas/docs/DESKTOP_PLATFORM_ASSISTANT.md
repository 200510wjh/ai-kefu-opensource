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

推荐先用这个。双击：

```text
scripts/start_desktop_auto_listener.bat
```

然后打开微信、抖音、千牛或拼多多客服窗口，停留在聊天页。脚本会自动识别当前窗口平台，并尝试读取窗口里的聊天内容。

命令版：

```powershell
npm run desktop:auto
```

默认行为：

- 自动读当前客服窗口，不需要你复制聊天记录。
- 自动生成回复。
- 自动粘贴候选回复到当前输入框。
- 不会自动按 Enter 发送。

真要自动发送，需要显式确认：

```powershell
npm run desktop:listen -- --platform auto --source uia --paste --send --confirm-send "我确认发送"
```

如果某个平台窗口读不到文字，说明客户端控件不开放给 Windows UI Automation。这个时候只能换官方 API、OCR 截图识别，或者临时退回剪贴板模式。

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
