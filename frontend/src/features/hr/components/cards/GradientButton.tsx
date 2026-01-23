"use client";

import * as React from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { accentGradient } from "@/features/hr/lib/theme";

export function GradientButton({ className, variant, ...props }: ButtonProps) {
  return (
    <Button
      variant={variant ?? "default"}
      className={cn("relative overflow-hidden", accentGradient(), className)}
      {...props}
    />
  );
}

