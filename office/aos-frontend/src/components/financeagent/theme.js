// Generated from apps/web/src/theme.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Light (Barclays blue) or dark (Barclays dark). Light is the default; a
// viewer's choice is kept in this browser.
// index.html applies it before the first paint so pages never flash.

import { useCallback, useEffect, useState } from "react";

const KEY = "aof.theme";

export function storedTheme() {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export const DEFAULT_THEME = "light";

export function applyTheme(theme) {
  const root = document.getElementById("aof-root");
  if (root) root.dataset.theme = theme;
}

export function useTheme() {
  const [theme, setState] = useState(() => storedTheme() ?? DEFAULT_THEME);

  useEffect(() => applyTheme(theme), [theme]);

  const set = useCallback((t) => {
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* private window: the choice lasts for this page only */
    }
    setState(t);
  }, []);

  return [theme, set];
}
