"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useTranslation } from "@/lib/i18n";

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
  const { t } = useTranslation();
  const router = useRouter();
  const branchId = useSelection((s) => s.branchId);
  const { create } = useOpenings(branchId ?? null);

  return (
    <HrPageShell>
      <HrHeader
        title={t("hr.openings_new_page.title", { defaultValue: "Create Opening" })}
        subtitle={t("hr.openings_new_page.subtitle", {
          defaultValue: "Draft an opening and start collecting resumes.",
        })}
        chips={
          branchId
            ? []
            : [
                t("hr.common.select_branch_first", {
                  defaultValue: "Select a branch first",
                }),
              ]
        }
      />

      {!branchId ? (
        <EmptyStateCard
          title={t("hr.openings_new_page.empty_title", {
            defaultValue: "Select a branch to continue",
          })}
          description={t("hr.openings_new_page.empty_description", {
            defaultValue:
              "HR Openings are branch-scoped. Pick a branch to create and manage openings.",
          })}
          icon={Sparkles}
          actions={<div className="w-full max-w-xl"><StorePicker /></div>}
        />
      ) : (
      <OpeningWizard
        saving={create.isPending}
        onSave={(draft) => {
          const payload: OpeningCreateRequest = {
            title:
              draft.title.trim() ||
              t("hr.openings_new_page.untitled_opening", {
                defaultValue: "Untitled opening",
              }),
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
              toast(t("hr.openings_new_page.toast_created", { defaultValue: "Opening created" }), {
                description: created.title,
              });
              router.push(`/hr/openings/${created.id}`);
            },
            onError: (err) => {
              toast(t("hr.openings_new_page.toast_failed", { defaultValue: "Failed to create opening" }), {
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
