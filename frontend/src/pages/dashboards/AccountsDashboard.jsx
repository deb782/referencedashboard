import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Clock, ArrowUpRight, FileText } from "lucide-react";
import { PageHeader, Kpi, StatusPill, SectionCard, EmptyState, inr, inrCompact } from "@/components/ui";

export default function AccountsDashboard({ stats, user }) {
  const s = stats || {};
  const watchlist = s.watchlist || [];
  const awaiting = s.procurement_awaiting_po || [];
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        overline="The Ledger"
        title={`Collections & payables, ${user?.name?.split(" ")[0]}`}
        subtitle="Clear pending installments on their due date and record PO payments for approved procurement.">
        <Link to="/sales" className="btn-primary" data-testid="dash-goto-payments">
          <Clock className="w-4 h-4" /> Payment watchlist
        </Link>
      </PageHeader>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Kpi label="Pending Collections" value={inrCompact(s.payments_pending_amount)}
             sub={`${s.payments_pending ?? 0} installments`} icon={Clock} tone="warn" accent="#c8912f" className="ag-rise" />
        <Kpi label="Overdue" value={inrCompact(s.payments_overdue_amount)}
             sub={`${s.payments_overdue_count ?? 0} past due date`} icon={AlertTriangle} tone="bad" accent="#a33b28" className="ag-rise ag-rise-1" />
        <Kpi label="Received" value={inrCompact(s.payments_received_amount)}
             sub={`${s.payments_received_count ?? 0} payments cleared`} icon={CheckCircle2} tone="ok" accent="#5a6b10" className="ag-rise ag-rise-2" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
        <div className="lg:col-span-2">
          <SectionCard title="Payment Watchlist · Soonest due"
            action={<Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Open ledger <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
            {watchlist.length === 0 ? (
              <EmptyState icon={CheckCircle2} title="Nothing pending" hint="Every scheduled installment has been collected." />
            ) : (
              <table className="w-full">
                <thead><tr className="border-b border-agborder">
                  <th className="th">Plot</th><th className="th">Buyer</th><th className="th">#</th><th className="th">Due</th><th className="th text-right">Amount</th><th className="th">Status</th>
                </tr></thead>
                <tbody>
                  {watchlist.map((p) => {
                    const overdue = p.due_date < today;
                    return (
                      <tr key={p.payment_id} className="row">
                        <td className="td font-mono-num font-semibold">{p.plot_number || "—"}</td>
                        <td className="td text-ink2">{p.buyer_name || "—"}</td>
                        <td className="td font-mono-num text-ink2">{p.seq}</td>
                        <td className={`td font-mono-num ${overdue ? "text-bad font-semibold" : "text-ink2"}`}>{p.due_date}</td>
                        <td className="td text-right font-mono-num font-semibold">{inr(p.amount)}</td>
                        <td className="td"><StatusPill status={overdue ? "overdue" : "pending"} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </SectionCard>
        </div>

        <SectionCard title="Approved · Awaiting PO"
          action={<Link to="/procurement" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">All <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {awaiting.length === 0 ? (
            <EmptyState icon={FileText} title="No PO pending" hint="Approved procurement will land here for payment." />
          ) : (
            <div className="divide-y divide-agborder">
              {awaiting.map((p) => (
                <Link to="/procurement" key={p.request_id} className="block px-5 py-3.5 hover:bg-surfacealt transition-colors duration-200">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-ink truncate">{p.subject}</div>
                    <StatusPill status="approved" />
                  </div>
                  <div className="text-xs text-ink2 mt-1">{(p.items || []).length} item(s) · record PO & payment</div>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
