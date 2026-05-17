const BACKEND_URL: string =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export type Business = {
  id: string;
  phone_number: string | null;
  name: string | null;
  website_url: string;
  timezone: string;
  cal_event_type_ids: number[];
  moss_index_name: string | null;
  agentmail_inbox_id: string | null;
  agentphone_agent_id: string | null;
  agentphone_number_id: string | null;
  system_prompt: string | null;
  onboarding_status: OnboardingStatus;
  extra: Record<string, unknown>;
  created_at: string;
};

export type OnboardingStatus = {
  current_step: string; // scraping | moss | inbox | calcom | agent | live | done | failed
  completed_steps: string[];
  error: { step: string; message: string } | null;
};

export type OnboardAccepted = {
  id: string;
  status: string;
};

export type CallSummary = {
  id: string;
  caller_phone: string;
  caller_name: string | null;
  status: "in_progress" | "completed" | "failed";
  outcome: string | null;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
};

export type Stats = {
  calls_today: number;
  bookings_today: number;
  escalations_today: number;
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`Backend ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function readError(r: Response): Promise<unknown> {
  const text = await r.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function startOnboarding(url: string): Promise<OnboardAccepted> {
  const r = await fetch(`${BACKEND_URL}/businesses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as OnboardAccepted;
}

export async function fetchOnboardingStatus(id: string): Promise<OnboardingStatus> {
  const r = await fetch(`${BACKEND_URL}/businesses/${id}/onboarding-status`, {
    cache: "no-store",
  });
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as OnboardingStatus;
}

export async function getBusiness(id: string): Promise<Business | null> {
  const r = await fetch(`${BACKEND_URL}/businesses/${id}`, { cache: "no-store" });
  if (r.status === 404) return null;
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as Business;
}

export async function listBusinessCalls(id: string, limit = 20): Promise<CallSummary[]> {
  const r = await fetch(`${BACKEND_URL}/businesses/${id}/calls?limit=${limit}`, {
    cache: "no-store",
  });
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as CallSummary[];
}

export async function getStats(id: string): Promise<Stats> {
  const r = await fetch(`${BACKEND_URL}/businesses/${id}/stats`, { cache: "no-store" });
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as Stats;
}

export function callStreamUrl(callId: string): string {
  return `${BACKEND_URL}/calls/${callId}/stream`;
}
