// The Agent One Finance API client. Identity is one header; in the office the SSO proxy
// sets it, here the user switcher does. Roles and data scopes are always
// decided by the server.
export const AOF_API = process.env.NEXT_PUBLIC_AOF_API ?? 'http://localhost:8300';
const USER_KEY = 'aof.user';
let memoryUser = null;

export function currentUser() {
  try {
    return window.localStorage.getItem(USER_KEY) || memoryUser;
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

export class AofError extends Error {
  constructor(message, { status, problems = [] } = {}) {
    super(message);
    this.name = 'AofError';
    this.status = status;
    this.problems = problems;
  }
}

async function request(method, path, body) {
  const user = currentUser();
  const res = await fetch(`${AOF_API}${path}`, {
    method,
    headers: {
      ...(user ? { 'X-AOF-User': user } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.ok) return res.json();
  let detail = `${method} ${path} failed (${res.status})`;
  let problems = [];
  try {
    const d = (await res.json()).detail;
    if (typeof d === 'string') detail = d;
    else if (d?.message) ({ message: detail, problems = [] } = d);
  } catch {
    // keep the generic message
  }
  throw new AofError(detail, { status: res.status, problems });
}

export const fetchDevUsers = () => request('GET', '/api/dev/users');
export const fetchMe = () => request('GET', '/api/me');
export const fetchCapabilities = () => request('GET', '/api/capabilities');
export const fetchCases = (capabilityId) =>
  request('GET', `/api/capabilities/${encodeURIComponent(capabilityId)}/cases`);
export const openCase = (capabilityId, caseKey) =>
  request('POST', `/api/capabilities/${encodeURIComponent(capabilityId)}/cases`, {
    case_key: caseKey,
  });
export const fetchCase = (caseId) => request('GET', `/api/cases/${encodeURIComponent(caseId)}`);
export const decide = (caseId, { groupId, action, comment, idempotencyKey }) =>
  request('POST', `/api/cases/${encodeURIComponent(caseId)}/decisions`, {
    group_id: groupId,
    action,
    comment: comment || null,
    idempotency_key: idempotencyKey,
  });
