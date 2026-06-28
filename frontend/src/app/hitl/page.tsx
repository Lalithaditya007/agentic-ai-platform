"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { apiService, WS_URL, API_URL } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import {
  UserCheck,
  CheckCircle,
  XCircle,
  Search,
  Clock,
  RefreshCw,
  Loader2,
  AlertCircle,
  Wifi,
  WifiOff,
  Edit3,
  Users,
  Target
} from "lucide-react";
import { Suspense } from "react";

// ── Helpers ─────────────────────────────────────────────────────────────────

function RunStatusBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const map: Record<string, { color: string; label: string }> = {
    running:      { color: "#3b82f6", label: "Running" },
    completed:    { color: "#10b981", label: "Completed" },
    paused_hitl:  { color: "#f59e0b", label: "Awaiting Review" },
    failed:       { color: "#ef4444", label: "Failed" },
  };
  const cfg = map[status] ?? { color: "#6b7280", label: status };
  return (
    <span style={{
      background: `${cfg.color}18`,
      color: cfg.color,
      border: `1px solid ${cfg.color}40`,
      borderRadius: 20,
      padding: "2px 10px",
      fontSize: 11,
      fontWeight: 700,
      textTransform: "uppercase" as const,
      letterSpacing: "0.06em",
    }}>
      {cfg.label}
    </span>
  );
}

import useSWR from "swr";
import { api } from "@/lib/api";

interface HitlQueueItem {
  id: string;
  company_name: string;
  status: string;
  overall_confidence: number | null;
  created_at?: string;
}

interface DecisionMaker {
  name: string;
  title: string;
  email: string;
}

interface HitlBrief {
  id: string;
  company_name: string;
  company_domain?: string | null;
  company_summary?: string | null;
  trigger_summary?: string | null;
  qualification_summary?: string | null;
  company_insights?: string[] | null;
  decision_makers?: DecisionMaker[] | null;
  next_best_actions?: string[] | null;
  priority_score?: number | null;
  overall_confidence?: number | null;
  hitl_status?: string | null;
}

interface HitlQueueResponse {
  queue: HitlQueueItem[];
  run_id?: string | null;
  run_status?: string | null;
}

const fetcher = (url: string) => api.get(url).then(res => res.data);

// ── Main Component ───────────────────────────────────────────────────────────

