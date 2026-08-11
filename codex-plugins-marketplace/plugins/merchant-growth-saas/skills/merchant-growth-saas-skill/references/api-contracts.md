# API Contracts

## Customer Need Intake

Use this route when a need comes from Douyin forms, miniapp forms, website forms, WeCom, manual imports, or another customer-intake API.

```http
POST /api/intake/customer-need
Content-Type: application/json
```

Minimal payload:

```json
{
  "source": "douyin",
  "business_name": "青提茶饮万达店",
  "contact": "13800000000",
  "industry": "新式茶饮",
  "product_name": "夏日青提冰茶",
  "need_text": "想做抖音同城引流，老板发一句需求就能出短视频脚本、分镜和客服回复",
  "platform": "抖音",
  "generation_kind": "customer_service",
  "customer_message": "这个系统多少钱？能不能先看一个样例？",
  "call_to_action": "私信领取试用方案"
}
```

Expected response:

```json
{
  "intake_id": "...",
  "lead": {"id": "..."},
  "project": {"id": "..."},
  "brief": {"industry": "..."},
  "scripts": [],
  "reply_analysis": {
    "intent_summary": "...",
    "service_insight": {
      "stage": "报价比较",
      "lead_score": 80,
      "temperature": "hot",
      "next_best_action": "..."
    },
    "candidates": [],
    "lead_capture": {}
  },
  "next_actions": []
}
```

If adding a new source, map its fields into this contract instead of creating a separate one-off endpoint.

## AI Customer Service

Use this route for pasted chats, DM replies, WeChat replies, and customer service sessions:

```http
POST /api/reply-assistant
```

Payload:

```json
{
  "channel": "douyin_dm",
  "scenario": "抖音私信转化",
  "conversation": "客户：多少钱？能先看案例吗？",
  "goal": "引导客户发需求并留下联系方式",
  "tone": "high_eq",
  "recipient_profile": "商家老板"
}
```

The response must include `service_insight`; if it only returns reply text, the AI客服 has regressed into a simple copywriting tool.
