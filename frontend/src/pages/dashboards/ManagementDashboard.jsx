import { Link } from "react-router-dom";
import { Building2, Package, ArrowUpRight, Layers, ShieldCheck } from "lucide-react";
import { StatusPill, EmptyState, inr, inrShort, AnimatedNumber, projectLogo } from "@/components/ui";

const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };
const today = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });

export default function ManagementDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const approvals = s.procurement_approvals || [];
  const perms = s.permissions || user?.permissions || [];
  const canProc = perms.includes("procurement");

  return (
    <div data-testid="dashboard-page" className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <div className="overline mb-3">{today()} · Stakeholder Console</div>
          <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">
            {greeting()}, {user?.name?.split(" ")[0]}.
          </h1>
          <p className="text-sm text-ink2 mt-3 max-w-xl leading-relaxed">Real-time visibility into financial, operational, sales, and project performance.</p>
        </div>
        <span className="pill" style={{ color: "#5a6b10", backgroundColor: "#5a6b1012", borderColor: "#5a6b1033" }} data-testid="mgmt-project-badge">
          <Building2 className="w-3.5 h-3.5" /> {s.project_name || "Assigned project"}
        </span>
      </header>

      {canProc && (
        <section className="panel p-6 lg:p-7 flex flex-wrap items-center justify-between gap-4 ag-rise" data-testid="mgmt-approvals-kpi">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-lg bg-clay/10 flex items-center justify-center"><ShieldCheck className="w-5 h-5 text-clay" strokeWidth={1.5} /></div>
            <div>
              <div className="overline">Awaiting your primary approval</div>
              <div className="kpi-value text-4xl mt-1 text-ink">{s.mgmt_approvals_pending ?? 0}</div>
            </div>
          </div>
          <Link to="/procurement" className="btn-primary" data-testid="mgmt-go-procurement">Review requests <ArrowUpRight className="w-4 h-4" /></Link>
        </section>
      )}

      <section>
        <div className="overline mb-4">By Project</div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {projects.map((p, i) => <ProjectPanel key={p.project_id} p={p} idx={i} />)}
          {projects.length === 0 && <div className="xl:col-span-2 panel"><EmptyState icon={Building2} title="No project data yet" hint="Once inventory is uploaded for your project, live pivots appear here." /></div>}
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {canProc && (
          <div className="panel">
            <PanelHead title="Procurement · Needs Your Approval" to="/procurement" cta="Review all" />
            {approvals.length === 0 ? (
              <EmptyState icon={Package} title="Queue is clear" hint="No requests waiting on your primary approval." />
            ) : (
              <div className="divide-y divide-line">
                {approvals.map((p) => (
                  <Link to="/procurement" key={p.request_id} className="flex items-center justify-between px-6 py-4 hover:bg-surfacealt transition-colors duration-200">
                    <div className="text-sm font-medium text-ink truncate">{p.subject}</div>
                    <div className="flex items-center gap-3 shrink-0"><StatusPill status={p.priority} dot={false} /><StatusPill status={p.status} /></div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="panel">
          <PanelHead title="Site Bills · PO Payments"
            meta={<span className="text-xs font-mono-num text-ink2">Pending <b className="text-warn">{inrShort(s.site_bills?.pending)}</b> · Paid <b className="text-ok">{inrShort(s.site_bills?.paid)}</b></span>} />
          {!(s.site_bills?.milestones || []).length ? (
            <EmptyState icon={Package} title="No PO milestones" hint="Payment structures set by accounts show here." />
          ) : (
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr className="hairline"><th className="th">Milestone</th><th className="th">PO</th><th className="th">Due</th><th className="th text-right">Amount</th><th className="th">Status</th></tr></thead>
              <tbody>
                {s.site_bills.milestones.map((m, i) => (
                  <tr key={i} className="row border-b border-line last:border-0">
                    <td className="td font-medium">{m.label}<div className="text-[11px] text-ink2 font-normal">{m.subject}</div></td>
                    <td className="td font-mono-num text-ink2">{m.po_number || "—"}</td>
                    <td className="td font-mono-num text-ink2">{m.due || "—"}</td>
                    <td className="td text-right font-mono-num">{inr(m.amount)}</td>
                    <td className="td"><StatusPill status={m.status === "paid" ? "paid" : "pending"} /></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>
      </section>
    </div>
  );
}

function ProjectPanel({ p, idx }) {
  const pivots = (p.pivots || []).filter(pv => pv.tag !== "reference");
  const max = Math.max(1, ...pivots.map(pv => Math.abs(pv.sum_sold || 0)));
  const rate = p.booked_value > 0 ? Math.round((p.received_total / p.booked_value) * 100) : 0;
  return (
    <div className={`panel overflow-hidden ag-rise ag-rise-${idx + 1}`} data-testid={`dash-project-${p.project_id}`}>
      <div className="p-6 lg:p-7 border-b border-line">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              {projectLogo(p.name) && <img src={projectLogo(p.name)} alt="" className="h-6 w-auto max-w-[110px] object-contain" />}
              <div className="font-display text-2xl font-medium text-ink tracking-tight">{p.name}</div>
            </div>
            <div className="text-xs text-ink2 mt-1" data-testid={`dash-soldplots-${p.project_id}`}>
              <span className="font-mono-num text-ink font-semibold">{p.sold}</span> / {p.total_units} plots sold
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.16em] text-ink2 font-semibold">Received</div>
            <div className="kpi-value text-4xl mt-1" title={inr(p.received_total)}><AnimatedNumber value={p.received_total || 0} format={inrShort} /></div>
          </div>
        </div>
        <div className="mt-5 flex items-center gap-3">
          <div className="flex-1 h-[6px] rounded-full bg-surfacealt overflow-hidden">
            <div className="h-full rounded-full bg-plate transition-[width] duration-700 ease-out" style={{ width: `${rate}%` }} />
          </div>
          <span className="text-xs font-mono-num text-ink2 shrink-0">{rate}% of {inrShort(p.booked_value)}</span>
        </div>
        <div className="grid grid-cols-3 gap-4 mt-5">
          <MiniStat label="Sold value" value={p.booked_value} />
          <MiniStat label="Outstanding" value={p.pending_total} tone="text-clay" />
          <MiniStat label="Awaiting" value={p.awaiting_verification || 0} lime />
        </div>
      </div>
      {pivots.length === 0 ? (
        <EmptyState icon={Layers} title="No pivot yet" hint="Upload this project's inventory to see component totals." />
      ) : (
        <div className="p-6 lg:p-7 space-y-3 max-h-80 overflow-y-auto">
          <div className="overline">Sold value by component</div>
          {pivots.map(pv => (
            <div key={pv.key} className="group">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-ink2 truncate flex items-center gap-1.5">
                  {pv.label}{pv.tag === "total" && <span className="text-[9px] text-plate font-bold uppercase tracking-wider bg-lime px-1 rounded">Total</span>}
                </span>
                <span className="font-mono-num text-ink font-medium shrink-0 ml-3">{inrShort(pv.sum_sold)}</span>
              </div>
              <div className="h-[4px] rounded-full bg-surfacealt overflow-hidden">
                <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${pv.tag === "total" ? "bg-plate" : "bg-brand/60"}`}
                  style={{ width: `${Math.max(2, (Math.abs(pv.sum_sold || 0) / max) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, tone = "text-ink", lime }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-ink2 font-semibold flex items-center gap-1">
        {lime && <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#ccff00" }} />}{label}
      </div>
      <div className={`font-mono-num font-semibold text-sm mt-1 ${tone}`} title={inr(value)}>{inrShort(value)}</div>
    </div>
  );
}

function PanelHead({ title, to, cta, meta }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-line">
      <div className="overline text-ink">{title}</div>
      {to && <Link to={to} className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">{cta} <ArrowUpRight className="w-3.5 h-3.5" /></Link>}
      {meta}
    </div>
  );
}
