import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, XCircle, HelpCircle, FileText, Receipt, Paperclip, Upload, FileCheck2, Layers } from "lucide-react";
import { api, apiError, fileUrl } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { StatusPill, EmptyState, Modal, inr, inrShort } from "@/components/ui";

const STAGES = ["Site", "Admin", "Mgmt", "Accounts"];
// number of stages completed for a given status
const REACHED = {
  pending_admin: 1, pending_clarification: 1,
  pending_management: 2, management_clarification: 2,
  approved: 3, po_issued: 3, paid: 4,
};

function StageTrack({ status }) {
  if (status === "rejected") {
    return <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-bad"><XCircle className="w-3.5 h-3.5" /> Rejected</span>;
  }
  const reached = REACHED[status] ?? 0;
  return (
    <div className="flex items-center gap-1" title={STAGES.join(" → ")}>
      {STAGES.map((label, i) => {
        const done = i < reached;
        const active = i === reached && reached < 4;
        return (
          <span key={label} className="flex items-center">
            <span className="w-1.5 h-1.5 rounded-full transition-colors duration-300"
              style={{ background: done ? "#1a1c18" : active ? "#ccff00" : "#e7e4dc", boxShadow: active ? "0 0 0 2px #1a1c18" : "none" }} />
            {i < STAGES.length - 1 && <span className="w-4 h-[1.5px]" style={{ background: i < reached ? "#1a1c18" : "#e7e4dc" }} />}
          </span>
        );
      })}
    </div>
  );
}

export default function Procurement() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [actionFor, setActionFor] = useState(null);
  const [poFor, setPoFor] = useState(null);
  const [msFor, setMsFor] = useState(null);
  const [resubFor, setResubFor] = useState(null);

  const load = async () => {
    const [r, p] = await Promise.all([api.get("/procurement"), api.get("/projects")]);
    setRows(r.data); setProjects(p.data);
  };
  useEffect(() => { load(); }, []);

  const projName = (id) => projects.find(p => p.project_id === id)?.name || "—";

  const buckets = useMemo(() => ({
    active: rows.filter(r => ["pending_management", "management_clarification", "pending_admin", "pending_clarification", "approved", "po_issued"].includes(r.status)),
    done: rows.filter(r => ["paid", "rejected"].includes(r.status)),
  }), [rows]);

  const subtitle = {
    site_manager: "Raise a request with a Performa Invoice → management & admin approve → accounts issue a PO you can download.",
    management: "Give approval to admin-cleared procurement requests. Once you approve, accounts issue the PO and payment structure.",
    admin: "Give the first approval to site requests. Approved requests move to Management, then Accounts for PO & payment.",
    accounts: "Approved → issue a PO (upload the document) → set milestone payment structure → mark milestones paid.",
  }[user?.role] || "";

  return (
    <div data-testid="procurement-page" className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">Site Procurement</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">Procurement</h1>
          {subtitle && <p className="text-sm text-ink2 mt-3 max-w-2xl leading-relaxed">{subtitle}</p>}
        </div>
        {can(user, "site_manager", "admin") && (
          <button onClick={() => setShowNew(true)} className="btn-primary" data-testid="new-proc-btn"><Plus className="w-4 h-4" /> New request</button>
        )}
      </header>

      <section className="space-y-4">
        <div className="overline">Active queue</div>
        <div className="panel overflow-hidden ag-rise">
          <ProcTable rows={buckets.active} projName={projName} user={user} onAction={setActionFor} onPo={setPoFor} onMs={setMsFor} onResubmit={setResubFor} />
        </div>
      </section>

      {buckets.done.length > 0 && (
        <section className="space-y-4">
          <div className="overline">History</div>
          <div className="panel overflow-hidden ag-rise">
            <ProcTable rows={buckets.done} projName={projName} user={user} onAction={setActionFor} onPo={setPoFor} onMs={setMsFor} onResubmit={setResubFor} />
          </div>
        </section>
      )}

      {showNew && <NewProcurement projects={projects} user={user} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />}
      {actionFor && <ActionDialog req={actionFor} onClose={() => setActionFor(null)} onSaved={() => { setActionFor(null); load(); }} />}
      {poFor && <PoDialog req={poFor} onClose={() => setPoFor(null)} onSaved={() => { setPoFor(null); load(); }} />}
      {msFor && <MilestoneDialog req={msFor} user={user} onClose={() => { setMsFor(null); load(); }}
                    onRefresh={async () => { const r = await api.get("/procurement"); setRows(r.data); return r.data.find(x => x.request_id === msFor.request_id); }} />}
      {resubFor && <ResubmitDialog req={resubFor} projName={projName} onClose={() => setResubFor(null)} onSaved={() => { setResubFor(null); load(); }} />}
    </div>
  );
}

