"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiService, WS_URL } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { UserCheck, CheckCircle, XCircle, Search, Clock, ShieldAlert } from "lucide-react";

import { Suspense } from "react";

function HitlContent() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");
  
  const [queue, setQueue] = useState<any[]>([]);
  const [selectedBrief, setSelectedBrief] = useState<any>(null);
  const [researchQuery, setResearchQuery] = useState("");
  const [wsLogs, setWsLogs] = useState<any[]>([]);
  
  // Real-time updates via WebSocket if project ID exists (Demo Flow)
  useEffect(() => {
    if (!projectId) return;
    
    // In our simplified demo, we connect to a generic run stream.
    // In a full app, we'd get the runId from the API.
    // For demo purposes, we'll mock the WS connection logs.
    const mockLogs = [
      { node: "trigger_monitoring", time: new Date(Date.now() - 6000).toLocaleTimeString(), status: "complete" },
      { node: "company_discovery", time: new Date(Date.now() - 1000).toLocaleTimeString(), status: "complete" },
      { node: "deduplication", time: new Date().toLocaleTimeString(), status: "complete" },
      { node: "company_validation", time: new Date(Date.now() + 2000).toLocaleTimeString(), status: "complete" },
      { node: "company_enrichment", time: new Date(Date.now() + 4000).toLocaleTimeString(), status: "complete" },
      { node: "contact_discovery", time: new Date(Date.now() + 6000).toLocaleTimeString(), status: "complete" },
      { node: "next_best_action", time: new Date(Date.now() + 8000).toLocaleTimeString(), status: "complete" },
      { node: "business_brief", time: new Date(Date.now() + 10000).toLocaleTimeString(), status: "complete" },
    ];
    
    let step = 0;
    const interval = setInterval(() => {
      if (step < mockLogs.length) {
        setWsLogs(prev => [...prev, mockLogs[step]]);
        step++;
      } else {
        clearInterval(interval);
        loadQueue(); // Refresh queue when workflow reaches HITL pause
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [projectId]);

  const loadQueue = async () => {
    try {
      console.log("[Frontend] Calling apiService.getHitlQueue...");
      const res = await apiService.getHitlQueue();
      console.log("[Frontend] Queue loaded successfully. Items:", res.data.queue);
      setQueue(res.data.queue || []);
    } catch (err) {
      console.error("[Frontend] Failed to load HITL queue:", err);
    }
  };

  useEffect(() => {
    loadQueue();
    const interval = setInterval(loadQueue, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  const openBrief = async (id: string) => {
    try {
      const res = await apiService.getHitlBrief(id);
      setSelectedBrief(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAction = async (action: string) => {
    if (!selectedBrief) return;
    
    try {
      console.log(`[Frontend] Submitting action '${action}' for brief ID: ${selectedBrief.id}`);
      const details = action === "request_research" ? { research_query: researchQuery } : {};
      await apiService.submitHitlAction(selectedBrief.id, action, details);
      console.log("[Frontend] Action submitted successfully.");
      
      setSelectedBrief(null);
      setResearchQuery("");
      loadQueue();
      
      // If research, add a mock log to show resumption
      if (action === "request_research") {
        console.log("[Frontend] Adding mock WS log for research resumption...");
        setWsLogs(prev => [...prev, { node: "hitl_review_research", time: new Date().toLocaleTimeString(), status: "resuming" }]);
      }
    } catch (err) {
      console.error("[Frontend] Failed to submit HITL action:", err);
    }
  };

  return (
    <div className="container">
      <div className="flex-between mb-6">
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>Human-in-the-Loop Review</h1>
          <p className="text-muted">Review generated business briefs before finalizing Next Best Actions.</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 3fr", gap: "24px" }}>
        
        {/* Left: WS Logs & Queue List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          
          <div className="glass-card" style={{ padding: "16px" }}>
            <h3 className="mb-4" style={{ fontSize: "1rem", color: "var(--accent-primary)" }}>Active Workflows</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "200px", overflowY: "auto" }}>
              {wsLogs.length === 0 ? (
                <div className="text-muted text-sm">No active runs.</div>
              ) : (
                wsLogs.map((log, i) => !log ? null : (
                  <div key={i} className="text-xs" style={{ display: "flex", gap: "8px" }}>
                    <span style={{ color: "var(--accent-success)" }}>[{log.time}]</span>
                    <span>{log.node}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="glass-card" style={{ padding: "16px", flex: 1 }}>
            <h3 className="mb-4" style={{ fontSize: "1rem", display: "flex", alignItems: "center", gap: "8px" }}>
              <Clock size={16} /> Pending Review ({queue.length})
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {queue.length === 0 ? (
                <div className="text-muted text-sm text-center py-8">Queue is empty.</div>
              ) : (
                queue.map((item) => (
                  <div 
                    key={item.id} 
                    onClick={() => openBrief(item.id)}
                    style={{ 
                      padding: "12px", 
                      background: selectedBrief?.id === item.id ? "rgba(59, 130, 246, 0.1)" : "rgba(0,0,0,0.2)",
                      border: `1px solid ${selectedBrief?.id === item.id ? "var(--accent-primary)" : "var(--border-color)"}`,
                      borderRadius: "8px",
                      cursor: "pointer"
                    }}
                  >
                    <div className="font-medium">{item.company_name}</div>
                    <div className="flex-between mt-2 text-xs">
                      <span className="text-muted">Score: {item.overall_confidence.toFixed(2)}</span>
                      <span className="badge badge-warning">{item.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Brief Details */}
        <div className="glass-card" style={{ padding: "32px", minHeight: "600px" }}>
          {!selectedBrief ? (
            <div className="flex-center" style={{ height: "100%", flexDirection: "column", color: "var(--text-muted)" }}>
              <UserCheck size={48} style={{ marginBottom: "16px", opacity: 0.5 }} />
              <h3>Select a brief to review</h3>
            </div>
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <div className="flex-between mb-6" style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "2rem", marginBottom: "4px" }}>{selectedBrief.company_name}</h2>
                  <a href={selectedBrief.company_domain} target="_blank" className="text-muted text-sm hover:text-white">
                    {selectedBrief.company_domain}
                  </a>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="text-sm text-muted">Confidence Score</div>
                  <div style={{ fontSize: "1.5rem", color: selectedBrief.overall_confidence >= 0.8 ? "var(--accent-success)" : "var(--accent-warning)" }}>
                    {(selectedBrief.overall_confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div className="grid-2 mb-6">
                <div>
                  <h4 className="text-sm text-muted mb-2 uppercase">Company Summary</h4>
                  <p className="text-sm" style={{ lineHeight: 1.6 }}>{selectedBrief.company_summary}</p>
                </div>
                <div>
                  <h4 className="text-sm text-muted mb-2 uppercase">Trigger Event</h4>
                  <div style={{ background: "rgba(245, 158, 11, 0.1)", padding: "12px", borderLeft: "3px solid var(--accent-warning)", borderRadius: "0 8px 8px 0" }}>
                    <p className="text-sm">{selectedBrief.trigger_summary}</p>
                  </div>
                </div>
              </div>

              <div className="mb-6">
                <h4 className="text-sm text-muted mb-2 uppercase">Key Contacts</h4>
                <div className="grid-2">
                  {selectedBrief.decision_makers?.map((dm: any, i: number) => (
                    <div key={i} style={{ border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                      <div className="font-medium">{dm.name}</div>
                      <div className="text-xs text-muted mb-2">{dm.title}</div>
                      <div className="text-sm">{dm.email === "unavailable" ? <span className="text-muted italic">Email unavailable</span> : dm.email}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mb-8">
                <h4 className="text-sm text-muted mb-2 uppercase">Next Best Action</h4>
                <div style={{ background: "rgba(59, 130, 246, 0.05)", padding: "16px", border: "1px solid var(--border-glow)", borderRadius: "8px" }}>
                  <div className="flex-between mb-2">
                    <span className="font-medium text-gradient">Recommended Channel: {selectedBrief.next_best_actions?.recommended_channel}</span>
                  </div>
                  <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    {selectedBrief.next_best_actions?.talking_points?.map((pt: string, i: number) => (
                      <li key={i} className="text-sm">{pt}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Action Bar */}
              <div style={{ display: "flex", gap: "16px", alignItems: "flex-end", borderTop: "1px solid var(--border-color)", paddingTop: "24px" }}>
                <button onClick={() => handleAction("approve")} className="btn-primary" style={{ display: "flex", gap: "8px", alignItems: "center", background: "var(--accent-success)", boxShadow: "0 4px 14px 0 rgba(16, 185, 129, 0.39)" }}>
                  <CheckCircle size={18} /> Approve Brief
                </button>
                
                <button onClick={() => handleAction("reject")} className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center", color: "var(--accent-danger)" }}>
                  <XCircle size={18} /> Reject
                </button>

                <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="E.g., Find recent funding amount..." 
                    value={researchQuery}
                    onChange={(e) => setResearchQuery(e.target.value)}
                    style={{ width: "250px" }}
                  />
                  <button onClick={() => handleAction("request_research")} className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }} disabled={!researchQuery.trim()}>
                    <Search size={18} /> Request Research
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </div>
        
      </div>
    </div>
  );
}

export default function HitlPage() {
  return (
    <Suspense fallback={<div className="container mt-8 text-center text-muted">Loading...</div>}>
      <HitlContent />
    </Suspense>
  );
}
