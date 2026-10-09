// The office's sign-on for AOF API calls: the one console file the office owns.
// aof_sync.py adds it once and never overwrites it.
//
// Return the headers Agent One's API needs on every AOF call, for example
//   import { getAccessToken } from "@/lib/sso";
//   export async function aofRequestHeaders() { return { Authorization: `Bearer ${await getAccessToken()}` }; }
// Cookies are sent anyway (same origin). Return {} when the proxy adds identity itself.

export function aofRequestHeaders() {
  return {};
}
