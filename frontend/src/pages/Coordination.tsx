import { AppLayout } from "@/components/AppLayout";
import { EventRow } from "@/components/EventRow";
import { useSSE } from "@/hooks/useSSE";
import * as api from "@/api/client";
import { useState, useEffect, useCallback } from "react";
import type { AgentFact, CatalogueProduct } from "@/data/types";
import { useCascadeStore } from "@/state/cascadeStore";
import { Radio, Zap, CheckCircle, Clock, AlertCircle, Play, Loader2, Square } from "lucide-react";

const PIPELINE_STAGES = [
  "Intent Parsed",
  "Discovery",
  "Quotes",
  "Negotiation",
  "Compliance",
  "Logistics",
  "Orders",
  "Reputation",
  "Reporting",
];

const Coordination = () => {
  const [agents, setAgents] = useState<AgentFact[]>([]);
  const [triggering, setTriggering] = useState(false);
  const { messages, connected, connect, disconnect, clear } = useSSE();
  const { progress, report, setProgress, setReport, controls, setControls } = useCascadeStore();
  const [catalogue, setCatalogue] = useState<CatalogueProduct[]>([]);
  const selectedProductId = controls.productId;
  const quantity = controls.quantity;
  const budgetEur = controls.budgetEur;
  const desiredDeliveryDate = controls.desiredDeliveryDate;

  // Load agents
  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => {});
  }, []);

  useEffect(() => {
    api.getCatalogue()
      .then((items) => {
        setCatalogue(items);
        if (items.length && !selectedProductId) {
          setControls({ productId: items[0].product_id });
        }
      })
      .catch(() => {});
  }, []);

  // Poll progress
  useEffect(() => {
    if (!progress.running) return;
    const interval = setInterval(async () => {
      try {
        const p = await api.getProgress();
        setProgress(p);
        if (!p.running) {
          clearInterval(interval);
          api.getReport().then(setReport).catch(() => {});
          api.listAgents().then(setAgents).catch(() => {});
        }
      } catch { /* ignore */ }
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
        intent: hasProduct ? undefined : "Buy all parts required to assemble one Ferrari 296 GTB",
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

  // Compute which pipeline stages are done based on progress
  const completedStages = Math.floor((progress.progress / 100) * PIPELINE_STAGES.length);

  const selectedProduct = catalogue.find((c) => c.product_id === selectedProductId);

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">
              Coordination Console
            </h1>
            <p className="text-sm text-muted-foreground font-mono mt-1">
              Execution cascade monitor — Agent-to-Agent message flows & negotiation state
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="hidden md:block rounded-md border border-border bg-background px-2 py-1 text-[10px] font-mono"
              value={selectedProductId}
              onChange={(e) => setControls({ productId: e.target.value })}
              disabled={progress.running}
            >
              {catalogue.map((item) => (
                <option key={item.product_id} value={item.product_id}>
                  {item.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              className="hidden md:block w-20 rounded-md border border-border bg-background px-2 py-1 text-[10px] font-mono"
              value={quantity}
              onChange={(e) => setControls({ quantity: Math.max(1, Number(e.target.value)) })}
              disabled={progress.running}
            />
            <input
              type="number"
              min={1}
              className="hidden md:block w-28 rounded-md border border-border bg-background px-2 py-1 text-[10px] font-mono"
              value={budgetEur}
              onChange={(e) => setControls({ budgetEur: Math.max(1, Number(e.target.value)) })}
              disabled={progress.running}
            />
            <input
              type="date"
              className="hidden md:block rounded-md border border-border bg-background px-2 py-1 text-[10px] font-mono"
              value={desiredDeliveryDate}
              onChange={(e) => setControls({ desiredDeliveryDate: e.target.value })}
              disabled={progress.running}
            />
            {connected && (
              <button
                onClick={disconnect}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary border border-border text-xs font-mono text-muted-foreground hover:text-foreground transition-colors"
              >
                <Square className="w-3 h-3" />
                Disconnect
              </button>
            )}
            <button
              onClick={handleTrigger}
              disabled={triggering || progress.running}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-mono font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {triggering ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
              {progress.running ? "Running..." : "Trigger Cascade"}
            </button>
          </div>
        </div>

        {/* Cascade Status */}
        <div className="rounded-lg border border-primary/20 bg-card glow-border p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-foreground">
                  {progress.running ? "Active Cascade" : report ? "Cascade Complete" : "Ready to Launch"}
                </h2>
                <p className="text-[10px] text-muted-foreground font-mono">
                  Intent: {selectedProduct ? selectedProduct.name : "Ferrari 296 GTB"}
                </p>
              </div>
            </div>
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md ${
              progress.running
                ? "bg-primary/10 border border-primary/20"
                : report
                ? "bg-success/10 border border-success/20"
                : "bg-secondary border border-border"
            }`}>
              {progress.running ? (
                <Radio className="w-3 h-3 text-primary animate-pulse" />
              ) : report ? (
                <CheckCircle className="w-3 h-3 text-success" />
              ) : (
                <Clock className="w-3 h-3 text-muted-foreground" />
              )}
              <span className={`text-xs font-mono ${
                progress.running ? "text-primary" : report ? "text-success" : "text-muted-foreground"
              }`}>
                {progress.running ? `IN PROGRESS ${Math.round(progress.progress)}%` : report ? "COMPLETE" : "IDLE"}
              </span>
            </div>
          </div>

          {/* Progress bar */}
          {(progress.running || report) && (
            <div className="w-full bg-secondary rounded-full h-1.5 mb-4">
              <div
                className={`h-1.5 rounded-full transition-all duration-500 ${report ? "bg-success" : "bg-primary"}`}
                style={{ width: `${report ? 100 : progress.progress}%` }}
              />
            </div>
          )}

          {/* Pipeline stages */}
          <div className="flex items-center gap-1 overflow-x-auto pb-2">
            {PIPELINE_STAGES.map((stage, i) => {
              const done = i < completedStages || !!report;
              const active = i === completedStages && progress.running;
              const Icon = done ? CheckCircle : active ? Clock : AlertCircle;
              return (
                <div key={stage} className="flex items-center gap-1">
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[10px] font-mono shrink-0 ${
                      done
                        ? "bg-success/10 text-success border border-success/20"
                        : active
                        ? "bg-primary/10 text-primary border border-primary/30 animate-pulse"
                        : "bg-secondary text-muted-foreground border border-border"
                    }`}
                  >
                    <Icon className="w-3 h-3" />
                    {stage}
                  </div>
                  {i < PIPELINE_STAGES.length - 1 && (
                    <div className={`w-6 h-px ${done ? "bg-success/40" : "bg-border"}`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Message Log */}
          <div className="lg:col-span-2 rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border flex items-center gap-2">
              <Radio className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">Message Log</h2>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                {messages.length} events
              </span>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {messages.length === 0 && (
                <div className="px-4 py-8 text-center text-xs text-muted-foreground font-mono">
                  Trigger a cascade to see live agent messages.
                </div>
              )}
              {[...messages].reverse().map((msg) => (
                <EventRow
                  key={msg.message_id}
                  timestamp={new Date(msg.timestamp).toLocaleTimeString()}
                  from={msg.from_label}
                  to={msg.to_label}
                  type={msg.type}
                  message={msg.summary}
                  color={msg.color}
                  detail={msg.detail}
                />
              ))}
            </div>
          </div>

          {/* Participants */}
          <div className="rounded-lg border border-border bg-card">
            <div className="px-4 py-3 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">Cascade Participants</h2>
            </div>
            <div className="divide-y divide-border/50">
              {agents.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground font-mono">
                  No agents yet.
                </div>
              )}
              {agents.map((agent) => (
                <div key={agent.agent_id} className="px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full bg-success" />
                    <span className="text-sm font-medium text-foreground">{agent.name}</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground font-mono ml-4">
                    {agent.role} · {agent.location?.headquarters?.country || "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-mono ml-4">
                    Trust: {agent.trust ? `${Math.round(agent.trust.trust_score * 100)}%` : "—"} · Contracts: {agent.trust?.past_contracts || 0}
                  </p>
                </div>
              ))}
            </div>

            {/* Execution Summary from report */}
            {report && (
              <div className="px-4 py-3 border-t border-border bg-secondary/20">
                <h3 className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                  Execution Summary
                </h3>
                <div className="space-y-1 text-[10px] font-mono text-foreground">
                  {report.dashboard.hero_metrics.map((m, i) => (
                    <div key={i} className="flex justify-between">
                      <span className="text-muted-foreground">{m.label}</span>
                      <span>{m.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default Coordination;
