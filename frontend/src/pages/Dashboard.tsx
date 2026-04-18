import { AppLayout } from "@/components/AppLayout";
import { MetricCard } from "@/components/MetricCard";
import { EventRow } from "@/components/EventRow";
import { RoleBadge } from "@/components/RoleBadge";
import { ReportSummary } from "@/components/ReportSummary";
import { useSSE } from "@/hooks/useSSE";
import * as api from "@/api/client";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { AgentFact, CatalogueProduct, SupplierSummary } from "@/data/types";
import { useCascadeStore } from "@/state/cascadeStore";
import {
  Users,
  Radio,
  Zap,
  Clock,
  Activity,
  Shield,
  GitBranch,
  ArrowUpRight,
  Play,
  Loader2,
  Printer,
} from "lucide-react";
import { Link } from "react-router-dom";

const Dashboard = () => {
  const [agents, setAgents] = useState<AgentFact[]>([]);
  const [triggering, setTriggering] = useState(false);
  const { messages, connected, connect, clear } = useSSE();
  const { progress, report, setProgress, setReport, controls, setControls } = useCascadeStore();
  const [catalogue, setCatalogue] = useState<CatalogueProduct[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const selectedProductId = controls.productId;
  const quantity = controls.quantity;
  const budgetEur = controls.budgetEur;
  const desiredDeliveryDate = controls.desiredDeliveryDate;
  // Load agents on mount
  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => { });
  }, []);

  useEffect(() => {
    api.getCatalogue()
      .then((items) => {
        setCatalogue(items);
        if (items.length && !selectedProductId) {
          setControls({ productId: items[0].product_id });
        }
      })
      .catch(() => { });
    api.getSuppliers().then(setSuppliers).catch(() => { });
  }, [selectedProductId, setControls]);

  // Poll progress while cascade is running
  useEffect(() => {
    if (!progress.running) return;
    const interval = setInterval(async () => {
      try {
        const p = await api.getProgress();
        setProgress(p);
        if (!p.running) {
          clearInterval(interval);
          // Cascade finished — fetch report and updated agents
          api.getReport().then(setReport).catch(() => { });
          api.listAgents().then(setAgents).catch(() => { });
        }
      } catch {
        // ignore
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [progress.running, setProgress, setReport]);

  const handleTrigger = useCallback(async () => {
    setTriggering(true);
    setReport(null);
    clear();
    try {
      const hasProduct = Boolean(selectedProductId);
      await api.triggerCascade({
        intent: hasProduct ? undefined : "Consolidate ingredient sourcing across all CPG companies",
        budget_eur: budgetEur,
        product_id: hasProduct ? selectedProductId : undefined,
        quantity: Math.max(1, quantity),
        desired_delivery_date: desiredDeliveryDate || undefined,
      });
      setProgress({ running: true, progress: 0 });
      connect();
    } catch (err) {
      console.error("Trigger failed:", err);
    } finally {
      setTriggering(false);
    }
  }, [connect, clear, selectedProductId, budgetEur, quantity, desiredDeliveryDate, setProgress, setReport]);

  // Derive metrics
  const agentCount = agents.length;
  const messageCount = messages.length;
  const heroMetrics = report?.dashboard?.hero_metrics;
  const selectedProduct = useMemo(
    () => catalogue.find((c) => c.product_id === selectedProductId),
    [catalogue, selectedProductId],
  );

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              Network Dashboard
            </h1>
            <p className="text-sm text-muted-foreground font-mono mt-1">
              Supply Chain Agent Network — Real-time Overview
            </p>
          </div>
          <div className="flex items-center gap-3">
            {progress.running && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10 border border-primary/20">
                <Loader2 className="w-3 h-3 text-primary animate-spin" />
                <span className="text-xs font-mono text-primary">
                  CASCADE {Math.round(progress.progress)}%
                </span>
              </div>
            )}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md ${connected ? "bg-success/10 border border-success/20" : "bg-secondary border border-border"}`}>
              <span className={`w-2 h-2 rounded-full ${connected ? "bg-success animate-pulse" : "bg-muted-foreground"}`} />
              <span className={`text-xs font-mono ${connected ? "text-success" : "text-muted-foreground"}`}>
                {connected ? "STREAM CONNECTED" : "IDLE"}
              </span>
            </div>
          </div>
        </div>

        {/* Trigger Controls */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Product
              </label>
              <select
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                value={selectedProductId}
                onChange={(e) => setControls({ productId: e.target.value })}
                disabled={progress.running}
              >
                {catalogue.map((item) => (
                  <option key={item.product_id} value={item.product_id}>
                    {item.name}{item.description ? ` — ${item.description}` : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Quantity
              </label>
              <input
                type="number"
                min={1}
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                value={quantity}
                onChange={(e) => setControls({ quantity: Math.max(1, Number(e.target.value)) })}
                disabled={progress.running}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Budget (EUR)
              </label>
              <input
                type="number"
                min={1}
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                value={budgetEur}
                onChange={(e) => setControls({ budgetEur: Math.max(1, Number(e.target.value)) })}
                disabled={progress.running}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                Desired Delivery
              </label>
              <input
                type="date"
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-2 text-xs"
                value={desiredDeliveryDate}
                onChange={(e) => setControls({ desiredDeliveryDate: e.target.value })}
                disabled={progress.running}
              />
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="text-[10px] text-muted-foreground font-mono">
              {selectedProduct ? `Intent: Source ingredients for ${selectedProduct.name}` : "Select a product to build intent"}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => report && window.print()}
                disabled={!report}
                className="flex items-center gap-2 px-3 py-2 rounded-md border border-border text-xs font-mono hover:bg-secondary disabled:opacity-50"
              >
                <Printer className="w-3 h-3" />
                Print last run
              </button>
              <button
                onClick={handleTrigger}
                disabled={triggering || progress.running}
                className="flex items-center gap-2 px-5 py-2.5 rounded-md bg-primary text-primary-foreground font-mono text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {triggering ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {progress.running ? "Cascade Running..." : "Trigger Procurement Cascade"}
              </button>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        {progress.running && (
          <div className="w-full bg-secondary rounded-full h-2">
            <div
              className="bg-primary h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress.progress}%` }}
            />
          </div>
        )}

        {/* Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {heroMetrics && heroMetrics.length > 0 ? (
            heroMetrics.slice(0, 4).map((m, i) => (
              <MetricCard
                key={i}
                label={m.label}
                value={m.value}
                icon={<Activity className="w-4 h-4" />}
                trend={m.trend || undefined}
                variant={i === 0 ? "primary" : i === 2 ? "accent" : i === 3 ? "success" : "default"}
              />
            ))
          ) : (
            <>
              <MetricCard
                label="Registered Agents"
                value={agentCount}
                icon={<Users className="w-4 h-4" />}
                variant="primary"
                trend={agentCount > 0 ? "From backend registry" : "Trigger a cascade to start"}
              />
              <MetricCard
                label="Live Messages"
                value={messageCount}
                icon={<Radio className="w-4 h-4" />}
                trend={connected ? "Streaming" : "Idle"}
              />
              <MetricCard
                label="Cascade Status"
                value={progress.running ? "Running" : report ? "Complete" : "Ready"}
                icon={<Zap className="w-4 h-4" />}
                variant="accent"
              />
              <MetricCard
                label="Progress"
                value={`${Math.round(progress.progress)}%`}
                icon={<Clock className="w-4 h-4" />}
                variant="success"
              />
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agent Overview */}
          <div className="lg:col-span-1 rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                Agent Status
              </h2>
              <Link
                to="/agents"
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                View all <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="divide-y divide-border/50">
              {agents.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No agents registered yet. Trigger a cascade to populate the registry.
                </div>
              )}
              {agents.slice(0, 6).map((agent) => (
                <div
                  key={agent.agent_id}
                  className="flex items-center justify-between px-4 py-3 hover:bg-secondary/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full bg-success" />
                    <div>
                      <p className="text-sm font-medium text-foreground">{agent.name}</p>
                      <p className="text-[10px] text-muted-foreground font-mono">
                        {agent.location?.headquarters?.country || "—"} · Trust{" "}
                        {agent.trust ? `${Math.round(agent.trust.trust_score * 100)}%` : "—"}
                      </p>
                    </div>
                  </div>
                  <RoleBadge role={agent.role} />
                </div>
              ))}
            </div>
          </div>

          {/* Live Coordination Feed */}
          <div className="lg:col-span-2 rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" />
                Live Coordination Feed
                {messages.length > 0 && (
                  <span className="text-[10px] font-mono text-muted-foreground">
                    ({messages.length} messages)
                  </span>
                )}
              </h2>
              <Link
                to="/coordination"
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                Full view <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              {messages.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No messages yet. Trigger a cascade to see live agent communication.
                </div>
              )}
              {[...messages].reverse().slice(0, 20).map((msg) => (
                <EventRow
                  key={msg.message_id}
                  timestamp={new Date(msg.timestamp).toLocaleTimeString()}
                  from={msg.from_label}
                  to={msg.to_label}
                  type={msg.type}
                  message={msg.summary}
                  color={msg.color}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Profit + Policy + Intent */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-foreground mb-2">Profit Summary</h3>
            {!report?.profit_summary && (
              <p className="text-xs text-muted-foreground font-mono">Run a cascade to see profit metrics.</p>
            )}
            {report?.profit_summary && (
              <div className="space-y-1 text-xs font-mono">
                <div className="flex justify-between"><span>Total Revenue</span><span>EUR {report.profit_summary.total_revenue_eur.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Total Cost</span><span>EUR {report.profit_summary.total_cost_eur.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Total Profit</span><span>EUR {report.profit_summary.total_profit_eur.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Profit / Item</span><span>EUR {report.profit_summary.profit_per_item_eur.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Margin</span><span>{report.profit_summary.margin_pct.toFixed(2)}%</span></div>
              </div>
            )}
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-foreground mb-2">Policy Evaluation</h3>
            {!report?.policy_evaluation && (
              <p className="text-xs text-muted-foreground font-mono">No policy results yet.</p>
            )}
            {report?.policy_evaluation && (
              <div className="space-y-2 text-xs font-mono">
                <span className={`inline-block px-2 py-0.5 rounded ${report.policy_evaluation.compliant ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"}`}>
                  {report.policy_evaluation.compliant ? "Compliant" : "Non-compliant"}
                </span>
                {(report.policy_evaluation.explanations || []).slice(0, 3).map((exp, idx) => (
                  <div key={idx} className="text-muted-foreground">{exp}</div>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-foreground mb-2">Intent Expansion</h3>
            {!report?.intent_expansion && (
              <p className="text-xs text-muted-foreground font-mono">No intent expansion available.</p>
            )}
            {report?.intent_expansion && (
              <div className="space-y-2 text-xs font-mono">
                <div className="text-muted-foreground">Root: {report.intent_expansion.root_intent}</div>
                <div>Components: {report.intent_expansion.component_intents.length}</div>
                <div>Logistics: {report.intent_expansion.logistics_intents.length}</div>
                <div>Compliance: {report.intent_expansion.compliance_intents.length}</div>
              </div>
            )}
          </div>
        </div>

        {/* Event Log + Suppliers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">Event Log</h3>
            </div>
            <div className="max-h-[320px] overflow-y-auto">
              {!report?.event_log?.length && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No events yet.
                </div>
              )}
              {(report?.event_log || []).map((ev, idx) => (
                <div key={`${ev.type}-${idx}`} className="px-4 py-3 border-b border-border/50 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{ev.type}</span>
                    <span className="text-muted-foreground">{ev.stage}</span>
                  </div>
                  <div className="text-muted-foreground mt-1">
                    {Object.entries(ev.impact || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Suppliers</h3>
              <span className="text-[10px] text-muted-foreground font-mono">{suppliers.length} listed</span>
            </div>
            <div className="max-h-[320px] overflow-y-auto">
              {suppliers.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No suppliers loaded.
                </div>
              )}
              {suppliers.map((s) => (
                <div key={s.agent_id} className="px-4 py-3 border-b border-border/50">
                  <div className="text-sm font-semibold text-foreground">{s.name || s.agent_id}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">
                    {s.role} · {s.location?.headquarters?.city || "—"}{s.location?.headquarters?.country ? `, ${s.location.headquarters.country}` : ""}
                  </div>
                  <div className="text-[10px] text-muted-foreground font-mono">
                    Trust: {s.trust?.trust_score !== undefined ? `${Math.round(s.trust.trust_score * 100)}%` : "—"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Reputation + Intelligence */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">Reputation Leaderboard</h3>
            </div>
            <div className="max-h-[320px] overflow-y-auto">
              {!(report?.reputation_summary?.leaderboard?.length) && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No reputation data yet.
                </div>
              )}
              {(report?.reputation_summary?.leaderboard || []).map((r) => (
                <div key={r.agent_id} className="px-4 py-3 border-b border-border/50">
                  <div className="text-sm font-semibold text-foreground">{r.agent_name || r.agent_id}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">
                    Composite: {(r.composite_score * 100).toFixed(1)}% · Attestations: {r.total_attestations}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">Intelligence Feed</h3>
            </div>
            <div className="max-h-[320px] overflow-y-auto">
              {!(report?.intelligence_feed?.length) && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No intelligence signals yet.
                </div>
              )}
              {(report?.intelligence_feed || []).map((sig, idx) => (
                <div key={idx} className="px-4 py-3 border-b border-border/50">
                  <div className="text-sm font-semibold text-foreground">{sig.event.title}</div>
                  <div className="text-[10px] text-muted-foreground font-mono">
                    {sig.event.category} · {sig.event.severity} · {sig.recipient_count} recipients
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1">
                    {sig.event.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="print-only">
          {report && <ReportSummary report={report} />}
        </div>

        {/* Quick Actions */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-primary" />
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Link
              to="/coordination"
              className="flex items-center gap-3 px-4 py-3 rounded-md border border-border bg-secondary/30 hover:bg-secondary/60 transition-colors group"
            >
              <Zap className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">View Cascade</p>
                <p className="text-[10px] text-muted-foreground font-mono">
                  Monitor live execution
                </p>
              </div>
            </Link>
            <Link
              to="/agents"
              className="flex items-center gap-3 px-4 py-3 rounded-md border border-border bg-secondary/30 hover:bg-secondary/60 transition-colors"
            >
              <Users className="w-5 h-5 text-accent" />
              <div>
                <p className="text-sm font-medium text-foreground">Agent Registry</p>
                <p className="text-[10px] text-muted-foreground font-mono">
                  Browse registered agents
                </p>
              </div>
            </Link>
            <Link
              to="/graph"
              className="flex items-center gap-3 px-4 py-3 rounded-md border border-border bg-secondary/30 hover:bg-secondary/60 transition-colors"
            >
              <GitBranch className="w-5 h-5 text-success" />
              <div>
                <p className="text-sm font-medium text-foreground">Supply Graph</p>
                <p className="text-[10px] text-muted-foreground font-mono">
                  Explore supply network
                </p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default Dashboard;
