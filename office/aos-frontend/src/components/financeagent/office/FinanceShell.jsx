"use client";
// The console's frame inside Agent One: its query cache, its Layout (sidebar,
// top bar, theme) and the page Next.js routed to. Mirrors the upstream
// main.tsx and App.tsx.

import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Layout from "../components/Layout";
import { makeQueryClient } from "../queryClient";
import { storedTheme, DEFAULT_THEME } from "../theme";
import { OutletProvider } from "./router";

function Frame({ children }) {
  const qc = useQueryClient();
  // Switching user (development) must drop every cached answer: what a user
  // may see is decided per request by the server.
  const [generation, setGeneration] = useState(0);
  const onUserChange = () => {
    qc.clear();
    setGeneration((g) => g + 1);
  };
  return (
    <OutletProvider
      value={
        <div key={generation} className="contents">
          {children}
        </div>
      }
    >
      <Layout onUserChange={onUserChange} />
    </OutletProvider>
  );
}

export default function FinanceShell({ children }) {
  const [queryClient] = useState(makeQueryClient);
  return (
    <div
      id="aof-root"
      data-theme={storedTheme() ?? DEFAULT_THEME}
      className="bg-surface-50 text-surface-900 antialiased"
    >
      <QueryClientProvider client={queryClient}>
        <Frame>{children}</Frame>
      </QueryClientProvider>
    </div>
  );
}
