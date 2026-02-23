import { useState } from "react";
import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";

export function Layout({
  children,
  currentPath,
  onNavigate,
}: {
  children: ReactNode;
  currentPath: string;
  onNavigate: (path: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen">
      <Sidebar
        currentPath={currentPath}
        onNavigate={onNavigate}
        collapsed={collapsed}
        onToggle={() => setCollapsed((prev) => !prev)}
      />
      <main className="flex-1 overflow-auto transition-all duration-200">
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
