// Entry for the read-only snapshot build (npm run build:snapshot): the real
// app, hash-routed, over recorded data, with a banner saying what it is.
import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";
import "../index.css";
import { installSnapshot, type Snapshot } from "./install";

// Written by scripts/capture-snapshot.mjs (not committed: it holds recorded data).
const recorded = import.meta.glob<Snapshot>("./data.json", { eager: true, import: "default" });
const snap: Snapshot = recorded["./data.json"] ?? { user: "", captured_at: new Date().toISOString(), responses: {} };
installSnapshot(snap);
// A showcase: the sidebar opens with its labels (a viewer's own choice still wins).
try {
  if (localStorage.getItem("aof.nav.collapsed") === null) localStorage.setItem("aof.nav.collapsed", "0");
} catch {
  /* storage unavailable: the sidebar keeps its default */
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false, staleTime: Infinity } },
});

function Banner() {
  const when = new Date(snap.captured_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="hx-topbar hx-pop pointer-events-none fixed bottom-3 right-3 z-50 flex items-center gap-2 rounded-full border border-surface-200 px-3 py-1.5 text-[11px] font-medium text-surface-700 shadow-lg">
      <span className="hx-live text-accent-500" aria-hidden="true" />
      Agent One Finance · read-only snapshot · {when}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <HashRouter>
        <App />
        <Banner />
      </HashRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
