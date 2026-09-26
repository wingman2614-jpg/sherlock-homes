import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "var(--ink)", soft: "var(--ink-soft)", muted: "var(--ink-muted)" },
        paper: { DEFAULT: "var(--paper)", raised: "var(--paper-raised)", sunk: "var(--paper-sunk)" },
        line: "var(--line)",
        stroke: "var(--stroke)",
        coral: "var(--coral)",
        brass: { DEFAULT: "var(--brass)", soft: "var(--brass-soft)" },
        oxblood: { DEFAULT: "var(--oxblood)", soft: "var(--oxblood-soft)" },
        hunter: { DEFAULT: "var(--hunter)", ink: "var(--hunter-ink)" },
        lvl: { high: "var(--lvl-high)", med: "var(--lvl-med)", low: "var(--lvl-low)", none: "var(--lvl-none)" },
      },
      fontFamily: {
        serif: ["var(--font-body)", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        type: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
