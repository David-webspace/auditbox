export type InboxItem = {
  base: string;
  invoice: string | null;
  attachment: string | null;
  pages: number;
  modified: string;
  problem: string | null;
};

export type JobItem = { base: string; status: string; case_id: string | null; outcome: string | null };
export type JobState = { running: boolean; pic?: string; items: JobItem[]; log: string[]; next: number };

export type Meta = {
  pics: string[];
  statuses: string[];
  llm: string;
  llm_ready: boolean;
  workspace: string;
  can_open: boolean;
  mailpit_url: string | null;
  company: string;
};
export type LLMSettings = {
  provider: "claude" | "ollama";
  model: string;
  models: Record<string, string>;
  key_hint: string | null;
  key_source: string | null;
  ollama: { base_url: string; model: string };
};
export type HealthCheck = { name: string; ok: boolean; detail: string };

export type CaseRow = {
  id: string;
  pic: string;
  base: string;
  po_no: string | null;
  vendor: string;
  outcome: string;
  status: string;
  folder: string;
  note: string;
  created: string;
  updated: string;
};

export type Evidence = {
  doc: string;
  file: "invoice" | "attachment" | null;
  page: number | null;
  value: unknown;
  raw: string | null;
  quote: string | null;
};

export type Finding = {
  rule: string;
  name: string;
  owner: string;
  status: "pass" | "fail" | "skipped";
  message: string;
  evidence: Evidence[];
};

export type Field = { value: unknown; raw: string | null; page: number | null; quote: string | null; verified: boolean | null };
export type ExtractedDoc = { file: "invoice" | "attachment"; pages: number[]; fields: Record<string, Field> };

export type CaseDetail = CaseRow & {
  history: { at: string; status: string; note: string }[];
  detail: {
    outcome: string;
    findings: Finding[];
    form: Record<string, string> | null;
    extraction: { llm: string; seconds: number; documents: Record<string, ExtractedDoc> };
    route: { to: string[]; cc: string[]; rules: string[]; warnings: string[] };
    draft: { subject: string; html: string; lang: string; intro_source: string; to: string[]; cc: string[] };
  } | null;
};

export type LintIssue = { level: "error" | "warning" | "info"; row: number; rule_id: string; message: string };
export type RoutingRule = {
  row: number;
  rule_id: string;
  enabled: boolean;
  outcome: string;
  cond: Record<string, string>;
  to: string[];
  cc: string[];
  maintainer: string;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `HTTP ${res.status}`);
  return body as T;
}

export const api = {
  meta: () => call<Meta>("/api/meta"),
  health: () => call<HealthCheck[]>("/api/health"),
  inbox: (pic: string) => call<InboxItem[]>(`/api/inbox?pic=${encodeURIComponent(pic)}`),
  startJob: (pic: string, bases: string[]) =>
    call<{ ok: boolean }>("/api/jobs", { method: "POST", body: JSON.stringify({ pic, bases }) }),
  job: (since: number) => call<JobState>(`/api/jobs/current?since=${since}`),
  stopJob: () => call("/api/jobs/stop", { method: "POST" }),
  skipJob: () => call("/api/jobs/skip", { method: "POST" }),
  cases: () => call<CaseRow[]>("/api/cases"),
  case: (id: string) => call<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`),
  listing: (id: string) => call<string[]>(`/api/cases/${encodeURIComponent(id)}/listing`),
  setStatus: (id: string, status: string, note: string) =>
    call<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ status, note }),
    }),
  lint: () => call<{ rules: RoutingRule[]; issues: LintIssue[] }>("/api/routing/lint"),
  llm: () => call<LLMSettings>("/api/llm"),
  saveLlm: (body: { provider: string; model?: string; api_key?: string | null }) =>
    call<LLMSettings>("/api/llm", { method: "PUT", body: JSON.stringify(body) }),
  open: (target: string) => call("/api/open", { method: "POST", body: JSON.stringify({ target }) }),
};

export const pageUrl = (id: string, file: string, n: number, q?: string | null) =>
  `/api/cases/${encodeURIComponent(id)}/page?file=${file}&n=${n}` + (q ? `&q=${encodeURIComponent(q)}` : "");

export const fileUrl = (id: string, rel: string) =>
  `/api/cases/${encodeURIComponent(id)}/files/${rel.split("/").map(encodeURIComponent).join("/")}`;

export function ageDays(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}
