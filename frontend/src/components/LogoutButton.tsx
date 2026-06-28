"use client";

import { createClient } from "@/lib/supabase";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleLogout = async () => {
    setLoading(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/auth");
  };

  return (
    <button 
      onClick={handleLogout} 
      disabled={loading}
      className="btn-secondary" 
      style={{ display: "flex", gap: "8px", alignItems: "center", padding: "8px 16px", fontSize: "0.9rem" }}
    >
      <LogOut size={16} />
      {loading ? "Logging out..." : "Logout"}
    </button>
  );
}
