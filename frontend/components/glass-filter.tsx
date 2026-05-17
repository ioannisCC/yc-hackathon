/** Singleton SVG filter mounted once in the root layout.
 *  All liquid-glass surfaces reference it via backdrop-filter: url(#liquid-glass).
 *
 *  feTurbulence generates fractal noise → feGaussianBlur softens it →
 *  feDisplacementMap warps the layer behind by that noise = refraction. */
export function GlassFilter() {
  return (
    <svg className="pointer-events-none absolute h-0 w-0" aria-hidden>
      <defs>
        <filter
          id="liquid-glass"
          x="0%"
          y="0%"
          width="100%"
          height="100%"
          colorInterpolationFilters="sRGB"
        >
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.012 0.012"
            numOctaves="2"
            seed="9"
            result="turbulence"
          />
          <feGaussianBlur in="turbulence" stdDeviation="1.4" result="softNoise" />
          <feDisplacementMap
            in="SourceGraphic"
            in2="softNoise"
            scale="22"
            xChannelSelector="R"
            yChannelSelector="G"
            result="displaced"
          />
          <feGaussianBlur in="displaced" stdDeviation="0.6" result="finalBlur" />
          <feComposite in="finalBlur" in2="finalBlur" operator="over" />
        </filter>
      </defs>
    </svg>
  );
}
