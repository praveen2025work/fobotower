// Entry for the read-only snapshot build (npm run build:snapshot): the real
// app, hash-routed, over recorded data, with a banner saying what it is and, for
// a snapshot of chosen agents, the walkthrough of its example tasks.
import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";
import "../index.css";
import { installSnapshot, type Snapshot } from "./install";
import Walkthrough from "./Walkthrough";

// Written by scripts/capture-snapshot.mjs: the recorded responses, gzipped and
// base64-encoded (most of it is run state that repeats).
const packed = import.meta.glob<string>("./data.b64", { eager: true, query: "?raw", import: "default" })["./data.b64"];

async function unpack(b64: string | undefined): Promise<Snapshot> {
  if (!b64) return { user: "", captured_at: new Date().toISOString(), responses: {} };
  const bytes = Uint8Array.from(atob(b64.trim()), (ch) => ch.charCodeAt(0));
  const text = await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return JSON.parse(text) as Snapshot;
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, refetchInterval: false, staleTime: Infinity } },
});

function Banner({ capturedAt }: { capturedAt: string }) {
  const when = new Date(capturedAt).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    // On phones it sits above the bottom navigation, not over its labels.
    <div className="wt-banner hx-topbar hx-pop pointer-events-none fixed bottom-[calc(env(safe-area-inset-bottom)+4rem)] right-3 z-50 flex items-center lg:bottom-3 gap-2 rounded-full border border-surface-200 px-3 py-1.5 text-[11px] font-medium text-surface-700 shadow-lg">
      <span className="hx-live text-accent-500" aria-hidden="true" />
      Agent One Finance · read-only snapshot · {when}
    </div>
  );
}

const root = document.getElementById("root")!;
if (typeof DecompressionStream === "undefined") {
  root.textContent = "This snapshot needs a current browser: Chrome, Edge, Firefox or Safari 16.4 or later.";
} else {
  unpack(packed).then((snap) => {
    installSnapshot(snap);
    // A showcase: the sidebar opens with its labels, unless the walkthrough needs the
    // room (a viewer's own choice still wins).
    try {
      if (snap.scope !== "agents" && localStorage.getItem("aof.nav.collapsed") === null) localStorage.setItem("aof.nav.collapsed", "0");
    } catch {
      /* storage unavailable: the sidebar keeps its default */
    }
    // A config-only snapshot opens on the agents and stays on configuration pages; a
    // snapshot of chosen agents has no platform pages.
    const allowed = (hash: string) =>
      snap.scope === "config" ? /^#\/(capabilities|connectors)(\/|$)/.test(hash)
        : snap.scope !== "agents" || !/^#\/(operations|audit|authoring)(\/|$)/.test(hash);
    const onPage = () => {
      if (!allowed(location.hash)) location.replace(snap.scope === "config" ? "#/capabilities" : "#/");
    };
    onPage();
    window.addEventListener("hashchange", onPage);
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <HashRouter>
            <App />
            <Banner capturedAt={snap.captured_at} />
            {snap.scope === "agents" && <Walkthrough recorded={(route) => `/api${route.split("?")[0]}` in snap.responses} />}
          </HashRouter>
        </QueryClientProvider>
      </React.StrictMode>,
    );
  });
}
