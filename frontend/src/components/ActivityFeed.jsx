import { useEffect, useState } from "react";
import { Activity, ShoppingBag, CalendarClock, Receipt } from "lucide-react";
import { api } from "@/lib/api";

const TYPE_META = {
  sale: { icon: ShoppingBag, tone: "text-ok", ring: "bg-ok" },
  schedule: { icon: CalendarClock, tone: "text-brand", ring: "bg-plate" },
  receipt: { icon: Receipt, tone: "text-ink", ring: "bg-plate" },
};
const RECEIPT_TONE = {
  submitted: "bg-plate", verified: "bg-ok", returned: "bg-bad",
  resubmitted: "bg-brand", bifurcated: "bg-brand", auto_bifurcated: "bg-brand",
};

export function ActivityFeed({ projects = [] }) {
  const [pid, setPid] = useState("all");
  const [events, setEvents] = useState(null);

  useEffect(() => {
    setEvents(null);
    const params = pid === "all" ? {} : { project_id: pid };
    api.get("/activity", { params }).then(r => setEvents(r.data)).catch(() => setEvents([]));
  }, [pid]);

  const fmt = (iso) => { try { return new Date(iso).toLocaleString(); } catch { return iso; } };

  return (
    <section className="panel overflow-hidden ag-rise" data-testid="activity-feed">
      <div className="p-6 lg:p-8 border-b border-line flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 overline"><Activity className="w-3.5 h-3.5" /> Activity Feed</div>
        <div className="flex gap-1.5 flex-wrap">
          <button onClick={() => setPid("all")} data-testid="activity-proj-all"
            className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${pid === "all" ? "bg-plate text-white border-plate" : "border-line text-ink2 hover:bg-surfacealt"}`}>All projects</button>
          {projects.map(p => (
            <button key={p.project_id} onClick={() => setPid(p.project_id)} data-testid={`activity-proj-${p.project_id}`}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${pid === p.project_id ? "bg-plate text-white border-plate" : "border-line text-ink2 hover:bg-surfacealt"}`}>{p.name}</button>
          ))}
        </div>
      </div>
      <div className="max-h-[28rem] overflow-y-auto">
        {events === null ? (
          <div className="p-8 text-center text-sm text-ink2">Loading…</div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center text-sm text-ink2">No activity recorded yet.</div>
        ) : (
          <ol>
            {events.map((e, i) => {
              const meta = TYPE_META[e.type] || TYPE_META.receipt;
              const Icon = meta.icon;
              const ring = e.type === "receipt" ? (RECEIPT_TONE[e.subtype] || "bg-plate") : meta.ring;
              return (
                <li key={i} className="flex items-start gap-3 px-6 lg:px-8 py-3 border-b border-line last:border-0 hover:bg-surfacealt/40" data-testid={`activity-${i}`}>
                  <span className={`mt-1 w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${meta.tone} bg-surfacealt`}>
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <span className="text-sm text-ink">
                        <b className="font-mono-num">Plot {e.plot_number}</b>
                        <span className="text-ink2"> · {e.project}</span>
                      </span>
                      <span className="text-[11px] font-mono-num text-ink2 whitespace-nowrap">{fmt(e.at)}</span>
                    </div>
                    <div className="text-xs text-ink2 mt-0.5">{e.detail}</div>
                    <div className="text-[11px] text-ink2 mt-0.5">by {e.actor || "—"}</div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}
