"use client";

/**
 * components/hr/AIActionsPanel.tsx
 *
 * A compact "assistant" panel for the HR overview. Phase 1 is UI-only:
 * buttons simply show a "Coming soon" toast.
 */

import * as React from "react";
import type { LucideIcon } from "lucide-react";
import {
  Sparkles,
  FileText,
  Wand2,
  TrendingUp,
  Mail,
} from "lucide-react";
import { toast } from "sonner";

import { GlassCard } from "@/components/hr/GlassCard";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ActionTile = {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

const ACTIONS: ActionTile[] = [
  {
    id: "candidate-summary",
    label: "Candidate Summary",
    description: "Fast, structured fit notes.",
    icon: FileText,
  },
  {
    id: "interview-questions",
    label: "Interview Questions",
    description: "Role-specific questions.",
    icon: Wand2,
  },
  {
    id: "skill-gaps",
    label: "Find Skill Gaps",
    description: "Compare JD vs resume.",
    icon: TrendingUp,
  },
  {
    id: "offer-email",
    label: "Draft Offer Email",
    description: "Professional, ready to send.",
    icon: Mail,
  },
];

export function AIActionsPanel({ className }: { className?: string }) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">
            How can I help you?
          </div>
          <div className="mt-1 text-xs text-white/60">
            Quick actions to accelerate your hiring loop.
          </div>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/5 ring-1 ring-white/10">
          <Sparkles className="h-4 w-4 text-white/80" />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        {ACTIONS.map((a) => {
          const Icon = a.icon;
          return (
            <Button
              key={a.id}
              type="button"
              variant="ghost"
              onClick={() =>
                toast("Coming soon", {
                  description: a.label,
                })
              }
              className={cn(
                "h-auto flex-col items-start gap-2 rounded-2xl bg-white/[0.02] p-3 text-start ring-1 ring-white/5",
                "hover:bg-white/[0.05] hover:text-white",
                "focus-visible:ring-2 focus-visible:ring-violet-400/50"
              )}
              aria-label={a.label}
            >
              <div className="flex w-full items-center justify-between gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/5 ring-1 ring-white/10">
                  <Icon className="h-4 w-4 text-white/80" />
                </div>
              </div>
              <div className="w-full">
                <div className="text-sm font-medium">{a.label}</div>
                <div className="mt-0.5 text-xs text-white/60">
                  {a.description}
                </div>
              </div>
            </Button>
          );
        })}
      </div>
    </GlassCard>
  );
}
