# Updating the AOF console: replace the whole folder

**For:** you and office Claude Code, updating the Agent One Finance (AOF) console in the office.

**Short answer: yes, replace the whole folder.**

- Swap the AOF console folder for upstream's `apps/web`.
- Then put back the few office files that are yours.
- Do not merge it screen by screen, convert it, or apply the patch file by file.

## Why the last update went wrong

Office Claude ported the changes file by file into the existing UI. That loses the parts that are not screens:

| What you saw | Usual cause | Which file brings it |
|---|---|---|
| Pages unstyled or partly styled | The Tailwind set-up was not copied or was merged wrongly. The colours and spacing come from the Barclays theme, not from the screens. | `tailwind.config.js`, `postcss.config.js`, `theme/barclays.js`, `src/index.css`, and `import "./index.css"` in `src/main.tsx` |
| Some classes have no effect, for example `bg-surface-200` or `text-brand-600` | The theme colours are missing. Or Tailwind's `content` paths do not include the new files, so their classes are not generated. | `theme/barclays.js`, `tailwind.config.js` |
| Left menu icons missing | The `lucide-react` icon package is missing or at a different version. Or the icons were dropped when screens were converted to the existing UI's own components. | `package.json`, `package-lock.json`, `src/components/Layout.tsx` |
| Fonts look different | `index.html` loads Inter from Google Fonts. The office network may block it. | Not a fault: it falls back to the system font. |

The console is one built unit: about 110 files plus its package list and its theme. Copying the whole folder takes minutes and is exact. Converting it costs a day each time and drifts on every update.

## What is the office's own, and kept

These are the only files to keep from the office copy. Everything else comes from upstream.

| Keep | Why |
|---|---|
| `.env`, `.env.*` (for example `VITE_AOF_API`, `VITE_AOF_TRACE_URL`) | Office API address and links |
| `.npmrc` | The office npm registry or mirror |
| `Dockerfile`, `nginx.conf` or other web-server config, `.gitlab-ci.yml` or pipeline files | How the office builds and serves it |
| Any file under `src/` that is **only** in the office (for example single sign-on glue) | Office additions. Office Claude must list these and ask you about each one first. |

Identity needs no code change. In the office, the single sign-on proxy sets the `X-AOF-User` header and the console sends nothing itself (`src/api/client.ts`).

## Where the folder comes from

The update package (`aof-update.zip`, built with `apps/backend/scripts/aof_office_update.py`) now has a `web/` folder:

| File | What it is |
|---|---|
| `web/aof-web-<version>.tar.gz` | The whole upstream `apps/web` at that version (no `node_modules`, no `dist`) |
| `web/files.txt` | The list of files it contains, to check the result |
| `web/README.md` | This page |

## Before you start

1. **Decide where the AOF console lives in the office.** It is its own folder: in `aos-frontend` it is either the repo root or a subfolder. It is **not** the existing Agent One UI.
   - If AOF screens were added into the existing Agent One UI app, remove them there.
   - Add a menu link from the Agent One UI to the AOF console instead. It is deployed as its own app. This is the recommended answer to open decision D08 in the plan.
2. **Check that the office npm mirror has the packages** in upstream's `package.json`, at those versions. In particular: `lucide-react`, `@tanstack/react-query`, `react-router-dom`, `tailwindcss`, `postcss`, `autoprefixer`, `vite`, `typescript`, `yaml`, `clsx`.

## The prompt for office Claude Code

Fill in the `<…>` and paste:

> We are replacing our Agent One Finance console with upstream's, as a whole folder. Read
> `<path>/aof-update/web/README.md` first. Our AOF console folder is `<office console folder>` in
> `aos-frontend`.
>
> Work on a new branch `aof-web-replace` only. Do not touch the main branch, any deployment,
> secret or the backend. Stop after each numbered step and show me the result.
>
> 1. **Inventory.** Unpack `web/aof-web-<version>.tar.gz` to a temporary folder outside the repo.
>    Compare it with `<office console folder>` (ignore `node_modules` and `dist`) and list:
>    - (a) files only in our folder;
>    - (b) files in both that differ.
>
>    For (b), say which differences are our office settings (API address, registry, build,
>    single sign-on) and which are just an older or converted copy of upstream. Do not change
>    anything yet.
> 2. **Undo the earlier port.** If the last update put AOF screens, styles or components into any
>    other app or folder (for example the existing Agent One UI), list them. Once I agree, remove
>    them, so AOF exists in one place only.
> 3. **Replace.** Delete everything in `<office console folder>` except the files I approved to
>    keep in step 1. Copy in the whole unpacked upstream folder. Do not convert any file: keep
>    `.tsx`, the Tailwind and PostCSS config, `theme/`, `src/index.css`, `package.json` and
>    `package-lock.json` exactly as upstream. Then put back our kept files.
> 4. **Install and check.**
>    - Run `npm ci`. If our registry needs a different lock file, run `npm install` once to
>      regenerate it, and tell me which packages changed.
>    - Run `npx tsc --noEmit -p .`, `npx vitest run`, `npm run check:styles` and `npm run build`.
>    - Report the counts. Upstream has 93 tests passing.
>    - If a package cannot be installed from our mirror, stop and tell me which one. Do not
>      replace it with another library.
> 5. **Look at it.** Run `npm run dev` with `AOF_API_URL=<UAT API URL>` and confirm:
>    - the left menu shows its icons;
>    - pages have the Barclays colours and spacing;
>    - light and dark themes both work.
>
>    Give me screenshots of Overview, a FOBO case and How it runs.
> 6. **Commit** with a clear message and list: the files kept from the office copy and why, any
>    lock-file changes, and the test and build results. Stop there; I will raise the merge request.
>
> Rules: never hand-edit upstream screens to "fit" our app, never convert TSX to JSX, and never
> copy styles into another stylesheet. If something does not work, tell me what and why instead.

## Next time

Every update to the console is the same: unpack the new `aof-web-<version>.tar.gz` and repeat
steps 1, 3, 4 and 5. Step 1 should then show only your kept files.

The backend keeps using the patches in `patches/`, as in [`README.md`](README.md).
