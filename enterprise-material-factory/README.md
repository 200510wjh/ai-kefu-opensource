# Enterprise Material Factory

An independent V1 scaffold for an enterprise product-material factory: product in, multi-platform assets out.

## V1 Scope

- Enterprise login and tenant isolation
- Product management and image upload
- Asset history and version records
- Main image, detail page, copy, and short-video generation
- 15s, 30s, and 60s short-video storyboards with subtitle, voiceover, and BGM interface flags
- Unified `AIEngine` for all model providers
- `Workflow` module for all automation
- Export/statistics-ready API surface
- React + TypeScript professional UI shell with zh-CN/en-US toggle
- FastAPI backend, PostgreSQL/Redis/MinIO/Celery-ready infrastructure

## Run Locally

Backend:

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Docker stack:

```powershell
docker compose up --build
```

Demo login:

- Tenant: `demo`
- Email: `owner@example.com`
- Password: `demo123`

## Architecture Rules

- Business modules never call model providers directly.
- AI work enters through `backend/app/ai_engine.py`.
- Automation enters through `backend/app/workflow.py`.
- Object persistence enters through `backend/app/storage.py`.
- The project is isolated from the parent repository and can be moved into its own repo.
