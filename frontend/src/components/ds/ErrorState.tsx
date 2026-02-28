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
import { getErrorUx } from "@/lib/errorUx";
import { useSelection } from "@/lib/selection";
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
  const ux = getErrorUx(error);
  const message = apiErr
    ? ux.description
    : error instanceof Error
      ? error.message
      : "Unexpected error";

  const resetSelection = useSelection((s) => s.reset);
  const [copied, setCopied] = React.useState(false);

  const correlationId = apiErr?.correlationId ?? null;
  const canCopy = Boolean(correlationId && typeof navigator !== "undefined" && navigator.clipboard);

  const headerTitle = apiErr ? ux.title : title;
  const showScopeCtas =
    apiErr?.code.startsWith("iam.scope.") || ux.suggestedActionKind === "reset_scope";
  const showLoginCta = apiErr?.status === 401 || ux.suggestedActionKind === "go_login";

  const content = (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="text-base font-semibold tracking-tight text-text-1">
          {headerTitle}
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
              {correlationId ? (
                <div className="flex flex-wrap items-center gap-2">
                  <div>
                    <span className="text-text-2">reference</span>:{" "}
                    <span className="font-mono text-xs">{correlationId}</span>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!canCopy}
                    onClick={() => {
                      if (!correlationId) return;
                      void navigator.clipboard.writeText(correlationId).then(
                        () => {
                          setCopied(true);
                          window.setTimeout(() => setCopied(false), 1200);
                        },
                        () => {
                          // Best-effort only.
                        }
                      );
                    }}
                  >
                    {copied ? "Copied" : "Copy ref"}
                  </Button>
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
        {showScopeCtas ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              resetSelection();
              window.location.assign("/scope?reason=iam.scope.forbidden");
            }}
          >
            Reset selection
          </Button>
        ) : null}
        <Button asChild variant={showScopeCtas ? "outline" : "secondary"}>
          <Link href="/scope">Scope</Link>
        </Button>
        {showLoginCta ? (
          <Button asChild variant="outline">
            <Link href="/login">Sign in</Link>
          </Button>
        ) : null}
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
