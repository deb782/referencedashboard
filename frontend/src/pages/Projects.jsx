import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Building2, MapPin } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { PageHeader, EmptyState, Modal } from "@/components/ui";

const emptyForm = { name: "", location: "", kind: "", site_manager_id: "" };

export default function Projects() {
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [p, u] = await Promise.all([api.get("/projects"), api.get("/users")]);
    setRows(p.data); setUsers(u.data);
  };
  useEffect(() => { load(); }, []);

  const siteManagers = users.filter(u => u.role === "site_manager");
  const smName = (id) => siteManagers.find(u => u.user_id === id)?.name || "—";

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
      <PageHeader overline="Portfolio" title="Projects" subtitle="Create projects and assign a site manager to each.">
        <button onClick={() => setShowForm(true)} className="btn-primary" data-testid="new-project-btn">
          <Plus className="w-4 h-4" /> New project
        </button>
      </PageHeader>

      <div className="card overflow-hidden ag-rise">
        <table className="w-full">
          <thead><tr className="border-b border-agborder bg-surfacealt/50">
            <th className="th">Name</th><th className="th">Type</th><th className="th">Location</th><th className="th">Site Manager</th><th className="th">Created</th><th className="th text-right">Action</th>
          </tr></thead>
          <tbody>
            {rows.map(p => (
              <tr key={p.project_id} className="row" data-testid={`project-row-${p.project_id}`}>
                <td className="td font-semibold">{p.name}</td>
                <td className="td text-ink2">{p.kind || "—"}</td>
                <td className="td text-ink2">{p.location || "—"}</td>
                <td className="td text-ink2">{smName(p.site_manager_id)}</td>
                <td className="td text-ink2 font-mono-num text-xs">{(p.created_at || "").slice(0,10)}</td>
                <td className="td text-right">
                  <button onClick={() => remove(p)} className="text-ink2 hover:text-bad transition-colors duration-200" title="Delete" data-testid={`del-project-${p.project_id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6}><EmptyState icon={Building2} title="No projects yet" hint="Create your first project to start uploading units." /></td></tr>}
          </tbody>
        </table>
      </div>

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
