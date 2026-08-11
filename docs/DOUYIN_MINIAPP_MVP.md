# 抖音小程序 MVP 落地记录

## 定位

小程序不是完整 SaaS 后台，而是抖音流量里的获客入口。

第一版目标：

- 商家看得懂。
- 可以从短视频挂载进入。
- 能输入需求。
- 能生成方案。
- 能留下联系方式。
- 后台能承接线索。

## 已创建目录

```text
douyin-miniapp/
```

## 页面

- `pages/index/index`：需求输入和生成入口。
- `pages/cases/cases`：奶茶店、健身房、电商零食案例。
- `pages/result/result`：脚本、分镜、客服话术。
- `pages/lead/lead`：留资表单。

## 已接接口

- `POST https://wjhai.cn/merchant-admin/api/scripts`
- `POST https://wjhai.cn/merchant-admin/api/leads`

## 当前限制

- 需要把 `project.config.json` 里的 AppID 替换成真实 AppID。
- 需要在抖音开放平台配置合法 request 域名：`https://wjhai.cn`。
- 真机请求是否成功取决于平台域名配置和小程序审核状态。
- 当前没有做抖音登录，因为 MVP 先做商家留资，不强制登录。

## 后续优先级

1. 隐私协议和用户协议页面。
2. 后台增加 `source=miniapp` 的线索筛选。
3. 增加案例生成结果固定模板，便于审核人员快速理解。
4. 增加“复制脚本”和“保存图片”能力。
5. 接入订阅/套餐前，先用人工回访成交。
