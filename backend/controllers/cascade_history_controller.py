from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services.cascade_history import list_summaries, get_report

router = APIRouter()


@router.get("/api/cascades")
async def list_cascades():
    return list_summaries()


@router.get("/api/cascades/{report_id}")
async def get_cascade(report_id: str):
    report = get_report(report_id)
    if not report:
        return JSONResponse(status_code=404, content={"error": "Cascade report not found"})
    return report
