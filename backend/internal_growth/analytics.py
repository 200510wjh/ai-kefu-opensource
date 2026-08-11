from __future__ import annotations

import uuid
from collections import Counter

from backend.internal_growth.models import AnalyticsReport, ContentTask, Lead


def build_weekly_report(leads: list[Lead], content_tasks: list[ContentTask]) -> AnalyticsReport:
    platform_counts = Counter(lead.source_platform or "manual" for lead in leads)
    content_counts = Counter(task.platform for task in content_tasks)
    won = [lead for lead in leads if lead.stage == "won"]
    lost = [lead for lead in leads if lead.stage == "lost"]
    high = [lead for lead in leads if lead.intent_level == "high"]
    best_platforms = [f"{platform}: {count} leads" for platform, count in platform_counts.most_common(3)]
    best_content = [f"{platform}: {count} tasks" for platform, count in content_counts.most_common(3)]
    stop_list = []
    if lost and len(lost) >= len(won) + 2:
        stop_list.append("本周流失线索偏多，暂停扩大投放，先复盘话术和报价。")
    if not leads:
        stop_list.append("暂无线索数据，先不要判断渠道优劣。")
    next_actions = [
        "每天至少录入3条需求信号，保留来源和客户原话。",
        "高意向线索当天完成一次人工跟进。",
        "每条已发布内容回填浏览、收藏、咨询和成交数据。",
    ]
    summary = f"本周内容任务{len(content_tasks)}个，线索{len(leads)}条，高意向{len(high)}条，成交{len(won)}条，流失{len(lost)}条。"
    return AnalyticsReport(
        id=str(uuid.uuid4()),
        summary=summary,
        best_platforms=best_platforms,
        best_content=best_content,
        best_services=["需求诊断", "内容测试", "CRM跟进"] if leads else [],
        stop_list=stop_list,
        next_actions=next_actions,
    )
