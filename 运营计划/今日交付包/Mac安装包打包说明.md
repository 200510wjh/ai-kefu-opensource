# Mac 安装包打包说明

当前已加入 Electron 桌面客户端工程，默认打开：

```text
https://wjhai.cn/merchant-admin/
```

本机 Windows 不能正式生成可签名的 macOS `.dmg`，需要在 Mac 电脑或 macOS CI 上执行：

```bash
npm install
bash scripts/build_mac_installer.sh
```

输出目录：

```text
release/
```

会生成：

```text
商家AI增长工作台-0.1.0-mac.dmg
商家AI增长工作台-0.1.0-mac.zip
```

如果要让 Mac 客户端打开本地测试页面：

```bash
MERCHANT_APP_URL=http://127.0.0.1:5173/ npm run desktop:preview
```

注意：

- 正式出售给客户前，需要 Apple Developer 账号做签名和 notarization。
- 当前客户端是 SaaS 桌面壳，核心功能仍由网页后台和服务器 API 提供。
- 如果服务器不可访问，客户端会显示内置错误页，不会白屏。

## 当前 Windows 侧已验证

```powershell
npm run desktop:mac:check
```

已通过配置验收：`appId`、`productName`、`dmg/zip` 目标、Electron 主进程文件均存在。

已生成 Mac 打包工程压缩包：

```text
C:\Users\Administrator\Documents\运营\release\商家AI增长工作台-mac打包工程.zip
```

## 服务器上线脚本

服务器 SSH 恢复后，在 Windows 本机运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_server.ps1
```

脚本会构建 `/merchant-admin/` 前端资源、打包、上传到 `/opt/merchant-growth-canvas`、备份旧版本并重启 `merchant-growth-canvas.service`。
