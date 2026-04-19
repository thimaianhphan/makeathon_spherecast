import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldCheck, ShieldAlert, ShieldQuestion, ExternalLink, RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getProductCompliance } from "@/api/client";
import type {
  ProductComplianceReport,
  ProductComplianceOverallStatus,
  RawMaterialComplianceAssessment,
  RawMaterialComplianceStatus,
} from "@/data/types";

interface ComplianceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  productId: number;
  productSku?: string;
  productName?: string;
  companyName?: string;
}

function overallStatusLabel(status: ProductComplianceOverallStatus): {
  label: string;
  tone: "green" | "amber" | "red" | "slate";
  Icon: typeof ShieldCheck;
} {
  switch (status) {
    case "VALID":
      return { label: "Valid", tone: "green", Icon: ShieldCheck };
    case "RISKY":
      return { label: "Risky", tone: "amber", Icon: ShieldAlert };
    case "INSUFFICIENT_EVIDENCE":
      return { label: "Insufficient evidence", tone: "red", Icon: ShieldAlert };
    default:
      return { label: "Unknown", tone: "slate", Icon: ShieldQuestion };
  }
}

function materialStatusLabel(status: RawMaterialComplianceStatus): {
  label: string;
  tone: "green" | "amber" | "red" | "slate";
} {
  switch (status) {
    case "VALID_RAW_MATERIAL":
      return { label: "Valid", tone: "green" };
    case "RISKY_RAW_MATERIAL":
      return { label: "Risky", tone: "amber" };
    case "INSUFFICIENT_EVIDENCE":
      return { label: "Insufficient evidence", tone: "red" };
    default:
      return { label: status, tone: "slate" };
  }
}

const TONE_CLASS: Record<"green" | "amber" | "red" | "slate", string> = {
  green: "bg-green-100 text-green-700 border-green-200",
  amber: "bg-amber-100 text-amber-800 border-amber-200",
  red: "bg-red-100 text-red-700 border-red-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
};

