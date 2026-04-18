import { AppLayout } from "@/components/AppLayout";
import { EventRow } from "@/components/EventRow";
import { useSSE } from "@/hooks/useSSE";
import * as api from "@/api/client";
import { useState, useEffect, useCallback } from "react";
import type { AgentFact, CascadeProgress, CascadeReport } from "@/data/types";
import { Radio, Zap, CheckCircle, Clock, AlertCircle, Play, Loader2, Square, Rss } from "lucide-react";

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
  const [progress, setProgress] = useState<CascadeProgress>({ running: false, progress: 0 });
  const [report, setReport] = useState<CascadeReport | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [pubsubEvents, setPubsubEvents] = useState<Array<{ event_type: string; severity: string; source_agent: string; affected_agents: string[]; timestamp: string; details: string }>>([]);
  const [pubsubSubs, setPubsubSubs] = useState<Array<{ agent_id: string; agent_name: string; topics: string[] }>>([]);
  const { messages, connected, connect, disconnect, clear } = useSSE();

  // Load agents + pubsub data on mount
  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => {});
    api.getReport().then(setReport).catch(() => {});
    api.getPubsubEvents().then(setPubsubEvents).catch(() => {});
    api.getPubsubSummary().then((s: any) => setPubsubSubs(s.subscriptions || [])).catch(() => {});
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
          api.getPubsubEvents().then(setPubsubEvents).catch(() => {});
          api.getPubsubSummary().then((s: any) => setPubsubSubs(s.subscriptions || [])).catch(() => {});
        }
      } catch { /* ignore */ }
    }, 1000);
    return () => clearInterval(interval);
  }, [progress.running]);

  const handleTrigger = useCallback(async () => {
    setTriggering(true);
    setReport(null);
    clear();
    try {
      await api.triggerCascade(
        "Buy all parts required to assemble one Ferrari 296 GTB",
        500000,
      );
      setProgress({ running: true, progress: 0 });
      connect();
    } catch (err) {
      console.error("Trigger failed:", err);
    } finally {
      setTriggering(false);
    }
  }, [connect, clear]);

  // Compute which pipeline stages are done based on progress
  const completedStages = Math.floor((progress.progress / 100) * PIPELINE_STAGES.length);

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
                  Intent: "Procure V8 engine assembly components — Ferrari 296 GTB"
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
        {/* Pub-Sub: Disruption Events & Subscriptions */}
        {(pubsubEvents.length > 0 || pubsubSubs.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Disruption Events */}
            <div className="lg:col-span-2 rounded-lg border border-border bg-card">
              <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                <Rss className="w-4 h-4 text-orange-400" />
                <h2 className="text-sm font-semibold text-foreground">Disruption Events (Pub-Sub)</h2>
                <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                  {pubsubEvents.length} events broadcast
                </span>
              </div>
              <div className="max-h-[350px] overflow-y-auto divide-y divide-border/50">
                {pubsubEvents.map((evt, i) => {
                  const severityColor = evt.severity === "high" ? "text-red-400" : evt.severity === "medium" ? "text-orange-400" : "text-yellow-400";
                  const severityBg = evt.severity === "high" ? "bg-red-500/10 border-red-500/20" : evt.severity === "medium" ? "bg-orange-500/10 border-orange-500/20" : "bg-yellow-500/10 border-yellow-500/20";
                  return (
                    <div key={i} className="px-4 py-3 hover:bg-secondary/30 transition-colors">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase border ${severityBg} ${severityColor}`}>
                          {evt.severity}
                        </span>
                        <span className="text-sm font-medium text-foreground">
                          {evt.event_type.replace(/_/g, " ")}
                        </span>
                        <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ""}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground ml-1 mb-1">{evt.details}</p>
                      <div className="flex items-center gap-1 ml-1">
                        <span className="text-[10px] text-muted-foreground font-mono">Source:</span>
                        <span className="text-[10px] text-foreground font-mono">{evt.source_agent}</span>
                        <span className="text-[10px] text-muted-foreground font-mono ml-2">Delivered to:</span>
                        <span className="text-[10px] text-primary font-mono">{evt.affected_agents?.length || 0} agents</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Agent Subscriptions */}
            <div className="rounded-lg border border-border bg-card">
              <div className="px-4 py-3 border-b border-border">
                <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Rss className="w-4 h-4 text-primary" />
                  Agent Subscriptions
                </h2>
                <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                  {pubsubSubs.length} agents subscribed to disruption topics
                </p>
              </div>
              <div className="max-h-[350px] overflow-y-auto divide-y divide-border/50">
                {pubsubSubs.map((sub, i) => (
                  <div key={i} className="px-4 py-3">
                    <p className="text-sm font-medium text-foreground mb-1">{sub.agent_name}</p>
                    <div className="flex flex-wrap gap-1">
                      {sub.topics.map((topic) => (
                        <span
                          key={topic}
                          className="px-2 py-0.5 rounded text-[10px] font-mono bg-primary/10 text-primary border border-primary/20"
                        >
                          {topic.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Coordination;
