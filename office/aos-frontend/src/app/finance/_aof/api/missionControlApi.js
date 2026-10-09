// Generated from apps/web/src/api/missionControlApi.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// aria-ai's Mission Control types, kept with the same shapes so its components
// (components/mission-control/*) are reused unchanged — fed by Agent One Finance's one
// /api/operations endpoint instead of aria-ai's seven.

import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export function useOperations() {
  return useQuery({
    queryKey: ["operations"],
    queryFn: () => api.get("/operations"),
    refetchInterval: 15_000,
  });
}
