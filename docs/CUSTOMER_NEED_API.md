# 客户需求接入 API

这个接口用于把外部来的商家需求统一接入系统。适用来源包括抖音线索表单、抖音小程序、网站表单、企业微信客服、人工导入和你已有的客户需求 API。

## Endpoint

```http
POST /api/intake/customer-need
Content-Type: application/json
```

## Example

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

## What It Creates

- `lead`: 一条可跟进线索。
- `project`: 一个商家项目。
- `brief`: 系统内部统一需求结构。
- `scripts`: 可选的脚本/分镜方向。
- `reply_analysis`: 客服成交分析，包括客户阶段、意向分、缺失信息、下一步动作和候选回复。

## Integration Rule

外部系统不用理解内部画布和客服逻辑，只要提交商家、联系方式、需求文本和来源。后端会自动转换成内容生成和客服成交所需的数据。
