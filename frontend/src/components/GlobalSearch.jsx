import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Home, Building2, Package, Boxes, User as UserIcon, CornerDownLeft } from "lucide-react";
import { api } from "@/lib/api";

const ICONS = {
  unit: Home, project: Building2, procurement: Package, inventory: Boxes, user: UserIcon,
};
const TYPE_LABEL = {
  unit: "Plot", project: "Project", procurement: "Procurement", inventory: "Inventory", user: "Team",
};

export default function GlobalSearch() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await api.get("/search", { params: { q } });
        setResults(r.data.results || []);
        setActive(0);
      } catch { setResults([]); }
      finally { setLoading(false); }
    }, 220);
    return () => clearTimeout(t);
  }, [q]);

  const go = (item) => {
    setOpen(false); setQ("");
    nav(item.link);
  };

  const onKeyDown = (e) => {
    if (!open) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === "Enter" && results[active]) { e.preventDefault(); go(results[active]); }
  };

  return (
    <div className="relative w-full max-w-md" ref={boxRef}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink2 pointer-events-none" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search plots, buyers, projects, procurement…"
          className="w-full rounded-md border border-agborder bg-surfacealt/60 pl-9 pr-16 py-2 text-sm text-ink placeholder:text-ink2/70 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand focus:bg-white transition-colors duration-300"
          data-testid="global-search-input"
        />
        <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden md:flex items-center gap-0.5 text-[10px] font-mono-num text-ink2 border border-agborder rounded px-1.5 py-0.5 bg-white">⌘K</kbd>
      </div>

      {open && q.trim().length >= 2 && (
        <div className="absolute left-0 right-0 top-12 bg-white border border-agborder rounded-lg shadow-strong z-50 ag-modal overflow-hidden" data-testid="search-panel">
          {loading && results.length === 0 && <div className="px-4 py-5 text-sm text-ink2">Searching…</div>}
          {!loading && results.length === 0 && <div className="px-4 py-5 text-sm text-ink2">No matches for “{q}”.</div>}
          <div className="max-h-[420px] overflow-y-auto py-1">
            {results.map((r, i) => {
              const Icon = ICONS[r.type] || Search;
              return (
                <button
                  key={`${r.type}-${r.id}`}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(r)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors duration-150 ${i === active ? "bg-surfacealt" : "hover:bg-surfacealt/60"}`}
                  data-testid={`search-result-${r.type}-${r.id}`}
                >
                  <div className="w-8 h-8 rounded-md bg-brand/[0.08] border border-brand/15 flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-brand" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-ink truncate">{r.label}</div>
                    <div className="text-xs text-ink2 truncate">{r.sublabel}</div>
                  </div>
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-ink2 shrink-0">{TYPE_LABEL[r.type]}</span>
                  {i === active && <CornerDownLeft className="w-3.5 h-3.5 text-ink2 shrink-0" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
