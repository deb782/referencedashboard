import { Link } from "react-router-dom";
import { Home, CheckCircle2, TrendingUp, ArrowUpRight, HandCoins } from "lucide-react";
import { PageHeader, Kpi, SectionCard, EmptyState, inr, inrCompact } from "@/components/ui";

export default function PostSalesDashboard({ stats, user }) {
  const s = stats || {};
  const recent = s.recent_sales || [];

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        overline="Post-Sales Desk"
        title={`Let's close some plots, ${user?.name?.split(" ")[0]}`}
        subtitle="Pick an available plot, capture buyer details, and lock in the payment schedule.">
        <Link to="/units" className="btn-primary" data-testid="dash-mark-sold">
          <Home className="w-4 h-4" /> Mark a plot sold
        </Link>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Kpi label="Plots Available" value={s.units_available ?? 0}
             sub="ready to book" icon={Home} tone="ok" accent="#5a6b10" className="ag-rise" mono={false} />
        <Kpi label="Plots Sold" value={s.units_sold ?? 0}
             sub="across all projects" icon={CheckCircle2} tone="brand" accent="#5a6b10" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Sales Value Booked" value={inrCompact(s.sales_booked)}
             sub={inr(s.sales_booked)} icon={TrendingUp} tone="ink" accent="#a8763f" className="ag-rise ag-rise-2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2">
          <SectionCard title="Recent Sales"
            action={<Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Sales & Payments <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
            {recent.length === 0 ? (
              <EmptyState icon={Home} title="No sales recorded yet"
                hint="Head to Units and click Mark Sold on any available plot to get started."
                action={<Link to="/units" className="btn-primary" data-testid="dash-empty-cta"><Home className="w-4 h-4" /> Go to Units</Link>} />
            ) : (
              <table className="w-full">
                <thead><tr className="border-b border-agborder">
                  <th className="th">Plot</th><th className="th">Buyer</th><th className="th">Sale date</th><th className="th text-right">Final price</th>
                </tr></thead>
                <tbody>
                  {recent.map((u) => (
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

        <SectionCard title="Your Contribution">
          <div className="p-6 space-y-6">
            <div>
              <div className="overline">Plots you sold</div>
              <div className="font-display font-extrabold text-brand text-4xl mt-2 font-mono-num">{s.my_sales_count ?? 0}</div>
            </div>
            <div className="pt-6 border-t border-agborder">
              <div className="overline">Value you booked</div>
              <div className="font-display font-extrabold text-ink text-3xl mt-2 font-mono-num">{inrCompact(s.my_sales_value)}</div>
              <div className="text-xs text-ink2 mt-1 font-mono-num">{inr(s.my_sales_value)}</div>
            </div>
            <Link to="/units" className="btn-secondary w-full" data-testid="dash-side-cta">
              <HandCoins className="w-4 h-4" /> Book another plot
            </Link>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
