import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, XCircle, HelpCircle, Banknote } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";

const fmt = (n) => "\u20B9" + Math.round(n || 0).toLocaleString("en-IN");

const STATUS_STYLE = {
  pending_admin: "bg-amber-50 border-amber-200 text-amber-800",
  pending_clarification: "bg-orange-50 border-orange-200 text-orange-800",
  approved: "bg-emerald-50 border-emerald-200 text-emerald-800",
  rejected: "bg-rose-50 border-rose-200 text-rose-800",
  paid: "bg-sky-50 border-sky-200 text-sky-800",
};
const STATUS_LABEL = {
  pending_admin: "Awaiting admin",
  pending_clarification: "Needs details",
  approved: "Approved — awaiting PO",
  rejected: "Rejected",
  paid: "Paid",
};

export default function Procurement() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [actionFor, setActionFor] = useState(null);
  const [paymentFor, setPaymentFor] = useState(null);

  const load = async () => {
    const [r, p] = await Promise.all([api.get("/procurement"), api.get("/projects")]);
    setRows(r.data); setProjects(p.data);
  };
  useEffect(() => { load(); }, []);

  const projName = (id) => projects.find(p => p.project_id === id)?.name || "—";

  const totalOf = (r) => (r.items || []).reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0);

  const buckets = useMemo(() => ({
    active: rows.filter(r => ["pending_admin","pending_clarification","approved"].includes(r.status)),
    done: rows.filter(r => ["paid","rejected"].includes(r.status)),
  }), [rows]);

  return (
    <div className="space-y-6" data-testid="procurement-page">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Procurement</h1>
          <p className="text-sm text-stone-500 mt-1">
            {user?.role === "site_manager" && "Raise a request → admin approves → accounts records PO + payment."}
            {user?.role === "admin" && "Review and approve site managers' procurement requests."}
            {user?.role === "accounts" && "Approved requests come here to record PO number, paid amount and date."}
          </p>
        </div>
        {can(user, "site_manager", "admin") && (
          <button onClick={() => setShowNew(true)} className="btn-primary" data-testid="new-proc-btn">
            <Plus className="w-4 h-4 inline mr-1" /> New request
          </button>
        )}
      </div>

      <div className="card">
        <div className="p-4 border-b border-stone-200 text-sm font-semibold">Active queue</div>
        <ProcList rows={buckets.active} projName={projName} totalOf={totalOf} user={user}
                   onAction={setActionFor} onPayment={setPaymentFor} />
      </div>

      {buckets.done.length > 0 && (
        <div className="card">
          <div className="p-4 border-b border-stone-200 text-sm font-semibold">History</div>
          <ProcList rows={buckets.done} projName={projName} totalOf={totalOf} user={user}
                     onAction={setActionFor} onPayment={setPaymentFor} />
        </div>
      )}

      {showNew && <NewProcurement projects={projects} defaultProject={user?.project_id} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />}
      {actionFor && <ActionDialog req={actionFor} onClose={() => setActionFor(null)} onSaved={() => { setActionFor(null); load(); }} />}
      {paymentFor && <PaymentDialog req={paymentFor} onClose={() => setPaymentFor(null)} onSaved={() => { setPaymentFor(null); load(); }} />}
    </div>
  );
}

