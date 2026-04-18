"""Cascade step: discovery and qualification."""

from __future__ import annotations

import asyncio

from backend.services.registry_service import registry
from backend.services.agent_service import CATEGORY_AGENT_MAP, ai_reason
from backend.config import TRUST_THRESHOLD


async def run_discovery(bom: list[dict], report: dict, emit, ts) -> tuple[dict, list[dict]]:
    all_agents = registry.list_all()
    qualified_agents = {}
    disqualified = []

    for cat_info in bom:
        cat = cat_info["category"]
        emit(
            "ferrari-procurement-01",
            "Ferrari Procurement",
            "registry",
            "Agent Registry",
            "discovery",
            summary=None,
            payload={"category": cat, "summary": f"Searching for {cat} suppliers"},
        )

        candidates = registry.search(role="tier_1_supplier", capability=cat)
        if cat in CATEGORY_AGENT_MAP:
            mapped = registry.get(CATEGORY_AGENT_MAP[cat])
            if mapped and mapped not in candidates:
                candidates.append(mapped)

        valid = []
        for c in candidates:
            if c.trust and c.trust.trust_score >= TRUST_THRESHOLD:
                valid.append(c)
            else:
                disqualified.append(
                    {
                        "agent_id": c.agent_id,
                        "reason": f"Trust score {c.trust.trust_score if c.trust else 0} below threshold {TRUST_THRESHOLD}",
                    }
                )

        final = []
        for c in valid:
            has_cert = any(cert.type == "IATF_16949" and cert.status == "active" for cert in c.certifications)
            if has_cert or (c.trust and c.trust.ferrari_tier_status == "internal"):
                final.append(c)
            else:
                disqualified.append({"agent_id": c.agent_id, "reason": "Failed IATF_16949 certification check"})

        if final:
            best = max(final, key=lambda a: a.trust.trust_score if a.trust else 0)
            qualified_agents[cat] = best

            reasoning = await ai_reason(
                "Ferrari Procurement AI",
                "procurement_agent",
                f"For {cat}, found {len(candidates)} candidates. Selected {best.name} (trust={best.trust.trust_score if best.trust else 'N/A'}). Explain why.",
            )
            report["reasoning_log"].append({"agent": "Ferrari Procurement", "timestamp": ts(), "thought": reasoning})

            report["discovery_results"]["discovery_paths"].append(
                {
                    "need": cat_info["key_components"][0] if cat_info["key_components"] else cat,
                    "query": f"role=tier_1_supplier, capability={cat}, certification=IATF_16949",
                    "results_count": len(candidates),
                    "selected": best.agent_id,
                    "selection_reason": f"Trust score {best.trust.trust_score if best.trust else 'N/A'}, {best.trust.ferrari_tier_status if best.trust else 'unknown'} status",
                }
            )

            emit(
                "registry",
                "Agent Registry",
                "ferrari-procurement-01",
                "Ferrari Procurement",
                "discovery_result",
                summary=None,
                payload={
                    "category": cat,
                    "selected_agent": best.name,
                    "candidates": len(candidates),
                    "trust_score": best.trust.trust_score if best.trust else None,
                    "ai_reasoning": reasoning,
                },
            )

        await asyncio.sleep(0.15)

    report["discovery_results"]["agents_discovered"] = len(all_agents)
    report["discovery_results"]["agents_qualified"] = len(qualified_agents)
    report["discovery_results"]["agents_disqualified"] = len(disqualified)
    report["discovery_results"]["disqualification_reasons"] = disqualified[:5]

    return qualified_agents, disqualified
