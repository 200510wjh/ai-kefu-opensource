# Windows 到 Mac 迁移审计

日期：2026-08-11

## 本地仓库

- 本地路径：`C:\Users\Administrator\Documents\运营`
- GitHub 远程：`https://github.com/200510wjh/ai-kefu-opensource.git`
- Mac 恢复入口：仓库根目录 `MAC_RESTORE_CONTEXT.md`
- 本地总文件体量约 4GB，包含依赖、缓存、视频、安装包、临时数据库和构建产物。
- 适合提交到 GitHub 的源码、脚本、配置模板和文档约 13MB，无单文件超过 GitHub 100MB 限制。

## 已排除内容

以下内容不适合直接进 GitHub，已在 `.gitignore` 中排除：

- `node_modules/`、`.venv/`、`__pycache__/`、`.pytest_cache/`
- `dist/`、`release/`、`tmp/`、`output/`、`outputs/`
- `.codex-video-output/`、`.codex-video-tools/`
- `*.zip`、`*.tar.gz`、`*.tgz`、`*.exe`、`*.dmg`、`*.msi`
- `*.mp4`、`*.mov`、`*.wav`、`*.mp3`
- `.env`、日志文件、客户 intake 输出、本地 WeChat/证据扫描结果

这些内容可以在新电脑上重新安装或重新生成；真实密钥和本地私有数据不要放进仓库。

## 左边栏目录备份状态

已进入 GitHub 的主要目录：

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

只保留源码/文档，未提交大文件或本地生成物的目录：

- `ai-solo-founder-douyin/`：保留项目源码和配置，排除帧图、音频、视频输出。
- `dist/`、`public/`：保留必要入口和下载清单，排除旧构建包、Windows 安装包。
- `work/`：保留脚本和示例输入，排除本地 WeChat 扫描证据、命中结果和 QA 截图输出。

未进入 GitHub，换 Mac 后建议重新生成或另备份的目录：

- `node_modules/`：用 `npm install` 重装。
- `.venv/`、`.pytest_cache/`、`__pycache__/`：Python 环境和缓存，用 `python3 -m venv .venv` 和 `pip install -r requirements.txt` 重建。
- `.codex-video-output/`、`.codex-video-tools/`、`output/`、`outputs/`、`release/`、`tmp/`：视频、构建、测试和临时产物。
- `data/`、`external/`、`videos/`、`system-optimization-backup/`：本地数据、外部依赖和历史备份，普通 GitHub 仓库不适合直接存。

如果需要把视频、安装包、数据库、历史缓存也完整带走，建议单独做一个大文件备份：移动硬盘、网盘、GitHub Release 分卷压缩包，或 Git LFS。普通 GitHub 仓库不适合直接提交这类内容。

## 当前电脑配置

- 主板/整机：Colorful H610M-E M.2
- CPU：Intel Core i5-12400F，6 核 12 线程
- 内存：16GB DDR4 3200
- 硬盘：Colorful CF600 512GB SSD
- 显卡：NVIDIA GeForce RTX 5060
- 系统：Windows 11 Pro 64-bit

## 置换估算

估算只作为出售/置换谈判参考，最终取决于保修、成色、发票、显卡显存、机箱电源品牌和本地平台成交价。

- 平台极速回收/置换：约 3000-3800 元
- 二手平台整机耐心卖：约 3800-4800 元
- 拆件卖且显卡有保修：可能约 4200-5200 元

这台机器主要价值在 RTX 5060 和 i5-12400F。若平台报价低于 3000 元，建议优先考虑二手平台自行出售；若能到 4000 元以上，换 Mac 的压力会小很多。

## 推荐 Mac 方向

工作用途包含 Codex、多 Agent、前后端开发、文档/脚本、图片视频生成或剪辑时，建议内存从 24GB 起步，存储 512GB 起步。

- 性价比桌面：Mac mini M4 或 M4 Pro，24GB 内存，512GB SSD 起步。适合固定工位，预算压力最小。
- 便携够用：MacBook Air M5，24GB/32GB 内存，512GB SSD 起步。适合移动办公和开发，持续剪辑/渲染不如 Pro。
- 更稳的主力机：14 英寸 MacBook Pro，M5 Pro 或更新 Pro 芯片，32GB/36GB 内存，1TB SSD 更舒服。适合同时跑 Codex、浏览器、后端服务、剪辑和多任务。

不建议再买 8GB/16GB 内存的 Mac 做主力开发机；后期不能升级内存，会很快卡住。

## 新 Mac 恢复步骤

```bash
git clone https://github.com/200510wjh/ai-kefu-opensource.git
cd ai-kefu-opensource
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
npm run dev
```

随后把真实 API Key、平台 token、部署密码等只写入本地 `.env` 或系统钥匙串，不提交到 GitHub。
