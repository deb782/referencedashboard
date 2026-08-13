import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiError } from "@/lib/api";

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (user && !user.must_reset_password) return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await login(phone, password);
      toast.success(`Welcome, ${u.name}`);
      nav(u.must_reset_password ? "/reset-password" : "/dashboard", { replace: true });
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-page">
      {/* Left: dark editorial brand canvas */}
      <div className="relative hidden lg:flex flex-col justify-between p-14 bg-plate text-white overflow-hidden">
        <div className="grid-canvas absolute inset-0 opacity-[0.12]" style={{ backgroundImage: "radial-gradient(#ffffff 1px, transparent 1px)" }} />
        <span className="absolute left-14 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full" style={{ background: "#ccff00" }} />

        {/* Brand */}
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
            <img src="/agrocorp-arch-white.webp" alt="" className="w-6 h-6 object-contain" />
          </div>
          <div className="leading-none">
            <div className="font-display text-lg font-semibold tracking-tight">Management Dashboard</div>
            <div className="text-[9.5px] uppercase tracking-[0.22em] text-white/50 font-semibold mt-1.5">Stakeholder Console</div>
          </div>
        </div>

        {/* Center lockup */}
        <div className="relative flex flex-col items-center justify-center text-center px-8">
          <img src="/group-logo-white.webp" alt="Agrocorp · Vacation Village · Landshare — real estate reimagined" className="w-auto max-h-40 xl:max-h-48 object-contain" />
          <p className="text-white/60 mt-10 text-sm leading-relaxed max-w-md">
            Real-time visibility into financial, operational, sales, and project performance.
          </p>
        </div>

        {/* Footer */}
        <div className="relative text-[11px] uppercase tracking-[0.22em] text-white/40 font-semibold">
          Agrocorp · Vacation Village · Landshare
        </div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm ag-rise">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-11 h-11 rounded-xl brandplate"><img src="/agrocorp-arch-white.webp" alt="Agrocorp" className="w-7 h-7 object-contain" /></div>
            <div className="leading-none">
              <div className="font-display text-xl font-semibold text-ink tracking-tight">Management Dashboard</div>
              <div className="text-[9.5px] uppercase tracking-[0.22em] text-ink2 font-semibold mt-0.5">Stakeholder Console</div>
            </div>
          </div>

          <div className="overline mb-3">Stakeholder Console</div>
          <h2 className="font-display text-5xl font-medium text-ink tracking-tight leading-none">Sign in</h2>
          <p className="text-sm text-ink2 mt-3">Enter your phone number and password to continue.</p>

          <form onSubmit={submit} className="mt-10 space-y-5">
            <div>
              <label className="label">Phone number</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="9999999999"
                     className="input font-mono-num py-2.5" data-testid="login-phone" />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                     placeholder="Your password" className="input py-2.5" data-testid="login-password" />
              <div className="text-xs text-ink2 mt-2">Your password is your phone number for the first time setup.</div>
            </div>
            <button type="submit" disabled={busy} className="btn-primary w-full py-3 group" data-testid="login-submit">
              {busy ? "Signing in…" : <>Sign in <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5" /></>}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
