# AI Provider 接入建议

当前项目先接入 OpenAI-compatible Chat Completions，用于生成更有网感的短视频脚本、主图/详情页结构和客服话术。

## 推荐开源/服务方向

- OpenShorts：适合参考短视频生成 SaaS 工作流。
- Open AI UGC：适合参考 UGC 广告视频生成链路。
- AdGen：适合参考商品 URL 到 Remotion 广告视频。
- 302 AI E-commerce Scene Image Generator：适合参考电商商品图、场景图生成。
- withoutbg / imgly background-removal：适合商品图抠图和素材预处理。

## 环境变量

```bash
AI_PROVIDER=openai_compatible
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_API_KEY=真实密钥
AI_TEMPERATURE=0.85
AI_TIMEOUT=35
```

## 下一步

- 视频：接 Remotion/HyperFrames，把 storyboard JSON 渲染成 mp4。
- 数字人：接 HeyGen，把口播脚本生成真人讲解。
- 电商图：接图片生成 API，把主图/详情图结构变成真实图片。
- 客服：接知识库/RAG，把客服话术升级成可回复私信的系统。
