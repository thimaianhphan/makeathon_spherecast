import type {
  BomData,
  CatalogueProduct,
  ComplianceResult,
  FinishedGoodAnalysis,
  IngredientAnalysis,
  PipelineEvidenceItem,
  PipelineResult,
  ProductComplianceReport,
  SourcingEvidenceItem,
  SubstitutionCandidate,
  SupplierEvidence,
  VariantCard,
} from "@/data/types";

const envBase = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL;
const BASE = envBase ?? "http://localhost:8000";

type StartAnalysisResponse = { analysis_id: string } | SourcingProposalRaw | FinishedGoodAnalysis;

interface SourcingProposalRaw {
  finished_good_id: number;
  finished_good_name: string;
  finished_good_sku: string;
  pipeline_results: PipelineResult[];
  total_estimated_savings_pct: number | null;
  overall_confidence: number;
  generated_at: string;
}

export const SCORE_WEIGHTS = { compliance: 0.5, quality: 0.3, price: 0.2 } as const;

const BACKEND_SOURCE_TYPE_MAP: Record<string, SourcingEvidenceItem["source_type"]> = {
  supplier_site: "supplier_site",
  supplier_website: "supplier_site",
  product_listing: "supplier_site",
  label_image: "supplier_site",
  aggregator: "news",
  certification_db: "cert_db",
  external_api: "cert_db",
  regulatory_reference: "regulatory",
  web_search: "news",
  llm_inference: "llm_inference",
  internal_db: "llm_inference",
  no_evidence: "no_evidence",
  news: "news",
};

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export function getCatalogue(): Promise<CatalogueProduct[]> {
  return fetchJSON("/api/catalogue");
}

export async function getFinishedGoods(): Promise<CatalogueProduct[]> {
  try {
    return await fetchJSON("/api/finished-goods");
  } catch {
    return getCatalogue();
  }
}

export function getBom(productId: number): Promise<BomData> {
  return fetchJSON(`/api/boms/${productId}`);
}

export function getProductCompliance(
  productId: number,
  options: { scrape?: boolean } = {},
): Promise<ProductComplianceReport> {
  const scrape = options.scrape ? "true" : "false";
  return fetchJSON(`/api/compliance/${productId}?scrape=${scrape}`);
}

function normalizeSupports(claim: string | undefined, sourceType: string): string {
  const raw = (claim ?? "").trim().toLowerCase();
  if (!raw) {
    if (sourceType === "supplier_website" || sourceType === "supplier_site") return "price";
    return "general";
  }

  if (raw.includes("price") || raw.includes("cost") || raw.includes("supplier evidence")) {
    return "price";
  }
  if (raw.includes("allergen")) return "allergen_safety";
  if (raw.includes("additive")) return "additive_approval";
  if (raw.includes("label")) return "labeling";
  if (raw.includes("claim")) return "claims_substantiation";
  return raw.replace(/\s+/g, "_");
}

function adaptEvidenceItem(ev: PipelineEvidenceItem): SourcingEvidenceItem {
  return {
    source_type: BACKEND_SOURCE_TYPE_MAP[ev.source_type] ?? "llm_inference",
    source_label: ev.source_title ?? ev.source_type,
    url: ev.source_url ?? null,
    excerpt: ev.excerpt,
    confidence: ev.confidence,
    fetched_at: ev.timestamp,
    supports: normalizeSupports((ev as PipelineEvidenceItem & { claim?: string }).claim, ev.source_type),
  };
}

function combineEvidence(
  candidate: SubstitutionCandidate,
  result: PipelineResult,
): SourcingEvidenceItem[] {
  const candidateName = candidate.substitute_name.toLowerCase();
  const candidateScopedShared = result.evidence_trail.filter((ev) => {
    const text = `${ev.excerpt} ${String((ev as PipelineEvidenceItem & { claim?: string }).claim ?? "")}`.toLowerCase();
    return text.includes(candidateName);
  });

  const shared = candidateScopedShared.length > 0 ? candidateScopedShared : result.evidence_trail;
  const merged = [...candidate.evidence_trail, ...shared].map(adaptEvidenceItem);
  const deduped = new Map<string, SourcingEvidenceItem>();

  for (const item of merged) {
    const key = [
      item.source_type,
      item.source_label,
      item.url ?? "",
      item.excerpt,
      item.supports,
      item.fetched_at,
    ].join("|");
    if (!deduped.has(key)) {
      deduped.set(key, item);
    }
  }

  return Array.from(deduped.values());
}

function computeComplianceScore(compliance: ComplianceResult | null | undefined): number {
  if (!compliance || !compliance.checks.length) return 50;
  const total = compliance.checks.reduce((sum, check) => {
    const base = check.status === "pass" ? 100 : check.status === "uncertain" ? 50 : 0;
    const weighted = check.source === "inferred" ? Math.min(base, 60) : base;
    return sum + weighted;
  }, 0);
  return Math.round(total / compliance.checks.length);
}

