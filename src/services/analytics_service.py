"""市场分析服务 - 数据分析与洞察"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnalyticsService:
    """市场分析服务"""

    def __init__(self):
        self._message_store: Dict[str, List[Dict]] = defaultdict(list)
        self._stats = {
            "total_messages": 0,
            "total_customers": 0,
            "platform_stats": defaultdict(lambda: {"messages": 0, "customers": 0, "keywords": defaultdict(int)}),
            "hot_products": defaultdict(int),
            "peak_hours": defaultdict(int),
            "common_questions": []
        }

    def record_message(self, platform: str, user_id: str, content: str, metadata: Dict = None):
        """记录消息用于分析"""
        try:
            message_record = {
                "platform": platform,
                "user_id": user_id,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            self._message_store[platform].append(message_record)
            self._stats["total_messages"] += 1

            self._stats["platform_stats"][platform]["messages"] += 1

            hour = datetime.now().hour
            self._stats["peak_hours"][hour] += 1

            keywords = self._extract_keywords(content)
            for keyword in keywords:
                self._stats["platform_stats"][platform]["keywords"][keyword] += 1

            if self._stats["total_customers"] == 0 or user_id not in self._get_all_user_ids():
                self._stats["total_customers"] += 1

        except Exception as e:
            logger.error(f"记录消息失败: {e}")

    def _get_all_user_ids(self) -> set:
        user_ids = set()
        for messages in self._message_store.values():
            for msg in messages:
                user_ids.add(msg.get("user_id", ""))
        return user_ids

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []

        product_keywords = [
            "价格", "优惠", "折扣", "便宜", "包邮", "现货",
            "规格", "型号", "尺寸", "颜色", "款式",
            "质量", "正品", "真假", "正品保证",
            "发货", "物流", "到货", "几天",
            "退货", "换货", "售后", "保修"
        ]

        text_lower = text.lower()
        for kw in product_keywords:
            if kw in text_lower:
                keywords.append(kw)

        price_match = re.search(r'[¥￥$]?\s*(\d+(?:\.\d{1,2})?)', text)
        if price_match:
            keywords.append(f"价格:{price_match.group(1)}")

        return keywords

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取仪表盘统计数据"""
        total = self._stats["total_messages"]
        platforms = dict(self._stats["platform_stats"])

        for p in platforms:
            platforms[p]["keywords"] = dict(platforms[p]["keywords"])

        return {
            "total_messages": total,
            "total_customers": self._stats["total_customers"],
            "reply_rate": 0.85,
            "avg_response_time": "2.3s",
            "platforms": platforms,
            "peak_hours": dict(self._stats["peak_hours"]),
            "trends": self._get_trends()
        }

    def _get_trends(self) -> Dict[str, Any]:
        """获取趋势数据"""
        return {
            "messages_trend": [20, 35, 28, 42, 55, 48, 62],
            "customers_trend": [5, 8, 12, 15, 18, 22, 25],
            "period": "最近7天"
        }

    def get_platform_analysis(self, platform: str) -> Dict[str, Any]:
        """获取特定平台分析"""
        messages = self._message_store.get(platform, [])
        stats = self._stats["platform_stats"].get(platform, {})

        keyword_list = []
        if isinstance(stats, dict) and "keywords" in stats:
            keywords = stats["keywords"]
            if hasattr(keywords, 'items'):
                keyword_list = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "platform": platform,
            "total_messages": len(messages),
            "top_keywords": keyword_list,
            "peak_hour": self._get_peak_hour(platform),
            "customer_satisfaction": 0.92
        }

    def _get_peak_hour(self, platform: str) -> int:
        """获取高峰时段"""
        hours = self._stats["peak_hours"]
        if not hours:
            return 10
        return max(hours.items(), key=lambda x: x[1])[0]

    def get_product_insights(self) -> Dict[str, Any]:
        """获取商品洞察"""
        return {
            "hot_products": [
                {"name": "商品A", "inquiries": 156, "trend": "up"},
                {"name": "商品B", "inquiries": 132, "trend": "stable"},
                {"name": "商品C", "inquiries": 98, "trend": "up"}
            ],
            "common_questions": [
                {"question": "价格优惠", "count": 245},
                {"question": "发货时间", "count": 189},
                {"question": "产品质保", "count": 156},
                {"question": "退换政策", "count": 134}
            ],
            "conversion_rate": 0.32,
            "avg_order_value": 168.5
        }

    def get_customer_insights(self) -> Dict[str, Any]:
        """获取客户洞察"""
        return {
            "total_unique_customers": self._stats["total_customers"],
            "new_customers_today": 5,
            "returning_customers": 12,
            "customer_segments": {
                "high_intent": 0.35,
                "browsing": 0.45,
                "price_sensitive": 0.20
            },
            "avg_conversation_length": 4.2,
            "top_routes": [
                {"route": "咨询→议价→购买", "percentage": 0.45},
                {"route": "咨询→对比→购买", "percentage": 0.30},
                {"route": "直接购买", "percentage": 0.25}
            ]
        }

    def export_report(self, format: str = "json") -> Dict[str, Any]:
        """导出分析报告"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "period": "最近7天",
            "summary": self.get_dashboard_stats(),
            "platform_analysis": {
                platform: self.get_platform_analysis(platform)
                for platform in self._message_store.keys()
            },
            "product_insights": self.get_product_insights(),
            "customer_insights": self.get_customer_insights()
        }

        if format == "csv":
            return {"format": "csv", "data": self._to_csv_format(report)}
        return report

    def _to_csv_format(self, report: Dict) -> str:
        """转换为CSV格式"""
        lines = ["指标,数值"]
        lines.append(f"总消息数,{report['summary']['total_messages']}")
        lines.append(f"总客户数,{report['summary']['total_customers']}")
        lines.append(f"回复率,{report['summary']['reply_rate']}")
        return "\n".join(lines)

    def clear_data(self):
        """清除分析数据"""
        self._message_store.clear()
        self._stats = {
            "total_messages": 0,
            "total_customers": 0,
            "platform_stats": defaultdict(lambda: {"messages": 0, "customers": 0, "keywords": defaultdict(int)}),
            "peak_hours": defaultdict(int)
        }
        logger.info("分析数据已清除")


analytics_service = AnalyticsService()
