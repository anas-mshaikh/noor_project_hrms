"use client";

/**
 * /videos
 *
 * Thin page wrapper around <UploadWizard />.
 * Keeping the wizard in components/ makes it easier to reuse later
 * (e.g., you may want “Upload history” + “Re-run job” on this page).
 */

import { UploadWizard } from "@/components/UploadWizard";

export default function VideosPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Videos</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload a clip for a specific business date and run the worker job.
        </p>
      </div>
      <UploadWizard />
    </div>
  );
}
