import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Building2, Users, Home as HomeIcon,
  HandCoins, Package, Boxes, Bell, LogOut, ChevronDown, Sprout,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, ROLE_LABELS } from "@/lib/auth";
import GlobalSearch from "@/components/GlobalSearch";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin","accounts","post_sales","site_manager"] },
  { to: "/projects", label: "Projects", icon: Building2, roles: ["admin"] },
  { to: "/users", label: "Team", icon: Users, roles: ["admin"] },
  { to: "/units", label: "Units", icon: HomeIcon, roles: ["admin","post_sales"] },
  { to: "/sales", label: "Sales & Payments", icon: HandCoins, roles: ["admin","post_sales","accounts"] },
  { to: "/inventory", label: "Inventory", icon: Boxes, roles: ["admin","site_manager"] },
  { to: "/procurement", label: "Procurement", icon: Package, roles: ["admin","site_manager","accounts"] },
];

function timeAgo(iso) {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const [notifs, setNotifs] = useState([]);
  const [showNotifs, setShowNotifs] = useState(false);
  const [showUser, setShowUser] = useState(false);
  const notifRef = useRef(null);
  const userRef = useRef(null);

  const load = async () => {
    try { const r = await api.get("/notifications"); setNotifs(r.data); } catch {}
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [loc.pathname]);

  useEffect(() => {
    const onClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifs(false);
      if (userRef.current && !userRef.current.contains(e.target)) setShowUser(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const unread = notifs.filter(n => !n.is_read).length;
  const markAll = async () => { await api.post("/notifications/read-all"); load(); };
  const items = NAV.filter(n => n.roles.includes(user?.role));
  const initials = (user?.name || "?").split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="min-h-screen bg-page">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-agborder flex flex-col z-40">
        <div className="h-16 flex items-center gap-3 px-5 border-b border-agborder">
          <div className="w-9 h-9 rounded-sm bg-brand flex items-center justify-center shrink-0">
            <Sprout className="w-5 h-5 text-white" strokeWidth={2.2} />
          </div>
          <div className="leading-tight">
            <div className="font-display font-extrabold text-ink tracking-tight">Agrocorp</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-ink2 font-semibold">Lite Console</div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          <div className="overline px-3 pt-2 pb-2">Workspace</div>
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={`nav-${to.slice(1)}`}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-sm text-sm font-semibold transition-colors duration-200 ${
                  isActive
                    ? "bg-brand text-white"
                    : "text-ink2 hover:bg-surfacealt hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-[18px] h-[18px] ${isActive ? "text-white" : "text-ink2 group-hover:text-ink"}`} strokeWidth={2} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-agborder">
          <div className="px-1 py-2">
            <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-bold">Signed in as</div>
            <div className="text-sm font-semibold text-ink mt-0.5 truncate">{user?.name}</div>
            <div className="text-xs text-ink2">{ROLE_LABELS[user?.role]}</div>
          </div>
        </div>
      </aside>

      {/* Topbar */}
      <header className="fixed top-0 right-0 left-64 h-16 bg-white/80 backdrop-blur-xl border-b border-agborder z-30 px-8 flex items-center justify-between gap-6">
        <GlobalSearch />
        <div className="flex items-center gap-2 shrink-0">
          {/* Notifications */}
          <div className="relative" ref={notifRef}>
            <button onClick={() => setShowNotifs(v => !v)} className="relative w-10 h-10 rounded-sm hover:bg-surfacealt flex items-center justify-center transition-colors duration-200" data-testid="notif-bell">
              <Bell className="w-5 h-5 text-ink2" />
              {unread > 0 && (
                <span className="absolute top-1.5 right-1.5 min-w-[16px] h-4 px-1 bg-bad text-white text-[10px] font-bold rounded-sm flex items-center justify-center font-mono-num">{unread}</span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 top-12 w-96 bg-white border border-agborder rounded-sm shadow-[0_12px_40px_-8px_rgba(20,21,20,0.25)] z-50 ag-modal" data-testid="notif-panel">
                <div className="px-4 py-3 border-b border-agborder flex justify-between items-center">
                  <div className="overline text-ink">Notifications</div>
                  {unread > 0 && <button onClick={markAll} className="text-xs font-semibold text-brand hover:text-brand-hover" data-testid="notif-mark-all">Mark all read</button>}
                </div>
                <div className="max-h-96 overflow-y-auto divide-y divide-agborder">
                  {notifs.length === 0 && <div className="p-8 text-center text-sm text-ink2">You're all caught up.</div>}
                  {notifs.map((n) => (
                    <Link key={n.notification_id} to={n.link || "#"} onClick={() => setShowNotifs(false)}
                          className={`block px-4 py-3 hover:bg-surfacealt transition-colors duration-200 ${!n.is_read ? "bg-brand/[0.04]" : ""}`}>
                      <div className="flex gap-2.5">
                        {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0" />}
                        <div className={!n.is_read ? "" : "pl-4"}>
                          <div className="text-sm text-ink leading-snug">{n.message}</div>
                          <div className="text-[11px] text-ink2 mt-1 font-mono-num">{timeAgo(n.created_at)}</div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* User menu */}
          <div className="relative" ref={userRef}>
            <button onClick={() => setShowUser(v => !v)} className="flex items-center gap-2 pl-1.5 pr-2 py-1.5 rounded-sm hover:bg-surfacealt transition-colors duration-200" data-testid="user-menu">
              <div className="w-8 h-8 rounded-sm bg-brand text-white flex items-center justify-center text-xs font-bold font-display">{initials}</div>
              <span className="text-sm font-semibold text-ink hidden md:block max-w-[120px] truncate">{user?.name}</span>
              <ChevronDown className="w-4 h-4 text-ink2" />
            </button>
            {showUser && (
              <div className="absolute right-0 top-12 w-56 bg-white border border-agborder rounded-sm shadow-[0_12px_40px_-8px_rgba(20,21,20,0.25)] z-50 ag-modal">
                <div className="px-4 py-3 border-b border-agborder">
                  <div className="text-sm font-semibold text-ink truncate">{user?.name}</div>
                  <div className="text-xs text-ink2">{user?.phone}</div>
                </div>
                <button onClick={logout} className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-bad hover:bg-surfacealt transition-colors duration-200" data-testid="logout-btn">
                  <LogOut className="w-4 h-4" /> Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="ml-64 pt-16 min-h-screen">
        <div className="p-8 max-w-[1600px]">{children}</div>
      </main>
    </div>
  );
}
