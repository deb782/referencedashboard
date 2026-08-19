import { useEffect, useState } from "react";
import { PieChart, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { inr } from "@/components/ui";

// Per-project reconciliation progress: share of VERIFIED money already split by component.
export function BifurcationProgress({ projectId, refresh }) {
  const [data, setData] = useState({ items: [], verified: 0, bifurcated: 0, unbifurcated: 0, pct: 0 });
  const [open, setOpen] = useState(true);

  useEffect(() => {
    api.get("/bifurcation-progress", { params: projectId ? { project_id: projectId } : {} })
      .then(r => setData(r.data)).catch(() => {});
  }, [refresh, projectId]);

  if (!data.items.length) return null;
  const barColor = (p) => p >= 100 ? "bg-ok" : p >= 60 ? "bg-brand" : p >= 25 ? "bg-warn" : "bg-bad";

  return (
    <div className="panel overflow-hidden" data-testid="bifurcation-progress">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between gap-3 px-5 py-3.5 text-left">
        <span className="flex items-center gap-2 text-ink font-semibold text-sm">
          <PieChart className="w-4 h-4 text-brand" />
          Bifurcation progress · {data.pct}% of verified money split
          {data.unbifurcated > 0.01 && <span className="text-ink2 font-normal">· {inr(data.unbifurcated)} left</span>}
        </span>
        <ChevronRight className={`w-4 h-4 text-ink2 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-line px-5 py-4 space-y-4">
          {data.items.map((it) => (
            <div key={it.project_id} data-testid={`bif-proj-${it.project_id}`}>
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <span className="text-sm font-semibold text-ink truncate">{it.project}</span>
                <span className="text-xs font-mono-num text-ink2 whitespace-nowrap">
                  {inr(it.bifurcated)} / {inr(it.verified)} · <b className="text-ink">{it.pct}%</b>
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-surfacealt overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-500 ${barColor(it.pct)}`}
                  style={{ width: `${Math.min(100, it.pct)}%` }} data-testid={`bif-bar-${it.project_id}`} />
              </div>
              {it.unbifurcated > 0.01 && (
                <div className="text-[11px] text-ink2 mt-1 font-mono-num">
                  {inr(it.unbifurcated)} across {it.pending_receipts} receipt(s) still to bifurcate
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
