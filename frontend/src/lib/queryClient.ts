"use client";

/**
 * lib/queryClient.ts
 *
 * Single source of truth for React Query defaults.
 *
 * Why:
 * - Tests should use the same defaults as production to surface retry/refetch bugs early.
 * - Centralizing defaults avoids drift between app and test harnesses.
 */

import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        // Avoid retry storms on permission/scope errors.
        retry: (failureCount, error) => {
          if (failureCount >= 2) return false;
          if (error instanceof ApiError) {
            if (error.isNetworkError || error.status === 0) return true;
            if (error.status >= 500) return true;
            return false;
          }
          // Unknown errors: retry once.
          return failureCount < 1;
        },
        staleTime: 30_000,
        gcTime: 5 * 60_000,
      },
      mutations: {
        // Mutations are often non-idempotent; default to no retries.
        retry: false,
      },
    },
  });
}

