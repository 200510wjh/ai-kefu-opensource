---
name: merchant-growth-saas-skill
description: Build, operate, debug, and extend a merchant growth SaaS that turns customer needs into AI customer-service analysis, leads, scripts, product images, short-video/storyboard plans, and delivery workflows. Use when the user asks about merchant AI growth SaaS, AI customer service, customer need API, Douyin miniapp or lead intake, WeCom/customer chat intake, in-product plugin marketplace, Remotion, HyperFrames, HeyGen, API2D, talking-head video editing skills, or packaging these workflows into a deployable SaaS skill.
---

# Merchant Growth SaaS Skill

## Core Positioning

Treat the product as a merchant conversion system, not a pure image/video toy.

Before making product claims, adding buttons, or marking work done, read `references/project-audit-memory.md` and apply its persistence, login, subscription, and real media generation checks.

Primary loop:

```text
customer need -> intake API -> lead/project/brief -> AI customer-service analysis -> scripts/storyboards -> media generation -> works library -> follow-up
```

Default business priority:

1. AI customer service and lead capture are the recurring paid product.
2. Product images, detail pages, and short videos are lead magnets and delivery assets.
3. Video tooling should be modular: use existing skills/plugins when possible, keep human confirmation before publishing or sending messages.

## Local Project Assumptions

Default workspace is the current Codex workspace. In this project it is the user's merchant-operations folder under `Documents`.

Expected app pieces:

- Frontend: React/Vite SaaS interface.
- Backend: FastAPI API under `backend/main.py`.
- Main local URL: `http://127.0.0.1:5173/`.
- Important backend endpoints:
  - `GET /api/health`
  - `POST /api/intake/customer-need`
  - `POST /api/reply-assistant`
  - `POST /api/scripts`
  - `POST /api/images/generate`
  - `GET /api/integrations/media-stack`
  - `GET /api/leads`

If the repository layout differs, inspect files first and adapt to the discovered codebase.

## Workflow

### 1. Clarify The Commercial Job

Before adding features, identify which job the user is trying to sell:

- Local merchant version: Douyin local traffic, appointments, store conversion.
- Ecommerce seller version: product image, detail page, short video, customer-service closing.
- Agency/developer version: open-source demo, private deployment, second development, template/API quota.

Prefer AI customer service plus lead CRM as the first sellable module. Do not lead with a full timeline editor unless explicitly requested.

### 2. Intake Customer Needs

Use the unified intake route for external demand sources:

```http
POST /api/intake/customer-need
```

It should create:

- `lead`
- `project`
- internal `brief`
- `scripts`
- `reply_analysis`
- `next_actions`

Read `references/api-contracts.md` when implementing or debugging intake payloads.

### 3. Build AI Customer Service As A Desk

AI customer service must do more than generate replies. It should show:

- customer stage
- intent summary
- lead score and hot/warm/cold temperature
- missing info
- risk flags
- next best action
- candidate replies
- lead capture suggestion
- follow-up cadence

Keep human approval before sending messages. Flag money, refund, complaint, account, verification-code, or private-data cases for manual review.

### 4. Wire Plugin And Skill Capabilities

Use the plugin marketplace as an operations surface, not a fake install button.

Recommended modules:

- AI customer-service closer: built in, always visible.
- Customer Need API: entry for external forms/webhooks.
- API2D/OpenAI-compatible image provider: product images and detail prompts.
- HyperFrames: HTML/GSAP showreel and render-plan templates.
- Remotion: server-side parameterized MP4 rendering.
- HeyGen: presenter/avatar videos when API keys exist.
- Fireflies or pasted notes: meeting-to-brief.
- Talking-head video editing skills: review pages, captions, and vertical MP4 delivery.
- GitHub/open-source deploy: acquisition and private deployment.

Read `references/plugin-runtime.md` when implementing status cards, environment checks, or enable/disable behavior.

### 5. Test Before Saying Done

Run focused tests:

```powershell
npm run build
python C:\Users\Administrator\.codex\skills\merchant-growth-saas-skill\scripts\check_stack.py --base-url http://127.0.0.1:8000
```

If the backend is not running, either start it according to the repo's existing scripts or use FastAPI `TestClient` for direct endpoint checks.

Validation targets:

- `/api/intake/customer-need` returns 200 and includes `lead`, `project`, `brief`, `scripts`, and `reply_analysis`.
- `/api/reply-assistant` returns service insight, not only text candidates.
- `/api/integrations/media-stack` reports installed/configured/missing dependencies clearly.
- Frontend build passes and relevant pages are clickable.

## Safety And Delivery Rules

- Never expose pasted API keys, server passwords, or tokens in summaries, docs, commits, or screenshots.
- Keep generated replies as drafts unless the user explicitly confirms sending.
- Keep platform publishing/uploading as a confirmation step.
- If adding external APIs, store keys in environment variables and document required variables without real values.
- Before public GitHub release, scan for secrets and replace private deployment details.

## Resources

- `references/api-contracts.md`: request/response examples for customer intake and AI customer service.
- `references/plugin-runtime.md`: module status model and integration checklist.
- `references/project-audit-memory.md`: persistent product audit memory and non-negotiable production checks.
- `scripts/check_stack.py`: local health check for the SaaS backend.
