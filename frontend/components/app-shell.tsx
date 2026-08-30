"use client";

import { createContext, useContext, useEffect, useState } from "react";
import SidebarNav from "./sidebar-nav";

const SidebarCtx = createContext<{ collapsed: boolean; toggle: () => void }>({
  collapsed: false,
  toggle: () => {},
});

export const useSidebar = () => useContext(SidebarCtx);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("sidebar-collapsed") === "1");
    } catch {}
  }, []);

  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem("sidebar-collapsed", c ? "0" : "1");
      } catch {}
      return !c;
    });

  return (
    <SidebarCtx.Provider value={{ collapsed, toggle }}>
      <div className="flex">
        <SidebarNav />
        <main className="min-h-screen flex-1 overflow-x-hidden">{children}</main>
      </div>
    </SidebarCtx.Provider>
  );
}
