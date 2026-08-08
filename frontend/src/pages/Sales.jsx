import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Home, Building2, Wallet, ChevronRight, Receipt } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, StatusPill, EmptyState, SectionCard, Modal, inr } from "@/components/ui";

export default function Sales() {
  const { user } = useAuth();
  const [head, setHead] = useState("plots");
  const [ov, setOv] = useState(null);
  const [drill, setDrill] = useState(null);   // {unit_id, plot_number, buyer_name}
  const canPay = can(user, "accounts", "admin");

  const load = async () => {
    try { const r = await api.get("/accounts/overview"); setOv(r.data); }
    catch (e) { toast.error(apiError(e)); }
  };
  useEffect(() => { load(); }, []);

  const plots = ov?.plots || { projects: [], totals: {} };
  const site = ov?.site || { rows: [], pending_total: 0, paid_total: 0 };

  return (
    <div data-testid="sales-page">
      <PageHeader overline="The Ledger" title="Sales & Payments"
        subtitle="Dues are grouped into two heads — Plots (buyer instalments) and Site (procurement bills)." />

      {/* Head toggle */}
      <div className="flex gap-2 mb-6">
        <HeadTab active={head === "plots"} onClick={() => setHead("plots")} icon={Home}
          label="Plots" pending={plots.totals?.pending} testid="head-plots" />
        <HeadTab active={head === "site"} onClick={() => setHead("site")} icon={Building2}
          label="Site" pending={site.pending_total} testid="head-site" />
      </div>

      {head === "plots" ? (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-6">
            <Summary label="Plots — Billed" value={inr(plots.totals?.total)} tone="text-ink" />
            <Summary label="Received" value={inr(plots.totals?.paid)} tone="text-ok" />
            <Summary label="Pending" value={inr(plots.totals?.pending)} tone="text-warn" />
          </div>
          {(plots.projects || []).map((p) => (
            <SectionCard key={p.project_id} title={`${p.name} · ${p.plot_count} plot(s)`} className="ag-rise"
              action={<span className="text-xs font-mono-num text-ink2">Pending <b className="text-warn">{inr(p.pending)}</b></span>}>
              <table className="w-full">
                <thead><tr className="border-b border-agborder bg-surfacealt/40">
                  <th className="th">Plot</th><th className="th">Buyer</th><th className="th">Instalments</th>
                  <th className="th">Next due</th><th className="th text-right">Billed</th>
                  <th className="th text-right">Received</th><th className="th text-right">Pending</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {p.plots.map((r) => (
                    <tr key={r.unit_id} className="row cursor-pointer" onClick={() => setDrill(r)} data-testid={`plot-pay-row-${r.plot_number}`}>
                      <td className="td font-mono-num font-bold">{r.plot_number}</td>
                      <td className="td text-ink2">{r.buyer_name || "—"}</td>
                      <td className="td font-mono-num text-ink2">{r.installments}</td>
                      <td className="td font-mono-num text-ink2">{r.next_due || "—"}</td>
                      <td className="td text-right font-mono-num">{inr(r.total)}</td>
                      <td className="td text-right font-mono-num text-ok">{inr(r.paid)}</td>
                      <td className="td text-right font-mono-num font-semibold text-warn">{inr(r.pending)}</td>
                      <td className="td text-right"><ChevronRight className="w-4 h-4 text-ink2 inline" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SectionCard>
          ))}
          {(plots.projects || []).length === 0 && <EmptyState icon={Home} title="No plot dues yet" hint="Payments appear here once plots are sold." />}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <Summary label="Site — Pending" value={inr(site.pending_total)} tone="text-warn" />
            <Summary label="Site — Paid" value={inr(site.paid_total)} tone="text-ok" />
          </div>
          <SectionCard title="Procurement bills" className="ag-rise">
            {site.rows.length === 0 ? <EmptyState icon={Building2} title="No site bills" hint="Approved procurement bills appear here." /> : (
              <table className="w-full">
                <thead><tr className="border-b border-agborder bg-surfacealt/40">
                  <th className="th">Subject</th><th className="th">Project</th><th className="th">PO</th>
                  <th className="th text-right">Estimated</th><th className="th text-right">Paid</th>
                  <th className="th text-right">Pending</th><th className="th">Status</th>
                </tr></thead>
                <tbody>
                  {site.rows.map((r) => (
                    <tr key={r.request_id} className="row" data-testid={`site-row-${r.request_id}`}>
                      <td className="td font-semibold">{r.subject}</td>
                      <td className="td text-ink2">{r.project_name}</td>
                      <td className="td font-mono-num text-ink2">{r.po_number || "—"}</td>
                      <td className="td text-right font-mono-num">{inr(r.est_total)}</td>
                      <td className="td text-right font-mono-num text-ok">{inr(r.paid)}</td>
                      <td className="td text-right font-mono-num font-semibold text-warn">{inr(r.pending)}</td>
                      <td className="td"><StatusPill status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="px-5 py-3 text-xs text-ink2 border-t border-agborder">Record PO payments from the Procurement page. Milestone payment structure comes in the next phase.</div>
          </SectionCard>
        </div>
      )}

      {drill && <PlotDrilldown plot={drill} canPay={canPay} onClose={() => setDrill(null)} onChanged={load} />}
    </div>
  );
}

function HeadTab({ active, onClick, icon: Icon, label, pending, testid }) {
  return (
    <button onClick={onClick} data-testid={testid}
      className={`flex items-center gap-3 px-5 py-3 rounded-lg border transition-colors duration-300 ${active ? "bg-brand text-white border-brand" : "bg-white border-agborder text-ink2 hover:bg-surfacealt"}`}>
      <Icon className="w-5 h-5" />
      <div className="text-left">
        <div className="font-display font-bold leading-none">{label}</div>
        <div className={`text-xs mt-1 font-mono-num ${active ? "text-white/80" : "text-warn"}`}>Pending {inr(pending)}</div>
      </div>
    </button>
  );
}

function Summary({ label, value, tone }) {
  return (
    <div className="card p-5 ag-rise">
      <div className="overline">{label}</div>
      <div className={`font-display font-extrabold text-2xl mt-2 font-mono-num ${tone}`}>{value}</div>
    </div>
  );
}

function PlotDrilldown({ plot, canPay, onClose, onChanged }) {
  const [rows, setRows] = useState([]);
  const [receiptFor, setReceiptFor] = useState(null);

  const load = async () => {
    const r = await api.get("/payments", { params: { unit_id: plot.unit_id } });
    r.data.sort((a, b) => a.seq - b.seq);
    setRows(r.data);
  };
  useEffect(() => { load(); }, [plot.unit_id]);

  const billed = rows.reduce((s, r) => s + Number(r.amount || 0), 0);
  const paid = rows.reduce((s, r) => s + Number(r.paid_amount || 0), 0);

  return (
    <Modal size="xl" title={`Plot ${plot.plot_number} · ${plot.buyer_name || ""}`}
      subtitle={`Billed ${inr(billed)} · Received ${inr(paid)} · Pending ${inr(billed - paid)}`}
      onClose={onClose}
      footer={<button onClick={onClose} className="btn-secondary">Close</button>}>
      <table className="w-full">
        <thead><tr className="border-b border-agborder">
          <th className="th">Instalment</th><th className="th">Due</th><th className="th text-right">Amount</th>
          <th className="th text-right">Paid</th><th className="th text-right">Balance</th><th className="th">Status</th>
          {canPay && <th className="th"></th>}
        </tr></thead>
        <tbody>
          {rows.map((r) => {
            const bal = round2(Number(r.amount) - Number(r.paid_amount || 0));
            return (
              <tr key={r.payment_id} className="row" data-testid={`inst-row-${r.payment_id}`}>
                <td className="td font-semibold">{r.notes || `#${r.seq}`}</td>
                <td className="td font-mono-num text-ink2">{r.due_date}</td>
                <td className="td text-right font-mono-num">{inr(r.amount)}</td>
                <td className="td text-right font-mono-num text-ok">{inr(r.paid_amount)}</td>
                <td className="td text-right font-mono-num font-semibold">{inr(bal)}</td>
                <td className="td"><StatusPill status={r.status} /></td>
                {canPay && (
                  <td className="td text-right">
                    {r.status !== "received" && (
                      <button onClick={() => setReceiptFor(r)} className="btn-primary text-xs py-1.5" data-testid={`receipt-btn-${r.payment_id}`}>
                        <Receipt className="w-3.5 h-3.5" /> Record
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {receiptFor && (
        <ReceiptDialog payment={receiptFor} onClose={() => setReceiptFor(null)}
          onSaved={() => { setReceiptFor(null); load(); onChanged(); }} />
      )}
    </Modal>
  );
}

function ReceiptDialog({ payment, onClose, onSaved }) {
  const remaining = round2(Number(payment.amount) - Number(payment.paid_amount || 0));
  const [amount, setAmount] = useState(remaining);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!amount || Number(amount) <= 0) return toast.error("Enter a payment amount");
    setBusy(true);
    try {
      await api.post(`/payments/${payment.payment_id}/receipt`, { amount: Number(amount), date, notes });
      toast.success("Payment recorded");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="md" title={`Record payment · ${payment.notes || `#${payment.seq}`}`}
      subtitle={`Instalment ${inr(payment.amount)} · already paid ${inr(payment.paid_amount)} · balance ${inr(remaining)}`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="receipt-submit">{busy ? "Saving…" : "Record payment"}</button>
      </>}>
      <div className="space-y-4">
        <div>
          <label className="label">Amount received (partial allowed)</label>
          <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="input font-mono-num" data-testid="receipt-amount" />
          <div className="flex gap-2 mt-2">
            <button onClick={() => setAmount(remaining)} className="text-xs font-semibold text-brand hover:text-brand-hover">Full balance</button>
            <button onClick={() => setAmount(round2(remaining / 2))} className="text-xs font-semibold text-ink2 hover:text-ink">50%</button>
          </div>
        </div>
        <div><label className="label">Received on</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input font-mono-num" data-testid="receipt-date" /></div>
        <div><label className="label">Reference / notes</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} className="input" placeholder="UPI ref, bank txn…" data-testid="receipt-notes" /></div>
        {(payment.receipts || []).length > 0 && (
          <div className="border-t border-agborder pt-3">
            <div className="overline mb-2">Previous receipts</div>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {payment.receipts.map((rc, i) => (
                <div key={i} className="flex justify-between text-xs text-ink2">
                  <span>{rc.date} · {rc.notes || "—"}</span>
                  <span className="font-mono-num text-ink">{inr(rc.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
