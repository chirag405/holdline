const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export const apiBase = BASE;

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText);
    throw new Error(`${r.status} ${text}`);
  }
  return r.json() as Promise<T>;
}

export interface Boundaries {
  may_agree_to: string[];
  must_escalate: string[];
}
export interface CallBrief {
  objective: string;
  provider_name: string;
  identity_info: Record<string, string>;
  boundaries: Boundaries;
  success_criteria: string[];
  ivr_hint: string | null;
  default_on_timeout: string;
  opening_line: string;
}
export interface Task {
  task_id: string;
  request_text: string;
  fields: Record<string, string>;
  brief: CallBrief | null;
  status: string;
}
export interface TranscriptTurn {
  role: string;
  text: string;
  ts?: number;
}
export interface CallSummary {
  outcome_status: string;
  summary: string;
  confirmation_number: string;
  follow_up_draft: string;
  follow_up_date: string;
  learned_ivr_path: string;
}
export interface Call {
  call_id: string;
  task_id: string;
  status: string;
  transcript: TranscriptTurn[];
  recording_url: string | null;
  outcome: string | null;
  confirmation_number: string | null;
  summary: CallSummary | null;
  started_at: number;
  ended_at: number | null;
}
export interface AppConfig {
  practice_ivr_number: string;
  has_twilio: boolean;
  public_ws_url_set: boolean;
  supervisor_enabled: boolean;
  escalation_timeout_s: number;
  state_backend: string;
}
export interface PendingDecision {
  decision_id: string;
  call_id: string | null;
  question: string;
  options: string[];
}

export const api = {
  config: () => j<AppConfig>("/config"),
  plan: (request: string, fields: Record<string, string>) =>
    j<{ task_id: string; brief: CallBrief; task: Task }>("/tasks", {
      method: "POST",
      body: JSON.stringify({ request, fields }),
    }),
  placeCall: (body: { to: string; task_id?: string; goal?: string }) =>
    j<{ call_sid: string; status: string }>("/calls", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  calls: () => j<{ calls: Call[] }>("/calls"),
  call: (id: string) => j<Call>(`/calls/${id}`),
  pending: () => j<{ pending: PendingDecision[] }>("/decisions"),
  answer: (id: string, answer: string) =>
    j<{ resolved: boolean }>(`/decisions/${id}`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),
};

// ---- SSE event shapes ----
export type StreamEvent =
  | { seq: number; kind: "call_started"; ts: number; call_id: string | null; task_id: string | null; provider?: string; objective?: string }
  | { seq: number; kind: "status"; ts: number; call_id: string | null; status: string }
  | { seq: number; kind: "turn"; ts: number; call_id: string | null; role: string; text: string }
  | { seq: number; kind: "decision_open"; ts: number; call_id: string | null; decision_id: string; question: string; options: string[]; context?: string; timeout_s: number }
  | { seq: number; kind: "decision_resolved"; ts: number; call_id: string | null; decision_id: string; answer: string; timed_out: boolean }
  | { seq: number; kind: "call_ended"; ts: number; call_id: string | null; task_id: string | null; outcome: string; confirmation_number: string | null; summary: CallSummary | null; turns: number };
