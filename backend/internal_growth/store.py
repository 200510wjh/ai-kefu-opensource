from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from backend.internal_growth.models import (
    AnalyticsReport,
    ContentTask,
    CustomerInteraction,
    DailyWorkflowRun,
    DemandSignal,
    FollowUpTask,
    Lead,
    OpportunityScore,
    ProspectCandidate,
    ProspectSearch,
    PublishingRecord,
    SalesAnalysis,
    ToolRunRecord,
)


T = TypeVar("T", bound=BaseModel)


class InternalGrowthStore:
    def __init__(self, root: Path | None = None) -> None:
        data_root = root or Path(os.getenv("INTERNAL_GROWTH_DATA_DIR", "data/internal_growth"))
        data_root.mkdir(parents=True, exist_ok=True)
        self.root = data_root
        self.demands_path = data_root / "demands.json"
        self.opportunities_path = data_root / "opportunities.json"
        self.content_tasks_path = data_root / "content_tasks.json"
        self.publishing_records_path = data_root / "publishing_records.json"
        self.leads_path = data_root / "leads.json"
        self.interactions_path = data_root / "interactions.json"
        self.follow_up_tasks_path = data_root / "follow_up_tasks.json"
        self.sales_analyses_path = data_root / "sales_analyses.json"
        self.analytics_reports_path = data_root / "analytics_reports.json"
        self.workflow_runs_path = data_root / "workflow_runs.json"
        self.tool_runs_path = data_root / "tool_runs.json"
        self.prospect_searches_path = data_root / "prospect_searches.json"
        self.prospect_candidates_path = data_root / "prospect_candidates.json"

    def _load(self, path: Path, model: type[T]) -> list[T]:
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8-sig") or "[]")
        return [model.model_validate(item) for item in raw]

    def _save(self, path: Path, items: list[BaseModel]) -> None:
        path.write_text(
            json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_demands(self) -> list[DemandSignal]:
        return sorted(self._load(self.demands_path, DemandSignal), key=lambda item: item.created_at, reverse=True)

    def save_demand(self, demand: DemandSignal) -> DemandSignal:
        items = [item for item in self.list_demands() if item.id != demand.id]
        items.append(demand)
        self._save(self.demands_path, items)
        return demand

    def get_demand(self, demand_id: str) -> DemandSignal | None:
        return next((item for item in self.list_demands() if item.id == demand_id), None)

    def list_opportunities(self) -> list[OpportunityScore]:
        return sorted(self._load(self.opportunities_path, OpportunityScore), key=lambda item: item.created_at, reverse=True)

    def save_opportunity(self, opportunity: OpportunityScore) -> OpportunityScore:
        items = [item for item in self.list_opportunities() if item.id != opportunity.id and item.demand_id != opportunity.demand_id]
        items.append(opportunity)
        self._save(self.opportunities_path, items)
        return opportunity

    def get_opportunity_for_demand(self, demand_id: str) -> OpportunityScore | None:
        return next((item for item in self.list_opportunities() if item.demand_id == demand_id), None)

    def list_content_tasks(self) -> list[ContentTask]:
        return sorted(self._load(self.content_tasks_path, ContentTask), key=lambda item: item.created_at, reverse=True)

    def save_content_tasks(self, tasks: list[ContentTask]) -> list[ContentTask]:
        current = self.list_content_tasks()
        incoming_ids = {item.id for item in tasks}
        merged = [item for item in current if item.id not in incoming_ids]
        merged.extend(tasks)
        self._save(self.content_tasks_path, merged)
        return tasks

    def get_content_task(self, task_id: str) -> ContentTask | None:
        return next((item for item in self.list_content_tasks() if item.id == task_id), None)

    def save_content_task(self, task: ContentTask) -> ContentTask:
        self.save_content_tasks([task])
        return task

    def list_publishing_records(self) -> list[PublishingRecord]:
        return sorted(self._load(self.publishing_records_path, PublishingRecord), key=lambda item: item.updated_at, reverse=True)

    def save_publishing_record(self, record: PublishingRecord) -> PublishingRecord:
        items = [item for item in self.list_publishing_records() if item.id != record.id]
        items.append(record)
        self._save(self.publishing_records_path, items)
        return record

    def get_publishing_record(self, record_id: str) -> PublishingRecord | None:
        return next((item for item in self.list_publishing_records() if item.id == record_id), None)

    def list_leads(self) -> list[Lead]:
        return sorted(self._load(self.leads_path, Lead), key=lambda item: item.updated_at, reverse=True)

    def save_lead(self, lead: Lead) -> Lead:
        items = [item for item in self.list_leads() if item.id != lead.id]
        items.append(lead)
        self._save(self.leads_path, items)
        return lead

    def get_lead(self, lead_id: str) -> Lead | None:
        return next((item for item in self.list_leads() if item.id == lead_id), None)

    def list_prospect_searches(self) -> list[ProspectSearch]:
        return sorted(self._load(self.prospect_searches_path, ProspectSearch), key=lambda item: item.created_at, reverse=True)

    def save_prospect_search(self, search: ProspectSearch) -> ProspectSearch:
        items = [item for item in self.list_prospect_searches() if item.id != search.id]
        items.append(search)
        self._save(self.prospect_searches_path, items)
        return search

    def get_prospect_search(self, search_id: str) -> ProspectSearch | None:
        return next((item for item in self.list_prospect_searches() if item.id == search_id), None)

    def list_prospect_candidates(self) -> list[ProspectCandidate]:
        return sorted(self._load(self.prospect_candidates_path, ProspectCandidate), key=lambda item: item.created_at, reverse=True)

    def save_prospect_candidate(self, candidate: ProspectCandidate) -> ProspectCandidate:
        items = [item for item in self.list_prospect_candidates() if item.id != candidate.id]
        items.append(candidate)
        self._save(self.prospect_candidates_path, items)
        return candidate

    def get_prospect_candidate(self, candidate_id: str) -> ProspectCandidate | None:
        return next((item for item in self.list_prospect_candidates() if item.id == candidate_id), None)

    def list_interactions(self, lead_id: str | None = None) -> list[CustomerInteraction]:
        items = sorted(self._load(self.interactions_path, CustomerInteraction), key=lambda item: item.created_at, reverse=True)
        return [item for item in items if item.lead_id == lead_id] if lead_id else items

    def save_interaction(self, interaction: CustomerInteraction) -> CustomerInteraction:
        items = [item for item in self.list_interactions() if item.id != interaction.id]
        items.append(interaction)
        self._save(self.interactions_path, items)
        return interaction

    def list_follow_up_tasks(self, lead_id: str | None = None) -> list[FollowUpTask]:
        items = sorted(self._load(self.follow_up_tasks_path, FollowUpTask), key=lambda item: item.created_at, reverse=True)
        return [item for item in items if item.lead_id == lead_id] if lead_id else items

    def save_follow_up_task(self, task: FollowUpTask) -> FollowUpTask:
        items = [item for item in self.list_follow_up_tasks() if item.id != task.id]
        items.append(task)
        self._save(self.follow_up_tasks_path, items)
        return task

    def list_sales_analyses(self, lead_id: str | None = None) -> list[SalesAnalysis]:
        items = sorted(self._load(self.sales_analyses_path, SalesAnalysis), key=lambda item: item.created_at, reverse=True)
        return [item for item in items if item.lead_id == lead_id] if lead_id else items

    def save_sales_analysis(self, analysis: SalesAnalysis) -> SalesAnalysis:
        items = [item for item in self.list_sales_analyses() if item.id != analysis.id]
        items.append(analysis)
        self._save(self.sales_analyses_path, items)
        return analysis

    def list_analytics_reports(self) -> list[AnalyticsReport]:
        return sorted(self._load(self.analytics_reports_path, AnalyticsReport), key=lambda item: item.created_at, reverse=True)

    def save_analytics_report(self, report: AnalyticsReport) -> AnalyticsReport:
        items = [item for item in self.list_analytics_reports() if item.id != report.id]
        items.append(report)
        self._save(self.analytics_reports_path, items)
        return report

    def list_workflow_runs(self) -> list[DailyWorkflowRun]:
        return sorted(self._load(self.workflow_runs_path, DailyWorkflowRun), key=lambda item: item.started_at, reverse=True)

    def save_workflow_run(self, run: DailyWorkflowRun) -> DailyWorkflowRun:
        items = [item for item in self.list_workflow_runs() if item.id != run.id]
        items.append(run)
        self._save(self.workflow_runs_path, items)
        return run

    def list_tool_runs(self, task_id: str | None = None) -> list[ToolRunRecord]:
        items = sorted(self._load(self.tool_runs_path, ToolRunRecord), key=lambda item: item.created_at, reverse=True)
        return [item for item in items if item.task_id == task_id] if task_id else items

    def save_tool_run(self, record: ToolRunRecord) -> ToolRunRecord:
        items = [item for item in self.list_tool_runs() if item.id != record.id]
        items.append(record)
        self._save(self.tool_runs_path, items)
        return record


store = InternalGrowthStore()
