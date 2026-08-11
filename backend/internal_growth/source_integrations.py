from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from backend.internal_growth.models import (
    ProspectExternalResult,
    ProspectExternalSearchResponse,
    ProspectIntegrationProvider,
    ProspectIntegrationStatus,
    ProspectSearch,
)


def normalized_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def list_source_integrations() -> list[ProspectIntegrationStatus]:
    searxng_url = normalized_base_url(os.getenv("INTERNAL_GROWTH_SEARXNG_URL", ""))
    firecrawl_url = normalized_base_url(os.getenv("INTERNAL_GROWTH_FIRECRAWL_URL", ""))
    firecrawl_key = os.getenv("INTERNAL_GROWTH_FIRECRAWL_API_KEY", "").strip()
    return [
        ProspectIntegrationStatus(
            provider="searxng",
            name="SearXNG",
            license="AGPL-3.0",
            repository_url="https://github.com/searxng/searxng",
            configured=bool(searxng_url),
            mode="search_api",
            status="ready" if searxng_url else "needs_config",
            env_keys=["INTERNAL_GROWTH_SEARXNG_URL"],
            best_for="把百度/必应/通用网页搜索聚合成一个可控的公开搜索入口。",
            guardrail="只读取公开搜索结果标题、链接和摘要；不抓私信、不绕过登录或验证码。",
            next_action="部署或填写一个 SearXNG 实例地址，例如 http://localhost:8080。",
        ),
        ProspectIntegrationStatus(
            provider="firecrawl",
            name="Firecrawl",
            license="AGPL-3.0",
            repository_url="https://github.com/mendableai/firecrawl",
            configured=bool(firecrawl_url and firecrawl_key),
            mode="scrape_api",
            status="ready" if firecrawl_url and firecrawl_key else "needs_config",
            env_keys=["INTERNAL_GROWTH_FIRECRAWL_URL", "INTERNAL_GROWTH_FIRECRAWL_API_KEY"],
            best_for="把已确认的官网或公开页面抽取成 Markdown，再交给 Demand Radar 分析。",
            guardrail="只抽取你有权限访问的公开页面；不用于平台登录页、私密内容或规避风控。",
            next_action="下一阶段接入页面抽取，先用于官网/博客/企业介绍页。",
        ),
        ProspectIntegrationStatus(
            provider="crawlee",
            name="Crawlee",
            license="Apache-2.0",
            repository_url="https://github.com/apify/crawlee",
            configured=False,
            mode="crawler_framework",
            status="planned",
            env_keys=[],
            best_for="后续做自建合规爬虫任务队列、速率限制、去重和失败重试。",
            guardrail="只跑白名单站点和授权数据源；不做平台账号自动化抓取。",
            next_action="等搜索结果闭环稳定后，再封装 Crawlee Worker。",
        ),
    ]


def get_integration(provider: ProspectIntegrationProvider) -> ProspectIntegrationStatus:
    return next(item for item in list_source_integrations() if item.provider == provider)


def run_searxng_search(search: ProspectSearch, limit: int = 8) -> ProspectExternalSearchResponse:
    integration = get_integration("searxng")
    base_url = normalized_base_url(os.getenv("INTERNAL_GROWTH_SEARXNG_URL", ""))
    if not base_url:
        return ProspectExternalSearchResponse(
            search_id=search.id,
            provider="searxng",
            configured=False,
            query=search.query,
            message="未配置 INTERNAL_GROWTH_SEARXNG_URL；当前只能使用页面里的平台搜索链接人工采集。",
        )

    query = urllib.parse.urlencode({"q": search.query, "format": "json", "language": "zh-CN"})
    request = urllib.request.Request(
        f"{base_url}/search?{query}",
        headers={"Accept": "application/json", "User-Agent": "InternalGrowthOS/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return ProspectExternalSearchResponse(
            search_id=search.id,
            provider="searxng",
            configured=integration.configured,
            query=search.query,
            message=f"SearXNG 请求失败：{exc}",
        )

    results: list[ProspectExternalResult] = []
    for item in payload.get("results", [])[:limit]:
        results.append(
            ProspectExternalResult(
                search_id=search.id,
                provider="searxng",
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip(),
                snippet=str(item.get("content") or item.get("snippet") or "").strip(),
                engine=str(item.get("engine") or item.get("engines") or "").strip(),
                score=float(item.get("score") or 0),
            )
        )
    return ProspectExternalSearchResponse(
        search_id=search.id,
        provider="searxng",
        configured=True,
        query=search.query,
        results=[item for item in results if item.title or item.url],
        message="已从 SearXNG 读取公开搜索结果，请人工核实后再导入候选客户。",
    )


def run_external_search(search: ProspectSearch, provider: ProspectIntegrationProvider) -> ProspectExternalSearchResponse:
    if provider == "searxng":
        return run_searxng_search(search)
    integration = get_integration(provider)
    return ProspectExternalSearchResponse(
        search_id=search.id,
        provider=provider,
        configured=integration.configured,
        query=search.query,
        message=f"{integration.name} 已列入架构，但当前版本只启用 SearXNG 搜索；{integration.next_action}",
    )
