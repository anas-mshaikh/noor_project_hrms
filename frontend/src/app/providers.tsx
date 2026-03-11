"use client";

/**
 * app/providers.tsx
 *
 * React Query provider:
 * - caching
 * - polling job status later
 */

import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

import { I18nProvider } from "@/lib/i18n";
import { AuthBootstrap } from "@/components/AuthBootstrap";
import { ScopeQueryReset } from "@/components/ScopeQueryReset";
import { createQueryClient } from "@/lib/queryClient";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => createQueryClient());

  return (
    <I18nProvider>
      <QueryClientProvider client={client}>
        <ScopeQueryReset />
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
