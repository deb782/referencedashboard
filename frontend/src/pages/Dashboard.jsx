import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth, ROLE_LABELS } from "@/lib/auth";

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/dashboard").then((r) => setStats(r.data)); }, []);

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div>
        <div className="text-xs uppercase tracking-widest text-stone-500">
          {ROLE_LABELS[user?.role]}
        </div>
        <h1 className="text-3xl font-bold text-stone-900 mt-1">Welcome back, {user?.name}</h1>
      </div>
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Tile label="Projects" value={stats.projects} tone="stone" />
          <Tile label="Units available" value={stats.units_available} tone="emerald" />
          <Tile label="Units sold" value={stats.units_sold} tone="sky" />
          <Tile label="Payments pending" value={stats.payments_pending} tone="amber" />
          <Tile label="Procurement queue" value={stats.procurement_pending} tone="rose" />
        </div>
      )}
      <div className="card p-6 text-sm text-stone-600 space-y-2">
        <div className="font-semibold text-stone-900">Quick guide</div>
        {user?.role === "admin" && (
          <ul className="list-disc pl-5 space-y-1">
            <li>Create projects and assign a site manager to each</li>
            <li>Add team members (initial password = phone number)</li>
            <li>Upload units in bulk from your RERA Excel</li>
            <li>Review procurement requests from site managers</li>
          </ul>
        )}
        {user?.role === "post_sales" && (
          <ul className="list-disc pl-5 space-y-1">
            <li>Open <b>Units</b> and click "Mark Sold" on any available plot</li>
            <li>Fill buyer details, sale date, final price, and booking amount</li>
            <li>Add the payment schedule table (row-per-installment)</li>
          </ul>
        )}
        {user?.role === "accounts" && (
          <ul className="list-disc pl-5 space-y-1">
            <li>Open <b>Sales & Payments</b> to see the payment watchlist</li>
            <li>On the due date, mark each row as <b>received</b> or leave it <b>pending</b></li>
            <li>Approved procurement requests come to you with a "Record PO/Payment" button</li>
          </ul>
        )}
        {user?.role === "site_manager" && (
          <ul className="list-disc pl-5 space-y-1">
            <li>Keep your <b>Inventory</b> up to date — add, edit, adjust quantities</li>
            <li>Raise a <b>Procurement</b> request when you need materials</li>
            <li>Track admin's decision + accounts' payment on the same page</li>
          </ul>
        )}
      </div>
    </div>
  );
}

function Tile({ label, value, tone }) {
  const cls = tone === "emerald" ? "bg-emerald-50 border-emerald-200 text-emerald-900"
    : tone === "sky" ? "bg-sky-50 border-sky-200 text-sky-900"
    : tone === "amber" ? "bg-amber-50 border-amber-200 text-amber-900"
    : tone === "rose" ? "bg-rose-50 border-rose-200 text-rose-900"
    : "bg-white border-stone-200 text-stone-900";
  return (
    <div className={`p-4 rounded-xl border ${cls}`}>
      <div className="text-[11px] uppercase tracking-widest text-stone-500">{label}</div>
      <div className="text-3xl font-bold mt-1">{value}</div>
    </div>
  );
}
