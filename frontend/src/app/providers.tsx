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

export function Providers({ children }: { children: React.ReactNode }) {
  // Create once per browser session
  const [client] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster
        position="top-right"
        closeButton
        richColors
        toastOptions={{
          // Keep toasts readable on both the default light UI and HR dark surfaces.
          className: "bg-background text-foreground border",
        }}
      />
    </QueryClientProvider>
  );
}
