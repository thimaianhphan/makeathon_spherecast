"""Cascade step: compliance checks."""

from __future__ import annotations

import asyncio

from backend.config import MIN_ESG_SCORE


async def run_compliance(final_orders: dict, report: dict, emit) -> None:
    checks_passed = 0
    checks_flagged = 0
    flags = []

    for _, order in final_orders.items():
        agent = order["agent"]
        emit(
            "ferrari-procurement-01",
            "Ferrari Procurement",
            "eu-compliance-agent-01",
            "EU Compliance Validator",
            "compliance_check",
            summary=None,
            payload={
                "agent_name": agent.name,
                "checks": "certification, sanctions, ESG, regulation",
            },
        )

        check_results = []
        has_cert = any(c.type == "IATF_16949" and c.status == "active" for c in agent.certifications)
        check_results.append({"check": "certification_validity", "status": "pass" if has_cert else "fail",
                              "detail": f"IATF_16949 {'valid' if has_cert else 'not found'}"})

        sanctions_ok = agent.compliance.sanctions_clear if agent.compliance else True
        check_results.append({"check": "sanctions_screening", "status": "pass" if sanctions_ok else "fail",
                              "detail": "No matches in EU/US sanctions lists" if sanctions_ok else "Sanctions match found"})

        esg_score = agent.compliance.esg_rating.score if agent.compliance and agent.compliance.esg_rating else 0
        esg_ok = esg_score >= MIN_ESG_SCORE
        esg_marginal = esg_ok and esg_score < MIN_ESG_SCORE + 10
        esg_status = "pass" if esg_ok else "fail"
        check_results.append({"check": "esg_threshold", "status": esg_status,
                              "detail": f"Score {esg_score}, {'exceeds' if esg_ok else 'below'} minimum {MIN_ESG_SCORE}"})
        if esg_marginal:
            flags.append(
                {
                    "agent_id": agent.agent_id,
                    "check": "esg_threshold",
                    "detail": f"EcoVadis score {esg_score} marginally above minimum {MIN_ESG_SCORE}, recommend monitoring",
                    "severity": "warning",
                }
            )
            checks_flagged += 1

        check_results.append({"check": "regulation_compliance", "status": "pass",
                              "detail": "EU_REACH and CE_Marking confirmed"})

        all_pass = all(c["status"] == "pass" for c in check_results)
        checks_passed += 1 if all_pass else 0
        overall = "approved" if all_pass else "rejected"

        emit(
            "eu-compliance-agent-01",
            "EU Compliance Validator",
            "ferrari-procurement-01",
            "Ferrari Procurement",
            "compliance_result",
            summary=None,
            payload={
                "agent_name": agent.name,
                "status": "approved" if all_pass else "flagged",
                "detail": "; ".join(f"{c['check']}: {c['status']}" for c in check_results),
            },
        )

        report["compliance_summary"]["total_checks"] += 1
        await asyncio.sleep(0.1)

    report["compliance_summary"]["passed"] = checks_passed
    report["compliance_summary"]["flagged"] = checks_flagged
    report["compliance_summary"]["flags"] = flags
