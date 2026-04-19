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
    Product,
    Trust,
)


def disqualified_agents() -> list[AgentFact]:
    """CPG ingredient suppliers that fail qualification criteria."""
    agents: list[AgentFact] = []

    # Low-trust additive supplier — expired certification, high defect rate
    agents.append(AgentFact(
        agent_id="cheapingredients-cn-03",
        name="CheapIngredients Shenzhen Ltd.",
        role="raw_material_supplier",
        description="Low-cost food additive manufacturer. Fails EU food safety standards.",
        capabilities=Capabilities(
            products=[
                Product(
                    product_id="generic-citric-acid",
                    name="Citric Acid (E330) — unverified grade",
                    category="acids",
                    unit_price_eur=0.5,
                    min_order_quantity=5000,
                    lead_time_days=45,
                ),
            ],
        ),
        identity=Identity(legal_entity="CheapIngredients Ltd.", registration_country="CN"),
        certifications=[
            Certification(
                type="ISO_22000",
                description="Food Safety Management",
                issued_by="Local",
                valid_until="2024-01-01",
                status="expired",
            ),
        ],
        location=LocationInfo(headquarters=Location(lat=22.5431, lon=114.0579, city="Shenzhen", country="CN")),
        compliance=Compliance(
            jurisdictions=["CN"],
            regulations=[],
            sanctions_clear=True,
            esg_rating=ESGRating(provider="Self-assessed", score=28, tier="None"),
        ),
        trust=Trust(
            trust_score=0.28,
            years_in_operation=3,
            tier_status="not_approved",
            past_contracts=5,
            on_time_delivery_pct=65.0,
            defect_rate_ppm=500,
            dispute_count_12m=4,
        ),
    ))

    # Small freight company not meeting food-grade transport requirements
    agents.append(AgentFact(
        agent_id="noname-logistics-07",
        name="NoName Freight Co.",
        role="logistics_provider",
        description="Small regional freight company. Lacks food-grade (ATP) transport certification.",
        capabilities=Capabilities(services=["road_freight"]),
        identity=Identity(legal_entity="NoName Freight", registration_country="RO"),
        location=LocationInfo(headquarters=Location(lat=44.4268, lon=26.1025, city="Bucharest", country="RO")),
        trust=Trust(
            trust_score=0.31,
            years_in_operation=2,
            tier_status="not_approved",
            past_contracts=8,
            on_time_delivery_pct=68.0,
        ),
    ))

    return agents
