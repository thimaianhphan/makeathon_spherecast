import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clock3, ChevronRight, History as HistoryIcon } from "lucide-react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";

const HISTORY_KEY = "agnes:history";

interface HistoryEntry {
  id: number;
  sku: string;
  name: string;
  company_name: string;
  analyzed_at: string;
  accepted_count: number;
}

export default function History() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) {
      setEntries([]);
      return;
    }
    try {
      const parsed = JSON.parse(raw) as HistoryEntry[];
      setEntries(parsed);
    } catch {
      setEntries([]);
    }
  }, []);

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-foreground mb-2">Saved analyses</h1>
          <p className="text-sm text-muted-foreground">
            Re-open previous finished-good analyses from local cache.
          </p>
        </div>

        {entries.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-10 text-center">
            <HistoryIcon className="w-6 h-6 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm font-medium text-foreground mb-1">No analyses yet</p>
            <p className="text-xs text-muted-foreground mb-4">
              Run an analysis from the Analyze page and it will appear here.
            </p>
            <Button variant="outline" size="sm" onClick={() => navigate("/")}>Go to Analyze</Button>
          </div>
        )}

        {entries.length > 0 && (
          <div className="space-y-2">
            {entries.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => navigate(`/analyze/${entry.id}`)}
                className="w-full rounded-lg border border-border bg-card p-4 text-left hover:bg-muted/40 transition-colors"
                aria-label={`Open analysis ${entry.sku}`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground font-mono">{entry.sku}</p>
                    <p className="text-sm font-semibold text-foreground truncate">{entry.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{entry.company_name}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
                </div>
                <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1 font-mono">
                    <Clock3 className="w-3 h-3" />
                    {new Date(entry.analyzed_at).toLocaleString()}
                  </span>
                  <span>
                    {entry.accepted_count} accepted variant{entry.accepted_count === 1 ? "" : "s"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
