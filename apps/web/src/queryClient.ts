import { QueryClient } from "@tanstack/react-query";

// One cache for the console. The office build (Next.js) uses this same client.
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        // Never retry a 4xx: a refusal (403/404) is an answer, not a blip.
        retry: (failureCount: number, error: unknown) => {
          const status = (error as { status?: number })?.status;
          if (status && status >= 400 && status < 500) return false;
          return failureCount < 1;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}
