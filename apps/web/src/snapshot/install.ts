// Read-only snapshot mode: GET /api/* is answered from responses recorded by
// scripts/capture-snapshot.mjs; anything that would change data is refused.
// Used only by the snapshot build (snapshot.html), never by the real app.

interface Recorded {
  status: number;
  body: unknown;
}
export interface Snapshot {
  user: string;
  captured_at: string;
  responses: Record<string, Recorded>;
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function installSnapshot(snap: Snapshot, apiBase = "/api"): void {
  try {
    localStorage.setItem("aof.user", snap.user);
  } catch {
    /* storage unavailable: the app falls back to its default user */
  }
  const real = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, location.href);
    const at = url.pathname.indexOf(apiBase + "/");
    if (at < 0) return real(input, init);
    const key = url.pathname.slice(at) + url.search;
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    if (method !== "GET") return json(403, { detail: "This is a read-only snapshot: changes are not saved." });
    const hit = snap.responses[key] ?? snap.responses[url.pathname.slice(at)];
    return hit ? json(hit.status, hit.body) : json(404, { detail: "Not part of this snapshot." });
  };
}
