const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Auth ---

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data: { access_token: string } = await res.json();
  window.localStorage?.setItem?.("access_token", data.access_token);
}

export async function signup(
  companyName: string,
  email: string,
  password: string
): Promise<void> {
  const data: { access_token: string } = await request("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ company_name: companyName, email, password }),
  });
  window.localStorage?.setItem?.("access_token", data.access_token);
}

export function logout(): void {
  window.localStorage?.removeItem?.("access_token");
}

// --- Data Sources ---

export interface DataSource {
  id: string;
  name: string;
  source_type: string;
  status: string;
}

export async function listDataSources(): Promise<DataSource[]> {
  return request<DataSource[]>("/api/data-sources/");
}

export async function deleteDataSource(id: string): Promise<void> {
  await request(`/api/data-sources/${id}`, { method: "DELETE" });
}

export interface SuggestedPrompt {
  label: string;
  question: string;
  icon: string;
}

export async function getSuggestedPrompts(dataSourceIds: string[]): Promise<SuggestedPrompt[]> {
  if (dataSourceIds.length === 0) return [];
  const qs = dataSourceIds.map((id) => `ids=${id}`).join("&");
  return request<SuggestedPrompt[]>(`/api/data-sources/suggested-prompts?${qs}`);
}

export async function uploadCSV(name: string, file: File): Promise<DataSource> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/data-sources/csv?name=${encodeURIComponent(name)}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function connectSQL(payload: {
  name: string;
  source_type: string;
  host: string;
  port: number;
  dbname: string;
  user: string;
  password: string;
}): Promise<DataSource> {
  return request<DataSource>("/api/data-sources/sql", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- Query ---

export interface ChartSuggestion {
  type: "bar" | "line" | "pie" | "table";
  x?: string;
  y?: string;
}

export interface QueryResult {
  query_id: string;
  question: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  chart_suggestion: ChartSuggestion;
  execution_ms: number;
  narrative?: string;
}

export async function runQuery(
  question: string,
  dataSourceIds: string | string[]
): Promise<QueryResult> {
  const ids = Array.isArray(dataSourceIds) ? dataSourceIds : [dataSourceIds];
  return request<QueryResult>("/api/query/", {
    method: "POST",
    body: JSON.stringify({ question, data_source_ids: ids }),
  });
}

export interface QueryHistoryItem {
  id: string;
  question: string;
  status: string;
  row_count?: number;
  execution_ms?: number;
  created_at: string;
  data_source_id?: string;
}

export async function getQueryHistory(dataSourceId?: string): Promise<QueryHistoryItem[]> {
  const qs = dataSourceId ? `?data_source_id=${dataSourceId}` : "";
  return request<QueryHistoryItem[]>(`/api/query/history${qs}`);
}
