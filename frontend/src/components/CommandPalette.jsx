import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, CornerDownLeft, ArrowRight, Home, Building2, Package, Boxes, User as UserIcon } from "lucide-react";
import { api } from "@/lib/api";

const RESULT_ICON = { unit: Home, project: Building2, procurement: Package, inventory: Boxes, user: UserIcon };
const RESULT_LABEL = { unit: "Plot", project: "Project", procurement: "Procurement", inventory: "Inventory", user: "Team" };

export default function CommandPalette({ open, onClose, navItems = [] }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => { if (open) { setQ(""); setResults([]); setActive(0); setTimeout(() => inputRef.current?.focus(), 20); } }, [open]);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); setLoading(false); return; }
    setLoading(true);
    const t = setTimeout(async () => {
      try { const r = await api.get("/search", { params: { q } }); setResults(r.data.results || []); }
      catch { setResults([]); }
      finally { setLoading(false); }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const navMatches = useMemo(() => {
    const s = q.trim().toLowerCase();
    return navItems.filter(n => !s || n.label.toLowerCase().includes(s)).map(n => ({ kind: "nav", ...n }));
  }, [q, navItems]);

  const flat = useMemo(() => [
    ...navMatches,
    ...results.map(r => ({ kind: "result", ...r })),
  ], [navMatches, results]);

  useEffect(() => { setActive(0); }, [q, results.length]);

  const run = (item) => {
    onClose();
    if (item.kind === "nav") nav(item.to);
    else nav(item.link);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive(a => Math.min(a + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && flat[active]) { e.preventDefault(); run(flat[active]); }
    else if (e.key === "Escape") { onClose(); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh] bg-plate/40" onMouseDown={onClose} data-testid="command-palette">
      <div className="w-full max-w-2xl bg-white border border-line rounded-2xl shadow-[0_40px_120px_-30px_rgba(20,21,20,0.45)] overflow-hidden ag-modal"
        onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-5 border-b border-line">
          <Search className="w-4 h-4 text-ink2 shrink-0" strokeWidth={1.75} />
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
            placeholder="Search plots, buyers, projects — or jump to a section"
            className="flex-1 bg-transparent py-4 text-[15px] text-ink placeholder:text-ink2/60 focus:outline-none"
            data-testid="command-input" />
          <span className="kbd2 shrink-0">ESC</span>
        </div>

        <div className="max-h-[52vh] overflow-y-auto py-2">
          {navMatches.length > 0 && (
            <Group title="Jump to">
              {navMatches.map((n, i) => {
                const Icon = n.icon;
                return (
                  <Row key={n.to} active={active === i} onHover={() => setActive(i)} onClick={() => run(n)} testid={`cmd-nav-${n.to.replace("/", "")}`}>
                    <Icon className="w-4 h-4 text-ink2" strokeWidth={1.75} />
                    <span className="flex-1 text-sm text-ink">{n.label}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-ink2/60" />
                  </Row>
                );
              })}
            </Group>
          )}

          {q.trim().length >= 2 && (
            <Group title={loading ? "Searching…" : `Records${results.length ? ` · ${results.length}` : ""}`}>
              {!loading && results.length === 0 && <div className="px-5 py-3 text-sm text-ink2">No records match “{q}”.</div>}
              {results.map((r, idx) => {
                const i = navMatches.length + idx;
                const Icon = RESULT_ICON[r.type] || Search;
                return (
                  <Row key={`${r.type}-${r.id}`} active={active === i} onHover={() => setActive(i)} onClick={() => run({ kind: "result", ...r })} testid={`cmd-result-${r.type}-${r.id}`}>
                    <span className="w-6 h-6 rounded-md bg-brand/[0.08] border border-brand/15 flex items-center justify-center shrink-0"><Icon className="w-3.5 h-3.5 text-brand" strokeWidth={1.75} /></span>
                    <span className="min-w-0 flex-1"><span className="block text-sm text-ink truncate">{r.label}</span><span className="block text-xs text-ink2 truncate">{r.sublabel}</span></span>
                    <span className="text-[10px] uppercase tracking-[0.14em] font-semibold text-ink2 shrink-0">{RESULT_LABEL[r.type]}</span>
                  </Row>
                );
              })}
            </Group>
          )}

          {q.trim().length < 2 && navMatches.length === 0 && (
            <div className="px-5 py-6 text-sm text-ink2">Start typing to search.</div>
          )}
        </div>

        <div className="flex items-center gap-4 px-5 py-2.5 border-t border-line bg-surfacealt/40 text-[11px] text-ink2">
          <span className="flex items-center gap-1.5"><span className="kbd2">↑</span><span className="kbd2">↓</span> navigate</span>
          <span className="flex items-center gap-1.5"><span className="kbd2"><CornerDownLeft className="w-2.5 h-2.5 inline" /></span> open</span>
        </div>
      </div>
    </div>
  );
}

function Group({ title, children }) {
  return (
    <div className="px-2">
      <div className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-[0.18em] font-semibold text-ink2/70">{title}</div>
      {children}
    </div>
  );
}

function Row({ active, onHover, onClick, children, testid }) {
  return (
    <button onMouseEnter={onHover} onClick={onClick} data-testid={testid}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors duration-150 ${active ? "bg-surfacealt" : "hover:bg-surfacealt/60"}`}>
      {children}
    </button>
  );
}
