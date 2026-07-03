import type {
  User,
  JobOut,
  JobIn,
  ExpenseOut,
  ExpenseIn,
  StateSummary,
  ShiftOut,
  ShiftIn,
  InsightsResponse,
  ProjectionResponse,
  HistoryResponse,
  IncomeByJob,
  EfficiencyReport,
  MonteCarloResult,
  WhatIfResult,
  OptimizeResult,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  token?: string | null;
}

function extractDetailMessage(data: unknown, status: number): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (Array.isArray(detail)) {
      // FastAPI/Pydantic validation errors: [{ msg, loc, ... }, ...]
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join(", ");
    }
    return String(detail);
  }
  return `Request failed with status ${status}`;
}

async function request<T>(path: string, { method = "GET", body, token }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Could not reach the ShiftIQ API. Is it running?");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const data: unknown = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    throw new ApiError(res.status, extractDetailMessage(data, res.status));
  }

  return data as T;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  auth: {
    register: (email: string, password: string) =>
      request<{ message: string; email: string }>("/api/auth/register", {
        method: "POST",
        body: { email, password },
      }),
    login: (email: string, password: string) =>
      request<{ access_token: string; token_type: string }>("/api/auth/login", {
        method: "POST",
        body: { email, password },
      }),
    me: (token: string) => request<User>("/api/auth/me", { token }),
  },

  state: {
    get: (token: string) => request<StateSummary>("/api/state", { token }),
    setBalance: (token: string, amount: number) =>
      request<{ balance: number; message: string }>("/api/balance", {
        method: "PUT",
        token,
        body: { amount },
      }),
  },

  jobs: {
    list: (token: string) => request<JobOut[]>("/api/jobs", { token }),
    create: (token: string, job: JobIn) => request<JobOut>("/api/jobs", { method: "POST", token, body: job }),
    update: (token: string, name: string, job: JobIn) =>
      request<JobOut>(`/api/jobs/${encodeURIComponent(name)}`, { method: "PUT", token, body: job }),
    delete: (token: string, name: string) =>
      request<{ message: string }>(`/api/jobs/${encodeURIComponent(name)}`, { method: "DELETE", token }),
  },

  expenses: {
    list: (token: string) => request<ExpenseOut[]>("/api/expenses", { token }),
    create: (token: string, expense: ExpenseIn) =>
      request<ExpenseOut>("/api/expenses", { method: "POST", token, body: expense }),
    update: (token: string, name: string, expense: ExpenseIn) =>
      request<ExpenseOut>(`/api/expenses/${encodeURIComponent(name)}`, {
        method: "PUT",
        token,
        body: expense,
      }),
    delete: (token: string, name: string) =>
      request<{ message: string }>(`/api/expenses/${encodeURIComponent(name)}`, {
        method: "DELETE",
        token,
      }),
  },

  shifts: {
    list: (token: string, day?: string) =>
      request<ShiftOut[]>(`/api/shifts${day ? `?day=${encodeURIComponent(day)}` : ""}`, { token }),
    create: (token: string, shift: ShiftIn) => request<ShiftOut>("/api/shifts", { method: "POST", token, body: shift }),
    update: (token: string, id: number, shift: ShiftIn) =>
      request<ShiftOut>(`/api/shifts/${id}`, { method: "PUT", token, body: shift }),
    delete: (token: string, id: number) => request<void>(`/api/shifts/${id}`, { method: "DELETE", token }),
  },

  history: (token: string) => request<HistoryResponse>("/api/history", { token }),

  insights: (token: string) => request<InsightsResponse>("/api/insights", { token }),

  projection: (token: string, weeks = 12) =>
    request<ProjectionResponse>(`/api/projection?weeks=${weeks}`, { token }),

  analytics: {
    income: (token: string) => request<IncomeByJob>("/api/analytics/income", { token }),
    efficiency: (token: string) => request<EfficiencyReport[]>("/api/analytics/efficiency", { token }),
  },

  simulate: {
    monteCarlo: (token: string, weeks: number, n?: number) =>
      request<MonteCarloResult>("/api/simulate/monte-carlo", {
        method: "POST",
        token,
        body: n ? { weeks, n } : { weeks },
      }),
    whatIf: (token: string, description: string, dollarChange: number, weeks: number) =>
      request<WhatIfResult>("/api/simulate/whatif", {
        method: "POST",
        token,
        body: { description, dollar_change: dollarChange, weeks },
      }),
  },

  optimize: {
    shifts: (token: string, maxHours: number) =>
      request<OptimizeResult>("/api/optimize/shifts", {
        method: "POST",
        token,
        body: { max_hours: maxHours },
      }),
  },
};
