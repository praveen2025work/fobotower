// Barclays themes for the Helix console — the single source of the colours.
//
// Pages keep aria-ai's Tailwind classes (`bg-surface-50`, `text-primary-700`,
// `bg-red-100`…); every palette here becomes CSS variables, so one class
// renders in either theme:
//
//   light — Barclays blue on white: navy sidebar, Barclays blue actions,
//           cyan highlights.
//   dark  — Barclays dark: deep navy surfaces, cyan actions.
//
// Scales are written for their *role*: in dark, the light tints (50–200) are
// dark tints and the dark text shades (600–900) are light text, so
// `bg-primary-50 text-primary-700` reads well in both. Things that must not
// flip have their own tokens: `card` (panels), `nav-*` (the sidebar),
// `code-*` (YAML and log panes, always dark) and `brand-*` (solid buttons).

// Barclays brand blues.
export const BARCLAYS = {
  cyan: "#00aeef",   // Barclays blue
  blue: "#007eb6",   // action blue
  navy: "#00395d",   // dark blue
};

const tailwindRed = { 50: "#fef2f2", 100: "#fee2e2", 200: "#fecaca", 300: "#fca5a5", 400: "#f87171", 500: "#ef4444", 600: "#dc2626", 700: "#b91c1c", 800: "#991b1b", 900: "#7f1d1d", 950: "#450a0a" };
const tailwindGreen = { 50: "#f0fdf4", 100: "#dcfce7", 200: "#bbf7d0", 300: "#86efac", 400: "#4ade80", 500: "#22c55e", 600: "#16a34a", 700: "#15803d", 800: "#166534", 900: "#14532d", 950: "#052e16" };
const tailwindOrange = { 50: "#fff7ed", 100: "#ffedd5", 200: "#fed7aa", 300: "#fdba74", 400: "#fb923c", 500: "#f97316", 600: "#ea580c", 700: "#c2410c", 800: "#9a3412", 900: "#7c2d12", 950: "#431407" };
const tailwindYellow = { 50: "#fefce8", 100: "#fef9c3", 200: "#fef08a", 300: "#fde047", 400: "#facc15", 500: "#eab308", 600: "#ca8a04", 700: "#a16207", 800: "#854d0e", 900: "#713f12", 950: "#422006" };

const darkRed = { 50: "#2a1215", 100: "#3b1519", 200: "#5f1f26", 300: "#fca5a5", 400: "#f87171", 500: "#ef4444", 600: "#e5484d", 700: "#ff9592", 800: "#ffc9c7", 900: "#ffe1df", 950: "#fff1f0" };
const darkGreen = { 50: "#0d2318", 100: "#112e1f", 200: "#1c4a31", 300: "#86efac", 400: "#4ade80", 500: "#22c55e", 600: "#22a85a", 700: "#6fdc96", 800: "#a7f0c2", 900: "#d1f8df", 950: "#ecfdf3" };
const darkOrange = { 50: "#2b1a0c", 100: "#3a220f", 200: "#613614", 300: "#fdba74", 400: "#fb923c", 500: "#f97316", 600: "#dd6511", 700: "#ffa860", 800: "#ffcb99", 900: "#ffe3c7", 950: "#fff3e6" };
const darkYellow = { 50: "#27210a", 100: "#352c0c", 200: "#584912", 300: "#fde047", 400: "#facc15", 500: "#eab308", 600: "#b88a05", 700: "#f5d453", 800: "#fae68f", 900: "#fdf2c4", 950: "#fefae6" };

