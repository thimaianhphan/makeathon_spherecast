import { useEffect, useRef } from "react";
import {
  Building2,
  ShieldCheck,
  Newspaper,
  BookOpen,
  Bot,
  MinusCircle,
  ExternalLink,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import type { SourcingEvidenceItem, VariantCard } from "@/data/types";

const SOURCE_CONFIG = {
  supplier_site: { icon: Building2, label: "Supplier site" },
  cert_db: { icon: ShieldCheck, label: "Certification DB" },
  news: { icon: Newspaper, label: "News" },
  regulatory: { icon: BookOpen, label: "Regulatory ref" },
  llm_inference: { icon: Bot, label: "LLM inference" },
  no_evidence: { icon: MinusCircle, label: "No external source" },
} as const;

export function buildEvidenceKey(item: SourcingEvidenceItem): string {
  return [
    item.source_type,
    item.source_label,
    item.supports || "general",
    item.url ?? "",
    item.fetched_at,
  ].join("|");
}

function confidenceColor(score: number): string {
  if (score >= 75) return "bg-green-500";
  if (score >= 50) return "bg-amber-400";
  return "bg-red-400";
}

function EvidenceRow({
  item,
  active,
  rowRef,
}: {
  item: SourcingEvidenceItem;
  active: boolean;
  rowRef: (node: HTMLDivElement | null) => void;
}) {
  const config = SOURCE_CONFIG[item.source_type];
  const Icon = config.icon;
  const isLlmOnly = item.source_type === "llm_inference" || item.source_type === "no_evidence";
  const rawConfidencePct = Math.round(item.confidence * 100);
  const shownConfidencePct = isLlmOnly ? Math.min(rawConfidencePct, 60) : rawConfidencePct;

  return (
    <div
      ref={rowRef}
      tabIndex={-1}
      className={`rounded-md p-2 transition-colors ${
        active ? "bg-primary/10 ring-1 ring-primary/30" : ""
      } ${isLlmOnly ? "opacity-80" : ""}`}
      aria-label={`Evidence: ${item.source_label}, confidence ${shownConfidencePct} percent`}
    >
      <div className="flex items-start gap-2 mb-1">
        <Icon className="w-3.5 h-3.5 mt-0.5 text-muted-foreground shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-foreground">{item.source_label}</span>
            <span className="text-[10px] text-muted-foreground">{config.label}</span>
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{item.excerpt}</p>

          <div className="mt-2 flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground">Confidence</span>
            <div
              className="h-1.5 w-24 rounded-full bg-muted overflow-hidden"
              role="progressbar"
              aria-label={`Evidence confidence ${shownConfidencePct} out of 100`}
              aria-valuenow={shownConfidencePct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className={`h-full ${confidenceColor(shownConfidencePct)}`}
                style={{ width: `${shownConfidencePct}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">{shownConfidencePct}%</span>
          </div>

          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-2 text-[11px] font-mono text-primary hover:underline break-all"
            >
              <ExternalLink className="w-3 h-3 shrink-0" />
              {item.url}
            </a>
          ) : (
            <p className="mt-2 text-[11px] text-muted-foreground italic">
              No external source - LLM inference only
            </p>
          )}

          <p className="text-[10px] text-muted-foreground mt-1 font-mono">
            Fetched {new Date(item.fetched_at).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

interface EvidencePanelProps {
  variant: VariantCard | null;
  activeEvidenceKey?: string | null;
}

export function EvidencePanel({ variant, activeEvidenceKey }: EvidencePanelProps) {
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!activeEvidenceKey) return;
    const target = rowRefs.current[activeEvidenceKey];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus({ preventScroll: true });
  }, [activeEvidenceKey]);

  if (!variant) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm px-6 text-center">
        Hover a variant to see its sources.
      </div>
    );
  }

  const groupedEvidence = new Map<string, SourcingEvidenceItem[]>();
  for (const item of variant.evidence) {
    const key = item.supports || "general";
    const existing = groupedEvidence.get(key) ?? [];
    existing.push(item);
    groupedEvidence.set(key, existing);
  }

  if (!variant.evidence.length) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">
          Evidence for {variant.substitute_name}
        </h3>
        <p className="text-sm text-muted-foreground">No evidence recorded for this variant.</p>
      </div>
    );
  }

  return (
    <div className="p-4 overflow-y-auto">
      <h3 className="text-sm font-semibold text-foreground mb-1">
        Evidence for {variant.substitute_name}
      </h3>
      <p className="text-[11px] text-muted-foreground mb-3">
        {variant.evidence.length} source{variant.evidence.length !== 1 ? "s" : ""}
      </p>

      {Array.from(groupedEvidence.entries()).map(([supportKey, items], groupIndex) => (
        <div key={supportKey} className="mb-2 last:mb-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
            {(supportKey || "general").replace(/_/g, " ")}
          </p>

          {items.map((item, itemIndex) => {
            const key = buildEvidenceKey(item);
            return (
              <div key={key}>
                <EvidenceRow
                  item={item}
                  active={activeEvidenceKey === key}
                  rowRef={(node) => {
                    rowRefs.current[key] = node;
                  }}
                />
                {itemIndex < items.length - 1 && <Separator />}
              </div>
            );
          })}

          {groupIndex < groupedEvidence.size - 1 && <Separator className="my-2" />}
        </div>
      ))}
    </div>
  );
}
