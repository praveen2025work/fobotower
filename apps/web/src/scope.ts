// What a read-only snapshot shows (scripts/capture-snapshot.mjs): everything ("all"),
// chosen agents with their tasks ("agents", SNAPSHOT_AGENTS), or only their
// configuration ("config", SNAPSHOT_SCOPE=config). The live console always shows everything.
type Scope = "all" | "agents" | "config";
const scope = (): Scope => (globalThis as { __aofSnapshotScope?: Scope }).__aofSnapshotScope ?? "all";

/** Agents and their configuration only: no tasks, inbox or operations. */
export function configOnly(): boolean {
  return scope() === "config";
}

/** The platform pages (operations, audit, authoring), left out of a snapshot of chosen agents. */
export function platformPages(): boolean {
  return scope() === "all";
}

/** Whether a page's data is in the snapshot (always, in the live console): a snapshot
 *  holds a few tasks in full and the rest only as rows of a summary. `apiPath`: /cases/<id>. */
export function recorded(apiPath: string): boolean {
  const has = (globalThis as { __aofSnapshotHas?: (path: string) => boolean }).__aofSnapshotHas;
  return has ? has(apiPath) : true;
}
