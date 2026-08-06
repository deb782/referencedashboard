import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, apiError } from "@/lib/api";

const emptyForm = { name: "", location: "", site_manager_id: "" };

export default function Projects() {
  const [rows, setRows] = useState([]);
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [p, u] = await Promise.all([api.get("/projects"), api.get("/users")]);
    setRows(p.data);
    setUsers(u.data);
  };
  useEffect(() => { load(); }, []);

  const siteManagers = users.filter(u => u.role === "site_manager");
  const smName = (id) => siteManagers.find(u => u.user_id === id)?.name || "—";

  const save = async () => {
    if (!form.name.trim()) return toast.error("Project name is required");
    try {
      const payload = { ...form, site_manager_id: form.site_manager_id || null };
      await api.post("/projects", payload);
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
    <div className="space-y-6" data-testid="projects-page">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Projects</h1>
          <p className="text-sm text-stone-500 mt-1">Create projects and assign a site manager to each.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary" data-testid="new-project-btn">
          <Plus className="w-4 h-4 inline mr-1" /> New project
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
            <tr>
              <th className="text-left py-3 px-4">Name</th>
              <th className="text-left py-3 px-4">Location</th>
              <th className="text-left py-3 px-4">Site Manager</th>
              <th className="text-left py-3 px-4">Created</th>
              <th className="text-right py-3 px-4">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {rows.map(p => (
              <tr key={p.project_id} data-testid={`project-row-${p.project_id}`}>
                <td className="py-3 px-4 font-medium">{p.name}</td>
                <td className="py-3 px-4 text-stone-600">{p.location || "—"}</td>
                <td className="py-3 px-4 text-stone-600">{smName(p.site_manager_id)}</td>
                <td className="py-3 px-4 text-xs text-stone-400">{(p.created_at || "").slice(0,10)}</td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => remove(p)} className="text-rose-600 hover:text-rose-700" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="py-12 text-center text-stone-500">No projects yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowForm(false)}>
          <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-bold mb-4">New project</div>
            <div className="space-y-3">
              <div>
                <label className="label">Name *</label>
                <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="proj-name" />
              </div>
              <div>
                <label className="label">Location</label>
                <input value={form.location} onChange={(e) => setForm({...form, location: e.target.value})} className="input" />
              </div>
              <div>
                <label className="label">Site Manager</label>
                <select value={form.site_manager_id} onChange={(e) => setForm({...form, site_manager_id: e.target.value})} className="input" data-testid="proj-sm">
                  <option value="">— none —</option>
                  {siteManagers.map(sm => <option key={sm.user_id} value={sm.user_id}>{sm.name} ({sm.phone})</option>)}
                </select>
                {siteManagers.length === 0 && (
                  <div className="text-xs text-amber-700 mt-1">Add a Site Manager under Team first.</div>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
              <button onClick={save} className="btn-primary" data-testid="proj-save">Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
