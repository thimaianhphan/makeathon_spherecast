import { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: ReactNode;
  trend?: string;
  variant?: "default" | "primary" | "accent" | "success";
}

const variantStyles = {
  default: "border-border",
  primary: "border-primary/20 glow-border",
  accent: "border-accent/20",
  success: "border-success/20",
};

export function MetricCard({ label, value, icon, trend, variant = "default" }: MetricCardProps) {
  return (
    <div className={`rounded-lg border bg-card p-4 ${variantStyles[variant]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          {label}
        </span>
        <div className="text-muted-foreground">{icon}</div>
      </div>
      <div className="text-2xl font-bold text-foreground font-mono">{value}</div>
      {trend && (
        <p className="text-xs text-success mt-1 font-mono">
          {trend}
        </p>
      )}
    </div>
  );
}
