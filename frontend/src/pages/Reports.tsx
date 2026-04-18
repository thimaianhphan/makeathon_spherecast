import { AppLayout } from "@/components/AppLayout";
import { ReportSummary } from "@/components/ReportSummary";
import * as api from "@/api/client";
import { useEffect, useState } from "react";
import type { CascadeSummary, CascadeReport } from "@/data/types";
import { ChevronDown, ChevronUp, Loader2, Printer } from "lucide-react";

const Reports = () => {
  const [reports, setReports] = useState<CascadeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeReport, setActiveReport] = useState<CascadeReport | null>(null);
  const [printing, setPrinting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reportCache, setReportCache] = useState<Record<string, CascadeReport>>({});

  useEffect(() => {
    api.getCascades()
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const loadReport = async (reportId: string) => {
    if (reportCache[reportId]) return reportCache[reportId];
    const report = await api.getCascadeReport(reportId);
    setReportCache((prev) => ({ ...prev, [reportId]: report }));
    return report;
  };

  const handlePrint = async (reportId: string) => {
    setPrinting(true);
    try {
      const report = await loadReport(reportId);
      setActiveReport(report);
      setTimeout(() => window.print(), 50);
    } finally {
      setTimeout(() => setPrinting(false), 500);
    }
  };

  const handleToggle = async (reportId: string) => {
    if (expandedId === reportId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(reportId);
    try {
      await loadReport(reportId);
    } catch {
      // ignore load errors
    }
  };

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Cascade Reports</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Historical cascades — select a report to print
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </div>
        )}

        {!loading && reports.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <p className="text-sm text-muted-foreground font-mono">
              No cascade history yet. Run a cascade to generate reports.
            </p>
          </div>
        )}

        {reports.length > 0 && (
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border text-sm font-semibold">
              Past Cascades
            </div>
            <div className="divide-y divide-border/50">
              {reports.map((r) => {
                const isExpanded = expandedId === r.report_id;
                const expandedReport = reportCache[r.report_id];
                return (
                  <div key={r.report_id} className="px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-foreground truncate">{r.intent}</div>
                        <div className="text-[10px] text-muted-foreground font-mono">
                          {r.report_id} · {r.initiated_at}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono">
                          Cost: EUR {r.total_cost_eur?.toLocaleString() || "—"} ·
                          Profit: EUR {r.total_profit_eur?.toLocaleString() || "—"} ·
                          Margin: {r.margin_pct?.toFixed(2) ?? "—"}%
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggle(r.report_id)}
                          className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-border text-xs font-mono hover:bg-secondary"
                        >
                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          Details
                        </button>
                        <button
                          onClick={() => handlePrint(r.report_id)}
                          disabled={printing}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-mono hover:bg-primary/90 disabled:opacity-50"
                        >
                          <Printer className="w-3 h-3" />
                          Print
                        </button>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="mt-4 border-t border-border/50 pt-4">
                        {!expandedReport && (
                          <div className="text-xs text-muted-foreground font-mono">Loading report...</div>
                        )}
                        {expandedReport && <ReportSummary report={expandedReport} />}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="print-only">
        {activeReport && <ReportSummary report={activeReport} />}
      </div>
    </AppLayout>
  );
};

export default Reports;
