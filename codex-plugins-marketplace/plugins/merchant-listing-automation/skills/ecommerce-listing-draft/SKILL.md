---
name: ecommerce-listing-draft
description: Generate safe ecommerce product listing drafts for Douyin Shop, Taobao, JD, Pinduoduo, Xiaohongshu, and Kuaishou. Use when the user asks to upload, list, publish, create a product draft, optimize product listing, generate SKU fields, or automate merchant back-office listing work.
---

# Ecommerce Listing Draft

Use this skill to help merchants prepare product listing drafts. The workflow is draft-first and confirmation-gated.

## Safety Boundary

Allowed without extra confirmation:

- Generate product titles.
- Generate selling points.
- Generate detail-page copy.
- Generate SKU tables.
- Generate customer FAQ.
- Generate short-video scripts.
- Create local JSON/Markdown draft files.
- Fill platform draft fields when the user explicitly asks to use Chrome/Computer Use for that platform.

Always require confirmation before:

- Publishing a product.
- Changing live prices.
- Changing live stock.
- Deleting or pausing products.
- Refunding orders.
- Shipping orders.
- Sending messages to buyers.
- Uploading private customer data or credentials.

## Inputs To Collect

Ask for missing essentials only when they cannot be inferred:

- Product name.
- Category.
- Target platform.
- Price or price range.
- Cost or margin target if available.
- SKU/spec options.
- Stock.
- Product images or image folder.
- 3-5 selling points.
- Shipping promise.
- After-sales promise.

## Draft Output Schema

Produce this structure:

```json
{
  "platform": "douyin|taobao|jd|pinduoduo|xiaohongshu|kuaishou",
  "product_name": "",
  "category": "",
  "titles": [],
  "short_title": "",
  "selling_points": [],
  "detail_sections": [],
  "sku_table": [],
  "price_strategy": "",
  "stock_plan": "",
  "image_brief": [],
  "video_scripts": [],
  "customer_faq": [],
  "risk_checks": [],
  "publish_boundary": "save_draft_only"
}
```

## Platform Field Guidance

Douyin Shop:

- Title should be direct and searchable.
- Avoid exaggerated promises.
- Prepare product highlight labels for short-video and live-room conversion.
- Draft-only unless the merchant explicitly confirms final publish.

Taobao/Tmall:

- Title can include category, material, season, audience, style, and core feature.
- Detail copy should emphasize trust, size/specs, logistics, and after-sales.

Pinduoduo:

- Title should be price-sensitive and benefit-led.
- SKU table should be simple and easy to compare.

JD:

- Emphasize specs, warranty, brand trust, and logistics.

Xiaohongshu:

- Prepare softer planting-note style copy and scene-based images.

## Computer Use Workflow

When the user asks to use `Computer Use` for platform back-office automation:

1. Use Chrome/browser capabilities first when available.
2. Use Computer Use only for desktop or weak-accessibility platform pages.
3. Navigate to the merchant platform only after the user names the platform.
4. Do not enter API keys, passwords, or payment information.
5. Fill fields as draft.
6. Stop before publish/submit if it creates a live listing.
7. Tell the user exactly what remains for them to confirm.

## Sellable Package

Recommended commercial packaging:

- 299 RMB: one-product listing draft pack.
- 999 RMB: ten-product batch listing pack.
- 2999 RMB/month: monthly new-product listing assistant.
- 9999 RMB/month: agency/private deployment with template customization.

