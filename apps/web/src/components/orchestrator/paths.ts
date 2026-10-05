// Dotted-path helpers over a manifest held as plain JSON, and the rules for
// what a team group may set (its capability's `configurable` paths).

export type Json = Record<string, unknown>;

export function get(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Json)[k] : undefined), obj);
}

/** A copy of obj with value at a dotted path (objects on the way are copied, not mutated). */
export function setPath(obj: Json, path: string, value: unknown): Json {
  const [head, ...rest] = path.split(".");
  const out = { ...obj };
  out[head] = rest.length ? setPath(((obj[head] as Json) ?? {}) as Json, rest.join("."), value) : value;
  return out;
}

/** May an owner with these `configurable` paths set `path`? null = anything (the capability's own owners). */
export function allowed(configurable: string[] | null, path: string): boolean {
  if (configurable === null) return true;
  return configurable.some(
    (c) => c === path || path.startsWith(`${c}.`) || (c.endsWith(".*") && path.startsWith(c.slice(0, -1))),
  );
}

export function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** Every path where two manifests differ, down to the first array or value. */
export function changedPaths(before: unknown, after: unknown, prefix = ""): string[] {
  const isObj = (v: unknown) => !!v && typeof v === "object" && !Array.isArray(v);
  if (isObj(before) && isObj(after)) {
    const keys = [...new Set([...Object.keys(before as Json), ...Object.keys(after as Json)])];
    return keys.flatMap((k) => changedPaths((before as Json)[k], (after as Json)[k], prefix ? `${prefix}.${k}` : k));
  }
  return same(before, after) ? [] : [prefix];
}

/**
 * A team group's `set` after an edit: for each configurable path whose value
 * changed, the new value is written at that path (a group replaces the
 * capability's value there, exactly as the server merges it).
 */
export function groupSet(currentSet: Json, configurable: string[], before: Json, after: Json): Json {
  let out = currentSet;
  for (const pattern of configurable) {
    const paths = pattern.endsWith(".*")
      ? [...new Set([
          ...Object.keys((get(before, pattern.slice(0, -2)) as Json) ?? {}),
          ...Object.keys((get(after, pattern.slice(0, -2)) as Json) ?? {}),
        ])].map((k) => `${pattern.slice(0, -2)}.${k}`)
      : [pattern];
    for (const p of paths) {
      if (!same(get(before, p), get(after, p))) out = setPath(out, p, get(after, p) ?? null);
    }
  }
  return out;
}

/** A short, readable rendering of a value for "before → after". */
export function preview(v: unknown): string {
  if (v === undefined || v === null || v === "") return "—";
  if (typeof v === "string") return v.length > 60 ? `${v.slice(0, 57)}…` : v;
  if (Array.isArray(v)) return v.length === 0 ? "none" : v.every((x) => typeof x !== "object") ? v.join(", ") : `${v.length} entries`;
  if (typeof v === "object") return `${Object.keys(v as Json).length} settings`;
  return String(v);
}
