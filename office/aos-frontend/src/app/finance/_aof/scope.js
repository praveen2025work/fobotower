// Generated from apps/web/src/scope.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// What a read-only snapshot shows. A config-only snapshot (SNAPSHOT_SCOPE=config in
// scripts/capture-snapshot.mjs) shows agents and their configuration, without tasks,
// inbox or operations; the live console always shows everything.
export function configOnly() {
  return globalThis.__aofSnapshotScope === "config";
}
