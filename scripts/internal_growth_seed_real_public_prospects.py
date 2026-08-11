from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.internal_growth.models import CustomerInteraction, FollowUpTask, Lead
from backend.internal_growth.store import store


PROSPECTS = [
    {
        "customer_name": "青岛易亚网络管理服务有限公司",
        "source_platform": "public_web",
        "industry": "抖音本地生活代运营 / 电商代运营",
        "demand": "官网公开提供抖音本地生活代运营、门店引流、团购成单、数据分析等服务。适合作为 Internal Growth OS 的真实潜在客户或合作服务商：他们服务本地商家，可能需要用AI减少需求判断、内容生产、客户跟进和复盘时间。",
        "contact": "官网：https://www.yiyaweb.com/like/；公开服务热线：400-003-6759",
        "next_action": "人工访问官网，准备一版“帮代运营团队提高内容产能和线索跟进效率”的合作私信/电话开场。",
    },
    {
        "customer_name": "客如云",
        "source_platform": "public_web",
        "industry": "餐饮门店SaaS / 抖音代运营生态服务",
        "demand": "公开页面显示其面向餐饮连锁企业提供餐饮门店抖音代运营及智慧门店管理服务。适合作为真实潜在客户或渠道合作对象：他们服务大量餐饮门店，可能需要AI辅助内容脚本、线索跟进和数据复盘。",
        "contact": "官网页面：https://www.keruyun.com/market/tiktok",
        "next_action": "人工访问官网，准备“餐饮门店抖音获客内容与CRM跟进自动化”的合作邀约。",
    },
    {
        "customer_name": "标点云",
        "source_platform": "public_web",
        "industry": "抖音本地生活小程序 / 服务商工具",
        "demand": "公开页面显示其为抖音官方认证服务商，提供抖音本地生活小程序开发制作，面向本地自媒体、本地生活团购达人、KOC、MCN机构。适合作为真实潜在客户：需要服务大量本地生活客户和内容/线索流程。",
        "contact": "官网页面：https://www.biaodianyun.com/dyxcx/",
        "next_action": "人工访问官网，准备“给服务商增加AI获客运营工作台”的合作话术。",
    },
    {
        "customer_name": "有赞",
        "source_platform": "public_web",
        "industry": "小红书/抖音私域与门店经营SaaS",
        "demand": "公开页面显示有赞提供小红书本地生活解决方案和抖音私域引流/客户沉淀方案。适合作为真实潜在客户或生态合作对象：其客户群需要内容种草、交易闭环、私域沉淀和CRM复购。",
        "contact": "小红书方案：https://www.youzan.com/solutions/xiaohongshu；抖音私域页面：https://www.youzan.com/search/topics/314bed5eb4c00000",
        "next_action": "人工确认合作入口，准备“AI需求雷达+内容工厂+线索跟进”生态合作提案。",
    },
    {
        "customer_name": "助标网络",
        "source_platform": "public_web",
        "industry": "抖音企业号代运营 / 本地生活运营",
        "demand": "公开页面显示其提供抖音企业号代运营、抖音本地生活团购开通、达人探店种草、评论私信话术等服务。适合作为真实潜在客户：可用AI减少内容方案、评论私信分析、线索跟进和复盘成本。",
        "contact": "官网页面：https://www.zhubiaotech.com/dyyytg.htm",
        "next_action": "人工访问官网，准备“代运营团队AI销售助手和内容工厂”的合作邀约。",
    },
    {
        "customer_name": "合肥三十六行网络科技有限公司",
        "source_platform": "public_web",
        "industry": "本地生活团购代运营",
        "demand": "公开文章提到其做抖音、美团、小红书、大众点评本地生活团购代运营，并给出官网 www.36hang.cc。适合作为真实潜在客户：跨平台团购代运营团队需要持续找需求、做内容、审核发布、跟踪咨询和成交。",
        "contact": "公开文章：https://www.cnblogs.com/yebang/p/19595377；官网：www.36hang.cc",
        "next_action": "人工核实官网和真实业务后，准备“跨平台代运营AI获客系统”的合作触达。",
    },
]


def save_prospect(item: dict[str, str]) -> Lead:
    existing = next((lead for lead in store.list_leads() if lead.customer_name == item["customer_name"]), None)
    lead = existing or Lead(
        id=str(uuid.uuid4()),
        customer_name=item["customer_name"],
        source_platform=item["source_platform"],
        industry=item["industry"],
        demand=item["demand"],
        contact=item["contact"],
        intent_level="medium",
        stage="new",
        next_followup_at="",
        next_action=item["next_action"],
    )
    if existing:
        lead = existing.model_copy(update={**item, "intent_level": existing.intent_level, "stage": existing.stage})
    saved = store.save_lead(lead)
    store.save_interaction(
        CustomerInteraction(
            id=str(uuid.uuid4()),
            lead_id=saved.id,
            channel="public_web",
            direction="note",
            content=f"真实公开潜在客户线索：{saved.customer_name}。{saved.demand} 联系/核实方式：{saved.contact}",
            ai_summary="公开信息来源的真实潜在客户，需人工核实并触达。",
        )
    )
    store.save_follow_up_task(
        FollowUpTask(
            id=str(uuid.uuid4()),
            lead_id=saved.id,
            title=saved.next_action,
            due_at=saved.next_followup_at,
            priority="normal",
        )
    )
    return saved


def main() -> int:
    saved = [save_prospect(item) for item in PROSPECTS]
    print(f"Saved {len(saved)} real public prospects:")
    for lead in saved:
        print(f"- {lead.customer_name} | {lead.industry} | {lead.contact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