function buildComplianceRationale(compliance: ComplianceResult | null | undefined): string {
  if (!compliance || !compliance.checks.length) {
    return "Compliance evidence incomplete; manual review recommended.";
  }

  const passed = compliance.checks.filter((check) => check.status === "pass").length;
  const uncertain = compliance.checks.filter((check) => check.status === "uncertain").length;
  const failed = compliance.checks.filter((check) => check.status === "fail").length;

  if (compliance.blocking_issues.length > 0) {
    return compliance.blocking_issues[0];
  }

  return `${passed} pass, ${uncertain} uncertain, ${failed} fail across ${compliance.checks.length} EU checks.`;
}

function computePriceScore(savingsPct: number | null | undefined): number {
  if (savingsPct == null) return 50;
  const clamped = Math.max(-0.2, Math.min(0.2, savingsPct));
  return Math.round(50 + (clamped / 0.2) * 50);
}

function pickBestSupplierEvidence(items: SupplierEvidence[]): SupplierEvidence | null {
  if (!items.length) return null;
  const sorted = [...items].sort((a, b) => {
    const aHasPrice = a.unit_price_eur != null ? 1 : 0;
    const bHasPrice = b.unit_price_eur != null ? 1 : 0;
    if (bHasPrice !== aHasPrice) return bHasPrice - aHasPrice;

    const aHasUrl = a.source_urls.length > 0 ? 1 : 0;
    const bHasUrl = b.source_urls.length > 0 ? 1 : 0;
    if (bHasUrl !== aHasUrl) return bHasUrl - aHasUrl;

    return b.confidence - a.confidence;
  });
  return sorted[0] ?? null;
}

function formatPriceRationale(
  savingsPct: number | null,
  priceSourceLabel: string | null,
): string {
  if (savingsPct == null) {
    if (priceSourceLabel) {
      return `Supplier quote available from ${priceSourceLabel}, but incumbent-relative delta is unavailable.`;
    }
    return "Price unverified - no incumbent-relative quote available.";
  }
  if (savingsPct >= 0) {
    return `Estimated ${(savingsPct * 100).toFixed(1)}% cheaper per kg from ${priceSourceLabel ?? "supplier evidence"}.`;
  }
  return `Estimated ${(Math.abs(savingsPct) * 100).toFixed(1)}% more expensive per kg from ${priceSourceLabel ?? "supplier evidence"}.`;
}

function buildTradeoffSummary(candidate: SubstitutionCandidate, fallbackReasoning: string): string {
  if (!candidate.tradeoffs) return fallbackReasoning;

  const segments = [
    candidate.tradeoffs.cost_impact,
    candidate.tradeoffs.lead_time_impact ? `Lead time: ${candidate.tradeoffs.lead_time_impact}` : "",
    candidate.tradeoffs.risk_notes,
  ].filter((segment) => segment && segment.trim().length > 0);

  if (segments.length === 0) return fallbackReasoning;
  return segments.join(" | ");
}

function adaptCandidate(
  candidate: SubstitutionCandidate,
  result: PipelineResult,
  supplierEvidenceByProductId: Map<number, SupplierEvidence[]>,
): Omit<VariantCard, "rank"> {
  const supplierOptions = supplierEvidenceByProductId.get(candidate.substitute_product_id) ?? [];
  const bestSupplier = pickBestSupplierEvidence(supplierOptions);
  const priceSourceLabel = bestSupplier
    ? `${bestSupplier.supplier_name} (${bestSupplier.source_type.replace(/_/g, " ")})`
    : null;

  const candidateSavings =
    result.recommended_substitute_id === candidate.substitute_product_id
      ? result.estimated_savings_pct
      : null;
  const priceKnown = candidateSavings != null;

  const compliance = computeComplianceScore(candidate.eu_compliance);
  const quality = Math.round(candidate.functional_equivalence_score * 100);
  const price = computePriceScore(candidateSavings);
  const composite = Math.round(
    SCORE_WEIGHTS.compliance * compliance +
      SCORE_WEIGHTS.quality * quality +
      SCORE_WEIGHTS.price * price,
  );

  return {
    substitute_product_id: candidate.substitute_product_id,
    substitute_name: candidate.substitute_name,
    supplier_id: bestSupplier?.supplier_id ?? 0,
    supplier_name: bestSupplier?.supplier_name ?? "Supplier pending",
    scores: { composite, compliance, quality, price },
    score_rationales: {
      compliance: buildComplianceRationale(candidate.eu_compliance),
      quality: `Functional equivalence score: ${quality}/100.`,
      price: formatPriceRationale(candidateSavings, priceSourceLabel),
    },
    judge_decision: result.judge_decision,
    flags_for_human: result.flags_for_human,
    tradeoff_summary: buildTradeoffSummary(candidate, result.judge_reasoning),
    evidence: combineEvidence(candidate, result),
    price_known: priceKnown,
    price_source_label: priceSourceLabel,
  };
}

