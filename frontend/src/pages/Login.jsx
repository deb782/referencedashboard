import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { apiError } from "@/lib/api";

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (user && !user.must_reset_password) {
    nav("/dashboard", { replace: true });
  }

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
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="card w-full max-w-md p-8">
        <div className="text-center mb-6">
          <div className="text-2xl font-bold text-emerald-900">Agrocorp Lite</div>
          <div className="text-sm text-stone-500 mt-1">Stakeholder console — sign in</div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Phone number</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)}
                   placeholder="9999999999" className="input" data-testid="login-phone" />
          </div>
          <div>
            <label className="label">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   placeholder="Your password" className="input" data-testid="login-password" />
            <div className="text-xs text-stone-500 mt-1">First-time users: initial password is your phone number.</div>
          </div>
          <button type="submit" disabled={busy} className="btn-primary w-full" data-testid="login-submit">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
