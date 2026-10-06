# Styles: use this project's, everywhere

**For:** office Claude Code (both skills) and anyone adding screens in the office.

The Agent One Finance console (`apps/web`) has **one** style system. When converting or
merging, take it exactly as upstream has it. Do not bring in the office's own styles. Do not
"tidy" it, and do not swap libraries. Office screens are built from the same tokens and classes,
so they look like the rest of the console in light and dark.

`npm run check:styles` in `apps/web` enforces this. It must pass at the end of every phase that
touches `apps/web`.

## What the style system is

| Piece | File | What it holds |
|---|---|---|
| Colours | `apps/web/theme/barclays.js` | **The only place colours are written.** These are the Barclays light and dark palettes: `surface`, `primary`, `accent`, `red`/`green`/`orange`/`yellow` (also `danger`/`success`/`warning`), `card`, `brand-*`, `nav-*` and `code-*`. Each colour becomes a CSS variable `--c-<name>`. |
| Tailwind | `apps/web/tailwind.config.js`, `postcss.config.js` | Tailwind **3**. Its colours read the variables, so `bg-primary-600` works in both themes. The fonts are Inter (text) and JetBrains Mono (code). |
| Base, utilities, graphics | `apps/web/src/index.css` | The single stylesheet: base rules, small utilities, and the `hx-*` graphics. These are `hx-hero`, `hx-glass`, `hx-path`/`hx-link`, `hx-card`, `hx-chip`, `hx-ring` (with `--hx-target`, `--hx-size` and `--hx-ring-color`), `hx-sheen`, `hx-mark` and `hx-rise`. Motion stops under `prefers-reduced-motion`. |
| Theme switch | `apps/web/src/theme.ts`, `index.html` | `data-theme="light"` or `"dark"` on `<html>`, saved as `aof.theme`. `index.html` applies it before the first paint and loads the fonts. |
| Pitch page | `apps/web/public/pitch/index.html` | Its own inline CSS and fonts (Archivo, IBM Plex). It is a separate page; take it as it is. |
| Icons and class helpers | `lucide-react`, `clsx` | The only UI libraries. There is no component kit. |

The FOBO console (`apps/console`, Next.js with Tailwind 4 and `console.css`) is FOBO's own
app with its own styles. Converting it only renames things (`src/aof`); never restyle it,
and never mix its styles into `apps/web`.

## Rules when converting or merging

1. **Take upstream's style files byte for byte.** The files are those in
   `apps/web/theme/style-manifest.json`. On a conflict upstream wins, without exception. If
   the office truly needs a change (a brand colour, a font it is allowed to serve), make it
   upstream. Run `node scripts/check-styles.mjs --write` there, and pull it into the office.
   Never edit the manifest by hand.
2. **Colours only through tokens.** In `.tsx`/`.ts` use token classes such as `bg-card`,
   `text-surface-700`, `bg-primary-50 text-primary-700`, `border-surface-200` and
   `bg-brand text-brand-fg`. In `index.css` use `rgb(var(--c-…) / alpha)`. Never write a hex,
   `rgb(…)` or `hsl(…)` value, or an arbitrary `bg-[#…]`. The check fails on them.
3. **One stylesheet.** Do not add a new `.css`/`.scss` file, CSS modules, styled-components,
   Bootstrap, MUI, Ant, Chakra or similar. A reusable office style belongs upstream in
   `src/index.css` under `@layer components`, built from tokens. Prefix it `hx-` when it is
   decoration.
4. **Stay on Tailwind 3.** Do not upgrade it while converting. The config and plugin are
   written for 3.
5. **Keep both themes working.** Every new screen must read well in light and dark: open it
   in both, using the sun/moon switch in the sidebar. Colours that must not flip have their own
   tokens (`card`, `nav-*`, `code-*`, `brand-*`); use those, not a fixed colour.
6. **Keep motion optional.** Any new animation goes in `index.css` and is switched off in the
   `prefers-reduced-motion` block.
7. **Fonts.** If the office network blocks Google Fonts, the console falls back to the system
   font stack in `tailwind.config.js`, which needs no change. To serve the fonts from the
   office instead, make the change upstream (rule 1).
8. **Inline `style` is only for CSS variables and sizes**, for example
   `style={{ ["--hx-target" as string]: pct }}`. Anything else is a class. The check warns
   on anything else.

## Checking

```bash
cd apps/web
npm run check:styles     # upstream style files, tokens only, one stylesheet, Tailwind 3, hx-* defined
npx tsc --noEmit -p . && npx vitest run
npm run dev              # then open Overview, a case, Configure and /pitch/ in light and dark
```

A passing check prints:

```
styles ok: upstream style files, tokens only, Tailwind ^3.4.14, 12 hx-* classes
```

Each failure names the file and line, and what to use instead.
