"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { OpeningWizard } from "@/features/hr/components/openings/OpeningWizard";
import { EmptyStateCard } from "@/features/hr/components/cards/EmptyStateCard";
import { StorePicker } from "@/components/StorePicker";
import { useSelection } from "@/lib/selection";
import { useOpenings } from "@/features/hr/hooks/useOpenings";
import type { OpeningCreateRequest } from "@/lib/types";
import { Sparkles } from "lucide-react";

export default function HROpeningsNewPage() {
  const router = useRouter();
  const storeId = useSelection((s) => s.storeId);
  const { create } = useOpenings(storeId ?? null);

  return (
    <HrPageShell>
      <HrHeader
        title="Create Opening"
        subtitle="Draft an opening and start collecting resumes."
        chips={storeId ? [] : ["Select a store first"]}
      />

      {!storeId ? (
        <EmptyStateCard
          title="Select a store to continue"
          description="HR Openings are store-scoped. Pick a store to create and manage openings."
          icon={Sparkles}
          actions={<div className="w-full max-w-xl"><StorePicker /></div>}
        />
      ) : (
      <OpeningWizard
        saving={create.isPending}
        onSave={(draft) => {
          const payload: OpeningCreateRequest = {
            title: draft.title.trim() || "Untitled opening",
            jd_text: draft.jdText ?? "",
            // Backend currently treats requirements_json as arbitrary JSON.
            requirements_json: {
              department: draft.department || null,
              location: draft.location || null,
              requirements: draft.requirements,
            },
          };

          create.mutate(payload, {
            onSuccess: (created) => {
              toast("Opening created", { description: created.title });
              router.push(`/hr/openings/${created.id}`);
            },
            onError: (err) => {
              toast("Failed to create opening", {
                description: err instanceof Error ? err.message : "Unknown error",
              });
            },
          });
        }}
      />
      )}
    </HrPageShell>
  );
}
