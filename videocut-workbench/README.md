# VideoCut Workbench

这是基于 `Ceeon/videocut-skills` 做的前端工作台原型。

打开：

```text
videocut-workbench/index.html
```

它负责把口播剪辑需求整理成标准任务：

```text
原始口播视频
-> 剪口播任务
-> 口误/静音审核
-> source_cut.mp4 + subtitles.srt
-> 口播成片任务
-> 分镜/预览/竖屏 MP4
```

当前版本是前端任务台，不直接在浏览器里剪视频。实际剪辑仍由 Codex skill、Node 脚本、FFmpeg、审核页完成。

## 适合卖的包装

- 299 元：口播粗剪，去口误、静音、重复。
- 499 元：口播粗剪 + 竖屏成片。
- 999 元：商品口播成片包，含商品上架文案、口播脚本、成片。
- 2999 元/月：商家短视频剪辑自动化工作台。

