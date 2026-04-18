import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

const typeIcons: Record<string, string> = {
  discovery: "🔍",
  response: "↩️",
  negotiation: "🤝",
  coordination: "📡",
  execution: "⚡",
  quote_request: "💰",
  quote_response: "📋",
  compliance_check: "✅",
  compliance_result: "🛡️",
  logistics_plan: "🚚",
  disruption_alert: "⚠️",
  order_confirmed: "📦",
  intelligence: "🧠",
  registration: "📝",
  info: "ℹ️",
};

const statusColors: Record<string, string> = {
  completed: "text-success",
  "in-progress": "text-primary",
  pending: "text-warning",
  failed: "text-destructive",
};

interface EventRowProps {
  timestamp: string;
  from: string;
  to: string;
  type: string;
  message: string;
  status?: string;
  color?: string;
  detail?: string;
}

export function EventRow({ timestamp, from, to, type, message, status, color, detail }: EventRowProps) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!detail;

  return (
    <div className="border-b border-border/50 hover:bg-secondary/30 transition-colors group">
      <div 
        className={`flex items-start gap-3 px-4 py-3 ${hasDetail ? "cursor-pointer" : ""}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <span className="text-[10px] text-muted-foreground font-mono mt-1 shrink-0 w-24">
          {timestamp}
        </span>
        <span className="text-sm shrink-0 mt-0.5">{typeIcons[type] || "📨"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-foreground">{from}</span>
            <span className="text-xs text-muted-foreground">→</span>
            <span className="text-xs font-semibold text-foreground">{to}</span>
            {status && (
              <span className={`text-[10px] font-mono uppercase ${statusColors[status] || "text-muted-foreground"}`}>
                [{status}]
              </span>
            )}
            {!status && color && (
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
            )}
          </div>
          <p className="text-xs text-muted-foreground font-mono leading-relaxed truncate group-hover:whitespace-normal">
            {message}
          </p>
        </div>
        {hasDetail && (
            <div className="shrink-0 mt-0.5 text-muted-foreground">
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </div>
        )}
      </div>
      {expanded && hasDetail && (
        <div className="px-14 pb-3 text-xs font-mono text-muted-foreground whitespace-pre-wrap pl-[72px] pr-4">
            {detail}
        </div>
      )}
    </div>
  );
}