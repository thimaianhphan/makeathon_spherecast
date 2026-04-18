import { AppLayout } from "@/components/AppLayout";
import * as api from "@/api/client";
import { useState, useEffect, useMemo } from "react";
import type { GraphNode, GraphEdge } from "@/data/types";
import { Loader2 } from "lucide-react";
import { useCascadeStore } from "@/state/cascadeStore";

const roleColorMap: Record<string, string> = {
  Supplier: "hsl(210, 85%, 50%)",
  "Tier-1 Supplier": "hsl(210, 85%, 50%)",
  "Tier-2 Supplier": "hsl(190, 70%, 45%)",
  Manufacturer: "hsl(0, 0%, 20%)",
  Logistics: "hsl(40, 90%, 48%)",
  "Logistics Coordinator": "hsl(40, 90%, 48%)",
  Retailer: "hsl(0, 60%, 35%)",
  Procurement: "hsl(0, 85%, 46%)",
  "Procurement Orchestrator": "hsl(0, 85%, 46%)",
  "Compliance Auditor": "hsl(130, 60%, 40%)",
  Intelligence: "hsl(270, 60%, 50%)",
};

const edgeTypeColors: Record<string, string> = {
  discovery: "hsl(210, 85%, 50%)",
  negotiation: "hsl(0, 0%, 30%)",
  material: "hsl(40, 90%, 48%)",
  coordination: "hsl(0, 60%, 40%)",
  delivery: "hsl(40, 70%, 42%)",
  execution: "hsl(0, 85%, 46%)",
  quote: "hsl(50, 80%, 45%)",
  compliance: "hsl(130, 60%, 40%)",
  logistics: "hsl(40, 90%, 48%)",
  procurement: "hsl(0, 85%, 46%)",
};

function layoutNodes(nodes: GraphNode[]): (GraphNode & { x: number; y: number })[] {
  // Simple circular layout
  const cx = 400, cy = 260, radius = 180;
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return {
      ...n,
      x: n.x ?? Math.round(cx + radius * Math.cos(angle)),
      y: n.y ?? Math.round(cy + radius * Math.sin(angle)),
    };
  });
}

const SupplyGraph = () => {
  const { report, setReport } = useCascadeStore();
  const [loading, setLoading] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  useEffect(() => {
    if (report) {
      setLoading(false);
      return;
    }
    api.getReport()
      .then(setReport)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [report, setReport]);

  const nodes = useMemo(
    () => layoutNodes(report?.graph_nodes || []),
    [report],
  );

  const edges: GraphEdge[] = report?.graph_edges || [];

  const getNodePos = (id: string) => nodes.find((n) => n.id === id);
  const hovered = nodes.find((n) => n.id === hoveredNode);

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Supply Graph</h1>
          <p className="text-sm text-muted-foreground font-mono mt-1">
            Dynamic dependency graph — Agent network topology & material flows
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-primary animate-spin" />
          </div>
        )}

        {!loading && nodes.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <p className="text-sm text-muted-foreground font-mono">
              No graph data available. Complete a cascade from the Dashboard to generate the supply network graph.
            </p>
          </div>
        )}

        {nodes.length > 0 && (
          <>
            {/* Legend */}
            <div className="flex flex-wrap gap-4">
              {[...new Set(nodes.map((n) => n.role))].map((role) => (
                <div key={role} className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: roleColorMap[role] || "#888" }}
                  />
                  <span className="text-xs text-muted-foreground font-mono">{role}</span>
                </div>
              ))}
            </div>

            {/* Graph Canvas */}
            <div className="relative rounded-lg border border-border bg-card overflow-hidden">
              {hovered && (
                <div className="absolute right-6 top-6 rounded-md border border-border bg-background/90 p-3 text-xs font-mono shadow-md">
                  <div className="font-semibold text-foreground">{hovered.label}</div>
                  <div className="text-muted-foreground">{hovered.role}</div>
                  <div className="mt-1 text-muted-foreground">
                    Trust: {hovered.trust_score !== undefined ? `${Math.round(hovered.trust_score * 100)}%` : "—"}
                  </div>
                  <div className="text-muted-foreground">
                    Risk: {hovered.risk_score !== undefined ? hovered.risk_score.toFixed(2) : "—"}
                  </div>
                </div>
              )}
              <svg viewBox="0 0 800 520" className="w-full h-auto" style={{ minHeight: 420 }}>
                {/* Edges */}
                {edges.map((edge) => {
                  const from = getNodePos(edge.from);
                  const to = getNodePos(edge.to);
                  if (!from || !to) return null;
                  const color = edgeTypeColors[edge.type] || "hsl(222, 30%, 25%)";
                  const isHighlighted = hoveredNode === edge.from || hoveredNode === edge.to;
                  return (
                    <g key={`${edge.from}-${edge.to}-${edge.type}`}>
                      <line
                        x1={from.x}
                        y1={from.y}
                        x2={to.x}
                        y2={to.y}
                        stroke={color}
                        strokeWidth={isHighlighted ? 2.5 : 1.5}
                        strokeOpacity={isHighlighted ? 0.9 : 0.4}
                        strokeDasharray={edge.type === "discovery" ? "6 3" : undefined}
                      />
                      <text
                        x={(from.x + to.x) / 2}
                        y={(from.y + to.y) / 2 - 8}
                        textAnchor="middle"
                        fill="hsl(215, 20%, 55%)"
                        fontSize="9"
                        fontFamily="JetBrains Mono, monospace"
                        opacity={isHighlighted ? 1 : 0.6}
                      >
                        {edge.label}
                      </text>
                    </g>
                  );
                })}

                {/* Nodes */}
                {nodes.map((node) => {
                  const color = roleColorMap[node.role] || node.color || "#888";
                  const isHovered = hoveredNode === node.id;
                  return (
                    <g
                      key={node.id}
                      onMouseEnter={() => setHoveredNode(node.id)}
                      onMouseLeave={() => setHoveredNode(null)}
                      className="cursor-pointer"
                    >
                      {isHovered && (
                        <circle cx={node.x} cy={node.y} r={32} fill={color} opacity={0.15} />
                      )}
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={22}
                        fill="hsl(0, 0%, 100%)"
                        stroke={color}
                        strokeWidth={isHovered ? 2.5 : 1.5}
                        strokeOpacity={isHovered ? 1 : 0.6}
                      />
                      <circle cx={node.x} cy={node.y} r={6} fill={color} opacity={0.8} />
                      <text
                        x={node.x}
                        y={node.y + 36}
                        textAnchor="middle"
                        fill="hsl(0, 0%, 15%)"
                        fontSize="10"
                        fontWeight="600"
                        fontFamily="Inter, sans-serif"
                      >
                        {node.label.length > 20 ? node.label.slice(0, 18) + "..." : node.label}
                      </text>
                      <text
                        x={node.x}
                        y={node.y + 50}
                        textAnchor="middle"
                        fill={color}
                        fontSize="8"
                        fontFamily="JetBrains Mono, monospace"
                        style={{ textTransform: "uppercase" }}
                      >
                        {node.role}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            {/* Edge Legend */}
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="text-xs font-semibold text-foreground font-mono uppercase tracking-wider mb-3">
                Edge Types
              </h3>
              <div className="flex flex-wrap gap-4">
                {[...new Set(edges.map((e) => e.type))].map((type) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="w-6 h-px" style={{ backgroundColor: edgeTypeColors[type] || "#888" }} />
                    <span className="text-[10px] text-muted-foreground font-mono capitalize">{type}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default SupplyGraph;
