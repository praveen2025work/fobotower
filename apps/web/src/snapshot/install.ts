// Read-only snapshot mode: GET /api/* (pages, and the files behind download
// buttons) is answered from responses recorded by scripts/capture-snapshot.mjs;
// anything that would change data is refused.
// The one POST answered is a configuration check (it stores nothing), and only
// for the exact body that was recorded: an edited configuration still needs the
// live service. Used only by the snapshot build (snapshot.html), never by the real app.

interface Recorded {
  status: number;
  body: unknown;
  /** A download (Excel, PDF), recorded as its bytes. */
  file?: { type: string; base64: string };
}
export interface Snapshot {
  user: string;
  captured_at: string;
  responses: Record<string, Recorded>;
}

/** FNV-1a of a request body; capture-snapshot.mjs keys recorded checks the same way. */
export function bodyKey(body: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < body.length; i++) h = Math.imul(h ^ body.charCodeAt(i), 0x01000193) >>> 0;
  return h.toString(16);
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
    if (method !== "GET") {
      const check = url.pathname.endsWith("/check") && typeof init?.body === "string"
        ? snap.responses[`POST ${key} ${bodyKey(init.body)}`] : undefined;
      return check ? json(check.status, check.body) : json(403, { detail: "This is a read-only snapshot: changes are not saved." });
    }
    const hit = snap.responses[key] ?? snap.responses[url.pathname.slice(at)];
    if (hit?.file) {
      const bytes = Uint8Array.from(atob(hit.file.base64), (ch) => ch.charCodeAt(0));
      return new Response(bytes, { status: hit.status, headers: { "Content-Type": hit.file.type } });
    }
    return hit ? json(hit.status, hit.body) : json(404, { detail: "Not part of this snapshot." });
  };
}
