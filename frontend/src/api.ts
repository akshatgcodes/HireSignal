import type { Application, Company, CompanyDetail, Dashboard, Detected, Digest, Run, Signal, Status } from "./types";

// Empty in dev (Vite proxies /api). Set VITE_API_URL when the API is elsewhere.
export const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, credentials: "include" });
  } catch {
    throw new ApiError(0, "Can't reach the HireSignal server");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    // FastAPI validation errors come as a list
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : res.statusText;
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export type ApplicationInput = Partial<Omit<Application, "id" | "company" | "position" | "status_changed_at">> & {
  company_name?: string;
};
export type CompanyInput = Partial<Pick<Company, "name" | "careers_url" | "board" | "board_slug" | "news_query">>;
export type SignalFilter = { company_id?: number; sentiment?: string; source?: string; unread?: boolean; limit?: number };

const qs = (params: Record<string, unknown>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "" && v !== false) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  me: () => request<{ owner: boolean }>("/api/auth/me"),
  login: (password: string) => request("/api/auth/login", json("POST", { password })),
  logout: () => request("/api/auth/logout", json("POST")),

  dashboard: () => request<Dashboard>("/api/dashboard"),

  applications: () => request<Application[]>("/api/applications"),
  createApplication: (body: ApplicationInput) => request<Application>("/api/applications", json("POST", body)),
  updateApplication: (id: number, body: ApplicationInput) => request<Application>(`/api/applications/${id}`, json("PATCH", body)),
  moveApplication: (id: number, status: Status, index: number) =>
    request<Application>(`/api/applications/${id}/move`, json("POST", { status, index })),
  removeApplication: (id: number) => request<void>(`/api/applications/${id}`, { method: "DELETE" }),

  companies: () => request<Company[]>("/api/companies"),
  company: (id: number) => request<CompanyDetail>(`/api/companies/${id}`),
  detect: (url: string) => request<Detected>("/api/companies/detect", json("POST", { url })),
  createCompany: (body: CompanyInput) => request<Company>("/api/companies", json("POST", body)),
  updateCompany: (id: number, body: CompanyInput) => request<Company>(`/api/companies/${id}`, json("PATCH", body)),
  removeCompany: (id: number) => request<void>(`/api/companies/${id}`, { method: "DELETE" }),
  scanCompany: (id: number) => request<{ run_id: number }>(`/api/companies/${id}/scan`, json("POST")),

  signals: (f: SignalFilter = {}) => request<Signal[]>(`/api/signals${qs(f)}`),
  markRead: (id: number, read = true) => request(`/api/signals/${id}/read?read=${read}`, json("POST")),
  markAllRead: (company_id?: number) => request<{ updated: number }>(`/api/signals/read-all${qs({ company_id })}`, json("POST")),

  runs: () => request<Run[]>("/api/runs"),
  run: (id: number) => request<Run>(`/api/runs/${id}`),
  scanAll: () => request<{ run_id: number }>("/api/runs", json("POST")),
  digests: () => request<Digest[]>("/api/digests"),
  digest: (id: number) => request<Digest>(`/api/digests/${id}`),
  sendDigest: () => request<Digest>("/api/digests", json("POST")),
};
