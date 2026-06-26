# 部署指南

## 本地开发

```bash
npm install
pip install -r requirements.txt
npm run api
npm run dev
```

前端：`http://localhost:5173`
后端：`http://localhost:8000`

## 生产建议

- 前端：Vercel、Cloudflare Pages、Nginx 静态站点均可。
- 后端：Docker、Railway、Render、ECS、轻量云服务器均可。
- 存储：开发用本地 `data/artifacts`，生产建议换 S3、R2、OSS。
- 队列：开发用内存任务，生产建议 Redis + Celery/RQ。
- 数据库：开发用内存模型，生产建议 PostgreSQL。

## 上线前检查

- 复制 `.env.example` 为 `.env`，填入真实配置。
- 运行 `python scripts/secret_scan.py`。
- 运行 `npm run build`。
- 运行 `python -m compileall backend`。
- 确认 README、截图、演示视频和 LICENSE 都已准备好。
