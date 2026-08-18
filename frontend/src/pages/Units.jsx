import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload, HandCoins, Plus, Home, Pencil, X, Check, Trash2, FileText, Calculator } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { EmptyState, Modal, inr, num2, ProjectSwitch, projectLogo } from "@/components/ui";
import { ReportViewer } from "@/components/ReportViewer";

const STATUS = {
  available: { dot: "#5a6b10", label: "Available" },
  sold: { dot: "#a8763f", label: "Sold" },
  booked: { dot: "#c8912f", label: "Booked" },
};

const TAG_OPTIONS = [
  { v: "plot_id", label: "Plot ID" },
  { v: "area", label: "Area" },
  { v: "charge", label: "Charge (summed)" },
  { v: "total", label: "Net Payable / Total" },
  { v: "reference", label: "Reference only" },
  { v: "ignore", label: "Ignore" },
];

export default function Units() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [sel, setSel] = useState(null);

  useEffect(() => { api.get("/projects").then(r => { setProjects(r.data); setSel(r.data[0]?.project_id || null); }); }, []);

  const active = projects.find(p => p.project_id === sel);

  return (
    <div data-testid="units-page" className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">Plot Inventory</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">Units</h1>
          <p className="text-sm text-ink2 mt-3 max-w-xl">A live map of every plot across your projects — availability, extent and the premiums that apply.</p>
        </div>
        {projects.length > 1 && <ProjectSwitch projects={projects} value={sel} onChange={setSel} />}
      </header>
      {active
        ? <ProjectInventory key={active.project_id} project={active} user={user} />
        : <div className="panel"><EmptyState icon={Home} title="No projects" hint="Create a project first." /></div>}
    </div>
  );
}

