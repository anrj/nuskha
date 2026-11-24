// Typed client for the engine API. The only place that knows URLs.
const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type DocStatus = "processing" | "ready" | "failed";

export interface Doc {
  id: string;
  filename: string;
  status: DocStatus;
  error: string | null;
  page_count: number | null;
  chunk_count: number | null;
  georgian_ratio: number | null;
  legacy_font_fixed: boolean;
  size_bytes: number;
  created_at: string;
}

export interface Citation {
  n: number;
  chunk_id: number;
  document_id: string;
  filename: string;
  page: number;
  snippet: string;
}

export interface Answer {
  question_id: string;
  answer: string;
  citations: Citation[];
  mode: "llm" | "none" | "unavailable";
  latency_ms: number;
}

export interface SourceOpen {
  id: string;
  document_id: string;
  page: number;
  url: string;
}

// Anonymous per-browser id: scopes documents in the MVP and is the PostHog distinct_id.
export const userId: string = (() => {
  const fresh = () => crypto.randomUUID().replaceAll("-", "");
  try {
    const existing = localStorage.getItem("nuskha.uid");
    if (existing) return existing;
    const id = fresh();
    localStorage.setItem("nuskha.uid", id);
    return id;
  } catch {
    return fresh();
  }
})();

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "X-User-Id": userId, ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listDocuments: () => request<Doc[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  ask: (question: string) => request<Answer>("/ask", json({ question })),
  openSource: (question_id: string, chunk_id: number) =>
    request<SourceOpen>("/source-opens", json({ question_id, chunk_id })),
  absolute: (path: string) => `${BASE}${path}`,
};

// Citation unit depends on the format: slides for PowerPoint, sheets for Excel, pages otherwise.
export function unitLabel(filename: string): string {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  if (ext === ".pptx" || ext === ".ppt") return "სლაიდი";
  if (ext === ".xlsx" || ext === ".xls") return "ფურცელი";
  return "გვ.";
}
