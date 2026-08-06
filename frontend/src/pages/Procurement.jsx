import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, XCircle, HelpCircle, Banknote, Package } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, StatusPill, EmptyState, SectionCard, Modal, inr } from "@/components/ui";

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

  const subtitle = {
    site_manager: "Raise a request → admin approves → accounts records PO + payment.",
    admin: "Review and approve site managers' procurement requests.",
    accounts: "Approved requests come here to record PO number, paid amount and date.",
  }[user?.role] || "";

  return (
    <div data-testid="procurement-page">
      <PageHeader overline="Site Procurement" title="Procurement" subtitle={subtitle}>
        {can(user, "site_manager", "admin") && (
          <button onClick={() => setShowNew(true)} className="btn-primary" data-testid="new-proc-btn"><Plus className="w-4 h-4" /> New request</button>
        )}
      </PageHeader>

      <div className="space-y-6">
        <SectionCard title="Active queue" className="ag-rise">
          <ProcList rows={buckets.active} projName={projName} totalOf={totalOf} user={user} onAction={setActionFor} onPayment={setPaymentFor} />
        </SectionCard>
        {buckets.done.length > 0 && (
          <SectionCard title="History" className="ag-rise">
            <ProcList rows={buckets.done} projName={projName} totalOf={totalOf} user={user} onAction={setActionFor} onPayment={setPaymentFor} />
          </SectionCard>
        )}
      </div>

      {showNew && <NewProcurement projects={projects} defaultProject={user?.project_id} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />}
      {actionFor && <ActionDialog req={actionFor} onClose={() => setActionFor(null)} onSaved={() => { setActionFor(null); load(); }} />}
      {paymentFor && <PaymentDialog req={paymentFor} onClose={() => setPaymentFor(null)} onSaved={() => { setPaymentFor(null); load(); }} />}
    </div>
  );
}

