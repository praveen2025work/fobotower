// Generated from apps/web/src/scope.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// What a read-only snapshot shows (scripts/capture-snapshot.mjs): everything ("all"),
// chosen agents with their tasks ("agents", SNAPSHOT_AGENTS), or only their
// configuration ("config", SNAPSHOT_SCOPE=config). The live console always shows everything.

const scope = () => globalThis.__aofSnapshotScope ?? "all";

/** Agents and their configuration only: no tasks, inbox or operations. */
export function configOnly() {
  return scope() === "config";
}

/** The platform pages (operations, audit, authoring), left out of a snapshot of chosen agents. */
export function platformPages() {
  return scope() === "all";
}

/** Whether a page's data is in the snapshot (always, in the live console): a snapshot
 *  holds a few tasks in full and the rest only as rows of a summary. `apiPath`: /tasks/<id>. */
export function recorded(apiPath) {
  const has = globalThis.__aofSnapshotHas;
  return has ? has(apiPath) : true;
}
