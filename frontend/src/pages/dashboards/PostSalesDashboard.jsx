import { useState } from "react";
import { Link } from "react-router-dom";
import { Home, TrendingUp, ArrowUpRight, Wallet } from "lucide-react";
import { EmptyState, inr, inrShort, AnimatedNumber, projectLogo, amountWords } from "@/components/ui";
import { CollectionsPeriod } from "@/components/CollectionsPeriod";

const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };
const today = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

const FILTERS = [
  { key: "all", label: "All" },
  { key: "due_today", label: "Due Today" },
  { key: "upcoming", label: "Upcoming" },
  { key: "partial", label: "Partial" },
  { key: "overdue", label: "Overdue" },
  { key: "awaiting", label: "Awaiting Verification" },
  { key: "returned", label: "Returned for Correction" },
];

const STATUS_TONE = {
  received: "bg-ok/10 text-ok", partial: "bg-brand/10 text-brand",
  overdue: "bg-bad/10 text-bad", due_today: "bg-warn/15 text-warn",
  upcoming: "bg-surfacealt text-ink2",
};
const VERIF_TONE = {
  verified: "bg-ok/10 text-ok", awaiting: "bg-warn/15 text-warn",
  returned: "bg-bad/10 text-bad", none: "bg-surfacealt text-ink2",
};
const labelize = (k) => (k || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function PostSalesDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const recent = s.recent_sales || [];
  const collections = s.collections || [];
  const [filter, setFilter] = useState("all");

  const shown = collections.filter((c) => {
    if (filter === "all") return true;
    if (filter === "awaiting") return c.verification === "awaiting";
    if (filter === "returned") return c.verification === "returned";
    return c.status === filter;
  });
  const count = (k) => collections.filter((c) =>
    k === "all" ? true : (k === "awaiting" || k === "returned") ? c.verification === k : c.status === k).length;

  const totalAvail = projects.reduce((a, p) => a + (p.available || 0), 0);
  const totalSold = projects.reduce((a, p) => a + (p.sold || 0), 0);

  return (
    <div data-testid="dashboard-page" className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">{today()} · Post-Sales Desk</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">
            {greeting()}, {user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-sm text-ink2 mt-3 max-w-xl leading-relaxed">Availability and bookings for each project. Pick a plot to book from Units.</p>
        </div>
        <div className="flex items-center gap-8">
          <Meta label="Available" value={totalAvail} />
          <Meta label="Sold" value={totalSold} accent />
          <Link to="/units" className="btn-primary" data-testid="dash-mark-sold"><Home className="w-4 h-4" /> Go to Units</Link>
        </div>
      </header>

      <CollectionsPeriod />

      <section>
        <div className="overline mb-4">By Project</div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {projects.map((p, i) => (
            <div key={p.project_id} className={`panel p-6 lg:p-7 ag-rise ag-rise-${i + 1}`} data-testid={`dash-project-${p.project_id}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    {projectLogo(p.name) && <img src={projectLogo(p.name)} alt="" className="h-6 w-auto max-w-[110px] object-contain" />}
                    <div className="font-display text-2xl font-medium text-ink tracking-tight">{p.name}</div>
                  </div>
                  <div className="text-xs text-ink2 mt-1">{p.kind || "Project"}</div>
                </div>
                <div className="text-right max-w-[240px]">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-semibold">Booked value</div>
                  <div className="kpi-value text-2xl lg:text-3xl mt-1 break-words" title={inr(p.booked_value)}>{inr(p.booked_value)}</div>
                  <div className="text-[10px] text-ink2 mt-1 italic leading-snug">{amountWords(p.booked_value)}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-6">
                <Stat label="Available" value={p.available} tone="text-ok" />
                <Stat label="Sold" value={p.sold} tone="text-brand" />
              </div>
              <Link to="/units" className="btn-secondary w-full mt-6"><Home className="w-4 h-4" /> Book a plot here</Link>
            </div>
          ))}
          {projects.length === 0 && <div className="xl:col-span-2 panel"><EmptyState icon={Home} title="No projects" /></div>}
        </div>
      </section>

      <section data-testid="collections-widget" className="panel">
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div className="overline text-ink">Payments · Collections</div>
          <Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Record payments <ArrowUpRight className="w-3.5 h-3.5" /></Link>
        </div>
        <div className="px-6 pt-5 flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} data-testid={`collections-filter-${f.key}`}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${filter === f.key ? "bg-plate text-white border-plate" : "border-line text-ink2 hover:bg-surfacealt"}`}>
              {f.label} <span className="opacity-70">({count(f.key)})</span>
            </button>
          ))}
        </div>
        {shown.length === 0 ? (
          <EmptyState icon={Wallet} title="Nothing here" hint="Booked plots and their due installments show up here for collection tracking." />
        ) : (
          <div className="overflow-x-auto mt-4"><table className="w-full">
            <thead><tr className="hairline">
              <th className="th">Plot</th><th className="th">Customer</th><th className="th text-right">Due Amount</th>
              <th className="th">Due Date</th><th className="th text-right">Received</th><th className="th text-right">Balance</th>
              <th className="th">Status</th><th className="th">Verification</th><th className="th text-right">Action</th>
            </tr></thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.payment_id} className="row border-b border-line last:border-0" data-testid={`collections-row-${c.payment_id}`}>
                  <td className="td font-mono-num font-semibold">{c.plot_number}<div className="text-[10px] text-ink2 font-sans">{c.project_name} · {c.installment}</div></td>
                  <td className="td">{c.buyer_name}</td>
                  <td className="td text-right font-mono-num">{inr(c.due_amount)}</td>
                  <td className="td font-mono-num text-ink2">{c.due_date || "—"}</td>
                  <td className="td text-right font-mono-num text-ok">{inr(c.received)}</td>
                  <td className="td text-right font-mono-num">{inr(c.balance)}{c.awaiting > 0 && <div className="text-[10px] text-warn">{inr(c.awaiting)} awaiting</div>}</td>
                  <td className="td"><span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${STATUS_TONE[c.status] || "bg-surfacealt text-ink2"}`}>{labelize(c.status)}</span></td>
                  <td className="td"><span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${VERIF_TONE[c.verification] || "bg-surfacealt text-ink2"}`}>{c.verification === "none" ? "—" : labelize(c.verification)}</span>
                    {c.expected_remaining_date && <div className="text-[10px] text-ink2 mt-0.5">exp {c.expected_remaining_date}</div>}</td>
                  <td className="td text-right">
                    <Link to="/sales" data-testid={`collections-action-${c.payment_id}`}
                      className={`text-xs font-semibold ${c.verification === "returned" ? "text-bad" : "text-brand"} hover:underline`}>
                      {c.verification === "returned" ? "Correct" : (c.status === "received" ? "View" : "Record")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section className="panel">
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div className="overline text-ink">Recent Sales</div>
          <Link to="/sales" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Sales & Payments <ArrowUpRight className="w-3.5 h-3.5" /></Link>
        </div>
        {recent.length === 0 ? <EmptyState icon={TrendingUp} title="No sales yet" hint="Booked plots will appear here." /> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="hairline"><th className="th">Plot</th><th className="th">Buyer</th><th className="th">Date</th><th className="th text-right">Final price</th></tr></thead>
            <tbody>
              {recent.map(u => (
                <tr key={u.unit_id} className="row border-b border-line last:border-0">
                  <td className="td font-mono-num font-semibold">{u.plot_number}</td>
                  <td className="td">{u.buyer_name || "—"}</td>
                  <td className="td font-mono-num text-ink2">{u.sale_date || "—"}</td>
                  <td className="td text-right font-mono-num">{inr(u.final_price)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>
    </div>
  );
}

function Meta({ label, value, accent }) {
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-semibold">{label}</div>
      <div className={`kpi-value text-3xl mt-1 ${accent ? "text-brand" : "text-ink"}`}><AnimatedNumber value={value} format={(v) => Math.round(v)} /></div>
    </div>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-ink2 font-semibold">{label}</div>
      <div className={`kpi-value text-4xl mt-1 ${tone}`}>{value}</div>
    </div>
  );
}