function ProcTable({ rows, projName, user, onAction, onPo, onMs, onResubmit }) {
  if (rows.length === 0) return <EmptyState icon={FileText} title="Nothing here" hint="Requests appear in this queue." />;
  const total = (r) => (r.milestones?.length
    ? r.milestones.reduce((s, m) => s + Number(m.amount || 0), 0)
    : (r.items || []).reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0));

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead><tr className="hairline">
          <th className="th">Request</th>
          <th className="th">Priority</th>
          <th className="th">Stage</th>
          <th className="th text-right">Est. value</th>
          <th className="th">Documents</th>
          <th className="th text-right">Action</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => {
            const notes = [r.notes && `Site Manager: ${r.notes}`, r.admin_note && `Admin: ${r.admin_note}`, r.mgmt_note && `Management: ${r.mgmt_note}`, r.accounts_note && `Accounts: ${r.accounts_note}`].filter(Boolean);
            const milestones = r.milestones || [];
            const hasDetail = notes.length > 0 || milestones.length > 0;
            return (
              <tr key={r.request_id} className="row align-top border-b border-line last:border-0" data-testid={`proc-row-${r.request_id}`}>
                <td className="td">
                  <div className="font-display text-base font-medium text-ink leading-tight">{r.subject}</div>
                  <div className="text-xs text-ink2 mt-0.5">{projName(r.project_id)} · {(r.items || []).length} item(s){r.po_number ? ` · PO ${r.po_number}` : ""}</div>
                  {hasDetail && (
                    <div className="mt-2 space-y-1.5">
                      {notes.map((n, i) => <div key={i} className="text-xs text-clay">{n}</div>)}
                      {milestones.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {milestones.map((m, i) => (
                            <span key={i} className={`text-[11px] px-2 py-0.5 rounded-md border ${m.status === "paid" ? "border-ok/30 bg-ok/5 text-ok" : "border-line text-ink2"}`}>
                              {m.label}: {inr(m.amount)} {m.status === "paid" ? "✓" : (m.due ? `· due ${m.due}` : "")}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </td>
                <td className="td"><StatusPill status={r.priority} dot={false} /></td>
                <td className="td">
                  <StageTrack status={r.status} />
                  <div className="mt-1.5"><StatusPill status={r.status} /></div>
                </td>
                <td className="td text-right font-mono-num text-ink whitespace-nowrap" title={inr(total(r))}>{inrShort(total(r))}</td>
                <td className="td">
                  <div className="flex flex-col gap-1.5">
                    {r.pi_file && <a href={fileUrl(r.pi_file.file_id)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid={`pi-link-${r.request_id}`}><Paperclip className="w-3.5 h-3.5" /> Performa Invoice</a>}
                    {r.po_file && <a href={fileUrl(r.po_file.file_id)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid={`po-link-${r.request_id}`}><FileCheck2 className="w-3.5 h-3.5" /> Purchase Order</a>}
                    {r.tax_invoice_file && <a href={fileUrl(r.tax_invoice_file.file_id)} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid={`tax-link-${r.request_id}`}><Paperclip className="w-3.5 h-3.5" /> Tax Invoice</a>}
                    {!r.pi_file && !r.po_file && !r.tax_invoice_file && <span className="text-xs text-ink2">—</span>}
                  </div>
                </td>
                <td className="td text-right whitespace-nowrap">
                  <div className="flex items-center justify-end gap-2">
                    {user?.role === "management" && ["pending_management", "management_clarification"].includes(r.status) && (
                      <button onClick={() => onAction(r)} className="btn-secondary text-xs py-1.5" data-testid={`mgmt-review-${r.request_id}`}>Review</button>
                    )}
                    {user?.role === "admin" && ["pending_admin", "pending_clarification"].includes(r.status) && (
                      <button onClick={() => onAction(r)} className="btn-secondary text-xs py-1.5" data-testid={`review-${r.request_id}`}>Review</button>
                    )}
                    {user?.role === "site_manager" && ["pending_clarification", "management_clarification"].includes(r.status) && (
                      <button onClick={() => onResubmit(r)} className="btn-primary text-xs py-1.5" data-testid={`resubmit-${r.request_id}`}><Upload className="w-3.5 h-3.5" /> Upload new PI</button>
                    )}
                    {can(user, "accounts", "admin") && r.status === "approved" && (
                      <button onClick={() => onPo(r)} className="btn-primary text-xs py-1.5" data-testid={`po-${r.request_id}`}><Upload className="w-3.5 h-3.5" /> Issue PO</button>
                    )}
                    {can(user, "accounts", "admin") && ["po_issued", "paid"].includes(r.status) && (
                      <button onClick={() => onMs(r)} className="btn-primary text-xs py-1.5" data-testid={`ms-${r.request_id}`}><Layers className="w-3.5 h-3.5" /> Payment structure</button>
                    )}
                    {!(user?.role === "management" && ["pending_management", "management_clarification"].includes(r.status)) &&
                     !(user?.role === "admin" && ["pending_admin", "pending_clarification"].includes(r.status)) &&
                     !(user?.role === "site_manager" && ["pending_clarification", "management_clarification"].includes(r.status)) &&
                     !(can(user, "accounts", "admin") && ["approved", "po_issued", "paid"].includes(r.status)) &&
                     <span className="text-xs text-ink2">—</span>}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function NewProcurement({ projects, user, onClose, onSaved }) {
  const [form, setForm] = useState({ project_id: user?.project_id || projects[0]?.project_id || "", subject: "", priority: "medium", notes: "", pi_amount: "" });
  const [items, setItems] = useState([{ name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const [pi, setPi] = useState(null);
  const [busy, setBusy] = useState(false);
  const itemsSum = items.reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0);
  const piAmt = Number(form.pi_amount || 0);
  const bifOff = piAmt > 0 && items.length > 1 && Math.abs(itemsSum - piAmt) >= 1;

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
      fd.append("pi_amount", piAmt || itemsSum);
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
        <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" data-testid="proc-notes" /></div>

      <div className="mt-4"><label className="label">PI amount (₹)</label>
        <input type="number" value={form.pi_amount} onChange={(e) => setForm({ ...form, pi_amount: e.target.value })} className="input font-mono-num" placeholder="Total value of this Performa Invoice" data-testid="proc-pi-amount" />
        {piAmt > 0 && items.length > 1 && (
          <div className={`text-[11px] mt-1 font-mono-num ${bifOff ? "text-clay" : "text-ok"}`} data-testid="proc-bif-hint">
            Bifurcated across {items.length} items: {inr(itemsSum)} {bifOff ? `· ${itemsSum > piAmt ? "over" : "under"} PI amount by ${inr(Math.abs(itemsSum - piAmt))} (you can still submit)` : "· matches PI amount ✓"}
          </div>
        )}
      </div>

      <div className="mt-4">
        <label className="label">Performa Invoice (PDF/image)</label>
        <label className="flex items-center gap-2 border border-dashed border-line rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="proc-pi-drop">
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
        <div className="border border-line rounded-md overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-line">
              <th className="th py-2">Name</th><th className="th py-2 text-right">Qty</th><th className="th py-2">Unit</th><th className="th py-2 text-right">Est. cost/unit</th><th></th>
            </tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="px-2 py-2"><input value={it.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" data-testid={`proc-name-${i}`} /></td>
                  <td className="px-2 py-2"><input type="number" value={it.quantity} onChange={(e) => updRow(i, { quantity: e.target.value })} className="input text-right w-20 font-mono-num" data-testid={`proc-qty-${i}`} /></td>
                  <td className="px-2 py-2"><input value={it.unit} onChange={(e) => updRow(i, { unit: e.target.value })} className="input w-20" /></td>
                  <td className="px-2 py-2"><input type="number" value={it.est_cost} onChange={(e) => updRow(i, { est_cost: e.target.value })} className="input text-right w-28 font-mono-num" /></td>
                  <td className="px-2 py-2">{items.length > 1 && <button onClick={() => rmRow(i)} className="text-bad"><Trash2 className="w-4 h-4" /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      </div>
    </Modal>
  );
}

function ResubmitDialog({ req, projName, onClose, onSaved }) {
  const [notes, setNotes] = useState(req.notes || "");
  const [piAmount, setPiAmount] = useState(req.pi_amount || "");
  const [items, setItems] = useState((req.items || []).length ? req.items.map(i => ({ ...i })) : [{ name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const [pi, setPi] = useState(null);
  const [busy, setBusy] = useState(false);
  const itemsSum = items.reduce((s, i) => s + Number(i.est_cost || 0) * Number(i.quantity || 0), 0);
  const piAmt = Number(piAmount || 0);
  const bifOff = piAmt > 0 && items.length > 1 && Math.abs(itemsSum - piAmt) >= 1;
  const askNote = req.admin_note || req.mgmt_note || "";

  const addRow = () => setItems([...items, { name: "", quantity: 1, unit: "pcs", est_cost: 0, notes: "" }]);
  const rmRow = (i) => setItems(items.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setItems(items.map((it, idx) => idx === i ? { ...it, ...patch } : it));

  const save = async () => {
    const valid = items.filter(i => i.name.trim() && Number(i.quantity) > 0);
    if (valid.length === 0) return toast.error("Add at least one item");
    if (!pi && !req.pi_file) return toast.error("Attach a Performa Invoice");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("notes", notes);
      fd.append("pi_amount", piAmt || itemsSum);
      fd.append("items", JSON.stringify(valid.map(i => ({ ...i, quantity: Number(i.quantity), est_cost: Number(i.est_cost || 0) }))));
      if (pi) fd.append("file", pi);
      await api.post(`/procurement/${req.request_id}/resubmit-pi`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("New PI submitted — admin notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title="Upload a new PI" subtitle={`${req.subject} · ${projName(req.project_id)}`} onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="resubmit-submit">{busy ? "Submitting…" : "Submit new PI"}</button></>}>
      {askNote && <div className="bg-clay/5 border border-clay/20 rounded-md p-3 mb-4 text-sm text-ink" data-testid="resubmit-ask-note"><span className="overline text-clay">What was asked</span><div className="mt-1">{askNote}</div></div>}
      <div className="mt-1"><label className="label">Notes to admin</label>
        <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className="input" data-testid="resubmit-notes" /></div>

      <div className="mt-4"><label className="label">PI amount (₹)</label>
        <input type="number" value={piAmount} onChange={(e) => setPiAmount(e.target.value)} className="input font-mono-num" placeholder="Total value of this Performa Invoice" data-testid="resubmit-pi-amount" />
        {piAmt > 0 && items.length > 1 && (
          <div className={`text-[11px] mt-1 font-mono-num ${bifOff ? "text-clay" : "text-ok"}`} data-testid="resubmit-bif-hint">
            Bifurcated across {items.length} items: {inr(itemsSum)} {bifOff ? `· ${itemsSum > piAmt ? "over" : "under"} PI amount by ${inr(Math.abs(itemsSum - piAmt))} (you can still submit)` : "· matches PI amount ✓"}
          </div>
        )}
      </div>

      <div className="mt-4">
        <label className="label">New Performa Invoice (PDF/image)</label>
        <label className="flex items-center gap-2 border border-dashed border-line rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="resubmit-pi-drop">
          <Paperclip className="w-4 h-4 text-ink2" />
          <span className="text-sm text-ink2">{pi ? pi.name : (req.pi_file ? "Attach a new PI (replaces the old one)" : "Attach the Performa Invoice")}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden onChange={(e) => setPi(e.target.files?.[0] || null)} data-testid="resubmit-pi-file" />
        </label>
      </div>

      <div className="mt-5">
        <div className="flex justify-between items-center mb-2">
          <div className="overline text-ink">Items</div>
          <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="resubmit-add-item"><Plus className="w-3.5 h-3.5" /> Add row</button>
        </div>
        <div className="border border-line rounded-md overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-line">
              <th className="th py-2">Name</th><th className="th py-2 text-right">Qty</th><th className="th py-2">Unit</th><th className="th py-2 text-right">Est. cost/unit</th><th></th>
            </tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="px-2 py-2"><input value={it.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" data-testid={`resubmit-name-${i}`} /></td>
                  <td className="px-2 py-2"><input type="number" value={it.quantity} onChange={(e) => updRow(i, { quantity: e.target.value })} className="input text-right w-20 font-mono-num" data-testid={`resubmit-qty-${i}`} /></td>
                  <td className="px-2 py-2"><input value={it.unit} onChange={(e) => updRow(i, { unit: e.target.value })} className="input w-20" /></td>
                  <td className="px-2 py-2"><input type="number" value={it.est_cost} onChange={(e) => updRow(i, { est_cost: e.target.value })} className="input text-right w-28 font-mono-num" /></td>
                  <td className="px-2 py-2">{items.length > 1 && <button onClick={() => rmRow(i)} className="text-bad"><Trash2 className="w-4 h-4" /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
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
      const isMgmt = ["pending_management", "management_clarification"].includes(req.status);
      const url = isMgmt ? `/procurement/${req.request_id}/mgmt-action` : `/procurement/${req.request_id}/action`;
      await api.post(url, { action, note });
      toast.success(action === "approve" ? (isMgmt ? "Approved — sent to Admin" : "Approved") : action === "reject" ? "Rejected" : "Marked for clarification");
      onSaved();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const btn = (val, label, Icon, active) => (
    <button onClick={() => setAction(val)} data-testid={`act-${val}`}
      className={`btn border transition-colors duration-200 ${action === val ? active : "border-line text-ink2 hover:bg-surfacealt"}`}>
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  );
  return (
    <Modal title="Review procurement" subtitle={req.subject} onClose={onClose}
      footer={<><button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="act-submit">{busy ? "Saving…" : "Confirm decision"}</button></>}>
      <div className="mb-4"><StageTrack status={req.status} /></div>
      {req.pi_file && <a href={fileUrl(req.pi_file.file_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold text-brand mb-4"><Paperclip className="w-4 h-4" /> View Performa Invoice</a>}
      {req.pi_amount > 0 && <div className="text-sm mb-2">PI amount: <span className="font-mono-num font-semibold">{inr(req.pi_amount)}</span></div>}
      {req.notes && <div className="bg-clay/5 border border-clay/20 rounded-md p-3 mb-4 text-sm text-ink" data-testid="review-sm-notes"><span className="overline text-clay">Site manager note</span><div className="mt-1">{req.notes}</div></div>}
      <div className="bg-surfacealt/60 border border-line rounded-md p-3 space-y-1 mb-4">
        {(req.items || []).map((i, idx) => <div key={idx} className="text-xs text-ink2">• {i.name} — <span className="font-mono-num">{i.quantity} {i.unit}</span> @ <span className="font-mono-num">{inr(i.est_cost)}</span>{i.notes ? <span className="text-clay"> · {i.notes}</span> : ""}</div>)}
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
  const [tax, setTax] = useState(null);
  const [note, setNote] = useState(req.accounts_note || "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!poNumber.trim()) return toast.error("PO number is required");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("po_number", poNumber);
      fd.append("note", note);
      if (po) fd.append("file", po);
      await api.post(`/procurement/${req.request_id}/po`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (tax) {
        const tf = new FormData(); tf.append("file", tax);
        await api.post(`/procurement/${req.request_id}/tax-invoice`, tf, { headers: { "Content-Type": "multipart/form-data" } });
      }
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
        <label className="flex items-center gap-2 border border-dashed border-line rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="po-drop">
          <FileCheck2 className="w-4 h-4 text-ink2" />
          <span className="text-sm text-ink2">{po ? po.name : "Attach the signed PO"}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden onChange={(e) => setPo(e.target.files?.[0] || null)} data-testid="po-file" />
        </label>
      </div>
      <div className="mt-4"><label className="label">Tax invoice (optional)</label>
        <label className="flex items-center gap-2 border border-dashed border-line rounded-md px-4 py-3 cursor-pointer hover:border-brand transition-colors duration-300" data-testid="po-tax-drop">
          <Paperclip className="w-4 h-4 text-ink2" />
          <span className="text-sm text-ink2">{tax ? tax.name : "Attach a tax invoice"}</span>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden onChange={(e) => setTax(e.target.files?.[0] || null)} data-testid="po-tax-file" />
        </label>
      </div>
      <div className="mt-4"><label className="label">Comment to site manager (optional)</label>
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="input" data-testid="po-note" placeholder="Anything to be incorporated by the site manager" /></div>
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
      <div className="border border-line rounded-md overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr className="bg-surfacealt/60 border-b border-line">
            <th className="th py-2">Milestone</th><th className="th py-2 text-right">Amount</th><th className="th py-2">Due</th><th className="th py-2">Status</th><th></th>
          </tr></thead>
          <tbody>
            {ms.map((m, i) => (
              <tr key={i} className="border-b border-line last:border-0">
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
        </table></div>
      </div>
      <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1 mt-3" data-testid="ms-add"><Plus className="w-3.5 h-3.5" /> Add milestone</button>
    </Modal>
  );
}