function HitlContent() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");

  const [selectedBrief, setSelectedBrief] = useState<HitlBrief | null>(null);
  const [researchQuery, setResearchQuery] = useState("");
  const [wsLogs, setWsLogs] = useState<{ node: string; time: string; status: string }[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // ── Load queue via SWR — filtered by project + current run ─────────────
  const endpoint = projectId ? `/hitl/queue?project_id=${projectId}` : "/hitl/queue";
  const { data, error, isLoading: queueLoading, mutate } = useSWR<HitlQueueResponse>(endpoint, fetcher, {
    refreshInterval: 8000,
  });
  const loadQueue = useCallback(() => mutate(), [mutate]);

  const queue = data?.queue || [];
  const runId = data?.run_id || null;
  const runStatus = data?.run_status || null;

  // ── WebSocket for live workflow node events ───────────────────────────────
  useEffect(() => {
    if (!runId) return;

    // Avoid reconnecting if already connected for this run
    if (wsRef.current?.url.includes(runId)) return;

    const url = `${WS_URL}/ws/workflow/${runId}`;
    console.log("[WS] Connecting to", url);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      console.log("[WS] Connected");
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "node_complete" || msg.node) {
          const node = msg.node ?? "unknown";
          const time = new Date(msg.timestamp ?? Date.now()).toLocaleTimeString();
          setWsLogs((prev) => {
            // Avoid duplicates
            if (prev.some((l) => l.node === node && l.time === time)) return prev;
            return [...prev, { node, time, status: "complete" }];
          });
          // Refresh queue whenever a node completes — briefs may have appeared
          loadQueue();
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      setWsConnected(false);
      console.warn("[WS] Connection error");
    };

    ws.onclose = () => {
      setWsConnected(false);
      console.log("[WS] Disconnected");
    };

    return () => {
      ws.close();
    };
  }, [runId, loadQueue]);

  // ── Open a brief for review ────────────────────────────────────────────
  const openBrief = async (id: string) => {
    try {
      const res = await apiService.getHitlBrief(id);
      setSelectedBrief(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  // ── Submit a HITL action ───────────────────────────────────────────────
  const handleAction = async (action: string) => {
    if (!selectedBrief) return;
    try {
      const details = action === "request_research" ? { research_query: researchQuery } : {};
      await apiService.submitHitlAction(selectedBrief.id, action, details);
      setSelectedBrief(null);
      setResearchQuery("");
      loadQueue();
    } catch (err) {
      console.error("[HITL] Action failed:", err);
    }
  };

  // ── UI ─────────────────────────────────────────────────────────────────
  return (
    <div className="container">
      <div className="flex-between mb-6">
        <div>
          <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>Human-in-the-Loop Review</h1>
          <p className="text-muted">
            Review generated business briefs before finalizing Next Best Actions.
            {projectId && (
              <span style={{ marginLeft: 8 }}>
                <RunStatusBadge status={runStatus} />
              </span>
            )}
          </p>
        </div>
        <button
          onClick={loadQueue}
          className="btn-secondary"
          style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13 }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 3fr", gap: "24px" }}>

        {/* ── Left: Active Workflow + Queue ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

          {/* Workflow log panel */}
          <div className="glass-card" style={{ padding: "16px" }}>
            <h3 className="mb-4" style={{ fontSize: "1rem", color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: 8 }}>
              {wsConnected
                ? <Wifi size={14} color="#10b981" />
                : <WifiOff size={14} color="#6b7280" />}
              Active Workflows
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "220px", overflowY: "auto" }}>
              {wsLogs.length === 0 ? (
                <div className="text-muted text-sm">
                  {runStatus === "running"
                    ? <span style={{ display: "flex", gap: 6, alignItems: "center" }}><Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> Workflow running…</span>
                    : "No active run yet."}
                </div>
              ) : (
                wsLogs.map((log, i) => (
                  <div key={i} className="text-xs" style={{ display: "flex", gap: "8px" }}>
                    <span style={{ color: "var(--accent-success)" }}>[{log.time}]</span>
                    <span>{log.node}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Queue panel */}
          <div className="glass-card" style={{ padding: "16px", flex: 1 }}>
            <h3 className="mb-4" style={{ fontSize: "1rem", display: "flex", alignItems: "center", gap: "8px" }}>
              <Clock size={16} /> Pending Review ({queue.length})
            </h3>

            {/* Hint when workflow still running and no briefs yet */}
            {runStatus === "running" && queue.length === 0 && (
              <div style={{
                background: "rgba(59,130,246,0.08)",
                border: "1px solid rgba(59,130,246,0.2)",
                borderRadius: 8,
                padding: "10px 12px",
                fontSize: 11.5,
                color: "#93c5fd",
                marginBottom: 12,
                lineHeight: 1.5,
              }}>
                <Loader2 size={11} style={{ animation: "spin 1s linear infinite", display: "inline", marginRight: 5 }} />
                Workflow is running — briefs will appear here as agents complete their work.
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {queueLoading ? (
                <div className="text-muted text-sm text-center" style={{ padding: "20px 0" }}>
                  <Loader2 size={18} style={{ animation: "spin 1s linear infinite", margin: "0 auto 8px" }} />
                  Loading…
                </div>
              ) : queue.length === 0 ? (
                <div className="text-muted text-sm text-center" style={{ padding: "20px 0" }}>
                  {projectId
                    ? "No briefs yet for this run. Refreshing every 8s."
                    : "Queue is empty."}
                </div>
              ) : (
                queue.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => openBrief(item.id)}
                    style={{
                      padding: "12px",
                      background: selectedBrief?.id === item.id
                        ? "rgba(59, 130, 246, 0.1)"
                        : "rgba(0,0,0,0.2)",
                      border: `1px solid ${selectedBrief?.id === item.id ? "var(--accent-primary)" : "var(--border-color)"}`,
                      borderRadius: "8px",
                      cursor: "pointer",
                      transition: "all 0.2s",
                    }}
                  >
                    <div className="font-medium">{item.company_name}</div>
                    <div className="flex-between mt-2 text-xs">
                      <span className="text-muted">
                        Score: {typeof item.overall_confidence === "number"
                          ? item.overall_confidence.toFixed(2)
                          : "—"}
                      </span>
                      <span className="badge badge-warning">{item.status?.toUpperCase()}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── Right: Brief Detail ── */}
        <div className="glass-card" style={{ padding: "32px", minHeight: "600px" }}>
          <AnimatePresence mode="wait">
            {!selectedBrief ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-center"
                style={{ height: "100%", flexDirection: "column", color: "var(--text-muted)" }}
              >
                <UserCheck size={48} style={{ marginBottom: "16px", opacity: 0.5 }} />
                <h3>Select a brief to review</h3>
              </motion.div>
            ) : (
              <motion.div key={selectedBrief.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>

                <div className="flex-between mb-6" style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: "16px" }}>
                  <div>
                    <h2 style={{ fontSize: "2rem", marginBottom: "4px" }}>{selectedBrief.company_name}</h2>
                    <span className="text-muted text-sm">{selectedBrief.company_domain}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="text-sm text-muted">Confidence Score</div>
                    <div style={{
                      fontSize: "1.5rem",
                      color: (selectedBrief.overall_confidence ?? 0) >= 0.8
                        ? "var(--accent-success)"
                        : "var(--accent-warning)",
                    }}>
                      {typeof selectedBrief.overall_confidence === "number"
                        ? `${(selectedBrief.overall_confidence * 100).toFixed(0)}%`
                        : "—"}
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

                {selectedBrief.qualification_summary && (
                  <div className="mb-6">
                    <h4 className="text-sm text-muted mb-2 uppercase">ICP Qualification</h4>
                    <p className="text-sm" style={{ lineHeight: 1.6, color: "var(--text-secondary)" }}>
                      {selectedBrief.qualification_summary}
                    </p>
                  </div>
                )}

                <div className="mb-6">
                  <h4 className="text-sm text-muted mb-2 uppercase">Key Contacts</h4>
                  <div className="grid-2">
                    {(selectedBrief.decision_makers ?? []).length === 0 ? (
                      <p className="text-sm text-muted">No contacts discovered for this company.</p>
                    ) : (
                      (selectedBrief.decision_makers ?? []).map((dm: DecisionMaker, i: number) => (
                        <div key={i} style={{ border: "1px solid var(--border-color)", padding: "12px", borderRadius: "8px" }}>
                          <div className="font-medium">{dm.name}</div>
                          <div className="text-xs text-muted mb-2">{dm.title}</div>
                          <div className="text-sm">
                            {dm.email === "unavailable"
                              ? <span className="text-muted" style={{ fontStyle: "italic" }}>Email unavailable</span>
                              : dm.email}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="mb-8">
                  <h4 className="text-sm text-muted mb-2 uppercase">Next Best Actions</h4>
                  <div style={{ background: "rgba(59, 130, 246, 0.05)", padding: "16px", border: "1px solid var(--border-glow)", borderRadius: "8px" }}>
                    <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "8px" }}>
                      {(selectedBrief.next_best_actions ?? []).map((pt: string, i: number) => (
                        <li key={i} className="text-sm">{pt}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Action Bar */}
                <div style={{ display: "flex", gap: "16px", alignItems: "flex-end", borderTop: "1px solid var(--border-color)", paddingTop: "24px" }}>
                  <button
                    onClick={() => handleAction("approve")}
                    className="btn-primary"
                    style={{ display: "flex", gap: "8px", alignItems: "center", background: "var(--accent-success)", boxShadow: "0 4px 14px 0 rgba(16,185,129,0.39)" }}
                  >
                    <CheckCircle size={18} /> Approve Brief
                  </button>
                  <button
                    onClick={() => handleAction("reject")}
                    className="btn-secondary"
                    style={{ display: "flex", gap: "8px", alignItems: "center", color: "var(--accent-danger)" }}
                  >
                    <XCircle size={18} /> Reject
                  </button>
                  <div style={{ display: "flex", gap: "8px", marginLeft: "16px", paddingLeft: "16px", borderLeft: "1px solid var(--border-color)" }}>
                    <button onClick={() => handleAction("modify")} className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <Edit3 size={16} /> Modify
                    </button>
                    <button onClick={() => handleAction("change_personas")} className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <Users size={16} /> Change Personas
                    </button>
                    <button onClick={() => handleAction("update_icp")} className="btn-secondary" style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <Target size={16} /> Update ICP
                    </button>
                  </div>
                  <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="E.g., Find recent funding amount…"
                      value={researchQuery}
                      onChange={(e) => setResearchQuery(e.target.value)}
                      style={{ width: "250px" }}
                    />
                    <button
                      onClick={() => handleAction("request_research")}
                      className="btn-secondary"
                      style={{ display: "flex", gap: "8px", alignItems: "center" }}
                      disabled={!researchQuery.trim()}
                    >
                      <Search size={18} /> Request Research
                    </button>
                  </div>
                </div>

              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

import dynamic from 'next/dynamic';

const DynamicHitlContent = dynamic(() => Promise.resolve(HitlContent), { 
  ssr: false, 
  loading: () => <div className="container mt-8 text-center text-muted">Loading Application...</div>
});

export default function HitlPage() {
  return (
    <Suspense fallback={<div className="container mt-8 text-center text-muted">Loading…</div>}>
      <DynamicHitlContent />
    </Suspense>
  );
}
