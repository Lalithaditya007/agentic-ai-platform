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
  const [editSection, setEditSection] = useState<string | null>(null);
  const [editData, setEditData] = useState<any>(null);
  const [saveError, setSaveError] = useState("");

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
    setEditSection(section);
    setSaveError("");
    if (section === "ICP") {
      setEditData({
        industry: [...(icpData.industry || [])],
        geography: [...(icpData.geography || [])],
        company_size: { ...(icpData.company_size || {}) },
        revenue_range: { ...(icpData.revenue_range || {}) },
        employee_count_min: icpData.employee_count_min,
        employee_count_max: icpData.employee_count_max
      });
    } else if (section === "Personas") {
      setEditData([...(icpData.personas || [])]);
    } else if (section === "Rules") {
      setEditData([...(icpData.qualification_rules || [])]);
    } else if (section === "Triggers") {
      setEditData([...(icpData.triggers || [])]);
    } else if (section === "Disqualifiers") {
      setEditData([...(icpData.disqualifiers || [])]);
    }
  };

  const handleSaveEdit = async () => {
    try {
      let updatedIcp = { ...icpData };
      if (editSection === "ICP") {
        updatedIcp = { ...updatedIcp, ...editData };
      } else if (editSection === "Personas") {
        updatedIcp.personas = editData;
      } else if (editSection === "Rules") {
        updatedIcp.qualification_rules = editData;
      } else if (editSection === "Triggers") {
        updatedIcp.triggers = editData;
      } else if (editSection === "Disqualifiers") {
        updatedIcp.disqualifiers = editData;
      }
      
      await apiService.updateIcp(projectId, updatedIcp);
      setIcpData(updatedIcp);
      setEditSection(null);
    } catch (err: any) {
      setSaveError("Failed to save: " + (err.message || err));
    }
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

      {editSection && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.7)", zIndex: 1000,
          display: "flex", justifyContent: "center", alignItems: "center"
        }}>
          <div className="glass-card" style={{ width: "600px", maxWidth: "90vw", maxHeight: "90vh", overflowY: "auto", padding: "32px" }}>
            <h3 style={{ marginBottom: "24px", fontSize: "1.5rem" }}>Edit {editSection}</h3>
            
            {editSection === "ICP" && editData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div>
                  <label className="text-sm text-muted mb-2 block" style={{ display: "block" }}>Industries (comma separated)</label>
                  <input className="input-field" value={editData.industry?.join(", ") || ""} onChange={(e) => setEditData({...editData, industry: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean)})} />
                </div>
                <div>
                  <label className="text-sm text-muted mb-2 block" style={{ display: "block" }}>Geography (comma separated)</label>
                  <input className="input-field" value={editData.geography?.join(", ") || ""} onChange={(e) => setEditData({...editData, geography: e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean)})} />
                </div>
                <div className="grid-2">
                  <div>
                    <label className="text-sm text-muted mb-2 block" style={{ display: "block" }}>Min Employees</label>
                    <input type="number" className="input-field" value={editData.company_size?.min || editData.employee_count_min || ''} onChange={(e) => setEditData({...editData, company_size: {...(editData.company_size || {}), min: parseInt(e.target.value)}, employee_count_min: parseInt(e.target.value)})} />
                  </div>
                  <div>
                    <label className="text-sm text-muted mb-2 block" style={{ display: "block" }}>Max Employees</label>
                    <input type="number" className="input-field" value={editData.company_size?.max || editData.employee_count_max || ''} onChange={(e) => setEditData({...editData, company_size: {...(editData.company_size || {}), max: parseInt(e.target.value)}, employee_count_max: parseInt(e.target.value)})} />
                  </div>
                </div>
              </div>
            )}

            {editSection === "Personas" && editData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {editData.map((p: any, idx: number) => (
                  <div key={idx} style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      <div>
                        <label className="text-xs text-muted mb-1 block" style={{ display: "block" }}>Job Title</label>
                        <input className="input-field" value={p.title || ""} onChange={(e) => {
                          const newData = [...editData]; newData[idx].title = e.target.value; setEditData(newData);
                        }} />
                      </div>
                      <div className="grid-2">
                        <div>
                          <label className="text-xs text-muted mb-1 block" style={{ display: "block" }}>Priority</label>
                          <select className="input-field" value={p.priority || "Medium"} onChange={(e) => {
                            const newData = [...editData]; newData[idx].priority = e.target.value; setEditData(newData);
                          }}>
                            <option value="High" style={{background: 'var(--bg-primary)'}}>High</option>
                            <option value="Medium" style={{background: 'var(--bg-primary)'}}>Medium</option>
                            <option value="Low" style={{background: 'var(--bg-primary)'}}>Low</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-xs text-muted mb-1 block" style={{ display: "block" }}>Seniority</label>
                          <input className="input-field" value={p.seniority || ""} onChange={(e) => {
                            const newData = [...editData]; newData[idx].seniority = e.target.value; setEditData(newData);
                          }} />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                <button className="btn-secondary mt-2" onClick={() => setEditData([...editData, { title: "", priority: "Medium", seniority: "" }])}>
                  + Add Persona
                </button>
              </div>
            )}

            {editSection === "Rules" && editData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {editData.map((r: any, idx: number) => (
                  <div key={idx} className="grid-3" style={{ alignItems: "center" }}>
                    <input className="input-field" placeholder="Field" value={r.field || ""} onChange={(e) => {
                      const newData = [...editData]; newData[idx].field = e.target.value; setEditData(newData);
                    }} />
                    <select className="input-field" value={r.operator || "eq"} onChange={(e) => {
                      const newData = [...editData]; newData[idx].operator = e.target.value; setEditData(newData);
                    }}>
                      <option value="eq" style={{background: 'var(--bg-primary)'}}>Equals (eq)</option>
                      <option value="gte" style={{background: 'var(--bg-primary)'}}>Greater/Eq (gte)</option>
                      <option value="lte" style={{background: 'var(--bg-primary)'}}>Less/Eq (lte)</option>
                      <option value="in" style={{background: 'var(--bg-primary)'}}>In (in)</option>
                    </select>
                    <input className="input-field" placeholder="Value" value={r.value || ""} onChange={(e) => {
                      const newData = [...editData]; newData[idx].value = e.target.value; setEditData(newData);
                    }} />
                  </div>
                ))}
                <button className="btn-secondary mt-2" onClick={() => setEditData([...editData, { field: "", operator: "eq", value: "" }])}>
                  + Add Rule
                </button>
              </div>
            )}

            {editSection === "Triggers" && editData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {editData.map((t: any, idx: number) => (
                  <div key={idx} className="flex gap-2">
                    <input className="input-field flex-1" placeholder="Trigger Type (e.g., EXPANSION)" value={t.type || ""} onChange={(e) => {
                      const newData = [...editData]; newData[idx].type = e.target.value.toUpperCase(); setEditData(newData);
                    }} />
                  </div>
                ))}
                <button className="btn-secondary mt-2" onClick={() => setEditData([...editData, { type: "" }])}>
                  + Add Trigger
                </button>
              </div>
            )}

            {editSection === "Disqualifiers" && editData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {editData.map((d: any, idx: number) => (
                  <div key={idx} style={{ background: "rgba(0,0,0,0.2)", padding: "16px", borderRadius: "8px", border: "1px solid var(--border-color)" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      <div>
                        <label className="text-xs text-muted mb-1 block" style={{ display: "block" }}>Condition</label>
                        <input className="input-field" value={d.condition || ""} onChange={(e) => {
                          const newData = [...editData]; newData[idx].condition = e.target.value; setEditData(newData);
                        }} />
                      </div>
                      <div>
                        <label className="text-xs text-muted mb-1 block" style={{ display: "block" }}>Description</label>
                        <textarea className="input-field" style={{ minHeight: "60px" }} value={d.description || ""} onChange={(e) => {
                          const newData = [...editData]; newData[idx].description = e.target.value; setEditData(newData);
                        }} />
                      </div>
                    </div>
                  </div>
                ))}
                <button className="btn-secondary mt-2" onClick={() => setEditData([...editData, { condition: "", description: "", severity: "hard" }])}>
                  + Add Disqualifier
                </button>
              </div>
            )}

            {saveError && <p style={{ color: "var(--accent-danger)", marginTop: "16px" }}>{saveError}</p>}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "32px" }}>
              <button className="btn-secondary" onClick={() => setEditSection(null)}>Cancel</button>
              <button className="btn-primary" onClick={handleSaveEdit}>Save Changes</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
