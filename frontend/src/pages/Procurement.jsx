import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, XCircle, HelpCircle, FileText, Receipt, Paperclip, Upload, FileCheck2, Layers } from "lucide-react";
import { api, apiError, fileUrl } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, StatusPill, EmptyState, SectionCard, Modal, inr } from "@/components/ui";

export default function Procurement() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [actionFor, setActionFor] = useState(null);
  const [poFor, setPoFor] = useState(null);
  const [msFor, setMsFor] = useState(null);

  const load = async () => {
    const [r, p] = await Promise.all([api.get("/procurement"), api.get("/projects")]);
    setRows(r.data); setProjects(p.data);
  };
  useEffect(() => { load(); }, []);

  const projName = (id) => projects.find(p => p.project_id === id)?.name || "—";

  const buckets = useMemo(() => ({
    active: rows.filter(r => ["pending_admin", "pending_clarification", "approved", "po_issued"].includes(r.status)),
    done: rows.filter(r => ["paid", "rejected"].includes(r.status)),
  }), [rows]);

  const subtitle = {
    site_manager: "Raise a request with a Performa Invoice → admin approves → accounts issue a PO you can download.",
    admin: "Approve requests; accounts then issue POs and set the payment structure.",
    accounts: "Approved → issue a PO (upload the document) → set milestone payment structure → mark milestones paid.",
  }[user?.role] || "";

  return (
    <div data-testid="procurement-page">
      <PageHeader overline="Site Procurement" title="Procurement" subtitle={subtitle}>
        {can(user, "site_manager", "admin") && (
          <button onClick={() => setShowNew(true)} className="btn-primary" data-testid="new-proc-btn"><Plus className="w-4 h-4" /> New request</button>
        )}
      </PageHeader>

      <div className="space-y-6">
        <SectionCard title="Active queue" className="ag-rise" bodyClass="divide-y divide-agborder">
          <ProcList rows={buckets.active} projName={projName} user={user} onAction={setActionFor} onPo={setPoFor} onMs={setMsFor} />
        </SectionCard>
        {buckets.done.length > 0 && (
          <SectionCard title="History" className="ag-rise" bodyClass="divide-y divide-agborder">
            <ProcList rows={buckets.done} projName={projName} user={user} onAction={setActionFor} onPo={setPoFor} onMs={setMsFor} />
          </SectionCard>
        )}
      </div>

      {showNew && <NewProcurement projects={projects} user={user} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />}
      {actionFor && <ActionDialog req={actionFor} onClose={() => setActionFor(null)} onSaved={() => { setActionFor(null); load(); }} />}
      {poFor && <PoDialog req={poFor} onClose={() => setPoFor(null)} onSaved={() => { setPoFor(null); load(); }} />}
      {msFor && <MilestoneDialog req={msFor} user={user} onClose={() => { setMsFor(null); load(); }}
                    onRefresh={async () => { const r = await api.get("/procurement"); setRows(r.data); return r.data.find(x => x.request_id === msFor.request_id); }} />}
    </div>
  );
}

