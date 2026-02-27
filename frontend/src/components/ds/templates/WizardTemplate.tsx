"use client";

/**
 * components/ds/templates/WizardTemplate.tsx
 *
 * T5: Wizard scaffold (stepper + content + footer actions).
 *
 * This is layout-only in v0.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function WizardTemplate({
  header,
  stepper,
  content,
  footerActions,
  className,
}: {
  header: React.ReactNode;
  stepper?: React.ReactNode;
  content: React.ReactNode;
  footerActions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header}
      {stepper ? <div>{stepper}</div> : null}
      <div>{content}</div>
      {footerActions ? <div className="pt-2">{footerActions}</div> : null}
    </div>
  );
}

