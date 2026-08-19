import { useEffect, useState } from "react";
import { Scale, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { inr } from "@/components/ui";
import { ScheduleEditor } from "@/components/ScheduleEditor";

// Sold plots whose instalment schedule total ≠ the plot's Grand Total.
// Reps open the full payment-plan editor to restructure the whole schedule.
export function MismatchedPlots({ projectId, refresh, onOpen, onFixed }) {
  const [data, setData] = useState({ total: 0, count: 0, items: [] });
  const [open, setOpen] = useState(true);
  const [editor, setEditor] = useState(null);   // {unit_id, plot_number, grandTotal, rows}

  const load = () => api.get("/mismatched-plots", { params: projectId ? { project_id: projectId } : {} })
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [refresh, projectId]);

  const openEditor = async (it) => {
    try {
      const r = await api.get("/payments", { params: { unit_id: it.unit_id } });
      r.data.sort((a, b) => a.seq - b.seq);
      setEditor({ unit_id: it.unit_id, plot_number: it.plot_number, grandTotal: it.grand_total, rows: r.data });
    } catch { /* ignore */ }
  };

  const afterSave = () => { setEditor(null); load(); onFixed && onFixed(); };

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
                    <button onClick={() => openEditor(it)} className="text-brand font-semibold hover:underline text-xs mr-3" data-testid={`edit-plan-${it.plot_number}`}>Edit payment plan</button>
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
      {editor && (
        <ScheduleEditor unitId={editor.unit_id} plotNumber={editor.plot_number}
          rows={editor.rows} grandTotal={editor.grandTotal}
          onClose={() => setEditor(null)} onSaved={afterSave} />
      )}
    </div>
  );
}
