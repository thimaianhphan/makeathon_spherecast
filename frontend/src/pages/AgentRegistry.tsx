import { AppLayout } from "@/components/AppLayout";
import { RoleBadge } from "@/components/RoleBadge";
import * as api from "@/api/client";
import { useState, useEffect } from "react";
import type { AgentFact } from "@/data/types";
import { Globe, Shield, Radio, FileText, Loader2 } from "lucide-react";

const AgentRegistry = () => {
  const [agents, setAgents] = useState<AgentFact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listAgents()
      .then(setAgents)
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Agent Registry</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Agent discovery layer — AgentFacts metadata & capabilities
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </div>
        )}

        {!loading && agents.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <p className="text-sm text-muted-foreground font-mono">
              No agents registered. Trigger a cascade from the Dashboard to populate the registry.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {agents.map((agent) => (
            <div
              key={agent.agent_id}
              className="rounded-lg border border-border bg-card hover:glow-border transition-all duration-300"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-border/50">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="text-lg font-bold text-primary font-mono">
                        {agent.name.charAt(0)}
                      </span>
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-success border-2 border-card" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-foreground">{agent.name}</h3>
                    <p className="text-[10px] text-muted-foreground font-mono">{agent.agent_id}</p>
                  </div>
                </div>
                <RoleBadge role={agent.role} />
              </div>

              {/* Body */}
              <div className="px-5 py-4 space-y-3">
                {/* Description */}
                {agent.description && (
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {agent.description}
                  </p>
                )}

                {/* Capabilities */}
                <div>
                  <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider mb-1.5">
                    Services
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {agent.capabilities.services.slice(0, 6).map((svc) => (
                      <span
                        key={svc}
                        className="px-2 py-0.5 text-[10px] font-mono rounded bg-secondary text-secondary-foreground"
                      >
                        {svc}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Metadata Grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center gap-2">
                    <Globe className="w-3 h-3 text-muted-foreground" />
                    <div>
                      <p className="text-[10px] text-muted-foreground font-mono">Region</p>
                      <p className="text-xs text-foreground">
                        {agent.location?.shipping_regions?.[0] || agent.location?.headquarters?.country || "—"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <FileText className="w-3 h-3 text-muted-foreground" />
                    <div>
                      <p className="text-[10px] text-muted-foreground font-mono">Country</p>
                      <p className="text-xs text-foreground">
                        {agent.identity?.registration_country || agent.location?.headquarters?.country || "—"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Shield className="w-3 h-3 text-muted-foreground" />
                    <div>
                      <p className="text-[10px] text-muted-foreground font-mono">Trust Score</p>
                      <p className="text-xs text-foreground font-bold">
                        {agent.trust ? `${Math.round(agent.trust.trust_score * 100)}%` : "—"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Radio className="w-3 h-3 text-muted-foreground" />
                    <div>
                      <p className="text-[10px] text-muted-foreground font-mono">Products</p>
                      <p className="text-xs text-foreground">
                        {agent.capabilities.products.length} items
                      </p>
                    </div>
                  </div>
                </div>

                {/* Certifications */}
                {agent.certifications.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {agent.certifications.map((cert, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 text-[10px] font-mono rounded bg-success/10 text-success border border-success/20"
                      >
                        {cert.type}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-5 py-2.5 border-t border-border/50 bg-secondary/20">
                <span className="text-[10px] text-muted-foreground font-mono">
                  Status: {agent.status}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono">
                  {agent.trust?.past_contracts || 0} past contracts
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
};

export default AgentRegistry;
