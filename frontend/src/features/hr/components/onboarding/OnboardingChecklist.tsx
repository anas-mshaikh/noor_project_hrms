"use client";

import * as React from "react";
import { CheckCircle2, Circle, OctagonAlert } from "lucide-react";

import type { HrOnboardingTask } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";

type OnboardingChecklistProps = {
  tasks: HrOnboardingTask[];
  className?: string;
};

function iconFor(status: HrOnboardingTask["status"]) {
  if (status === "DONE") return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
  if (status === "BLOCKED") return <OctagonAlert className="h-4 w-4 text-fuchsia-300" />;
  return <Circle className="h-4 w-4 text-muted-foreground" />;
}

export function OnboardingChecklist({ tasks, className }: OnboardingChecklistProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {tasks.map((t) => (
        <div
          key={t.id}
          className="flex items-start gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
        >
          <div className="mt-0.5">{iconFor(t.status)}</div>
          <div className="min-w-0">
            <div className="text-sm font-medium">{t.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {t.status === "DONE"
                ? "Completed"
                : t.status === "BLOCKED"
                ? "Blocked"
                : "Pending"}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

