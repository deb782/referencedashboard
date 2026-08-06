import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import ResetPassword from "@/pages/ResetPassword";
import Dashboard from "@/pages/Dashboard";
import Projects from "@/pages/Projects";
import UsersPage from "@/pages/Users";
import Units from "@/pages/Units";
import Sales from "@/pages/Sales";
import Inventory from "@/pages/Inventory";
import Procurement from "@/pages/Procurement";

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-12 text-center text-stone-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_reset_password && window.location.pathname !== "/reset-password") {
    return <Navigate to="/reset-password" replace />;
  }
  if (roles && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
        <Route path="/projects" element={<Protected roles={["admin"]}><Projects /></Protected>} />
        <Route path="/users" element={<Protected roles={["admin"]}><UsersPage /></Protected>} />
        <Route path="/units" element={<Protected roles={["admin","post_sales"]}><Units /></Protected>} />
        <Route path="/sales" element={<Protected roles={["admin","post_sales","accounts"]}><Sales /></Protected>} />
        <Route path="/inventory" element={<Protected roles={["admin","site_manager"]}><Inventory /></Protected>} />
        <Route path="/procurement" element={<Protected roles={["admin","site_manager","accounts"]}><Procurement /></Protected>} />
      </Routes>
    </AuthProvider>
  );
}
