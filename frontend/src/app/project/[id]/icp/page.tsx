"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiService } from "@/lib/api";
import { motion } from "framer-motion";
import { Check, Edit2, Play, AlertCircle, RefreshCw } from "lucide-react";

export default function IcpReviewPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  
  const [icpData, setIcpData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    if (projectId) {
      loadIcp();
    }
  }, [projectId]);

  const loadIcp = async () => {
    try {
      const res = await apiService.getIcp(projectId);
      setIcpData(res.data);
      setLoading(false);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    try {
      setIsStarting(true);
      await apiService.confirmIcp(projectId);
      await apiService.runWorkflow(projectId);
      router.push(`/hitl?project=${projectId}`);
    } catch (err) {
      console.error(err);
      setIsStarting(false);
    }
  };

  const handleEdit = (section: string) => {
    // In a full implementation, this would open an inline editor or modal.
    // For demo purposes, we will just alert.
    alert(`Editing ${section} is supported in the full build. You can modify the JSON directly via API for now.`);
  };

  if (loading) {
    return (
      <div className="container flex-center" style={{ minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }} className="text-muted">
          <RefreshCw className="spin" size={48} style={{ marginBottom: "16px", animation: "spin 1s linear infinite" }} />
          <h2>Generating Business Rules...</h2>
          <p>Analyzing description and extracting ICP parameters.</p>
        </div>
        <style dangerouslySetInnerHTML={{__html: `
          @keyframes spin { 100% { transform: rotate(360deg); } }
        `}} />
      </div>
    );
  }

  if (!icpData) {
    return <div className="container"><p>Failed to load ICP data.</p></div>;
  }

  return (
    <div className="container">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
        
        <div className="flex-between" style={{ marginBottom: "32px", paddingBottom: "16px", borderBottom: "1px solid var(--border-color)" }}>
          <div>
            <h1 style={{ fontSize: "2rem", marginBottom: "8px" }}>Business Understanding Review</h1>
            <p className="text-muted">Review and refine the AI-generated execution rules before starting the agents.</p>
          </div>
          <button 
            onClick={handleConfirm} 
            className="btn-primary" 
            style={{ display: "flex", gap: "8px", alignItems: "center" }}
            disabled={isStarting}
          >
            {isStarting ? <RefreshCw size={18} className="spin" style={{ animation: "spin 1s linear infinite" }}/> : <Play size={18} />}
            {isStarting ? "Starting Agents..." : "Confirm & Start Monitoring"}
          </button>
        </div>

        <div className="grid-2">
          {/* Left Column */}
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            
            <div className="glass-card" style={{ padding: "24px" }}>
              <div className="flex-between mb-4">
                <h3 style={{ color: "var(--accent-primary)" }}>Ideal Customer Profile (ICP)</h3>
                <button className="btn-icon" onClick={() => handleEdit("ICP")}><Edit2 size={16} /></button>
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div>
                  <div className="text-xs text-muted mb-2">Industries</div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {icpData.industry?.map((ind: string) => (
                      <span key={ind} className="badge badge-info">{ind}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted mb-2">Geography</div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {icpData.geography?.map((geo: string) => (
                      <span key={geo} className="badge badge-info">{geo}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted mb-2">Company Size</div>
                  <div className="font-medium">{icpData.company_size?.min || icpData.employee_count_min || '1'} - {icpData.company_size?.max || icpData.employee_count_max || '10000+'} employees</div>
                </div>
                <div>
                  <div className="text-xs text-muted mb-2">Revenue</div>
                  <div className="font-medium">{icpData.revenue_range?.min || '$0'} - {icpData.revenue_range?.max || '$1B+'}</div>
                </div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: "24px" }}>
              <div className="flex-between mb-4">
                <h3 style={{ color: "var(--accent-secondary)" }}>Target Personas</h3>
                <button className="btn-icon" onClick={() => handleEdit("Personas")}><Edit2 size={16} /></button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {icpData.personas?.map((persona: any, idx: number) => (
                  <div key={idx} style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                    <div className="flex-between">
                      <div className="font-medium">{persona.title}</div>
                      <span className={`badge ${persona.priority === 'High' ? 'badge-success' : 'badge-warning'}`}>
                        {persona.priority} Priority
                      </span>
                    </div>
                    <div className="text-xs text-muted mt-2">Seniority: {persona.seniority}</div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Right Column */}
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            
            <div className="glass-card" style={{ padding: "24px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
              <div className="flex-between mb-4">
                <h3 style={{ color: "var(--accent-success)" }}>Qualification Rules</h3>
                <button className="btn-icon" onClick={() => handleEdit("Rules")}><Edit2 size={16} /></button>
              </div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "12px" }}>
                {icpData.qualification_rules?.map((rule: any, idx: number) => (
                  <li key={idx} style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                    <Check size={18} color="var(--accent-success)" style={{ marginTop: "2px" }} />
                    <span className="text-sm">{rule.field} {rule.operator} {rule.value}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="glass-card" style={{ padding: "24px", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
              <div className="flex-between mb-4">
                <h3 style={{ color: "var(--accent-warning)" }}>Business Triggers</h3>
                <button className="btn-icon" onClick={() => handleEdit("Triggers")}><Edit2 size={16} /></button>
              </div>
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {icpData.triggers?.map((trigger: any, idx: number) => (
                  <span key={idx} className="badge badge-warning" style={{ background: "rgba(245, 158, 11, 0.1)" }}>
                    {trigger.type}
                  </span>
                ))}
              </div>
            </div>

            <div className="glass-card" style={{ padding: "24px", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
              <div className="flex-between mb-4">
                <h3 style={{ color: "var(--accent-danger)" }}>Disqualifiers</h3>
                <button className="btn-icon" onClick={() => handleEdit("Disqualifiers")}><Edit2 size={16} /></button>
              </div>
              <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "12px" }}>
                {icpData.disqualifiers?.map((rule: any, idx: number) => (
                  <li key={idx} style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                    <AlertCircle size={18} color="var(--accent-danger)" style={{ marginTop: "2px" }} />
                    <span className="text-sm">{rule.condition}</span>
                  </li>
                ))}
              </ul>
            </div>

          </div>
        </div>

      </motion.div>
    </div>
  );
}
