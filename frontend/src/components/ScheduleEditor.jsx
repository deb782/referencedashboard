import { useState } from "react";
import { toast } from "sonner";
import { XCircle, Plus } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { inr, Modal } from "@/components/ui";

const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;

// Full payment-plan editor: edit/add/remove any instalment. Editing an instalment
// that already has receipts triggers an Accounts re-approval (a Schedule Revision).
export function ScheduleEditor({ unitId, plotNumber, rows, grandTotal, onClose, onSaved }) {
  const [items, setItems] = useState(() => rows.map(r => ({
    payment_id: r.payment_id,
    name: r.notes || "",
    on_possession: r.due_date === "On Offer of Possession",
    due_date: r.due_date === "On Offer of Possession" ? "" : (r.due_date || ""),
    amount: Number(r.amount || 0),
    verified: Number(r.paid_amount || 0),
    has_receipts: (r.receipts || []).length > 0,
  })));
  const [busy, setBusy] = useState(false);

  const upd = (i, patch) => setItems(items.map((it, idx) => idx === i ? { ...it, ...patch } : it));
  const addRow = () => setItems([...items, { payment_id: null, name: "", on_possession: false, due_date: "", amount: 0, verified: 0, has_receipts: false }]);
  const rmRow = (i) => setItems(items.filter((_, idx) => idx !== i));
  const total = round2(items.reduce((s, it) => s + Number(it.amount || 0), 0));
  const gap = round2(total - Number(grandTotal || 0));
  const matches = Math.abs(gap) < 1;
  const touchesPaid = items.some(it => it.has_receipts);

  // Snap this instalment so the schedule total equals the Grand Total.
  const fitHere = (i) => {
    const it = items[i];
    const newAmt = round2(Number(it.amount || 0) - gap);
    if (it.payment_id && newAmt < it.verified - 0.01)
      return toast.error(`Can't fit onto "${it.name || 'this instalment'}" — it already has ${inr(it.verified)} verified. Pick another instalment.`);
    if (newAmt <= 0)
      return toast.error(`Fitting onto "${it.name || 'this instalment'}" would make it ${inr(newAmt)}. Pick another instalment.`);
    upd(i, { amount: newAmt });
    toast.success("Snapped to Grand Total");
  };

  const save = async () => {
    if (items.length === 0) return toast.error("Add at least one instalment");
    for (const it of items) {
      if (!(Number(it.amount) > 0)) return toast.error("Each instalment needs an amount greater than zero");
      if (it.payment_id && Number(it.amount) < it.verified - 0.01) return toast.error(`"${it.name || 'Instalment'}" already has ${inr(it.verified)} verified — its amount can't be below that`);
    }
    if (grandTotal > 0 && !matches) return toast.error(`Instalments (${inr(total)}) must add up to the Grand Total (${inr(grandTotal)})`);
    setBusy(true);
    try {
      const r = await api.put(`/units/${unitId}/schedule`, {
        installments: items.map(it => ({
          payment_id: it.payment_id || null,
          due_date: it.on_possession ? "On Offer of Possession" : (it.due_date || new Date().toISOString().slice(0, 10)),
          amount: Number(it.amount), notes: it.name || "",
        })),
      });
      if (r.data?.revision_raised) toast.success("Schedule updated · sent to Accounts to recheck & approve");
      else toast.success("Schedule updated");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="xl" title={`Edit payment plan · Plot ${plotNumber}`}
      subtitle="Restructure the whole instalment plan — add, remove or edit any row. Instalments must add up to the Grand Total, a paid instalment can't drop below what's already verified, and one with recorded receipts can't be removed. Editing a paid instalment notifies Accounts to recheck & approve."
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy || (grandTotal > 0 && !matches)} className="btn-primary" data-testid="schedule-save">{busy ? "Saving…" : "Save plan"}</button>
      </>}>
      {touchesPaid && (
        <div className="mb-3 text-[11px] text-warn bg-warn/5 border border-warn/30 rounded-md px-3 py-2" data-testid="sched-paid-warning">
          This plan has paid instalments. Any change to a paid row is sent to Accounts to recheck &amp; approve.
        </div>
      )}
      <div className="space-y-2">
        <div className="grid grid-cols-12 gap-2 px-2 text-[10px] uppercase tracking-[0.12em] text-ink2 font-semibold">
          <div className="col-span-4">Instalment</div><div className="col-span-3">Due</div><div className="col-span-4 text-right">Amount</div><div className="col-span-1" />
        </div>
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-center border border-line rounded-md p-2" data-testid={`sched-row-${i}`}>
            <div className="col-span-4">
              <input value={it.name} onChange={(e) => upd(i, { name: e.target.value })} placeholder="Instalment name" className="input w-full" data-testid={`sched-name-${i}`} />
              {it.has_receipts && <div className="text-[9px] uppercase tracking-wide text-warn font-semibold mt-0.5">Paid · needs re-approval</div>}
            </div>
            <div className="col-span-3 flex items-center gap-2">
              {it.on_possession
                ? <span className="text-xs text-ink2 italic flex-1">On Offer of Possession</span>
                : <input type="date" value={it.due_date} onChange={(e) => upd(i, { due_date: e.target.value })} className="input font-mono-num flex-1" data-testid={`sched-due-${i}`} />}
              <label className="flex items-center gap-1 text-[10px] text-ink2 cursor-pointer whitespace-nowrap" title="On Offer of Possession">
                <input type="checkbox" checked={it.on_possession} onChange={(e) => upd(i, { on_possession: e.target.checked })} data-testid={`sched-poss-${i}`} /> Poss.
              </label>
            </div>
            <div className="col-span-4">
              <input type="number" value={it.amount} onChange={(e) => upd(i, { amount: e.target.value })}
                className={`input text-right font-mono-num ${it.payment_id && Number(it.amount) < it.verified - 0.01 ? "border-bad" : ""}`} data-testid={`sched-amount-${i}`} />
              {it.verified > 0 && <div className="text-[10px] text-ink2 mt-0.5 text-right">min {inr(it.verified)} verified</div>}
              {grandTotal > 0 && !matches && (
                <button type="button" onClick={() => fitHere(i)}
                  className="text-[10px] text-brand font-semibold hover:underline mt-0.5 block ml-auto" data-testid={`sched-fit-${i}`}>
                  Fit here (→ {inr(round2(Number(it.amount || 0) - gap))})
                </button>
              )}
            </div>
            <div className="col-span-1 text-right">
              <button onClick={() => rmRow(i)} disabled={it.has_receipts}
                title={it.has_receipts ? "Has receipts — cannot remove" : "Remove"}
                className={`text-bad ${it.has_receipts ? "opacity-30 cursor-not-allowed" : "hover:opacity-70"}`} data-testid={`sched-remove-${i}`}>
                <XCircle className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
        <button onClick={addRow} className="btn-secondary text-xs" data-testid="sched-add"><Plus className="w-3.5 h-3.5" /> Add instalment</button>
        <div className="flex items-center justify-between border-t border-line pt-3 mt-2 text-sm">
          <span className="text-ink2">Schedule total <span className="text-ink2">· must equal Grand Total {inr(grandTotal)}</span></span>
          <div className="text-right">
            <span className={`font-mono-num font-bold ${matches ? "text-ok" : "text-bad"}`} data-testid="sched-total">{inr(total)}</span>
            <div className={`text-[11px] font-mono-num ${matches ? "text-ok" : "text-bad"}`} data-testid="sched-gap">
              {matches ? "Matches Grand Total ✓" : `${gap > 0 ? "Over" : "Under"} Grand Total by ${inr(Math.abs(gap))} — adjust to save`}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
