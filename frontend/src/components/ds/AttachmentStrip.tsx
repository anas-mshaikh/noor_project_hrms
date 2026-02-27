"use client";

/**
 * components/ds/AttachmentStrip.tsx
 *
 * Minimal attachment chip list.
 */

import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export type AttachmentChip = {
  id: string;
  label: string;
  onClick?: () => void;
};

export function AttachmentStrip({
  items,
  className,
}: {
  items: AttachmentChip[];
  className?: string;
}) {
  if (!items.length) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {items.map((it) => (
        <Button
          key={it.id}
          type="button"
          variant="outline"
          size="sm"
          onClick={it.onClick}
          className="border-border-subtle bg-surface-1 hover:bg-surface-2"
        >
          {it.label}
        </Button>
      ))}
    </div>
  );
}

