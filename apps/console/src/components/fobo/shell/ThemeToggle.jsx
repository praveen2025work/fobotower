'use client';

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'fobo-theme';

/**
 * Sets data-theme on <html>, which the token file keys its dark palette to.
 * The stored preference is per-viewer and best-effort: a private window or
 * blocked site data makes the read throw, and the page must still render.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    let stored = null;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      stored = null;
    }
    const initial =
      stored ??
      (window.matchMedia?.('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light');
    setTheme(initial);
    document.documentElement.setAttribute('data-theme', initial);
  }, []);

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* per-viewer convenience only */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      className="rounded-full flex items-center justify-center shrink-0"
      style={{
        width: 26,
        height: 26,
        background: 'rgba(255,255,255,0.10)',
        color: 'var(--text-on-brand)',
        fontSize: 13,
      }}
    >
      ◑
    </button>
  );
}
