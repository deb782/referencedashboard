import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
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
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="card w-full max-w-md p-8">
        <div className="text-2xl font-bold text-emerald-900">Set a new password</div>
        <div className="text-sm text-stone-500 mt-1 mb-6">
          {user.must_reset_password
            ? "This is your first login. Please set a permanent password before continuing."
            : "Change your password."}
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Current password (your phone number for first login)</label>
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
          <button type="submit" disabled={busy} className="btn-primary w-full" data-testid="rp-submit">
            {busy ? "Saving…" : "Save & continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
