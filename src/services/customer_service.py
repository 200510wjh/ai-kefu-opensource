"""获客服务 - 客户获取与管理"""
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class CustomerAcquisitionService:
    """获客服务"""

    def __init__(self):
        self._customers: Dict[str, Dict] = {}
        self._conversations: Dict[str, List[Dict]] = defaultdict(list)
        self._leads: List[Dict] = []
        self._campaigns: List[Dict] = []

    def register_customer(self, platform: str, user_id: str, user_name: str = None,
                         source: str = None, metadata: Dict = None) -> Dict[str, Any]:
        """注册新客户"""
        customer_id = f"{platform}_{user_id}"

        if customer_id in self._customers:
            self._customers[customer_id]["last_active"] = datetime.now().isoformat()
            return {"success": True, "customer_id": customer_id, "is_new": False}

        customer = {
            "id": customer_id,
            "platform": platform,
            "user_id": user_id,
            "user_name": user_name or f"{platform}用户",
            "source": source or platform,
            "first_contact": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "status": "new",
            "score": 50,
            "tags": [],
            "metadata": metadata or {}
        }

        self._customers[customer_id] = customer
        logger.info(f"新客户注册: {customer_id}")

        return {"success": True, "customer_id": customer_id, "is_new": True}

    def update_customer_score(self, customer_id: str, score_delta: int) -> bool:
        """更新客户评分"""
        if customer_id not in self._customers:
            return False

        customer = self._customers[customer_id]
        customer["score"] = max(0, min(100, customer["score"] + score_delta))

        if customer["score"] >= 80:
            customer["status"] = "hot_lead"
        elif customer["score"] >= 50:
            customer["status"] = "warm_lead"
        else:
            customer["status"] = "cold_lead"

        customer["last_active"] = datetime.now().isoformat()
        return True

    def record_interaction(self, customer_id: str, interaction_type: str,
                          content: str, metadata: Dict = None) -> bool:
        """记录客户互动"""
        if customer_id not in self._customers:
            return False

        interaction = {
            "id": str(uuid.uuid4())[:8],
            "type": interaction_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        self._conversations[customer_id].append(interaction)

        score_map = {
            "message": 1,
            "inquiry": 3,
            "negotiation": 5,
            "purchase_intent": 8,
            "purchase": 15
        }

        self.update_customer_score(customer_id, score_map.get(interaction_type, 1))

        if interaction_type in ["purchase_intent", "purchase"]:
            self._add_lead(customer_id, interaction_type)

        return True

    def _add_lead(self, customer_id: str, lead_type: str):
        """添加线索"""
        if customer_id not in self._customers:
            return

        customer = self._customers[customer_id]

        for existing_lead in self._leads:
            if existing_lead["customer_id"] == customer_id:
                existing_lead["last_update"] = datetime.now().isoformat()
                return

        lead = {
            "id": str(uuid.uuid4())[:8],
            "customer_id": customer_id,
            "platform": customer["platform"],
            "user_name": customer["user_name"],
            "score": customer["score"],
            "status": "new",
            "type": lead_type,
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "notes": []
        }

        self._leads.append(lead)
        logger.info(f"新线索添加: {customer_id}")

    def get_leads(self, status: str = None, limit: int = 50) -> List[Dict]:
        """获取线索列表"""
        leads = self._leads

        if status:
            leads = [l for l in leads if l.get("status") == status]

        leads.sort(key=lambda x: (x.get("score", 0), x.get("last_update", "")), reverse=True)
        return leads[:limit]

    def update_lead_status(self, lead_id: str, status: str, note: str = None) -> bool:
        """更新线索状态"""
        for lead in self._leads:
            if lead["id"] == lead_id:
                lead["status"] = status
                lead["last_update"] = datetime.now().isoformat()
                if note:
                    lead["notes"].append({
                        "content": note,
                        "timestamp": datetime.now().isoformat()
                    })
                return True
        return False

    def get_customers(self, filters: Dict = None) -> List[Dict]:
        """获取客户列表"""
        customers = list(self._customers.values())

        if filters:
            if filters.get("platform"):
                customers = [c for c in customers if c.get("platform") == filters["platform"]]
            if filters.get("status"):
                customers = [c for c in customers if c.get("status") == filters["status"]]
            if filters.get("min_score"):
                customers = [c for c in customers if c.get("score", 0) >= filters["min_score"]]

        customers.sort(key=lambda x: x.get("last_active", ""), reverse=True)
        return customers

    def get_customer_detail(self, customer_id: str) -> Optional[Dict]:
        """获取客户详情"""
        if customer_id not in self._customers:
            return None

        customer = self._customers[customer_id].copy()
        customer["conversations"] = self._conversations.get(customer_id, [])
        return customer

    def get_conversation_history(self, customer_id: str, limit: int = 20) -> List[Dict]:
        """获取对话历史"""
        conversations = self._conversations.get(customer_id, [])
        return conversations[-limit:]

    def create_campaign(self, name: str, target: str, content: str,
                       channels: List[str] = None) -> Dict[str, Any]:
        """创建营销活动"""
        campaign = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "target": target,
            "content": content,
            "channels": channels or ["auto_reply"],
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "stats": {
                "sent": 0,
                "opened": 0,
                "converted": 0
            }
        }

        self._campaigns.append(campaign)
        return {"success": True, "campaign": campaign}

    def get_campaigns(self) -> List[Dict]:
        """获取营销活动列表"""
        return self._campaigns

    def get_acquisition_stats(self) -> Dict[str, Any]:
        """获取获客统计"""
        total_customers = len(self._customers)
        new_today = sum(1 for c in self._customers.values()
                       if datetime.now().strftime("%Y-%m-%d") in c.get("first_contact", ""))

        hot_leads = sum(1 for c in self._customers.values() if c.get("score", 0) >= 80)
        warm_leads = sum(1 for c in self._customers.values()
                        if 50 <= c.get("score", 0) < 80)

        platform_distribution = defaultdict(int)
        for c in self._customers.values():
            platform_distribution[c.get("platform", "unknown")] += 1

        return {
            "total_customers": total_customers,
            "new_today": new_today,
            "hot_leads": hot_leads,
            "warm_leads": warm_leads,
            "total_leads": len(self._leads),
            "platform_distribution": dict(platform_distribution),
            "avg_score": sum(c.get("score", 0) for c in self._customers.values()) / max(total_customers, 1),
            "conversion_rate": len([l for l in self._leads if l.get("status") == "converted"]) / max(len(self._leads), 1)
        }

    def export_customers(self, format: str = "json") -> Dict[str, Any]:
        """导出客户数据"""
        return {
            "format": format,
            "exported_at": datetime.now().isoformat(),
            "total": len(self._customers),
            "customers": list(self._customers.values()),
            "leads": self._leads
        }


customer_acquisition_service = CustomerAcquisitionService()
