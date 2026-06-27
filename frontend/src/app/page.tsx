"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight, Bot, Target } from "lucide-react";
import { apiService } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [description, setDescription] = useState(
    "We provide cybersecurity software for banks. Our ideal customers are financial institutions with more than 500 employees that recently expanded their security teams."
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;
    
    try {
      console.log("[Frontend] Form submitted with description:", description);
      setIsSubmitting(true);
      // 1. Create the project
      console.log("[Frontend] Calling apiService.createProject...");
      const projectRes = await apiService.createProject(description);
      const projectId = projectRes.data.id;
      console.log("[Frontend] Project created successfully. Project ID:", projectId);
      
      // 2. Trigger Business Understanding AI
      console.log("[Frontend] Calling apiService.generateIcp...");
      const icpRes = await apiService.generateIcp(projectId, description);
      console.log("[Frontend] ICP generation complete. Response:", icpRes.data);
      
      // 3. Redirect to the ICP Review Screen
      console.log(`[Frontend] Redirecting to /project/${projectId}/icp`);
      router.push(`/project/${projectId}/icp`);
    } catch (error) {
      console.error("[Frontend] Failed to create project or generate ICP:", error);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="container" style={{ minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ maxWidth: "800px", width: "100%", textAlign: "center" }}
      >
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "24px" }}>
          <div style={{ 
            background: "rgba(59, 130, 246, 0.1)",
            padding: "16px",
            borderRadius: "50%",
            border: "1px solid rgba(59, 130, 246, 0.3)"
          }}>
            <Bot size={48} className="text-gradient" />
          </div>
        </div>
        
        <h1 style={{ fontSize: "3.5rem", marginBottom: "16px", lineHeight: 1.1 }}>
          The Platform Learns <br/>
          <span className="text-gradient">Your Business First.</span>
        </h1>
        
        <p className="text-muted" style={{ fontSize: "1.2rem", marginBottom: "48px", maxWidth: "600px", margin: "0 auto 48px auto" }}>
          Enter a description of what you sell and who you sell to. 
          We'll dynamically build an agentic workflow tailored to your domain.
        </p>

        <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: "32px", textAlign: "left" }}>
          <div style={{ display: "flex", gap: "8px", marginBottom: "16px", color: "var(--accent-primary)" }}>
            <Target size={20} />
            <h3 style={{ fontSize: "1.1rem" }}>Business Description</h3>
          </div>
          
          <textarea 
            className="input-field"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            placeholder="Describe your business and ideal customers..."
            style={{ marginBottom: "24px", resize: "none" }}
            disabled={isSubmitting}
          />
          
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button 
              type="submit" 
              className="btn-primary" 
              style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "1.05rem" }}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>Generating Business Rules...</>
              ) : (
                <>Build My Agentic Workflow <ArrowRight size={18} /></>
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
