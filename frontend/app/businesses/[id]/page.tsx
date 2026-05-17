type PageProps = { params: { id: string } };

export default function BusinessDashboard({ params }: PageProps) {
  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold">Business {params.id}</h1>
      <p className="mt-2 text-neutral-400">
        Dashboard coming in Phase 4 — call transcripts, bookings, knowledge edits.
      </p>
    </main>
  );
}
