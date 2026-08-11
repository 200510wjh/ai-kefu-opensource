# Ceeon videocut-skills 前端化方案

## 当前状态

已移除之前安装的 `chengfeng-videocut-skills`，并按用户指定仓库安装：

```text
https://github.com/Ceeon/videocut-skills
```

本地源码：

```text
external/videocut-skills-ceeon
```

Codex skills 安装目录：

```text
C:\Users\Administrator\.codex\skills\ceeon-videocut-skills
```

已把 skill 名称区分为：

- `ceeon-videocut-skills:剪口播`
- `ceeon-videocut-skills:口播成片`
- `ceeon-videocut-skills:自进化`

## 前端工作台

已创建：

```text
videocut-workbench/index.html
```

这个前端把 skill 的流程变成可视化任务台：

```text
项目输入
-> 选择剪口播/口播成片
-> 填原始视频、口播稿、素材路径
-> 自动生成任务 JSON
-> 自动生成给 Codex 的执行提示词
-> 下载任务文件或复制提示词
```

## 为什么前端不能直接等于剪辑器

`videocut-skills` 的核心依赖是：

- Node.js 脚本
- FFmpeg
- 语音转写 API
- 本地文件读写
- 审核页服务
- Agent 读取和改写中间产物

这些能力不能只靠静态 HTML 在浏览器里完整完成。正确产品架构是：

```text
前端工作台
-> 后端任务 API
-> videocut skill runner
-> FFmpeg / 转写 / 审核页
-> 成片产物
```

## 下一步做成真正 SaaS

1. 后端新增 `/api/videocut/tasks`。
2. 前端上传视频到 `data/videocut/uploads`。
3. 后端生成任务目录。
4. 调用 skill 脚本生成审核页。
5. 用户在前端确认删除片段。
6. 后端调用 FFmpeg 剪辑。
7. 后端重新转写并生成字幕。
8. 前端展示预览页和下载 MP4。

## 商业包装

- 299 元：口播粗剪。
- 499 元：口播粗剪 + 竖屏成片。
- 999 元：商品上架草稿 + 商品口播视频。
- 2999 元/月：商家口播视频自动化工作台。

