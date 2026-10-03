/** A random id, from the Web Crypto API where it is available. Outside a
 *  secure context — plain HTTP on a non-localhost origin — `crypto.randomUUID`
 *  is undefined, so this falls back to a value that is unique enough for a
 *  client-side idempotency or confirmation key. */
export function randomId() {
  return globalThis.crypto?.randomUUID?.() ?? `id-${Date.now()}-${Math.random()}`;
}
