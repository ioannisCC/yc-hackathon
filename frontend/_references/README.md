# Design references

These files document the visual vocabulary the live components in `components/`
are built from. They are **not imported** by the app — they're reference
implementations only. The live components combine and adapt these patterns to
the specific composition the onboarding page needs.

## Mapping

| Reference | Live component | What's shared |
|---|---|---|
| `lamp.tsx` (LampContainer)        | `components/ambient-background.tsx` (LampGlow)      | Two conic gradients meeting at top + masked cones + diffuse bulb + horizon line |
| `falling-pattern.tsx`             | `components/ambient-background.tsx` (FallingPattern)| 12 radial-gradient row systems scrolled vertically via background-position |
| `button.tsx` (LiquidButton)       | `components/liquid-button.tsx`                      | SVG turbulence + displacement filter referenced from `backdrop-filter` |
| `liquid-glass-button.tsx`         | `components/liquid-button.tsx`, `liquid-input.tsx`  | Multi-layer inset shadow stack + edge highlights |
| `dynamic-island-toc.tsx`          | `components/dynamic-island.tsx`                     | Framer `layout` morph + mode-keyed AnimatePresence child cross-fade |

## SVG filter

The liquid components reference `#liquid-glass`, which is defined once in
`components/glass-filter.tsx` and mounted from `app/layout.tsx`. Don't
duplicate the filter inside each component — the singleton avoids id
collisions and saves the displacement-map computation per element.
