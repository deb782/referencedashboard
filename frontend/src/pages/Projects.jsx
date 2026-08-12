import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Building2, MapPin, Home, IndianRupee, Check } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, EmptyState, Modal, inr } from "@/components/ui";
const emptyForm = { name: "", location: "", kind: "", site_manager_id: "" };

export default function Projects() {
  const { user } = useAuth();
  const readOnly = user?.role === "management";
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [counts, setCounts] = useState({});
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [p, d] = await Promise.all([api.get("/projects"), api.get("/dashboard")]);
    setRows(p.data);
    try { const u = await api.get("/users"); setUsers(u.data); } catch { setUsers([]); }
    const map = {};
    (d.data?.by_project || []).forEach(bp => { map[bp.project_id] = bp; });
    setCounts(map);
  };
  useEffect(() => { load(); }, []);

  const siteManagers = users.filter(u => u.role === "site_manager");
  const admins = users.filter(u => u.role === "admin");
  const postSales = users.filter(u => u.role === "post_sales");

  const save = async () => {
    if (!form.name.trim()) return toast.error("Project name is required");
    try {
      await api.post("/projects", { ...form, site_manager_id: form.site_manager_id || null });
      toast.success("Project created");
      setShowForm(false); setForm(emptyForm); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete project "${p.name}" and all its units?`)) return;
    try { await api.delete(`/projects/${p.project_id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div data-testid="projects-page">
      <PageHeader overline="Portfolio" title="Projects" subtitle="Set each project's sale rate and see who's catering to its inventory.">
        {!readOnly && (
          <button onClick={() => setShowForm(true)} className="btn-primary" data-testid="new-project-btn">
            <Plus className="w-4 h-4" /> New project
          </button>
        )}
      </PageHeader>

      {rows.length === 0 ? (
        <div className="card"><EmptyState icon={Building2} title="No projects yet" hint="Create your first project to start uploading units." /></div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {rows.map((p, i) => (
            <ProjectCard key={p.project_id} p={p} idx={i} count={counts[p.project_id]}
              admins={admins} postSales={postSales} onDelete={remove} onSaved={load} readOnly={readOnly} />
          ))}
        </div>
      )}

      {showForm && (
        <Modal title="New project" subtitle="Assign a site manager if you have one." onClose={() => setShowForm(false)}
          footer={<>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            <button onClick={save} className="btn-primary" data-testid="proj-save">Create project</button>
          </>}>
          <div className="space-y-4">
            <div><label className="label">Name *</label>
              <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="proj-name" placeholder="e.g. Central Vista Farms" /></div>
            <div><label className="label">Project type</label>
              <input value={form.kind} onChange={(e) => setForm({...form, kind: e.target.value})} className="input" data-testid="proj-kind" placeholder="e.g. Agricultural Plots / Residential" /></div>
            <div><label className="label"><MapPin className="w-3 h-3 inline mr-1" />Location</label>
              <input value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} className="input" /></div>
            <div><label className="label">Site Manager</label>
              <select value={form.site_manager_id} onChange={(e) => setForm({...form, site_manager_id: e.target.value})} className="input" data-testid="proj-sm">
                <option value="">— none —</option>
                {siteManagers.map(sm => <option key={sm.user_id} value={sm.user_id}>{sm.name} ({sm.phone})</option>)}
              </select>
              {siteManagers.length === 0 && <div className="text-xs text-warn mt-1.5">Add a Site Manager under Team first.</div>}
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ProjectCard({ p, idx, count, admins, postSales, onDelete, onSaved }) {
  const [rate, setRate] = useState(p.rate_per_sqft || 0);
  const [busy, setBusy] = useState(false);
  const dirty = Number(rate) !== Number(p.rate_per_sqft || 0);

  const saveRate = async () => {
    setBusy(true);
    try {
      await api.patch(`/projects/${p.project_id}/rate`, { rate_per_sqft: Number(rate) || 0 });
      toast.success("Rate updated");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  const total = count?.total_units ?? 0;
  const sold = count?.sold ?? 0;

  return (
    <div className={`card overflow-hidden ag-rise ag-rise-${idx + 1}`} data-testid={`project-card-${p.project_id}`}>
      <div className="flex items-start justify-between px-6 py-5 border-b border-agborder bg-surfacealt/40">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-brand" />
            <div className="font-display text-2xl font-bold text-ink tracking-tight">{p.name}</div>
          </div>
          <div className="text-xs text-ink2 mt-1">
            {p.kind || "Project"}{p.location ? ` · ${p.location}` : ""}
          </div>
        </div>
        <button onClick={() => onDelete(p)} className={`text-ink2 hover:text-bad transition-colors duration-200 ${readOnly ? "hidden" : ""}`} title="Delete project" data-testid={`del-project-${p.project_id}`}>
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* Rate per sqft */}
        <div>
          <label className="label flex items-center gap-1"><IndianRupee className="w-3 h-3" /> Sale rate (per sq.ft)</label>
          <div className="flex items-center gap-2 mt-1">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink2 text-sm">₹</span>
              <input type="number" min="0" value={rate} onChange={(e) => setRate(e.target.value)} disabled={readOnly}
                className="input font-mono-num pl-7 disabled:opacity-60" data-testid={`rate-input-${p.project_id}`} placeholder="0" />
            </div>
            {!readOnly && (
              <button onClick={saveRate} disabled={busy || !dirty}
                className="btn-primary text-xs py-2 disabled:opacity-40 disabled:cursor-not-allowed" data-testid={`rate-save-${p.project_id}`}>
                {busy ? "Saving…" : <><Check className="w-3.5 h-3.5" /> Save</>}
              </button>
            )}
          </div>
          <div className="text-[11px] text-ink2 mt-1.5">Per-sq.ft rate used for this project's inventory pricing.</div>
        </div>

        {/* Inventory glance */}
        <div className="grid grid-cols-2 gap-3">
          <Stat icon={Home} label="Total plots" value={total} />
          <Stat icon={Home} label="Sold" value={`${sold}/${total}`} tone="text-brand" />
        </div>

        {/* Team catering */}
        <div>
          <div className="overline text-ink mb-2">Catering to this inventory</div>
          <TeamRow label="Admin" people={admins} tone="#5a6b10" testid={`admins-${p.project_id}`} />
          <TeamRow label="Process Admin" people={postSales} tone="#a8763f" testid={`process-${p.project_id}`} />
        </div>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, tone = "text-ink" }) {
  return (
    <div className="bg-white border border-agborder rounded-md px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-ink2 font-bold">
        <Icon className="w-3 h-3" /> {label}
      </div>
      <div className={`font-mono-num font-bold text-lg mt-0.5 ${tone}`}>{value}</div>
    </div>
  );
}

function TeamRow({ label, people, tone, testid }) {
  return (
    <div className="flex items-start gap-2 py-1.5" data-testid={testid}>
      <div className="text-xs font-semibold text-ink2 w-28 shrink-0 pt-0.5">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {people.length === 0 ? <span className="text-xs text-ink2">—</span> :
          people.map(u => (
            <span key={u.user_id} className="pill text-xs"
              style={{ color: tone, backgroundColor: `${tone}12`, borderColor: `${tone}26` }}>
              {u.name}
            </span>
          ))}
      </div>
    </div>
  );
}
