// Light (Barclays blue) or dark (Barclays dark). The choice is the viewer's,
// kept in this browser; with no choice the operating system's setting wins.
// index.html applies it before the first paint so pages never flash.

import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "helix.theme";

export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setState] = useState<Theme>(() => storedTheme() ?? systemTheme());

  useEffect(() => applyTheme(theme), [theme]);

  // Follow the operating system until the viewer picks a theme.
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => storedTheme() === null && setState(mq.matches ? "dark" : "light");
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

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
