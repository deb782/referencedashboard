import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, KeyRound, Trash2, Users as UsersIcon } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/auth";
import { PageHeader, StatusPill, EmptyState, Modal } from "@/components/ui";

const emptyForm = { name: "", phone: "", email: "", role: "post_sales", project_id: "" };

export default function Users() {
  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [u, p] = await Promise.all([api.get("/users"), api.get("/projects")]);
    setRows(u.data); setProjects(p.data);
  };
  useEffect(() => { load(); }, []);

  const projName = (id) => projects.find(p => p.project_id === id)?.name || "—";

  const save = async () => {
    if (!form.name.trim() || !form.phone.trim()) return toast.error("Name and phone are required");
    if (form.role === "site_manager" && !form.project_id) return toast.error("Site manager needs a project");
    try {
      await api.post("/users", { ...form, project_id: form.project_id || null, email: form.email || null });
      toast.success(`Team member added. Initial password = phone: ${form.phone}`);
      setShowForm(false); setForm(emptyForm); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const resetPw = async (u) => {
    if (!window.confirm(`Reset password for ${u.name} to their phone number?`)) return;
    try { await api.post(`/users/${u.user_id}/reset-password`); toast.success(`Password reset to ${u.phone}`); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.name}?`)) return;
    try { await api.delete(`/users/${u.user_id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const roleTone = { admin: "brand", accounts: "clay", post_sales: "moss", site_manager: "ink" };

  return (
    <div data-testid="users-page">
      <PageHeader overline="Access" title="Team" subtitle="Initial password is the phone number; each user resets on first login.">
        <button onClick={() => setShowForm(true)} className="btn-primary" data-testid="new-user-btn">
          <Plus className="w-4 h-4" /> Add member
        </button>
      </PageHeader>

      <div className="card overflow-hidden ag-rise">
        <table className="w-full">
          <thead><tr className="border-b border-agborder bg-surfacealt/50">
            <th className="th">Name</th><th className="th">Phone</th><th className="th">Role</th><th className="th">Project</th><th className="th">First login</th><th className="th text-right">Action</th>
          </tr></thead>
          <tbody>
            {rows.map(u => (
              <tr key={u.user_id} className="row" data-testid={`user-row-${u.user_id}`}>
                <td className="td font-semibold">{u.name}</td>
                <td className="td text-ink2 font-mono-num">{u.phone}</td>
                <td className="td"><span className="pill" style={{ color: "#5a6b10", backgroundColor: "#5a6b1010", borderColor: "#5a6b1022" }}>{ROLE_LABELS[u.role]}</span></td>
                <td className="td text-ink2">{u.role === "site_manager" ? projName(u.project_id) : "—"}</td>
                <td className="td">{u.must_reset_password ? <StatusPill status="pending" label="Awaiting" /> : <StatusPill status="received" label="Done" />}</td>
                <td className="td text-right whitespace-nowrap">
                  <button onClick={() => resetPw(u)} className="text-ink2 hover:text-brand transition-colors duration-200 mr-4" title="Reset password to phone" data-testid={`reset-pw-${u.user_id}`}>
                    <KeyRound className="w-4 h-4" />
                  </button>
                  <button onClick={() => remove(u)} className="text-ink2 hover:text-bad transition-colors duration-200" title="Delete" data-testid={`del-user-${u.user_id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6}><EmptyState icon={UsersIcon} title="No team members yet" hint="Add your accounts, post-sales and site-manager users." /></td></tr>}
          </tbody>
        </table>
      </div>

      {showForm && (
        <Modal title="Add team member" subtitle="They'll sign in with their phone as the initial password." onClose={() => setShowForm(false)}
          footer={<>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            <button onClick={save} className="btn-primary" data-testid="u-save">Add member</button>
          </>}>
          <div className="space-y-4">
            <div><label className="label">Name *</label>
              <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="u-name" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Phone * (initial password)</label>
                <input value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} className="input font-mono-num" data-testid="u-phone" /></div>
              <div><label className="label">Email (optional)</label>
                <input value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} className="input" /></div>
            </div>
            <div><label className="label">Role *</label>
              <select value={form.role} onChange={(e) => setForm({...form, role: e.target.value, project_id: ""})} className="input" data-testid="u-role">
                <option value="admin">Admin</option>
                <option value="accounts">Accounts</option>
                <option value="post_sales">Post-Sales Rep</option>
                <option value="site_manager">Site Manager</option>
              </select></div>
            {form.role === "site_manager" && (
              <div><label className="label">Assign to project *</label>
                <select value={form.project_id} onChange={(e) => setForm({...form, project_id: e.target.value})} className="input" data-testid="u-proj">
                  <option value="">— pick a project —</option>
                  {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
                </select></div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
