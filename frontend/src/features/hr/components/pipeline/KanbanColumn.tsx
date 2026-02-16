"use client";

import * as React from "react";
import { useTranslation } from "@/lib/i18n";

import { GlassCard } from "@/features/hr/components/cards/GlassCard";
import { KanbanCard } from "@/features/hr/components/pipeline/KanbanCard";
import type {
  PipelineCardUi,
  PipelineStageUi,
} from "@/features/hr/components/pipeline/types";

type KanbanColumnProps = {
  stage: PipelineStageUi;
  cards: PipelineCardUi[];
  stages: PipelineStageUi[];
  onMove?: (cardId: string, stageId: string) => void;
  onOpenCandidate?: (cardId: string) => void;
};

export function KanbanColumn({
  stage,
  cards,
  stages,
  onMove,
  onOpenCandidate,
}: KanbanColumnProps) {
  const { t } = useTranslation();
  return (
    <GlassCard className="p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold tracking-tight">{stage.name}</div>
        <div className="rounded-full bg-white/[0.04] px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-white/10 tabular-nums">
          {cards.length}
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {cards.length === 0 ? (
          <div className="rounded-2xl bg-white/[0.02] p-3 text-xs text-muted-foreground ring-1 ring-white/5">
            {t("hr.pipeline.no_candidates", { defaultValue: "No candidates yet." })}
          </div>
        ) : (
          cards.map((c) => (
            <KanbanCard
              key={c.id}
              card={c}
              stages={stages}
              onMove={onMove}
              onOpen={() => onOpenCandidate?.(c.id)}
            />
          ))
        )}
      </div>
    </GlassCard>
  );
}
