"use client";

import { useState, type FormEvent } from "react";
import { onboardBusiness, type OnboardResponse } from "@/lib/api";

export function OnboardingFlow() {
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OnboardResponse | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await onboardBusiness(url);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-6">
        <p className="text-sm text-neutral-400">Your number is live:</p>
        <p className="mt-2 font-mono text-4xl">
          {result.phone_number ?? "(pending)"}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <input
        type="url"
        required
        placeholder="https://your-business.com"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        className="rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 text-lg focus:border-neutral-600 focus:outline-none"
      />
      <button
        type="submit"
        disabled={submitting}
        className="rounded-lg bg-white px-4 py-3 font-semibold text-neutral-950 hover:bg-neutral-200 disabled:opacity-50"
      >
        {submitting ? "Setting up your receptionist…" : "Get my number"}
      </button>
      {error !== null && <p className="text-sm text-red-400">{error}</p>}
    </form>
  );
}
