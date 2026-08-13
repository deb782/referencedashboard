import { Link } from "react-router-dom";
import { Clock, ArrowUpRight, Building2 } from "lucide-react";
import { EmptyState, inr, inrShort, AnimatedNumber } from "@/components/ui";

const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };
const today = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

export default function AccountsDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const con = s.consolidated || {};
  const booked = con.booked_value || 0;
  const rate = booked > 0 ? Math.round(((con.received_total || 0) / booked) * 100) : 0;

  return (
    <div data-testid="dashboard-page" className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">{today()} · The Ledger</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">
            {greeting()}, {user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-sm text-ink2 mt-3 max-w-xl leading-relaxed">Per-project collections plus the company-wide position.</p>
        </div>
        <Link to="/sales" className="btn-primary" data-testid="dash-goto-payments"><Clock className="w-4 h-4" /> Payment watchlist</Link>
      </header>

      <section className="panel overflow-hidden ag-rise">
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr]">
          <div className="p-8 lg:p-12 border-b lg:border-b-0 lg:border-r border-line relative">
            <div className="grid-canvas absolute inset-0 opacity-40 pointer-events-none" />
            <div className="relative">
              <div className="flex items-center gap-3">
                <span className="overline">Pending Collections · Portfolio</span>
                <span className="text-[11px] font-semibold text-ink px-2 py-0.5 rounded-md" style={{ background: "#ccff00" }}>{rate}% collected</span>
              </div>
              <div className="kpi-value text-6xl sm:text-7xl lg:text-[92px] mt-4 text-clay" title={inr(con.pending_total)}>
                <AnimatedNumber value={con.pending_total || 0} format={inrShort} />
              </div>
              <div className="mt-8 h-[6px] rounded-full bg-surfacealt overflow-hidden max-w-md">
                <div className="h-full rounded-full bg-plate transition-[width] duration-700 ease-out" style={{ width: `${rate}%` }} />
              </div>
              <div className="text-xs text-ink2 mt-2 max-w-md">Received {inrShort(con.received_total)} of total booked {inrShort(booked)}.</div>
            </div>
          </div>
          <div className="divide-y divide-line">
            <HeroStat label="Received" value={con.received_total || 0} tone="text-ok" />
            <HeroStat label="Total Booked" value={booked} />
            <HeroStat label="Pending" value={con.pending_total || 0} tone="text-clay" lime />
          </div>
        </div>
      </section>

      <section>
        <div className="overline mb-4">By Project</div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {projects.map((p, i) => {
            const pr = p.booked_value > 0 ? Math.round((p.received_total / p.booked_value) * 100) : 0;
            return (
              <div key={p.project_id} className={`panel p-6 lg:p-7 ag-rise ag-rise-${i + 1}`} data-testid={`dash-project-${p.project_id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="font-display text-2xl font-medium text-ink tracking-tight">{p.name}</div>
                    <div className="text-xs text-ink2 mt-1"><span className="font-mono-num text-ink font-semibold">{p.sold}</span> sold</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-semibold">Received</div>
                    <div className="kpi-value text-4xl mt-1 text-ok" title={inr(p.received_total)}><AnimatedNumber value={p.received_total || 0} format={inrShort} /></div>
                  </div>
                </div>
                <div className="mt-5 flex items-center gap-3">
                  <div className="flex-1 h-[6px] rounded-full bg-surfacealt overflow-hidden">
                    <div className="h-full rounded-full bg-plate transition-[width] duration-700 ease-out" style={{ width: `${pr}%` }} />
                  </div>
                  <span className="text-xs font-mono-num text-ink2 shrink-0">{pr}%</span>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-5">
                  <MiniStat label="Pending" value={p.pending_total} tone="text-clay" />
                  <MiniStat label="Received" value={p.received_total} tone="text-ok" />
                </div>
                <Link to="/sales" className="btn-secondary w-full mt-6"><ArrowUpRight className="w-4 h-4" /> Open ledger</Link>
              </div>
            );
          })}
          {projects.length === 0 && <div className="xl:col-span-2 panel"><EmptyState icon={Building2} title="No projects" /></div>}
        </div>
      </section>
    </div>
  );
}

function HeroStat({ label, value, tone = "text-ink", lime }) {
  return (
    <div className="p-6 lg:p-8 flex items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        {lime && <span className="w-2 h-2 rounded-full" style={{ background: "#ccff00" }} />}
        <span className="text-[11px] uppercase tracking-[0.16em] text-ink2 font-semibold">{label}</span>
      </div>
      <div className={`kpi-value text-3xl lg:text-4xl ${tone}`} title={inr(value)}><AnimatedNumber value={value} format={inrShort} /></div>
    </div>
  );
}

function MiniStat({ label, value, tone = "text-ink" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-ink2 font-semibold">{label}</div>
      <div className={`font-mono-num font-semibold text-sm mt-1 ${tone}`} title={inr(value)}>{inrShort(value)}</div>
    </div>
  );
}
