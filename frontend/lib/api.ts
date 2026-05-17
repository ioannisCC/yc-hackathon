const BACKEND_URL: string =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export type Business = {
  id: string;
  phone_number: string;
  name: string;
  website_url: string;
  timezone: string;
  cal_event_type_ids: number[];
  moss_index_name: string;
  agentmail_inbox_id: string;
  agentphone_agent_id: string;
  agentphone_number_id: string;
  system_prompt: string;
  extra: Record<string, unknown>;
  created_at: string;
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

export async function onboardBusiness(url: string): Promise<Business> {
  const r = await fetch(`${BACKEND_URL}/businesses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as Business;
}

export async function getBusiness(id: string): Promise<Business | null> {
  const r = await fetch(`${BACKEND_URL}/businesses/${id}`, {
    cache: "no-store",
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new ApiError(r.status, await readError(r));
  return (await r.json()) as Business;
}
