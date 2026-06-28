"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { apiService } from "@/lib/api";
import {
  Play,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Cpu,
  Search,
  Filter,
  CheckCircle,
  Database,
  Users,
  Zap,
  FileText,
  Bell,
  Box,
  GitBranch,
  Layers,
  DollarSign,
  Target,
  AlertTriangle,
  Sparkles,
  ArrowRight,
  Info,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────

interface NodeDisplay {
  icon: string;
  color: string;
  category: string;
  description: string;
  label: string;
}

interface DagNode {
  task_id: string;
  agent_template: string;
  goal: string;
  required_capabilities: string[];
  model: string;
  priority: number;
  timeout_seconds: number;
  retry_on_failure: boolean;
  display: NodeDisplay;
  position: { x: number; y: number; layer: number };
}

interface DagEdge {
  from: string;
  to: string;
  condition: string;
}

interface DagData {
  project_id: string;
  run_id?: string;
  generated_at: string;
  strategy: {
    name: string;
    rationale: string;
    cost_estimate_usd: number;
    targets: Record<string, unknown>;
    hitl_triggers: Array<{ trigger_at: string; reason: string; condition: string }>;
  };
  dag: {
    nodes: DagNode[];
    edges: DagEdge[];
    node_count: number;
    edge_count: number;
  };
  layout: {
    canvas: { width: number; height: number };
    node_dims: { width: number; height: number };
    positions: Record<string, { x: number; y: number; layer: number }>;
  };
  meta: {
    total_capabilities_available: number;
    icp_industry?: string[];
    icp_geography?: string[];
    is_fallback: boolean;
    from_live_run?: boolean;
  };
}

// ─────────────────────────────────────────────────────────────────
// Icon resolver
// ─────────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ElementType> = {
  search: Search,
  filter: Filter,
  "check-circle": CheckCircle,
  database: Database,
  users: Users,
  zap: Zap,
  "file-text": FileText,
  bell: Bell,
  cpu: Cpu,
  box: Box,
};

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Box;
}

// ─────────────────────────────────────────────────────────────────
// Edge condition color
// ─────────────────────────────────────────────────────────────────

function conditionColor(condition: string): string {
  switch (condition) {
    case "on_success": return "#10b981";
    case "on_data":    return "#3b82f6";
    case "always":     return "#6b7280";
    case "on_failure": return "#ef4444";
    default:           return "#8b5cf6";
  }
}

// ─────────────────────────────────────────────────────────────────
// SVG Arrow between two nodes
// ─────────────────────────────────────────────────────────────────

interface EdgeArrowProps {
  fromNode: DagNode;
  toNode: DagNode;
  edge: DagEdge;
  nodeW: number;
  nodeH: number;
  isHighlighted: boolean;
}

function EdgeArrow({ fromNode, toNode, edge, nodeW, nodeH, isHighlighted }: EdgeArrowProps) {
  const fx = fromNode.position.x + nodeW;
  const fy = fromNode.position.y + nodeH / 2;
  const tx = toNode.position.x;
  const ty = toNode.position.y + nodeH / 2;
  const midX = (fx + tx) / 2;
  const d = `M ${fx} ${fy} C ${midX} ${fy}, ${midX} ${ty}, ${tx} ${ty}`;
  const color = conditionColor(edge.condition);
  const strokeW = isHighlighted ? 2.5 : 1.5;
  const opacity = isHighlighted ? 1 : 0.4;
  const edgeId = `${edge.from}-${edge.to}`;

  return (
    <g>
      <defs>
        <marker id={`arr-${edgeId}`} markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill={color} opacity={opacity} />
        </marker>
      </defs>
      <path
        id={`path-${edgeId}`}
        d={d}
        stroke={color}
        strokeWidth={strokeW}
        fill="none"
        opacity={opacity}
        markerEnd={`url(#arr-${edgeId})`}
        strokeDasharray={isHighlighted ? "none" : "6 4"}
        style={{ transition: "all 0.3s ease" }}
      />
      {isHighlighted && (
        <path
          d={d}
          stroke={color}
          strokeWidth={3}
          fill="none"
          opacity={0.6}
          strokeDasharray="8 20"
          style={{ animation: "dashFlow 1.5s linear infinite" }}
        />
      )}
      <text style={{ fontSize: 9 }} fill={color} opacity={isHighlighted ? 0.9 : 0.5}>
        <textPath href={`#path-${edgeId}`} startOffset="50%" textAnchor="middle">
          {edge.condition.replace(/_/g, " ")}
        </textPath>
      </text>
    </g>
  );
}

