"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { FileText, ShieldCheck, Sparkles, UserRound } from "lucide-react";

import type { HrCandidate } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";
import { ScorePill } from "@/features/hr/components/candidates/ScorePill";
import { TagChip } from "@/features/hr/components/candidates/TagChip";

export type CandidateDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  candidate: HrCandidate | null;
};

export function CandidateDrawer({
  open,
  onOpenChange,
  candidate,
}: CandidateDrawerProps) {
  const reducedMotion = useReducedMotion();

  const header = candidate ? (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <SheetTitle className="truncate">{candidate.name}</SheetTitle>
          <SheetDescription className="truncate">
            {candidate.current_title}
          </SheetDescription>
        </div>
        <ScorePill score={candidate.score} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {candidate.tags.map((t) => (
          <TagChip key={t}>{t}</TagChip>
        ))}
      </div>
    </>
  ) : (
    <>
      <SheetTitle>Candidate</SheetTitle>
      <SheetDescription>Select a candidate to preview details.</SheetDescription>
    </>
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="border-white/10 bg-white/[0.04] backdrop-blur-xl">
        <SheetHeader className="p-6">{header}</SheetHeader>

        {candidate ? (
          <motion.div
            initial={reducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.24 }}
            className="space-y-5 px-6 pb-6"
          >
            <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Sparkles className="h-4 w-4" />
                Summary
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {candidate.one_line_summary}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <ShieldCheck className="h-4 w-4" />
                  Matched
                </div>
                <ul className="mt-3 space-y-2 text-sm">
                  {candidate.matched_requirements.map((r) => (
                    <li key={r} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-300/80" />
                      <span className="text-foreground/90">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  Missing
                </div>
                <ul className="mt-3 space-y-2 text-sm">
                  {candidate.missing_requirements.map((r) => (
                    <li key={r} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-fuchsia-300/70" />
                      <span className="text-foreground/90">{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div>
              <div className="text-sm font-semibold tracking-tight">Evidence</div>
              <div className="mt-3 space-y-3">
                {candidate.evidence.map((e, idx) => (
                  <div
                    key={idx}
                    className="rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5"
                  >
                    <div className="text-xs font-medium text-muted-foreground">
                      {e.claim}
                    </div>
                    <div className="mt-2 text-sm text-foreground/90">
                      <span className="text-muted-foreground">“</span>
                      {e.quote}
                      <span className="text-muted-foreground">”</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Separator className="bg-white/10" />

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                className={cn(
                  "rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
                )}
                onClick={() => toast("Coming soon", { description: "Shortlist" })}
              >
                <UserRound className="h-4 w-4" />
                Shortlist
              </Button>
              <Button
                type="button"
                variant="outline"
                className="rounded-2xl border-white/10 bg-white/[0.02] hover:bg-white/[0.06]"
                onClick={() =>
                  toast("Coming soon", { description: "Add to Pipeline" })
                }
              >
                Add to Pipeline
              </Button>
              <Button
                type="button"
                variant="outline"
                className="rounded-2xl border-rose-500/30 bg-rose-500/10 text-rose-100 hover:bg-rose-500/15 hover:text-rose-50"
                onClick={() => toast("Coming soon", { description: "Reject" })}
              >
                Reject
              </Button>
            </div>
          </motion.div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
