from __future__ import annotations

from backend.internal_growth.analytics import build_weekly_report
from backend.internal_growth.content_factory import create_content_tasks
from backend.internal_growth.models import (
    AnalyticsReport,
    ContentPlatform,
    ContentTask,
    DemandSignal,
    Lead,
    OpportunityScore,
    SalesAnalysis,
    SalesAnalyzeRequest,
)
from backend.internal_growth.sales import analyze_sales_conversation
from backend.internal_growth.scoring import score_demand
from backend.internal_growth.store import InternalGrowthStore, store as default_store


class MarketAgent:
    """Finds and scores market demand signals."""

    def __init__(self, growth_store: InternalGrowthStore | None = None) -> None:
        self.store = growth_store or default_store

    def score(self, demand: DemandSignal) -> OpportunityScore:
        return self.store.save_opportunity(score_demand(demand))

    def top_directions(self, limit: int = 3) -> list[OpportunityScore]:
        opportunities = []
        for demand in self.store.list_demands():
            opportunities.append(self.store.get_opportunity_for_demand(demand.id) or self.score(demand))
        return sorted(opportunities, key=lambda item: item.total_score, reverse=True)[:limit]


class ContentAgent:
    """Turns a scored demand into platform-specific draft content."""

    def __init__(self, growth_store: InternalGrowthStore | None = None) -> None:
        self.store = growth_store or default_store

    def generate(self, demand: DemandSignal, opportunity: OpportunityScore | None, platforms: list[ContentPlatform]) -> list[ContentTask]:
        tasks = create_content_tasks(demand, opportunity, platforms)
        return self.store.save_content_tasks(tasks)


class SalesAgent:
    """Analyzes customer conversations and suggests next sales actions."""

    def analyze(self, payload: SalesAnalyzeRequest) -> SalesAnalysis:
        return analyze_sales_conversation(payload)


class AnalysisAgent:
    """Reviews channel/content/lead performance and proposes the next loop."""

    def weekly_report(self, leads: list[Lead], content_tasks: list[ContentTask]) -> AnalyticsReport:
        return build_weekly_report(leads, content_tasks)

