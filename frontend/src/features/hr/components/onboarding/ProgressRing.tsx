"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type ProgressRingProps = {
  value: number; // 0..100
  size?: number;
  stroke?: number;
  className?: string;
};

export function ProgressRing({
  value,
  size = 44,
  stroke = 5,
  className,
}: ProgressRingProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = (clamped / 100) * c;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg width={size} height={size} className="block">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="transparent"
          stroke="rgba(255,255,255,0.10)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="transparent"
          stroke="rgba(168,85,247,0.9)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute text-xs font-medium tabular-nums text-foreground/80">
        {Math.round(clamped)}%
      </div>
    </div>
  );
}

