"use client";

import * as React from "react";

import { KanbanColumn } from "@/features/hr/components/pipeline/KanbanColumn";
import type { PipelineCardUi, PipelineStageUi } from "@/features/hr/components/pipeline/types";

type KanbanBoardProps = {
  stages: PipelineStageUi[];
  cards: PipelineCardUi[];
  onMove?: (cardId: string, stageId: string) => void;
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
            key={stage.id}
            stage={stage}
            cards={cards.filter((c) => c.stageId === stage.id)}
            stages={stages}
            onMove={onMove}
            onOpenCandidate={onOpenCandidate}
          />
        ))}
    </div>
  );
}