// ─────────────────────────────────────────────────────────────────
// Single DAG Node card (SVG foreignObject)
// ─────────────────────────────────────────────────────────────────

interface NodeCardProps {
  node: DagNode;
  nodeW: number;
  nodeH: number;
  isSelected: boolean;
  isHighlighted: boolean;
  animDelay: number;
}

function DagNodeCard({ node, nodeW, nodeH, isSelected, isHighlighted, animDelay }: NodeCardProps) {
  const Icon = resolveIcon(node.display.icon);
  const color = node.display.color;
  const dimmed = !isSelected && !isHighlighted;

  return (
    <foreignObject x={node.position.x} y={node.position.y} width={nodeW} height={nodeH} style={{ overflow: "visible" }}>
      <div
        style={{
          width: nodeW,
          height: nodeH,
          borderRadius: 14,
          border: `1.5px solid ${isSelected ? color : isHighlighted ? color + "88" : "rgba(255,255,255,0.09)"}`,
          background: isSelected
            ? `linear-gradient(135deg, ${color}20, ${color}0a)`
            : "rgba(13,17,28,0.93)",
          backdropFilter: "blur(20px)",
          cursor: "pointer",
          transition: "all 0.25s ease",
          boxShadow: isSelected
            ? `0 0 40px ${color}44, 0 8px 32px rgba(0,0,0,0.6)`
            : isHighlighted
            ? `0 0 18px ${color}28, 0 4px 16px rgba(0,0,0,0.4)`
            : "0 4px 16px rgba(0,0,0,0.3)",
          padding: "11px 13px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
          transform: isSelected ? "scale(1.04)" : dimmed ? "scale(0.98)" : "scale(1)",
          opacity: dimmed ? 0.65 : 1,
          animation: `nodeIn 0.45s ease ${animDelay}ms both`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            background: `${color}1a`,
            border: `1px solid ${color}44`,
            borderRadius: 7,
            padding: "4px 5px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}>
            <Icon size={13} color={color} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 11.5, fontWeight: 700, color: "#f3f4f6", fontFamily: "Outfit, sans-serif", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {node.display.label}
            </div>
            <div style={{ fontSize: 8.5, fontWeight: 700, color, textTransform: "uppercase", letterSpacing: "0.07em" }}>
              {node.display.category}
            </div>
          </div>
          <div style={{
            background: `${color}15`,
            border: `1px solid ${color}30`,
            borderRadius: 20,
            padding: "1px 7px",
            fontSize: 9,
            color,
            fontWeight: 700,
            flexShrink: 0,
          }}>
            P{node.priority}
          </div>
        </div>

        <div style={{ fontSize: 10, color: "#9ca3af", lineHeight: 1.4, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
          {node.goal}
        </div>

        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: "auto" }}>
          <Chip color="#3b82f6">{node.required_capabilities.length} caps</Chip>
          <Chip color="#8b5cf6">{node.timeout_seconds}s</Chip>
          {node.retry_on_failure && <Chip color="#f59e0b">retry</Chip>}
        </div>
      </div>
    </foreignObject>
  );
}

function Chip({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span style={{
      background: `${color}14`,
      color,
      borderRadius: 4,
      padding: "1px 5px",
      fontSize: 8.5,
      fontWeight: 700,
    }}>
      {children}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────
// Node Detail Panel
// ─────────────────────────────────────────────────────────────────

function NodeDetailPanel({ node, onClose }: { node: DagNode; onClose: () => void }) {
  const Icon = resolveIcon(node.display.icon);
  const color = node.display.color;

  return (
    <motion.div
      key={node.task_id}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ type: "spring", stiffness: 300, damping: 28 }}
      style={{ position: "relative" }}
    >
      <button
        onClick={onClose}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 7,
          color: "#9ca3af",
          cursor: "pointer",
          padding: "3px 9px",
          fontSize: 12,
          zIndex: 1,
        }}
      >
        ✕
      </button>

      <div style={{ background: `${color}10`, border: `1px solid ${color}35`, borderRadius: 12, padding: 16, marginBottom: 18, display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ background: `${color}20`, border: `1px solid ${color}55`, borderRadius: 9, padding: 10 }}>
          <Icon size={22} color={color} />
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#f9fafb", fontFamily: "Outfit, sans-serif" }}>{node.display.label}</div>
          <div style={{ fontSize: 10, color, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>{node.display.category}</div>
        </div>
      </div>

      <DetailSection label="Agent Goal">
        <p style={{ fontSize: 12.5, color: "#d1d5db", lineHeight: 1.65 }}>{node.goal}</p>
      </DetailSection>

      <DetailSection label="Required Capabilities">
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {node.required_capabilities.map((cap) => (
            <div key={cap} style={{
              background: "rgba(59,130,246,0.07)",
              border: "1px solid rgba(59,130,246,0.18)",
              borderRadius: 5,
              padding: "4px 9px",
              fontSize: 11,
              color: "#93c5fd",
              fontFamily: "monospace",
            }}>
              {cap}
            </div>
          ))}
        </div>
      </DetailSection>

      <DetailSection label="Configuration">
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          <CfgRow label="Model" value={node.model} />
          <CfgRow label="Timeout" value={`${node.timeout_seconds}s`} />
          <CfgRow label="Priority" value={`P${node.priority}`} />
          <CfgRow label="Retry" value={node.retry_on_failure ? "✓ Yes" : "✗ No"} />
          <CfgRow label="Task ID" value={node.task_id} mono />
          <CfgRow label="Template" value={node.agent_template} mono />
        </div>
      </DetailSection>
    </motion.div>
  );
}

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 9.5, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 8 }}>{label}</div>
      {children}
    </div>
  );
}

function CfgRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 11.5, color: "#6b7280" }}>{label}</span>
      <span style={{ fontSize: 11.5, color: "#d1d5db", fontFamily: mono ? "monospace" : "inherit", textAlign: "right", maxWidth: 170, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Legend Panel
// ─────────────────────────────────────────────────────────────────

function LegendPanel({ dag, strategy }: { dag: DagData["dag"]; strategy: DagData["strategy"] }) {
  const COND_DEFS = [
    { cond: "on_success", label: "On Success" },
    { cond: "on_data",    label: "On Data Ready" },
    { cond: "always",     label: "Always" },
    { cond: "on_failure", label: "On Failure" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Agent nodes */}
      <div className="glass-panel" style={{ padding: 16, borderRadius: 14 }}>
        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 12 }}>Agent Nodes</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {dag.nodes.map((node) => {
            const Icon = resolveIcon(node.display.icon);
            return (
              <div key={node.task_id} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <div style={{
                  width: 27,
                  height: 27,
                  background: `${node.display.color}15`,
                  border: `1px solid ${node.display.color}38`,
                  borderRadius: 7,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Icon size={12} color={node.display.color} />
                </div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#e5e7eb" }}>{node.display.label}</div>
                  <div style={{ fontSize: 9, color: "#6b7280" }}>{node.display.category}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Edge conditions */}
      <div className="glass-panel" style={{ padding: 16, borderRadius: 14 }}>
        <div style={{ fontSize: 9.5, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 12 }}>Edge Conditions</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {COND_DEFS.filter(({ cond }) => dag.edges.some((e) => e.condition === cond)).map(({ cond, label }) => (
            <div key={cond} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <svg width="30" height="10" style={{ flexShrink: 0 }}>
                <line x1="0" y1="5" x2="22" y2="5" stroke={conditionColor(cond)} strokeWidth="2" strokeDasharray="5 3" />
                <polygon points="22,2 28,5 22,8" fill={conditionColor(cond)} />
              </svg>
              <span style={{ fontSize: 11, color: "#d1d5db" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* HITL triggers */}
      {strategy.hitl_triggers?.length > 0 && (
        <div className="glass-panel" style={{ padding: 16, borderRadius: 14, border: "1px solid rgba(245,158,11,0.2)" }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, color: "#f59e0b", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <AlertTriangle size={11} color="#f59e0b" /> HITL Triggers
          </div>
          {strategy.hitl_triggers.map((t, i) => (
            <div key={i} style={{ marginBottom: 10, fontSize: 11, lineHeight: 1.5 }}>
              <span style={{ color: "#fbbf24", fontWeight: 600 }}>{t.trigger_at}</span>
              <br />
              <span style={{ color: "#6b7280", fontSize: 10 }}>{t.reason}</span>
            </div>
          ))}
        </div>
      )}

      {/* Run targets */}
      {strategy.targets && Object.keys(strategy.targets).length > 0 && (
        <div className="glass-panel" style={{ padding: 16, borderRadius: 14 }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.09em", marginBottom: 12 }}>Run Targets</div>
          {Object.entries(strategy.targets).map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: "#6b7280" }}>{k.replace(/_/g, " ")}</span>
              <span style={{ fontSize: 10, color: "#d1d5db", fontWeight: 600 }}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Meta Stat chip
// ─────────────────────────────────────────────────────────────────

function MetaStat({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 14px", background: "rgba(255,255,255,0.03)", borderRadius: 9, border: "1px solid rgba(255,255,255,0.06)" }}>
      {icon}
      <div>
        <div style={{ fontSize: 9, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color }}>{value}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────

export default function DagVisualizationPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [dagData, setDagData] = useState<DagData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<DagNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);
  const [launched, setLaunched] = useState(false);

  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 50, y: 50 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ mx: number; my: number; px: number; py: number } | null>(null);

  // ── Load DAG ──
  const loadDag = useCallback(async (forceGenerate = false) => {
    try {
      if (forceGenerate) {
        setGenerating(true);
        const res = await apiService.generateDagPreview(projectId);
        setDagData(res.data);
      } else {
        setLoading(true);
        try {
          const res = await apiService.getDagPreview(projectId);
          setDagData(res.data);
        } catch {
          const res = await apiService.generateDagPreview(projectId);
          setDagData(res.data);
        }
      }
      setError(null);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: unknown } } };
      const detail = err?.response?.data?.detail;
      let msg: string;
      if (typeof detail === "string") {
        msg = detail;
      } else if (Array.isArray(detail)) {
        // FastAPI validation errors are an array of {type, loc, msg, ...}
        msg = detail.map((d: { msg?: string; loc?: string[] }) => `${(d.loc || []).join(".")} — ${d.msg}`).join("; ");
      } else if (detail && typeof detail === "object") {
        msg = JSON.stringify(detail);
      } else {
        msg = "Failed to load DAG. Check that the backend is running.";
      }
      setError(msg);
    } finally {
      setLoading(false);
      setGenerating(false);
    }
  }, [projectId]);

  useEffect(() => { loadDag(); }, [loadDag]);

  // ── Launch ──
  const handleLaunch = async () => {
    try {
      setLaunching(true);
      await apiService.runWorkflow(projectId);
      setLaunched(true);
      setTimeout(() => router.push(`/hitl?project=${projectId}`), 1800);
    } catch (e) {
      console.error(e);
      setLaunching(false);
    }
  };

  // ── Pan/Zoom ──
  const handleMouseDown = (e: React.MouseEvent) => {
    if (selectedNode) return; // don't pan when a node is selected
    setIsPanning(true);
    panStart.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning || !panStart.current) return;
    setPan({ x: panStart.current.px + e.clientX - panStart.current.mx, y: panStart.current.py + e.clientY - panStart.current.my });
  };
  const stopPan = () => { setIsPanning(false); panStart.current = null; };
  const handleWheel = (e: React.WheelEvent) => { e.preventDefault(); setZoom((z) => Math.max(0.3, Math.min(2.5, z + (e.deltaY > 0 ? -0.1 : 0.1)))); };

  // ── Highlight connected nodes ──
  const getHighlighted = (): Set<string> => {
    if (!hoveredNode || !dagData) return new Set();
    const s = new Set([hoveredNode]);
    dagData.dag.edges.forEach((e) => {
      if (e.from === hoveredNode) s.add(e.to);
      if (e.to === hoveredNode) s.add(e.from);
    });
    return s;
  };
  const highlighted = getHighlighted();
  const isEdgeHL = (edge: DagEdge) => !!hoveredNode && (edge.from === hoveredNode || edge.to === hoveredNode);

  const resetView = () => { setZoom(0.85); setPan({ x: 50, y: 50 }); };

  // ── Loading state ──
  if (loading) {
    return (
      <div style={{ height: "80vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 24 }}>
        <div style={{ position: "relative" }}>
          <div style={{ width: 76, height: 76, borderRadius: "50%", border: "2px solid rgba(59,130,246,0.15)", borderTopColor: "#3b82f6", animation: "spin 1s linear infinite" }} />
          <GitBranch size={26} color="#3b82f6" style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)" }} />
        </div>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "#f9fafb", fontSize: 16, fontWeight: 600, fontFamily: "Outfit, sans-serif" }}>Building Your Agentic Graph…</p>
          <p style={{ color: "#6b7280", fontSize: 13, marginTop: 6 }}>The Planner is analyzing your ICP and designing a unique DAG</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: "80vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="glass-panel" style={{ padding: 40, textAlign: "center", maxWidth: 440 }}>
          <AlertTriangle size={40} color="#ef4444" style={{ margin: "0 auto 16px" }} />
          <h3 style={{ color: "#f9fafb", marginBottom: 8 }}>DAG Generation Failed</h3>
          <p style={{ color: "#9ca3af", marginBottom: 24, fontSize: 13 }}>{error}</p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button className="btn-secondary" onClick={() => router.back()}>← Go Back</button>
            <button className="btn-primary" onClick={() => loadDag(true)}>Try Again</button>
          </div>
        </div>
      </div>
    );
  }

  if (!dagData) return null;

  const { dag, strategy, layout, meta } = dagData;
  const nodeW = layout.node_dims?.width ?? 220;
  const nodeH = layout.node_dims?.height ?? 100;

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes nodeIn { from { opacity:0; transform: translateY(12px) scale(0.95); } to { opacity:1; transform: translateY(0) scale(1); } }
        @keyframes dashFlow { to { stroke-dashoffset: -28; } }
        @keyframes glowPulse { 0%,100% { box-shadow: 0 0 20px rgba(59,130,246,0.2); } 50% { box-shadow: 0 0 44px rgba(59,130,246,0.5); } }
        @keyframes fadeSlideUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

      <div style={{ maxWidth: 1440, margin: "0 auto" }}>

        {/* ── Header ── */}
        <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} style={{ marginBottom: 22 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 5 }}>
                <div style={{
                  background: "linear-gradient(135deg, rgba(59,130,246,0.18), rgba(139,92,246,0.18))",
                  border: "1px solid rgba(59,130,246,0.35)",
                  borderRadius: 10,
                  padding: "7px 9px",
                  display: "flex",
                }}>
                  <GitBranch size={18} color="#60a5fa" />
                </div>
                <h1 style={{ fontSize: "1.85rem", fontFamily: "Outfit, sans-serif", background: "linear-gradient(135deg, #f9fafb 30%, #9ca3af)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text", margin: 0 }}>
                  Agentic Execution Graph
                </h1>
                {meta.is_fallback && (
                  <span style={{ background: "rgba(245,158,11,0.14)", color: "#fbbf24", border: "1px solid rgba(245,158,11,0.28)", borderRadius: 20, padding: "3px 10px", fontSize: 10.5, fontWeight: 700, textTransform: "uppercase" }}>
                    Fallback
                  </span>
                )}
                {meta.from_live_run && (
                  <span style={{ background: "rgba(16,185,129,0.14)", color: "#34d399", border: "1px solid rgba(16,185,129,0.28)", borderRadius: 20, padding: "3px 10px", fontSize: 10.5, fontWeight: 700, textTransform: "uppercase" }}>
                    Live Run
                  </span>
                )}
              </div>
              <p style={{ color: "#6b7280", fontSize: 13, maxWidth: 540, margin: 0 }}>
                The Planner AI analyzed your ICP and designed this unique DAG — every business gets a different graph.
              </p>
            </div>

            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <button
                onClick={() => loadDag(true)}
                disabled={generating}
                className="btn-secondary"
                style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13 }}
              >
                <RefreshCw size={13} style={{ animation: generating ? "spin 1s linear infinite" : "none" }} />
                {generating ? "Regenerating…" : "Regenerate DAG"}
              </button>
              <button
                onClick={handleLaunch}
                disabled={launching || launched}
                className="btn-primary"
                style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, padding: "10px 22px", animation: !launching && !launched ? "glowPulse 3s ease-in-out infinite" : "none" }}
              >
                {launched
                  ? <><CheckCircle size={15} /> Launched! Redirecting…</>
                  : launching
                  ? <><RefreshCw size={15} style={{ animation: "spin 1s linear infinite" }} /> Launching…</>
                  : <><Play size={15} /> Launch Workflow</>}
              </button>
            </div>
          </div>
        </motion.div>

        {/* ── Strategy Banner ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="glass-panel"
          style={{ padding: "16px 22px", marginBottom: 18, display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 180 }}>
            <Sparkles size={15} color="#f59e0b" />
            <div>
              <div style={{ fontSize: 10, color: "#6b7280", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>Strategy</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#f9fafb", fontFamily: "Outfit, sans-serif" }}>{strategy.name}</div>
            </div>
          </div>

          <MetaStat icon={<Layers size={13} color="#60a5fa" />} label="Nodes" value={String(dag.node_count)} color="#60a5fa" />
          <MetaStat icon={<GitBranch size={13} color="#a78bfa" />} label="Edges" value={String(dag.edge_count)} color="#a78bfa" />
          <MetaStat icon={<Cpu size={13} color="#34d399" />} label="Capabilities" value={`${meta.total_capabilities_available ?? "?"} avail.`} color="#34d399" />
          <MetaStat icon={<DollarSign size={13} color="#fbbf24" />} label="Est. Cost" value={`$${strategy.cost_estimate_usd?.toFixed(3) ?? "—"}`} color="#fbbf24" />
          {meta.icp_industry && meta.icp_industry.length > 0 && (
            <MetaStat icon={<Target size={13} color="#f472b6" />} label="Industry" value={meta.icp_industry.slice(0, 2).join(", ")} color="#f472b6" />
          )}

          {strategy.rationale && (
            <div style={{ flex: "0 0 100%", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 13, marginTop: 2, fontSize: 12, color: "#9ca3af", lineHeight: 1.65, display: "flex", gap: 8, alignItems: "flex-start" }}>
              <Info size={12} color="#6b7280" style={{ flexShrink: 0, marginTop: 2 }} />
              <span><strong style={{ color: "#d1d5db" }}>Planner Rationale:</strong> {strategy.rationale}</span>
            </div>
          )}
        </motion.div>

        {/* ── Canvas + Sidebar ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          style={{ display: "flex", gap: 14, alignItems: "flex-start" }}
        >
          {/* Graph canvas */}
          <div
            className="glass-panel"
            style={{
              flex: 1,
              position: "relative",
              overflow: "hidden",
              borderRadius: 18,
              minHeight: 540,
              cursor: isPanning ? "grabbing" : "grab",
              background: "rgba(7,10,18,0.9)",
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={stopPan}
            onMouseLeave={stopPan}
            onWheel={handleWheel}
          >
            {/* Grid */}
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.028)" strokeWidth="1" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>

            {/* Zoom controls */}
            <div style={{ position: "absolute", top: 14, right: 14, display: "flex", flexDirection: "column", gap: 6, zIndex: 10 }}>
              {[
                { icon: <ZoomIn size={15} />, action: () => setZoom((z) => Math.min(2.5, z + 0.15)), title: "Zoom In" },
                { icon: <ZoomOut size={15} />, action: () => setZoom((z) => Math.max(0.3, z - 0.15)), title: "Zoom Out" },
                { icon: <Maximize2 size={15} />, action: resetView, title: "Reset View" },
              ].map(({ icon, action, title }) => (
                <button key={title} onClick={action} className="btn-icon" title={title}>{icon}</button>
              ))}
            </div>

            {/* Zoom label */}
            <div style={{ position: "absolute", bottom: 12, left: 14, zIndex: 10, background: "rgba(0,0,0,0.55)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 6, padding: "3px 9px", fontSize: 10.5, color: "#6b7280" }}>
              {Math.round(zoom * 100)}%
            </div>
            <div style={{ position: "absolute", bottom: 12, right: 14, zIndex: 10, background: "rgba(0,0,0,0.55)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 6, padding: "3px 9px", fontSize: 10, color: "#4b5563" }}>
              Scroll to zoom · Drag to pan · Click node for details
            </div>

            {/* DAG SVG */}
            <svg width="100%" height="100%" style={{ minHeight: 540, display: "block", userSelect: "none" }}>
              <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
                {/* Edges */}
                {dag.edges.map((edge) => {
                  const fromNode = dag.nodes.find((n) => n.task_id === edge.from);
                  const toNode = dag.nodes.find((n) => n.task_id === edge.to);
                  if (!fromNode || !toNode) return null;
                  return (
                    <EdgeArrow
                      key={`${edge.from}__${edge.to}`}
                      fromNode={fromNode}
                      toNode={toNode}
                      edge={edge}
                      nodeW={nodeW}
                      nodeH={nodeH}
                      isHighlighted={isEdgeHL(edge)}
                    />
                  );
                })}

                {/* Nodes */}
                {dag.nodes.map((node, i) => (
                  <g
                    key={node.task_id}
                    onMouseEnter={() => setHoveredNode(node.task_id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={(e) => { e.stopPropagation(); setSelectedNode(selectedNode?.task_id === node.task_id ? null : node); }}
                    style={{ cursor: "pointer" }}
                  >
                    <DagNodeCard
                      node={node}
                      nodeW={nodeW}
                      nodeH={nodeH}
                      isSelected={selectedNode?.task_id === node.task_id}
                      isHighlighted={highlighted.has(node.task_id) && !selectedNode}
                      animDelay={i * 90}
                    />
                  </g>
                ))}
              </g>
            </svg>

            {/* Empty state */}
            {dag.nodes.length === 0 && (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
                <GitBranch size={36} color="#374151" />
                <p style={{ color: "#6b7280", fontSize: 14 }}>No DAG nodes generated</p>
                <button className="btn-primary" onClick={() => loadDag(true)}>Generate DAG</button>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div style={{ width: 268, flexShrink: 0 }}>
            <AnimatePresence mode="wait">
              {selectedNode ? (
                <motion.div
                  key="detail"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="glass-panel" style={{ padding: 22, borderRadius: 16, overflowY: "auto", maxHeight: "calc(100vh - 220px)" }}>
                    <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="legend"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <LegendPanel dag={dag} strategy={strategy} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* ── Bottom CTA ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="glass-panel"
          style={{ marginTop: 18, padding: "18px 26px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14 }}
        >
          <div>
            <div style={{ fontSize: 14.5, fontWeight: 600, color: "#f9fafb", fontFamily: "Outfit, sans-serif", marginBottom: 3 }}>
              Ready to run this agentic workflow?
            </div>
            <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>
              This DAG was uniquely designed for your business — agents execute in the dependency order shown above.
            </p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <button onClick={() => router.back()} className="btn-secondary" style={{ fontSize: 13 }}>← Edit ICP</button>
            <button
              onClick={handleLaunch}
              disabled={launching || launched}
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, padding: "10px 24px" }}
            >
              {launched
                ? <><CheckCircle size={15} /> Launched!</>
                : launching
                ? <><RefreshCw size={15} style={{ animation: "spin 1s linear infinite" }} /> Launching…</>
                : <>Launch Workflow <ArrowRight size={15} /></>}
            </button>
          </div>
        </motion.div>

      </div>
    </>
  );
}
