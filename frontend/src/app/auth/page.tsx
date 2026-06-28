"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase";
import { Mail, Key, LogIn, UserPlus } from "lucide-react";
import { motion } from "framer-motion";

export default function AuthPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "error" | "success" } | null>(null);

  const supabase = createClient();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        setMessage({ text: "Success! Check your email for a verification link.", type: "success" });
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        window.location.href = "/dashboard";
      }
    } catch (err: any) {
      setMessage({ text: err.message, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container flex-center" style={{ minHeight: "80vh" }}>
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          width: "100%",
          maxWidth: "400px",
          background: "var(--card-bg)",
          border: "1px solid var(--border-color)",
          borderRadius: "16px",
          padding: "32px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)"
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <h1 style={{ fontSize: "1.75rem", marginBottom: "8px" }}>
            {isSignUp ? "Create an Account" : "Welcome Back"}
          </h1>
          <p className="text-muted">
            {isSignUp 
              ? "Sign up to start discovering B2B leads automatically." 
              : "Sign in to access your saved Agentic Workflows."}
          </p>
        </div>

        {message && (
          <div style={{
            padding: "12px",
            borderRadius: "8px",
            marginBottom: "24px",
            fontSize: "0.875rem",
            background: message.type === "error" ? "rgba(239, 68, 68, 0.1)" : "rgba(16, 185, 129, 0.1)",
            color: message.type === "error" ? "var(--accent-danger)" : "var(--accent-success)",
            border: `1px solid ${message.type === "error" ? "rgba(239,68,68,0.3)" : "rgba(16,185,129,0.3)"}`
          }}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleAuth} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label className="text-sm text-muted" style={{ display: "block", marginBottom: "8px" }}>Email</label>
            <div style={{ position: "relative" }}>
              <Mail size={18} style={{ position: "absolute", left: "12px", top: "11px", color: "var(--text-muted)" }} />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input-field"
                style={{ width: "100%", paddingLeft: "40px" }}
                placeholder="you@company.com"
              />
            </div>
          </div>

          <div>
            <label className="text-sm text-muted" style={{ display: "block", marginBottom: "8px" }}>Password</label>
            <div style={{ position: "relative" }}>
              <Key size={18} style={{ position: "absolute", left: "12px", top: "11px", color: "var(--text-muted)" }} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input-field"
                style={{ width: "100%", paddingLeft: "40px" }}
                placeholder="••••••••"
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn-primary" 
            style={{ width: "100%", marginTop: "8px", display: "flex", justifyContent: "center", gap: "8px" }}
            disabled={loading}
          >
            {loading ? "Please wait..." : isSignUp ? <><UserPlus size={18} /> Sign Up</> : <><LogIn size={18} /> Sign In</>}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: "24px" }}>
          <button 
            type="button"
            onClick={() => { setIsSignUp(!isSignUp); setMessage(null); }}
            style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.875rem" }}
          >
            {isSignUp ? "Already have an account? Sign In" : "Don't have an account? Sign Up"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
