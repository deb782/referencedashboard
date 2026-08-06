import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Building2, Users, Home as HomeIcon,
  HandCoins, Package, Boxes, Bell, LogOut, KeyRound,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, ROLE_LABELS } from "@/lib/auth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin","accounts","post_sales","site_manager"] },
  { to: "/projects", label: "Projects", icon: Building2, roles: ["admin"] },
  { to: "/users", label: "Team", icon: Users, roles: ["admin"] },
  { to: "/units", label: "Units", icon: HomeIcon, roles: ["admin","post_sales"] },
  { to: "/sales", label: "Sales & Payments", icon: HandCoins, roles: ["admin","post_sales","accounts"] },
  { to: "/inventory", label: "Inventory", icon: Boxes, roles: ["admin","site_manager"] },
  { to: "/procurement", label: "Procurement", icon: Package, roles: ["admin","site_manager","accounts"] },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const [notifs, setNotifs] = useState([]);
  const [showNotifs, setShowNotifs] = useState(false);

  const load = async () => {
    try { const r = await api.get("/notifications"); setNotifs(r.data); } catch {}
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [loc.pathname]);

  const unread = notifs.filter(n => !n.is_read).length;
  const markAll = async () => { await api.post("/notifications/read-all"); load(); };

  const items = NAV.filter(n => n.roles.includes(user?.role));

  return (
    <div className="min-h-screen bg-stone-50 flex">
      <aside className="w-64 bg-white border-r border-stone-200 flex flex-col">
        <div className="p-4 border-b border-stone-200">
          <div className="text-lg font-bold text-emerald-900">Agrocorp Lite</div>
          <div className="text-[10px] uppercase tracking-widest text-stone-400">Stakeholder Console</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={`nav-${to.slice(1)}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm ${
                  isActive
                    ? "bg-emerald-900 text-white"
                    : "text-stone-700 hover:bg-stone-100"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-stone-200">
          <div className="text-sm font-medium">{user?.name}</div>
          <div className="text-xs text-stone-500 mb-2">{ROLE_LABELS[user?.role]}</div>
          <button onClick={logout} className="text-xs text-stone-500 hover:text-rose-700 flex items-center gap-1" data-testid="logout-btn">
            <LogOut className="w-3 h-3" /> Logout
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col">
        <header className="h-14 bg-white border-b border-stone-200 flex items-center justify-end px-6 gap-3 relative">
          <div className="relative">
            <button onClick={() => setShowNotifs(!showNotifs)} className="relative p-2 rounded-md hover:bg-stone-100" data-testid="notif-bell">
              <Bell className="w-5 h-5 text-stone-600" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-rose-600 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">{unread}</span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 top-11 w-96 bg-white border border-stone-200 rounded-lg shadow-lg z-20">
                <div className="p-3 border-b border-stone-200 flex justify-between items-center">
                  <div className="text-sm font-semibold">Notifications</div>
                  {unread > 0 && <button onClick={markAll} className="text-xs text-emerald-800">Mark all read</button>}
                </div>
                <div className="max-h-96 overflow-y-auto divide-y divide-stone-100">
                  {notifs.length === 0 && (
                    <div className="p-6 text-center text-sm text-stone-500">No notifications yet</div>
                  )}
                  {notifs.map((n) => (
                    <Link key={n.notification_id} to={n.link || "#"}
                          onClick={() => setShowNotifs(false)}
                          className={`block p-3 hover:bg-stone-50 ${!n.is_read ? "bg-emerald-50/50" : ""}`}>
                      <div className="text-sm">{n.message}</div>
                      <div className="text-[11px] text-stone-400 mt-1">
                        {new Date(n.created_at).toLocaleString()}
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 p-8 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
