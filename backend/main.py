"""
FastAPI application — Agnes AI Supply Chain Manager.

Endpoints:
  POST   /registry/register           → Register an agent
  GET    /registry/search             → Discover agents
  GET    /registry/list               → List all agents
  GET    /registry/agent/{agent_id}   → Get single agent
  DELETE /registry/deregister/{id}    → Remove agent
  POST   /registry/log                → Log a message
  GET    /registry/logs               → Get all messages
  POST   /registry/trigger            → Kick off Agnes cascade
  POST   /registry/disrupt/{agent_id} → Simulate disruption
  GET    /api/stream                  → SSE live message feed
  GET    /api/report                  → Get latest report
  GET    /api/progress                → Get cascade progress
  GET    /api/companies               → List all companies from DB
  GET    /api/boms                    → List all BOMs (optionally filtered by company)
  GET    /api/boms/{product_id}       → Get BOM for a specific finished good
  GET    /api/raw-materials           → List all raw materials with supplier mappings
  GET    /api/substitutions           → Latest substitution graph
  GET    /api/proposal                → Latest consolidation proposal
  GET    /api/demand                  → Cross-company ingredient demand aggregation
  Backend serves API only unless SERVE_FRONTEND=true
"""

from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.controllers.registry_controller import router as registry_router
from backend.controllers.pubsub_controller import router as pubsub_router
from backend.controllers.reputation_controller import router as reputation_router
from backend.controllers.stream_controller import router as stream_router
from backend.controllers.catalogue_controller import router as catalogue_router
from backend.controllers.policy_controller import router as policy_router
from backend.controllers.escalation_controller import router as escalation_router
from backend.controllers.agent_protocol_controller import router as agent_protocol_router
from backend.controllers.cascade_history_controller import router as cascade_history_router
from backend.controllers.mcp_controller import router as mcp_router
from backend.controllers.a2a_controller import router as a2a_router
from backend.controllers.compliance_controller import router as compliance_router

app = FastAPI(title="Agnes — AI Supply Chain Manager", version="2.0.0")


@app.on_event("startup")
async def _startup() -> None:
    from backend.services.db_service import ensure_price_cache_table
    ensure_price_cache_table()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(registry_router)
app.include_router(catalogue_router)
app.include_router(policy_router)
app.include_router(escalation_router)
app.include_router(pubsub_router)
app.include_router(reputation_router)
app.include_router(stream_router)
app.include_router(agent_protocol_router)
app.include_router(cascade_history_router)
app.include_router(mcp_router)
app.include_router(a2a_router)
app.include_router(compliance_router)

if os.environ.get("SERVE_FRONTEND", "").lower() in ("1", "true", "yes"):
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static-assets")

        @app.get("/", response_class=HTMLResponse)
        async def serve_frontend_root():
            index_path = frontend_dist / "index.html"
            if index_path.exists():
                return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Frontend not built</h1>", status_code=404)

        @app.get("/{full_path:path}", response_class=HTMLResponse)
        async def serve_frontend(full_path: str):
            index_path = frontend_dist / "index.html"
            if index_path.exists():
                return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Frontend not built</h1>", status_code=404)
