/* eslint-disable */
// REFERENCE ONLY — do not import. See _references/README.md.
//
// Visual DNA: a single cyan lamp shining down from the top of the page.
// Two stacked gradients:
//   1. Radial halo for the bulb (warm at center, dim at edges)
//   2. Conic gradient masked to a downward cone for the beam, heavily blurred
// One faint horizon line where the lamp would meet a surface.

export function LampContainer({ children }: { children?: React.ReactNode }) {
  return (
    <div className="relative isolate">
      <div className="absolute inset-x-0 top-0 -z-10 flex h-[55vh] items-start justify-center">
        {/* bulb */}
        <div
          className="absolute left-1/2 top-0 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/3 rounded-full opacity-60"
          style={{
            background:
              "radial-gradient(circle at center, rgba(34,211,238,0.55), rgba(34,211,238,0.18) 35%, transparent 65%)",
          }}
        />
        {/* beam */}
        <div
          className="absolute left-1/2 top-32 h-56 w-[60rem] -translate-x-1/2 opacity-50"
          style={{
            background:
              "conic-gradient(from 90deg at 50% 100%, transparent 0deg, rgba(34,211,238,0.35) 90deg, rgba(34,211,238,0.35) 270deg, transparent 360deg)",
            filter: "blur(48px)",
            maskImage: "linear-gradient(to bottom, black 30%, transparent 100%)",
          }}
        />
        {/* horizon */}
        <div className="absolute left-1/2 top-72 h-px w-[28rem] -translate-x-1/2 bg-gradient-to-r from-transparent via-cyan-400/35 to-transparent" />
      </div>
      {children}
    </div>
  );
}
