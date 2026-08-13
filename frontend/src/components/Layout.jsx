import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Building2, Users, Home as HomeIcon,
  HandCoins, Package, Boxes, Bell, LogOut, Menu, X, Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAuth, ROLE_LABELS } from "@/lib/auth";
import CommandPalette from "@/components/CommandPalette";
import ErrorBoundary from "@/components/ErrorBoundary";

const NAV = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, roles: ["admin","accounts","post_sales","site_manager","management"] },
  { to: "/projects", label: "Projects", icon: Building2, roles: ["admin","management"], section: "projects" },
  { to: "/units", label: "Units", icon: HomeIcon, roles: ["admin","post_sales","management"], section: "units" },
  { to: "/sales", label: "Sales", icon: HandCoins, roles: ["admin","post_sales","accounts","management"], section: "sales" },
  { to: "/inventory", label: "Inventory", icon: Boxes, roles: ["admin","site_manager","management"], section: "inventory" },
  { to: "/procurement", label: "Procurement", icon: Package, roles: ["admin","site_manager","accounts","management"], section: "procurement" },
  { to: "/users", label: "Team", icon: Users, roles: ["admin","management"], section: "users" },
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
  const [menuOpen, setMenuOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const notifRef = useRef(null);
  const userRef = useRef(null);

  const load = async () => { try { const r = await api.get("/notifications"); setNotifs(r.data); } catch {} };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [loc.pathname]);
  useEffect(() => { setMenuOpen(false); }, [loc.pathname]);

  useEffect(() => {
    const onClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifs(false);
      if (userRef.current && !userRef.current.contains(e.target)) setShowUser(false);
    };
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdOpen(v => !v); }
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, []);

  useEffect(() => {
    const TIMEOUT = 5 * 60 * 1000;
    let timer;
    const doLogout = () => { toast.error("Signed out due to inactivity"); logout(); };
    const reset = () => { clearTimeout(timer); timer = setTimeout(doLogout, TIMEOUT); };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => { clearTimeout(timer); events.forEach((e) => window.removeEventListener(e, reset)); };
  }, [logout]);

  const unread = notifs.filter(n => !n.is_read).length;
  const markAll = async () => { await api.post("/notifications/read-all"); load(); };
  const items = NAV.filter(n => n.roles.includes(user?.role)
    && (user?.role !== "management" || !n.section || (user?.permissions || []).includes(n.section)));
  const initials = (user?.name || "?").split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();

  const Brand = (
    <Link to="/dashboard" className="flex items-center gap-3 shrink-0 group">
      <div className="w-10 h-10 rounded-xl brandplate group-hover:scale-[1.03] transition-transform duration-200">
        <img src="/agrocorp-arch-white.webp" alt="Agrocorp" className="w-6 h-6 object-contain" />
      </div>
      <div className="leading-none hidden sm:block">
        <div className="font-display text-[19px] font-semibold text-ink tracking-tight">Management Dashboard</div>
        <div className="text-[9.5px] uppercase tracking-[0.22em] text-ink2 font-semibold mt-0.5">Stakeholder Console</div>
      </div>
    </Link>
  );

  return (
    <div className="min-h-screen bg-page">
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} navItems={items} />

      <header className="sticky top-0 z-30 bg-page/85 backdrop-blur-xl border-b border-line">
        <div className="max-w-[1680px] mx-auto px-5 lg:px-10 h-[68px] flex items-center gap-6">
          {Brand}

          <nav className="hidden lg:flex items-center gap-1 flex-1 pl-4">
            {items.map(({ to, label }) => (
              <NavLink key={to} to={to} data-testid={`nav-${to.slice(1)}`}
                className="navlink px-3 py-2 rounded-lg hover:bg-surfacealt/70">
                {({ isActive }) => (
                  <span className="relative" data-active={isActive}>
                    <span className={isActive ? "text-ink" : ""}>{label}</span>
                    {isActive && <span className="absolute -bottom-2 left-0 right-0 h-[2px] rounded-full" style={{ background: "#ccff00" }} />}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2 ml-auto lg:ml-0 shrink-0">
            <button onClick={() => setCmdOpen(true)} data-testid="command-trigger"
              className="hidden sm:flex items-center gap-2 pl-3 pr-2 py-2 rounded-lg border border-line bg-white text-ink2 hover:border-ink/20 transition-colors duration-200">
              <Search className="w-4 h-4" strokeWidth={1.75} />
              <span className="text-[13px] pr-6">Search…</span>
              <span className="kbd2">⌘K</span>
            </button>
            <button onClick={() => setCmdOpen(true)} className="sm:hidden w-10 h-10 rounded-lg border border-line bg-white flex items-center justify-center" data-testid="command-trigger-mobile">
              <Search className="w-4 h-4 text-ink2" strokeWidth={1.75} />
            </button>

            <div className="relative" ref={notifRef}>
              <button onClick={() => setShowNotifs(v => !v)} className="relative w-10 h-10 rounded-lg hover:bg-surfacealt flex items-center justify-center transition-colors duration-200" data-testid="notif-bell">
                <Bell className="w-5 h-5 text-ink2" strokeWidth={1.75} />
                {unread > 0 && <span className="absolute top-1.5 right-1.5 min-w-[16px] h-4 px-1 bg-plate text-lime text-[10px] font-bold rounded-md flex items-center justify-center font-mono-num">{unread}</span>}
              </button>
              {showNotifs && (
                <div className="fixed sm:absolute top-[68px] sm:top-12 left-3 right-3 sm:left-auto sm:right-0 w-auto sm:w-96 bg-white border border-line rounded-xl shadow-[0_20px_60px_-15px_rgba(20,21,20,0.3)] z-50 ag-modal overflow-hidden" data-testid="notif-panel">
                  <div className="px-4 py-3 border-b border-line flex justify-between items-center">
                    <div className="overline text-ink">Notifications</div>
                    {unread > 0 && <button onClick={markAll} className="text-xs font-semibold text-brand hover:text-brand-hover" data-testid="notif-mark-all">Mark all read</button>}
                  </div>
                  <div className="max-h-96 overflow-y-auto divide-y divide-line">
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

            <div className="relative" ref={userRef}>
              <button onClick={() => setShowUser(v => !v)} className="flex items-center gap-2 pl-1 pr-1 sm:pr-2 py-1 rounded-lg hover:bg-surfacealt transition-colors duration-200" data-testid="user-menu">
                <div className="w-9 h-9 rounded-lg bg-plate text-lime flex items-center justify-center text-xs font-bold font-mono-num">{initials}</div>
                <span className="text-sm font-medium text-ink hidden md:block max-w-[110px] truncate">{user?.name?.split(" ")[0]}</span>
              </button>
              {showUser && (
                <div className="absolute right-0 top-12 w-60 bg-white border border-line rounded-xl shadow-[0_20px_60px_-15px_rgba(20,21,20,0.3)] z-50 ag-modal overflow-hidden">
                  <div className="px-4 py-3.5 border-b border-line">
                    <div className="text-sm font-semibold text-ink truncate">{user?.name}</div>
                    <div className="text-xs text-ink2 mt-0.5">{ROLE_LABELS[user?.role]} · {user?.phone}</div>
                  </div>
                  <button onClick={logout} className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-bad hover:bg-surfacealt transition-colors duration-200" data-testid="logout-btn">
                    <LogOut className="w-4 h-4" /> Sign out
                  </button>
                </div>
              )}
            </div>

            <button onClick={() => setMenuOpen(true)} className="lg:hidden w-10 h-10 rounded-lg hover:bg-surfacealt flex items-center justify-center" data-testid="sidebar-open">
              <Menu className="w-5 h-5 text-ink" />
            </button>
          </div>
        </div>
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-nav">
          <div className="absolute inset-0 bg-plate/40" onClick={() => setMenuOpen(false)} data-testid="sidebar-backdrop" />
          <div className="absolute right-0 top-0 bottom-0 w-72 max-w-[85%] bg-white border-l border-line p-4 flex flex-col ag-modal">
            <div className="flex items-center justify-between mb-4">
              <div className="font-display text-lg font-semibold text-ink">Menu</div>
              <button onClick={() => setMenuOpen(false)} className="w-9 h-9 rounded-lg hover:bg-surfacealt flex items-center justify-center" data-testid="sidebar-close"><X className="w-5 h-5 text-ink2" /></button>
            </div>
            <nav className="space-y-1">
              {items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} data-testid={`mnav-${to.slice(1)}`}
                  className={({ isActive }) => `flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-colors duration-200 ${isActive ? "bg-plate text-white" : "text-ink2 hover:bg-surfacealt"}`}>
                  <Icon className="w-[18px] h-[18px]" strokeWidth={1.75} /> {label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}

      <main className="max-w-[1680px] mx-auto px-5 sm:px-8 lg:px-10 py-8 lg:py-12">
        <ErrorBoundary routeKey={loc.pathname}>{children}</ErrorBoundary>
      </main>
    </div>
  );
}
