import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, Boxes } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { PageHeader, EmptyState, Modal } from "@/components/ui";

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
        await api.patch(`/inventory/${editing.item_id}`, { name: form.name, quantity: Number(form.quantity), unit: form.unit, notes: form.notes });
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
    <div data-testid="inventory-page">
      <PageHeader overline="On-site Materials" title="Inventory" subtitle="Update quantities as materials move in and out. Low stock (≤10) shows in clay.">
        {!scoped && (
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input w-60" data-testid="inv-proj-select">
            {projects.map(p => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </select>
        )}
        {can(user, "site_manager", "admin") && (
          <button onClick={openNew} className="btn-primary" data-testid="add-item-btn"><Plus className="w-4 h-4" /> Add item</button>
        )}
      </PageHeader>

      <div className="card overflow-hidden ag-rise">
        <table className="w-full">
          <thead><tr className="border-b border-agborder bg-surfacealt/50">
            <th className="th">Item</th><th className="th text-right">Qty</th><th className="th">Unit</th><th className="th">Notes</th><th className="th">Updated</th><th className="th text-right">Action</th>
          </tr></thead>
          <tbody>
            {items.map(it => {
              const low = (Number(it.quantity) || 0) <= 10;
              return (
                <tr key={it.item_id} className="row" data-testid={`inv-row-${it.item_id}`}>
                  <td className="td font-semibold">{it.name}</td>
                  <td className={`td text-right font-mono-num font-semibold ${low ? "text-clay" : ""}`}>{it.quantity}</td>
                  <td className="td text-ink2">{it.unit}</td>
                  <td className="td text-ink2 text-xs">{it.notes || "—"}</td>
                  <td className="td text-ink2 font-mono-num text-xs">{(it.updated_at || "").slice(0, 10)}</td>
                  <td className="td text-right whitespace-nowrap">
                    {can(user, "site_manager", "admin") && (
                      <>
                        <button onClick={() => openEdit(it)} className="text-ink2 hover:text-brand transition-colors duration-200 mr-4" title="Edit" data-testid={`edit-inv-${it.item_id}`}><Pencil className="w-4 h-4" /></button>
                        <button onClick={() => remove(it)} className="text-ink2 hover:text-bad transition-colors duration-200" title="Delete" data-testid={`del-inv-${it.item_id}`}><Trash2 className="w-4 h-4" /></button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && <tr><td colSpan={6}><EmptyState icon={Boxes} title="No inventory items yet" hint="Add materials to start tracking on-site stock." /></td></tr>}
          </tbody>
        </table>
      </div>

      {showForm && (
        <Modal title={editing ? "Edit item" : "New inventory item"} onClose={() => setShowForm(false)}
          footer={<>
            <button onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            <button onClick={save} className="btn-primary" data-testid="inv-save">{editing ? "Save changes" : "Add item"}</button>
          </>}>
          <div className="space-y-4">
            <div><label className="label">Name *</label>
              <input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} className="input" data-testid="inv-name" /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Quantity</label>
                <input type="number" value={form.quantity} onChange={(e) => setForm({...form, quantity: e.target.value})} className="input font-mono-num" data-testid="inv-qty" /></div>
              <div><label className="label">Unit</label>
                <input value={form.unit} onChange={(e) => setForm({...form, unit: e.target.value})} className="input" placeholder="pcs / bags / tonnes" /></div>
            </div>
            <div><label className="label">Notes</label>
              <input value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} className="input" /></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
