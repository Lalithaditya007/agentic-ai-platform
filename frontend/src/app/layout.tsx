import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { Activity, LayoutDashboard, Settings, UserCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "Universal Agentic AI Platform",
  description: "Dynamic AI Agent Orchestration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <nav className="glass-panel" style={{ 
          margin: "16px 24px", 
          padding: "16px 24px", 
          display: "flex", 
          justifyContent: "space-between",
          alignItems: "center",
          position: "sticky",
          top: "16px",
          zIndex: 100
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div style={{ 
              background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
              padding: "8px",
              borderRadius: "8px",
              display: "flex"
            }}>
              <Activity size={20} color="white" />
            </div>
            <h1 style={{ fontSize: "1.25rem", margin: 0 }}>
              Agentic <span className="text-gradient">Platform</span>
            </h1>
          </div>
          
          <div style={{ display: "flex", gap: "32px", alignItems: "center" }}>
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem", color: "var(--text-secondary)", transition: "color 0.2s" }} className="hover:text-white">
              <Settings size={18} /> Configure
            </Link>
            <Link href="/hitl" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem", color: "var(--text-secondary)", transition: "color 0.2s" }} className="hover:text-white">
              <UserCheck size={18} /> HITL Review
            </Link>
            <Link href="/analytics" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem", color: "var(--text-secondary)", transition: "color 0.2s" }} className="hover:text-white">
              <LayoutDashboard size={18} /> Analytics
            </Link>
          </div>
        </nav>
        
        <main style={{ padding: "24px", paddingBottom: "64px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
