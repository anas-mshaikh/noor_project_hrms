/**
 * components/shell/ShellBackdrop.tsx
 *
 * One-time background layer used across the dashboard.
 * Keep it subtle and "premium": dark gradient + faint purple/pink glow + tiny noise.
 */

export function ShellBackdrop() {
  return (
    <>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(1200px_circle_at_10%_0%,rgba(168,85,247,0.22),transparent_55%),radial-gradient(900px_circle_at_85%_10%,rgba(236,72,153,0.16),transparent_55%),linear-gradient(to_bottom,rgba(2,6,23,1),rgba(15,23,42,0.96),rgba(2,6,23,1))]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.045] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.35'/%3E%3C/svg%3E\")",
        }}
      />
    </>
  );
}

