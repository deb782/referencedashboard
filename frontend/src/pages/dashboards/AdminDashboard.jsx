import { Link } from "react-router-dom";
import { Building2, Home, HandCoins, Package, Users, TrendingUp, ArrowUpRight, CheckCircle2 } from "lucide-react";
import { PageHeader, Kpi, StatusPill, SectionCard, EmptyState, inr, inrCompact } from "@/components/ui";

export default function AdminDashboard({ stats, user }) {
  const s = stats || {};
  const approvals = s.procurement_approvals || [];
  const recent = s.recent_sales || [];

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        overline="Command Center"
        title={`Good to see you, ${user?.name?.split(" ")[0]}`}
        subtitle="Full oversight across projects, sales, collections and procurement. Clear the bottlenecks first.">
        <Link to="/projects" className="btn-secondary" data-testid="dash-new-project">
          <Building2 className="w-4 h-4" /> Projects
        </Link>
        <Link to="/units" className="btn-primary" data-testid="dash-upload-units">
          <Home className="w-4 h-4" /> Units
        </Link>
      </PageHeader>

      {/* Hero KPI grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-6 card p-8 relative overflow-hidden ag-rise flex flex-col justify-between">
          <div className="absolute -right-8 -top-8 opacity-[0.04]"><TrendingUp className="w-48 h-48" /></div>
          <div>
            <div className="overline">Total Sales Booked</div>
            <div className="font-display font-extrabold tracking-tighter text-brand text-5xl md:text-6xl mt-4 font-mono-num">
              {inrCompact(s.sales_booked)}
            </div>
            <div className="text-sm text-ink2 mt-3 font-mono-num">{inr(s.sales_booked)}</div>
          </div>
          <div className="flex gap-6 mt-8 pt-6 border-t border-agborder">
            <MiniStat label="Units sold" value={s.units_sold ?? 0} />
            <MiniStat label="Available" value={s.units_available ?? 0} />
            <MiniStat label="Collected" value={inrCompact(s.payments_received_amount)} mono />
          </div>
        </div>

        <div className="lg:col-span-3 ag-rise ag-rise-1">
          <Kpi label="Payments Pending" value={inrCompact(s.payments_pending_amount)}
               sub={`${s.payments_pending ?? 0} installments outstanding`} icon={HandCoins} tone="warn" accent="#c8912f" className="h-full" mono />
        </div>
        <div className="lg:col-span-3 ag-rise ag-rise-2">
          <Kpi label="Procurement Queue" value={s.procurement_pending ?? 0}
               sub="requests awaiting your decision" icon={Package} tone="clay" accent="#a8763f" className="h-full" mono={false} />
        </div>
      </div>

      {/* Secondary counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-6">
        <Kpi label="Projects" value={s.projects ?? 0} icon={Building2} tone="ink" className="ag-rise" mono={false} />
        <Kpi label="Team Members" value={s.team_members ?? 0} icon={Users} tone="ink" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Units Sold" value={s.units_sold ?? 0} icon={Home} tone="ok" className="ag-rise ag-rise-2" mono={false} />
        <Kpi label="Procurement Paid" value={s.procurement_paid ?? 0} icon={CheckCircle2} tone="ok" className="ag-rise ag-rise-3" mono={false} />
      </div>

      {/* Bento tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <SectionCard title="Procurement · Needs Action"
          action={<Link to="/procurement" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="dash-view-procurement">Review all <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {approvals.length === 0 ? (
            <EmptyState icon={Package} title="Queue is clear" hint="No procurement requests are waiting on you." />
          ) : (
            <div className="divide-y divide-agborder">
              {approvals.map((p) => (
                <Link to="/procurement" key={p.request_id} className="flex items-center justify-between px-5 py-3.5 hover:bg-surfacealt transition-colors duration-200">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-ink truncate">{p.subject}</div>
                    <div className="text-xs text-ink2 mt-0.5">{(p.items || []).length} item(s)</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <StatusPill status={p.priority} />
                    <StatusPill status={p.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="Recent Sales"
          action={<Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Sales & Payments <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {recent.length === 0 ? (
            <EmptyState icon={Home} title="No sales yet" hint="Sold plots will appear here as your team books them." />
          ) : (
            <table className="w-full">
              <thead><tr className="border-b border-agborder">
                <th className="th">Plot</th><th className="th">Buyer</th><th className="th text-right">Value</th>
              </tr></thead>
              <tbody>
                {recent.map((u) => (
                  <tr key={u.unit_id} className="row">
                    <td className="td font-mono-num font-semibold">{u.plot_number}</td>
                    <td className="td text-ink2">{u.buyer_name || "—"}</td>
                    <td className="td text-right font-mono-num">{inr(u.final_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function MiniStat({ label, value, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink2 font-bold">{label}</div>
      <div className={`font-display font-bold text-ink text-xl mt-1 ${mono ? "font-mono-num" : ""}`}>{value}</div>
    </div>
  );
}
