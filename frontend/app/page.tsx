import { OnboardingFlow } from "@/components/OnboardingFlow";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="w-full max-w-2xl">
        <h1 className="mb-4 text-5xl font-bold tracking-tight">
          Your business gets a phone.
        </h1>
        <p className="mb-8 text-lg text-neutral-400">
          Paste a URL. In under five minutes, your business has a number
          staffed by a voice AI that books real appointments.
        </p>
        <OnboardingFlow />
      </div>
    </main>
  );
}
