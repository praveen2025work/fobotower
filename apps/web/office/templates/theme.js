"use client";
// Office build: the console follows Agent One's light / dark theme (next-themes), so there
// is one theme switch for the whole page. Same exports as upstream src/theme.ts.

import { useTheme as useAgentOneTheme } from "next-themes";
import { useCallback, useEffect } from "react";

export const DEFAULT_THEME = "light";

/** Agent One's current theme, read from the page (next-themes sets the "dark" class). */
export function storedTheme() {
  if (typeof document === "undefined") return null;
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function applyTheme(theme) {
  const root = document.getElementById("aof-root");
  if (root) root.dataset.theme = theme;
}

export function useTheme() {
  const { resolvedTheme, setTheme } = useAgentOneTheme();
  const theme = resolvedTheme === "dark" || resolvedTheme === "light" ? resolvedTheme : storedTheme() ?? DEFAULT_THEME;

  useEffect(() => applyTheme(theme), [theme]);

  const set = useCallback((t) => setTheme?.(t), [setTheme]);

  return [theme, set];
}