function ProcList({ rows, projName, totalOf, user, onAction, onPayment }) {
  if (rows.length === 0) return <EmptyState icon={Package} title="Nothing here" hint="Requests will appear in this queue." />;
  return (
    <table className="w-full">
      <thead><tr className="border-b border-agborder bg-surfacealt/50">
        <th className="th">Subject</th><th className="th">Project</th><th className="th">Priority</th><th className="th">Items</th><th className="th text-right">Est. total</th><th className="th">Status</th><th className="th text-right">Action</th>
      </tr></thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.request_id} className="row" data-testid={`proc-row-${r.request_id}`}>
            <td className="td max-w-xs">
              <div className="font-semibold text-ink">{r.subject}</div>
              {r.notes && <div className="text-xs text-ink2 mt-0.5">{r.notes}</div>}
              {r.admin_note && <div className="text-xs text-clay mt-0.5">Admin: {r.admin_note}</div>}
            </td>
            <td className="td text-ink2">{projName(r.project_id)}</td>
            <td className="td"><StatusPill status={r.priority} dot={false} /></td>
            <td className="td text-ink2 text-xs">
              {(r.items || []).slice(0,3).map(i => `${i.name} ×${i.quantity}`).join(" · ")}
              {(r.items?.length || 0) > 3 && ` +${r.items.length - 3} more`}
            </td>
            <td className="td text-right font-mono-num">{inr(totalOf(r))}</td>
            <td className="td">
              <StatusPill status={r.status} />
              {r.po_number && <div className="text-xs text-ink2 mt-1 font-mono-num">PO: {r.po_number}</div>}
            </td>
            <td className="td text-right">
              {user?.role === "admin" && ["pending_admin","pending_clarification"].includes(r.status) && (
                <button onClick={() => onAction(r)} className="btn-secondary text-xs py-1.5" data-testid={`review-${r.request_id}`}>Review</button>
              )}
              {(user?.role === "accounts" || user?.role === "admin") && r.status === "approved" && (
                <button onClick={() => onPayment(r)} className="btn-primary text-xs py-1.5" data-testid={`pay-${r.request_id}`}><Banknote className="w-3.5 h-3.5" /> Record PO</button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NewProcurement({ projects, defaultProject, onClose, onSaved }) {
  const [form, setForm] = useState({ project_id: defaultProject || projects[0]?.project_id || "", subject: "", priority: "medium", notes: "" });
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
      await api.post("/procurement", { ...form, items: valid.map(i => ({ ...i, quantity: Number(i.quantity), est_cost: Number(i.est_cost || 0) })) });
      toast.success("Request submitted — admin has been notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title="New procurement request" onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="proc-submit">{busy ? "Submitting…" : "Submit request"}</button>
      </>}>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Project *</label>
          <select value={form.project_id} onChange={(e) => setForm({...form, project_id: e.target.value})} className="input" data-testid="proc-proj">
            {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </select></div>
        <div><label className="label">Priority</label>
          <select value={form.priority} onChange={(e) => setForm({...form, priority: e.target.value})} className="input">
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select></div>
      </div>
      <div className="mt-4"><label className="label">Subject *</label>
        <input value={form.subject} onChange={(e) => setForm({...form, subject: e.target.value})} className="input" placeholder="e.g. Cement + steel for phase 2" data-testid="proc-subject" /></div>
      <div className="mt-4"><label className="label">Notes</label>
        <textarea rows={2} value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" /></div>

      <div className="mt-5">
        <div className="flex justify-between items-center mb-2">
          <div className="overline text-ink">Items</div>
          <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="proc-add-item"><Plus className="w-3.5 h-3.5" /> Add row</button>
        </div>
        <div className="border border-agborder rounded-sm overflow-hidden">
          <table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-agborder">
              <th className="th py-2">Name</th><th className="th py-2 text-right">Qty</th><th className="th py-2">Unit</th><th className="th py-2 text-right">Est. cost/unit</th><th className="th py-2">Notes</th><th></th>
            </tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-b border-agborder last:border-0">
                  <td className="px-2 py-2"><input value={it.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" data-testid={`proc-name-${i}`} /></td>
                  <td className="px-2 py-2"><input type="number" value={it.quantity} onChange={(e) => updRow(i, { quantity: e.target.value })} className="input text-right w-20 font-mono-num" data-testid={`proc-qty-${i}`} /></td>
                  <td className="px-2 py-2"><input value={it.unit} onChange={(e) => updRow(i, { unit: e.target.value })} className="input w-20" /></td>
                  <td className="px-2 py-2"><input type="number" value={it.est_cost} onChange={(e) => updRow(i, { est_cost: e.target.value })} className="input text-right w-24 font-mono-num" /></td>
                  <td className="px-2 py-2"><input value={it.notes} onChange={(e) => updRow(i, { notes: e.target.value })} className="input" /></td>
                  <td className="px-2 py-2">{items.length > 1 && <button onClick={() => rmRow(i)} className="text-bad"><Trash2 className="w-4 h-4" /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Modal>
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

  const btn = (val, label, Icon, active) => (
    <button onClick={() => setAction(val)} data-testid={`act-${val}`}
      className={`btn border transition-colors duration-200 ${action === val ? active : "border-agborder text-ink2 hover:bg-surfacealt"}`}>
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  );

  return (
    <Modal title="Review procurement" subtitle={req.subject} onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="act-submit">{busy ? "Saving…" : "Confirm decision"}</button>
      </>}>
      <div className="space-y-4">
        <div className="bg-surfacealt/60 border border-agborder rounded-sm p-3 space-y-1">
          {(req.items || []).map((i, idx) => (
            <div key={idx} className="text-xs text-ink2">• {i.name} — <span className="font-mono-num">{i.quantity} {i.unit}</span> @ <span className="font-mono-num">{inr(i.est_cost)}</span>{i.notes ? ` (${i.notes})` : ""}</div>
          ))}
        </div>
        <div>
          <label className="label">Decision</label>
          <div className="grid grid-cols-3 gap-2">
            {btn("approve", "Approve", CheckCircle2, "bg-brand text-white border-brand")}
            {btn("reject", "Reject", XCircle, "bg-bad text-white border-bad")}
            {btn("clarify", "Details", HelpCircle, "bg-clay text-white border-clay")}
          </div>
        </div>
        <div>
          <label className="label">Note {action !== "approve" && <span className="text-bad">*</span>}</label>
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} className="input"
            placeholder={action === "clarify" ? "What extra info do you need?" : "Optional"} data-testid="act-note" />
        </div>
      </div>
    </Modal>
  );
}

function PaymentDialog({ req, onClose, onSaved }) {
  const total = (req.items || []).reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0);
  const [form, setForm] = useState({ po_number: "", paid_amount: total, paid_date: new Date().toISOString().slice(0,10), notes: "" });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!form.po_number.trim()) return toast.error("PO number is required");
    if (!form.paid_amount || form.paid_amount <= 0) return toast.error("Paid amount must be > 0");
    setBusy(true);
    try {
      await api.post(`/procurement/${req.request_id}/payment`, { ...form, paid_amount: Number(form.paid_amount) });
      toast.success("Payment recorded");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal title="Record PO & Payment" subtitle={req.subject} onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="pay-submit">{busy ? "Saving…" : "Record payment"}</button>
      </>}>
      <div className="space-y-4">
        <div><label className="label">PO number *</label>
          <input value={form.po_number} onChange={(e) => setForm({...form, po_number: e.target.value})} className="input font-mono-num" data-testid="pay-po" /></div>
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Paid amount *</label>
            <input type="number" value={form.paid_amount} onChange={(e) => setForm({...form, paid_amount: e.target.value})} className="input font-mono-num" data-testid="pay-amt" /></div>
          <div><label className="label">Paid date</label>
            <input type="date" value={form.paid_date} onChange={(e) => setForm({...form, paid_date: e.target.value})} className="input font-mono-num" /></div>
        </div>
        <div><label className="label">Notes / Reference</label>
          <input value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" placeholder="Vendor, txn ref, etc." /></div>
      </div>
    </Modal>
  );
}
