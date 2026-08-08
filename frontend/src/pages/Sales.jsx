import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Clock, AlertTriangle } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, Kpi, StatusPill, EmptyState, SectionCard, Modal, inr } from "@/components/ui";

export default function Sales() {
  const { user } = useAuth();
  const [units, setUnits] = useState([]);
  const [payments, setPayments] = useState([]);
  const [markFor, setMarkFor] = useState(null);

  const load = async () => {
    const [u, p] = await Promise.all([
      api.get("/units", { params: { status: "sold" } }),
      api.get("/payments"),
    ]);
    setUnits(u.data); setPayments(p.data);
  };
  useEffect(() => { load(); }, []);

  const unitOf = (uid) => units.find(u => u.unit_id === uid);
  const today = new Date().toISOString().slice(0, 10);

  const buckets = useMemo(() => ({
    overdue: payments.filter(p => p.status === "pending" && p.due_date < today),
    dueSoon: payments.filter(p => p.status === "pending" && p.due_date >= today),
    received: payments.filter(p => p.status === "received"),
  }), [payments, today]);

  const sum = (arr) => arr.reduce((s, p) => s + Number(p.amount || 0), 0);

  return (
    <div data-testid="sales-page">
      <PageHeader overline="The Ledger" title="Sales & Payments"
        subtitle={can(user, "accounts") ? "Mark each installment received on its due date, or leave it pending." : "Every sold plot and its full payment schedule."} />

      <div className="grid grid-cols-3 gap-6 mb-6">
        <Kpi label="Overdue" value={buckets.overdue.length} sub={inr(sum(buckets.overdue))} icon={AlertTriangle} tone="bad" accent="#a33b28" className="ag-rise" mono={false} />
        <Kpi label="Upcoming" value={buckets.dueSoon.length} sub={inr(sum(buckets.dueSoon))} icon={Clock} tone="warn" accent="#c8912f" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Received" value={buckets.received.length} sub={inr(sum(buckets.received))} icon={CheckCircle2} tone="ok" accent="#5a6b10" className="ag-rise ag-rise-2" mono={false} />
      </div>

      <div className="space-y-6">
        <SectionCard title="Pending payments" className="ag-rise">
          <PaymentTable rows={[...buckets.overdue, ...buckets.dueSoon]} unitOf={unitOf} onMark={setMarkFor} canMark={can(user, "accounts", "admin")} today={today} />
        </SectionCard>
        <SectionCard title="Received" className="ag-rise">
          <PaymentTable rows={buckets.received} unitOf={unitOf} onMark={setMarkFor} canMark={can(user, "accounts", "admin")} today={today} />
        </SectionCard>
      </div>

      {markFor && <MarkDialog payment={markFor} unit={unitOf(markFor.unit_id)} onClose={() => setMarkFor(null)} onSaved={() => { setMarkFor(null); load(); }} />}
    </div>
  );
}

function PaymentTable({ rows, unitOf, onMark, canMark, today }) {
  if (rows.length === 0) return <EmptyState icon={CheckCircle2} title="Nothing here" hint="No payments in this bucket." />;
  return (
    <table className="w-full">
      <thead><tr className="border-b border-agborder bg-surfacealt/50">
        <th className="th">Plot</th><th className="th">Buyer</th><th className="th">Instalment</th><th className="th">Due date</th><th className="th text-right">Amount</th><th className="th">Status</th><th className="th text-right">Action</th>
      </tr></thead>
      <tbody>
        {rows.map(p => {
          const u = unitOf(p.unit_id) || {};
          const overdue = p.status === "pending" && p.due_date < today;
          return (
            <tr key={p.payment_id} className="row" data-testid={`payment-row-${p.payment_id}`}>
              <td className="td font-mono-num font-bold">{u.plot_number || p.unit_id}</td>
              <td className="td text-ink2">{u.buyer_name || "—"}</td>
              <td className="td text-ink2">{p.notes || `#${p.seq}`}</td>
              <td className={`td font-mono-num ${overdue ? "text-bad font-semibold" : "text-ink2"}`}>{p.due_date}</td>
              <td className="td text-right font-mono-num font-semibold">{inr(p.amount)}</td>
              <td className="td"><StatusPill status={p.status === "received" ? "received" : overdue ? "overdue" : "pending"} /></td>
              <td className="td text-right">
                {canMark && <button onClick={() => onMark(p)} className="btn-secondary text-xs py-1.5" data-testid={`mark-${p.payment_id}`}>Update</button>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function MarkDialog({ payment, unit, onClose, onSaved }) {
  const [status, setStatus] = useState(payment.status || "pending");
  const [rDate, setRDate] = useState(payment.received_date || new Date().toISOString().slice(0,10));
  const [notes, setNotes] = useState(payment.received_notes || "");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.patch(`/payments/${payment.payment_id}`, {
        status, received_date: status === "received" ? rDate : null, received_notes: notes,
      });
      toast.success(status === "received" ? "Marked received" : "Marked pending");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal title="Update payment"
      subtitle={`Plot ${unit?.plot_number} · Instalment ${payment.seq} · ${inr(payment.amount)} · due ${payment.due_date}`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="mark-submit">{busy ? "Saving…" : "Save"}</button>
      </>}>
      <div className="space-y-4">
        <div><label className="label">Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="input" data-testid="mark-status">
            <option value="pending">Pending</option>
            <option value="received">Received</option>
          </select></div>
        {status === "received" && (
          <div><label className="label">Received on</label>
            <input type="date" value={rDate} onChange={(e) => setRDate(e.target.value)} className="input font-mono-num" data-testid="mark-date" /></div>
        )}
        <div><label className="label">Notes / Reference</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} className="input" placeholder="e.g. UPI ref, bank txn ID" data-testid="mark-notes" /></div>
      </div>
    </Modal>
  );
}
