"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        // App-wide "glass" surface so existing pages automatically inherit the new theme.
        "relative overflow-hidden rounded-2xl border border-border bg-white/[0.03] text-card-foreground shadow-[0_18px_60px_-40px_rgba(0,0,0,0.85)] backdrop-blur-xl",
        // Soft inner highlight (kept subtle so it doesn't distract on dense pages).
        "before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(900px_circle_at_10%_0%,rgba(168,85,247,0.10),transparent_55%),radial-gradient(700px_circle_at_90%_10%,rgba(236,72,153,0.07),transparent_55%)] before:opacity-80",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pb-3", className)} {...props} />;
}

export function CardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-base font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("mt-1 text-sm text-muted-foreground", className)} {...props} />
  );
}

export function CardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

export function CardFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center justify-end gap-2 p-5 pt-0", className)} {...props} />
  );
}
