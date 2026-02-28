"use client";

/**
 * app/providers.tsx
 *
 * React Query provider:
 * - caching
 * - polling job status later
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

import { I18nProvider } from "@/lib/i18n";
import { AuthBootstrap } from "@/components/AuthBootstrap";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
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
      })
  );

  return (
    <I18nProvider>
      <QueryClientProvider client={client}>
        <AuthBootstrap />
        {children}
        <Toaster
          position="top-right"
          closeButton
          richColors
          toastOptions={{
            className: "bg-background text-foreground border",
          }}
        />
      </QueryClientProvider>
    </I18nProvider>
  );
}
