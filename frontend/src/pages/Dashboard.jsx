import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import AdminDashboard from "./dashboards/AdminDashboard";
import PostSalesDashboard from "./dashboards/PostSalesDashboard";
import AccountsDashboard from "./dashboards/AccountsDashboard";
import SiteManagerDashboard from "./dashboards/SiteManagerDashboard";
import ManagementDashboard from "./dashboards/ManagementDashboard";

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.get("/dashboard").then((r) => { if (alive) { setStats(r.data); setLoading(false); } })
      .catch(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const props = { stats, loading, user };
  switch (user?.role) {
    case "admin": return <AdminDashboard {...props} />;
    case "post_sales": return <PostSalesDashboard {...props} />;
    case "accounts": return <AccountsDashboard {...props} />;
    case "site_manager": return <SiteManagerDashboard {...props} />;
    case "management": return <ManagementDashboard {...props} />;
    default: return <div className="text-ink2" data-testid="dashboard-page">Loading…</div>;
  }
}
