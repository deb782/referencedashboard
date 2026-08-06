import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Upload, HandCoins, Plus, Trash2 } from "lucide-react";
import { api, API_BASE, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";

const fmt = (n) => "\u20B9" + Math.round(n || 0).toLocaleString("en-IN");

export default function Units() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [units, setUnits] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [sellFor, setSellFor] = useState(null);

  const load = async () => {
    const r = await api.get("/units", { params: projectId ? { project_id: projectId } : {} });
    setUnits(r.data);
  };
  useEffect(() => {
    api.get("/projects").then((r) => {
      setProjects(r.data);
      if (r.data.length && !projectId) setProjectId(r.data[0].project_id);
    });
  }, []);
  useEffect(() => { if (projectId) load(); }, [projectId]);

  const filtered = units;
  const available = filtered.filter(u => u.status === "available").length;
  const sold = filtered.filter(u => u.status === "sold").length;

  const handleUpload = async (file) => {
    if (!file || !projectId) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("project_id", projectId);
      fd.append("file", file);
      const r = await api.post("/units/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Imported ${r.data.inserted} units${r.data.errors?.length ? ` (${r.data.errors.length} skipped)` : ""}`);
      load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setUploading(false); }
  };

  return (
    <div className="space-y-6" data-testid="units-page">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Units</h1>
          <p className="text-sm text-stone-500 mt-1">
            {can(user, "admin") ? "Bulk-upload the RERA cost sheet, then Post-Sales can mark plots sold." : "Available plots for booking."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input w-64" data-testid="unit-project-select">
            {projects.length === 0 && <option value="">No projects yet</option>}
            {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </select>
          {can(user, "admin") && (
            <label className="btn-secondary cursor-pointer inline-flex items-center" data-testid="unit-upload-btn">
              <Upload className="w-4 h-4 mr-1" /> {uploading ? "Uploading…" : "Upload Excel"}
              <input type="file" accept=".xlsx,.csv" hidden onChange={(e) => handleUpload(e.target.files?.[0])} />
            </label>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tile label="Available" value={available} tone="emerald" />
        <Tile label="Sold" value={sold} tone="sky" />
        <Tile label="Total" value={filtered.length} tone="stone" />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
            <tr>
              <th className="text-left py-3 px-4">Plot</th>
              <th className="text-left py-3 px-4">Area (sft)</th>
              <th className="text-left py-3 px-4">PLC</th>
              <th className="text-right py-3 px-4">Sheet total</th>
              <th className="text-left py-3 px-4">Status</th>
              <th className="text-left py-3 px-4">Buyer</th>
              <th className="text-right py-3 px-4">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {filtered.map(u => (
              <tr key={u.unit_id} data-testid={`unit-row-${u.plot_number}`}>
                <td className="py-2 px-4 font-medium">{u.plot_number}</td>
                <td className="py-2 px-4 text-stone-600">{u.area_sqft || "—"}</td>
                <td className="py-2 px-4 text-xs text-stone-500">
                  {Object.entries(u.plc_details || {}).filter(([,v]) => v).map(([k]) => k.replace(/_/g," ")).join(", ") || "—"}
                </td>
                <td className="py-2 px-4 text-right tabular-nums text-stone-600">{fmt(u.other_charges?.sheet_grand_total)}</td>
                <td className="py-2 px-4">
                  {u.status === "sold"
                    ? <span className="pill bg-sky-50 border-sky-200 text-sky-800">Sold</span>
                    : <span className="pill bg-emerald-50 border-emerald-200 text-emerald-800">Available</span>}
                </td>
                <td className="py-2 px-4 text-stone-600 text-xs">{u.buyer_name || "—"}</td>
                <td className="py-2 px-4 text-right">
                  {u.status === "available" && can(user, "admin", "post_sales") && (
                    <button onClick={() => setSellFor(u)} className="btn-primary text-xs" data-testid={`sell-${u.plot_number}`}>
                      <HandCoins className="w-3 h-3 inline mr-1" /> Mark Sold
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={7} className="py-12 text-center text-stone-500">
                No units yet — {can(user, "admin") ? "upload your RERA Excel to get started" : "wait for admin to upload inventory"}.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {sellFor && <SellDialog unit={sellFor} onClose={() => setSellFor(null)} onSaved={() => { setSellFor(null); load(); }} />}
    </div>
  );
}

function Tile({ label, value, tone }) {
  const cls = tone === "emerald" ? "bg-emerald-50 border-emerald-200 text-emerald-900"
    : tone === "sky" ? "bg-sky-50 border-sky-200 text-sky-900"
    : "bg-white border-stone-200 text-stone-900";
  return <div className={`p-4 rounded-xl border ${cls}`}>
    <div className="text-[11px] uppercase tracking-widest text-stone-500">{label}</div>
    <div className="text-2xl font-bold mt-1">{value}</div>
  </div>;
}

function SellDialog({ unit, onClose, onSaved }) {
  const [form, setForm] = useState({
    buyer_name: "", buyer_contact: "", sale_date: new Date().toISOString().slice(0,10),
    final_price: unit.other_charges?.sheet_grand_total || 0,
    booking_amount: 0,
  });
  const [schedule, setSchedule] = useState([{ due_date: "", amount: 0, notes: "" }]);
  const [busy, setBusy] = useState(false);

  const remainder = Math.max(0, (form.final_price || 0) - (form.booking_amount || 0));
  const scheduleTotal = schedule.reduce((s, r) => s + Number(r.amount || 0), 0);
  const diff = remainder - scheduleTotal;

  const addRow = () => setSchedule([...schedule, { due_date: "", amount: 0, notes: "" }]);
  const removeRow = (i) => setSchedule(schedule.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setSchedule(schedule.map((r, idx) => idx === i ? { ...r, ...patch } : r));

  const save = async () => {
    if (!form.buyer_name || !form.buyer_contact) return toast.error("Buyer name and contact are required");
    if (!form.sale_date) return toast.error("Sale date is required");
    if (!form.final_price || form.final_price <= 0) return toast.error("Final price must be > 0");
    if (schedule.some(r => !r.due_date || !r.amount)) return toast.error("Every schedule row needs a date and amount");
    if (Math.abs(diff) > 1) return toast.error(`Schedule total (${scheduleTotal.toLocaleString()}) must equal remainder (${remainder.toLocaleString()})`);
    setBusy(true);
    try {
      await api.post(`/units/${unit.unit_id}/sell`, {
        ...form,
        final_price: Number(form.final_price),
        booking_amount: Number(form.booking_amount),
        schedule: schedule.map(r => ({ ...r, amount: Number(r.amount) })),
      });
      toast.success("Sale recorded — accounts & admin notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6" onClick={onClose}>
      <div className="card w-full max-w-3xl p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="text-lg font-bold">Mark Plot {unit.plot_number} as sold</div>
        <div className="text-xs text-stone-500 mb-4">Sheet grand total (reference): {fmt(unit.other_charges?.sheet_grand_total)}</div>

        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Buyer name *</label>
            <input value={form.buyer_name} onChange={(e) => setForm({...form, buyer_name: e.target.value})} className="input" data-testid="s-buyer" /></div>
          <div><label className="label">Buyer contact *</label>
            <input value={form.buyer_contact} onChange={(e) => setForm({...form, buyer_contact: e.target.value})} className="input" data-testid="s-contact" /></div>
          <div><label className="label">Sale date *</label>
            <input type="date" value={form.sale_date} onChange={(e) => setForm({...form, sale_date: e.target.value})} className="input" data-testid="s-date" /></div>
          <div><label className="label">Final price (all inclusive) *</label>
            <input type="number" value={form.final_price} onChange={(e) => setForm({...form, final_price: e.target.value})} className="input" data-testid="s-price" /></div>
          <div><label className="label">Booking amount paid</label>
            <input type="number" value={form.booking_amount} onChange={(e) => setForm({...form, booking_amount: e.target.value})} className="input" data-testid="s-booking" /></div>
          <div className="bg-stone-50 border border-stone-200 rounded-md p-3 text-sm">
            <div className="text-xs uppercase tracking-widest text-stone-500">Remainder to schedule</div>
            <div className="text-xl font-bold tabular-nums">{fmt(remainder)}</div>
          </div>
        </div>

        <div className="mt-6">
          <div className="flex justify-between items-center mb-2">
            <div className="text-sm font-semibold">Payment schedule</div>
            <button onClick={addRow} className="text-xs text-emerald-800 hover:text-emerald-900" data-testid="s-add-row">
              <Plus className="w-3 h-3 inline" /> Add row
            </button>
          </div>
          <div className="border border-stone-200 rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
                <tr>
                  <th className="text-left py-2 px-3">#</th>
                  <th className="text-left py-2 px-3">Due date</th>
                  <th className="text-right py-2 px-3">Amount</th>
                  <th className="text-left py-2 px-3">Notes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((r, i) => (
                  <tr key={i} className="border-t border-stone-100">
                    <td className="py-2 px-3 text-stone-500">{i+1}</td>
                    <td className="py-2 px-3">
                      <input type="date" value={r.due_date} onChange={(e) => updRow(i, { due_date: e.target.value })} className="input" data-testid={`s-row-date-${i}`} />
                    </td>
                    <td className="py-2 px-3">
                      <input type="number" value={r.amount} onChange={(e) => updRow(i, { amount: e.target.value })} className="input text-right" data-testid={`s-row-amt-${i}`} />
                    </td>
                    <td className="py-2 px-3">
                      <input value={r.notes} onChange={(e) => updRow(i, { notes: e.target.value })} className="input" placeholder="Optional" />
                    </td>
                    <td className="py-2 px-3">
                      {schedule.length > 1 && (
                        <button onClick={() => removeRow(i)} className="text-rose-600" title="Remove">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className={`text-sm ${Math.abs(diff) > 1 ? "bg-rose-50" : "bg-emerald-50"}`}>
                <tr>
                  <td colSpan={2} className="py-2 px-3 font-semibold">
                    Schedule total {Math.abs(diff) > 1 ? `· off by ${fmt(Math.abs(diff))}` : "· matches ✓"}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums font-bold">{fmt(scheduleTotal)}</td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={save} disabled={busy} className="btn-primary" data-testid="s-submit">
            {busy ? "Saving…" : "Confirm sale"}
          </button>
        </div>
      </div>
    </div>
  );
}
