const roleColors: Record<string, string> = {
  Supplier: "bg-graph-supplier/15 text-graph-supplier border-graph-supplier/30",
  Manufacturer: "bg-graph-manufacturer/15 text-graph-manufacturer border-graph-manufacturer/30",
  Logistics: "bg-graph-logistics/15 text-graph-logistics border-graph-logistics/30",
  Retailer: "bg-graph-retailer/15 text-graph-retailer border-graph-retailer/30",
  Procurement: "bg-graph-procurement/15 text-graph-procurement border-graph-procurement/30",
};

const defaultColor = "bg-secondary text-secondary-foreground border-border";

export function RoleBadge({ role }: { role: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border ${roleColors[role] || defaultColor}`}>
      {role}
    </span>
  );
}
