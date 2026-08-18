import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Scale, ChevronRight } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { inr, Modal } from "@/components/ui";

const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;

// Sold plots whose instalment schedule total ≠ the plot's Grand Total.
// Reps can Auto-Fit (snap a chosen instalment to close the gap) per row.
export function MismatchedPlots({ projectId, refresh, onOpen, onFixed }) {
  const [data, setData] = useState({ total: 0, count: 0, items: [] });
  const [open, setOpen] = useState(true);
  const [picker, setPicker] = useState(null);

  const load = () => api.get("/mismatched-plots", { params: projectId ? { project_id: projectId } : {} })
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [refresh, projectId]);

  const afterFix = () => { setPicker(null); load(); onFixed && onFixed(); };

  if (!data.count) return null;
  return (
    <div className="panel border-bad/30 bg-bad/5 overflow-hidden" data-testid="mismatched-plots">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between gap-3 px-5 py-3.5 text-left">
        <span className="flex items-center gap-2 text-bad font-semibold text-sm">
          <Scale className="w-4 h-4" />
          {data.count} booked plot(s) whose schedule doesn&rsquo;t match the Grand Total
        </span>
        <ChevronRight className={`w-4 h-4 text-ink2 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-bad/20 overflow-x-auto">
          <table className="w-full">
            <thead><tr className="bg-surfacealt/50 border-b border-line">
              <th className="th">Plot</th><th className="th">Buyer</th><th className="th">Project</th>
              <th className="th text-right">Grand Total</th><th className="th text-right">Schedule</th>
              <th className="th text-right">Difference</th><th className="th"></th>
            </tr></thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.unit_id} className="row" data-testid={`mismatch-${it.plot_number}`}>
                  <td className="td font-mono-num font-bold">{it.plot_number}</td>
                  <td className="td text-ink2">{it.buyer_name || "—"}</td>
                  <td className="td text-ink2">{it.project}</td>
                  <td className="td text-right font-mono-num">{inr(it.grand_total)}</td>
                  <td className="td text-right font-mono-num text-ink2">{inr(it.schedule_total)}</td>
                  <td className={`td text-right font-mono-num font-semibold ${it.difference > 0 ? "text-warn" : "text-bad"}`}>
                    {it.difference > 0 ? "+" : "−"}{inr(Math.abs(it.difference))}
                  </td>
                  <td className="td text-right whitespace-nowrap">
                    <button onClick={() => setPicker(it)} className="text-brand font-semibold hover:underline text-xs mr-3" data-testid={`autofit-open-${it.plot_number}`}>Auto-Fit</button>
                    {onOpen && (
                      <button onClick={() => onOpen({ unit_id: it.unit_id, plot_number: it.plot_number, buyer_name: it.buyer_name, project_id: it.project_id })}
                        className="text-ink2 font-semibold hover:underline text-xs" data-testid={`mismatch-open-${it.plot_number}`}>Open plot</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {picker && <AutoFitPicker item={picker} onClose={() => setPicker(null)} onFixed={afterFix} />}
    </div>
  );
}

function AutoFitPicker({ item, onClose, onFixed }) {
  const [pid, setPid] = useState("");
  const [busy, setBusy] = useState(false);
  const diff = round2(item.difference);
  const overUnder = diff > 0 ? "add" : "subtract";

  const resultingOf = (ins) => round2(Number(ins.amount || 0) + diff);
  const blockedOf = (ins) => resultingOf(ins) < Number(ins.verified || 0) - 0.01 || resultingOf(ins) <= 0;

  const apply = async () => {
    if (!pid) return toast.error("Pick an instalment to absorb the difference");
    setBusy(true);
    try {
      const r = await api.post(`/units/${item.unit_id}/auto-fit-schedule`, { payment_id: pid });
      toast.success(`Fitted to Grand Total · ${r.data.adjusted.notes || "instalment"} → ${inr(r.data.adjusted.new_amount)}`);
      onFixed();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="lg" title={`Auto-Fit · Plot ${item.plot_number}`}
      subtitle={`The schedule is ${diff > 0 ? "under" : "over"} the Grand Total by ${inr(Math.abs(diff))}. Pick which instalment should ${overUnder} the difference so the plan sums to ${inr(item.grand_total)}.`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={apply} disabled={busy || !pid} className="btn-primary" data-testid="autofit-apply">{busy ? "Fitting…" : "Apply Auto-Fit"}</button>
      </>}>
      <div className="space-y-2" data-testid="autofit-picker">
        {item.installments.map((ins) => {
          const blocked = blockedOf(ins);
          const res = resultingOf(ins);
          return (
            <label key={ins.payment_id}
              className={`flex items-center gap-3 border rounded-md p-3 cursor-pointer transition-colors ${pid === ins.payment_id ? "border-brand bg-brand/5" : "border-line"} ${blocked ? "opacity-50 cursor-not-allowed" : "hover:bg-surfacealt/50"}`}
              data-testid={`autofit-row-${ins.payment_id}`}>
              <input type="radio" name="autofit" disabled={blocked} checked={pid === ins.payment_id}
                onChange={() => setPid(ins.payment_id)} data-testid={`autofit-pick-${ins.payment_id}`} />
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink truncate">{ins.notes || "Instalment"}</div>
                <div className="text-[11px] text-ink2 font-mono-num">{ins.due_date}{ins.verified > 0 ? ` · ${inr(ins.verified)} verified` : ""}</div>
              </div>
              <div className="text-right whitespace-nowrap">
                <div className="font-mono-num text-sm">{inr(ins.amount)} → <b className={blocked ? "text-bad" : "text-ok"}>{inr(res)}</b></div>
                {blocked && <div className="text-[10px] text-bad">below verified — can&rsquo;t use</div>}
              </div>
            </label>
          );
        })}
      </div>
    </Modal>
  );
}
