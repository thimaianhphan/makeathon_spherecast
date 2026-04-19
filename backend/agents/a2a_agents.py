"""A2A protocol agents with plain Python and LangChain frameworks."""

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


def a2a_agents() -> list[AgentFact]:
    """Create agents that use A2A (Agent-to-Agent) protocol."""
    agents: list[AgentFact] = []

    # LogistiX Route Optimizer — Plain Python framework
    agents.append(AgentFact(
        agent_id="logistix-a2a-01",
        name="LogistiX Route Optimizer",
        role="logistics_optimizer",
        description="Optimizes delivery routes and shipping logistics using integer linear programming. Pure Python implementation.",
        capabilities=Capabilities(
            services=["route_optimization", "carrier_selection", "tracking"],
        ),
        identity=Identity(
            legal_entity="LogistiX S.r.l.",
            registration_country="IT",
            vat_id="IT456789012",
        ),
        location=LocationInfo(
            headquarters=Location(lat=45.4642, lon=9.1900, city="Milan", country="IT"),
        ),
        compliance=Compliance(
            jurisdictions=["EU", "IT"],
            regulations=["EU_REACH", "CE_Marking"],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="EcoVadis", score=72, tier="Gold", valid_until="2026-05-01"),
        ),
        policies=Policies(payment_terms="Net 30", accepted_currencies=["EUR"]),
        trust=Trust(
            trust_score=0.90,
            years_in_operation=12,
            ferrari_tier_status="approved_supplier",
            past_contracts=342,
            on_time_delivery_pct=97.8,
            defect_rate_ppm=3,
            dispute_count_12m=0,
        ),
        network=NetworkInfo(
            endpoint="http://localhost:8000/a2a/logistix-a2a-01",
            protocol="A2A",
            api_version="1.0",
            supported_message_types=["route_request", "route_result", "tracking_update"],
            framework="plain_python",
        ),
    ))

    # MarketIntel Analyst — LangChain framework
    agents.append(AgentFact(
        agent_id="marketintel-a2a-01",
        name="MarketIntel Analyst",
        role="market_intelligence",
        description="Real-time market intelligence, price analysis, and risk signals. Built with LangChain for multi-source data fusion.",
        capabilities=Capabilities(
            services=["market_analysis", "price_forecasting", "risk_detection"],
        ),
        identity=Identity(
            legal_entity="MarketIntel Ltd.",
            registration_country="GB",
            vat_id="GB345678901",
        ),
        location=LocationInfo(
            headquarters=Location(lat=51.5074, lon=-0.1278, city="London", country="GB"),
        ),
        compliance=Compliance(
            jurisdictions=["EU", "GB"],
            regulations=["EU_REACH", "CE_Marking", "FCA_Regulated"],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="EcoVadis", score=68, tier="Silver", valid_until="2026-03-01"),
        ),
        policies=Policies(payment_terms="Net 30", accepted_currencies=["EUR", "GBP", "USD"]),
        trust=Trust(
            trust_score=0.87,
            years_in_operation=7,
            ferrari_tier_status="approved_supplier",
            past_contracts=201,
            on_time_delivery_pct=95.3,
            defect_rate_ppm=10,
            dispute_count_12m=0,
        ),
        network=NetworkInfo(
            endpoint="http://localhost:8000/a2a/marketintel-a2a-01",
            protocol="A2A",
            api_version="1.0",
            supported_message_types=["market_report_request", "risk_signal", "price_alert"],
            framework="langchain",
        ),
    ))

    return agents
