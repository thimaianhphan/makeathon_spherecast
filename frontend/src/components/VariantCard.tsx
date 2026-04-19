import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreBar } from "@/components/ScoreBar";
import { EvidenceChip } from "@/components/EvidenceChip";
import { buildEvidenceKey } from "@/components/EvidencePanel";
import type { VariantCard as VariantCardType, SourcingEvidenceItem } from "@/data/types";

// ── Score pill ────────────────────────────────────────────────────────────────

function scorePillStyle(score: number, decision: VariantCardType["judge_decision"]): string {
  if (score >= 75 && decision === "accept") return "bg-green-100 text-green-700 border-green-200";
  if (decision === "reject" || score < 50) return "bg-red-100 text-red-700 border-red-200";
  return "bg-amber-100 text-amber-700 border-amber-200";
}

interface KeepCurrentCardProps {
  ingredientName: string;
  currentSupplierName: string | null;
  reason: string | null;
}

// ── Keep current card ─────────────────────────────────────────────────────────

export function KeepCurrentCard({ ingredientName, currentSupplierName, reason }: KeepCurrentCardProps) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">Keep current (no change)</p>
      </div>
      <p className="text-xs text-foreground mb-1.5">{ingredientName}</p>
      <p className="text-[11px] text-muted-foreground mb-2">
        Current supplier: {currentSupplierName ?? "Not available"}
      </p>
      <p className="text-xs text-muted-foreground">
        {reason ?? "No substitution recommended - current ingredient remains the safest option."}
      </p>
    </div>
  );
}

// ── Variant card ──────────────────────────────────────────────────────────────

interface VariantCardProps {
  variant: VariantCardType;
  isSelected: boolean;
  isHovered: boolean;
  activeEvidenceKey?: string | null;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onSelect: () => void;
  onEvidenceClick: (item: SourcingEvidenceItem, key: string) => void;
}

export function VariantCard({
  variant,
  isSelected,
  isHovered,
  activeEvidenceKey,
  onMouseEnter,
  onMouseLeave,
  onSelect,
  onEvidenceClick,
}: VariantCardProps) {
  const { scores, score_rationales, judge_decision, evidence } = variant;
  const pillStyle = scorePillStyle(scores.composite, judge_decision);

  const isNeedsReview = judge_decision === "needs_review";
  const isReject = judge_decision === "reject";

  const borderClass = isSelected
    ? "border-primary ring-1 ring-primary"
    : isNeedsReview
    ? "border-amber-300"
    : isReject
    ? "border-red-200"
    : "border-border";

  return (
    <div
      className={`rounded-lg border bg-card p-4 transition-shadow cursor-pointer ${borderClass} ${
        isHovered ? "shadow-md" : ""
      }`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onSelect}
      role="article"
      aria-label={`Variant ${variant.rank}: ${variant.substitute_name}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <Badge variant="outline" className="text-[10px] shrink-0">
            #{variant.rank}
          </Badge>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground leading-tight truncate">
              {variant.substitute_name}
            </p>
            <p className="text-xs text-muted-foreground truncate">{variant.supplier_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded border text-sm font-bold ${pillStyle}`}
            aria-label={`Composite score ${scores.composite}, ${judge_decision}`}
          >
            {scores.composite}
          </span>
        </div>
      </div>

      {/* Score bars — compliance widest, quality medium, price narrower */}
      <div className="space-y-3 mb-3">
        <ScoreBar
          label="Compliance"
          score={scores.compliance}
          rationale={score_rationales.compliance}
          relativeWidth={1}
        />
        <ScoreBar
          label="Quality"
          score={scores.quality}
          rationale={score_rationales.quality}
          relativeWidth={0.8}
        />
        <ScoreBar
          label="Price"
          score={variant.price_known ? scores.price : 50}
          rationale={score_rationales.price}
          relativeWidth={0.65}
          disclaimer={!variant.price_known ? "Unverified" : undefined}
        />
      </div>

      {/* Evidence chips */}
      {evidence.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {evidence.map((ev, i) => {
            const evidenceKey = buildEvidenceKey(ev);
            return (
              <EvidenceChip
                key={`${evidenceKey}-${i}`}
                item={ev}
                active={activeEvidenceKey === evidenceKey}
                onClick={(event) => {
                  event.stopPropagation();
                  onEvidenceClick(ev, evidenceKey);
                }}
              />
            );
          })}
        </div>
      )}

      {/* Tradeoff line */}
      {variant.tradeoff_summary && (
        <p className="text-[11px] text-muted-foreground mb-3 italic">
          {variant.tradeoff_summary}
        </p>
      )}

      {/* Price unverified notice */}
      {variant.price_source_label && (
        <p className="text-[11px] text-muted-foreground mb-2">
          Price source: <span className="font-medium text-foreground">{variant.price_source_label}</span>
        </p>
      )}
      {!variant.price_known && (
        <p className="text-[11px] text-amber-700 mb-3">
          Price unverified - incumbent-relative delta unavailable
        </p>
      )}

      {/* Action */}
      <Button
        size="sm"
        variant={isSelected ? "default" : "outline"}
        className="w-full text-xs"
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
      >
        {isSelected ? "Selected" : "Select this variant"}
      </Button>
    </div>
  );
}
