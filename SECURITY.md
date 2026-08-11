# Security

## 密钥处理

不要提交真实 API Key、服务器密码、数据库连接串或 Cookie。使用 `.env.example` 公开变量名，真实值只放本地 `.env` 或部署平台的环境变量。

## 发布前扫描

```bash
python scripts/secret_scan.py
```

如果扫描命中，请先确认是否为真实密钥。真实密钥需要从历史记录和部署平台中一并轮换。
