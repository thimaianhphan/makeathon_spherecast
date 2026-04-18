import type { CascadeReport } from "@/data/types";

interface ReportSummaryProps {
  report: CascadeReport;
}

export function ReportSummary({ report }: ReportSummaryProps) {
  const profit = report.profit_summary;
  const costs = report.component_costs || [];
  const events = report.event_log || [];

  return (
    <div className="report-print p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Cascade Report</h1>
        <div className="text-xs text-muted-foreground font-mono">
          {report.report_id} · {report.initiated_at} · {report.status}
        </div>
        <div className="mt-2 text-sm">Intent: {report.intent}</div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="rounded border border-border p-3">
          <div className="text-xs text-muted-foreground font-mono mb-2">Totals</div>
          <div>Total Cost: EUR {report.execution_plan?.total_cost_eur?.toLocaleString() || "—"}</div>
          {profit && (
            <>
              <div>Total Revenue: EUR {profit.total_revenue_eur.toLocaleString()}</div>
              <div>Total Profit: EUR {profit.total_profit_eur.toLocaleString()}</div>
              <div>Margin: {profit.margin_pct.toFixed(2)}%</div>
            </>
          )}
        </div>
        <div className="rounded border border-border p-3">
          <div className="text-xs text-muted-foreground font-mono mb-2">Delivery Target</div>
          <div>Date: {report.delivery_target?.requested_date || "—"}</div>
          <div>Days: {report.delivery_target?.requested_days ?? "—"}</div>
        </div>
      </div>

      <div>
        <h2 className="text-sm font-semibold">Cost Breakdown</h2>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          {(report.dashboard?.cost_breakdown || []).map((item) => (
            <div key={item.label} className="flex justify-between border-b border-border/50 py-1">
              <span>{item.label}</span>
              <span>EUR {item.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-sm font-semibold">Component Costs</h2>
        {costs.length === 0 && (
          <div className="text-xs text-muted-foreground font-mono mt-2">No component costs available.</div>
        )}
        {costs.length > 0 && (
          <table className="w-full text-xs mt-2 border-collapse">
            <thead>
              <tr className="text-left border-b border-border">
                <th className="py-1">Supplier</th>
                <th className="py-1">Product</th>
                <th className="py-1">Qty</th>
                <th className="py-1">Unit EUR</th>
                <th className="py-1">Total EUR</th>
              </tr>
            </thead>
            <tbody>
              {costs.map((c) => (
                <tr key={`${c.supplier_id}-${c.product_name}`} className="border-b border-border/50">
                  <td className="py-1">{c.supplier_name}</td>
                  <td className="py-1">{c.product_name}</td>
                  <td className="py-1">{c.quantity}</td>
                  <td className="py-1">{c.unit_price_eur.toLocaleString()}</td>
                  <td className="py-1">{c.total_eur.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div>
        <h2 className="text-sm font-semibold">Disruptive Events</h2>
        {events.length === 0 && (
          <div className="text-xs text-muted-foreground font-mono mt-2">No disruptions recorded.</div>
        )}
        {events.length > 0 && (
          <ul className="mt-2 text-xs list-disc pl-5 space-y-1">
            {events.map((ev, idx) => (
              <li key={`${ev.type}-${idx}`}>
                {ev.type} ({ev.stage}) — {Object.entries(ev.impact || {}).map(([k, v]) => `${k}: ${v}`).join(", ")}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
