// Generated from apps/web/src/components/orchestrator/paths.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Dotted-path helpers over a manifest held as plain JSON, and the rules for
// what a team group may set (its capability's `configurable` paths).

export function get(obj, path) {
  return path.split(".").reduce((o, k) => (o && typeof o === "object" ? o[k] : undefined), obj);
}

/** A copy of obj with value at a dotted path (objects on the way are copied, not mutated). */
export function setPath(obj, path, value) {
  const [head, ...rest] = path.split(".");
  const out = { ...obj };
  out[head] = rest.length ? setPath(obj[head] ?? {}, rest.join("."), value) : value;
  return out;
}

/** May an owner with these `configurable` paths set `path`? null = anything (the capability's own owners). */
export function allowed(configurable, path) {
  if (configurable === null) return true;
  return configurable.some(
    (c) => c === path || path.startsWith(`${c}.`) || (c.endsWith(".*") && path.startsWith(c.slice(0, -1))),
  );
}

export function same(a, b) {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** Every path where two manifests differ, down to the first array or value. */
export function changedPaths(before, after, prefix = "") {
  const isObj = (v) => !!v && typeof v === "object" && !Array.isArray(v);
  if (isObj(before) && isObj(after)) {
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
    return keys.flatMap((k) => changedPaths(before[k], after[k], prefix ? `${prefix}.${k}` : k));
  }
  return same(before, after) ? [] : [prefix];
}

/**
 * A team group's `set` after an edit: for each configurable path whose value
 * changed, the new value is written at that path (a group replaces the
 * capability's value there, exactly as the server merges it).
 */
export function groupSet(currentSet, configurable, before, after) {
  let out = currentSet;
  for (const pattern of configurable) {
    const paths = pattern.endsWith(".*")
      ? [
          ...new Set([
            ...Object.keys(get(before, pattern.slice(0, -2)) ?? {}),
            ...Object.keys(get(after, pattern.slice(0, -2)) ?? {}),
          ]),
        ].map((k) => `${pattern.slice(0, -2)}.${k}`)
      : [pattern];
    for (const p of paths) {
      if (!same(get(before, p), get(after, p))) out = setPath(out, p, get(after, p) ?? null);
    }
  }
  return out;
}

/** A short, readable rendering of a value for "before → after". */
export function preview(v) {
  if (v === undefined || v === null || v === "") return "—";
  if (typeof v === "string") return v.length > 60 ? `${v.slice(0, 57)}…` : v;
  if (Array.isArray(v))
    return v.length === 0 ? "none" : v.every((x) => typeof x !== "object") ? v.join(", ") : `${v.length} entries`;
  if (typeof v === "object") return `${Object.keys(v).length} settings`;
  return String(v);
}
