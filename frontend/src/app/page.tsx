import { createServerSupabaseClient } from "@/lib/supabase-server";
import { redirect } from "next/navigation";
import { Bot } from "lucide-react";
import Link from "next/link";
import { NewProjectForm } from "@/components/NewProjectForm";

export default async function Home() {
  const supabase = await createServerSupabaseClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (!session) {
    redirect("/auth");
  }

  return (
    <div className="container" style={{ minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div 
        style={{ maxWidth: "800px", width: "100%", textAlign: "center" }}
      >
        <div className="slide-up-animation" style={{ display: "flex", justifyContent: "center", marginBottom: "24px" }}>
          <div style={{ 
            background: "rgba(59, 130, 246, 0.1)",
            padding: "16px",
            borderRadius: "50%",
            border: "1px solid rgba(59, 130, 246, 0.3)"
          }}>
            <Bot size={48} className="text-gradient" />
          </div>
        </div>
        
        <h1 className="slide-up-animation" style={{ fontSize: "3rem", marginBottom: "16px", lineHeight: 1.1, animationDelay: "0.1s" }}>
          The Platform Learns<br/>
          <span className="text-gradient">Your Business First.</span>
        </h1>
        
        <p className="text-muted slide-up-animation" style={{ fontSize: "1.25rem", marginBottom: "40px", animationDelay: "0.15s" }}>
          Enter a description of what you sell and who you sell to. We'll<br/>dynamically build an agentic workflow tailored to your domain.
        </p>

        <div className="slide-up-animation" style={{ marginBottom: "32px", animationDelay: "0.18s" }}>
          <Link 
            href="/dashboard" 
            className="btn-secondary" 
            style={{ fontSize: "1rem", padding: "12px 24px", textDecoration: "none", display: "inline-block" }}
          >
            ← Go to My Workspace Dashboard
          </Link>
        </div>

        <NewProjectForm />
      </div>
    </div>
  );
}
