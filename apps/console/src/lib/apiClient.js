const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8100';

export async function get(path) {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function post(path, body, extraHeaders = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    // Surface the server's own explanation: "a rejection requires a reason"
    // is far more useful than "422".
    let detail = '';
    try {
      detail = (await res.json())?.detail ?? '';
    } catch {
      detail = '';
    }
    throw new Error(detail || `POST ${path} failed: ${res.status}`);
  }
  return res.status === 202 || res.status === 204 ? null : res.json();
}
