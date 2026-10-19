// What a read-only snapshot shows. A config-only snapshot (SNAPSHOT_SCOPE=config in
// scripts/capture-snapshot.mjs) shows agents and their configuration, without tasks,
// inbox or operations; the live console always shows everything.
export function configOnly(): boolean {
  return (globalThis as { __aofSnapshotScope?: string }).__aofSnapshotScope === "config";
}
