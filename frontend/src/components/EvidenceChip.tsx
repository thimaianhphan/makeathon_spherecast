import { Building2, ShieldCheck, Newspaper, BookOpen, Bot, MinusCircle } from "lucide-react";
import type { ComponentType, MouseEvent } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { SourcingEvidenceItem } from "@/data/types";

const SOURCE_CONFIG: Record<
  SourcingEvidenceItem["source_type"],
  { icon: ComponentType<{ className?: string }>; label: string; muted: boolean }
> = {
  supplier_site: { icon: Building2, label: "Supplier site", muted: false },
  cert_db: { icon: ShieldCheck, label: "Certification DB", muted: false },
  news: { icon: Newspaper, label: "News", muted: false },
  regulatory: { icon: BookOpen, label: "Regulatory ref", muted: false },
  llm_inference: { icon: Bot, label: "LLM inference", muted: true },
  no_evidence: { icon: MinusCircle, label: "No external source", muted: true },
};

interface EvidenceChipProps {
  item: SourcingEvidenceItem;
  active?: boolean;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
}

export function EvidenceChip({ item, active, onClick }: EvidenceChipProps) {
  const config = SOURCE_CONFIG[item.source_type];
  const Icon = config.icon;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-label={`${config.label}: ${item.source_label}, supports ${item.supports || "general"}`}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] border transition-colors ${
            active
              ? "border-primary bg-primary/10 text-primary"
              : config.muted
              ? "border-border bg-muted text-muted-foreground"
              : "border-border bg-background text-foreground hover:bg-muted"
          }`}
        >
          <Icon className="w-3 h-3 shrink-0" />
          <span className="truncate max-w-[120px]">{item.source_label}</span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">
        <p className="font-medium mb-1">{item.source_label}</p>
        <p className="text-muted-foreground">{item.excerpt}</p>
        <p className="text-muted-foreground mt-1">Confidence: {Math.round(item.confidence * 100)}%</p>
      </TooltipContent>
    </Tooltip>
  );
}
