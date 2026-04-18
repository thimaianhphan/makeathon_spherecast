"""
Agnes AI Supply Chain Manager — Demo Script.

Triggers a cascade, polls progress, and pretty-prints the top 3
consolidation proposals with their evidence trails.

Usage:
    cd <repo-root>
    python scripts/demo_cascade.py [--base-url http://localhost:8000]

Expected runtime: under ~90 seconds with a warm model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

# CPG-specific intent targeting supplement brands visible in the Company table
DEMO_INTENT = (
    "Evaluate consolidation opportunities for protein and emulsifier ingredients "
    "across all sports-nutrition and supplement BOMs. "
    "Identify which suppliers can cover multiple substitution groups and surface "
    "evidence-backed proposals with EU compliance status."
)


def trigger_cascade(client: httpx.Client) -> dict:
    resp = client.post(
        "/registry/trigger",
        json={
            "intent": DEMO_INTENT,
            "strategy": "consolidation-first",
            "budget_eur": 500000,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def poll_progress(client: httpx.Client, poll_interval: float = 3.0, timeout: float = 180.0) -> None:
    start = time.time()
    last_pct = -1
    print("\nProgress:")
    while time.time() - start < timeout:
        try:
            resp = client.get("/api/progress", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                pct = data.get("progress", 0)
                running = data.get("running", True)
                if pct != last_pct:
                    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                    print(f"  [{bar}] {pct:3d}%", end="\r", flush=True)
                    last_pct = pct
                if not running:
                    print(f"\n  Cascade complete ({pct}%).")
                    return
        except Exception:
            pass
        time.sleep(poll_interval)
    print("\n  Timed out waiting for cascade.")


def fetch_report(client: httpx.Client) -> dict:
    resp = client.get("/api/report", timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_proposals(client: httpx.Client) -> list[dict]:
    resp = client.get("/api/proposal", timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def fetch_evidence_item(client: httpx.Client, evidence_id: str) -> dict | None:
    try:
        resp = client.get(f"/api/evidence/{evidence_id}", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def print_separator(char: str = "─", width: int = 72) -> None:
    print(char * width)


def pretty_proposal(client: httpx.Client, idx: int, proposal: dict) -> None:
    print_separator()
    print(f"PROPOSAL {idx + 1}: {proposal.get('group_id', 'N/A')}")
    print(f"  Companies benefiting : {', '.join(proposal.get('companies_benefiting', [])) or 'N/A'}")
    print(f"  BOM coverage         : {proposal.get('total_bom_coverage', 0)} BOMs")
    print(f"  Savings estimate     : {proposal.get('estimated_savings_description', 'N/A')}")

    suppliers = proposal.get("recommended_suppliers", [])
    print(f"\n  Recommended Suppliers ({len(suppliers)}):")
    for sup in suppliers[:3]:
        flags = sup.get("risk_flags", [])
        print(
            f"    • {sup['supplier_name']}  "
            f"coverage={sup.get('volume_leverage_score', 0):.2f}  "
            f"{'[!] ' + ', '.join(flags) if flags else '[ok]'}"
        )

    # Evidence trail — pull from substitution graph or report
    print("\n  Evidence Trail:")
    shown = 0
    for sup in suppliers[:1]:
        for mat_id in sup.get("materials_covered", [])[:2]:
            # Try to find evidence via /api/evidence?claim=...
            ev_resp = client.get(
                "/api/evidence",
                params={"claim": str(mat_id)},
                timeout=5,
            )
            if ev_resp.status_code == 200:
                items = ev_resp.json()[:3]
                for ev in items:
                    print(
                        f"    [{ev.get('source_type', '?'):22s}] "
                        f"conf={ev.get('confidence', 0):.2f}  "
                        f"{ev.get('excerpt', '')[:80].strip()}"
                    )
                    if ev.get("source_url"):
                        print(f"      url: {ev['source_url']}")
                    shown += 1
                    if shown >= 4:
                        break
            if shown >= 4:
                break
    if shown == 0:
        print("    (No evidence items available — run with ENABLE_WEB_SEARCH=true)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agnes cascade demo")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("=" * 72)
    print("  Agnes AI Supply Chain Manager — Demo")
    print("=" * 72)
    print(f"\nTarget: {base_url}")
    print(f"Intent: {DEMO_INTENT[:80]}...")

    with httpx.Client(base_url=base_url) as client:
        # Health check
        try:
            client.get("/registry/health", timeout=5).raise_for_status()
        except Exception as exc:
            print(f"\nERROR: Server not reachable at {base_url}. Is the backend running?")
            print(f"  {exc}")
            sys.exit(1)

        # Trigger
        print("\nTriggering cascade...")
        trigger_result = trigger_cascade(client)
        print(f"  Status : {trigger_result.get('status')}")

        # Poll
        poll_progress(client)

        # Fetch proposals
        proposals = fetch_proposals(client)
        if not proposals:
            print("\nNo proposals returned. Check cascade logs for errors.")
            sys.exit(0)

        print(f"\nTop {min(3, len(proposals))} consolidation proposals:\n")
        for i, proposal in enumerate(proposals[:3]):
            pretty_proposal(client, i, proposal)

    print_separator("═")
    print("Demo complete. Evidence endpoints: GET /api/evidence?source_type=web_search")
    print("=" * 72)


if __name__ == "__main__":
    main()
