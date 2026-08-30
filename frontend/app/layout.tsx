import type { Metadata } from "next";
import "./globals.css";
import SidebarNav from "@/components/sidebar-nav";

export const metadata: Metadata = {
  title: "Arca Bulk Review",
  description: "Bulk regulatory document review with auditable citations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex">
          <SidebarNav />
          <main className="min-h-screen flex-1 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
