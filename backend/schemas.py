"""Pydantic models for Agnes — AI Supply Chain Manager (CPG edition)."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional, Callable, Literal
import uuid
from backend.time_utils import utc_now, utc_now_iso


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_id(prefix: str = "msg") -> str:
    return f"{prefix}-{utc_now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


# ── AgentFact (Registry Schema) ─────────────────────────────────────────────

class ProductSpec(BaseModel):
    material: Optional[str] = None
    diameter_mm: Optional[float] = None
    weight_kg: Optional[float] = None
    max_temp_celsius: Optional[float] = None
    displacement_cc: Optional[float] = None
    power_hp: Optional[float] = None
    voltage: Optional[float] = None

class Product(BaseModel):
    product_id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    specifications: dict = Field(default_factory=dict)
    unit_price_eur: float
    currency: str = "EUR"
    min_order_quantity: int = 1
    lead_time_days: int = 14

class ProductionCapacity(BaseModel):
    units_per_month: int
    current_utilization_pct: float

class Capabilities(BaseModel):
    products: list[Product] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    production_capacity: Optional[ProductionCapacity] = None

class Identity(BaseModel):
    legal_entity: str
    registration_country: str
    vat_id: Optional[str] = None
    duns_number: Optional[str] = None

class Certification(BaseModel):
    type: str
    description: str = ""
    issued_by: str = ""
    valid_until: Optional[str] = None
    status: str = "active"

class Location(BaseModel):
    lat: float
    lon: float
    city: str = ""
    country: str = ""

class SiteInfo(BaseModel):
    site_id: str
    city: str
    country: str
    lat: float
    lon: float
    capabilities: list[str] = []

class LocationInfo(BaseModel):
    headquarters: Optional[Location] = None
    manufacturing_sites: list[SiteInfo] = Field(default_factory=list)
    shipping_regions: list[str] = Field(default_factory=list)

class ESGRating(BaseModel):
    provider: str
    score: float
    tier: str
    valid_until: Optional[str] = None

class Compliance(BaseModel):
    jurisdictions: list[str] = Field(default_factory=list)
    regulations: list[str] = Field(default_factory=list)
    sanctions_clear: bool = True
    esg_rating: Optional[ESGRating] = None

class InsuranceInfo(BaseModel):
    product_liability: bool = True
    max_coverage_eur: float = 0

class Policies(BaseModel):
    payment_terms: str = "Net 30"
    incoterms: list[str] = Field(default_factory=list)
    accepted_currencies: list[str] = Field(default_factory=lambda: ["EUR"])
    insurance: Optional[InsuranceInfo] = None
    min_contract_value_eur: float = 0
    nda_required: bool = False

class Trust(BaseModel):
    trust_score: float = 0.5
    years_in_operation: int = 0
    ferrari_tier_status: str = "pending"
    tier_status: str = "pending"
    past_contracts: int = 0
    on_time_delivery_pct: float = 0
    defect_rate_ppm: float = 0
    dispute_count_12m: int = 0

    def model_post_init(self, __context) -> None:
        # Sync the two status fields: tier_status is the canonical name,
        # ferrari_tier_status kept for backwards compatibility
        if self.tier_status != "pending" and self.ferrari_tier_status == "pending":
            object.__setattr__(self, "ferrari_tier_status", self.tier_status)
        elif self.ferrari_tier_status != "pending" and self.tier_status == "pending":
            object.__setattr__(self, "tier_status", self.ferrari_tier_status)

class NetworkInfo(BaseModel):
    endpoint: str = ""
    protocol: str = "HTTP/JSON"
    api_version: str = "1.0"
    supported_message_types: list[str] = Field(default_factory=list)
    framework: str = "plain_python"
    heartbeat_url: str = ""

class UpstreamDependency(BaseModel):
    material: str
    typical_supplier_role: str
    critical: bool = False

class AgentFact(BaseModel):
    agent_id: str
    name: str
    role: str
    description: str = ""
    capabilities: Capabilities = Capabilities()
    identity: Optional[Identity] = None
    certifications: list[Certification] = Field(default_factory=list)
    location: Optional[LocationInfo] = None
    compliance: Optional[Compliance] = None
    policies: Optional[Policies] = None
    trust: Optional[Trust] = None
    network: Optional[NetworkInfo] = None
    upstream_dependencies: list[UpstreamDependency] = Field(default_factory=list)
    registered_at: str = ""
    last_heartbeat: str = ""
    status: str = "active"
    framework: Literal["langchain", "autogen", "plain_python"] = "plain_python"
    executor: Optional[Callable] = Field(default=None, exclude=True)  # Not serialized (runtime only)

    class Config:
        arbitrary_types_allowed = True


# ── Message Schema (Agent-to-Agent) ─────────────────────────────────────────

class MessageMetadata(BaseModel):
    hop_count: int = 1
    origin: str = ""
    trace_path: list[str] = Field(default_factory=list)

class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: make_id("msg"))
    conversation_id: str = ""
    timestamp: str = Field(default_factory=utc_now_iso)
    from_agent: str = Field(alias="from", default="")
    to_agent: str = Field(alias="to", default="")
    type: str = ""
    priority: str = "normal"
    payload: dict = Field(default_factory=dict)
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)

    class Config:
        populate_by_name = True


class AgentProtocolMessage(BaseModel):
    protocol_version: str = "0.1"
    message_id: str = Field(default_factory=lambda: make_id("apm"))
    conversation_id: str = ""
    timestamp: str = Field(default_factory=utc_now_iso)
    from_agent: str = ""
    to_agent: str = ""
    message_type: str = ""
    payload: dict = Field(default_factory=dict)
    reply_to: str = ""
    signature: str | None = None


class AgentProtocolReceipt(BaseModel):
    protocol_version: str = "0.1"
    receipt_id: str = Field(default_factory=lambda: make_id("apr"))
    received_at: str = Field(default_factory=utc_now_iso)
    message_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    status: str = "accepted"
    detail: str = ""
    details: Any = None  # Can be dict/str for rich response data
    success: bool = True  # Explicit success flag


# ── Product Catalogue ───────────────────────────────────────────────────────

class CatalogueProduct(BaseModel):
    product_id: str
    name: str
    description: str = ""
    selling_price_eur: float
    intent_template: str = "Buy all parts required to assemble one {name}"
    currency: str = "EUR"


class PolicySpec(BaseModel):
    jurisdiction: str = "EU"
    max_risk_score: float = 0.7
    min_trust_score: float = 0.70
    min_esg_score: float = 50
    forbid_single_supplier: bool = False


class PolicyEvaluation(BaseModel):
    compliant: bool
    violations: list[dict] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)


class EscalationEvent(BaseModel):
    escalation_id: str = ""
    reason: str = ""
    agent_id: str | None = None
    trust_score: float | None = None
    risk_score: float | None = None
    threshold: float = 0.0
    timestamp: str = ""


class EscalationResponse(BaseModel):
    escalation_id: str
    action: str = "proceed"


class RiskReport(BaseModel):
    agent_id: str
    risk_type: str
    severity: float
    timestamp: str = ""


class InteractionRecord(BaseModel):
    agent_id: str
    event_type: str
    payload: dict = Field(default_factory=dict)
    timestamp: str = ""


class TrustSubmission(BaseModel):
    agent_id: str
    dimension: str
    score: float
    context: str = ""
    rater_id: str = ""


class ProfitSummary(BaseModel):
    total_revenue_eur: float
    total_cost_eur: float
    total_profit_eur: float
    profit_per_item_eur: float
    quantity: int
    margin_pct: float


# ── Trigger Request ─────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    intent: str | None = None
    budget_eur: float = 500000
    product_id: str | None = None
    quantity: int = 1
    strategy: str = "consolidation-first"  # consolidation-first | cost-first | compliance-first
    desired_delivery_date: str | None = None
    company_id: int | None = None  # scope to one company, or None for all
    focus_category: str | None = None  # e.g. "emulsifiers" — optional filter


# ── Substitution & Compliance Models ────────────────────────────────────────

class ComplianceCheck(BaseModel):
    check: str  # allergen_safety, additive_approval, etc.
    status: str  # pass, fail, uncertain
    confidence: float
    reasoning: str
    source: str  # inferred, enriched, database
    regulation: str  # EU 1169/2011, EU 1333/2008, etc.


class ComplianceResult(BaseModel):
    checks: list[ComplianceCheck] = Field(default_factory=list)
    overall_status: str = "needs_review"  # approved, rejected, needs_review
    blocking_issues: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: make_id("ev"))
    source_type: Literal[
        "internal_db",
        "llm_inference",
        "web_search",
        "supplier_website",
        "product_listing",
        "certification_db",
        "regulatory_reference",
        "label_image",
        "external_api",
    ]
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    excerpt: str
    confidence: float
    timestamp: str = Field(default_factory=utc_now_iso)
    retrieved_at: Optional[str] = None
    content_hash: Optional[str] = None
    claim: Optional[str] = None


class TradeoffSummary(BaseModel):
    cost_impact: str = ""
    supplier_consolidation_benefit: str = ""
    lead_time_impact: str = ""
    compliance_risk: str = ""
    risk_notes: str = ""
    evidence_confidence_avg: float = 0.0
    external_evidence_ratio: float = 0.0


class SubstitutionCandidate(BaseModel):
    original_product_id: int
    original_name: str
    substitute_product_id: int
    substitute_name: str
    functional_equivalence_score: float = 0.0  # 0-1
    eu_compliance: Optional[ComplianceResult] = None
    overall_viable: bool = False
    confidence: float = 0.0
    evidence_trail: list[EvidenceItem] = Field(default_factory=list)
    tradeoffs: Optional[TradeoffSummary] = None


class SubstitutionGroup(BaseModel):
    group_id: str
    canonical_material: dict = Field(default_factory=dict)
    members: list[int] = Field(default_factory=list)  # product IDs
    candidates: list[SubstitutionCandidate] = Field(default_factory=list)
    functional_category: str = "other"  # emulsifier, sweetener, fat/oil, etc.


# ── Consolidation Models ─────────────────────────────────────────────────────

class SupplierRecommendation(BaseModel):
    supplier_id: int
    supplier_name: str
    materials_covered: list[int] = Field(default_factory=list)
    volume_leverage_score: float = 0.0
    consolidation_benefit: str = ""
    risk_flags: list[str] = Field(default_factory=list)


class ConsolidationProposal(BaseModel):
    group_id: str
    recommended_suppliers: list[SupplierRecommendation] = Field(default_factory=list)
    estimated_savings_description: str = ""
    companies_benefiting: list[str] = Field(default_factory=list)
    total_bom_coverage: int = 0


# ── Frontend Data Shapes ────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    role: str
    color: str = "#2196F3"
    location: Optional[dict] = None
    trust_score: Optional[float] = None
    status: str = "active"
    size: int = 30

class GraphEdge(BaseModel):
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    type: str = ""
    label: str = ""
    value_eur: Optional[float] = None
    message_count: int = 0
    status: str = ""

    class Config:
        populate_by_name = True

class LiveMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: make_id("msg"))
    timestamp: str = Field(default_factory=utc_now_iso)
    from_id: str = ""
    from_label: str = ""
    to_id: str = ""
    to_label: str = ""
    type: str = ""
    summary: str = ""
    detail: str = ""
    color: str = "#2196F3"
    icon: str = "info"

class HeroMetric(BaseModel):
    label: str
    value: str
    trend: Optional[str] = None

class DashboardData(BaseModel):
    hero_metrics: list[HeroMetric] = Field(default_factory=list)
    cost_breakdown: list[dict] = Field(default_factory=list)
    timeline_items: list[dict] = Field(default_factory=list)
    supplier_markers: list[dict] = Field(default_factory=list)
    supplier_routes: list[dict] = Field(default_factory=list)
    risk_items: list[dict] = Field(default_factory=list)
    reasoning_log: list[dict] = Field(default_factory=list)
    negotiations: list[dict] = Field(default_factory=list)
    discovery_results: dict = Field(default_factory=dict)
    compliance_summary: dict = Field(default_factory=dict)


# ── MCP (JSON-RPC 2.0) Models ─────────────────────────────────────────────

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict = Field(default_factory=dict)

class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    result: Any = None
    error: Optional[dict] = None

class McpToolDefinition(BaseModel):
    name: str
    description: str = ""
    inputSchema: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})

class McpToolsListResult(BaseModel):
    tools: list[McpToolDefinition] = Field(default_factory=list)

class McpToolCallParams(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)

class McpToolCallResult(BaseModel):
    content: list[dict] = Field(default_factory=list)
    isError: bool = False


# ── A2A (Google Agent-to-Agent) Models ─────────────────────────────────────

class A2AAgentSkill(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)

class A2AAgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = True

class A2AAgentCard(BaseModel):
    name: str
    description: str = ""
    url: str = ""
    version: str = "1.0"
    capabilities: A2AAgentCapabilities = Field(default_factory=A2AAgentCapabilities)
    skills: list[A2AAgentSkill] = Field(default_factory=list)
    defaultInputModes: list[str] = Field(default_factory=lambda: ["text/plain"])
    defaultOutputModes: list[str] = Field(default_factory=lambda: ["text/plain"])

class A2APart(BaseModel):
    type: str = "text"
    text: str = ""

class A2AMessage(BaseModel):
    role: str = "user"
    parts: list[A2APart] = Field(default_factory=list)

class A2ATaskStatus(BaseModel):
    state: str = "submitted"  # submitted | working | completed | failed | canceled
    message: Optional[A2AMessage] = None
    timestamp: str = Field(default_factory=utc_now_iso)

class A2AArtifact(BaseModel):
    name: str = ""
    description: str = ""
    parts: list[A2APart] = Field(default_factory=list)
    index: int = 0
    append: bool = False
    lastChunk: bool = True

class A2ATask(BaseModel):
    id: str = Field(default_factory=lambda: make_id("task"))
    sessionId: str = Field(default_factory=lambda: make_id("session"))
    status: A2ATaskStatus = Field(default_factory=A2ATaskStatus)
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    history: list[A2AMessage] = Field(default_factory=list)

class A2ATaskSendParams(BaseModel):
    id: str = Field(default_factory=lambda: make_id("task"))
    sessionId: str = ""
    message: A2AMessage = Field(default_factory=A2AMessage)


# ── Sourcing Pipeline Models ─────────────────────────────────────────────────

class SupplierEvidence(BaseModel):
    supplier_id: int
    supplier_name: str
    candidate_product_id: int
    unit_price_eur: Optional[float] = None
    currency_original: Optional[str] = None
    moq: Optional[int] = None
    lead_time_days: Optional[int] = None
    claimed_certifications: list[str] = Field(default_factory=list)
    country_of_origin: Optional[str] = None
    red_flags: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    source_type: Literal["supplier_site", "aggregator", "news", "cert_db", "no_evidence"]
    confidence: float
    fetched_at: str


class PipelineResult(BaseModel):
    original_raw_material_id: int
    original_raw_material_name: str
    equivalence_candidates: list[SubstitutionCandidate] = Field(default_factory=list)
    supplier_evidence: list[SupplierEvidence] = Field(default_factory=list)
    judge_decision: Literal["accept", "needs_review", "reject"]
    judge_reasoning: str
    recommended_substitute_id: Optional[int] = None
    recommended_supplier_id: Optional[int] = None
    estimated_savings_pct: Optional[float] = None
    evidence_trail: list[EvidenceItem] = Field(default_factory=list)
    flags_for_human: list[str] = Field(default_factory=list)


class SourcingProposal(BaseModel):
    finished_good_id: int
    finished_good_name: str
    finished_good_sku: str
    pipeline_results: list[PipelineResult] = Field(default_factory=list)
    total_estimated_savings_pct: Optional[float] = None
    overall_confidence: float
    generated_at: str