export const light = {
  // Cool greys with a blue cast, for pages, borders and text.
  surface: { 50: "#f5f8fb", 100: "#eaf0f5", 200: "#d8e2eb", 300: "#bccbd8", 400: "#8da2b5", 500: "#61778c", 600: "#46596b", 700: "#33465a", 800: "#1f3245", 900: "#0f2133", 950: "#06121f" },
  // Barclays blue: cyan → action blue → navy.
  primary: { 50: "#e6f6fd", 100: "#c0e9fa", 200: "#8fd8f6", 300: "#4fc4f2", 400: BARCLAYS.cyan, 500: "#0096d6", 600: BARCLAYS.blue, 700: "#00608f", 800: BARCLAYS.navy, 900: "#002a46", 950: "#001a2d" },
  // Barclays cyan, for highlights.
  accent: { 50: "#e5f7fe", 100: "#bfeefc", 200: "#8ae1fa", 300: "#4dd2f7", 400: "#1ec0f3", 500: BARCLAYS.cyan, 600: "#0091cc", 700: "#0074a6", 800: "#005a82", 900: "#00466a", 950: "#002c45" },
  red: tailwindRed,
  green: tailwindGreen,
  orange: tailwindOrange,
  yellow: tailwindYellow,
  card: "#ffffff",
  brand: { DEFAULT: BARCLAYS.blue, strong: "#00608f", fg: "#ffffff", accent: BARCLAYS.cyan, "accent-strong": "#0091cc", "accent-fg": "#ffffff" },
  nav: { bg: BARCLAYS.navy, hover: "#004b7a", line: "#0b4a72", fg: "#cfe6f3", muted: "#7fb3d1", active: "#0a5c8c", "active-fg": "#ffffff", mark: BARCLAYS.cyan },
  code: { bg: "#06121f", line: "#1f3245", fg: "#dbe7f1", muted: "#7f93a8" },
};

export const dark = {
  surface: { 50: "#081521", 100: "#0f2131", 200: "#1a2f43", 300: "#284259", 400: "#57708a", 500: "#7f95ab", 600: "#a3b4c6", 700: "#c2cfdc", 800: "#dae3ec", 900: "#ecf2f7", 950: "#f7fafc" },
  primary: { 50: "#0a2a40", 100: "#0d3551", 200: "#124868", 300: "#1c6a94", 400: "#2b9fd6", 500: BARCLAYS.cyan, 600: "#4cc6f4", 700: "#7fd6f7", 800: "#b3e7fa", 900: "#d9f3fd", 950: "#eefaff" },
  accent: { 50: "#062a3d", 100: "#09364f", 200: "#0e4b6c", 300: "#4dd2f7", 400: "#1ec0f3", 500: BARCLAYS.cyan, 600: "#3fc3f5", 700: "#7ad6f8", 800: "#b0e8fb", 900: "#d6f4fd", 950: "#ecfaff" },
  red: darkRed,
  green: darkGreen,
  orange: darkOrange,
  yellow: darkYellow,
  card: "#0d1d2c",
  brand: { DEFAULT: BARCLAYS.cyan, strong: "#33c1f4", fg: "#00263e", accent: "#1ec0f3", "accent-strong": "#4dd2f7", "accent-fg": "#00263e" },
  nav: { bg: "#03111d", hover: "#0b2234", line: "#132a3d", fg: "#a9c3d6", muted: "#5f7f98", active: "#0a2f47", "active-fg": BARCLAYS.cyan, mark: BARCLAYS.cyan },
  code: { bg: "#040d16", line: "#1a2f43", fg: "#dbe7f1", muted: "#7f93a8" },
};

// Status aliases used by aria-ai's watchtower components.
for (const t of [light, dark]) {
  t.success = t.green;
  t.warning = t.yellow;
  t.danger = t.red;
}

const channels = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
};

const flatten = (theme) => {
  const out = {};
  for (const [name, value] of Object.entries(theme)) {
    if (typeof value === "string") out[name] = value;
    else for (const [k, v] of Object.entries(value)) out[k === "DEFAULT" ? name : `${name}-${k}`] = v;
  }
  return out;
};

/** `{ "--c-primary-700": "0 96 143", … }` for one theme. */
export const cssVars = (theme) =>
  Object.fromEntries(Object.entries(flatten(theme)).map(([k, v]) => [`--c-${k}`, channels(v)]));

/** Tailwind `colors`: every token reads its CSS variable, with alpha support. */
export const tailwindColors = () => {
  const colors = {};
  for (const [name, value] of Object.entries(light)) {
    const ref = (key) => `rgb(var(--c-${key}) / <alpha-value>)`;
    if (typeof value === "string") colors[name] = ref(name);
    else colors[name] = Object.fromEntries(Object.keys(value).map((k) => [k, ref(k === "DEFAULT" ? name : `${name}-${k}`)]));
  }
  return colors;
};
