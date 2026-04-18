// ── Frontend display types ──────────────────────────────────────────────────

export type AgentRole = "Supplier" | "Manufacturer" | "Logistics" | "Retailer" | "Procurement" | string;

// ── Backend API response types ──────────────────────────────────────────────

export interface LiveMessage {
  message_id: string;
  timestamp: string;
  from_id: string;
  from_label: string;
  to_id: string;
  to_label: string;
  type: string;
  summary: string;
  detail: string;
  color?: string;
  icon?: string;
}

export interface HeroMetric {
  label: string;
  value: string;
  trend?: string;
}

export interface CostBreakdownItem {
  label: string;
  value: number;
  color: string;
}

export interface TimelineItem {
  label: string;
  category: string;
  lead_time_days: number;
  critical_path: boolean;
}

export interface SupplierMarker {
  lat: number;
  lon: number;
  label: string;
  color: string;
  type: string;
}

export interface RiskItem {
  type: string;
  component?: string;
  supplier?: string;
  detail?: string;
  mitigation?: string;
}

export interface Negotiation {
  product: string;
  with_name: string;
  rounds: number;
  initial_ask_eur: number;
  initial_offer_eur: number;
  final_agreed_eur: number;
  discount_pct: number;
}

export interface GraphNode {
  id: string;
  label: string;
  role: string;
  color: string;
  size: number;
  trust_score?: number;
  risk_score?: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: string;
  label: string;
  value_eur?: number;
  message_count: number;
  risk_level?: number;
}

export interface ComplianceSummary {
  total_checks: number;
  passed: number;
  flagged: number;
  failed: number;
  flags: Array<{ agent_id: string; detail: string }>;
}

export interface DiscoveryResults {
  agents_discovered: number;
  agents_qualified: number;
  agents_disqualified: number;
  discovery_paths: Array<{
    need: string;
    query: string;
    selected: string;
    results_count: number;
  }>;
}

export interface ReputationScore {
  agent_id: string;
  agent_name: string;
  composite_score: number;
  delivery?: number;
  quality?: number;
  pricing?: number;
  compliance?: number;
  reliability?: number;
  transactions?: number;
  total_attestations: number;
  trend?: string;
}

export interface PubsubSummary {
  total_events: number;
  total_subscriptions: number;
  total_deliveries: number;
  subscriptions: Array<{ agent_id: string; agent_name: string; categories: string[] }>;
}

export interface IntelligenceFeedItem {
  event: {
    severity: string;
    category: string;
    source: string;
    title: string;
    description: string;
    recommended_actions: string[];
  };
  recipient_count: number;
  ai_reaction?: string;
}

export interface ReasoningLogEntry {
  agent: string;
  thought: string;
}

export interface CascadeReport {
  dashboard: {
    hero_metrics: HeroMetric[];
    cost_breakdown: CostBreakdownItem[];
    timeline_items: TimelineItem[];
    supplier_markers: SupplierMarker[];
    supplier_routes: Array<{ from: { lat: number; lon: number }; to: { lat: number; lon: number } }>;
    risk_items: RiskItem[];
  };
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  negotiations: Negotiation[];
  compliance_summary: ComplianceSummary;
  discovery_results: DiscoveryResults;
  execution_plan: { risk_assessment: { overall_risk: string; risks: RiskItem[] } };
  intelligence_feed: IntelligenceFeedItem[];
  pubsub_summary: PubsubSummary;
  reputation_summary: {
    total_agents_scored: number;
    total_attestations: number;
    leaderboard: ReputationScore[];
    chain_verifications: Record<string, { valid: boolean; length: number }>;
  };
  reasoning_log: ReasoningLogEntry[];
  component_costs?: Array<{
    supplier_id: string;
    supplier_name: string;
    product_name: string;
    quantity: number;
    unit_price_eur: number;
    total_eur: number;
  }>;
  profit_summary?: ProfitSummary | null;
  policy_evaluation?: PolicyEvaluation | null;
  intent_expansion?: IntentExpansion | null;
  event_log?: EventLogEntry[];
  delivery_target?: {
    requested_date: string | null;
    requested_days: number | null;
  };
}

export interface CascadeProgress {
  running: boolean;
  progress: number;
}

export interface CatalogueProduct {
  product_id: string;
  name: string;
  description?: string;
  selling_price_eur: number;
  intent_template?: string;
  currency?: string;
}

export interface ProfitSummary {
  total_revenue_eur: number;
  total_cost_eur: number;
  total_profit_eur: number;
  profit_per_item_eur: number;
  quantity: number;
  margin_pct: number;
}

export interface PolicySpec {
  jurisdiction: string;
  max_risk_score: number;
  min_trust_score: number;
  min_esg_score: number;
  forbid_single_supplier: boolean;
}

export interface PolicyEvaluation {
  compliant: boolean;
  violations: Record<string, unknown>[];
  explanations: string[];
}

export interface IntentExpansion {
  root_intent: string;
  component_intents: string[];
  logistics_intents: string[];
  compliance_intents: string[];
}

export interface EventLogEntry {
  type: string;
  stage: string;
  impact: Record<string, number>;
}

export interface TrustSubmission {
  agent_id: string;
  dimension: string;
  score: number;
  context?: string;
  rater_id?: string;
}

export interface TrustSummary {
  agent_id: string;
  dimension: string;
  score: number;
  submissions: number;
}

export interface SupplierSummary {
  agent_id: string;
  name: string;
  role: string;
  status?: string;
  location?: {
    headquarters?: { city?: string; country?: string };
  };
  trust?: {
    trust_score?: number;
  };
}

export interface CascadeSummary {
  report_id: string;
  intent: string;
  initiated_at: string;
  status: string;
  total_cost_eur?: number;
  total_profit_eur?: number;
  margin_pct?: number;
}

// ── Backend AgentFact (from registry) ───────────────────────────────────────

export interface AgentFact {
  agent_id: string;
  name: string;
  role: string;
  description: string;
  capabilities: {
    products: Array<{ product_id: string; name: string; category: string; unit_price_eur: number }>;
    services: string[];
    production_capacity?: { units_per_month: number; current_utilization_pct: number };
  };
  identity?: { legal_entity: string; registration_country: string };
  certifications: Array<{ type: string; description: string; issued_by: string }>;
  location?: {
    headquarters?: { lat: number; lon: number; city: string; country: string };
    manufacturing_sites: Array<{ site_id: string; city: string; country: string }>;
    shipping_regions: string[];
  };
  trust?: {
    trust_score: number;
    years_in_operation: number;
    ferrari_tier_status: string;
    past_contracts: number;
    on_time_delivery_pct: number;
  };
  status: string;
  registered_at: string;
}
