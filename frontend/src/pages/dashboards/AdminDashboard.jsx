import { Link } from "react-router-dom";
import { Building2, Home, HandCoins, Package, Users, TrendingUp, ArrowUpRight, Layers } from "lucide-react";
import { PageHeader, Kpi, StatusPill, SectionCard, EmptyState, inr } from "@/components/ui";

export default function AdminDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const con = s.consolidated || {};
  const approvals = s.procurement_approvals || [];

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline="Command Center"
        title={`Good to see you, ${user?.name?.split(" ")[0]}`}
        subtitle="A live sold-value pivot for each project.">
        <Link to="/units" className="btn-secondary" data-testid="dash-units"><Home className="w-4 h-4" /> Units</Link>
        <Link to="/projects" className="btn-primary" data-testid="dash-projects"><Building2 className="w-4 h-4" /> Projects</Link>
      </PageHeader>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
        <Kpi label="Projects" value={con.projects ?? 0} icon={Building2} tone="ink" className="ag-rise" mono={false} />
        <Kpi label="Team Members" value={s.team_members ?? 0} icon={Users} tone="ink" className="ag-rise ag-rise-1" mono={false} />
        <Kpi label="Procurement Queue" value={s.procurement_pending ?? 0} icon={Package} tone="clay" accent="#a8763f" className="ag-rise ag-rise-2" mono={false} />
        <Kpi label="Procurement Paid" value={s.procurement_paid ?? 0} icon={HandCoins} tone="ok" className="ag-rise ag-rise-3" mono={false} />
      </div>

      {/* Per-project pivots — two columns */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {projects.map((p, i) => <ProjectPivot key={p.project_id} p={p} idx={i} />)}
        {projects.length === 0 && <div className="xl:col-span-2"><EmptyState icon={Building2} title="No projects yet" hint="Create projects and upload inventory to see live pivots." /></div>}
      </div>

      {/* Procurement queue + Site bills */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <SectionCard title="Procurement · Needs Action"
          action={<Link to="/procurement" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Review all <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
          {approvals.length === 0 ? (
            <EmptyState icon={Package} title="Queue is clear" hint="No procurement requests waiting on you." />
          ) : (
            <div className="divide-y divide-agborder">
              {approvals.map((p) => (
                <Link to="/procurement" key={p.request_id} className="flex items-center justify-between px-5 py-3.5 hover:bg-surfacealt transition-colors duration-200">
                  <div className="text-sm font-semibold text-ink truncate">{p.subject}</div>
                  <div className="flex items-center gap-3"><StatusPill status={p.priority} /><StatusPill status={p.status} /></div>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title={`Site Bills · PO Payments`}
          action={<span className="text-xs font-mono-num text-ink2">Pending <b className="text-warn">{inr(s.site_bills?.pending)}</b> · Paid <b className="text-ok">{inr(s.site_bills?.paid)}</b></span>}>
          {!(s.site_bills?.milestones || []).length ? (
            <EmptyState icon={Package} title="No PO milestones" hint="Payment structures set by accounts show here." />
          ) : (
            <table className="w-full">
              <thead><tr className="border-b border-agborder"><th className="th">Milestone</th><th className="th">PO</th><th className="th">Due</th><th className="th text-right">Amount</th><th className="th">Status</th></tr></thead>
              <tbody>
                {s.site_bills.milestones.map((m, i) => (
                  <tr key={i} className="row">
                    <td className="td font-semibold">{m.label}<div className="text-[11px] text-ink2 font-normal">{m.subject}</div></td>
                    <td className="td font-mono-num text-ink2">{m.po_number || "—"}</td>
                    <td className="td font-mono-num text-ink2">{m.due || "—"}</td>
                    <td className="td text-right font-mono-num">{inr(m.amount)}</td>
                    <td className="td"><StatusPill status={m.status === "paid" ? "paid" : "pending"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function Big({ label, value, tone }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink2 font-bold">{label}</div>
      <div className={`font-display font-extrabold tracking-tight text-2xl md:text-3xl mt-1.5 font-mono-num ${tone}`}>{value}</div>
    </div>
  );
}

function ProjectPivot({ p, idx }) {
  const pivots = p.pivots || [];
  return (
    <div className={`card overflow-hidden ag-rise ag-rise-${idx + 1}`} data-testid={`dash-project-${p.project_id}`}>
      <div className="px-5 py-4 border-b border-agborder bg-surfacealt/40">
        <div className="font-display text-xl font-bold text-ink">{p.name}</div>
        <div className="text-xs text-ink2 mt-0.5">{p.kind || "Project"}</div>
        <div className="grid grid-cols-3 gap-3 mt-4">
          <Mini label="Total Sold" value={inr(p.booked_value)} />
          <Mini label="Total Received" value={inr(p.received_total)} />
          <Mini label="Total Pending" value={inr(p.pending_total)} />
        </div>
      </div>
      {pivots.length === 0 ? (
        <EmptyState icon={Layers} title="No pivot yet" hint="Upload this project's inventory to see component totals." />
      ) : (
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-white"><tr className="border-b border-agborder">
              <th className="th">Component</th><th className="th text-right">Sold (booked)</th>
            </tr></thead>
            <tbody>
              {pivots.map(pv => (
                <tr key={pv.key} className="row">
                  <td className="td font-semibold">{pv.label}{pv.tag === "reference" && <span className="text-[10px] text-ink2 ml-1">(ref)</span>}{pv.tag === "total" && <span className="text-[10px] text-brand ml-1 font-bold">TOTAL</span>}</td>
                  <td className="td text-right font-mono-num font-semibold">{inr(pv.sum_sold)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="bg-white border border-agborder rounded-md px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ink2 font-bold">{label}</div>
      <div className="font-mono-num font-bold text-ink text-sm mt-0.5">{value}</div>
    </div>
  );
}
