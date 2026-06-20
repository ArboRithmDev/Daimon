// marks.jsx — the Duo brand marks, de-playgrounded from the Claude Design system.
// Mono glyph (alpha-only, currentColor) = the "beside" Duo silhouette, baked path
// data shared with build/assets/daimon-menubar-glyph.svg.
import React from "react";

export function DuoGlyph({ size = 22 }) {
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} fill="currentColor" aria-label="Daimon">
      <path d="M346.17 339.75 C332.96 371.94 287.34 402.86 253.60 412.27 C219.86 421.69 173.82 414.54 143.71 396.26 C113.61 377.97 75.49 335.20 72.96 302.56 C70.43 269.92 102.02 224.54 128.53 200.43 C155.04 176.32 197.96 154.79 232.02 157.90 C266.09 161.02 313.88 188.80 332.91 219.11 C351.94 249.42 359.39 307.56 346.17 339.75Z" />
      <path d="M419.18 199.86 C407.10 208.96 383.51 210.31 367.17 206.49 C350.82 202.67 327.41 190.94 321.10 176.94 C314.78 162.93 321.07 136.91 329.28 122.47 C337.50 108.04 354.47 94.15 370.40 90.34 C386.34 86.53 413.36 89.38 424.90 99.64 C436.45 109.89 440.60 135.17 439.65 151.87 C438.70 168.57 431.26 190.75 419.18 199.86Z" />
    </svg>
  );
}

// Bicolour tile mark for the header chip — presence lobe + companion lobe.
export function DuoMark({ size = 23, presence = "#B66CFF", companion = "#E8B23A" }) {
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} aria-label="Daimon Duo">
      <path d="M346.17 339.75 C332.96 371.94 287.34 402.86 253.60 412.27 C219.86 421.69 173.82 414.54 143.71 396.26 C113.61 377.97 75.49 335.20 72.96 302.56 C70.43 269.92 102.02 224.54 128.53 200.43 C155.04 176.32 197.96 154.79 232.02 157.90 C266.09 161.02 313.88 188.80 332.91 219.11 C351.94 249.42 359.39 307.56 346.17 339.75Z" fill={presence} />
      <path d="M419.18 199.86 C407.10 208.96 383.51 210.31 367.17 206.49 C350.82 202.67 327.41 190.94 321.10 176.94 C314.78 162.93 321.07 136.91 329.28 122.47 C337.50 108.04 354.47 94.15 370.40 90.34 C386.34 86.53 413.36 89.38 424.90 99.64 C436.45 109.89 440.60 135.17 439.65 151.87 C438.70 168.57 431.26 190.75 419.18 199.86Z" fill={companion} />
    </svg>
  );
}
