# Supply Chainer — Agnes AI Supply Chain Manager
CPG Ingredient Consolidation & Substitution Intelligence

## Overview
Agnes is an AI-native supply chain manager for CPG (Consumer Packaged Goods) companies. It:
- Loads ingredient BOMs from a SQLite database (multiple companies and products)
- Analyses cross-company raw material demand to identify consolidation opportunities
- Uses LLM-based reasoning to detect functionally equivalent ingredient substitutions
- Validates all substitution candidates against EU food regulations (EU 1333/2008, EU 1169/2011, EU 834/2007, EU 1829/2003, EU 1907/2006)
- Generates consolidated sourcing proposals with evidence trails and tradeoff analysis
- Scores and ranks suppliers based on consolidation coverage and trust
- Live agent messaging via SSE
- Trust/reputation scoring that evolves with each cascade

## New API Endpoints
- `GET /api/companies` — List all CPG companies from the database
- `GET /api/boms` — List all BOMs (optionally filter by company_id)
- `GET /api/boms/{product_id}` — Get BOM for a specific finished good
- `GET /api/raw-materials` — List all raw materials with supplier mappings
- `GET /api/substitutions` — Latest substitution graph from most recent cascade
- `GET /api/proposal` — Latest consolidated sourcing proposal
- `GET /api/demand` — Cross-company ingredient demand aggregation

## Database Schema
The SQLite database at `data/db.sqlite` contains:
- **Company** — CPG manufacturing companies
- **Product** — Finished goods and raw materials (with type enum)
- **BOM / BOM_Component** — Bill of materials linking finished goods to raw materials
- **Supplier / Supplier_Product** — Supplier catalogue and product availability mappings

## Legacy Features (kept for backwards compatibility)

Public URL (Cloud Run):
- https://supply-chainer-379894741496.europe-west1.run.app

## Repository Structure
- `backend/` — FastAPI app, services, agents, schemas
- `frontend/` — React (Vite) UI
- `run.py` — dev runner for backend (and optional UI notes)

## Requirements
- Python 3.11+ (3.12 OK)
- Node.js 20+ (for Vite)
- Docker (optional, for containerized deploy)

## Environment Variables
Create a `.env` in the repo root or set env vars in your shell:

Required for AI features:
- `OPENAI_API_KEY` — OpenAI API key
- `SQLITE_DB_PATH` — Path to SQLite database (default: `data/db.sqlite`)

Optional:
- `SERVE_FRONTEND=true` — serve built frontend from backend (for Docker/Cloud Run)
- `VITE_API_BASE_URL` — frontend API base (only needed if decoupled)
- `AGENT_PROTOCOL_SECRET` — HMAC signing for agent protocol (optional)
- `ENABLE_EXTERNAL_AGENT_TRANSPORT=true` — send protocol messages over HTTP (optional)
- `ENABLE_EXTERNAL_ENRICHMENT=true` — enrich ingredient data from OpenFoodFacts/ECHA (default: true)

## Local Development (Backend + Frontend)

### 1) Backend (FastAPI)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r backend/requirements.txt
python run.py
```

Backend will run at `http://localhost:8000`.

### 2) Frontend (React)
```bash
cd frontend
npm install
npm run dev
```

Frontend will run at `http://localhost:5173`.

If you want the frontend to call a different backend:
```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Docker (Single Container)

Build and run:
```bash
docker build -t supply-chainer .
docker run --rm -e PORT=8080 -e SERVE_FRONTEND=true -e OPENAI_API_KEY=YOUR_KEY -p 8080:8080 supply-chainer
```

Open:
- `http://localhost:8080/` (frontend)
- `http://localhost:8080/docs` (API)

## Cloud Run (Single Container)

Enable APIs:
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

Build & push:
```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/supply-chainer
```

Deploy:
```bash
gcloud run deploy supply-chainer \
  --image gcr.io/PROJECT_ID/supply-chainer \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars SERVE_FRONTEND=true,OPENAI_API_KEY=YOUR_KEY
```

## Key API Endpoints
- `POST /registry/trigger` — start a cascade
- `GET /api/progress` — cascade progress
- `GET /api/report` — latest report
- `GET /api/stream` — SSE live messages
- `GET /api/catalogue` — product catalogue
- `GET /api/suppliers` — suppliers list
- `GET /api/cascades` — past cascade summaries
- `GET /api/cascades/{report_id}` — report by id

## Notes
- The frontend can run decoupled or served from the backend (Docker/Cloud Run).
- `0.0.0.0` is a bind address — use `http://localhost:PORT` in your browser.
