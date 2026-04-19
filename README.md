Google Drive: https://drive.google.com/drive/folders/12f9w-at7ATn9lE_qTII1d3ehcfLkXlkU?usp=drive_link

# Supply Chainer — Agnes AI Supply Chain Manager
CPG Ingredient Consolidation & Substitution Intelligence

## Overview
Agnes is an AI-native supply chain manager for CPG (Consumer Packaged Goods) companies. It:
- Loads ingredient BOMs from a SQLite database (multiple companies and products)
- Analyses cross-company raw material demand to identify consolidation opportunities
- Uses LLM-based reasoning to detect functionally equivalent ingredient substitutions
- Validates substitution candidates against food regulations (EU 1169/2011, Codex HACCP)
- Generates consolidated sourcing proposals with evidence trails and tradeoff analysis
- Scores and ranks suppliers based on consolidation coverage and trust
- Live agent messaging via SSE
- Trust/reputation scoring that evolves with each cascade


## How the compliance check works

The compliance check evaluates raw materials of a finished product by combining internal database data with verified supplier website evidence.

### Step-by-step logic

1. **Load raw materials from BOM**
   - The system retrieves all raw materials used in a finished product via the BOM structure.

2. **Identify suppliers**
   - For each raw material, all linked suppliers are loaded from the database.

3. **Normalize ingredient names**
   - Raw material SKUs are cleaned and converted into readable ingredient names.
   - This enables consistent matching against external data sources.

4. **Validate suppliers against allowlist**
   - Each supplier is checked against a predefined allowlist.
   - If a match is found, the supplier is linked to a known official domain and URL.

5. **Fetch supplier website data**
   - Only pre-approved supplier URLs are accessed.
   - HTML content is cleaned and converted into searchable text.

6. **Build search terms**
   - The system generates search terms based on:
     - full ingredient name
     - individual meaningful tokens from the name

7. **Extract evidence from supplier pages**
   - The system scans the page text for:
     - ingredient name matches
     - predefined evidence keywords (allergens, quality indicators, composition terms)
   - Relevant text snippets are extracted around matches for context.

8. **Match with regulations**
   - Check is made against **EU_FIC_1169_2011** (Regulation (EU) No 1169/2011 — food information to consumers) and **CODEX_GPFH_HACCP** (Codex General Principles of Food Hygiene)

9. **Assign compliance status**
   - The final status is determined based on:
     - supplier allowlist presence
     - existence and strength of external evidence
     - detected regulatory relevance signals

## How the Quality check works

- Quality grade is extracted from supplier pages and mapped to a score:
  - Pharmaceutical grade / USP / EP / BP → 1.0
  - GMP → 0.9
  - Food grade / Kosher / Halal / Organic → 0.7
  - Feed grade → 0.4
  - Industrial grade → 0.2
- Quality metrics extracted where available: identity confidence, assay potency, heavy metals, pesticide residues, microbial limits, moisture content, residual solvents

## How the Cost check works
- Cost comparison done if any data on the websites of the list of suppliers directly provided
- *List of suppliers given by us*


## Batching

- Reduces total supplier count via a greedy set-cover algorithm
- Assigns all BOM components to the minimum number of suppliers
- Ensures better supplier leverage, improved quality consistency, and reduced costs


## API Endpoints

### Sourcing
- `GET /api/sourcing/boms` — List all BOMs
- `GET /api/sourcing/bom/{sku}` — Get BOM for a specific finished good
- `POST /api/sourcing/batch` — Run batching (supplier consolidation) on a BOM
- `GET /api/sourcing/analyze/{finished_good_id}` — Full sourcing analysis for a product

### Compliance
- `GET /api/compliance/{product_id}` — Run compliance check for a product

### Catalogue & Data
- `GET /api/catalogue` — Product catalogue
- `GET /api/catalogue/{product_id}` — Single product
- `GET /api/finished-goods` — All finished goods
- `GET /api/companies` — All CPG companies
- `GET /api/boms` — All BOMs (optionally filter by company)
- `GET /api/boms/{product_id}` — BOM for a specific product
- `GET /api/raw-materials` — Raw materials with supplier mappings
- `GET /api/suppliers` — Suppliers list

### Cascade & Proposals
- `POST /registry/trigger` — Start a cascade
- `GET /api/progress` — Cascade progress
- `GET /api/report` — Latest report
- `GET /api/stream` — SSE live messages
- `GET /api/substitutions` — Latest substitution graph
- `GET /api/proposal` — Latest consolidated sourcing proposal
- `GET /api/demand` — Cross-company ingredient demand aggregation
- `GET /api/evidence` — Evidence store
- `GET /api/evidence/{evidence_id}` — Single evidence record
- `GET /api/cascades` — Past cascade summaries
- `GET /api/cascades/{report_id}` — Report by ID

### Trust & Reputation
- `POST /api/trust/submit` — Submit trust signal
- `GET /api/trust/contextual/{agent_id}` — Contextual trust for agent
- `GET /api/reputation/summary` — Reputation summary
- `GET /api/reputation/scores` — All reputation scores
- `GET /api/reputation/agent/{agent_id}` — Agent reputation

### Registry
- `POST /registry/register` — Register agent
- `GET /registry/search` — Search registry
- `GET /registry/list` — List agents
- `GET /registry/agent/{agent_id}` — Agent details
- `GET /registry/health` — Health check
- `POST /registry/deregister/{agent_id}` — Deregister agent

## Database Schema
The SQLite database at `data/db.sqlite` contains:
- **Company** — CPG manufacturing companies (61)
- **Product** — Finished goods (149) and raw materials (876)
- **BOM / BOM_Component** — Bill of materials linking finished goods to raw materials (149 BOMs)
- **Supplier / Supplier_Product** — Supplier catalogue (40 suppliers, 1,633 supplier–product links)

## Repository Structure
- `backend/` — FastAPI app, services, agents, schemas
- `frontend/` — React (Vite) UI
- `run.py` — Dev runner for backend
- `notebook.ipynb` — Interactive demo of DB queries and batching

## Requirements
- Python 3.14+
- Node.js 20+ (for Vite)
- Docker (optional, for containerised deploy)

## Environment Variables
Create a `.env` in the repo root or set env vars in your shell:

Required for AI features:
- `OPENAI_API_KEY` — OpenAI API key
- `SQLITE_DB_PATH` — Path to SQLite database (default: `data/db.sqlite`)

Optional:
- `SERVE_FRONTEND=true` — serve built frontend from backend (for Docker/Cloud Run)
- `VITE_API_BASE_URL` — frontend API base (only needed if decoupled)
- `AGENT_PROTOCOL_SECRET` — HMAC signing for agent protocol
- `ENABLE_EXTERNAL_AGENT_TRANSPORT=true` — send protocol messages over HTTP
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

## Notes
- The frontend can run decoupled or served from the backend (Docker/Cloud Run).
- `0.0.0.0` is a bind address — use `http://localhost:PORT` in your browser.
