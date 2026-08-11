# 已配置到 Codex 本地插件市场

这次不是只放在 `.codex/skills` 里，而是已经配置成 Codex 本地插件市场里的插件。

## 插件名称

```text
merchant-growth-saas
```

## 所属本地市场

```text
merchant-codex-plugins
```

## 插件实际位置

```text
C:\Users\Administrator\Documents\运营\codex-plugins-marketplace\plugins\merchant-growth-saas
```

## 市场清单位置

```text
C:\Users\Administrator\Documents\运营\codex-plugins-marketplace\.agents\plugins\marketplace.json
```

## Codex 启用配置

已经写入：

```text
C:\Users\Administrator\.codex\config.toml
```

配置项：

```toml
[plugins."merchant-growth-saas@merchant-codex-plugins"]
enabled = true
```

## 怎么使用

重启 Codex，或者新开一个 Codex 线程后，可以直接说：

```text
用商家 AI 增长中台插件，帮我接入商家需求
```

也可以说：

```text
用 merchant-growth-saas-skill 检查 AI客服、出图、出视频和抖音小程序订阅
```

## 注意

当前这个对话启动时插件还没有启用，所以本线程不一定能立刻看到新插件。

重启 Codex 或新开线程后，Codex 会重新读取本地插件市场和配置。

