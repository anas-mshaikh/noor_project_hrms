"use client";

/**
 * /videos
 *
 * Thin page wrapper around <UploadWizard />.
 * Keeping the wizard in components/ makes it easier to reuse later
 * (e.g., you may want “Upload history” + “Re-run job” on this page).
 */

import { UploadWizard } from "@/components/UploadWizard";
import { useTranslation } from "@/lib/i18n";

export default function VideosPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("nav.items.videos.title", { defaultValue: "Videos" })}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("page.videos.subtitle", {
            defaultValue: "Upload a clip for a specific business date and run the worker job.",
          })}
        </p>
      </div>
      <UploadWizard />
    </div>
  );
}
