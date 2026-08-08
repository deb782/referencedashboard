import { Link } from "react-router-dom";
import { Home, TrendingUp, ArrowUpRight } from "lucide-react";
import { PageHeader, SectionCard, EmptyState, inr } from "@/components/ui";

export default function PostSalesDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const recent = s.recent_sales || [];

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline="Post-Sales Desk" title={`Let's close some plots, ${user?.name?.split(" ")[0]}`}
        subtitle="Availability and bookings for each project. Pick a plot to book from Units.">
        <Link to="/units" className="btn-primary" data-testid="dash-mark-sold"><Home className="w-4 h-4" /> Go to Units</Link>
      </PageHeader>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {projects.map((p, i) => (
          <div key={p.project_id} className={`card p-6 ag-rise ag-rise-${i + 1}`} data-testid={`dash-project-${p.project_id}`}>
            <div className="font-display text-xl font-bold text-ink">{p.name}</div>
            <div className="text-xs text-ink2 mt-0.5">{p.kind || "Project"}</div>
            <div className="grid grid-cols-3 gap-4 mt-5">
              <Stat label="Available" value={p.available} tone="text-ok" />
              <Stat label="Sold" value={p.sold} tone="text-brand" />
              <Stat label="Booked value" value={inr(p.booked_value)} tone="text-ink" small />
            </div>
            <Link to="/units" className="btn-secondary w-full mt-5"><Home className="w-4 h-4" /> Book a plot here</Link>
          </div>
        ))}
        {projects.length === 0 && <div className="xl:col-span-2"><EmptyState icon={Home} title="No projects" /></div>}
      </div>

      <div className="mt-6">
        <SectionCard title="Recent Sales"
          action={<Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Sales & Payments <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {recent.length === 0 ? <EmptyState icon={TrendingUp} title="No sales yet" hint="Booked plots will appear here." /> : (
            <table className="w-full">
              <thead><tr className="border-b border-agborder"><th className="th">Plot</th><th className="th">Buyer</th><th className="th">Date</th><th className="th text-right">Final price</th></tr></thead>
              <tbody>
                {recent.map(u => (
                  <tr key={u.unit_id} className="row">
                    <td className="td font-mono-num font-semibold">{u.plot_number}</td>
                    <td className="td">{u.buyer_name || "—"}</td>
                    <td className="td font-mono-num text-ink2">{u.sale_date || "—"}</td>
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

function Stat({ label, value, tone, small }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-ink2 font-bold">{label}</div>
      <div className={`font-display font-extrabold ${small ? "text-lg" : "text-3xl"} mt-1 ${tone} ${small ? "font-mono-num" : ""}`}>{value}</div>
    </div>
  );
}
