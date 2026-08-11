# 商品媒体工厂 E2E 验收报告

时间：2026-07-12T16:49:30

本地验收：閫氳繃
线上验收：通过

## 本地产物

- 商品实拍图锛歚C:\Users\Administrator\Documents\运营\运营计划\今日交付包\商品媒体工厂测试\商品实拍样图_E2E.png`
- 主图 SVG锛歚data\artifacts\product_media\4994e8bf-8a82-4bdf-a4c8-3c03205a9afd_main.png`
- 详情图 SVG锛歚data\artifacts\product_media\4994e8bf-8a82-4bdf-a4c8-3c03205a9afd_detail.png`
- MP4 视频锛歚data\artifacts\product_media\4994e8bf-8a82-4bdf-a4c8-3c03205a9afd_video.mp4`
- 视频首帧锛歚C:\Users\Administrator\Documents\运营\运营计划\今日交付包\商品媒体工厂测试\商品短视频首帧_E2E.png`
- 验收截图：`C:\Users\Administrator\Documents\运营\运营计划\今日交付包\商品媒体工厂测试\商品媒体工厂E2E验收截图.png`

## 本地检查

- product_name_preserved: 閫氳繃
- main_image_exists: 閫氳繃
- detail_image_exists: 閫氳繃
- video_rendered: 閫氳繃
- publish_boundary_safe: 閫氳繃
- first_frame_extracted: 閫氳繃

## 线上检查

- product_name_preserved: 閫氳繃
- main_accessible: 閫氳繃
- detail_accessible: 閫氳繃
- video_accessible: 閫氳繃
- publish_boundary_safe: 閫氳繃

## 线上产物 URL

- 主图：https://wjhai.cn/merchant-admin/artifacts/product_media/1814b17d-e24a-4b53-ad1b-23a80f44e675_main.png
- 详情图：https://wjhai.cn/merchant-admin/artifacts/product_media/1814b17d-e24a-4b53-ad1b-23a80f44e675_detail.png
- 视频：https://wjhai.cn/merchant-admin/artifacts/product_media/1814b17d-e24a-4b53-ad1b-23a80f44e675_video.mp4

## 边界

- 当前是生成商品主图、详情图和 MP4 视频，不是自动发布到抖音小店。
- 上架草稿的 publish_boundary 必须保持 save_draft_only，发布前需要商家人工确认。
