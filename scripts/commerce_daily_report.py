from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "ecommerce_daily_sample.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "artifacts" / "commerce_reports"


def money(value: float) -> str:
    return f"{value:,.2f} 元"


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def change_rate(today: float, yesterday: float) -> str:
    if yesterday == 0:
        return "N/A"
    delta = (today - yesterday) / yesterday
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta * 100:.1f}%"


def pp_change(today: float, yesterday: float) -> str:
    delta = (today - yesterday) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}pp"


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def shop_summary(shop: dict[str, Any]) -> dict[str, float]:
    summary = shop.get("summary", {})
    yesterday = shop.get("yesterday", {})
    return {
        "gmv": float(summary.get("gmv", 0)),
        "orders": float(summary.get("order_count", 0)),
        "avg_order_value": float(summary.get("avg_order_value", 0)),
        "refund_rate": float(summary.get("refund_rate", 0)),
        "yesterday_gmv": float(yesterday.get("gmv", 0)),
        "yesterday_orders": float(yesterday.get("order_count", 0)),
        "yesterday_refund_rate": float(yesterday.get("refund_rate", 0)),
    }


def build_report(payload: dict[str, Any]) -> str:
    shops = payload.get("shops", [])
    date = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    totals = {
        "gmv": sum(shop_summary(shop)["gmv"] for shop in shops),
        "orders": sum(shop_summary(shop)["orders"] for shop in shops),
        "yesterday_gmv": sum(shop_summary(shop)["yesterday_gmv"] for shop in shops),
        "yesterday_orders": sum(shop_summary(shop)["yesterday_orders"] for shop in shops),
    }
    total_refunds = sum(float(shop.get("summary", {}).get("refund_count", 0)) for shop in shops)
    total_orders = max(totals["orders"], 1)
    refund_rate = total_refunds / total_orders
    yesterday_refund_rate = (
        sum(shop_summary(shop)["yesterday_refund_rate"] * max(shop_summary(shop)["yesterday_orders"], 1) for shop in shops)
        / max(totals["yesterday_orders"], 1)
    )
    avg_order_value = totals["gmv"] / total_orders
    yesterday_avg_order_value = totals["yesterday_gmv"] / max(totals["yesterday_orders"], 1)

    all_products: list[dict[str, Any]] = []
    review_reasons: Counter[str] = Counter()
    for shop in shops:
        for product in shop.get("top_products", []):
            item = dict(product)
            item["shop_name"] = shop.get("shop_name", "")
            item["platform"] = shop.get("platform", "")
            all_products.append(item)
        for review in shop.get("reviews", []):
            reason = str(review.get("reason", "未分类"))
            review_reasons[reason] += 1

    all_products.sort(key=lambda item: float(item.get("gmv", 0)), reverse=True)
    low_stock = payload.get("low_stock_alerts", [])
    high_refund_shops = [
        shop for shop in shops if float(shop.get("summary", {}).get("refund_rate", 0)) >= 0.05
    ]

    lines = [
        f"# AI 电商经营日报 - {date}",
        "",
        "## 今日老板结论",
    ]
    if high_refund_shops:
        names = "、".join(str(shop.get("shop_name", "")) for shop in high_refund_shops)
        lines.append(f"今天整体有增长机会，但 {names} 的退款率偏高，优先处理退款原因和高风险 SKU。")
    else:
        lines.append("今天整体经营稳定，重点关注热销品补货和高 GMV 商品的持续投放。")

    lines.extend(
        [
            "",
            "## 核心指标",
            "| 指标 | 今日 | 昨日 | 变化 |",
            "| --- | ---: | ---: | ---: |",
            f"| GMV | {money(totals['gmv'])} | {money(totals['yesterday_gmv'])} | {change_rate(totals['gmv'], totals['yesterday_gmv'])} |",
            f"| 订单数 | {int(totals['orders'])} | {int(totals['yesterday_orders'])} | {change_rate(totals['orders'], totals['yesterday_orders'])} |",
            f"| 客单价 | {money(avg_order_value)} | {money(yesterday_avg_order_value)} | {change_rate(avg_order_value, yesterday_avg_order_value)} |",
            f"| 退款率 | {percent(refund_rate)} | {percent(yesterday_refund_rate)} | {pp_change(refund_rate, yesterday_refund_rate)} |",
            "",
            "## 平台对比",
            "| 店铺 | 平台 | GMV | 订单 | 退款率 | 判断 |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )

    for shop in shops:
        summary = shop_summary(shop)
        judgment = "需要关注退款" if summary["refund_rate"] >= 0.05 else "正常"
        lines.append(
            f"| {shop.get('shop_name', '')} | {shop.get('platform', '')} | {money(summary['gmv'])} | {int(summary['orders'])} | {percent(summary['refund_rate'])} | {judgment} |"
        )

    lines.extend(["", "## 热销商品 Top 5", "| 商品 | 店铺 | 销量 | GMV | 库存 | 建议 |", "| --- | --- | ---: | ---: | ---: | --- |"])
    for product in all_products[:5]:
        stock = int(product.get("stock", 9999))
        advice = "优先补货" if stock < 50 else "保持投放"
        lines.append(
            f"| {product.get('name', '')} | {product.get('shop_name', '')} | {int(product.get('sales', 0))} | {money(float(product.get('gmv', 0)))} | {stock} | {advice} |"
        )

    lines.extend(["", "## 异常预警"])
    if not high_refund_shops and not low_stock:
        lines.append("- 暂无明显异常。")
    for shop in high_refund_shops:
        rate = float(shop.get("summary", {}).get("refund_rate", 0))
        lines.append(f"- {shop.get('shop_name', '')} 退款率 {percent(rate)}，超过 5%，需要查看尺码、质量、物流或客服原因。")
    for item in low_stock:
        lines.append(f"- {item.get('platform', '')} {item.get('product', '')} {item.get('sku', '')} 库存仅 {item.get('stock', 0)}，建议确认补货或限流。")

    lines.extend(["", "## 差评 / 退款原因"])
    if review_reasons:
        for reason, count in review_reasons.most_common():
            lines.append(f"- {reason}：{count} 条")
    else:
        lines.append("- 暂无差评原因数据。")

    lines.extend(
        [
            "",
            "## 明日自动行动清单",
            "1. 先处理退款率超过 5% 的店铺和 SKU，不要盲目加投放。",
            "2. 对库存低于 50 的热销品确认补货，避免爆品断货。",
            "3. 把差评原因整理成客服话术，优先引导换货和解释，不直接退款。",
            "4. 对 GMV Top 商品继续保留预算，对退款高的规格暂停或降预算。",
            "",
            "## 自动化状态",
            "- 当前版本：本地数据自动生成日报。",
            "- 下一步：接入 mcp-cn-commerce 后，把数据源替换成抖店 / 京东 / 淘宝 / 拼多多 API。",
            "- 安全边界：只读数据，不自动改价、不自动退款、不自动发货。",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: str, output_dir: Path, date: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"ai-commerce-daily-report-{date}.md"
    path.write_text(report, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an automated AI commerce daily report.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    payload = load_payload(args.input)
    report = build_report(payload)
    output = write_report(report, args.output_dir, str(payload.get("date", datetime.now().strftime("%Y-%m-%d"))))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
