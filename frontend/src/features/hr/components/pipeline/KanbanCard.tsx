"use client";

import * as React from "react";
import { MoreHorizontal } from "lucide-react";

import type { HrPipelineCard, HrPipelineStage } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";

type KanbanCardProps = {
  card: HrPipelineCard;
  stages: HrPipelineStage[];
  onMove?: (cardId: string, stageKey: HrPipelineStage["key"]) => void;
  onOpen?: () => void;
};

export function KanbanCard({ card, stages, onMove, onOpen }: KanbanCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5",
        "hover:bg-white/[0.04]"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="min-w-0 text-left outline-none focus-visible:ring-2 focus-visible:ring-violet-300/60 rounded-lg"
          aria-label={`Open candidate ${card.name}`}
        >
          <div className="truncate text-sm font-medium">{card.name}</div>
          <div className="mt-1 flex flex-wrap gap-2">
            {card.tags.slice(0, 2).map((t) => (
              <TagChip key={t} className="bg-white/[0.03]">
                {t}
              </TagChip>
            ))}
          </div>
        </button>

        <div className="flex items-center gap-2">
          <ScorePill score={card.score} />
          {onMove ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 rounded-xl text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
                  aria-label="Move candidate"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                {stages
                  .slice()
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((s) => (
                    <DropdownMenuItem
                      key={s.key}
                      onClick={() => onMove(card.id, s.key)}
                    >
                      Move to {s.name}
                    </DropdownMenuItem>
                  ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled>Coming soon: Notes</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </div>
    </div>
  );
}

