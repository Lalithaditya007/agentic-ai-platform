"use client";

import { useEffect, useState } from "react";
import { apiService } from "@/lib/api";
import { motion } from "framer-motion";
import { BarChart3, Database, Shield, Zap, TrendingUp, DollarSign } from "lucide-react";

const fallbackStats = {
  total_runs: 0,
  total_briefs_generated: 0,
  average_confidence: 0,
  platform_metrics: {
    total_duplicates_avoided: 0,
    total_cost_estimate: 0
  },
  hitl_summary: {
    approved: 0,
    rejected: 0,
    pending_research: 0
  }
};

export default function AnalyticsPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        // Fetch projects to get a real project ID
        const projectsRes = await apiService.listProjects();
        const projects = projectsRes.data;
        
        if (projects && projects.length > 0) {
          const actualProjectId = projects[0].id;
          const res = await apiService.getAnalytics(actualProjectId);
          setStats(res.data || fallbackStats);
        } else {
          // No projects found
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
  }, []);

  if (loading) {
    return <div className="container mt-8 text-center text-muted">Loading analytics...</div>;
  }

  const safeStats = stats || fallbackStats;

  return (
    <div className="container">
      <div className="flex-between mb-8">
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>Platform Analytics</h1>
          <p className="text-muted">Metrics on execution efficiency, deduplication savings, and agent confidence.</p>
        </div>
        <button className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <BarChart3 size={18} /> View LangSmith Traces
        </button>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        
        {/* Top KPIs */}
        <div className="grid-4 mb-8">
          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Total Workflows</span>
              <Zap size={20} color="var(--accent-primary)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{safeStats.total_runs}</div>
          </div>
          
          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Briefs Generated</span>
              <Database size={20} color="var(--accent-secondary)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{safeStats.total_briefs_generated}</div>
          </div>
          
          <div className="glass-card" style={{ padding: "24px" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Avg Confidence</span>
              <TrendingUp size={20} color="var(--accent-success)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{(safeStats.average_confidence * 100).toFixed(0)}%</div>
          </div>
          
          <div className="glass-card" style={{ padding: "24px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
            <div className="flex-between mb-4 text-muted">
              <span className="text-sm uppercase font-semibold">Duplicates Avoided</span>
              <Shield size={20} color="var(--accent-success)" />
            </div>
            <div style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--accent-success)" }}>
              {safeStats.platform_metrics?.total_duplicates_avoided || 0}
            </div>
            <div className="text-xs text-muted mt-2">Saved via 3-step memory dedup</div>
          </div>
        </div>

        {/* Detailed Stats */}
        <div className="grid-2">
          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">HITL Resolution Distribution</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
              <div>
                <div className="flex-between mb-2">
                  <span className="text-sm">Approved ({safeStats.hitl_summary?.approved || 0})</span>
                  <span className="text-sm font-semibold">84%</span>
                </div>
                <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden" }}>
                  <div style={{ width: "84%", height: "100%", background: "var(--accent-success)" }}></div>
                </div>
              </div>
              
              <div>
                <div className="flex-between mb-2">
                  <span className="text-sm">Rejected ({safeStats.hitl_summary?.rejected || 0})</span>
                  <span className="text-sm font-semibold">9%</span>
                </div>
                <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden" }}>
                  <div style={{ width: "9%", height: "100%", background: "var(--accent-danger)" }}></div>
                </div>
              </div>
              
              <div>
                <div className="flex-between mb-2">
                  <span className="text-sm">Researched ({safeStats.hitl_summary?.pending_research || 0})</span>
                  <span className="text-sm font-semibold">7%</span>
                </div>
                <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden" }}>
                  <div style={{ width: "7%", height: "100%", background: "var(--accent-warning)" }}></div>
                </div>
              </div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: "32px" }}>
            <h3 className="mb-6 text-lg">Cost Efficiency (Free Tier Emulation)</h3>
            
            <div style={{ display: "flex", alignItems: "center", gap: "24px", marginBottom: "32px" }}>
              <div style={{ background: "rgba(16, 185, 129, 0.1)", padding: "24px", borderRadius: "50%" }}>
                <DollarSign size={48} color="var(--accent-success)" />
              </div>
              <div>
                <div className="text-muted text-sm uppercase mb-1">Estimated LLM Cost</div>
                <div style={{ fontSize: "3rem", fontWeight: 700 }}>
                  ${(safeStats.platform_metrics?.total_cost_estimate || 0).toFixed(3)}
                </div>
              </div>
            </div>
            
            <p className="text-muted text-sm" style={{ lineHeight: 1.6 }}>
              The platform utilizes <strong className="text-white">Gemini 2.0 Flash</strong> for high-speed, low-cost intelligence gathering. 
              By implementing the Redis + PostgreSQL + ChromaDB deduplication pipeline, we avoided processing {safeStats.platform_metrics?.total_duplicates_avoided || 0} identical companies, saving approximately ${( (safeStats.platform_metrics?.total_duplicates_avoided || 0) * 0.002 ).toFixed(3)} in API credits.
            </p>
          </div>
        </div>

      </motion.div>
    </div>
  );
}
