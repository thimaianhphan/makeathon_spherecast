interface ScoreBarProps {
  label: string;
  score: number;
  rationale: string;
  /** width fraction relative to other bars; 1.0 = full, 0.6 = narrower */
  relativeWidth?: number;
  disclaimer?: string;
}

export function ScoreBar({ label, score, rationale, relativeWidth = 1, disclaimer }: ScoreBarProps) {
  const clipped = Math.max(0, Math.min(100, score));
  const color =
    clipped >= 75 ? "bg-green-500" : clipped >= 50 ? "bg-amber-400" : "bg-red-400";
  const valueText = disclaimer ?? String(clipped);

  return (
    <div className="space-y-1" style={{ maxWidth: `${Math.round(relativeWidth * 100)}%` }}>
      <div className="flex items-center justify-between gap-4">
        <span className="text-xs font-medium text-foreground w-24 shrink-0">{label}</span>
        <span className="text-xs text-muted-foreground">{valueText}</span>
      </div>
      <div
        className="h-1.5 rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-label={disclaimer ? `${label} score unverified` : `${label} score ${clipped} out of 100`}
        aria-valuenow={clipped}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${clipped}%` }}
        />
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug">{rationale}</p>
    </div>
  );
}
