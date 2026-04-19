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
    ProductionCapacity,
    Trust,
)


def logistics_agents() -> list[AgentFact]:
    agents: list[AgentFact] = []

    # DHL Logistics
    agents.append(AgentFact(
        agent_id="dhl-logistics-01",
        name="DHL Supply Chain Italy",
        role="logistics_provider",
        description="Global logistics provider offering dedicated automotive supply chain solutions across Europe.",
        capabilities=Capabilities(
            services=["road_freight", "express_delivery", "warehousing", "customs_clearance", "insurance"],
            production_capacity=ProductionCapacity(units_per_month=100000, current_utilization_pct=55),
        ),
        identity=Identity(legal_entity="DHL Supply Chain (Italy) S.p.A.", registration_country="IT", vat_id="IT12580090158"),
        certifications=[
            Certification(type="ISO_9001", description="Quality Management", issued_by="Lloyd's Register", valid_until="2026-12-01"),
            Certification(type="AEO", description="Authorized Economic Operator", issued_by="EU Customs", valid_until="2026-06-01"),
        ],
        location=LocationInfo(
            headquarters=Location(lat=45.4654, lon=9.1859, city="Milan", country="IT"),
            shipping_regions=["EU", "NA", "APAC", "ME", "AF"],
        ),
        compliance=Compliance(jurisdictions=["EU", "IT"], regulations=["EU_REACH", "ADR_Transport"], sanctions_clear=True,
                              esg_rating=ESGRating(provider="CDP", score=75, tier="A-")),
        policies=Policies(payment_terms="Net 30", incoterms=["DAP", "DDP", "CIF"], accepted_currencies=["EUR", "USD", "GBP"]),
        trust=Trust(trust_score=0.92, years_in_operation=55, ferrari_tier_status="approved_provider", past_contracts=2100, on_time_delivery_pct=97.1, defect_rate_ppm=2, dispute_count_12m=0),
        network=NetworkInfo(endpoint="http://localhost:8000/agent/dhl-logistics-01",
                            supported_message_types=["logistics_request", "shipment_update"]),
    ))

    return agents
