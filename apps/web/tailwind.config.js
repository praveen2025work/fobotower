/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#e8edf4",
          100: "#c5d1e3",
          200: "#9eb3d0",
          300: "#7795bd",
          400: "#597fae",
          500: "#3b69a0",
          600: "#335a8a",
          700: "#294a72",
          800: "#1e3a5f",
          900: "#122747",
          950: "#091529",
        },
        accent: {
          50: "#effefa",
          100: "#c7fff0",
          200: "#90ffe2",
          300: "#51f7d0",
          400: "#1de4b9",
          500: "#0d9488",
          600: "#067a70",
          700: "#09615a",
          800: "#0d4d49",
          900: "#10403d",
          950: "#022624",
        },
        surface: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          950: "#020617",
        },
        // Watchtower / status temperature tokens. Used by the Operator Home
        // (FF_HOME_V2) redesign and any other surface that needs explicit
        // success / warning / danger / info color semantics.
        success: {
          100: "#dcfce7",
          200: "#bbf7d0",
          300: "#86efac",
          600: "#16a34a",
          700: "#15803d",
        },
        warning: {
          100: "#fef9c3",
          200: "#fef08a",
          300: "#fde68a",
          600: "#ca8a04",
          700: "#a16207",
        },
        danger: {
          100: "#fee2e2",
          200: "#fecaca",
          300: "#fca5a5",
          600: "#dc2626",
          700: "#b91c1c",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
