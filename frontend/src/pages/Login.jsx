import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiError } from "@/lib/api";

const BG = "https://images.unsplash.com/photo-1771131825971-af45a242808c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwxfHxhZXJpYWwlMjB2aWV3JTIwbGFuZCUyMHBsb3QlMjBuYXR1cmV8ZW58MHx8fHwxNzg2MDA1NTk5fDA&ixlib=rb-4.1.0&q=85";

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
    <div className="min-h-screen grid lg:grid-cols-2 bg-page">
      {/* Left: brand / imagery */}
      <div className="relative hidden lg:block overflow-hidden">
        <img src={BG} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-brand/80 mix-blend-multiply" />
        <div className="absolute inset-0 bg-gradient-to-t from-brand-hover via-transparent to-transparent" />
        <div className="relative h-full flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-sm bg-white flex items-center justify-center overflow-hidden shrink-0">
              <img src="/agrocorp-logo.webp" alt="Agrocorp" className="w-full h-full object-contain p-1" />
            </div>
            <div>
              <div className="font-display font-extrabold text-xl tracking-tight">Management Dashboard</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-white/70 font-semibold">Stakeholder Console</div>
            </div>
          </div>
          <div className="max-w-lg">
            <div className="bg-white rounded-sm p-8 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.4)]">
              <img src="/companies-logo.png" alt="Agrocorp · Vacation Village · Landshare" className="w-full h-auto" />
            </div>
            <p className="text-white/80 mt-6 text-sm leading-relaxed">Real-time visibility into financial, operational, sales, and project performance.</p>
          </div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-white/50 font-semibold">Agrocorp · Vacation Village · Landshare</div>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm ag-rise">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-sm bg-white border border-agborder flex items-center justify-center overflow-hidden"><img src="/agrocorp-logo.webp" alt="Agrocorp" className="w-full h-full object-contain p-1" /></div>
            <div className="font-display font-extrabold text-xl text-ink">Management Dashboard</div>
          </div>
          <div className="overline mb-2">Stakeholder Console</div>
          <h2 className="font-display text-3xl font-bold text-ink tracking-tight">Sign in</h2>
          <p className="text-sm text-ink2 mt-2">Use your phone number and password.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="label">Phone number</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="9999999999"
                     className="input font-mono-num" data-testid="login-phone" />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                     placeholder="Your password" className="input" data-testid="login-password" />
              <div className="text-xs text-ink2 mt-2">Your password is your phone number for the first time setup.</div>
            </div>
            <button type="submit" disabled={busy} className="btn-primary w-full py-2.5 group" data-testid="login-submit">
              {busy ? "Signing in…" : <>Sign in <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5" /></>}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
