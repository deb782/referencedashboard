import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, KeyRound, Trash2 } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/auth";

const emptyForm = { name: "", phone: "", email: "", role: "post_sales", project_id: "" };

export default function Users() {
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [u, p] = await Promise.all([api.get("/users"), api.get("/projects")]);
    setRows(u.data);
    setProjects(p.data);
  };
  useEffect(() => { load(); }, []);

  const projName = (id) => projects.find(p => p.project_id === id)?.name || "—";

  const save = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Name and phone are required");
    if (form.role === "site_manager" && !form.project_id) return toast.error("Site manager needs a project");
    try {
      const payload = { ...form, project_id: form.project_id || null, email: form.email || null };
      await api.post("/users", payload);
      toast.success(`Team member added. Initial password = phone number: ${form.phone}`);
      setShowForm(false); setForm(emptyForm); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const resetPw = async (u) => {
    if (!window.confirm(`Reset password for ${u.name} to their phone number?`)) return;
    try { await api.post(`/users/${u.user_id}/reset-password`); toast.success(`Password reset to ${u.phone}`); }
    catch (e) { toast.error(apiError(e)); }
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.name}?`)) return;
    try { await api.delete(`/users/${u.user_id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Team</h1>
          <p className="text-sm text-stone-500 mt-1">Add users. Initial password is the phone number; each user resets on first login.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary" data-testid="new-user-btn">
          <Plus className="w-4 h-4 inline mr-1" /> Add member
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
            <tr>
              <th className="text-left py-3 px-4">Name</th>
              <th className="text-left py-3 px-4">Phone</th>
              <th className="text-left py-3 px-4">Role</th>
              <th className="text-left py-3 px-4">Project</th>
              <th className="text-left py-3 px-4">First login done?</th>
              <th className="text-right py-3 px-4">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {rows.map(u => (
              <tr key={u.user_id} data-testid={`user-row-${u.user_id}`}>
                <td className="py-3 px-4 font-medium">{u.name}</td>
                <td className="py-3 px-4 text-stone-600">{u.phone}</td>
                <td className="py-3 px-4">
                  <span className="pill bg-stone-50 border-stone-200 text-stone-700">{ROLE_LABELS[u.role]}</span>
                </td>
                <td className="py-3 px-4 text-stone-600">{u.role === "site_manager" ? projName(u.project_id) : "—"}</td>
                <td className="py-3 px-4 text-xs">
                  {u.must_reset_password
                    ? <span className="pill bg-amber-50 border-amber-200 text-amber-800">Awaiting first login</span>
                    : <span className="pill bg-emerald-50 border-emerald-200 text-emerald-800">Done</span>}
                </td>
                <td className="py-3 px-4 text-right">
                  <button onClick={() => resetPw(u)} className="text-stone-500 hover:text-stone-800 mr-3" title="Reset password to phone">
                    <KeyRound className="w-4 h-4" />
                  </button>
                  <button onClick={() => remove(u)} className="text-rose-600 hover:text-rose-700" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="py-12 text-center text-stone-500">No team members yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowForm(false)}>
          <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-bold mb-4">Add team member</div>
            <div className="space-y-3">
              <div><label className="label">Name *</label>
                <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="u-name" /></div>
              <div><label className="label">Phone * (initial password)</label>
                <input value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} className="input" data-testid="u-phone" /></div>
              <div><label className="label">Email (optional)</label>
                <input value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className="input" /></div>
              <div><label className="label">Role *</label>
                <select value={form.role} onChange={(e) => setForm({...form, role: e.target.value, project_id: ""})} className="input" data-testid="u-role">
                  <option value="admin">Admin</option>
                  <option value="accounts">Accounts</option>
                  <option value="post_sales">Post-Sales Rep</option>
                  <option value="site_manager">Site Manager</option>
                </select></div>
              {form.role === "site_manager" && (
                <div>
                  <label className="label">Assign to project *</label>
                  <select value={form.project_id} onChange={(e) => setForm({...form, project_id: e.target.value})} className="input" data-testid="u-proj">
                    <option value="">— pick a project —</option>
                    {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
                  </select>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
              <button onClick={save} className="btn-primary" data-testid="u-save">Add</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
