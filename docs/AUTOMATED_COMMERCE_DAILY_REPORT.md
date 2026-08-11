# 自动化电商日报使用说明

这版是你自己先试用的自动化版本：不用真实店铺授权，先用本地示例数据一键生成日报。跑通后，再把数据源换成 `mcp-cn-commerce` 的真实抖店、京东、淘宝、拼多多数据。

## 一键生成

在项目根目录运行：

```bash
npm run auto:daily-report
```

输出文件会生成到：

```text
data/artifacts/commerce_reports/
```

## API 调用

启动后端：

```bash
npm run api
```

调用：

```text
POST http://localhost:8000/api/ecommerce/daily-report
```

返回内容包含：

- `report`：日报 Markdown 内容
- `artifact_url`：生成文件下载地址
- `source`：当前数据源
- `next_action`：下一步自动化建议

## 替换成你自己的测试数据

编辑这个文件：

```text
data/ecommerce_daily_sample.json
```

可以先用你自己的店铺截图手工录入这些字段：

- `gmv`
- `order_count`
- `avg_order_value`
- `refund_rate`
- `top_products`
- `reviews`
- `low_stock_alerts`

## 接真实平台数据

后续接入真实平台时，把数据源换成：

- 抖店：`mcp-cn-doudian`
- 巨量引擎：`mcp-cn-oceanengine`
- 京东：`mcp-cn-jd`
- 淘宝：`mcp-cn-taobao`
- 拼多多：`mcp-cn-pinduoduo`

第一版先保持只读：

- 不自动改价
- 不自动退款
- 不自动发货
- 不自动发布商品

