"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { HrPageShell } from "@/features/hr/components/layout/HrPageShell";
import { HrHeader } from "@/features/hr/components/layout/HrHeader";
import { OpeningWizard } from "@/features/hr/components/openings/OpeningWizard";

export default function HROpeningsNewPage() {
  const router = useRouter();

  return (
    <HrPageShell>
      <HrHeader
        title="Create Opening"
        subtitle="Draft an opening and start collecting resumes. (UI-only for now)"
        chips={["Wizard", "Mock save"]}
      />

      <OpeningWizard
        onSave={() => {
          // UI-only: route to a deterministic mock ID. The detail page will show a
          // placeholder view if it doesn't exist in mock data yet.
          const id = `op_new_${Date.now().toString(36)}`;
          toast("Opening saved (mock)", { description: `opening_id: ${id}` });
          router.push(`/hr/openings/${id}`);
        }}
      />
    </HrPageShell>
  );
}