function ProcList({ rows, projName, user, onAction, onPo, onMs }) {
  if (rows.length === 0) return <EmptyState icon={FileText} title="Nothing here" hint="Requests appear in this queue." />;
  const total = (r) => (r.milestones?.length
    ? r.milestones.reduce((s, m) => s + Number(m.amount || 0), 0)
    : (r.items || []).reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0));
  return rows.map((r) => (
    <div key={r.request_id} className="px-5 py-4" data-testid={`proc-row-${r.request_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-display text-lg font-bold text-ink">{r.subject}</span>
            <StatusPill status={r.priority} dot={false} />
            <StatusPill status={r.status} />
          </div>
          <div className="text-xs text-ink2 mt-1">{projName(r.project_id)} · {(r.items || []).length} item(s) · Est. {inr(total(r))}{r.po_number ? ` · PO ${r.po_number}` : ""}</div>
          {r.admin_note && <div className="text-xs text-clay mt-1">Admin: {r.admin_note}</div>}
          <div className="flex items-center gap-3 mt-2">
            {r.pi_file && <a href={fileUrl(r.pi_file.file_id)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid={`pi-link-${r.request_id}`}><Paperclip className="w-3.5 h-3.5" /> Performa Invoice</a>}
            {r.po_file && <a href={fileUrl(r.po_file.file_id)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid={`po-link-${r.request_id}`}><FileCheck2 className="w-3.5 h-3.5" /> Purchase Order</a>}
          </div>
          {(r.milestones || []).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {r.milestones.map((m, i) => (
                <span key={i} className={`text-[11px] px-2 py-1 rounded-md border ${m.status === "paid" ? "border-ok/30 bg-ok/5 text-ok" : "border-agborder text-ink2"}`}>
                  {m.label}: {inr(m.amount)} {m.status === "paid" ? "✓" : (m.due ? `· due ${m.due}` : "")}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {user?.role === "admin" && ["pending_admin", "pending_clarification"].includes(r.status) && (
            <button onClick={() => onAction(r)} className="btn-secondary text-xs py-1.5" data-testid={`review-${r.request_id}`}>Review</button>
          )}
          {can(user, "accounts", "admin") && r.status === "approved" && (
            <button onClick={() => onPo(r)} className="btn-primary text-xs py-1.5" data-testid={`po-${r.request_id}`}><Upload className="w-3.5 h-3.5" /> Issue PO</button>
          )}
          {can(user, "accounts", "admin") && ["po_issued", "paid"].includes(r.status) && (
            <button onClick={() => onMs(r)} className="btn-primary text-xs py-1.5" data-testid={`ms-${r.request_id}`}><Layers className="w-3.5 h-3.5" /> Payment structure</button>
          )}
        </div>
      </div>
    </div>
  ));
}

function NewProcurement({ projects, user, onClose, onSaved }) {
  const [form, setForm] = useState({ project_id: user?.project_id || projects[0]?.project_id || "", subject: "", priority: "medium", notes: "" });
  const [items, setItems] = useState([{ name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const [pi, setPi] = useState(null);
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
      const fd = new FormData();
      fd.append("project_id", form.project_id); fd.append("subject", form.subject);
      fd.append("priority", form.priority); fd.append("notes", form.notes);
      fd.append("items", JSON.stringify(valid.map(i => ({ ...i, quantity: Number(i.quantity), est_cost: Number(i.est_cost || 0) }))));
      if (pi) fd.append("file", pi);
      await api.post("/procurement", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Request submitted — admin notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title="New procurement request" onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="proc-submit">{busy ? "Submitting…" : "Submit request"}</button></>}>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Project *</label>
          <select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="input" data-testid="proc-proj">
            {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </select></div>
        <div><label className="label">Priority</label>
          <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="input">
            <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option>
          </select></div>
      </div>
      <div className="mt-4"><label className="label">Subject *</label>
        <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" placeholder="e.g. Cement + steel for phase 2" data-testid="proc-subject" /></div>
      <div className="mt-4"><label className="label">Notes</label>
        <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" /></div>

      <div className="mt-4">
        <label className="label">Performa Invoice (PDF/image)</label>
        <label className="flex items-center gap-2 border border-dashed border-agborder rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="proc-pi-drop">
          <Paperclip className="w-4 h-4 text-ink2" />
          <span className="text-sm text-ink2">{pi ? pi.name : "Attach the Performa Invoice"}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden onChange={(e) => setPi(e.target.files?.[0] || null)} data-testid="proc-pi-file" />
        </label>
      </div>

      <div className="mt-5">
        <div className="flex justify-between items-center mb-2">
          <div className="overline text-ink">Items</div>
          <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="proc-add-item"><Plus className="w-3.5 h-3.5" /> Add row</button>
        </div>
        <div className="border border-agborder rounded-md overflow-hidden">
          <table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-agborder">
              <th className="th py-2">Name</th><th className="th py-2 text-right">Qty</th><th className="th py-2">Unit</th><th className="th py-2 text-right">Est. cost/unit</th><th></th>
            </tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-b border-agborder last:border-0">
                  <td className="px-2 py-2"><input value={it.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" data-testid={`proc-name-${i}`} /></td>
                  <td className="px-2 py-2"><input type="number" value={it.quantity} onChange={(e) => updRow(i, { quantity: e.target.value })} className="input text-right w-20 font-mono-num" data-testid={`proc-qty-${i}`} /></td>
                  <td className="px-2 py-2"><input value={it.unit} onChange={(e) => updRow(i, { unit: e.target.value })} className="input w-20" /></td>
                  <td className="px-2 py-2"><input type="number" value={it.est_cost} onChange={(e) => updRow(i, { est_cost: e.target.value })} className="input text-right w-28 font-mono-num" /></td>
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
      toast.success(action === "approve" ? "Approved" : action === "reject" ? "Rejected" : "Marked for clarification");
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const btn = (val, label, Icon, active) => (
    <button onClick={() => setAction(val)} data-testid={`act-${val}`}
      className={`btn border transition-colors duration-200 ${action === val ? active : "border-agborder text-ink2 hover:bg-surfacealt"}`}>
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  );
  return (
    <Modal title="Review procurement" subtitle={req.subject} onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="act-submit">{busy ? "Saving…" : "Confirm decision"}</button></>}>
      {req.pi_file && <a href={fileUrl(req.pi_file.file_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold text-brand mb-4"><Paperclip className="w-4 h-4" /> View Performa Invoice</a>}
      <div className="bg-surfacealt/60 border border-agborder rounded-md p-3 space-y-1 mb-4">
        {(req.items || []).map((i, idx) => <div key={idx} className="text-xs text-ink2">• {i.name} — <span className="font-mono-num">{i.quantity} {i.unit}</span> @ <span className="font-mono-num">{inr(i.est_cost)}</span></div>)}
      </div>
      <label className="label">Decision</label>
      <div className="grid grid-cols-3 gap-2">
        {btn("approve", "Approve", CheckCircle2, "bg-brand text-white border-brand")}
        {btn("reject", "Reject", XCircle, "bg-bad text-white border-bad")}
        {btn("clarify", "Details", HelpCircle, "bg-clay text-white border-clay")}
      </div>
      <label className="label mt-4">Note {action !== "approve" && <span className="text-bad">*</span>}</label>
      <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} className="input" data-testid="act-note" />
    </Modal>
  );
}

function PoDialog({ req, onClose, onSaved }) {
  const [poNumber, setPoNumber] = useState(req.po_number || "");
  const [po, setPo] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!poNumber.trim()) return toast.error("PO number is required");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("po_number", poNumber);
      if (po) fd.append("file", po);
      await api.post(`/procurement/${req.request_id}/po`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("PO issued — site manager notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  return (
    <Modal title="Issue Purchase Order" subtitle={req.subject} onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="po-submit">{busy ? "Saving…" : "Issue PO"}</button></>}>
      <div><label className="label">PO number *</label>
        <input value={poNumber} onChange={(e) => setPoNumber(e.target.value)} className="input font-mono-num" data-testid="po-number" /></div>
      <div className="mt-4"><label className="label">PO document (PDF/image)</label>
        <label className="flex items-center gap-2 border border-dashed border-agborder rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="po-drop">
          <FileCheck2 className="w-4 h-4 text-ink2" />
          <span className="text-sm text-ink2">{po ? po.name : "Attach the signed PO"}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden onChange={(e) => setPo(e.target.files?.[0] || null)} data-testid="po-file" />
        </label>
      </div>
    </Modal>
  );
}

function MilestoneDialog({ req, user, onClose, onRefresh }) {
  const [live, setLive] = useState(req);
  const [ms, setMs] = useState(() => (req.milestones?.length ? req.milestones.map(m => ({ ...m })) : [{ label: "", amount: 0, due: "", status: "pending" }]));
  const [busy, setBusy] = useState(false);
  const canPay = can(user, "accounts", "admin");

  const addRow = () => setMs([...ms, { label: "", amount: 0, due: "", status: "pending" }]);
  const rmRow = (i) => setMs(ms.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setMs(ms.map((m, idx) => idx === i ? { ...m, ...patch } : m));

  const refresh = async () => {
    const updated = await onRefresh();
    if (updated) { setLive(updated); setMs((updated.milestones || []).map(m => ({ ...m }))); }
  };

  const saveStructure = async () => {
    const valid = ms.filter(m => m.label.trim() && Number(m.amount) > 0);
    if (valid.length === 0) return toast.error("Add at least one milestone");
    setBusy(true);
    try {
      await api.post(`/procurement/${req.request_id}/milestones`, { milestones: valid.map(m => ({ label: m.label, amount: Number(m.amount), due: m.due || "" })) });
      toast.success("Payment structure saved");
      await refresh();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const payMilestone = async (i) => {
    try {
      await api.post(`/procurement/${req.request_id}/milestones/${i}/pay`, { paid_date: new Date().toISOString().slice(0, 10) });
      toast.success("Milestone marked paid");
      await refresh();
    } catch (e) { toast.error(apiError(e)); }
  };

  const total = ms.reduce((s, m) => s + Number(m.amount || 0), 0);
  const saved = (live.milestones || []).length > 0;

  return (
    <Modal size="xl" title="Payment structure (PO milestones)" subtitle={`${req.subject}${req.po_number ? ` · PO ${req.po_number}` : ""}`} onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Close</button>
        <button onClick={saveStructure} disabled={busy} className="btn-primary" data-testid="ms-save">{busy ? "Saving…" : saved ? "Update structure" : "Save structure"}</button></>}>
      <div className="text-xs text-ink2 mb-3">Define milestones e.g. 50% advance on a date, 50% on completion. Mark each paid as accounts clears it.</div>
      <div className="border border-agborder rounded-md overflow-hidden">
        <table className="w-full">
          <thead><tr className="bg-surfacealt/60 border-b border-agborder">
            <th className="th py-2">Milestone</th><th className="th py-2 text-right">Amount</th><th className="th py-2">Due</th><th className="th py-2">Status</th><th></th>
          </tr></thead>
          <tbody>
            {ms.map((m, i) => (
              <tr key={i} className="border-b border-agborder last:border-0">
                <td className="px-2 py-2"><input value={m.label} onChange={(e) => updRow(i, { label: e.target.value })} className="input" placeholder="e.g. 50% advance" data-testid={`ms-label-${i}`} disabled={m.status === "paid"} /></td>
                <td className="px-2 py-2"><input type="number" value={m.amount} onChange={(e) => updRow(i, { amount: e.target.value })} className="input text-right w-32 font-mono-num" data-testid={`ms-amt-${i}`} disabled={m.status === "paid"} /></td>
                <td className="px-2 py-2"><input type="date" value={m.due || ""} onChange={(e) => updRow(i, { due: e.target.value })} className="input font-mono-num" disabled={m.status === "paid"} /></td>
                <td className="px-2 py-2"><StatusPill status={m.status === "paid" ? "paid" : "pending"} /></td>
                <td className="px-2 py-2">
                  {m.status === "paid" ? <span className="text-xs text-ok">{m.paid_date}</span>
                    : saved && canPay ? <button onClick={() => payMilestone(i)} className="btn-primary text-xs py-1" data-testid={`ms-pay-${i}`}><Receipt className="w-3 h-3" /> Pay</button>
                    : ms.length > 1 ? <button onClick={() => rmRow(i)} className="text-bad"><Trash2 className="w-4 h-4" /></button> : null}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr className="bg-surfacealt/40"><td className="px-2 py-2.5 text-sm font-semibold">Total</td><td className="px-2 py-2.5 text-right font-mono-num font-bold">{inr(total)}</td><td colSpan={3}></td></tr></tfoot>
        </table>
      </div>
      <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1 mt-3" data-testid="ms-add"><Plus className="w-3.5 h-3.5" /> Add milestone</button>
    </Modal>
  );
}
