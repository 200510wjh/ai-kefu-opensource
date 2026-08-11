from __future__ import annotations

import uuid

from backend.internal_growth.content_factory import create_content_tasks
from backend.internal_growth.models import DailyWorkflowRun, FollowUpTask, PublishingRecord, now_iso
from backend.internal_growth.scoring import score_demand
from backend.internal_growth.store import InternalGrowthStore, store as default_store


def run_daily_growth_workflow(trigger: str = "manual", growth_store: InternalGrowthStore | None = None) -> DailyWorkflowRun:
    active_store = growth_store or default_store
    run = DailyWorkflowRun(id=str(uuid.uuid4()), status="running", trigger="schedule" if trigger == "schedule" else "manual")
    logs: list[str] = ["Workflow started: demand radar -> scoring -> content drafts -> human review queue."]
    try:
        demands = active_store.list_demands()
        run.demand_count = len(demands)
        opportunities = []
        for demand in demands:
            opportunity = active_store.get_opportunity_for_demand(demand.id) or active_store.save_opportunity(score_demand(demand))
            opportunities.append(opportunity)
        run.opportunity_count = len(opportunities)
        logs.append(f"Scored {run.opportunity_count} opportunities.")

        top = sorted(opportunities, key=lambda item: item.total_score, reverse=True)[:3]
        existing_task_keys = {(item.demand_id, item.platform) for item in active_store.list_content_tasks()}
        generated_count = 0
        publishing_count = 0
        for opportunity in top:
            demand = active_store.get_demand(opportunity.demand_id)
            if not demand:
                continue
            missing_platforms = [platform for platform in ["douyin", "xianyu", "wechat_moments"] if (demand.id, platform) not in existing_task_keys]
            if missing_platforms:
                tasks = create_content_tasks(demand, opportunity, missing_platforms)  # type: ignore[arg-type]
                active_store.save_content_tasks(tasks)
                generated_count += len(tasks)
            else:
                tasks = [item for item in active_store.list_content_tasks() if item.demand_id == demand.id]
            existing_records = {item.content_task_id for item in active_store.list_publishing_records()}
            for task in tasks:
                if task.id in existing_records:
                    continue
                active_store.save_publishing_record(
                    PublishingRecord(
                        id=str(uuid.uuid4()),
                        content_task_id=task.id,
                        platform=task.platform,
                        status="review",
                        notes="Created by daily workflow. Human confirmation required before publishing.",
                    )
                )
                publishing_count += 1

        run.generated_content_tasks = generated_count
        run.publishing_records_created = publishing_count
        logs.append(f"Generated {generated_count} content drafts and {publishing_count} publishing review records.")

        leads = [lead for lead in active_store.list_leads() if lead.stage not in {"won", "lost"} and lead.intent_level == "high"]
        existing_followup_keys = {(task.lead_id, task.title) for task in active_store.list_follow_up_tasks() if task.status == "open"}
        followup_count = 0
        for lead in leads:
            title = lead.next_action or "Follow up high-intent lead today"
            if (lead.id, title) in existing_followup_keys:
                continue
            active_store.save_follow_up_task(FollowUpTask(id=str(uuid.uuid4()), lead_id=lead.id, title=title, priority="high"))
            followup_count += 1
        run.followup_tasks_created = followup_count
        logs.append(f"Created {followup_count} high-intent follow-up tasks.")
        logs.append("Workflow stopped at human review. It does not auto-publish or auto-send messages.")
        run.status = "needs_human"
        run.needs_human_confirmation = True
    except Exception as exc:
        logs.append(f"Workflow failed: {exc}")
        run.status = "failed"
    run.logs = logs
    run.finished_at = now_iso()
    return active_store.save_workflow_run(run)

