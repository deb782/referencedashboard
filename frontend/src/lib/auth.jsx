import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("user") || "null"); }
    catch { return null; }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const t = localStorage.getItem("token");
      if (!t) return setLoading(false);
      try {
        const r = await api.get("/auth/me");
        setUser(r.data);
        localStorage.setItem("user", JSON.stringify(r.data));
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const login = async (phone, password) => {
    const r = await api.post("/auth/login", { phone, password });
    localStorage.setItem("token", r.data.access_token);
    localStorage.setItem("user", JSON.stringify(r.data.user));
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export const ROLE_LABELS = {
  admin: "Admin",
  accounts: "Accounts",
  post_sales: "Post-Sales Rep",
  site_manager: "Site Manager",
};

export const can = (user, ...roles) => user && roles.includes(user.role);