function ProjectInventory({ project, user }) {
  const [units, setUnits] = useState([]);
  const [cols, setCols] = useState(project.columns || []);
  const [wizard, setWizard] = useState(false);
  const [plotDlg, setPlotDlg] = useState(null);
  const [sellFor, setSellFor] = useState(null);
  const [cancelFor, setCancelFor] = useState(null);
  const [reportFor, setReportFor] = useState(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);

  const recomputeTotals = async () => {
    if (!window.confirm(`Recompute the Grand Total of every plot in ${project.name} by summing its component charges? This overwrites any hand-typed total.`)) return;
    setRecomputing(true);
    try {
      const r = await api.post(`/projects/${project.project_id}/recompute-totals`);
      const { updated, changed } = r.data;
      toast.success(`Recomputed ${updated} plot(s)${changed ? ` · ${changed} total(s) corrected` : " · all were already correct"}`);
      load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setRecomputing(false); }
  };

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/units", { params: { project_id: project.project_id } });
      setUnits(r.data);
      const pr = await api.get("/projects");
      const fresh = pr.data.find(x => x.project_id === project.project_id);
      if (fresh) setCols(fresh.columns || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [project.project_id]);

  const extentCol = cols.find(c => c.tag === "area");
  const plcCols = cols.filter(c => c.tag === "charge" && /plc/i.test(c.label));
  const available = units.filter(u => u.status === "available").length;
  const sold = units.filter(u => u.status === "sold").length;
  const booked = units.filter(u => u.status === "booked").length;
  const total = units.length || 1;

  const extentOf = (u) => (u.area && u.area > 0) ? u.area : (extentCol ? Number(u.data?.[extentCol.key] || 0) : 0);
  const applicablePlcs = (u) => plcCols.filter(c => Number(u.data?.[c.key] || 0) > 0);
  const shown = units.filter(u => filter === "all" ? true : u.status === filter);

  return (
    <section className="panel overflow-hidden ag-rise" data-testid={`project-inv-${project.project_id}`}>
      <div className="p-6 lg:p-8 border-b border-line">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              {projectLogo(project.name) && <img src={projectLogo(project.name)} alt={project.name} className="h-10 w-auto max-w-[180px] object-contain" data-testid={`project-logo-${project.project_id}`} />}
              <div className="font-display text-3xl font-medium text-ink tracking-tight">{project.name}</div>
            </div>
            <div className="text-xs text-ink2 mt-1">{project.kind || "Project"} · {units.length} plots</div>
          </div>
          {can(user, "admin", "post_sales") && (
            <div className="flex items-center gap-2">
              {can(user, "admin", "post_sales") && units.length > 0 && (
                <button onClick={recomputeTotals} disabled={recomputing} className="btn-secondary" data-testid={`recompute-${project.project_id}`}>
                  <Calculator className="w-4 h-4" /> {recomputing ? "Recomputing…" : "Recompute totals"}
                </button>
              )}
              {can(user, "admin") && (<>
                <button onClick={() => setPlotDlg({ mode: "add" })} className="btn-secondary" data-testid={`add-plot-${project.project_id}`}>
                  <Plus className="w-4 h-4" /> Add plot
                </button>
                <button onClick={() => setWizard(true)} className="btn-primary" data-testid={`upload-${project.project_id}`}>
                  <Upload className="w-4 h-4" /> Upload inventory
                </button>
              </>)}
            </div>
          )}
        </div>

        {units.length > 0 && (
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-5 lg:gap-10 lg:items-center">
            <div>
              <div className="flex h-2.5 rounded-full overflow-hidden bg-surfacealt">
                <div style={{ width: `${(available / total) * 100}%` }} className="transition-[width] duration-700" title={`${available} available`} data-bar="available" />
                <div style={{ width: `${(sold / total) * 100}%`, background: "#a8763f" }} className="transition-[width] duration-700" title={`${sold} sold`} />
                <div style={{ width: `${(booked / total) * 100}%`, background: "#c8912f" }} className="transition-[width] duration-700" title={`${booked} booked`} />
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2 mt-3">
                <Legend dot="#5a6b10" label="Available" n={available} />
                <Legend dot="#a8763f" label="Sold" n={sold} />
                {booked > 0 && <Legend dot="#c8912f" label="Booked" n={booked} />}
              </div>
            </div>
            <div className="flex gap-1.5 shrink-0">
              {["all", "available", "sold"].map(f => (
                <button key={f} onClick={() => setFilter(f)} data-testid={`filter-${project.project_id}-${f}`}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${filter === f ? "bg-plate text-white border-plate" : "border-line text-ink2 hover:bg-surfacealt"}`}>
                  {f === "all" ? "All" : STATUS[f].label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="p-5 lg:p-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5 gap-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-line bg-white p-4 h-[92px] animate-pulse">
                <div className="h-6 w-10 bg-surfacealt rounded" />
                <div className="h-3 w-16 bg-surfacealt rounded mt-4" />
              </div>
            ))}
          </div>
        </div>
      ) : units.length === 0 ? (
        <EmptyState icon={Home} title="No plots yet"
          hint={can(user, "admin") ? "Upload the inventory sheet or add a plot manually." : "Waiting for admin to upload inventory."} />
      ) : (
        <div className="p-5 lg:p-6 max-h-[74vh] overflow-y-auto">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5 gap-3">
            {shown.map(u => (
              <PlotTile key={u.unit_id} u={u} extent={extentOf(u)} plcs={applicablePlcs(u)} user={user}
                onEdit={() => setPlotDlg({ mode: "edit", unit: u })}
                onSell={() => setSellFor(u)} onCancel={() => setCancelFor(u)} onReport={() => setReportFor(u)} />
            ))}
          </div>
          {shown.length === 0 && <div className="text-sm text-ink2 py-10 text-center">No {filter} plots.</div>}
        </div>
      )}

      {wizard && <UploadWizard project={project} onClose={() => setWizard(false)} onDone={() => { setWizard(false); load(); }} />}
      {plotDlg && <PlotDialog project={{ ...project, columns: cols }} mode={plotDlg.mode} unit={plotDlg.unit}
                    onClose={() => setPlotDlg(null)} onSaved={() => { setPlotDlg(null); load(); }} />}
      {sellFor && <SellDialog unit={sellFor} columns={cols} onClose={() => setSellFor(null)} onSaved={() => { setSellFor(null); load(); }} />}
      {cancelFor && <CancelDialog unit={cancelFor} onClose={() => setCancelFor(null)} onSaved={() => { setCancelFor(null); load(); }} />}
      {reportFor && <ReportViewer unitId={reportFor.unit_id} plotNumber={reportFor.plot_number} onClose={() => setReportFor(null)} />}
    </section>
  );
}

function Legend({ dot, label, n }) {
  return (
    <span className="flex items-center gap-2 text-xs">
      <span className="w-2 h-2 rounded-full" style={{ background: dot }} />
      <span className="text-ink2">{label}</span>
      <span className="font-mono-num font-semibold text-ink">{n}</span>
    </span>
  );
}

function PlotTile({ u, extent, plcs, user, onEdit, onSell, onCancel, onReport }) {
  const st = STATUS[u.status] || STATUS.available;
  const actionable = can(user, "admin", "post_sales");
  const canReport = user && user.role !== "site_manager" && u.status === "sold";
  return (
    <div data-testid={`unit-row-${u.plot_number}`}
      className="group relative rounded-xl border border-line bg-white p-4 hover:border-ink/25 hover:shadow-[0_10px_30px_-14px_rgba(20,21,20,0.18)] transition-all duration-200">
      <span className="absolute left-0 top-4 bottom-4 w-[3px] rounded-full" style={{ background: st.dot }} />
      <div className="flex items-start justify-between pl-2">
        <div className="font-mono-num text-2xl font-semibold text-ink leading-none">{u.plot_number}</div>
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] font-semibold text-ink2 whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: st.dot }} /> {st.label}
        </span>
      </div>
      <div className="mt-3 pl-2 text-xs text-ink2">
        {extent > 0 ? <><span className="font-mono-num text-ink font-medium">{num2(extent)}</span> sq.ft</> : "—"}
      </div>
      {plcs.length > 0 && (
        <div className="mt-2 pl-2 flex flex-wrap gap-1">
          {plcs.slice(0, 2).map(c => (
            <span key={c.key} data-testid={`plc-${u.plot_number}-${c.key}`}
              className="text-[10px] px-1.5 py-0.5 rounded bg-brand/[0.07] text-brand border border-brand/15"
              title={`${c.label}: ${inr(Number(u.data?.[c.key] || 0))}`}>{c.label}</span>
          ))}
          {plcs.length > 2 && <span className="text-[10px] text-ink2 self-center" title={plcs.slice(2).map(c => c.label).join(", ")}>+{plcs.length - 2}</span>}
        </div>
      )}
      {(actionable || canReport) && (
        <div className="mt-3 pl-2 flex items-center gap-3 pt-3 border-t border-line/70">
          {actionable && (
            <button onClick={onEdit} data-testid={`edit-plot-${u.plot_number}`} className="text-ink2 hover:text-brand transition-colors duration-200" title="Edit plot">
              <Pencil className="w-4 h-4" />
            </button>
          )}
          {canReport && (
            <button onClick={onReport} data-testid={`view-report-${u.plot_number}`} className="text-ink2 hover:text-brand transition-colors duration-200" title="View payment report">
              <FileText className="w-4 h-4" />
            </button>
          )}
          {actionable && u.status === "available" && (
            <button onClick={onSell} data-testid={`sell-${u.plot_number}`} className="btn-primary text-xs py-1 px-2.5 ml-auto">
              <HandCoins className="w-3.5 h-3.5" /> Sell
            </button>
          )}
          {actionable && u.status === "sold" && can(user, "admin") && (
            <button onClick={onCancel} data-testid={`cancel-${u.plot_number}`} className="text-ink2 hover:text-bad ml-auto transition-colors duration-200" title="Cancel booking">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function UploadWizard({ project, onClose, onDone }) {
  const [step, setStep] = useState("pick");
  const [file, setFile] = useState(null);
  const [columns, setColumns] = useState([]);
  const [rowCount, setRowCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const doPreview = async (f) => {
    if (!f) return;
    setFile(f); setBusy(true);
    try {
      const fd = new FormData(); fd.append("project_id", project.project_id); fd.append("file", f);
      const r = await api.post("/units/preview", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setColumns(r.data.columns); setRowCount(r.data.row_count); setStep("map");
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  const setTag = (i, tag) => setColumns(columns.map((c, idx) => idx === i ? { ...c, tag } : c));

  const commit = async () => {
    const plotCount = columns.filter(c => c.tag === "plot_id").length;
    if (plotCount !== 1) return toast.error("Tag exactly one column as 'Plot ID'");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("project_id", project.project_id); fd.append("file", file);
      fd.append("mapping", JSON.stringify(columns));
      const r = await api.post("/units/commit", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setResult(r.data); setStep("done");
      toast.success(`Imported: ${r.data.inserted} added, ${r.data.updated} updated`);
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title={`Upload inventory — ${project.name}`}
      subtitle={step === "map" ? `${rowCount} rows detected · tag each column below` : "CSV or Excel. I'll read the columns and ask you how to use each."}
      onClose={onClose}
      footer={
        step === "map" ? <>
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={commit} disabled={busy} className="btn-primary" data-testid="wizard-commit">{busy ? "Importing…" : "Import & save mapping"}</button>
        </> : step === "done" ? <button onClick={onDone} className="btn-primary" data-testid="wizard-done">Done</button>
        : <button onClick={onClose} className="btn-secondary">Cancel</button>
      }>
      {step === "pick" && (
        <label className="flex flex-col items-center justify-center border-2 border-dashed border-agborder rounded-lg py-14 cursor-pointer hover:border-brand hover:bg-surfacealt/40 transition-colors duration-300" data-testid="wizard-drop">
          <Upload className="w-8 h-8 text-ink2 mb-3" />
          <div className="font-display font-semibold text-ink">{busy ? "Reading…" : "Choose a .xlsx or .csv file"}</div>
          <div className="text-xs text-ink2 mt-1">Its columns become this project's structure</div>
          <input type="file" accept=".xlsx,.csv" hidden onChange={(e) => doPreview(e.target.files?.[0])} data-testid="wizard-file" />
        </label>
      )}

      {step === "map" && (
        <div className="max-h-[55vh] overflow-y-auto -mx-2 px-2">
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="border-b border-agborder"><th className="th">Column</th><th className="th">Sample</th><th className="th">Use as</th></tr></thead>
            <tbody>
              {columns.map((c, i) => (
                <tr key={c.key} className="border-b border-agborder/60">
                  <td className="td font-semibold">{c.label}</td>
                  <td className="td text-ink2 text-xs">{(c.samples || []).join(", ") || "—"}</td>
                  <td className="td">
                    <select value={c.tag} onChange={(e) => setTag(i, e.target.value)} className="input py-1.5" data-testid={`map-${c.key}`}>
                      {TAG_OPTIONS.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}

      {step === "done" && result && (
        <div className="space-y-3 py-2">
          <ResultRow icon={Check} tone="text-ok" label="Plots added" value={result.inserted} />
          <ResultRow icon={Check} tone="text-brand" label="Plots updated" value={result.updated} />
          {result.skipped_sold?.length > 0 && <ResultRow icon={X} tone="text-warn" label="Skipped (already sold)" value={result.skipped_sold.length} />}
          {result.errors?.length > 0 && <div className="text-xs text-bad">{result.errors.length} row error(s): {result.errors.slice(0,3).map(e => `row ${e.row}`).join(", ")}</div>}
          <div className="text-sm text-ink2 pt-2">Saved {result.columns?.length || 0} columns as this project's structure.</div>
        </div>
      )}
    </Modal>
  );
}

function ResultRow({ icon: Icon, tone, label, value }) {
  return (
    <div className="flex items-center justify-between border border-agborder rounded-md px-4 py-2.5">
      <span className="flex items-center gap-2 text-sm text-ink"><Icon className={`w-4 h-4 ${tone}`} /> {label}</span>
      <span className="font-mono-num font-bold text-ink">{value}</span>
    </div>
  );
}

function PlotDialog({ project, mode, unit, onClose, onSaved }) {
  const cols = (project.columns || []);
  const editable = cols.filter(c => c.tag !== "plot_id" && c.tag !== "ignore");
  const chargeKeys = cols.filter(c => c.tag === "charge").map(c => c.key);
  const totalKey = (cols.find(c => c.tag === "total") || {}).key;
  const [plotNumber, setPlotNumber] = useState(unit?.plot_number || "");
  const [data, setData] = useState(() => {
    const d = {}; editable.forEach(c => { d[c.key] = unit?.data?.[c.key] ?? ""; }); return d;
  });
  const [busy, setBusy] = useState(false);

  const chargeSum = Math.round(chargeKeys.reduce((s, k) => s + Number(data[k] || 0), 0) * 100) / 100;
  useEffect(() => {
    if (totalKey && Number(data[totalKey] || 0) !== chargeSum) setData(d => ({ ...d, [totalKey]: chargeSum }));
  }, [chargeSum, totalKey]);

  const save = async () => {
    if (!plotNumber.trim()) return toast.error("Plot number is required");
    setBusy(true);
    const payload = { ...data };
    if (totalKey) payload[totalKey] = chargeSum;
    try {
      if (mode === "add") await api.post(`/projects/${project.project_id}/plots`, { plot_number: plotNumber, data: payload });
      else await api.patch(`/units/${unit.unit_id}`, { plot_number: plotNumber, data: payload });
      toast.success(mode === "add" ? "Plot added" : "Plot updated");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="lg" title={mode === "add" ? `Add plot — ${project.name}` : `Edit plot ${unit.plot_number}`}
      subtitle={cols.length === 0 ? "No column structure yet — upload a sheet first to define fields." : "Follows this project's column structure."}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="plot-save">{busy ? "Saving…" : "Save"}</button>
      </>}>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Plot number *</label>
          <input value={plotNumber} onChange={(e) => setPlotNumber(e.target.value)} className="input font-mono-num" data-testid="plot-number" /></div>
        {editable.map(c => {
          const isTotal = c.tag === "total";
          return (
            <div key={c.key}>
              <label className="label">{c.label} <span className="normal-case tracking-normal text-ink2 font-normal">({c.tag})</span>
                {isTotal && <span className="normal-case tracking-normal text-brand font-semibold ml-1">· auto-summed</span>}</label>
              <input value={isTotal ? chargeSum : data[c.key]} readOnly={isTotal}
                onChange={isTotal ? undefined : (e) => setData({ ...data, [c.key]: e.target.value })}
                className={`input ${c.tag === "reference" ? "" : "font-mono-num"} ${isTotal ? "bg-surfacealt/70 font-bold cursor-not-allowed" : ""}`}
                data-testid={`plot-field-${c.key}`} />
            </div>
          );
        })}
      </div>
    </Modal>
  );
}

function SellDialog({ unit, columns, onClose, onSaved }) {
  const [form, setForm] = useState({
    buyer_name: "", sale_date: new Date().toISOString().slice(0, 10),
    final_price: unit.total || 0, booking_amount: 0,
  });
  const [schedule, setSchedule] = useState([{ name: "", due_date: "", on_possession: false, amount: 0 }]);
  const [busy, setBusy] = useState(false);

  const comps = (columns || []).filter(c => c.tag !== "plot_id" && c.tag !== "ignore");
  const compVal = (c) => {
    const v = unit.data?.[c.key];
    if (c.tag === "reference" && typeof v === "string") return v || "—";
    if (c.tag === "area") return num2(v);
    return inr(Number(v || 0));
  };

  const addRow = () => setSchedule([...schedule, { name: "", due_date: "", on_possession: false, amount: 0 }]);
  const rmRow = (i) => setSchedule(schedule.filter((_, idx) => idx !== i));
  const updRow = (i, patch) => setSchedule(schedule.map((r, idx) => idx === i ? { ...r, ...patch } : r));
  const scheduleTotal = schedule.reduce((s, r) => s + Number(r.amount || 0), 0);

  const save = async () => {
    if (!form.sale_date) return toast.error("Sale date is required");
    // Only rows with an amount count; blank rows are ignored. Due date is optional (defaults to the sale date).
    const filled = schedule.filter(r => Number(r.amount) > 0);
    if (filled.length === 0) return toast.error("Add at least one payment row with an amount");
    setBusy(true);
    try {
      await api.post(`/units/${unit.unit_id}/sell`, {
        buyer_name: form.buyer_name, sale_date: form.sale_date,
        final_price: Number(form.final_price), booking_amount: Number(form.booking_amount),
        schedule: filled.map(r => ({
          due_date: r.on_possession ? "On Offer of Possession" : (r.due_date || form.sale_date),
          amount: Number(r.amount), notes: r.name || "",
        })),
      });
      toast.success("Sale recorded — accounts & admin notified");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title={`Book plot ${unit.plot_number}`} subtitle={`Net payable (Grand Total): ${inr(unit.total)}`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="s-submit">{busy ? "Saving…" : "Confirm sale"}</button>
      </>}>
      {/* Buyer / booking manual entry */}
      <div className="grid grid-cols-2 gap-4">
        <div><label className="label">Buyer name</label><input value={form.buyer_name} onChange={(e) => setForm({ ...form, buyer_name: e.target.value })} className="input" data-testid="s-buyer" placeholder="Buyer's name" /></div>
        <div><label className="label">Sale date *</label><input type="date" value={form.sale_date} onChange={(e) => setForm({ ...form, sale_date: e.target.value })} className="input font-mono-num" data-testid="s-date" /></div>
        <div><label className="label">Final price <span className="normal-case tracking-normal text-ink2 font-normal">(= Grand Total)</span></label><input type="number" value={form.final_price} onChange={(e) => setForm({ ...form, final_price: e.target.value })} className="input font-mono-num" data-testid="s-price" /></div>
        <div><label className="label">Booking amount</label><input type="number" value={form.booking_amount} onChange={(e) => setForm({ ...form, booking_amount: e.target.value })} className="input font-mono-num" data-testid="s-booking" /></div>
      </div>

      {/* Read-only cost breakdown captured from the plot's edit form */}
      <div className="mt-6">
        <div className="overline text-ink mb-2">Payment breakdown <span className="normal-case tracking-normal text-ink2 font-normal text-xs">— from plot details</span></div>
        {comps.length === 0 ? (
          <div className="text-xs text-ink2 border border-agborder rounded-md px-3 py-3">No cost components — upload this project's sheet or edit the plot to add them.</div>
        ) : (
          <div className="border border-agborder rounded-md overflow-hidden">
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr className="bg-surfacealt/60 border-b border-agborder">
                <th className="th py-2">Component</th><th className="th py-2 text-right">Amount</th>
              </tr></thead>
              <tbody>
                {comps.map(c => (
                  <tr key={c.key} className="border-b border-agborder last:border-0" data-testid={`s-comp-${c.key}`}>
                    <td className="td py-2 font-semibold">{c.label}{c.tag === "total" && <span className="text-[10px] text-brand ml-1 font-bold">GRAND TOTAL</span>}{c.tag === "reference" && <span className="text-[10px] text-ink2 ml-1">(ref)</span>}</td>
                    <td className={`td py-2 text-right ${c.tag === "reference" ? "text-ink2 italic" : "font-mono-num"} ${c.tag === "total" ? "font-bold" : ""}`}>{compVal(c)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          </div>
        )}
      </div>

      {/* Manual payment schedule (installments) */}
      <div className="mt-6">
        <div className="flex justify-between items-center mb-2">
          <div className="overline text-ink">Payment schedule</div>
          <button onClick={addRow} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1" data-testid="s-add-row"><Plus className="w-3.5 h-3.5" /> Add instalment</button>
        </div>
        <div className="border border-agborder rounded-md overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="bg-surfacealt/60 border-b border-agborder">
              <th className="th py-2">Instalment name</th><th className="th py-2">Due date</th><th className="th py-2 text-right">Amount</th><th></th>
            </tr></thead>
            <tbody>
              {schedule.map((r, i) => (
                <tr key={i} className="border-b border-agborder last:border-0">
                  <td className="px-3 py-2"><input value={r.name} onChange={(e) => updRow(i, { name: e.target.value })} className="input" placeholder="e.g. On agreement" data-testid={`s-name-${i}`} /></td>
                  <td className="px-3 py-2">
                    {r.on_possession ? (
                      <div className="text-xs font-semibold text-brand py-2">On Offer of Possession</div>
                    ) : (
                      <input type="date" value={r.due_date} onChange={(e) => updRow(i, { due_date: e.target.value })} className="input font-mono-num" data-testid={`s-row-date-${i}`} />
                    )}
                    <label className="flex items-center gap-1.5 text-[11px] text-ink2 mt-1 cursor-pointer">
                      <input type="checkbox" checked={r.on_possession} onChange={(e) => updRow(i, { on_possession: e.target.checked })} data-testid={`s-possession-${i}`} />
                      On Offer of Possession
                    </label>
                  </td>
                  <td className="px-3 py-2"><input type="number" value={r.amount} onChange={(e) => updRow(i, { amount: e.target.value })} className="input text-right font-mono-num" data-testid={`s-row-amt-${i}`} /></td>
                  <td className="px-3 py-2">{schedule.length > 1 && <button onClick={() => rmRow(i)} className="text-bad"><X className="w-4 h-4" /></button>}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr className="bg-surfacealt/40"><td colSpan={2} className="px-3 py-2.5 text-sm font-semibold text-ink">Schedule total</td><td className="px-3 py-2.5 text-right font-mono-num font-bold">{inr(scheduleTotal)}</td><td></td></tr></tfoot>
          </table></div>
        </div>
      </div>
    </Modal>
  );
}


function CancelDialog({ unit, onClose, onSaved }) {
  const [cancelDate, setCancelDate] = useState(new Date().toISOString().slice(0, 10));
  const [refunded, setRefunded] = useState(0);
  const [paid, setPaid] = useState(null);   // total received against this plot
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/payments", { params: { unit_id: unit.unit_id } })
      .then(r => setPaid(r.data.reduce((s, p) => s + Number(p.paid_amount || 0), 0)))
      .catch(() => setPaid(0));
  }, [unit.unit_id]);

  const balance = paid == null ? null : Math.round((paid - Number(refunded || 0)) * 100) / 100;

  const save = async () => {
    if (!cancelDate) return toast.error("Date of cancellation is required");
    if (Number(refunded) < 0) return toast.error("Refund cannot be negative");
    if (paid != null && Number(refunded) > paid) return toast.error(`Refund can't exceed amount paid (${inr(paid)})`);
    setBusy(true);
    try {
      await api.post(`/units/${unit.unit_id}/cancel`, {
        cancel_date: cancelDate, amount_refunded: Number(refunded || 0),
      });
      toast.success("Booking cancelled — plot is available again");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="md" title={`Cancel booking · Plot ${unit.plot_number}`}
      subtitle={unit.buyer_name ? `Buyer: ${unit.buyer_name}` : "This will free the plot and remove its payment schedule."}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Keep booking</button>
        <button onClick={save} disabled={busy} className="btn-primary" style={{ backgroundColor: "#b23b3b" }} data-testid="cancel-submit">{busy ? "Cancelling…" : "Cancel booking"}</button>
      </>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Date of cancellation *</label>
            <input type="date" value={cancelDate} onChange={(e) => setCancelDate(e.target.value)} className="input font-mono-num" data-testid="cancel-date" /></div>
          <div><label className="label">Amount refunded</label>
            <input type="number" min="0" value={refunded} onChange={(e) => setRefunded(e.target.value)} className="input font-mono-num" data-testid="cancel-refund" placeholder="0" /></div>
        </div>
        <div className="border border-agborder rounded-md divide-y divide-agborder" data-testid="cancel-summary">
          <Row label="Amount paid so far" value={paid == null ? "…" : inr(paid)} tone="text-ok" />
          <Row label="Amount refunded" value={inr(Number(refunded || 0))} tone="text-ink2" />
          <Row label="Balance retained" value={balance == null ? "…" : inr(balance)} tone="text-brand" bold />
        </div>
        <div className="text-[11px] text-ink2">The retained balance is added to this project's Total Received on the dashboard.</div>
      </div>
    </Modal>
  );
}

function Row({ label, value, tone, bold }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-sm text-ink">{label}</span>
      <span className={`font-mono-num ${bold ? "font-bold" : ""} ${tone}`}>{value}</span>
    </div>
  );
}
