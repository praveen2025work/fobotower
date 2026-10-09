// Generated from apps/web/src/queryClient.ts by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { QueryClient } from "@tanstack/react-query";

// One cache for the console. The office build (Next.js) uses this same client.
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        // Never retry a 4xx: a refusal (403/404) is an answer, not a blip.
        retry: (failureCount, error) => {
          const status = error?.status;
          if (status && status >= 400 && status < 500) return false;
          return failureCount < 1;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}
