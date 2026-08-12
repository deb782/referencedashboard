import { Link } from "react-router-dom";
import { Building2, Package, ArrowUpRight, Layers, ShieldCheck } from "lucide-react";
import { PageHeader, StatusPill, SectionCard, EmptyState, inr } from "@/components/ui";

export default function ManagementDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const approvals = s.procurement_approvals || [];
  const perms = s.permissions || user?.permissions || [];
  const canProc = perms.includes("procurement");

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline="Management · Stakeholder Console"
        title={`Good to see you, ${user?.name?.split(" ")[0]}`}
        subtitle="Real-time visibility into financial, operational, sales, and project performance.">
        <span className="pill" style={{ color: "#5a6b10", backgroundColor: "#5a6b1010", borderColor: "#5a6b1022" }} data-testid="mgmt-project-badge">
          <Building2 className="w-3.5 h-3.5" /> {s.project_name || "Assigned project"}
        </span>
      </PageHeader>

      {canProc && (
        <div className="mb-6">
          <div className="card p-5 flex items-center justify-between ag-rise" data-testid="mgmt-approvals-kpi">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-sm bg-clay/10 flex items-center justify-center"><ShieldCheck className="w-5 h-5 text-clay" /></div>
              <div>
                <div className="overline">Awaiting your primary approval</div>
                <div className="font-display font-extrabold text-2xl text-ink font-mono-num">{s.mgmt_approvals_pending ?? 0}</div>
              </div>
            </div>
            <Link to="/procurement" className="btn-primary text-sm" data-testid="mgmt-go-procurement">Review requests <ArrowUpRight className="w-4 h-4" /></Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {projects.map((p, i) => <ProjectPivot key={p.project_id} p={p} idx={i} />)}
        {projects.length === 0 && <div className="xl:col-span-2"><EmptyState icon={Building2} title="No project data yet" hint="Once inventory is uploaded for your project, live pivots appear here." /></div>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {canProc && (
          <SectionCard title="Procurement · Needs Your Approval"
            action={<Link to="/procurement" className="text-xs font-semibold text-brand hover:text-brand-hover flex items-center gap-1">Review all <ArrowUpRight className="w-3.5 h-3.5" /></Link>}>
            {approvals.length === 0 ? (
              <EmptyState icon={Package} title="Queue is clear" hint="No requests waiting on your primary approval." />
            ) : (
              <div className="divide-y divide-agborder">
                {approvals.map((p) => (
                  <Link to="/procurement" key={p.request_id} className="flex items-center justify-between px-5 py-3.5 hover:bg-surfacealt transition-colors duration-200">
                    <div className="text-sm font-semibold text-ink truncate">{p.subject}</div>
                    <div className="flex items-center gap-3"><StatusPill status={p.priority} dot={false} /><StatusPill status={p.status} /></div>
                  </Link>
                ))}
              </div>
            )}
          </SectionCard>
        )}

        <SectionCard title="Site Bills · PO Payments"
          action={<span className="text-xs font-mono-num text-ink2">Pending <b className="text-warn">{inr(s.site_bills?.pending)}</b> · Paid <b className="text-ok">{inr(s.site_bills?.paid)}</b></span>}>
          {!(s.site_bills?.milestones || []).length ? (
            <EmptyState icon={Package} title="No PO milestones" hint="Payment structures set by accounts show here." />
          ) : (
            <div className="overflow-x-auto"><table className="w-full">
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
            </table></div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

function ProjectPivot({ p, idx }) {
  const pivots = p.pivots || [];
  return (
    <div className={`card overflow-hidden ag-rise ag-rise-${idx + 1}`} data-testid={`dash-project-${p.project_id}`}>
      <div className="px-5 py-4 border-b border-agborder bg-surfacealt/40">
        <div className="font-display text-xl font-bold text-ink">{p.name}</div>
        <div className="text-xs text-ink2 mt-0.5" data-testid={`dash-soldplots-${p.project_id}`}>{p.sold}/{p.total_units} plots sold</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <Mini label="Total Sold" value={inr(p.booked_value)} />
          <Mini label="Total Received" value={inr(p.received_total)} />
          <Mini label="Total Pending" value={inr(p.pending_total)} />
          <Mini label="Awaiting Verify" value={inr(p.awaiting_verification || 0)} />
        </div>
      </div>
      {pivots.length === 0 ? (
        <EmptyState icon={Layers} title="No pivot yet" hint="Upload this project's inventory to see component totals." />
      ) : (
        <div className="max-h-96 overflow-y-auto">
          <div className="overflow-x-auto"><table className="w-full">
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
          </table></div>
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
