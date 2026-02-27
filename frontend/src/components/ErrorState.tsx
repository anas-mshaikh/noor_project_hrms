"use client";

/**
 * components/ErrorState.tsx
 *
 * Shared, correlation-aware error rendering.
 *
 * This is intentionally small and dependency-free so it can be used from:
 * - Next.js App Router error boundaries (`error.tsx`, `global-error.tsx`)
 * - Page-level catch blocks if needed
 */

import Link from "next/link";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ErrorState({
  title,
  error,
  onRetry,
  className,
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const apiErr = error instanceof ApiError ? error : null;
  const message =
    apiErr?.message ??
    (error instanceof Error ? error.message : "Unexpected error");

  return (
    <div className={cn("mx-auto max-w-2xl", className)}>
      <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
        <CardHeader>
          <CardTitle className="tracking-tight">{title}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {message}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {apiErr ? (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-sm">
              <div>
                <span className="text-muted-foreground">status</span>: {apiErr.status}
              </div>
              {apiErr.code ? (
                <div>
                  <span className="text-muted-foreground">code</span>: {apiErr.code}
                </div>
              ) : null}
              {apiErr.correlationId ? (
                <div>
                  <span className="text-muted-foreground">correlation_id</span>:{" "}
                  <span className="font-mono text-xs">{apiErr.correlationId}</span>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {onRetry ? (
              <Button type="button" onClick={onRetry}>
                Try again
              </Button>
            ) : null}
            <Button asChild variant="secondary">
              <Link href="/scope">Scope</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

