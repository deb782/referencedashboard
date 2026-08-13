import { Link } from "react-router-dom";
import { Boxes, Package, ArrowUpRight, Clock, CheckCircle2, AlertTriangle } from "lucide-react";
import { StatusPill, EmptyState } from "@/components/ui";

const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };
const today = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

export default function SiteManagerDashboard({ stats, user }) {
  const s = stats || {};
  const low = s.low_stock || [];
  const proc = s.recent_procurement || [];
  const by = s.procurement_by_status || {};
  const open = (by.pending_admin || 0) + (by.pending_clarification || 0) + (by.pending_management || 0) + (by.management_clarification || 0);
  const approved = (by.approved || 0) + (by.paid || 0) + (by.po_issued || 0);
  const maxQty = Math.max(10, ...low.map((i) => Number(i.quantity) || 0));

  return (
    <div data-testid="dashboard-page" className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">{today()} · Tactical Operations</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">
            {greeting()}, {user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-sm text-ink2 mt-3 max-w-xl leading-relaxed">Keep material stock accurate and raise procurement the moment you're running low.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/inventory" className="btn-secondary" data-testid="dash-goto-inventory"><Boxes className="w-4 h-4" /> Inventory</Link>
          <Link to="/procurement" className="btn-primary" data-testid="dash-raise-procurement"><Package className="w-4 h-4" /> Raise request</Link>
        </div>
      </header>

      <section className="panel overflow-hidden ag-rise">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-line">
          <StatCell label="Material Items" value={s.inventory_count ?? 0} icon={Boxes} />
          <StatCell label="Low Stock" value={low.length} icon={AlertTriangle} tone="text-clay" lime={low.length > 0} />
          <StatCell label="Open Requests" value={open} icon={Clock} tone="text-warn" />
          <StatCell label="Approved" value={approved} icon={CheckCircle2} tone="text-ok" />
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="panel">
          <PanelHead title="Low Stock · Reorder soon" to="/inventory" cta="Manage" />
          {low.length === 0 ? (
            <EmptyState icon={Boxes} title="Stock looks healthy" hint="Nothing is running low right now." />
          ) : (
            <div className="p-6 lg:p-7 space-y-4">
              {low.map((i) => {
                const pct = Math.min(100, Math.round(((Number(i.quantity) || 0) / maxQty) * 100));
                return (
                  <div key={i.item_id}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="text-sm font-medium text-ink">{i.name}</div>
                      <div className="text-sm font-mono-num text-clay font-semibold">{i.quantity} {i.unit}</div>
                    </div>
                    <div className="h-1.5 bg-surfacealt rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-clay transition-[width] duration-700 ease-out" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="panel">
          <PanelHead title="My Procurement Requests" to="/procurement" cta="All" />
          {proc.length === 0 ? (
            <EmptyState icon={Package} title="No requests yet"
              hint="Raise a procurement request when you need materials."
              action={<Link to="/procurement" className="btn-primary" data-testid="dash-empty-proc"><Package className="w-4 h-4" /> Raise a request</Link>} />
          ) : (
            <div className="divide-y divide-line">
              {proc.map((p) => (
                <Link to="/procurement" key={p.request_id} className="block px-6 py-4 hover:bg-surfacealt transition-colors duration-200">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-ink truncate">{p.subject}</div>
                    <StatusPill status={p.status} />
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <StatusPill status={p.priority} dot={false} />
                    <span className="text-xs text-ink2">{(p.items || []).length} item(s)</span>
                    {p.admin_note && <span className="text-xs text-clay truncate">· {p.admin_note}</span>}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCell({ label, value, icon: Icon, tone = "text-ink", lime }) {
  return (
    <div className="p-6 lg:p-7">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-semibold flex items-center gap-1.5">
          {lime && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#ccff00" }} />}{label}
        </div>
        {Icon && <Icon className={`w-4 h-4 ${tone} opacity-60`} strokeWidth={1.5} />}
      </div>
      <div className={`kpi-value text-4xl lg:text-5xl mt-4 ${tone}`}>{value}</div>
    </div>
  );
}

function PanelHead({ title, to, cta }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-line">
      <div className="overline text-ink">{title}</div>
      {to && <Link to={to} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">{cta} <ArrowUpRight className="w-3.5 h-3.5" /></Link>}
    </div>
  );
}
