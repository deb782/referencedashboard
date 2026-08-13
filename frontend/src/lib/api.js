import axios from "axios";

export const API_BASE = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export function apiError(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || String(x)).join(" · ");
  return e?.message || "Something went wrong";
}

export function fileUrl(fileId) {
  const token = localStorage.getItem("token");
  return `${API_BASE}/api/files/${fileId}/download?token=${encodeURIComponent(token || "")}`;
}

export async function fetchPdfUrl(path) {
  const res = await api.get(path, { responseType: "blob" });
  return window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
}

export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const url = window.URL.createObjectURL(
    new Blob([res.data], { type: res.headers["content-type"] || "application/pdf" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(url);
}
