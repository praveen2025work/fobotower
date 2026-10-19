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
