// Apple-flavored non-linear motion tokens.
// Used by both CSS (via the string) and Svelte transitions (via the easing fn).

// iOS standard "ease-out" spring-like curve. Feels physical, not linear.
export const APPLE_EASE_CSS = "cubic-bezier(0.32, 0.72, 0, 1)";

// A slightly softer curve for larger surfaces (dialogs, page enter).
export const APPLE_EASE_SOFT_CSS = "cubic-bezier(0.22, 1, 0.36, 1)";

// JS easing equivalent of APPLE_EASE_CSS for `svelte/transition` `easing`.
// cubic-bezier(0.32, 0.72, 0, 1) sampled as a cubic Bézier solver.
export function appleEase(t: number): number {
  // Control points: P1=(0.32,0.72), P2=(0,1)
  const x1 = 0.32;
  const y1 = 0.72;
  const x2 = 0.0;
  const y2 = 1.0;

  // Solve for parametric u given x = t, then return y.
  // Newton-Raphson on the x(u) cubic.
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;

  const sampleX = (u: number) => ((ax * u + bx) * u + cx) * u;
  const sampleDX = (u: number) => (3 * ax * u + 2 * bx) * u + cx;

  let u = t;
  for (let i = 0; i < 8; i++) {
    const x = sampleX(u) - t;
    if (Math.abs(x) < 1e-4) break;
    const d = sampleDX(u);
    if (Math.abs(d) < 1e-6) break;
    u -= x / d;
  }
  u = Math.max(0, Math.min(1, u));
  return ((ay * u + by) * u + cy) * u;
}

// Softer variant for big surfaces.
export function appleEaseSoft(t: number): number {
  const x1 = 0.22;
  const y1 = 1.0;
  const x2 = 0.36;
  const y2 = 1.0;

  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;

  const sampleX = (u: number) => ((ax * u + bx) * u + cx) * u;
  const sampleDX = (u: number) => (3 * ax * u + 2 * bx) * u + cx;

  let u = t;
  for (let i = 0; i < 8; i++) {
    const x = sampleX(u) - t;
    if (Math.abs(x) < 1e-4) break;
    const d = sampleDX(u);
    if (Math.abs(d) < 1e-6) break;
    u -= x / d;
  }
  u = Math.max(0, Math.min(1, u));
  return ((ay * u + by) * u + cy) * u;
}
