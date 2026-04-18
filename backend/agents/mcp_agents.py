"""MCP protocol agents with LangChain and AutoGen frameworks."""

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


def mcp_agents() -> list[AgentFact]:
    """Create agents that use MCP (JSON-RPC 2.0) protocol."""
    agents: list[AgentFact] = []

    # QualityAI Inspection Service — LangChain framework
    agents.append(AgentFact(
        agent_id="qualityai-mcp-01",
        name="QualityAI Inspection Service",
        role="quality_inspector",
        description="AI-powered quality inspection and defect detection using computer vision and statistical analysis. Built with LangChain.",
        capabilities=Capabilities(
            services=["defect_detection", "quality_report", "trend_analysis"],
        ),
        identity=Identity(
            legal_entity="QualityAI GmbH",
            registration_country="DE",
            vat_id="DE123456789",
        ),
        location=LocationInfo(
            headquarters=Location(lat=48.1351, lon=11.5820, city="Munich", country="DE"),
        ),
        compliance=Compliance(
            jurisdictions=["EU", "DE"],
            regulations=["EU_REACH", "CE_Marking"],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="EcoVadis", score=75, tier="Gold", valid_until="2026-06-01"),
        ),
        policies=Policies(payment_terms="Net 30", accepted_currencies=["EUR"]),
        trust=Trust(
            trust_score=0.88,
            years_in_operation=8,
            ferrari_tier_status="approved_supplier",
            past_contracts=156,
            on_time_delivery_pct=96.5,
            defect_rate_ppm=8,
            dispute_count_12m=0,
        ),
        network=NetworkInfo(
            endpoint="http://localhost:8000/mcp/qualityai-mcp-01",
            protocol="MCP",
            api_version="2.0",
            supported_message_types=["inspection_request", "quality_report", "defect_alert"],
            framework="langchain",
        ),
    ))

    # PredictMaint Analytics — AutoGen framework
    agents.append(AgentFact(
        agent_id="predictmaint-mcp-01",
        name="PredictMaint Analytics",
        role="maintenance_advisor",
        description="Predictive maintenance and spare parts forecasting engine using ML models. Built with AutoGen.",
        capabilities=Capabilities(
            services=["maintenance_prediction", "spare_parts_forecast", "scheduling"],
        ),
        identity=Identity(
            legal_entity="PredictMaint B.V.",
            registration_country="NL",
            vat_id="NL987654321",
        ),
        location=LocationInfo(
            headquarters=Location(lat=52.3676, lon=4.9041, city="Amsterdam", country="NL"),
        ),
        compliance=Compliance(
            jurisdictions=["EU", "NL"],
            regulations=["EU_REACH", "CE_Marking"],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="EcoVadis", score=70, tier="Silver", valid_until="2026-04-01"),
        ),
        policies=Policies(payment_terms="Net 45", accepted_currencies=["EUR", "USD"]),
        trust=Trust(
            trust_score=0.85,
            years_in_operation=5,
            ferrari_tier_status="approved_supplier",
            past_contracts=89,
            on_time_delivery_pct=94.2,
            defect_rate_ppm=12,
            dispute_count_12m=0,
        ),
        network=NetworkInfo(
            endpoint="http://localhost:8000/mcp/predictmaint-mcp-01",
            protocol="MCP",
            api_version="2.0",
            supported_message_types=["maintenance_prediction", "maintenance_schedule", "spare_parts_forecast"],
            framework="autogen",
        ),
    ))

    return agents
