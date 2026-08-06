import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Clock } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";

const fmt = (n) => "\u20B9" + Math.round(n || 0).toLocaleString("en-IN");

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

  return (
    <div className="space-y-6" data-testid="sales-page">
      <div>
        <h1 className="text-3xl font-bold text-stone-900">Sales & Payments</h1>
        <p className="text-sm text-stone-500 mt-1">
          {can(user, "accounts") ? "Payments watchlist — mark each row as received or leave pending."
          : "Every sold plot and its full payment schedule."}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tile label="Overdue" value={buckets.overdue.length} tone="rose" />
        <Tile label="Upcoming" value={buckets.dueSoon.length} tone="amber" />
        <Tile label="Received" value={buckets.received.length} tone="emerald" />
      </div>

      <Section title="Pending payments">
        <PaymentTable rows={[...buckets.overdue, ...buckets.dueSoon]} unitOf={unitOf} onMark={setMarkFor} canMark={can(user, "accounts", "admin")} today={today} />
      </Section>

      <Section title="Received">
        <PaymentTable rows={buckets.received} unitOf={unitOf} onMark={setMarkFor} canMark={can(user, "accounts", "admin")} today={today} />
      </Section>

      {markFor && <MarkDialog payment={markFor} unit={unitOf(markFor.unit_id)} onClose={() => setMarkFor(null)} onSaved={() => { setMarkFor(null); load(); }} />}
    </div>
  );
}

function Tile({ label, value, tone }) {
  const cls = tone === "emerald" ? "bg-emerald-50 border-emerald-200 text-emerald-900"
    : tone === "amber" ? "bg-amber-50 border-amber-200 text-amber-900"
    : tone === "rose" ? "bg-rose-50 border-rose-200 text-rose-900"
    : "bg-white border-stone-200 text-stone-900";
  return <div className={`p-4 rounded-xl border ${cls}`}>
    <div className="text-[11px] uppercase tracking-widest text-stone-500">{label}</div>
    <div className="text-2xl font-bold mt-1">{value}</div>
  </div>;
}

function Section({ title, children }) {
  return (
    <div className="card">
      <div className="p-4 border-b border-stone-200 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}

function PaymentTable({ rows, unitOf, onMark, canMark, today }) {
  if (rows.length === 0) return <div className="p-8 text-center text-stone-500 text-sm">Nothing here</div>;
  return (
    <table className="w-full text-sm">
      <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
        <tr>
          <th className="text-left py-3 px-4">Plot</th>
          <th className="text-left py-3 px-4">Buyer</th>
          <th className="text-left py-3 px-4">#</th>
          <th className="text-left py-3 px-4">Due date</th>
          <th className="text-right py-3 px-4">Amount</th>
          <th className="text-left py-3 px-4">Status</th>
          <th className="text-right py-3 px-4">Action</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-stone-100">
        {rows.map(p => {
          const u = unitOf(p.unit_id) || {};
          const overdue = p.status === "pending" && p.due_date < today;
          return (
            <tr key={p.payment_id} data-testid={`payment-row-${p.payment_id}`}>
              <td className="py-3 px-4 font-medium">{u.plot_number || p.unit_id}</td>
              <td className="py-3 px-4 text-stone-600">{u.buyer_name || "—"}</td>
              <td className="py-3 px-4 text-stone-500">{p.seq}</td>
              <td className={`py-3 px-4 tabular-nums ${overdue ? "text-rose-700 font-semibold" : "text-stone-600"}`}>{p.due_date}</td>
              <td className="py-3 px-4 text-right tabular-nums">{fmt(p.amount)}</td>
              <td className="py-3 px-4">
                {p.status === "received"
                  ? <span className="pill bg-emerald-50 border-emerald-200 text-emerald-800"><CheckCircle2 className="w-3 h-3 inline mr-1" />Received</span>
                  : overdue
                    ? <span className="pill bg-rose-50 border-rose-200 text-rose-800">Overdue</span>
                    : <span className="pill bg-amber-50 border-amber-200 text-amber-800"><Clock className="w-3 h-3 inline mr-1" />Pending</span>}
              </td>
              <td className="py-3 px-4 text-right">
                {canMark && (
                  <button onClick={() => onMark(p)} className="btn-secondary text-xs" data-testid={`mark-${p.payment_id}`}>
                    Update
                  </button>
                )}
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
        status, received_date: status === "received" ? rDate : null,
        received_notes: notes,
      });
      toast.success(status === "received" ? "Marked received" : "Marked pending");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold">Update payment</div>
        <div className="text-sm text-stone-500 mb-4">
          Plot {unit?.plot_number} · Instalment {payment.seq} · {fmt(payment.amount)} · due {payment.due_date}
        </div>
        <div className="space-y-3">
          <div>
            <label className="label">Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="input" data-testid="mark-status">
              <option value="pending">Pending</option>
              <option value="received">Received</option>
            </select>
          </div>
          {status === "received" && (
            <div>
              <label className="label">Received on</label>
              <input type="date" value={rDate} onChange={(e) => setRDate(e.target.value)} className="input" data-testid="mark-date" />
            </div>
          )}
          <div>
            <label className="label">Notes / Reference</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} className="input" placeholder="e.g. UPI ref, bank txn ID" data-testid="mark-notes" />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={busy} className="btn-primary" data-testid="mark-submit">
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
