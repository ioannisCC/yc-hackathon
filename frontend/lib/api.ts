const BACKEND_URL: string =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export type OnboardResponse = {
  business_id: string;
  phone_number: string | null;
  status: string;
};

export async function onboardBusiness(url: string): Promise<OnboardResponse> {
  const r = await fetch(`${BACKEND_URL}/businesses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!r.ok) {
    throw new Error(`Backend ${r.status}: ${await r.text()}`);
  }
  return (await r.json()) as OnboardResponse;
}
