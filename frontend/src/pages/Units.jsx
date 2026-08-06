import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, HandCoins, Plus, Trash2, Home } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, Kpi, StatusPill, EmptyState, Modal, inr } from "@/components/ui";

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

  const available = units.filter(u => u.status === "available").length;
  const sold = units.filter(u => u.status === "sold").length;

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
    <div data-testid="units-page">
      <PageHeader overline="Plot Inventory" title="Units"
        subtitle={can(user, "admin") ? "Bulk-upload the RERA cost sheet, then Post-Sales can mark plots sold." : "Available plots for booking."}>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input w-60" data-testid="unit-project-select">
          {projects.length === 0 && <option value="">No projects yet</option>}
          {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
        </select>
        {can(user, "admin") && (
          <label className="btn-secondary cursor-pointer" data-testid="unit-upload-btn">
            <Upload className="w-4 h-4" /> {uploading ? "Uploading…" : "Upload Excel"}
            <input type="file" accept=".xlsx,.csv" hidden onChange={(e) => handleUpload(e.target.files?.[0])} />
          </label>
        )}
      </PageHeader>

      <div className="grid grid-cols-3 gap-6 mb-6">
        <Kpi label="Available" value={available} tone="ok" accent="#5a6b10" className="ag-rise" mono={false} />
        <Kpi label="Sold" value={sold} tone="brand" accent="#3d4a0a" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Total" value={units.length} tone="ink" className="ag-rise ag-rise-2" mono={false} />
      </div>

      <div className="card overflow-hidden ag-rise">
        <table className="w-full">
          <thead><tr className="border-b border-agborder bg-surfacealt/50">
            <th className="th">Plot</th><th className="th">Area (sft)</th><th className="th">PLC</th><th className="th text-right">Sheet total</th><th className="th">Status</th><th className="th">Buyer</th><th className="th text-right">Action</th>
          </tr></thead>
          <tbody>
            {units.map(u => (
              <tr key={u.unit_id} className="row" data-testid={`unit-row-${u.plot_number}`}>
                <td className="td font-mono-num font-bold">{u.plot_number}</td>
                <td className="td text-ink2 font-mono-num">{u.area_sqft || "—"}</td>
                <td className="td text-ink2 text-xs">{Object.entries(u.plc_details || {}).filter(([,v]) => v).map(([k]) => k.replace(/_/g," ")).join(", ") || "—"}</td>
                <td className="td text-right font-mono-num text-ink2">{inr(u.other_charges?.sheet_grand_total)}</td>
                <td className="td"><StatusPill status={u.status} /></td>
                <td className="td text-ink2 text-xs">{u.buyer_name || "—"}</td>
                <td className="td text-right">
                  {u.status === "available" && can(user, "admin", "post_sales") && (
                    <button onClick={() => setSellFor(u)} className="btn-primary text-xs py-1.5" data-testid={`sell-${u.plot_number}`}>
                      <HandCoins className="w-3.5 h-3.5" /> Mark Sold
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {units.length === 0 && (
              <tr><td colSpan={7}><EmptyState icon={Home} title="No units yet"
                hint={can(user, "admin") ? "Upload your RERA Excel to populate plots." : "Wait for admin to upload inventory."} /></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {sellFor && <SellDialog unit={sellFor} onClose={() => setSellFor(null)} onSaved={() => { setSellFor(null); load(); }} />}
    </div>
  );
}

function SellDialog({ unit, onClose, onSaved }) {
  const [form, setForm] = useState({
    buyer_name: "", buyer_contact: "", sale_date: new Date().toISOString().slice(0,10),
    final_price: unit.other_charges?.sheet_grand_total || 0, booking_amount: 0,
  });
  const [schedule, setSchedule] = useState([{ due_date: "", amount: 0, notes: "" }]);
  const [busy, setBusy] = useState(false);

  const remainder = Math.max(0, (form.final_price || 0) - (form.booking_amount || 0));
  const scheduleTotal = schedule.reduce((s, r) => s + Number(r.amount || 0), 0);
  const diff = remainder - scheduleTotal;
  const matches = Math.abs(diff) <= 1;

  const addRow = () => setSchedule([...schedule, { due_date: "", amount: 0, notes: "" }]);
  const removeRow = (i) => setSchedule(schedule.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setSchedule(schedule.map((r, idx) => idx === i ? { ...r, ...patch } : r));

  const save = async () => {
    if (!form.buyer_name || !form.buyer_contact) return toast.error("Buyer name and contact are required");
    if (!form.sale_date) return toast.error("Sale date is required");
    if (!form.final_price || form.final_price <= 0) return toast.error("Final price must be > 0");
    if (schedule.some(r => !r.due_date || !r.amount)) return toast.error("Every schedule row needs a date and amount");
    if (!matches) return toast.error(`Schedule total (${scheduleTotal.toLocaleString()}) must equal remainder (${remainder.toLocaleString()})`);
    setBusy(true);
    try {
      await api.post(`/units/${unit.unit_id}/sell`, {
        ...form, final_price: Number(form.final_price), booking_amount: Number(form.booking_amount),
        schedule: schedule.map(r => ({ ...r, amount: Number(r.amount) })),
      });
      toast.success("Sale recorded — accounts & admin notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title={`Mark Plot ${unit.plot_number} as sold`}
      subtitle={`Sheet grand total (reference): ${inr(unit.other_charges?.sheet_grand_total)}`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="s-submit">{busy ? "Saving…" : "Confirm sale"}</button>
      </>}>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Buyer name *</label>
          <input value={form.buyer_name} onChange={(e) => setForm({...form, buyer_name: e.target.value})} className="input" data-testid="s-buyer" /></div>
        <div><label className="label">Buyer contact *</label>
          <input value={form.buyer_contact} onChange={(e) => setForm({...form, buyer_contact: e.target.value})} className="input font-mono-num" data-testid="s-contact" /></div>
        <div><label className="label">Sale date *</label>
          <input type="date" value={form.sale_date} onChange={(e) => setForm({...form, sale_date: e.target.value})} className="input font-mono-num" data-testid="s-date" /></div>
        <div><label className="label">Final price (all inclusive) *</label>
          <input type="number" value={form.final_price} onChange={(e) => setForm({...form, final_price: e.target.value})} className="input font-mono-num" data-testid="s-price" /></div>
        <div><label className="label">Booking amount paid</label>
          <input type="number" value={form.booking_amount} onChange={(e) => setForm({...form, booking_amount: e.target.value})} className="input font-mono-num" data-testid="s-booking" /></div>
        <div className="bg-surfacealt border border-agborder rounded-sm p-3 flex flex-col justify-center">
          <div className="overline">Remainder to schedule</div>
          <div className="font-display text-xl font-bold font-mono-num text-ink mt-1">{inr(remainder)}</div>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex justify-between items-center mb-2">
          <div className="overline text-ink">Payment schedule</div>
          <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="s-add-row"><Plus className="w-3.5 h-3.5" /> Add row</button>
        </div>
        <div className="border border-agborder rounded-sm overflow-hidden">
          <table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-agborder">
              <th className="th py-2">#</th><th className="th py-2">Due date</th><th className="th py-2 text-right">Amount</th><th className="th py-2">Notes</th><th></th>
            </tr></thead>
            <tbody>
              {schedule.map((r, i) => (
                <tr key={i} className="border-b border-agborder last:border-0">
                  <td className="px-3 py-2 text-ink2 font-mono-num text-sm">{i+1}</td>
                  <td className="px-3 py-2"><input type="date" value={r.due_date} onChange={(e) => updRow(i, { due_date: e.target.value })} className="input font-mono-num" data-testid={`s-row-date-${i}`} /></td>
                  <td className="px-3 py-2"><input type="number" value={r.amount} onChange={(e) => updRow(i, { amount: e.target.value })} className="input text-right font-mono-num" data-testid={`s-row-amt-${i}`} /></td>
                  <td className="px-3 py-2"><input value={r.notes} onChange={(e) => updRow(i, { notes: e.target.value })} className="input" placeholder="Optional" /></td>
                  <td className="px-3 py-2">{schedule.length > 1 && <button onClick={() => removeRow(i)} className="text-bad" title="Remove"><Trash2 className="w-4 h-4" /></button>}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className={matches ? "bg-ok/[0.08]" : "bg-bad/[0.08]"}>
                <td colSpan={2} className={`px-3 py-2.5 text-sm font-semibold ${matches ? "text-ok" : "text-bad"}`}>
                  Schedule total {matches ? "· matches ✓" : `· off by ${inr(Math.abs(diff))}`}
                </td>
                <td className="px-3 py-2.5 text-right font-mono-num font-bold">{inr(scheduleTotal)}</td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </Modal>
  );
}
