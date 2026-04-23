# AI客服知识库

> 用于存储商品信息、常见问题等知识，供AI参考回复

## 目录结构

```
knowledge-base/
├── products/          # 商品信息
│   ├── product_list.txt
│   └── product_details/
├── faq/              # 常见问题
│   ├── shipping.txt
│   ├── refund.txt
│   └── size_guide.txt
└── responses/        # 标准回复模板
    ├── greeting.txt
    ├── goodbye.txt
    └── holiday.txt
```

## 添加商品信息

在 `products/product_list.txt` 中添加商品信息：

```
商品编号 | 商品名称 | 价格 | 库存 | 规格
SKU001 | 商品A | ¥99 | 有货 | M/L/XL
SKU002 | 商品B | ¥199 | 有货 | 均码
```

## FAQ格式

在 `faq/` 目录下创建问答对文本文件，格式：

```
问题：如何退换货？
回答：亲，7天内可无理由退换货，请联系客服提供订单号办理。

问题：发什么快递？
回答：默认发顺丰快递，部分地区可能使用圆通/中通。
```
