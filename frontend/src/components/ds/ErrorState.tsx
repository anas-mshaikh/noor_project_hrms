"use client";

/**
 * components/ds/ErrorState.tsx
 *
 * Shared, correlation-aware error rendering (design-system styled).
 *
 * Keep this dependency-light so it can be used from:
 * - Next.js App Router error boundaries (`error.tsx`, `global-error.tsx`)
 * - Page-level error states
 */

import * as React from "react";
import Link from "next/link";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DSCard } from "@/components/ds/DSCard";

export function ErrorState({
  title,
  error,
  onRetry,
  className,
  details,
  variant = "card",
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
  details?: React.ReactNode;
  variant?: "card" | "inline";
}) {
  const apiErr = error instanceof ApiError ? error : null;
  const message =
    apiErr?.message ?? (error instanceof Error ? error.message : "Unexpected error");

  const content = (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="text-base font-semibold tracking-tight text-text-1">
          {title}
        </div>
        <div className="text-sm text-text-2">{message}</div>
      </div>

      {apiErr || details ? (
        <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-[var(--ds-space-16)] text-sm">
          {apiErr ? (
            <div className="space-y-1">
              <div>
                <span className="text-text-2">status</span>: {apiErr.status}
              </div>
              {apiErr.code ? (
                <div>
                  <span className="text-text-2">code</span>: {apiErr.code}
                </div>
              ) : null}
              {apiErr.correlationId ? (
                <div>
                  <span className="text-text-2">correlation_id</span>:{" "}
                  <span className="font-mono text-xs">{apiErr.correlationId}</span>
                </div>
              ) : null}
            </div>
          ) : null}
          {details ? <div className="mt-3">{details}</div> : null}
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
    </div>
  );

  return (
    <div className={cn("mx-auto max-w-2xl", className)}>
      {variant === "inline" ? (
        content
      ) : (
        <DSCard surface="card" className="p-[var(--ds-space-20)]">
          {content}
        </DSCard>
      )}
    </div>
  );
}
