"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Target, ArrowRight } from "lucide-react";
import { apiService } from "@/lib/api";

export function NewProjectForm() {
  const router = useRouter();
  const [description, setDescription] = useState(
    "We provide cybersecurity software for banks. Our ideal customers are financial institutions with more than 500 employees that recently expanded their security teams."
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;
    
    try {
      setIsSubmitting(true);
      const projectRes = await apiService.createProject(description);
      const projectId = projectRes.data.id;
      
      await apiService.generateIcp(projectId, description);
      router.push(`/project/${projectId}/icp`);
    } catch (error) {
      console.error("[Frontend] Failed to create project or generate ICP:", error);
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel slide-up-animation" style={{ padding: "32px", textAlign: "left", animationDelay: "0.2s" }}>
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", color: "var(--accent-primary)" }}>
        <Target size={20} />
        <h2 style={{ fontSize: "1.1rem", margin: 0, fontWeight: 600 }}>Business Description</h2>
      </div>
      
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="e.g., We sell enterprise HR software to mid-sized tech companies in North America."
        className="input-field"
        style={{ 
          width: "100%", 
          minHeight: "120px", 
          marginBottom: "24px",
          fontSize: "1rem",
          lineHeight: 1.5,
          resize: "vertical"
        }}
        required
      />

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button 
          type="submit" 
          className="btn-primary"
          style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "1.1rem", padding: "12px 24px" }}
          disabled={isSubmitting}
        >
          {isSubmitting ? "Building..." : "Build My Agentic Workflow"} 
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
}
