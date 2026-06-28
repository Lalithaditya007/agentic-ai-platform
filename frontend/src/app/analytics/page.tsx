"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiService } from "@/lib/api";
import { motion } from "framer-motion";
import { BarChart3, Database, Shield, Zap, TrendingUp, DollarSign, Users, Phone, Mail, Link } from "lucide-react";

interface AnalyticsStats {
  total_runs: number;
  total_briefs_generated: number;
  average_confidence: number;
  hitl_summary: Record<string, number>;
  platform_metrics: {
    total_cost_estimate: number;
    total_duplicates_avoided: number;
    memory_hit_rate: number;
    average_execution_time_seconds: number;
    agent_success_rate: number;
  };
  business_metrics: {
    companies_discovered: number;
    companies_qualified: number;
    companies_enriched: number;
    contacts_discovered: number;
    email_coverage: number;
    phone_coverage: number;
    linkedin_coverage: number;
  };
  recent_strategies: string[];
}

const fallbackStats: AnalyticsStats = {
  total_runs: 0,
  total_briefs_generated: 0,
  average_confidence: 0,
  hitl_summary: {},
  platform_metrics: {
    total_cost_estimate: 0,
    total_duplicates_avoided: 0,
    memory_hit_rate: 0,
    average_execution_time_seconds: 0,
    agent_success_rate: 0,
  },
  business_metrics: {
    companies_discovered: 0,
    companies_qualified: 0,
    companies_enriched: 0,
    contacts_discovered: 0,
    email_coverage: 0,
    phone_coverage: 0,
    linkedin_coverage: 0,
  },
  recent_strategies: [],
};

function MetricBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
  return (
    <div>
      <div className="flex-between mb-2">
        <span className="text-sm">{label} ({value})</span>
        <span className="text-sm font-semibold">{pct}%</span>
      </div>
      <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color }}></div>
      </div>
    </div>
  );
}

function CoverageRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="flex-between" style={{ padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <span className="text-sm font-semibold">{Math.round(value * 100)}%</span>
    </div>
  );
}

function AnalyticsContent() {
  const searchParams = useSearchParams();
  const projectIdParam = searchParams.get("project");

  const [stats, setStats] = useState<AnalyticsStats>(fallbackStats);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        if (projectIdParam) {
          const res = await apiService.getAnalytics(projectIdParam);
          setStats(res.data || fallbackStats);
          return;
        }

        const projectsRes = await apiService.listProjects();
        const projects = projectsRes.data;
        if (projects && projects.length > 0) {
          const res = await apiService.getAnalytics(projects[0].id);
          setStats(res.data || fallbackStats);
        } else {
          setStats(fallbackStats);
        }
      } catch (err) {
        console.error("Analytics error:", err);
        setStats(fallbackStats);
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, [projectIdParam]);

  if (loading) {
    return <div className="container mt-8 text-center text-muted">Loading analytics...</div>;
  }

  const totalHitl = Object.values(stats.hitl_summary || {}).reduce((sum, value) => sum + value, 0);

  return (
    <div className="container">
      <div className="flex-between mb-8">
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>Platform Analytics</h1>
          <p className="text-muted">Real workflow, memory, qualification, and contact coverage metrics for this project.</p>
        </div>
        <div className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <BarChart3 size={18} /> {stats.recent_strategies[0] || "No strategy yet"}
        </div>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="grid-4 mb-8">
          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Total Workflows</span>
              <Zap size={20} color="var(--accent-primary)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{stats.total_runs}</div>
          </div>

          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Briefs Generated</span>
              <Database size={20} color="var(--accent-secondary)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{stats.total_briefs_generated}</div>
          </div>

          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Avg Confidence</span>
              <TrendingUp size={20} color="var(--accent-success)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{Math.round(stats.average_confidence * 100)}%</div>
          </div>

          <div className="glass-card" style={{ padding: "24px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Duplicates Avoided</span>
              <Shield size={20} color="var(--accent-success)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--accent-success)" }}>
              {stats.platform_metrics.total_duplicates_avoided}
            </div>
            <div className="text-xs text-muted mt-2">Persisted from workflow execution logs</div>
          </div>
        </div>

        <div className="grid-2">
          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">HITL Resolution Distribution</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
              <MetricBar label="Approved" value={stats.hitl_summary.approved || 0} total={totalHitl} color="var(--accent-success)" />
              <MetricBar label="Rejected" value={stats.hitl_summary.rejected || 0} total={totalHitl} color="var(--accent-danger)" />
              <MetricBar label="Pending Review" value={stats.hitl_summary.pending_review || 0} total={totalHitl} color="var(--accent-warning)" />
              <MetricBar label="Pending Research" value={stats.hitl_summary.pending_research || 0} total={totalHitl} color="#38bdf8" />
            </div>
          </div>

          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">Platform Efficiency</h3>
            <div style={{ display: "flex", alignItems: "center", gap: "24px", marginBottom: "24px" }}>
              <div style={{ background: "rgba(16, 185, 129, 0.1)", padding: "24px", borderRadius: "50%" }}>
                <DollarSign size={48} color="var(--accent-success)" />
              </div>
              <div>
                <div className="text-muted text-sm uppercase mb-1">Estimated Cost</div>
                <div style={{ fontSize: "3rem", fontWeight: 700 }}>
                  ${stats.platform_metrics.total_cost_estimate.toFixed(3)}
                </div>
              </div>
            </div>
            <p className="text-muted text-sm" style={{ lineHeight: 1.8 }}>
              Agent success rate is <strong className="text-white">{Math.round(stats.platform_metrics.agent_success_rate * 100)}%</strong>, 
              average execution time is <strong className="text-white">{stats.platform_metrics.average_execution_time_seconds}s</strong>, 
              and memory hit rate is <strong className="text-white">{Math.round(stats.platform_metrics.memory_hit_rate * 100)}%</strong>.
            </p>
          </div>
        </div>

        <div className="grid-2" style={{ marginTop: "24px" }}>
          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">Pipeline Output</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="flex-between"><span>Companies Discovered</span><strong>{stats.business_metrics.companies_discovered}</strong></div>
              <div className="flex-between"><span>Companies Qualified</span><strong>{stats.business_metrics.companies_qualified}</strong></div>
              <div className="flex-between"><span>Companies Enriched</span><strong>{stats.business_metrics.companies_enriched}</strong></div>
              <div className="flex-between"><span>Contacts Discovered</span><strong>{stats.business_metrics.contacts_discovered}</strong></div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">Contact Coverage</h3>
            <CoverageRow icon={<Mail size={16} color="#60a5fa" />} label="Email Coverage" value={stats.business_metrics.email_coverage} />
            <CoverageRow icon={<Phone size={16} color="#f59e0b" />} label="Phone Coverage" value={stats.business_metrics.phone_coverage} />
            <CoverageRow icon={<Link size={16} color="#38bdf8" />} label="LinkedIn Coverage" value={stats.business_metrics.linkedin_coverage} />
            <div style={{ marginTop: "18px", display: "flex", gap: 10, alignItems: "center" }}>
              <Users size={18} color="var(--accent-primary)" />
              <span className="text-sm text-muted">Contact enrichment quality is now measured from stored contact records, not mock data.</span>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<div className="container mt-8 text-center text-muted">Loading analytics...</div>}>
      <AnalyticsContent />
    </Suspense>
  );
}
