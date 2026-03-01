"use client";

/**
 * test/utils/render.tsx
 *
 * Canonical render helper for component/page tests.
 *
 * Rules:
 * - Always wrap in the same providers as production (QueryClient + I18n).
 * - Prefer MSW over ad-hoc fetch mocks.
 */

import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";

import { I18nProvider } from "@/lib/i18n";
import { createQueryClient } from "@/lib/queryClient";

export function renderWithProviders(
  ui: React.ReactElement,
  opts?: RenderOptions & { queryClient?: ReturnType<typeof createQueryClient> }
) {
  const queryClient = opts?.queryClient ?? createQueryClient();
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>{children}</I18nProvider>
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper, ...opts });
}

