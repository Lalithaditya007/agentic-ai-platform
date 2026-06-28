import { createServerSupabaseClient } from "@/lib/supabase-server";
import { redirect } from "next/navigation";
import { Folder, Play, Edit3, Clock } from "lucide-react";
import Link from "next/link";
import { API_URL } from "@/lib/api";
import { LogoutButton } from "@/components/LogoutButton";

// 1. Mark as an async Server Component (no "use client")
export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient();
  
  // 2. Fetch auth user server-side
  const { data: { user } } = await supabase.auth.getUser();
  const { data: { session } } = await supabase.auth.getSession();

  if (!user || !session) {
    redirect("/auth");
  }

  // 3. Fetch projects server-side
  let projects: any[] = [];
  try {
    // Next.js server component fetch with no-store to ensure it's dynamic
    const res = await fetch(`${API_URL}/api/projects`, {
      headers: {
        "Authorization": `Bearer ${session.access_token}`
      },
      cache: "no-store",
    });
    
    if (res.ok) {
      const data = await res.json();
      projects = Array.isArray(data) ? data : (data.projects || []);
    }
  } catch (err) {
    console.error("Failed to load projects on server", err);
  }

  return (
    <div className="container" style={{ padding: "40px 20px" }}>
      <div className="flex-between mb-8">
        <div>
          <h1 style={{ fontSize: "2.5rem", marginBottom: "8px", fontWeight: "700" }}>Your Workspace</h1>
          <p className="text-muted" style={{ fontSize: "1.1rem" }}>
            Welcome back, {user?.email}. Manage your agentic workflows and saved ICPs.
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <LogoutButton />
          <Link href="/" className="btn-primary" style={{ display: "flex", gap: "8px", alignItems: "center", textDecoration: "none" }}>
            <Folder size={18} /> New Project
          </Link>
        </div>
      </div>

      <div className="grid-3">
        {projects.map((project: any, i: number) => (
          <div 
            key={project.id}
            className="project-card slide-up-animation"
            style={{
              background: "var(--card-bg)",
              border: "1px solid var(--border-color)",
              borderRadius: "12px",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              position: "relative",
              overflow: "hidden",
              animationDelay: `${i * 0.1}s`
            }}
          >
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "4px", background: "linear-gradient(90deg, var(--accent-primary), var(--accent-secondary))" }} />
            
            <div className="flex-between">
              <h3 style={{ fontSize: "1.25rem", margin: 0 }}>{project.name}</h3>
              <span style={{ fontSize: "0.75rem", background: "rgba(255,255,255,0.05)", padding: "4px 8px", borderRadius: "12px", color: "var(--text-muted)" }}>
                {project.status}
              </span>
            </div>
            
            <p className="text-muted text-sm" style={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
              {project.business_description}
            </p>

            <div style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "auto", paddingTop: "16px", borderTop: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted)", fontSize: "0.875rem" }}>
                <Clock size={14} />
                {new Date(project.created_at).toLocaleDateString()}
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
              <Link 
                href={`/?project=${project.id}`} 
                className="btn-secondary flex-center"
                style={{ flex: 1, gap: "6px", textDecoration: "none", fontSize: "0.875rem" }}
              >
                <Edit3 size={14} /> Edit ICP
              </Link>
              <Link 
                href={`/hitl?project=${project.id}`} 
                className="btn-primary flex-center"
                style={{ flex: 1, gap: "6px", textDecoration: "none", fontSize: "0.875rem" }}
              >
                <Play size={14} /> View Leads
              </Link>
            </div>
          </div>
        ))}

        {projects.length === 0 && (
          <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: "64px", background: "rgba(255,255,255,0.02)", borderRadius: "16px", border: "1px dashed var(--border-color)" }}>
            <Folder size={48} style={{ color: "var(--text-muted)", marginBottom: "16px", opacity: 0.5 }} />
            <h3 style={{ marginBottom: "8px" }}>No projects yet</h3>
            <p className="text-muted mb-6">Create your first agentic workflow to start discovering B2B leads.</p>
            <Link href="/" className="btn-primary" style={{ textDecoration: "none" }}>
              Get Started
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
