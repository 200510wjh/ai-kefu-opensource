# 商剪增长画布

一个面向本地商家、电商卖家和 AI 代理商的商家内容增长 SaaS 原型。它把一句商家需求转换成短视频分镜、主图/详情图结构、客服话术和线索承接流程。

## 核心场景

- 本地商家版：输入门店、活动和优惠，生成抖音同城短视频脚本、分镜和预约 CTA。
- 电商卖家版：输入商品卖点，生成主图、详情图、商品短视频和客服话术结构。
- 代理商/开发者版：开源核心画布，后续用于私有化部署、二开模板库和 API 调用额度。

## 当前能力

- 9:16 竖屏画布预览。
- 三种获客入口：本地商家、电商卖家、代理商/开发者。
- 四类生成任务：短视频、主图、详情图、客服话术。
- SaaS 核心 API：Project、Asset、GenerationJob、Lead、Subscription。
- 抖音/GitHub 线索收集面板。
- Starter、Pro、Agency 三档订阅套餐展示。
- 30 天抖音内容测试日历。
- 本地文件存储的生成清单下载。

## 运行

```bash
npm install
pip install -r requirements.txt
npm run api
npm run dev
```

前端默认运行在 `http://localhost:5173`，后端默认运行在 `http://localhost:8000`。

## 验证

```bash
npm run build
python -m compileall backend
python scripts/secret_scan.py
```

## 存储

默认写入 `data/artifacts`。如果当前磁盘空间低于 10MB，会自动写入 `D:/merchant-auto-cut-data`。也可以通过 `MERCHANT_AUTO_CUT_DATA_DIR` 指定存储路径。

## 开源发布前清单

- 准备首页截图和 3 个 demo 视频：奶茶店、健身房、电商零食。
- 复制 `.env.example` 为 `.env`，真实密钥只放本地或部署平台。
- 运行 `python scripts/secret_scan.py`。
- 确认 `LICENSE`、`SECURITY.md`、`docs/DEPLOYMENT.md`、`docs/GTM.md` 都已更新。
- 创建 GitHub remote 后再提交和推送。

## 后续接入

当前后端的生成接口按可替换适配器设计。后续可以接入 FFmpeg、Remotion、HyperFrames、图片生成模型、知识库客服和抖音企业号线索链路。

## 接入更好的 AI 生成

后端支持 OpenAI-compatible `/v1/chat/completions`。配置后，`/api/scripts` 会优先调用大模型生成更强的脚本和分镜；未配置或调用失败时自动回退模板。

```bash
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_API_KEY=你的真实密钥
```

也可以把 `AI_BASE_URL` 指向火山方舟、DeepSeek、通义、OpenRouter、硅基流动等兼容服务。
