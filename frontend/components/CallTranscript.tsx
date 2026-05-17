export type TranscriptTurn = {
  role: "caller" | "agent";
  text: string;
};

export function CallTranscript({ turns }: { turns: TranscriptTurn[] }) {
  return (
    <div className="flex flex-col gap-2">
      {turns.map((t, i) => (
        <div
          key={i}
          className={`max-w-[80%] rounded-lg px-3 py-2 ${
            t.role === "agent"
              ? "self-start bg-neutral-800"
              : "self-end bg-blue-600/30"
          }`}
        >
          <p className="mb-0.5 text-xs text-neutral-400">{t.role}</p>
          <p>{t.text}</p>
        </div>
      ))}
    </div>
  );
}
