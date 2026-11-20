/** @type {import('tailwindcss').Config} */

// ─────────────────────────────────────────────────────────────────────────────
// "Lavender mist" theme: ice #B4D8DF · mist #95B9C0 · teal #6A939A · deep #3E5F6C · violet #7B6894 · lavender #B9A9DA
// Every colour in the app resolves to a CSS variable defined in
// src/styles/index.css, so dark and light mode are controlled in ONE place.
// Tailwind's built-in hue names (slate, amber, rose, …) are remapped onto the
// five theme scales so existing classes such as `bg-slate-950` or
// `text-amber-300` automatically follow the palette.
// ─────────────────────────────────────────────────────────────────────────────

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

/** Build a Tailwind colour scale that reads `--<prefix>-<step>` RGB triplets. */
const scale = (prefix) =>
  Object.fromEntries(STEPS.map((s) => [s, `rgb(var(--${prefix}-${s}) / <alpha-value>)`]));

// Scale names say what they render (they used to read marigold / lilac / coral).
const neutral = scale("n"); // teal-slate neutrals
const lavenderScale = scale("a"); // lavender: primary accent and "in progress"
const sage = scale("g"); // muted sage: success only
const mistScale = scale("l"); // teal mist: AI / info and "awaiting your review"
const roseScale = scale("r"); // dusty rose: danger

const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Theme-level semantic tokens
        canvas: { DEFAULT: v("canvas"), dark: v("canvas"), light: v("canvas") },
        surface: { DEFAULT: v("surface"), dark: v("surface"), light: v("surface"), raised: v("raised") },
        ink: { DEFAULT: v("ink"), dark: v("ink"), light: v("ink"), dim: v("ink-dim") },
        line: v("line"),
        "on-accent": v("on-accent"),
        primary: { DEFAULT: mistScale[500], dark: mistScale[600] },
        accent: sage[400],
        success: sage[400],
        // Warning has its own ochre so a caution never looks like the primary button.
        warning: v("warn"),
        // Awaiting the user's review: teal mist, distinct from primary/running lavender.
        pending: { DEFAULT: mistScale[400], soft: mistScale[300] },
        danger: roseScale[400],
        gold: { DEFAULT: lavenderScale[400], soft: lavenderScale[300] },
        lavender: mistScale[400],
        teal: { ...sage, DEFAULT: sage[400] },

        // Tailwind hue names remapped onto the theme scales
        white: v("on"),
        black: v("shade"),
        slate: neutral,
        gray: neutral,
        zinc: neutral,
        neutral,
        stone: neutral,
        amber: lavenderScale,
        orange: lavenderScale,
        yellow: lavenderScale,
        emerald: sage,
        green: sage,
        lime: sage,
        cyan: sage,
        purple: mistScale,
        violet: mistScale,
        indigo: mistScale,
        fuchsia: mistScale,
        sky: mistScale,
        blue: mistScale,
        rose: roseScale,
        red: roseScale,
        pink: roseScale,
      },
      fontFamily: {
        sans: ['"Instrument Sans Variable"', "Instrument Sans", "system-ui", "sans-serif"],
        display: ['"Bricolage Grotesque Variable"', "Bricolage Grotesque", "system-ui", "sans-serif"],
        serif: ['"Bricolage Grotesque Variable"', "Bricolage Grotesque", "system-ui", "sans-serif"],
        jost: ['"Instrument Sans Variable"', "system-ui", "sans-serif"],
      },
      // Type scale on φ (Fibonacci): 13 · 16 · 21 · 34 · 55
      fontSize: {
        body: ["16px", { lineHeight: "1.6" }],
        h3: ["17px", { lineHeight: "1.4" }],
        h2: ["21px", { lineHeight: "1.3", letterSpacing: "-0.01em" }],
        h1: ["34px", { lineHeight: "1.12", letterSpacing: "-0.02em" }],
        display: ["55px", { lineHeight: "1.04", letterSpacing: "-0.03em" }],
      },
      // Fibonacci spacing (each step ≈ previous × φ)
      spacing: {
        8: "8px",
        13: "13px",
        21: "21px",
        34: "34px",
        55: "55px",
        89: "89px",
      },
      width: {
        golden: "61.8%",
        "golden-side": "38.2%",
      },
      gridTemplateColumns: {
        golden: "1.618fr 1fr",
        "golden-reverse": "1fr 1.618fr",
      },
      aspectRatio: {
        golden: "1.618 / 1",
        "golden-portrait": "1 / 1.618",
      },
      // Radius follows hierarchy: controls 13, panels 21
      borderRadius: {
        card: "13px",
        panel: "21px",
      },
    },
  },
  plugins: [],
};
