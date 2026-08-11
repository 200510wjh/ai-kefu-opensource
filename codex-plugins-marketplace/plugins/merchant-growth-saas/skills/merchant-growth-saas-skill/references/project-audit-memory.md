# Project Audit Memory

Use this as persistent project memory for merchant-growth-saas work.

## Non-negotiable Product Rules

1. Do not ship a copywriting-only product. The sellable product needs real images, real videos, AI customer service, leads, and subscriptions.
2. A clickable button is not complete unless a real API runs, state changes, errors are shown, and data is persisted.
3. Page data is not real if it disappears after refresh, backend restart, or switching browsers.
4. Login cannot be fake. It needs accounts, merchants, sessions/JWT, permissions, and admin visibility.
5. Subscription cannot be a static pricing card. It needs orders, plans, quotas, expiration, usage records, and admin management.
6. Real media generation means actual image files and actual MP4 files, not only prompts, storyboard JSON, or demo progress.
7. Customers should use the SaaS web app or Douyin miniapp. The Codex plugin is only for developer/operator workflow.
8. Every delivery must include: files changed, how to test each feature, what is not covered, what is fake/demo/static, and what data disappears after refresh or backend restart.
9. Any UI that says connected, logged in, subscribed, generated, uploaded, published, or paid must be backed by real backend state that the admin can inspect.
10. For merchant SaaS, the admin owner must be able to see merchant accounts, logins, stores, subscriptions, usage, leads, jobs, artifacts, failures, and costs.

## Known Current Gaps

- Backend uses in-memory dictionaries for `projects`, `assets`, `leads`, and `tasks`; data is lost on backend restart.
- There is no production database yet.
- There is no real login, merchant account, team member, or admin auth.
- Subscription plans are static demo data.
- `/api/render` simulates progress and writes JSON; it does not generate MP4.
- Image generation falls back to prompt mode when provider keys are missing or fail.
- The in-app plugin marketplace is a status/explanation surface, not a real install/enable runtime.
- Douyin miniapp lead submission falls back to local storage when backend fails; this does not mean the backend received the lead.
- `product-kit/index.html` is a static sales/demo page. Its nav links work, but it does not submit leads, create accounts, collect payments, or persist data.
- `videocut-workbench/index.html` is a static task-prep workbench. Its copy/download buttons work, but it does not upload files, run FFmpeg, call transcription APIs, create review pages, or export MP4.
- `/api/ecommerce/daily-report` currently reads `data/ecommerce_daily_sample.json` and returns `source="sample"`; it is not connected to real merchant stores yet.
- `mcp-cn-commerce` is installed separately, but real platform credentials and actual API data flow are not wired into this app.
- Codex skills/plugins help the operator; they are not customer-facing SaaS features until wrapped by backend jobs and UI.

## Required Production Backend

Add a database on Aliyun or another managed provider. Prefer PostgreSQL or MySQL.

Minimum tables:

- users
- merchants
- merchant_members
- merchant_store_connections
- projects
- assets
- leads
- conversations
- messages
- generation_jobs
- listing_drafts
- daily_reports
- artifacts
- subscriptions
- orders
- usage_records
- api_keys
- plugin_configs
- audit_logs
- admin_events

Admin must be able to see every merchant, login account, subscription, usage record, lead, conversation, generation job, cost, failure, and artifact.

## Testing Checklist For Every Feature

For each button/page/API, verify:

- The button calls a real API or clearly says it is a demo.
- The API has success and failure behavior.
- Data survives browser refresh.
- Data survives backend restart.
- Data belongs to the correct merchant.
- Login/session is required where needed.
- Subscription/quota is enforced where needed.
- Image output is a real file when claiming image generation.
- Video output is a real MP4 when claiming video generation.
- Admin can see the resulting records.

## Next Build Priority

1. Database and login.
2. Merchant workspace and admin backend.
3. Persistent leads, projects, jobs, and artifacts.
4. Real image generation with object storage.
5. Real video generation with Remotion/HyperFrames worker.
6. AI customer-service knowledge base per merchant.
7. Douyin miniapp login, subscription, and quota.
