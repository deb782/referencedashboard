import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Sprout, ShieldCheck } from "lucide-react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ResetPassword() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  if (!user) { nav("/login", { replace: true }); return null; }

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 8) return toast.error("New password must be at least 8 characters");
    if (next !== confirm) return toast.error("New passwords don't match");
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      const updated = { ...user, must_reset_password: false };
      localStorage.setItem("user", JSON.stringify(updated));
      setUser(updated);
      toast.success("Password updated");
      nav("/dashboard", { replace: true });
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-page p-6">
      <div className="w-full max-w-md ag-rise">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-sm bg-brand flex items-center justify-center"><Sprout className="w-6 h-6 text-white" /></div>
          <div className="font-display font-extrabold text-xl text-ink">Agrocorp Lite</div>
        </div>
        <div className="card p-8">
          <div className="w-11 h-11 rounded-sm bg-brand/[0.08] border border-brand/15 flex items-center justify-center mb-5">
            <ShieldCheck className="w-5 h-5 text-brand" />
          </div>
          <h1 className="font-display text-2xl font-bold text-ink tracking-tight">Set a new password</h1>
          <p className="text-sm text-ink2 mt-2 mb-6">
            {user.must_reset_password
              ? "This is your first login. Set a permanent password before continuing."
              : "Change your password."}
          </p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Current password <span className="normal-case tracking-normal font-normal text-ink2">(phone number for first login)</span></label>
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="input" data-testid="rp-current" />
            </div>
            <div>
              <label className="label">New password (min. 8 characters)</label>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} className="input" data-testid="rp-new" />
            </div>
            <div>
              <label className="label">Confirm new password</label>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input" data-testid="rp-confirm" />
            </div>
            <button type="submit" disabled={busy} className="btn-primary w-full py-2.5" data-testid="rp-submit">
              {busy ? "Saving…" : "Save & continue"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
