import { Link } from "react-router-dom";

export const inr = (n) =>
  "\u20B9" + (Number(n) || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const num2 = (n) =>
  (Number(n) || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const inrCompact = (n) => {
  const v = Number(n) || 0;
  if (v >= 1e7) return "\u20B9" + (v / 1e7).toFixed(2) + " Cr";
  if (v >= 1e5) return "\u20B9" + (v / 1e5).toFixed(2) + " L";
  return inr(v);
};

export function PageHeader({ overline, title, subtitle, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
      <div>
        {overline && <div className="overline mb-1">{overline}</div>}
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="text-sm text-ink2 mt-1.5 max-w-xl">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

const TONES = {
  brand: "text-brand",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  clay: "text-clay",
  ink: "text-ink",
};

export function Kpi({ label, value, sub, icon: Icon, tone = "ink", accent, className = "", mono = true }) {
  return (
    <div className={`card p-6 flex flex-col justify-between relative overflow-hidden ${className}`}>
      {accent && <div className="absolute top-0 left-0 h-full w-1" style={{ background: accent }} />}
      <div className="flex items-start justify-between">
        <div className="overline">{label}</div>
        {Icon && <Icon className={`w-5 h-5 ${TONES[tone]} opacity-70`} strokeWidth={2} />}
      </div>
      <div className="mt-6">
        <div className={`font-display font-extrabold tracking-tighter leading-none text-4xl md:text-5xl ${TONES[tone]} ${mono ? "font-mono-num" : ""}`}>
          {value}
        </div>
        {sub && <div className="text-xs text-ink2 mt-2">{sub}</div>}
      </div>
    </div>
  );
}

const STATUS_STYLES = {
  available: { c: "#5a6b10", label: "Available" },
  sold: { c: "#3d4a0a", label: "Sold" },
  pending: { c: "#c8912f", label: "Pending" },
  partial: { c: "#a8763f", label: "Partial" },
  received: { c: "#5a6b10", label: "Received" },
  overdue: { c: "#a33b28", label: "Overdue" },
  pending_admin: { c: "#c8912f", label: "Awaiting Admin" },
  pending_clarification: { c: "#a8763f", label: "Needs Clarification" },
  approved: { c: "#5a6b10", label: "Approved" },
  po_issued: { c: "#3d4a0a", label: "PO Issued" },
  paid: { c: "#3d4a0a", label: "Paid" },
  rejected: { c: "#a33b28", label: "Rejected" },
  low: { c: "#718096", label: "Low" },
  medium: { c: "#5a6b10", label: "Medium" },
  high: { c: "#c8912f", label: "High" },
  urgent: { c: "#a33b28", label: "Urgent" },
};

export function StatusPill({ status, label, dot = true }) {
  const s = STATUS_STYLES[status] || { c: "#5C5C58", label: label || status };
  return (
    <span className="pill" style={{ color: s.c, backgroundColor: `${s.c}14`, borderColor: `${s.c}33` }}>
      {dot && <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.c }} />}
      {label || s.label}
    </span>
  );
}

export function EmptyState({ icon: Icon, title, hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {Icon && (
        <div className="w-12 h-12 rounded-sm bg-surfacealt border border-agborder flex items-center justify-center mb-4">
          <Icon className="w-5 h-5 text-ink2" />
        </div>
      )}
      <div className="font-display font-semibold text-ink">{title}</div>
      {hint && <div className="text-sm text-ink2 mt-1 max-w-sm">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function SectionCard({ title, action, children, className = "", bodyClass = "" }) {
  return (
    <div className={`card ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-agborder">
          <div className="overline text-ink">{title}</div>
          {action}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </div>
  );
}

export function LinkPill({ to, children }) {
  return (
    <Link to={to} className="text-xs font-semibold text-brand hover:text-brand-hover transition-colors duration-200">
      {children}
    </Link>
  );
}

export function Modal({ title, subtitle, onClose, children, footer, size = "md" }) {
  const w = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-3xl" }[size] || "max-w-lg";
  return (
    <div className="fixed inset-0 bg-ink/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className={`card w-full ${w} max-h-[92vh] flex flex-col ag-modal shadow-[0_24px_70px_-12px_rgba(20,21,20,0.35)]`} onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b border-agborder">
          <div className="font-display text-lg font-bold text-ink tracking-tight">{title}</div>
          {subtitle && <div className="text-sm text-ink2 mt-0.5">{subtitle}</div>}
        </div>
        <div className="px-6 py-5 overflow-y-auto">{children}</div>
        {footer && <div className="px-6 py-4 border-t border-agborder flex justify-end gap-2 bg-surfacealt/40">{footer}</div>}
      </div>
    </div>
  );
}

