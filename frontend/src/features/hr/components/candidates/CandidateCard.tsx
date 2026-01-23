"use client";

import * as React from "react";

import type { HrCandidate } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";

type CandidateCardProps = {
  candidate: HrCandidate;
  rank?: number;
  meta?: React.ReactNode;
  onClick?: () => void;
  className?: string;
};

export function CandidateCard({
  candidate,
  rank,
  meta,
  onClick,
  className,
}: CandidateCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-2xl bg-white/[0.02] p-4 text-left ring-1 ring-white/5",
        "hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/60",
        className
      )}
      aria-label={`Open candidate ${candidate.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {typeof rank === "number" ? (
              <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10 tabular-nums">
                #{rank}
              </span>
            ) : null}
            <div className="truncate text-sm font-semibold tracking-tight">
              {candidate.name}
            </div>
          </div>
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {candidate.current_title}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ScorePill score={candidate.score} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {candidate.tags.slice(0, 3).map((t) => (
          <TagChip key={t} className="bg-white/[0.03]">
            {t}
          </TagChip>
        ))}
      </div>

      {meta ? <div className="mt-3 text-xs text-muted-foreground">{meta}</div> : null}
    </button>
  );
}

