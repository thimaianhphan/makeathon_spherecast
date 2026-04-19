import { AppLayout } from "@/components/AppLayout";
import { MetricCard } from "@/components/MetricCard";
import { EventRow } from "@/components/EventRow";
import { RoleBadge } from "@/components/RoleBadge";
import { useSSE } from "@/hooks/useSSE";
import * as api from "@/api/client";
import { useState, useEffect, useCallback } from "react";
import type { AgentFact, CascadeReport, CascadeProgress } from "@/data/types";
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
  Rss,
} from "lucide-react";
import { Link } from "react-router-dom";

const Dashboard = () => {
  const [agents, setAgents] = useState<AgentFact[]>([]);
  const [report, setReport] = useState<CascadeReport | null>(null);
  const [progress, setProgress] = useState<CascadeProgress>({ running: false, progress: 0 });
  const [triggering, setTriggering] = useState(false);
  const [pubsubStats, setPubsubStats] = useState<{ total_events: number; total_deliveries: number } | null>(null);
  const { messages, connected, connect, disconnect, clear } = useSSE();

  // Load agents, report, and progress on mount
  useEffect(() => {
    api.listAgents().then(setAgents).catch(() => {});
    api.getReport().then(setReport).catch(() => {});
    api.getProgress().then(setProgress).catch(() => {});
    api.getPubsubSummary().then((s: any) => setPubsubStats({ total_events: s.total_events || 0, total_deliveries: s.total_deliveries || 0 })).catch(() => {});
  }, []);

  // Poll progress while cascade is running
  useEffect(() => {
    if (!progress.running) return;
    const interval = setInterval(async () => {
      try {
        const p = await api.getProgress();
        setProgress(p);
        if (!p.running) {
          clearInterval(interval);
          // Cascade finished — fetch report, agents, pubsub
          api.getReport().then(setReport).catch(() => {});
          api.listAgents().then(setAgents).catch(() => {});
          api.getPubsubSummary().then((s: any) => setPubsubStats({ total_events: s.total_events || 0, total_deliveries: s.total_deliveries || 0 })).catch(() => {});
        }
      } catch {
        // ignore
      }
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

  // Derive metrics
  const agentCount = agents.length;
  const messageCount = messages.length;
  const heroMetrics = report?.dashboard?.hero_metrics;

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
              NANDA Supply Chain Agent Network — Real-time Overview
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

        {/* Trigger Button */}
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
                label="Pub-Sub Events"
                value={pubsubStats ? pubsubStats.total_events : 0}
                icon={<Rss className="w-4 h-4" />}
                variant="success"
                trend={pubsubStats && pubsubStats.total_deliveries > 0 ? `${pubsubStats.total_deliveries} deliveries` : "No events yet"}
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
