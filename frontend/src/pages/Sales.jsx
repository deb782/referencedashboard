import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Home, Building2, Wallet, ChevronRight, Receipt, XCircle, ShieldCheck, Download } from "lucide-react";
import { api, apiError, downloadFile } from "@/lib/api";
import { useAuth, can } from "@/lib/auth";
import { StatusPill, EmptyState, SectionCard, Modal, inr } from "@/components/ui";

export default function Sales() {
  const { user } = useAuth();
  const [head, setHead] = useState("plots");
  const [ov, setOv] = useState(null);
  const [cancels, setCancels] = useState([]);
  const [drill, setDrill] = useState(null);   // {unit_id, plot_number, buyer_name}
  const canRecord = can(user, "post_sales");
  const canVerify = can(user, "accounts");
  const canViewPay = can(user, "post_sales", "accounts", "admin");
  const canPay = canViewPay;
  const [verifs, setVerifs] = useState([]);

  const load = async () => {
    try { const r = await api.get("/accounts/overview"); setOv(r.data); }
    catch (e) { toast.error(apiError(e)); }
    if (can(user, "admin", "accounts")) {
      try { const c = await api.get("/cancellations"); setCancels(c.data); } catch (e) { /* ignore */ }
      try { const v = await api.get("/payments/verifications"); setVerifs(v.data); } catch (e) { /* ignore */ }
    }
  };
  useEffect(() => { load(); }, []);

  const plots = ov?.plots || { projects: [], totals: {} };
  const site = ov?.site || { rows: [], pending_total: 0, paid_total: 0 };

  return (
    <div data-testid="sales-page" className="space-y-8">
      <header>
        <div className="overline mb-3">The Ledger</div>
        <h1 className="font-display text-5xl sm:text-6xl font-medium tracking-tight text-ink leading-[0.95]">Sales &amp; Payments</h1>
        <p className="text-sm text-ink2 mt-3 max-w-xl">Dues are grouped into two heads — Plots (buyer instalments) and Site (procurement bills). Only Accounts-verified money is counted.</p>
      </header>

      {/* Head toggle */}
      <div className="flex flex-wrap gap-2">
        <HeadTab active={head === "plots"} onClick={() => setHead("plots")} icon={Home}
          label="Plots" pending={plots.totals?.pending} testid="head-plots" />
        <HeadTab active={head === "site"} onClick={() => setHead("site")} icon={Building2}
          label="Site" pending={site.pending_total} testid="head-site" />
        {can(user, "admin", "accounts") && (
          <button onClick={() => setHead("verify")} data-testid="head-verify"
            className={`flex items-center gap-3 px-5 py-3 rounded-lg border transition-colors duration-300 ${head === "verify" ? "bg-plate text-white border-plate" : "bg-white border-line text-ink2 hover:bg-surfacealt"}`}>
            <ShieldCheck className="w-5 h-5" />
            <div className="text-left">
              <div className="font-display font-bold leading-none">Verification</div>
              <div className={`text-xs mt-1 font-mono-num ${head === "verify" ? "text-white/80" : "text-ink2"}`}>{verifs.filter(v => v.verification_status === "pending").length} pending</div>
            </div>
          </button>
        )}
        {can(user, "admin", "accounts") && (
          <button onClick={() => setHead("cancellations")} data-testid="head-cancellations"
            className={`flex items-center gap-3 px-5 py-3 rounded-lg border transition-colors duration-300 ${head === "cancellations" ? "bg-plate text-white border-plate" : "bg-white border-line text-ink2 hover:bg-surfacealt"}`}>
            <XCircle className="w-5 h-5" />
            <div className="text-left">
              <div className="font-display font-bold leading-none">Cancellations</div>
              <div className={`text-xs mt-1 font-mono-num ${head === "cancellations" ? "text-white/80" : "text-ink2"}`}>{cancels.length} record(s)</div>
            </div>
          </button>
        )}
      </div>

      {head === "plots" ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <Summary label="Plots — Billed" value={inr(plots.totals?.total)} tone="text-ink" />
            <Summary label="Received" value={inr(plots.totals?.paid)} tone="text-ok" />
            <Summary label="Pending" value={inr(plots.totals?.pending)} tone="text-warn" />
          </div>
          {(plots.projects || []).map((p) => (
            <SectionCard key={p.project_id} title={`${p.name} · ${p.plot_count} plot(s)`} className="ag-rise"
              action={<span className="text-xs font-mono-num text-ink2">Pending <b className="text-warn">{inr(p.pending)}</b></span>}>
              <div className="overflow-x-auto"><table className="w-full">
                <thead><tr className="border-b border-line bg-surfacealt/40">
                  <th className="th">Plot</th><th className="th">Buyer</th><th className="th">Instalments</th>
                  <th className="th">Next due</th><th className="th text-right">Billed</th>
                  <th className="th text-right">Received</th><th className="th text-right">Pending</th><th className="th"></th>
                </tr></thead>
                <tbody>
                  {p.plots.map((r) => (
                    <tr key={r.unit_id} className="row cursor-pointer" onClick={() => setDrill(r)} data-testid={`plot-pay-row-${r.plot_number}`}>
                      <td className="td font-mono-num font-bold">{r.plot_number}</td>
                      <td className="td text-ink2">{r.buyer_name || "—"}</td>
                      <td className="td font-mono-num text-ink2">{r.installments}</td>
                      <td className="td font-mono-num text-ink2">{r.next_due || "—"}</td>
                      <td className="td text-right font-mono-num">{inr(r.total)}</td>
                      <td className="td text-right font-mono-num text-ok">{inr(r.paid)}</td>
                      <td className="td text-right font-mono-num font-semibold text-warn">{inr(r.pending)}</td>
                      <td className="td text-right"><ChevronRight className="w-4 h-4 text-ink2 inline" /></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            </SectionCard>
          ))}
          {(plots.projects || []).length === 0 && <EmptyState icon={Home} title="No plot dues yet" hint="Payments appear here once plots are sold." />}
        </div>
      ) : head === "site" ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <Summary label="Site — Pending" value={inr(site.pending_total)} tone="text-warn" />
            <Summary label="Site — Paid" value={inr(site.paid_total)} tone="text-ok" />
          </div>
          <SectionCard title="Procurement bills" className="ag-rise">
            {site.rows.length === 0 ? <EmptyState icon={Building2} title="No site bills" hint="Approved procurement bills appear here." /> : (
              <div className="overflow-x-auto"><table className="w-full">
                <thead><tr className="border-b border-line bg-surfacealt/40">
                  <th className="th">Subject</th><th className="th">Project</th><th className="th">PO</th>
                  <th className="th text-right">Estimated</th><th className="th text-right">Paid</th>
                  <th className="th text-right">Pending</th><th className="th">Status</th>
                </tr></thead>
                <tbody>
                  {site.rows.map((r) => (
                    <tr key={r.request_id} className="row" data-testid={`site-row-${r.request_id}`}>
                      <td className="td font-semibold">{r.subject}</td>
                      <td className="td text-ink2">{r.project_name}</td>
                      <td className="td font-mono-num text-ink2">{r.po_number || "—"}</td>
                      <td className="td text-right font-mono-num">{inr(r.est_total)}</td>
                      <td className="td text-right font-mono-num text-ok">{inr(r.paid)}</td>
                      <td className="td text-right font-mono-num font-semibold text-warn">{inr(r.pending)}</td>
                      <td className="td"><StatusPill status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
            <div className="px-5 py-3 text-xs text-ink2 border-t border-line">Record PO payments from the Procurement page. Milestone payment structure comes in the next phase.</div>
          </SectionCard>
        </div>
      ) : head === "cancellations" ? (
        <CancellationsView rows={cancels} />
      ) : (
        <VerificationQueue rows={verifs} canVerify={canVerify} onChanged={load} />
      )}

      {drill && <PlotDrilldown plot={drill} canRecord={canRecord} canVerify={canVerify} onClose={() => setDrill(null)} onChanged={load} />}
    </div>
  );
}

function HeadTab({ active, onClick, icon: Icon, label, pending, testid }) {
  return (
    <button onClick={onClick} data-testid={testid}
      className={`flex items-center gap-3 px-5 py-3 rounded-xl border transition-colors duration-300 ${active ? "bg-plate text-white border-plate" : "bg-white border-line text-ink2 hover:bg-surfacealt"}`}>
      <Icon className="w-5 h-5" strokeWidth={1.75} />
      <div className="text-left">
        <div className="font-display text-lg font-medium leading-none">{label}</div>
        <div className={`text-xs mt-1 font-mono-num ${active ? "text-white/70" : "text-warn"}`}>Pending {inr(pending)}</div>
      </div>
    </button>
  );
}

function Summary({ label, value, tone }) {
  return (
    <div className="panel p-6 ag-rise">
      <div className="overline">{label}</div>
      <div className={`kpi-value text-4xl mt-3 ${tone}`}>{value}</div>
    </div>
  );
}

function CancellationsView({ rows }) {
  const retained = rows.reduce((s, r) => s + Number(r.balance_retained || 0), 0);
  const refunded = rows.reduce((s, r) => s + Number(r.amount_refunded || 0), 0);
  return (
    <div className="space-y-6" data-testid="cancellations-view">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Summary label="Cancellations" value={rows.length} tone="text-ink" />
        <Summary label="Total Refunded" value={inr(refunded)} tone="text-warn" />
        <Summary label="Balance Retained" value={inr(retained)} tone="text-brand" />
      </div>
      <SectionCard title="Cancelled bookings" className="ag-rise">
        {rows.length === 0 ? <EmptyState icon={XCircle} title="No cancellations" hint="Cancelled bookings will appear here with paid, refunded and retained amounts." /> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="border-b border-line bg-surfacealt/40">
              <th className="th">Date</th><th className="th">Plot</th><th className="th">Buyer</th>
              <th className="th text-right">Paid</th><th className="th text-right">Refunded</th>
              <th className="th text-right">Balance retained</th><th className="th">By</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.cancellation_id} className="row" data-testid={`cancel-row-${r.plot_number}`}>
                  <td className="td font-mono-num text-ink2 whitespace-nowrap">{r.cancel_date}</td>
                  <td className="td font-mono-num font-bold">{r.plot_number}</td>
                  <td className="td text-ink2">{r.buyer_name || "—"}</td>
                  <td className="td text-right font-mono-num text-ok">{inr(r.amount_paid)}</td>
                  <td className="td text-right font-mono-num text-warn">{inr(r.amount_refunded)}</td>
                  <td className="td text-right font-mono-num font-semibold text-brand">{inr(r.balance_retained)}</td>
                  <td className="td text-ink2 text-xs">{r.cancelled_by_name || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </SectionCard>
    </div>
  );
}

const MODES = ["Bank Transfer", "NEFT", "RTGS", "IMPS", "UPI", "Cheque", "Cash", "Demand Draft", "Other"];
const HEADS = ["Booking Amount", "Installment Payment", "BSP Collection", "PLC Collection", "Registration Collection", "Maintenance Collection", "Other"];
const VBADGE = {
  pending: { t: "Awaiting verification", c: "#a8763f" },
  verified: { t: "Verified", c: "#5a6b10" },
  returned: { t: "Returned", c: "#b23b3b" },
};

function VStatus({ s }) {
  const b = VBADGE[s] || VBADGE.verified;
  return <span className="pill text-[11px]" style={{ color: b.c, backgroundColor: `${b.c}14`, borderColor: `${b.c}30` }}>{b.t}</span>;
}

function PlotDrilldown({ plot, canRecord, canVerify, onClose, onChanged }) {
  const [rows, setRows] = useState([]);
  const [components, setComponents] = useState([]);
  const [dlg, setDlg] = useState(null);       // {payment, existing?}

  const load = async () => {
    const r = await api.get("/payments", { params: { unit_id: plot.unit_id } });
    r.data.sort((a, b) => a.seq - b.seq);
    setRows(r.data);
    try {
      const [pr, un] = await Promise.all([
        api.get("/projects"),
        api.get("/units", { params: { project_id: plot.project_id } }),
      ]);
      const proj = pr.data.find(p => p.project_id === plot.project_id);
      const unit = un.data.find(u => u.unit_id === plot.unit_id);
      const cols = (proj?.columns || []).filter(c => c.tag === "charge" || c.tag === "total");
      const paidByKey = {};
      r.data.forEach(p => (p.receipts || []).forEach(rc => {
        if (rc.verification_status === "verified") (rc.allocations || []).forEach(a => { paidByKey[a.key] = (paidByKey[a.key] || 0) + Number(a.amount || 0); });
      }));
      setComponents(cols.map(c => ({ key: c.key, label: c.label, amount: Number(unit?.data?.[c.key] || 0), already_paid: round2(paidByKey[c.key] || 0) })));
    } catch { /* ignore */ }
  };
  useEffect(() => { load(); }, [plot.unit_id]);

  const billed = rows.reduce((s, r) => s + Number(r.amount || 0), 0);
  const paid = rows.reduce((s, r) => s + Number(r.paid_amount || 0), 0);
  const awaiting = rows.reduce((s, r) => s + (r.receipts || []).filter(x => x.verification_status === "pending").reduce((a, x) => a + Number(x.amount || 0), 0), 0);

  const act = async (pid, rcid, decision) => {
    let reason = "";
    if (decision === "no") { reason = window.prompt("Reason for returning this payment:"); if (!reason) return; }
    try {
      await api.post(`/payments/${pid}/receipts/${rcid}/verify`, { decision, reason });
      toast.success(decision === "yes" ? "Payment verified" : "Payment returned");
      load(); onChanged();
    } catch (e) { toast.error(apiError(e)); }
  };

  const downloadReport = async () => {
    try {
      toast.info("Generating report…");
      await downloadFile(`/units/${plot.unit_id}/payment-report`, `Payment_Report_${plot.plot_number}.pdf`);
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <Modal size="xl" title={`Plot ${plot.plot_number} · ${plot.buyer_name || ""}`}
      subtitle={`Billed ${inr(billed)} · Verified received ${inr(paid)} · Awaiting ${inr(awaiting)} · Official balance ${inr(billed - paid)}`}
      onClose={onClose}
      footer={<div className="flex items-center justify-between w-full gap-2">
        <button onClick={downloadReport} className="btn-secondary" data-testid={`download-report-${plot.unit_id}`}>
          <Download className="w-4 h-4" /> Download Payment Report
        </button>
        <button onClick={onClose} className="btn-secondary">Close</button>
      </div>}>
      <div className="space-y-3">
        {rows.map((r) => {
          const bal = round2(Number(r.amount) - Number(r.paid_amount || 0));
          return (
            <div key={r.payment_id} className="border border-line rounded-md p-3" data-testid={`inst-row-${r.payment_id}`}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="font-semibold text-ink">{r.notes || `#${r.seq}`} <StatusPill status={r.status} /></div>
                  <div className="text-xs text-ink2 mt-0.5 font-mono-num">Due {r.due_date} · {inr(r.amount)} · Verified {inr(r.paid_amount)} · Balance {inr(bal)}</div>
                </div>
                {canRecord && r.status !== "received" && (
                  <button onClick={() => setDlg({ payment: r })} className="btn-primary text-xs py-1.5" data-testid={`receipt-btn-${r.payment_id}`}>
                    <Receipt className="w-3.5 h-3.5" /> Record payment
                  </button>
                )}
              </div>
              {(r.receipts || []).length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {r.receipts.map((rc) => (
                    <div key={rc.receipt_id} className="flex items-center justify-between gap-2 text-xs bg-surfacealt/50 rounded px-2.5 py-1.5" data-testid={`rc-${rc.receipt_id}`}>
                      <div className="min-w-0">
                        <span className="font-mono-num font-semibold text-ink">{inr(rc.amount)}</span>
                        <span className="text-ink2"> · {rc.date} · {rc.mode}{rc.head ? ` · ${rc.head}` : ""}{rc.notes ? ` · ${rc.notes}` : ""}</span>
                        {rc.verification_status === "returned" && rc.return_reason && <span className="text-bad"> · {rc.return_reason}</span>}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <VStatus s={rc.verification_status} />
                        {canVerify && rc.verification_status === "pending" && (<>
                          <button onClick={() => act(r.payment_id, rc.receipt_id, "yes")} className="text-ok font-semibold hover:underline" data-testid={`verify-yes-${rc.receipt_id}`}>YES</button>
                          <button onClick={() => act(r.payment_id, rc.receipt_id, "no")} className="text-bad font-semibold hover:underline" data-testid={`verify-no-${rc.receipt_id}`}>NO</button>
                        </>)}
                        {canRecord && rc.verification_status === "returned" && (
                          <button onClick={() => setDlg({ payment: r, existing: rc })} className="text-brand font-semibold hover:underline" data-testid={`correct-${rc.receipt_id}`}>Correct</button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {dlg && (
        <ReceiptDialog payment={dlg.payment} existing={dlg.existing} components={components}
          onClose={() => setDlg(null)} onSaved={() => { setDlg(null); load(); onChanged(); }} />
      )}
    </Modal>
  );
}

function ReceiptDialog({ payment, existing, components, onClose, onSaved }) {
  const remaining = round2(Number(payment.amount) - Number(payment.paid_amount || 0));
  const [amount, setAmount] = useState(existing ? existing.amount : remaining);
  const [date, setDate] = useState(existing?.date || new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState(existing?.notes || "");
  const [mode, setMode] = useState(existing?.mode || "");
  const [head, setHead] = useState(existing?.head || "");
  const [expDate, setExpDate] = useState(existing?.expected_remaining_date || "");
  const [alloc, setAlloc] = useState(() => {
    const m = {}; (existing?.allocations || []).forEach(a => { m[a.key] = a.amount; }); return m;
  });
  const [busy, setBusy] = useState(false);

  const selected = components.filter(c => alloc[c.key] !== undefined);
  const allocTotal = round2(Object.values(alloc).reduce((s, v) => s + Number(v || 0), 0));
  const isPartial = Number(amount) > 0 && Number(amount) < remaining - 0.01;
  const toggle = (c) => setAlloc(p => { const n = { ...p }; if (n[c.key] !== undefined) delete n[c.key]; else n[c.key] = round2(Math.max(0, c.amount - c.already_paid)); return n; });

  const save = async () => {
    if (!amount || Number(amount) <= 0) return toast.error("Enter a payment amount");
    if (!mode) return toast.error("Select a mode of payment");
    if (selected.length > 0 && Math.abs(allocTotal - Number(amount)) > 0.01) return toast.error(`Component allocation (${inr(allocTotal)}) must equal amount received (${inr(Number(amount))})`);
    if (isPartial && !expDate) return toast.error("Enter the expected date for the remaining payment");
    setBusy(true);
    const body = {
      amount: Number(amount), date, notes, mode, head,
      allocations: selected.map(c => ({ key: c.key, label: c.label, amount: Number(alloc[c.key] || 0) })),
      expected_remaining_date: isPartial ? expDate : null,
    };
    try {
      if (existing) await api.patch(`/payments/${payment.payment_id}/receipts/${existing.receipt_id}`, body);
      else await api.post(`/payments/${payment.payment_id}/receipt`, body);
      toast.success(existing ? "Payment corrected & resubmitted" : "Payment submitted for verification");
      onSaved();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal size="lg" title={`${existing ? "Correct" : "Record"} payment · ${payment.notes || `#${payment.seq}`}`}
      subtitle={`Instalment ${inr(payment.amount)} · verified ${inr(payment.paid_amount)} · balance ${inr(remaining)}`}
      onClose={onClose}
      footer={<>
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={busy} className="btn-primary" data-testid="receipt-submit">{busy ? "Saving…" : (existing ? "Resubmit" : "Submit to Accounts")}</button>
      </>}>
      <div className="space-y-4">
        {existing && existing.return_reason && (
          <div className="text-xs bg-bad/10 border border-bad/30 rounded px-3 py-2 text-bad">Returned: {existing.return_reason}{existing.return_notes ? ` — ${existing.return_notes}` : ""}</div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div><label className="label">Amount received</label>
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="input font-mono-num" data-testid="receipt-amount" /></div>
          <div><label className="label">Received on</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input font-mono-num" data-testid="receipt-date" /></div>
          <div><label className="label">Mode of payment *</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)} className="input" data-testid="receipt-mode">
              <option value="">— select —</option>{MODES.map(m => <option key={m} value={m}>{m}</option>)}
            </select></div>
          <div><label className="label">Payment head</label>
            <select value={head} onChange={(e) => setHead(e.target.value)} className="input" data-testid="receipt-head">
              <option value="">— select —</option>{HEADS.map(h => <option key={h} value={h}>{h}</option>)}
            </select></div>
        </div>
        <div><label className="label">Reference / notes</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} className="input" placeholder="UTR, cheque no, bank ref…" data-testid="receipt-notes" /></div>

        {components.length > 0 && (
          <div>
            <label className="label">Component allocation (optional — must total the amount)</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {components.map(c => (
                <button key={c.key} onClick={() => toggle(c)} data-testid={`comp-${c.key}`}
                  className={`pill text-xs ${alloc[c.key] !== undefined ? "bg-plate text-white border-plate" : "text-ink2"}`}>{c.label}</button>
              ))}
            </div>
            {selected.length > 0 && (
              <div className="border border-line rounded-md overflow-x-auto"><table className="w-full">
                <thead><tr className="bg-surfacealt/60 border-b border-line"><th className="th py-1.5">Component</th><th className="th py-1.5 text-right">Outstanding</th><th className="th py-1.5 text-right">Allocate</th></tr></thead>
                <tbody>
                  {selected.map(c => (
                    <tr key={c.key} className="border-b border-line last:border-0">
                      <td className="td py-1.5">{c.label}</td>
                      <td className="td py-1.5 text-right font-mono-num text-ink2">{inr(round2(c.amount - c.already_paid))}</td>
                      <td className="td py-1.5 text-right"><input type="number" value={alloc[c.key]} onChange={(e) => setAlloc(p => ({ ...p, [c.key]: e.target.value }))} className="input text-right font-mono-num py-1 w-32" data-testid={`alloc-${c.key}`} /></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot><tr className="bg-surfacealt/40"><td className="px-3 py-1.5 text-sm font-semibold" colSpan={2}>Allocated</td><td className={`px-3 py-1.5 text-right font-mono-num font-bold ${Math.abs(allocTotal - Number(amount)) > 0.01 ? "text-bad" : "text-ok"}`}>{inr(allocTotal)}</td></tr></tfoot>
              </table></div>
            )}
          </div>
        )}
        {isPartial && (
          <div><label className="label">Expected date for remaining {inr(remaining - Number(amount))} *</label>
            <input type="date" value={expDate} onChange={(e) => setExpDate(e.target.value)} className="input font-mono-num" data-testid="receipt-expdate" /></div>
        )}
      </div>
    </Modal>
  );
}

function VerificationQueue({ rows, canVerify, onChanged }) {
  const [f, setF] = useState("pending");
  const list = rows.filter(r => r.verification_status === f);
  const act = async (r, decision) => {
    let reason = "";
    if (decision === "no") { reason = window.prompt("Reason for returning this payment:"); if (!reason) return; }
    try {
      await api.post(`/payments/${r.payment_id}/receipts/${r.receipt_id}/verify`, { decision, reason });
      toast.success(decision === "yes" ? "Payment verified" : "Payment returned");
      onChanged();
    } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="space-y-4" data-testid="verification-view">
      <div className="flex flex-wrap gap-2">
        {["pending", "returned", "verified"].map(s => (
          <button key={s} onClick={() => setF(s)} data-testid={`vfilter-${s}`}
            className={`pill text-xs capitalize ${f === s ? "bg-plate text-white border-plate" : "text-ink2"}`}>{s} ({rows.filter(r => r.verification_status === s).length})</button>
        ))}
      </div>
      <SectionCard title="Payment verification queue">
        {list.length === 0 ? <EmptyState icon={ShieldCheck} title="Nothing here" hint="Payments submitted by Post Sales appear here for confirmation." /> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr className="border-b border-line bg-surfacealt/40">
              <th className="th">Plot</th><th className="th">Customer</th><th className="th">Instalment</th>
              <th className="th text-right">Amount</th><th className="th">Mode</th><th className="th">Date</th><th className="th">By</th>
              {canVerify && <th className="th text-right">Decision</th>}
            </tr></thead>
            <tbody>
              {list.map(r => (
                <tr key={r.receipt_id} className="row" data-testid={`vq-${r.receipt_id}`}>
                  <td className="td font-mono-num font-bold">{r.plot_number}<div className="text-[10px] text-ink2 font-sans">{r.project_name}</div></td>
                  <td className="td text-ink2">{r.buyer_name || "—"}</td>
                  <td className="td">{r.instalment}{r.return_reason && <div className="text-[10px] text-bad">↩ {r.return_reason}</div>}</td>
                  <td className="td text-right font-mono-num font-semibold">{inr(r.amount)}</td>
                  <td className="td text-xs">{r.mode}{r.head ? <div className="text-[10px] text-ink2">{r.head}</div> : null}</td>
                  <td className="td font-mono-num text-ink2 whitespace-nowrap">{r.date}</td>
                  <td className="td text-xs text-ink2">{r.submitted_by_name}</td>
                  {canVerify && (
                    <td className="td text-right whitespace-nowrap">
                      {r.verification_status === "pending" ? (<>
                        <button onClick={() => act(r, "yes")} className="text-ok font-bold hover:underline mr-3" data-testid={`vq-yes-${r.receipt_id}`}>YES</button>
                        <button onClick={() => act(r, "no")} className="text-bad font-bold hover:underline" data-testid={`vq-no-${r.receipt_id}`}>NO</button>
                      </>) : <VStatus s={r.verification_status} />}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </SectionCard>
    </div>
  );
}

const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
