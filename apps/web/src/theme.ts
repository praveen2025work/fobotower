// Light (Barclays blue) or dark (Barclays dark). Light is the default; a
// viewer's choice is kept in this browser.
// index.html applies it before the first paint so pages never flash.

import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "aof.theme";

export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export const DEFAULT_THEME: Theme = "light";

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setState] = useState<Theme>(() => storedTheme() ?? DEFAULT_THEME);

  useEffect(() => applyTheme(theme), [theme]);

  const set = useCallback((t: Theme) => {
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* private window: the choice lasts for this page only */
    }
    setState(t);
  }, []);

  return [theme, set];
}
