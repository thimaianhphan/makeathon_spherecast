from __future__ import annotations

import re

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
    Product,
    ProductionCapacity,
    SiteInfo,
    Trust,
    UpstreamDependency,
)


def _slugify(name: str) -> str:
    """Convert a supplier name to a URL-safe agent ID slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def supplier_agents() -> list[AgentFact]:
    """
    Build one AgentFact per Supplier from the SQLite data.
    Falls back to a hardcoded baseline list if the database is unavailable.
    """
    try:
        from backend.services.db_service import get_supplier_product_mappings
        mappings = get_supplier_product_mappings()
        return _build_from_db(mappings)
    except Exception:
        return _default_supplier_agents()


def company_agents() -> list[AgentFact]:
    """
    Build one AgentFact per Company as a 'procurement_agent'.
    Represents the buying side.
    """
    try:
        from backend.services.db_service import get_all_companies
        companies = get_all_companies()
        agents: list[AgentFact] = []
        for company in companies:
            agent_id = f"company-{_slugify(company['Name'])}"
            agents.append(AgentFact(
                agent_id=agent_id,
                name=company["Name"],
                role="procurement_agent",
                description=f"Procurement agent for {company['Name']} — CPG manufacturer.",
                capabilities=Capabilities(
                    services=["procurement", "bom_management", "supplier_negotiation"],
                ),
                identity=Identity(legal_entity=company["Name"], registration_country="EU"),
                compliance=Compliance(
                    jurisdictions=["EU"],
                    regulations=["EU_1333_2008", "EU_1169_2011", "EU_834_2007"],
                    sanctions_clear=True,
                ),
                trust=Trust(
                    trust_score=0.85,
                    years_in_operation=10,
                    tier_status="active",
                    past_contracts=0,
                ),
                network=NetworkInfo(
                    endpoint=f"http://localhost:8000/agent/{agent_id}",
                    supported_message_types=["request_quote", "purchase_order"],
                ),
            ))
        return agents
    except Exception:
        return []


def _build_from_db(mappings: list[dict]) -> list[AgentFact]:
    """Build AgentFact list from Supplier_Product join data."""
    # Group products by supplier
    supplier_map: dict[int, dict] = {}
    for row in mappings:
        sid = row["supplier_id"]
        if sid not in supplier_map:
            supplier_map[sid] = {"name": row["supplier_name"], "products": []}
        supplier_map[sid]["products"].append({
            "product_id": row["product_id"],
            "sku": row["product_sku"],
            "name": row["product_name"],
        })

    agents: list[AgentFact] = []
    for sid, data in supplier_map.items():
        agent_id = f"supplier-{_slugify(data['name'])}"
        products = [
            Product(
                product_id=str(p["product_id"]),
                name=p["name"],
                category="raw_material",
                subcategory=p["sku"],
                unit_price_eur=0.0,
                min_order_quantity=1,
                lead_time_days=14,
            )
            for p in data["products"]
        ]
        agents.append(AgentFact(
            agent_id=agent_id,
            name=data["name"],
            role="raw_material_supplier",
            description=f"Raw material supplier: {data['name']}. Supplies {len(products)} ingredient(s) to EU CPG companies.",
            capabilities=Capabilities(
                products=products,
                services=["ingredient_supply", "quality_certification", "regulatory_compliance"],
                production_capacity=ProductionCapacity(units_per_month=100000, current_utilization_pct=65),
            ),
            identity=Identity(legal_entity=data["name"], registration_country="EU"),
            certifications=[
                Certification(type="ISO_22000", description="Food Safety Management", issued_by="Bureau Veritas", valid_until="2027-01-01"),
                Certification(type="FSSC_22000", description="Food Safety System Certification", issued_by="SGS", valid_until="2026-12-01"),
            ],
            compliance=Compliance(
                jurisdictions=["EU"],
                regulations=["EU_1333_2008", "EU_1169_2011", "EU_1334_2008", "EU_REACH"],
                sanctions_clear=True,
                esg_rating=ESGRating(provider="EcoVadis", score=65, tier="Silver", valid_until="2026-06-01"),
            ),
            policies=Policies(
                payment_terms="Net 45",
                incoterms=["DAP", "EXW"],
                accepted_currencies=["EUR"],
                min_contract_value_eur=5000,
            ),
            trust=Trust(
                trust_score=0.80,
                years_in_operation=15,
                tier_status="approved_supplier",
                past_contracts=50,
                on_time_delivery_pct=92.0,
                defect_rate_ppm=20,
                dispute_count_12m=0,
            ),
            network=NetworkInfo(
                endpoint=f"http://localhost:8000/agent/{agent_id}",
                supported_message_types=["request_quote", "negotiate", "purchase_order", "shipment_update"],
            ),
        ))
    return agents


def _default_supplier_agents() -> list[AgentFact]:
    """Fallback hardcoded CPG ingredient supplier agents."""
    agents: list[AgentFact] = []

    agents.append(AgentFact(
        agent_id="supplier-cargill-food-ingredients",
        name="Cargill Food Ingredients",
        role="raw_material_supplier",
        description="Global supplier of oils, starches, sweeteners, and emulsifiers for the CPG food industry.",
        capabilities=Capabilities(
            products=[
                Product(product_id="1", name="Sunflower Oil (Refined)", category="raw_material", subcategory="RM-001", unit_price_eur=0.0),
                Product(product_id="3", name="Lecithin (Soy-based, E322)", category="raw_material", subcategory="RM-003", unit_price_eur=0.0),
                Product(product_id="5", name="Sucrose (Cane Sugar)", category="raw_material", subcategory="RM-005", unit_price_eur=0.0),
            ],
            services=["ingredient_supply", "quality_certification"],
        ),
        identity=Identity(legal_entity="Cargill B.V.", registration_country="NL"),
        compliance=Compliance(jurisdictions=["EU"], regulations=["EU_1333_2008", "EU_1169_2011"], sanctions_clear=True),
        trust=Trust(trust_score=0.88, years_in_operation=155, tier_status="approved_supplier", past_contracts=500),
        network=NetworkInfo(endpoint="http://localhost:8000/agent/supplier-cargill-food-ingredients",
                            supported_message_types=["request_quote", "purchase_order"]),
    ))

    agents.append(AgentFact(
        agent_id="supplier-brenntag-se",
        name="Brenntag SE",
        role="raw_material_supplier",
        description="Chemical distribution specialist. Supplies food-grade acids, antioxidants, and preservatives.",
        capabilities=Capabilities(
            products=[
                Product(product_id="15", name="Citric Acid (E330)", category="raw_material", subcategory="RM-015", unit_price_eur=0.0),
                Product(product_id="16", name="Ascorbic Acid (Vitamin C, E300)", category="raw_material", subcategory="RM-016", unit_price_eur=0.0),
            ],
            services=["ingredient_supply", "regulatory_compliance"],
        ),
        identity=Identity(legal_entity="Brenntag SE", registration_country="DE"),
        compliance=Compliance(jurisdictions=["EU"], regulations=["EU_1333_2008", "EU_REACH"], sanctions_clear=True),
        trust=Trust(trust_score=0.85, years_in_operation=150, tier_status="approved_supplier", past_contracts=300),
        network=NetworkInfo(endpoint="http://localhost:8000/agent/supplier-brenntag-se",
                            supported_message_types=["request_quote", "purchase_order"]),
    ))

    return agents

