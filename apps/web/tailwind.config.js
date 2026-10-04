import plugin from "tailwindcss/plugin";
import { cssVars, dark, light, tailwindColors } from "./theme/barclays.js";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // Barclays light / dark — see theme/barclays.js.
      colors: tailwindColors(),
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
  plugins: [
    plugin(({ addBase }) => {
      addBase({
        ":root": { ...cssVars(light), colorScheme: "light" },
        ':root[data-theme="dark"]': { ...cssVars(dark), colorScheme: "dark" },
      });
    }),
  ],
};
