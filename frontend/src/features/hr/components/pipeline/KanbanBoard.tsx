"use client";

import * as React from "react";

import type { HrPipelineCard, HrPipelineStage } from "@/features/hr/mock/types";
import { KanbanColumn } from "@/features/hr/components/pipeline/KanbanColumn";

type KanbanBoardProps = {
  stages: HrPipelineStage[];
  cards: HrPipelineCard[];
  onMove?: (cardId: string, stageKey: HrPipelineStage["key"]) => void;
  onOpenCandidate?: (cardId: string) => void;
};

export function KanbanBoard({
  stages,
  cards,
  onMove,
  onOpenCandidate,
}: KanbanBoardProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-6">
      {stages
        .slice()
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((stage) => (
          <KanbanColumn
            key={stage.key}
            stage={stage}
            cards={cards.filter((c) => c.stage === stage.key)}
            stages={stages}
            onMove={onMove}
            onOpenCandidate={onOpenCandidate}
          />
        ))}
    </div>
  );
}

