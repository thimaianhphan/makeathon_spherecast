"""In-memory cascade history store."""

from __future__ import annotations

from copy import deepcopy

_history: list[dict] = []


def add_report(report: dict) -> None:
    _history.append(deepcopy(report))


def list_reports() -> list[dict]:
    return list(_history)


def get_report(report_id: str) -> dict | None:
    return next((r for r in _history if r.get("report_id") == report_id), None)


def list_summaries() -> list[dict]:
    summaries = []
    for r in _history:
        exec_plan = r.get("execution_plan", {})
        profit = r.get("profit_summary") or {}
        summaries.append(
            {
                "report_id": r.get("report_id"),
                "intent": r.get("intent"),
                "initiated_at": r.get("initiated_at"),
                "status": r.get("status"),
                "total_cost_eur": exec_plan.get("total_cost_eur"),
                "total_profit_eur": profit.get("total_profit_eur"),
                "margin_pct": profit.get("margin_pct"),
            }
        )
    return summaries
