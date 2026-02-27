"use client";

/**
 * Root segment error boundary.
 *
 * This prevents one failing page/module from crashing the entire shell.
 */

import { ErrorState } from "@/components/ErrorState";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorState title="Something went wrong" error={error} onRetry={reset} />;
}

