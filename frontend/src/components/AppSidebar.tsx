import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import {
  Home,
  Clock,
  ChevronLeft,
  ChevronRight,
  Layers,
} from "lucide-react";
import { useState } from "react";

const navItems = [
  { title: "Analyze", url: "/", icon: Home },
  { title: "History", url: "/history", icon: Clock },
];

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-64"} sticky top-0 flex h-screen flex-col border-r border-border bg-sidebar transition-all duration-300 shrink-0`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Layers className="w-4 h-4 text-primary" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <h1 className="text-sm font-bold text-foreground tracking-tight">Agnes</h1>
            <p className="text-[10px] text-muted-foreground tracking-wide uppercase">
              Ingredient Variant Explorer
            </p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.url ||
            (item.url === "/" && location.pathname.startsWith("/analyze"));
          return (
            <NavLink
              key={item.url}
              to={item.url}
              end={item.url === "/"}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all ${
                isActive
                  ? ""
                  : "text-sidebar-foreground hover:text-foreground hover:bg-sidebar-accent"
              }`}
              activeClassName="bg-primary/10 text-primary font-medium"
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span>{item.title}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-border text-muted-foreground hover:text-foreground transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
