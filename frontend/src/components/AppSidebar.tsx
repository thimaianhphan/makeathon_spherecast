import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  GitBranch,
  Radio,
  FileText,
  Zap,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState, useEffect } from "react";
import * as api from "@/api/client";

const navItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Agent Registry", url: "/agents", icon: Users },
  { title: "Supply Graph", url: "/graph", icon: GitBranch },
  { title: "Coordination", url: "/coordination", icon: Radio },
  { title: "Reports", url: "/reports", icon: FileText },
];

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const [agentCount, setAgentCount] = useState(0);

  useEffect(() => {
    api.listAgents()
      .then((agents) => setAgentCount(agents.length))
      .catch(() => { });
  }, []);

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-64"
        } sticky top-0 flex h-screen flex-col border-r border-border bg-sidebar transition-all duration-300 shrink-0`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center glow-primary shrink-0">
          <Zap className="w-4 h-4 text-primary" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <h1 className="text-sm font-bold text-foreground tracking-tight">Orchestr8</h1>
            <p className="text-[10px] text-muted-foreground font-mono tracking-wider uppercase">
              Inspired from NANDA Network
            </p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.url;
          return (
            <NavLink
              key={item.url}
              to={item.url}
              end
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all ${isActive
                ? ""
                : "text-sidebar-foreground hover:text-foreground hover:bg-sidebar-accent"
                }`}
              activeClassName="bg-primary/10 text-primary glow-border font-medium"
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.title}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Network Status */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-border">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse-glow" />
            <span className="text-xs text-muted-foreground font-mono">NETWORK ONLINE</span>
          </div>
          <div className="text-[10px] text-muted-foreground font-mono space-y-0.5">
            <div>Agents: {agentCount}</div>
            <div>Latency: —</div>
            <div>Uptime: —</div>
          </div>
        </div>
      )}

      {/* Collapse */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-border text-muted-foreground hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
