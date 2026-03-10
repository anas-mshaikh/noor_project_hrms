"use client";

import * as React from "react";
import Link from "next/link";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";

export function PayrollScopeState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
      <EmptyState
        title={title}
        description={description}
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
      <StorePicker />
    </DSCard>
  );
}
