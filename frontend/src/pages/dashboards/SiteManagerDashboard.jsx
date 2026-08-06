import { Link } from "react-router-dom";
import { Boxes, AlertTriangle, Package, ArrowUpRight, Clock, CheckCircle2 } from "lucide-react";
import { PageHeader, Kpi, StatusPill, SectionCard, EmptyState } from "@/components/ui";

export default function SiteManagerDashboard({ stats, user }) {
  const s = stats || {};
  const low = s.low_stock || [];
  const proc = s.recent_procurement || [];
  const by = s.procurement_by_status || {};
  const open = (by.pending_admin || 0) + (by.pending_clarification || 0);

  const maxQty = Math.max(10, ...low.map((i) => Number(i.quantity) || 0));

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        overline="Tactical Operations"
        title={`On-site status, ${user?.name?.split(" ")[0]}`}
        subtitle="Keep material stock accurate and raise procurement the moment you're running low.">
        <Link to="/inventory" className="btn-secondary" data-testid="dash-goto-inventory">
          <Boxes className="w-4 h-4" /> Inventory
        </Link>
        <Link to="/procurement" className="btn-primary" data-testid="dash-raise-procurement">
          <Package className="w-4 h-4" /> Raise request
        </Link>
      </PageHeader>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <Kpi label="Material Items" value={s.inventory_count ?? 0} icon={Boxes} tone="ink" accent="#1A2F24" className="ag-rise" mono={false} />
        <Kpi label="Low Stock" value={low.length} icon={AlertTriangle} tone="clay" accent="#C06E52" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Open Requests" value={open} icon={Clock} tone="warn" accent="#D99530" className="ag-rise ag-rise-2" mono={false} />
        <Kpi label="Approved" value={(by.approved || 0) + (by.paid || 0)} icon={CheckCircle2} tone="ok" accent="#4A5D4E" className="ag-rise ag-rise-3" mono={false} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <SectionCard title="Low Stock · Reorder soon"
          action={<Link to="/inventory" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Manage <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {low.length === 0 ? (
            <EmptyState icon={Boxes} title="Stock looks healthy" hint="Nothing is running low right now." />
          ) : (
            <div className="p-5 space-y-4">
              {low.map((i) => {
                const pct = Math.min(100, Math.round(((Number(i.quantity) || 0) / maxQty) * 100));
                return (
                  <div key={i.item_id}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="text-sm font-semibold text-ink">{i.name}</div>
                      <div className="text-sm font-mono-num text-clay font-semibold">{i.quantity} {i.unit}</div>
                    </div>
                    <div className="h-1.5 bg-surfacealt rounded-sm overflow-hidden">
                      <div className="h-full rounded-sm bg-clay transition-transform duration-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>

        <SectionCard title="My Procurement Requests"
          action={<Link to="/procurement" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">All <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {proc.length === 0 ? (
            <EmptyState icon={Package} title="No requests yet"
              hint="Raise a procurement request when you need materials."
              action={<Link to="/procurement" className="btn-primary" data-testid="dash-empty-proc"><Package className="w-4 h-4" /> Raise a request</Link>} />
          ) : (
            <div className="divide-y divide-agborder">
              {proc.map((p) => (
                <Link to="/procurement" key={p.request_id} className="block px-5 py-3.5 hover:bg-surfacealt transition-colors duration-200">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-ink truncate">{p.subject}</div>
                    <StatusPill status={p.status} />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <StatusPill status={p.priority} dot={false} />
                    <span className="text-xs text-ink2">{(p.items || []).length} item(s)</span>
                    {p.admin_note && <span className="text-xs text-clay truncate">· {p.admin_note}</span>}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
