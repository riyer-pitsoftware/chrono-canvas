import { BookOpen, Download, FileSearch, Image, LayoutDashboard, Settings, Shield, Users, Cpu, Scroll } from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Timeline", href: "/timeline", icon: Scroll },
  { label: "Figures", href: "/figures", icon: Users },
  { label: "Generate", href: "/generate", icon: Image },
  { label: "Validate", href: "/validate", icon: Shield },
  { label: "Audit", href: "/audit", icon: FileSearch },
  { label: "Export", href: "/export", icon: Download },
  { label: "Admin", href: "/admin", icon: Settings },
];

export function Sidebar({ currentPath, onNavigate }: { currentPath: string; onNavigate: (path: string) => void }) {
  const guideActive = currentPath === "/guide";
  return (
    <aside className="w-64 border-r border-[var(--border)] bg-[var(--card)] h-screen flex flex-col">
      <div className="p-6 pb-4">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Cpu className="w-6 h-6" />
          ChronoCanvas
        </h1>
        <button
          onClick={() => onNavigate("/guide")}
          className={`mt-3 w-full flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
            guideActive
              ? "bg-[var(--accent)] border-[var(--border)] text-[var(--accent-foreground)]"
              : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--accent-foreground)]"
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          Guide
        </button>
      </div>
      <nav className="flex-1 px-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = currentPath === item.href;
          return (
            <button
              key={item.href}
              onClick={() => onNavigate(item.href)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${
                active
                  ? "bg-[var(--accent)] text-[var(--accent-foreground)] font-medium"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
