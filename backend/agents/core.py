from __future__ import annotations

from backend.schemas import (
    AgentFact,
    Capabilities,
    Certification,
    Compliance,
    ESGRating,
    Identity,
    Location,
    LocationInfo,
    NetworkInfo,
    Policies,
    Trust,
)


def core_agents() -> list[AgentFact]:
    agents: list[AgentFact] = []

    # Agnes — central AI Supply Chain Manager
    agents.append(AgentFact(
        agent_id="agnes-01",
        name="Agnes — AI Supply Chain Manager",
        role="procurement_agent",
        description=(
            "Central AI supply chain orchestrator for CPG ingredient consolidation. "
            "Analyses BOMs across multiple companies, detects substitution opportunities, "
            "validates EU food compliance, and generates consolidated sourcing proposals."
        ),
        capabilities=Capabilities(
            services=[
                "intent_decomposition",
                "bom_analysis",
                "substitution_detection",
                "supplier_discovery",
                "consolidation_planning",
                "eu_compliance_validation",
                "negotiation",
                "order_management",
            ],
        ),
        identity=Identity(legal_entity="Agnes AI GmbH", registration_country="DE"),
        location=LocationInfo(
            headquarters=Location(lat=52.5200, lon=13.4050, city="Berlin", country="DE"),
        ),
        trust=Trust(trust_score=1.0, years_in_operation=3, tier_status="internal", past_contracts=0),
        network=NetworkInfo(
            endpoint="http://localhost:8000/agent/agnes-01",
            supported_message_types=["request_quote", "negotiate", "purchase_order", "disruption_alert", "compliance_check"],
        ),
    ))

    # EU Compliance Validator — scoped to EU CPG food regulations
    agents.append(AgentFact(
        agent_id="eu-compliance-agent-01",
        name="EU Compliance Validator",
        role="compliance_agent",
        description=(
            "Automated compliance validation for EU food regulations. "
            "Checks allergen safety (EU 1169/2011), additive approval (EU 1333/2008), "
            "flavouring compliance (EU 1334/2008), organic consistency (EU 834/2007), "
            "GMO labelling (EU 1829/2003), and REACH status (EU 1907/2006)."
        ),
        capabilities=Capabilities(
            services=[
                "allergen_screening",
                "additive_approval_check",
                "organic_certification_check",
                "gmo_consistency_check",
                "reach_registration_check",
                "eu_food_label_compliance",
            ],
        ),
        identity=Identity(legal_entity="SupplyGuard GmbH", registration_country="DE"),
        location=LocationInfo(
            headquarters=Location(lat=50.1109, lon=8.6821, city="Frankfurt", country="DE"),
        ),
        certifications=[
            Certification(
                type="ISO_22000",
                description="Food Safety Management System",
                issued_by="TUV SUD",
                valid_until="2027-01-01",
            ),
        ],
        compliance=Compliance(
            jurisdictions=["EU"],
            regulations=[
                "EU_1333_2008",
                "EU_1334_2008",
                "EU_231_2012",
                "EU_1169_2011",
                "EU_834_2007",
                "EU_1829_2003",
                "EU_1907_2006",
            ],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="EcoVadis", score=80, tier="Gold", valid_until="2026-12-01"),
        ),
        trust=Trust(
            trust_score=0.95,
            years_in_operation=12,
            tier_status="approved_provider",
            past_contracts=5400,
        ),
        network=NetworkInfo(
            endpoint="http://localhost:8000/agent/eu-compliance-agent-01",
            supported_message_types=["compliance_check", "compliance_result"],
        ),
    ))

    return agents
