"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";

import { cn } from "@/lib/utils";
import { glassCard } from "@/features/hr/lib/theme";

type GlassCardProps = React.HTMLAttributes<HTMLDivElement> & {
  asChild?: boolean;
};

export function GlassCard({ asChild, className, ...props }: GlassCardProps) {
  const Comp = asChild ? Slot : "div";
  return <Comp className={cn(glassCard(), className)} {...props} />;
}

