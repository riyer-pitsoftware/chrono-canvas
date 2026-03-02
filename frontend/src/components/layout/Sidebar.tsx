import { BarChart3, BookOpen, Download, FileSearch, Home, Image, LayoutDashboard, Settings, Shield, Users, Cpu, Scroll, Database, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHackathonMode } from "@/api/hooks/useConfig";

const defaultNavItems = [
  { label: "Home", href: "/", icon: Home },
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Timeline", href: "/timeline", icon: Scroll },
  { label: "Figures", href: "/figures", icon: Users },
  { label: "Generate", href: "/generate", icon: Image },
  { label: "Validate", href: "/validate", icon: Shield },
  { label: "Audit", href: "/audit", icon: FileSearch },
  { label: "Memory", href: "/memory", icon: Database },
  { label: "Export", href: "/export", icon: Download },
  { label: "Eval", href: "/eval", icon: BarChart3 },
  { label: "Admin", href: "/admin", icon: Settings },
];

// In hackathon mode, Story Director (Generate) is first, admin/eval items move to the end
const hackathonNavItems = [
  { label: "Story Director", href: "/generate?mode=creative_story", icon: Image },
  { label: "Home", href: "/", icon: Home },
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Timeline", href: "/timeline", icon: Scroll },
  { label: "Export", href: "/export", icon: Download },
  { label: "Figures", href: "/figures", icon: Users },
  { label: "Validate", href: "/validate", icon: Shield },
  { label: "Memory", href: "/memory", icon: Database },
  { label: "Audit", href: "/audit", icon: FileSearch },
  { label: "Eval", href: "/eval", icon: BarChart3 },
  { label: "Admin", href: "/admin", icon: Settings },
];

export function Sidebar({
  currentPath,
  onNavigate,
  collapsed,
  onToggle,
}: {
  currentPath: string;
  onNavigate: (path: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const hackathonMode = useHackathonMode();
  const navItems = hackathonMode ? hackathonNavItems : defaultNavItems;
  const guideActive = currentPath === "/guide";

  // For active-state matching, strip query params from both sides
  const currentPathname = currentPath.split("?")[0];

  return (
    <aside
      className={cn(
        "border-r border-[var(--border)] bg-[var(--card)] h-screen flex flex-col transition-[width] duration-200",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div className={cn("pb-4 flex items-center gap-2", collapsed ? "p-3 justify-center" : "p-6")}>
        <div className="flex items-center gap-2">
          <Cpu className="w-6 h-6" />
          {!collapsed && <span className="text-xl font-bold">ChronoCanvas</span>}
        </div>
        <button
          onClick={onToggle}
          className="ml-auto flex items-center justify-center rounded-md border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] transition-colors w-8 h-8"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
      <div className={cn("px-3", collapsed ? "flex flex-col items-center" : "px-6")}>
        <button
          onClick={() => onNavigate("/guide")}
          className={cn(
            "mt-3 w-full flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border relative overflow-hidden",
            guideActive
              ? "bg-[var(--accent)] border-[var(--border)] text-[var(--accent-foreground)]"
              : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)]",
            collapsed && "justify-center px-0",
          )}
          title="Guide"
        >
          {guideActive && (
            <span className="absolute left-1 top-1 bottom-1 w-1 rounded-full bg-[var(--primary)]" />
          )}
          <BookOpen className="w-3.5 h-3.5" />
          {!collapsed && "Guide"}
        </button>
      </div>
      <nav className={cn("flex-1 px-3", collapsed && "px-0 flex flex-col items-center")}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const itemPathname = item.href.split("?")[0];
          const active = currentPathname === itemPathname;
          return (
            <button
              key={item.href}
              onClick={() => onNavigate(item.href)}
              className={cn(
                "relative w-full flex items-center gap-3 py-2 rounded-md text-sm mb-1 transition-colors overflow-hidden",
                active
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)] font-medium"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)]",
                collapsed ? "justify-center px-0" : "pl-6 pr-3",
              )}
              title={item.label}
            >
              {active && (
                <span className="absolute left-1 top-1 bottom-1 w-1 rounded-full bg-[var(--primary)]" />
              )}
              <Icon className="w-4 h-4" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
