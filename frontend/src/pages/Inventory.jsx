import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Pencil } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";

export default function Inventory() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(user?.project_id || "");
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", quantity: 0, unit: "pcs", notes: "" });

  const load = async () => {
    const r = await api.get("/inventory", { params: projectId ? { project_id: projectId } : {} });
    setItems(r.data);
  };
  useEffect(() => {
    api.get("/projects").then((r) => {
      setProjects(r.data);
      if (!projectId && r.data.length) setProjectId(r.data[0].project_id);
    });
  }, []);
  useEffect(() => { if (projectId) load(); }, [projectId]);

  const openNew = () => { setForm({ name: "", quantity: 0, unit: "pcs", notes: "" }); setEditing(null); setShowForm(true); };
  const openEdit = (it) => { setForm({ ...it }); setEditing(it); setShowForm(true); };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Name is required");
    try {
      if (editing) {
        await api.patch(`/inventory/${editing.item_id}`, {
          name: form.name, quantity: Number(form.quantity), unit: form.unit, notes: form.notes,
        });
      } else {
        await api.post("/inventory", { ...form, project_id: projectId, quantity: Number(form.quantity) });
      }
      toast.success("Saved");
      setShowForm(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const remove = async (it) => {
    if (!window.confirm(`Delete ${it.name}?`)) return;
    try { await api.delete(`/inventory/${it.item_id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const scoped = user?.role === "site_manager";

  return (
    <div className="space-y-6" data-testid="inventory-page">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-stone-900">Inventory</h1>
          <p className="text-sm text-stone-500 mt-1">On-site materials. Update quantities as things move in and out.</p>
        </div>
        <div className="flex items-center gap-3">
          {!scoped && (
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input w-64" data-testid="inv-proj-select">
              {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
            </select>
          )}
          {can(user, "site_manager", "admin") && (
            <button onClick={openNew} className="btn-primary" data-testid="add-item-btn">
              <Plus className="w-4 h-4 inline mr-1" /> Add item
            </button>
          )}
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
            <tr>
              <th className="text-left py-3 px-4">Item</th>
              <th className="text-right py-3 px-4">Qty</th>
              <th className="text-left py-3 px-4">Unit</th>
              <th className="text-left py-3 px-4">Notes</th>
              <th className="text-left py-3 px-4">Updated</th>
              <th className="text-right py-3 px-4">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {items.map(it => (
              <tr key={it.item_id} data-testid={`inv-row-${it.item_id}`}>
                <td className="py-3 px-4 font-medium">{it.name}</td>
                <td className="py-3 px-4 text-right tabular-nums">{it.quantity}</td>
                <td className="py-3 px-4 text-stone-600">{it.unit}</td>
                <td className="py-3 px-4 text-stone-500 text-xs">{it.notes || "—"}</td>
                <td className="py-3 px-4 text-xs text-stone-400">{(it.updated_at || "").slice(0, 10)}</td>
                <td className="py-3 px-4 text-right">
                  {can(user, "site_manager", "admin") && (
                    <>
                      <button onClick={() => openEdit(it)} className="text-stone-500 hover:text-stone-800 mr-3" title="Edit">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => remove(it)} className="text-rose-600" title="Delete">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="py-12 text-center text-stone-500">No inventory items yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowForm(false)}>
          <div className="card w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="text-lg font-bold mb-4">{editing ? "Edit item" : "New inventory item"}</div>
            <div className="space-y-3">
              <div><label className="label">Name *</label>
                <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="inv-name" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="label">Quantity</label>
                  <input type="number" value={form.quantity} onChange={(e) => setForm({...form, quantity: e.target.value})} className="input" data-testid="inv-qty" /></div>
                <div><label className="label">Unit</label>
                  <input value={form.unit} onChange={(e) => setForm({...form, unit: e.target.value})} className="input" placeholder="pcs / bags / tonnes" /></div>
              </div>
              <div><label className="label">Notes</label>
                <input value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" /></div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
              <button onClick={save} className="btn-primary" data-testid="inv-save">{editing ? "Save" : "Add"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
