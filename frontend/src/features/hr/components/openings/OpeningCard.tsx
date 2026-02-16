"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Briefcase, MapPin } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

import type { HrOpening } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";

type OpeningCardProps = {
  opening: HrOpening;
  className?: string;
};

export function OpeningCard({ opening, className }: OpeningCardProps) {
  const { t } = useTranslation();

  return (
    <GlassCard asChild className={cn("p-5", className)}>
      <Link href={`/hr/openings/${opening.id}`} className="block">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-base font-semibold tracking-tight">
              {opening.title}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Briefcase className="h-3.5 w-3.5" />
                {opening.department}
              </span>
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {opening.location}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ScorePill score={opening.in_pipeline_count * 4 + 50} />
            <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <TagChip>{opening.status}</TagChip>
          <TagChip>
            {opening.resumes_count}{" "}
            {t("hr.opening_card.resumes_suffix", { defaultValue: "resumes" })}
          </TagChip>
          <TagChip>
            {opening.in_pipeline_count}{" "}
            {t("hr.opening_card.in_pipeline_suffix", { defaultValue: "in pipeline" })}
          </TagChip>
        </div>
      </Link>
    </GlassCard>
  );
}
