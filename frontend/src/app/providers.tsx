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

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());

  return (
    <I18nProvider>
      <QueryClientProvider client={client}>
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
