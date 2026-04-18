import type {
  AgentFact,
  CascadeReport,
  CascadeProgress,
  LiveMessage,
  CatalogueProduct,
  PolicyEvaluation,
  PolicySpec,
  CascadeSummary,
  SupplierSummary,
  TrustSubmission,
  TrustSummary,
} from "@/data/types";

const envBase = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL;
const BASE = envBase ?? "http://localhost:8000";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ── Registry ────────────────────────────────────────────────────────────────

export function listAgents(): Promise<AgentFact[]> {
  return fetchJSON("/registry/list");
}

export function getAgent(agentId: string): Promise<AgentFact> {
  return fetchJSON(`/registry/agent/${agentId}`);
}

export function searchAgents(params: {
  role?: string;
  capability?: string;
  region?: string;
  min_trust?: number;
}): Promise<AgentFact[]> {
  const qs = new URLSearchParams();
  if (params.role) qs.set("role", params.role);
  if (params.capability) qs.set("capability", params.capability);
  if (params.region) qs.set("region", params.region);
  if (params.min_trust) qs.set("min_trust", String(params.min_trust));
  return fetchJSON(`/registry/search?${qs}`);
}

// ── Catalogue & Suppliers ───────────────────────────────────────────────────

export function getCatalogue(): Promise<CatalogueProduct[]> {
  return fetchJSON("/api/catalogue");
}

export function getSuppliers(): Promise<SupplierSummary[]> {
  return fetchJSON("/api/suppliers");
}

// ── Cascade ─────────────────────────────────────────────────────────────────

export function triggerCascade(params: {
  intent?: string;
  budget_eur?: number;
  product_id?: string;
  quantity?: number;
  desired_delivery_date?: string;
}) {
  return fetchJSON<{ status: string; intent: string }>("/registry/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

export function getProgress(): Promise<CascadeProgress> {
  return fetchJSON("/api/progress");
}

export function getReport(): Promise<CascadeReport> {
  return fetchJSON("/api/report");
}

// ── Messages ────────────────────────────────────────────────────────────────

export function getLogs(): Promise<LiveMessage[]> {
  return fetchJSON("/registry/logs");
}

// ── Policy ──────────────────────────────────────────────────────────────────

export function getPolicy(): Promise<PolicySpec> {
  return fetchJSON("/api/policy");
}

export function evaluatePolicy(plan: Record<string, unknown>): Promise<PolicyEvaluation> {
  return fetchJSON("/api/policy/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(plan),
  });
}

// ── Trust ───────────────────────────────────────────────────────────────────

export function getContextualTrust(agentId: string): Promise<TrustSummary> {
  return fetchJSON(`/api/trust/contextual/${agentId}`);
}

export function submitTrustRating(payload: TrustSubmission): Promise<void> {
  return fetchJSON("/api/trust/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ── Reputation ──────────────────────────────────────────────────────────────

export function getReputationSummary() {
  return fetchJSON<{
    total_agents_scored: number;
    total_attestations: number;
    leaderboard: Array<{
      agent_id: string;
      agent_name: string;
      composite_score: number;
      total_attestations: number;
    }>;
  }>("/api/reputation/summary");
}

export function getReputationScores() {
  return fetchJSON<Array<{
    agent_id: string;
    agent_name: string;
    composite_score: number;
    total_attestations: number;
  }>>("/api/reputation/scores");
}

// ── Pub-Sub ─────────────────────────────────────────────────────────────────

export function getPubsubSummary() {
  return fetchJSON("/api/pubsub/summary");
}

export function getPubsubEvents() {
  return fetchJSON("/api/pubsub/events");
}

// ── Simulation ──────────────────────────────────────────────────────────────

export function simulateSupplierFailure(agent_id: string) {
  return fetchJSON("/api/simulate/supplier-failure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id }),
  });
}

// ── Cascade History ─────────────────────────────────────────────────────────

export function getCascades(): Promise<CascadeSummary[]> {
  return fetchJSON("/api/cascades");
}

export function getCascadeReport(reportId: string): Promise<CascadeReport> {
  return fetchJSON(`/api/cascades/${reportId}`);
}

// ── SSE Stream ──────────────────────────────────────────────────────────────

export function subscribeToStream(
  onMessage: (msg: LiveMessage) => void,
  onError?: (err: Event) => void,
): EventSource {
  const es = new EventSource(`${BASE}/api/stream`);
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as LiveMessage;
      if (data.type === "heartbeat") return;
      onMessage(data);
    } catch {
      // ignore parse errors
    }
  };
  if (onError) es.onerror = onError;
  return es;
}