function RawMaterialBlock({ item }: { item: RawMaterialComplianceAssessment }) {
  const { label, tone } = materialStatusLabel(item.status);
  const matchedCount = item.supplier_checks.filter((c) => c.official_website_known).length;

  return (
    <div className="rounded-md border border-border bg-card p-3 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {item.normalized_name || item.ingredient_sku}
          </p>
          <p className="text-[11px] font-mono text-muted-foreground truncate">{item.ingredient_sku}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONE_CLASS[tone]}`}>
          {label}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <div className="rounded border border-border bg-muted/30 px-2 py-1">
          <p className="uppercase tracking-wide text-muted-foreground">Suppliers</p>
          <p className="font-medium text-foreground">{item.suppliers.length}</p>
        </div>
        <div className="rounded border border-border bg-muted/30 px-2 py-1">
          <p className="uppercase tracking-wide text-muted-foreground">Public pricing</p>
          <p className="font-medium text-foreground">
            {matchedCount}/{item.supplier_checks.length || 0}
          </p>
        </div>
        <div className="rounded border border-border bg-muted/30 px-2 py-1">
          <p className="uppercase tracking-wide text-muted-foreground">Evidence</p>
          <p className="font-medium text-foreground">{item.external_evidence.length}</p>
        </div>
      </div>

      {item.supplier_checks.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Supplier checks
          </p>
          <ul className="space-y-1">
            {item.supplier_checks.map((check) => {
              const isPublic = check.official_website_known;
              return (
                <li
                  key={`${item.ingredient_id}-${check.supplier_id}`}
                  className="flex items-start justify-between gap-2 text-xs"
                >
                  <div className="min-w-0">
                    <span className="font-medium text-foreground">{check.supplier_name}</span>
                    <span className="text-muted-foreground">
                      {" - "}
                      {isPublic
                        ? "Price publicly listed online."
                        : "Please contact the supplier for more details."}
                    </span>
                  </div>
                  {isPublic && check.official_url ? (
                    <a
                      href={check.official_url}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <ExternalLink className="w-3 h-3" />
                      site
                    </a>
                  ) : (
                    <span className="shrink-0 rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                      Contact supplier
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {item.external_evidence.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Supplier-site evidence
          </p>
          <ul className="space-y-1.5">
            {item.external_evidence.map((ev) => (
              <li key={ev.source_url} className="text-xs rounded border border-border bg-muted/20 px-2 py-1.5">
                <div className="flex items-center justify-between gap-2">
                  <a
                    href={ev.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate text-primary hover:underline"
                  >
                    {ev.source_domain}
                  </a>
                  <span className="shrink-0 text-[10px] uppercase text-muted-foreground">
                    {ev.confidence} confidence
                  </span>
                </div>
                {ev.matched_terms.length > 0 && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Terms: {ev.matched_terms.slice(0, 8).join(", ")}
                  </p>
                )}
                {ev.matched_snippets.length > 0 && (
                  <p className="mt-1 italic text-muted-foreground line-clamp-2">
                    "...{ev.matched_snippets[0]}..."
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.regulation_references.length > 0 && (
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Regulation references
          </p>
          <ul className="space-y-1">
            {item.regulation_references.map((reg) => (
              <li key={`${item.ingredient_id}-${reg.rule_id}`} className="text-xs">
                <a
                  href={reg.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                >
                  {reg.rule_id}
                  <ExternalLink className="w-3 h-3" />
                </a>
                <span className="text-muted-foreground"> - {reg.matched_reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.rationale.length > 0 && (
        <div className="space-y-0.5 pt-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Rationale
          </p>
          <ul className="space-y-0.5">
            {item.rationale.map((line, idx) => (
              <li key={idx} className="text-[11px] text-muted-foreground">
                - {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function ComplianceDialog({
  open,
  onOpenChange,
  productId,
  productSku,
  productName,
  companyName,
}: ComplianceDialogProps) {
  const [report, setReport] = useState<ProductComplianceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scrape, setScrape] = useState(false);

  const load = useCallback(
    async (scrapeFlag: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const result = await getProductCompliance(productId, { scrape: scrapeFlag });
        setReport(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [productId],
  );

  useEffect(() => {
    if (!open) return;
    void load(scrape);
  }, [open, load, scrape]);

  const overall = report ? overallStatusLabel(report.overall_status) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="w-4 h-4 text-primary" />
            Raw-material compliance check
          </DialogTitle>
          <DialogDescription className="text-xs">
            {productSku && <span className="font-mono">{productSku}</span>}
            {productName && <span className="ml-1">{productName}</span>}
            {companyName && <span className="ml-1 text-muted-foreground">- {companyName}</span>}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-between gap-3 pb-2">
          <div className="flex items-center gap-2">
            {overall && (
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASS[overall.tone]}`}
              >
                <overall.Icon className="w-3.5 h-3.5" />
                {overall.label}
              </span>
            )}
            {report && (
              <span className="text-[11px] text-muted-foreground">
                {report.summary.valid} valid / {report.summary.risky} risky /{" "}
                {report.summary.insufficient} insufficient across {report.summary.total} raw materials
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                className="h-3 w-3"
                checked={scrape}
                onChange={(e) => setScrape(e.target.checked)}
              />
              Search public supplier sites
            </label>
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2.5 text-[11px]"
              onClick={() => void load(scrape)}
              disabled={loading}
            >
              <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
              Re-run
            </Button>
          </div>
        </div>

        <Separator />

        <div className="flex-1 overflow-y-auto pt-3 pr-1 space-y-2">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              {scrape
                ? "Running compliance check (searching public supplier sites)..."
                : "Running compliance check..."}
            </div>
          )}
          {!loading && error && (
            <div className="py-6 text-center text-sm text-red-600">{error}</div>
          )}
          {!loading && !error && report && report.results.length === 0 && (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No BOM raw materials were found for this finished good.
            </div>
          )}
          {!loading && !error && report && report.results.length > 0 && (
            <>
              {!report.scrape_enabled && (
                <div className="rounded-md border border-dashed border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
                  Showing suppliers with public pricing only. Enable "Search public supplier sites" to pull live web evidence (slower). Suppliers without public pricing will still show as "contact supplier".
                </div>
              )}
              {report.results.map((item) => (
                <RawMaterialBlock key={item.ingredient_id} item={item} />
              ))}
            </>
          )}
        </div>

        {report && (
          <div className="flex items-center justify-between pt-2 text-[11px] text-muted-foreground">
            <span>
              Source: <Badge variant="outline" className="text-[10px]">raw-material compliance checker</Badge>
            </span>
            <span>
              Finished product id: {report.finished_product.product_id}
            </span>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