function rankVariants(variants: Array<Omit<VariantCard, "rank">>): VariantCard[] {
  const sorted = [...variants]
    .sort((a, b) => {
      if (b.scores.composite !== a.scores.composite) return b.scores.composite - a.scores.composite;
      if (b.scores.compliance !== a.scores.compliance) return b.scores.compliance - a.scores.compliance;
      if (b.scores.quality !== a.scores.quality) return b.scores.quality - a.scores.quality;
      return b.scores.price - a.scores.price;
    })
    .slice(0, 3);

  return sorted.map((variant, index) => ({
    ...variant,
    rank: (index + 1) as 1 | 2 | 3,
  }));
}

function adaptPipelineResult(result: PipelineResult): IngredientAnalysis {
  const supplierEvidenceByProductId = new Map<number, SupplierEvidence[]>();
  for (const supplierEvidence of result.supplier_evidence) {
    const existing = supplierEvidenceByProductId.get(supplierEvidence.candidate_product_id) ?? [];
    existing.push(supplierEvidence);
    supplierEvidenceByProductId.set(supplierEvidence.candidate_product_id, existing);
  }

  const top_variants = rankVariants(
    result.equivalence_candidates.map((candidate) =>
      adaptCandidate(candidate, result, supplierEvidenceByProductId),
    ),
  );

  return {
    raw_material_id: result.original_raw_material_id,
    raw_material_name: result.original_raw_material_name,
    current_supplier_id: null,
    current_supplier_name: null,
    status: "done",
    top_variants,
    keep_current_reason: result.judge_decision === "reject" ? result.judge_reasoning : null,
  };
}

function adaptSourcingProposal(proposal: SourcingProposalRaw, companyName = ""): FinishedGoodAnalysis {
  return {
    finished_good_id: proposal.finished_good_id,
    finished_good_sku: proposal.finished_good_sku,
    finished_good_name: proposal.finished_good_name,
    company_name: companyName,
    ingredients: proposal.pipeline_results.map(adaptPipelineResult),
    analyzed_at: proposal.generated_at,
  };
}

function isFinishedGoodAnalysis(payload: unknown): payload is FinishedGoodAnalysis {
  if (!payload || typeof payload !== "object") return false;
  const parsed = payload as FinishedGoodAnalysis;
  return (
    typeof parsed.finished_good_id === "number" &&
    typeof parsed.finished_good_sku === "string" &&
    typeof parsed.finished_good_name === "string" &&
    Array.isArray(parsed.ingredients)
  );
}

function isStartResponse(payload: unknown): payload is { analysis_id: string } {
  if (!payload || typeof payload !== "object") return false;
  const parsed = payload as { analysis_id?: unknown };
  return typeof parsed.analysis_id === "string";
}

function normalizeAnalysisPayload(
  payload: SourcingProposalRaw | FinishedGoodAnalysis,
  companyName = "",
): FinishedGoodAnalysis {
  if (isFinishedGoodAnalysis(payload)) return payload;
  return adaptSourcingProposal(payload, companyName);
}

const inMemoryAnalysisCache = new Map<number, FinishedGoodAnalysis>();

async function fetchAndCacheAnalysis(
  finishedGoodId: number,
  companyName = "",
): Promise<FinishedGoodAnalysis> {
  const payload = await fetchJSON<SourcingProposalRaw | FinishedGoodAnalysis>(
    `/api/sourcing/analyze/${finishedGoodId}`,
    { method: "POST" },
  );
  const normalized = normalizeAnalysisPayload(payload, companyName);
  inMemoryAnalysisCache.set(finishedGoodId, normalized);
  return normalized;
}

export async function startAnalysis(finishedGoodId: number): Promise<{ analysis_id: string }> {
  const payload = await fetchJSON<StartAnalysisResponse>(`/api/sourcing/analyze/${finishedGoodId}`, {
    method: "POST",
  });

  if (isStartResponse(payload)) {
    return payload;
  }

  const normalized = normalizeAnalysisPayload(payload);
  inMemoryAnalysisCache.set(finishedGoodId, normalized);
  return { analysis_id: String(finishedGoodId) };
}

export async function getAnalysis(finishedGoodId: number): Promise<FinishedGoodAnalysis> {
  const cached = inMemoryAnalysisCache.get(finishedGoodId);
  if (cached) return cached;
  return fetchAndCacheAnalysis(finishedGoodId);
}

export function streamAnalysis(_finishedGoodId: number): EventSource {
  return new EventSource(`${BASE}/api/stream`);
}
