"use client";

/**
 * Global error boundary.
 *
 * This catches errors thrown from the root layout itself (rare, but important).
 */

import { ErrorState } from "@/components/ErrorState";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <div className="min-h-screen p-6 text-foreground">
          <ErrorState title="App error" error={error} onRetry={reset} />
        </div>
      </body>
    </html>
  );
}
