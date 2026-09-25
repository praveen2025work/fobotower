export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8100';

// Dev only: act as another caller, so a workflow change drafted by one
// person can be approved by another. The API ignores the header unless it
// runs with FOBO_ENV=dev.
export const DEV_CALLER_KEY = 'fobo.devCaller';
let memoryCaller = null;

export function devCaller() {
  try {
    return window.localStorage.getItem(DEV_CALLER_KEY) || memoryCaller;
  } catch {
    return memoryCaller;
  }
}

export function setDevCaller(id) {
  memoryCaller = id || null;
  try {
    if (id) window.localStorage.setItem(DEV_CALLER_KEY, id);
    else window.localStorage.removeItem(DEV_CALLER_KEY);
  } catch {
    // Storage blocked (a private window): the choice lasts until reload.
  }
}

const identity = () => {
  const id = devCaller();
  return id ? { 'X-Dev-Caller': id } : {};
};

/** A failed call, in the server's own words; for a refused workflow change,
 * every problem it listed. */
export class ApiError extends Error {
  constructor(message, { status, errors = [] } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errors = errors;
  }
}

const requestErrors = (detail) =>
  detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`);

async function failure(res, method, path) {
  let detail = '';
  try {
    detail = (await res.json())?.detail ?? '';
  } catch {
    detail = '';
  }
  // A dev caller the server no longer knows (e.g. seeded data changed under
  // a name saved in localStorage) fails every call with this 400 forever,
  // and the switch that would let someone pick a new one never renders
  // because every call — including the one that loads it — fails the same
  // way. Clearing it here breaks that lock: the next load falls back to no
  // identity, and the switch appears again.
  if (res.status === 400 && typeof detail === 'string' && detail.startsWith('unknown dev caller')) {
    setDevCaller(null);
  }
  const fallback = `${method} ${path} failed: ${res.status}`;
  if (Array.isArray(detail)) {
    const errors = requestErrors(detail);
    return new ApiError(errors.join('; ') || fallback, { status: res.status, errors });
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(detail.message || fallback, {
      status: res.status,
      errors: detail.errors || [],
    });
  }
  // Surface the server's own explanation: "a rejection requires a reason"
  // is far more useful than "422".
  return new ApiError(detail || fallback, { status: res.status });
}

async function fetchOk(method, path, init) {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw await failure(res, method, path);
  return res;
}

export async function get(path) {
  const res = await fetchOk('GET', path, { cache: 'no-store', headers: identity() });
  return res.json();
}

export async function getText(path) {
  const res = await fetchOk('GET', path, { cache: 'no-store', headers: identity() });
  return res.text();
}

export async function post(path, body, extraHeaders = {}) {
  const res = await fetchOk('POST', path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...identity(), ...extraHeaders },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.status === 202 || res.status === 204 ? null : res.json();
}
