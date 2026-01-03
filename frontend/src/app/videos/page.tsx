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
      <h1 className="text-2xl font-semibold">Videos</h1>
      <UploadWizard />
    </div>
  );
}
