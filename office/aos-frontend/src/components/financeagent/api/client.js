// Generated from apps/web/src/api/client.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// The Agent One Finance API client. Identity is one header: in the office the SSO proxy
// sets it and this module sends nothing; in development the user switcher
// picks a fixture user. Roles and data scopes are always the server's call.

export const API_BASE = process.env.NEXT_PUBLIC_AOF_API ?? "/api";
const USER_KEY = "aof.user";
let memoryUser = null;

export function currentUser() {
  try {
    return window.localStorage.getItem(USER_KEY) ?? memoryUser;
  } catch {
    return memoryUser;
  }
}

export function setCurrentUser(id) {
  memoryUser = id;
  try {
    window.localStorage.setItem(USER_KEY, id);
  } catch {
    // storage blocked: the choice lasts until reload
  }
}

export class ApiError extends Error {
  status;
  problems;

  constructor(message, status, problems = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problems = problems;
  }
}

async function request(method, path, body) {
  const user = currentUser();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(user ? { "X-AOF-User": user } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return undefined;
  if (res.ok) return await res.json();
  let message = `${method} ${path} failed (${res.status})`;
  let problems = [];
  try {
    const detail = (await res.json()).detail;
    if (typeof detail === "string") message = detail;
    else if (detail?.message) {
      message = detail.message;
      problems = detail.problems ?? [];
    }
  } catch {
    // keep the generic message
  }
  throw new ApiError(message, res.status, problems);
}

/** POST a multipart form (file uploads) with the identity header. */
export async function upload(path, form) {
  const user = currentUser();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    headers: user ? { "X-AOF-User": user } : {},
  });
  if (res.ok) return await res.json();
  let message = `upload failed (${res.status})`;
  try {
    const detail = (await res.json()).detail;
    if (typeof detail === "string") message = detail;
  } catch {
    // keep the generic message
  }
  throw new ApiError(message, res.status);
}

/** Fetch a file the API serves (it needs the identity header too) and save it. */
export async function download(path, filename) {
  const user = currentUser();
  const res = await fetch(`${API_BASE}${path}`, { headers: user ? { "X-AOF-User": user } : {} });
  if (!res.ok) throw new ApiError(`download failed (${res.status})`, res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  del: (path) => request("DELETE", path),
};

export function newIdempotencyKey() {
  return globalThis.crypto?.randomUUID?.() ?? `key-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
