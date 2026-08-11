# Internal Growth OS

Internal Growth OS is the internal acquisition operating system for demand discovery, opportunity scoring, content production, publishing review, lead follow-up, sales analysis, and growth retrospectives.

It is an internal tool, not the customer-facing AI customer service product.

## Run

Frontend:

```bash
npm run dev
```

Backend:

```bash
npm run api
```

Open:

```text
http://localhost:5173/internal-growth
```

## Data

Default local storage:

```text
data/internal_growth
```

Override it:

```bash
set INTERNAL_GROWTH_DATA_DIR=D:\internal-growth-data
```

The store boundary is centralized in `backend/internal_growth/store.py`, so PostgreSQL can replace the JSON store without changing the UI or API contracts.

PostgreSQL schema:

```text
backend/internal_growth/schema.sql
```

## Agents

Agent boundaries live in:

```text
backend/internal_growth/agents.py
```

- `MarketAgent`: demand scoring and top directions
- `ContentAgent`: platform content drafts
- `SalesAgent`: chat analysis and next sales action
- `AnalysisAgent`: weekly growth retrospectives

## Daily Workflow

Manual API:

```bash
curl -X POST http://localhost:8000/api/internal-growth/workflows/daily/run
```

Command-line runner for Windows Task Scheduler or cron:

```bash
python scripts/internal_growth_daily_workflow.py
```

Douyin project-scan content pack:

```bash
npm run growth:douyin-daily
```

This scans local project assets such as `峰会内容`, `ai-solo-founder-douyin`, `backend/internal_growth`, `douyin-miniapp`, and desktop agent work, then creates a daily Douyin script, storyboard, cover copy, caption, render plan, and publishing review record under `output/douyin-daily/YYYYMMDD`.

Optional in-process scheduler:

```bash
set INTERNAL_GROWTH_ENABLE_DAILY_SCHEDULE=true
set INTERNAL_GROWTH_DAILY_TIME=08:00
set INTERNAL_GROWTH_TIMEZONE=Asia/Shanghai
npm run api
```

The workflow does:

```text
Demand Radar
-> Opportunity Scoring
-> Content Tasks
-> Publishing Review Queue
-> High-intent Follow-up Tasks
-> Human Confirmation
```

It does not auto-publish content or auto-send customer messages. Publishing should stop at official authorization or human confirmation.

## Verification

```bash
python -m compileall backend\internal_growth backend\main.py
python tests\test_internal_growth.py
npm run build
```
