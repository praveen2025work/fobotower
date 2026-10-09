// The Agent One Finance API client. Identity is one header: in the office the SSO proxy
// sets it and this module sends nothing; in development the user switcher
// picks a fixture user. Roles and data scopes are always the server's call.

export const API_BASE = import.meta.env.VITE_AOF_API ?? "/api";
const USER_KEY = "aof.user";
let memoryUser: string | null = null;

type HeaderSource = () => Record<string, string> | Promise<Record<string, string>>;
let signOn: HeaderSource = () => ({});

/** Extra headers for every API call, such as a sign-on token. Upstream sends none; the
 *  office build sets them in one office-owned file (office/auth.js). */
export function setRequestHeaders(source: HeaderSource): void {
  signOn = source;
}

async function identity(): Promise<Record<string, string>> {
  const user = currentUser();
  return { ...(await signOn()), ...(user ? { "X-AOF-User": user } : {}) };
}

export function currentUser(): string | null {
  try {
    return window.localStorage.getItem(USER_KEY) ?? memoryUser;
  } catch {
    return memoryUser;
  }
}

export function setCurrentUser(id: string): void {
  memoryUser = id;
  try {
    window.localStorage.setItem(USER_KEY, id);
  } catch {
    // storage blocked: the choice lasts until reload
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly problems: string[];

  constructor(message: string, status: number, problems: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problems = problems;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(await identity()),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  if (res.ok) return (await res.json()) as T;
  let message = `${method} ${path} failed (${res.status})`;
  let problems: string[] = [];
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
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form, headers: await identity() });
  if (res.ok) return (await res.json()) as T;
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
export async function download(path: string, filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { headers: await identity() });
  if (!res.ok) throw new ApiError(`download failed (${res.status})`, res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body: unknown) => request<T>("POST", path, body),
  del: (path: string) => request<void>("DELETE", path),
};

export function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `key-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
