# Mac 恢复上下文

这份文件是给未来 Mac 上的 Codex 看的。用户换电脑后，不需要自己写命令；可以直接把下面这句话发给 Codex：

> 帮我从 GitHub 恢复我的运营项目。仓库是 `https://github.com/200510wjh/ai-kefu-opensource.git`，请先读取仓库里的 `MAC_RESTORE_CONTEXT.md` 和 `docs/WINDOWS_TO_MAC_MIGRATION_AUDIT_2026-08-11.md`，然后把项目恢复到 Mac 的工作目录。

## 仓库信息

- GitHub 账号：`200510wjh`
- 仓库：`ai-kefu-opensource`
- 备份分支：`codex-windows-mac-migration-backup-20260811`
- 本机原路径：`C:\Users\Administrator\Documents\运营`
- 建议 Mac 目标路径：`~/Documents/运营` 或 `~/Projects/运营`

## 恢复目标

在 Mac 上恢复这个 Windows 工作区的主要项目文件，包括源码、文档、脚本、配置模板、前端、后端、小程序、插件市场、交付资料和运营计划。

主要已备份目录：

- `backend/`
- `codex-plugins-marketplace/`
- `desktop/`
- `desktop_agent/`
- `docs/`
- `douyin-miniapp/`
- `enterprise-material-factory/`
- `product-kit/`
- `scripts/`
- `src/`
- `tests/`
- `videocut-workbench/`
- `work/`
- `峰会内容/`
- `运营计划/`

## 不在普通 GitHub 仓库里的内容

下面这些是刻意排除的，不是遗漏。它们通常太大、可重新生成，或可能包含本地数据：

- `node_modules/`
- `.venv/`、`.pytest_cache/`、`__pycache__/`
- `.codex-video-output/`、`.codex-video-tools/`
- `tmp/`、`output/`、`outputs/`、`release/`
- `data/`、`external/`、`videos/`
- `*.mp4`、`*.mp3`、`*.wav`、`*.exe`、`*.zip`、`*.tar.gz`
- `.env`、日志、本地扫描结果、本地 WeChat 证据输出

如果用户说“要把视频、数据库、安装包也完整搬过去”，不要强行塞进普通 GitHub。建议单独做移动硬盘、网盘、GitHub Release、Git LFS 或分卷压缩备份。

## Mac 上恢复后要做的事

1. 克隆仓库并切到备份分支。
2. 安装 Node 依赖。
3. 建 Python 虚拟环境并安装 `requirements.txt`。
4. 从 `.env.example` 创建本地 `.env`，让用户重新填真实 API Key 和平台 token。
5. 运行项目自检或开发服务。

参考命令由 Codex 代跑即可，用户不需要手写。

## 重要提醒

- 不要把真实密钥、账号 cookie、平台 token、客户私密数据提交到 GitHub。
- 如果 Mac 上路径不同，优先用新路径替换旧的 `C:\Users\Administrator\Documents\运营`。
- 如果用户只想“先把文件拿回来”，先完成 clone 和依赖安装；运行、部署、打包可以后做。
- 更详细的备份覆盖和置换建议在 `docs/WINDOWS_TO_MAC_MIGRATION_AUDIT_2026-08-11.md`。
