import { useEffect, useState } from "react";
import { CalendarRange, AlertTriangle, Download } from "lucide-react";
import { toast } from "sonner";
import { api, apiError, downloadFile } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { inr, amountWords } from "@/components/ui";

const RANGES = [
  { m: 1, label: "1 month" },
  { m: 3, label: "3 months" },
  { m: 6, label: "6 months" },
  { m: 12, label: "12 months" },
];

export function CollectionsPeriod() {
  const { user } = useAuth();
  const canExport = can(user, "admin", "accounts");
  const [months, setMonths] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get("/dashboard/collections", { params: { months } })
      .then((r) => { if (alive) { setData(r.data); setLoading(false); } })
      .catch(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [months]);

  const d = data || { expected: 0, collected: 0, outstanding: 0, by_project: [], overdue: { total: 0, count: 0, items: [] } };
  const overdue = d.overdue || { total: 0, count: 0, items: [] };

  const exportCsv = async () => {
    setExporting(true);
    try { await downloadFile(`/dashboard/collections.csv?months=${months}`, `Collections_${d.start}_to_${d.end}.csv`); }
    catch (e) { toast.error(apiError(e)); }
    finally { setExporting(false); }
  };

  return (
    <section className="panel overflow-hidden ag-rise" data-testid="collections-period">
      <div className="p-6 lg:p-8 border-b border-line flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 overline"><CalendarRange className="w-3.5 h-3.5" /> Collections Outlook</div>
          <div className="font-display text-2xl font-medium text-ink tracking-tight mt-2">Due in the next {months === 1 ? "month" : `${months} months`}</div>
          <div className="text-xs text-ink2 mt-1 font-mono-num">{d.start} → {d.end}</div>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex gap-1.5 flex-wrap">
            {RANGES.map((r) => (
              <button key={r.m} onClick={() => setMonths(r.m)} data-testid={`range-${r.m}`}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${months === r.m ? "bg-plate text-white border-plate" : "border-line text-ink2 hover:bg-surfacealt"}`}>
                {r.label}
              </button>
            ))}
          </div>
          {canExport && (
            <button onClick={exportCsv} disabled={exporting} data-testid="collections-export"
              className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1 disabled:opacity-50">
              <Download className="w-3.5 h-3.5" /> {exporting ? "Preparing…" : "Export CSV"}
            </button>
          )}
        </div>
      </div>

      {overdue.count > 0 && (
        <div className="px-6 lg:px-8 py-4 border-b border-line bg-clay/5" data-testid="overdue-alert">
          <div className="flex items-center gap-2 text-clay">
            <AlertTriangle className="w-4 h-4" strokeWidth={2} />
            <span className="text-sm font-semibold">{overdue.count} instalment{overdue.count > 1 ? "s" : ""} overdue · {inr(overdue.total)} past due</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {overdue.items.slice(0, 8).map((o, i) => (
              <span key={i} data-testid={`overdue-item-${o.plot_number}`}
                className="text-[11px] px-2 py-1 rounded-md border border-clay/30 bg-white text-ink font-mono-num">
                Plot {o.plot_number} · {o.due_date} · {o.days_overdue}d · <b className="text-clay">{inr(o.outstanding)}</b>
              </span>
            ))}
            {overdue.count > 8 && <span className="text-[11px] text-ink2 self-center">+{overdue.count - 8} more</span>}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-line">
        <PeriodStat label="Expected to receive" value={d.expected} tone="text-ink" testid="period-expected" loading={loading} />
        <PeriodStat label="Received against it" value={d.collected} tone="text-ok" lime testid="period-collected" loading={loading} />
        <PeriodStat label="Still to collect" value={d.outstanding} tone="text-clay" testid="period-outstanding" loading={loading} />
      </div>

      {(d.by_project || []).length > 0 && (
        <div className="p-6 lg:p-8 border-t border-line space-y-3">
          <div className="overline">By project</div>
          {d.by_project.map((p) => {
            const rate = p.expected > 0 ? Math.round((p.collected / p.expected) * 100) : 0;
            return (
              <div key={p.project_id} data-testid={`period-project-${p.project_id}`}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-ink font-medium">{p.name}</span>
                  <span className="font-mono-num text-ink2 text-xs">
                    <b className="text-ok">{inr(p.collected)}</b> / {inr(p.expected)} · <b className="text-clay">{inr(p.outstanding)}</b> due
                  </span>
                </div>
                <div className="h-[5px] rounded-full bg-surfacealt overflow-hidden">
                  <div className="h-full rounded-full bg-plate transition-[width] duration-700 ease-out" style={{ width: `${rate}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {!loading && (d.by_project || []).length === 0 && (
        <div className="p-8 text-sm text-ink2 text-center">No instalments fall due in this period.</div>
      )}
    </section>
  );
}

function PeriodStat({ label, value, tone = "text-ink", lime, testid, loading }) {
  return (
    <div className="p-6 lg:p-8">
      <div className="flex items-center gap-2">
        {lime && <span className="w-2 h-2 rounded-full" style={{ background: "#ccff00" }} />}
        <span className="text-[11px] uppercase tracking-[0.16em] text-ink2 font-semibold">{label}</span>
      </div>
      <div className={`kpi-value text-2xl lg:text-3xl mt-2 break-words ${tone}`} data-testid={testid} title={inr(value)}>
        {loading ? "…" : inr(value)}
      </div>
      {!loading && <div className="text-[10px] text-ink2 mt-1 italic leading-snug">{amountWords(value)}</div>}
    </div>
  );
}
