import { Link } from "react-router-dom";
import { Clock, CheckCircle2, AlertTriangle, ArrowUpRight } from "lucide-react";
import { PageHeader, SectionCard, EmptyState, inr } from "@/components/ui";

export default function AccountsDashboard({ stats, user }) {
  const s = stats || {};
  const projects = s.by_project || [];
  const con = s.consolidated || {};

  return (
    <div data-testid="dashboard-page">
      <PageHeader overline="The Ledger" title={`Collections & payables, ${user?.name?.split(" ")[0]}`}
        subtitle="Per-project collections plus the company-wide position.">
        <Link to="/sales" className="btn-primary" data-testid="dash-goto-payments"><Clock className="w-4 h-4" /> Payment watchlist</Link>
      </PageHeader>

      <div className="card p-8 ag-rise mb-6">
        <div className="overline">Consolidated · All Projects</div>
        <div className="grid grid-cols-3 gap-6 mt-4">
          <Big label="Pending Collections" value={inr(con.pending_total)} tone="text-warn" />
          <Big label="Received" value={inr(con.received_total)} tone="text-ok" />
          <Big label="Total Booked" value={inr(con.booked_value)} tone="text-brand" />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {projects.map((p, i) => (
          <div key={p.project_id} className={`card p-6 ag-rise ag-rise-${i + 1}`} data-testid={`dash-project-${p.project_id}`}>
            <div className="font-display text-xl font-bold text-ink">{p.name}</div>
            <div className="text-xs text-ink2 mt-0.5">{p.kind || "Project"} · {p.sold} sold</div>
            <div className="grid grid-cols-2 gap-4 mt-5">
              <Box icon={Clock} tone="text-warn" label="Pending" value={inr(p.pending_total)} />
              <Box icon={CheckCircle2} tone="text-ok" label="Received" value={inr(p.received_total)} />
            </div>
            <Link to="/sales" className="btn-secondary w-full mt-5"><ArrowUpRight className="w-4 h-4" /> Open ledger</Link>
          </div>
        ))}
        {projects.length === 0 && <div className="xl:col-span-2"><EmptyState icon={AlertTriangle} title="No projects" /></div>}
      </div>
    </div>
  );
}

function Big({ label, value, tone }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-ink2 font-bold">{label}</div>
      <div className={`font-display font-extrabold text-2xl md:text-3xl mt-1.5 font-mono-num ${tone}`}>{value}</div>
    </div>
  );
}

function Box({ icon: Icon, tone, label, value }) {
  return (
    <div className="border border-agborder rounded-md p-4">
      <div className="flex items-center gap-2"><Icon className={`w-4 h-4 ${tone}`} /><span className="text-[10px] uppercase tracking-wider text-ink2 font-bold">{label}</span></div>
      <div className="font-mono-num font-bold text-ink text-lg mt-1.5">{value}</div>
    </div>
  );
}