function ProcList({ rows, projName, totalOf, user, onAction, onPayment }) {
  if (rows.length === 0) return <div className="p-8 text-center text-stone-500 text-sm">Nothing here</div>;
  return (
    <table className="w-full text-sm">
      <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
        <tr>
          <th className="text-left py-3 px-4">Subject</th>
          <th className="text-left py-3 px-4">Project</th>
          <th className="text-left py-3 px-4">Priority</th>
          <th className="text-left py-3 px-4">Items</th>
          <th className="text-right py-3 px-4">Est. total</th>
          <th className="text-left py-3 px-4">Status</th>
          <th className="text-right py-3 px-4">Action</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-stone-100">
        {rows.map(r => (
          <tr key={r.request_id} data-testid={`proc-row-${r.request_id}`}>
            <td className="py-3 px-4">
              <div className="font-medium">{r.subject}</div>
              {r.notes && <div className="text-[11px] text-stone-500 mt-0.5">{r.notes}</div>}
              {r.admin_note && (
                <div className="text-[11px] text-orange-700 mt-0.5">Admin: {r.admin_note}</div>
              )}
            </td>
            <td className="py-3 px-4 text-stone-600">{projName(r.project_id)}</td>
            <td className="py-3 px-4">
              <span className="pill bg-stone-50 border-stone-200 text-stone-700">{r.priority}</span>
            </td>
            <td className="py-3 px-4 text-xs text-stone-500">
              {(r.items || []).slice(0,3).map(i => `${i.name} ×${i.quantity}`).join(" · ")}
              {(r.items?.length || 0) > 3 && ` +${r.items.length - 3} more`}
            </td>
            <td className="py-3 px-4 text-right tabular-nums">{fmt(totalOf(r))}</td>
            <td className="py-3 px-4">
              <span className={`pill ${STATUS_STYLE[r.status] || ""}`}>{STATUS_LABEL[r.status] || r.status}</span>
              {r.po_number && (
                <div className="text-[11px] text-stone-500 mt-1">PO: {r.po_number}</div>
              )}
            </td>
            <td className="py-3 px-4 text-right">
              {user?.role === "admin" && ["pending_admin","pending_clarification"].includes(r.status) && (
                <button onClick={() => onAction(r)} className="btn-secondary text-xs" data-testid={`review-${r.request_id}`}>Review</button>
              )}
              {(user?.role === "accounts" || user?.role === "admin") && r.status === "approved" && (
                <button onClick={() => onPayment(r)} className="btn-primary text-xs" data-testid={`pay-${r.request_id}`}>
                  <Banknote className="w-3 h-3 inline mr-1" /> Record PO/Payment
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NewProcurement({ projects, defaultProject, onClose, onSaved }) {
  const [form, setForm] = useState({
    project_id: defaultProject || projects[0]?.project_id || "",
    subject: "", priority: "medium", notes: "",
  });
  const [items, setItems] = useState([{ name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const [busy, setBusy] = useState(false);

  const addRow = () => setItems([...items, { name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const rmRow = (i) => setItems(items.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setItems(items.map((it, idx) => idx === i ? { ...it, ...patch } : it));

  const save = async () => {
    if (!form.project_id) return toast.error("Pick a project");
    if (!form.subject.trim()) return toast.error("Subject is required");
    const valid = items.filter(i => i.name.trim() && Number(i.quantity) > 0);
    if (valid.length === 0) return toast.error("Add at least one item");
    setBusy(true);
    try {
      await api.post("/procurement", {
        ...form,
        items: valid.map(i => ({ ...i, quantity: Number(i.quantity), est_cost: Number(i.est_cost || 0) })),
      });
      toast.success("Request submitted — admin has been notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6" onClick={onClose}>
      <div className="card w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold mb-4">New procurement request</div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Project *</label>
            <select value={form.project_id} onChange={(e) => setForm({...form, project_id: e.target.value})} className="input" data-testid="proc-proj">
              {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
            </select></div>
          <div><label className="label">Priority</label>
            <select value={form.priority} onChange={(e) => setForm({...form, priority: e.target.value})} className="input">
              <option value="low">Low</option><option value="medium">Medium</option>
              <option value="high">High</option><option value="urgent">Urgent</option>
            </select></div>
        </div>
        <div className="mt-3">
          <label className="label">Subject *</label>
          <input value={form.subject} onChange={(e) => setForm({...form, subject: e.target.value})} className="input" placeholder="e.g. Cement + steel for phase 2" data-testid="proc-subject" />
        </div>
        <div className="mt-3">
          <label className="label">Notes</label>
          <textarea rows={2} value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" />
        </div>

        <div className="mt-4">
          <div className="flex justify-between items-center mb-2">
            <div className="text-sm font-semibold">Items</div>
            <button onClick={addRow} className="text-xs text-emerald-800" data-testid="proc-add-item">
              <Plus className="w-3 h-3 inline" /> Add row
            </button>
          </div>
          <div className="border border-stone-200 rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
                <tr>
                  <th className="text-left py-2 px-2">Name</th>
                  <th className="text-right py-2 px-2">Qty</th>
                  <th className="text-left py-2 px-2">Unit</th>
                  <th className="text-right py-2 px-2">Est. cost / unit</th>
                  <th className="text-left py-2 px-2">Notes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it, i) => (
                  <tr key={i} className="border-t border-stone-100">
                    <td className="py-2 px-2"><input value={it.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" data-testid={`proc-name-${i}`} /></td>
                    <td className="py-2 px-2"><input type="number" value={it.quantity} onChange={(e) => updRow(i, { quantity: e.target.value })} className="input text-right w-20" data-testid={`proc-qty-${i}`} /></td>
                    <td className="py-2 px-2"><input value={it.unit} onChange={(e) => updRow(i, { unit: e.target.value })} className="input w-20" /></td>
                    <td className="py-2 px-2"><input type="number" value={it.est_cost} onChange={(e) => updRow(i, { est_cost: e.target.value })} className="input text-right w-24" /></td>
                    <td className="py-2 px-2"><input value={it.notes} onChange={(e) => updRow(i, { notes: e.target.value })} className="input" /></td>
                    <td className="py-2 px-2">{items.length > 1 && <button onClick={() => rmRow(i)} className="text-rose-600"><Trash2 className="w-3.5 h-3.5" /></button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={busy} className="btn-primary" data-testid="proc-submit">
            {busy ? "Submitting…" : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ActionDialog({ req, onClose, onSaved }) {
  const [action, setAction] = useState("approve");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (action !== "approve" && !note.trim()) return toast.error("Please add a note");
    setBusy(true);
    try {
      await api.post(`/procurement/${req.request_id}/action`, { action, note });
      toast.success(action === "approve" ? "Approved" : action === "reject" ? "Rejected" : "Marked pending clarification");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold mb-1">Review procurement</div>
        <div className="text-sm text-stone-500 mb-4">{req.subject}</div>
        <div className="space-y-3">
          <div className="text-xs text-stone-500">
            {(req.items || []).map((i, idx) => (
              <div key={idx}>• {i.name} — {i.quantity} {i.unit} @ {fmt(i.est_cost)}{i.notes ? ` (${i.notes})` : ""}</div>
            ))}
          </div>
          <div>
            <label className="label">Decision</label>
            <div className="grid grid-cols-3 gap-2">
              <button onClick={() => setAction("approve")} className={`btn ${action === "approve" ? "bg-emerald-900 text-white" : "border border-stone-300 text-stone-700"}`} data-testid="act-approve">
                <CheckCircle2 className="w-3 h-3 inline mr-1" /> Approve
              </button>
              <button onClick={() => setAction("reject")} className={`btn ${action === "reject" ? "bg-rose-600 text-white" : "border border-stone-300 text-stone-700"}`} data-testid="act-reject">
                <XCircle className="w-3 h-3 inline mr-1" /> Reject
              </button>
              <button onClick={() => setAction("clarify")} className={`btn ${action === "clarify" ? "bg-orange-600 text-white" : "border border-stone-300 text-stone-700"}`} data-testid="act-clarify">
                <HelpCircle className="w-3 h-3 inline mr-1" /> Need details
              </button>
            </div>
          </div>
          <div>
            <label className="label">Note {action !== "approve" && <span className="text-rose-600">*</span>}</label>
            <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} className="input"
              placeholder={action === "clarify" ? "What extra info do you need?" : "Optional"} data-testid="act-note" />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={busy} className="btn-primary" data-testid="act-submit">
            {busy ? "Saving…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PaymentDialog({ req, onClose, onSaved }) {
  const total = (req.items || []).reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0);
  const [form, setForm] = useState({
    po_number: "", paid_amount: total, paid_date: new Date().toISOString().slice(0,10), notes: "",
  });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!form.po_number.trim()) return toast.error("PO number is required");
    if (!form.paid_amount || form.paid_amount <= 0) return toast.error("Paid amount must be > 0");
    setBusy(true);
    try {
      await api.post(`/procurement/${req.request_id}/payment`, {
        ...form, paid_amount: Number(form.paid_amount),
      });
      toast.success("Payment recorded");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold">Record PO & Payment</div>
        <div className="text-sm text-stone-500 mb-4">{req.subject}</div>
        <div className="space-y-3">
          <div><label className="label">PO number *</label>
            <input value={form.po_number} onChange={(e) => setForm({...form, po_number: e.target.value})} className="input" data-testid="pay-po" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Paid amount *</label>
              <input type="number" value={form.paid_amount} onChange={(e) => setForm({...form, paid_amount: e.target.value})} className="input" data-testid="pay-amt" /></div>
            <div><label className="label">Paid date</label>
              <input type="date" value={form.paid_date} onChange={(e) => setForm({...form, paid_date: e.target.value})} className="input" /></div>
          </div>
          <div><label className="label">Notes / Reference</label>
            <input value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" placeholder="Vendor, txn ref, etc." /></div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={busy} className="btn-primary" data-testid="pay-submit">
            {busy ? "Saving…" : "Record"}
          </button>
        </div>
      </div>
    </div>
  );
}
