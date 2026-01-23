"use client";

import * as React from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { pageFade } from "@/features/hr/lib/motion";

type HrPageShellProps = {
  children: React.ReactNode;
  className?: string;
};

export function HrPageShell({ children, className }: HrPageShellProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={pageFade(reducedMotion)}
      className={cn("relative", className)}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 left-0 h-72 w-72 rounded-full bg-violet-500/12 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-28 right-0 h-72 w-72 rounded-full bg-fuchsia-500/10 blur-3xl"
      />

      <div className="relative space-y-6">{children}</div>
    </motion.div>
  );
}

