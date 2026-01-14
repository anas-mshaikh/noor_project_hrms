"use client";

/**
 * components/UploadWizard.tsx
 *
 * This is the MVP “video upload → job creation” wizard.
 *
 * Backend flow (exact order):
 *  1) POST /api/v1/stores/{store_id}/videos/init
 *     - creates the Video row in DB
 *     - returns upload_endpoint + finalize_endpoint
 *
 *  2) PUT  {upload_endpoint}
 *     - multipart/form-data upload using field name "file"
 *     - we use XHR so we can show upload progress %
 *
 *  3) POST {finalize_endpoint}
 *     - computes sha256 and (best-effort) metadata via ffprobe
 *     - REQUIRED before job creation (backend enforces sha256 exists)
 *
 *  4) POST /api/v1/videos/{video_id}/jobs
 *     - enqueues the worker job
 *
 * Notes:
 * - This wizard reads storeId + cameraId from Zustand (top-right picker).
 * - recorded_start_ts is optional, but if your worker uses it to create “real”
 *   timestamps, you SHOULD set it for accurate punch-in/out times.
 */

import Link from "next/link";
import { useMemo, useState } from "react";

import { apiJson, xhrUploadFormWithProgress } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { JobCreateResponse, VideoInitResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * Browser-safe helper: get today's date in LOCAL time for <input type="date" />
 * (Do NOT use toISOString().slice(0,10) because that uses UTC and can shift dates.)
 */
function todayLocalYYYYMMDD(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * The backend response from PUT /videos/{video_id}/file.
 * We keep it local here to avoid editing lib/types.ts right now.
 */
type UploadVideoResponse = {
  status: string; // "uploaded"
  file_path: string;
  bytes: number;
};

/**
 * The backend response from POST /videos/{video_id}/finalize.
 * Again, local type for quick iteration.
 */
type FinalizeVideoResponse = {
  video_id: string;
  sha256: string;
  file_path: string;
  fps: number | null;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
};

type Step = "idle" | "init" | "upload" | "finalize" | "create_job" | "done";

export function UploadWizard() {
  // Selected IDs come from StorePicker (Zustand persisted).
  const storeId = useSelection((s) => s.storeId);
  const cameraId = useSelection((s) => s.cameraId);

  // Form inputs.
  const [businessDate, setBusinessDate] = useState(() => todayLocalYYYYMMDD());
  const [uploadedBy, setUploadedBy] = useState("");
  const [recordedStartLocal, setRecordedStartLocal] = useState(""); // <input type="datetime-local" />
  const [file, setFile] = useState<File | null>(null);

  // Wizard state.
  const [step, setStep] = useState<Step>("idle");
  const [uploadPct, setUploadPct] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Debug/visibility (helps a lot while wiring the backend).
  const [initRes, setInitRes] = useState<VideoInitResponse | null>(null);
  const [uploadRes, setUploadRes] = useState<UploadVideoResponse | null>(null);
  const [finalizeRes, setFinalizeRes] = useState<FinalizeVideoResponse | null>(
    null
  );
  const [jobRes, setJobRes] = useState<JobCreateResponse | null>(null);

  const canStart = useMemo(() => {
    // We can only upload if a store + camera + file are selected.
    return Boolean(storeId && cameraId && file && businessDate);
  }, [storeId, cameraId, file, businessDate]);

  function reset() {
    // Reset only the wizard state (do NOT clear store/camera selection).
    setStep("idle");
    setUploadPct(0);
    setError(null);
    setInitRes(null);
    setUploadRes(null);
    setFinalizeRes(null);
    setJobRes(null);
  }

  async function run() {
    try {
      setError(null);
      setUploadPct(0);
      setStep("idle");
      setInitRes(null);
      setUploadRes(null);
      setFinalizeRes(null);
      setJobRes(null);

      if (!storeId) throw new Error("Select a store in the header first.");
      if (!cameraId) throw new Error("Select a camera in the header first.");
      if (!file) throw new Error("Select a video file first.");
      if (!businessDate) throw new Error("Business date is required.");

      // recorded_start_ts is optional.
      // If your worker uses it to map frame timestamps to real timestamps,
      // send it (as ISO string) for accurate punch-in/out times.
      const recorded_start_ts =
        recordedStartLocal.trim().length === 0
          ? null
          : new Date(recordedStartLocal).toISOString();

      // -----------------------------
      // 1) INIT (creates Video row)
      // -----------------------------
      setStep("init");
      const init = await apiJson<VideoInitResponse>(
        `/api/v1/stores/${storeId}/videos/init`,
        {
          method: "POST",
          body: JSON.stringify({
            camera_id: cameraId,
            business_date: businessDate,
            filename: file.name, // backend uses this mainly for extension
            uploaded_by: uploadedBy.trim() ? uploadedBy.trim() : null,
            recorded_start_ts,
          }),
        }
      );
      setInitRes(init);

      // -----------------------------
      // 2) UPLOAD FILE (with progress)
      // -----------------------------
      setStep("upload");

      // IMPORTANT: backend expects the UploadFile param named "file"
      const form = new FormData();
      form.append("file", file, file.name);

      const uploaded = await xhrUploadFormWithProgress<UploadVideoResponse>(
        init.upload_endpoint,
        form,
        (pct) => setUploadPct(pct)
      );
      setUploadRes(uploaded);

      // -----------------------------
      // 3) FINALIZE (compute sha256)
      // -----------------------------
      setStep("finalize");
      const finalized = await apiJson<FinalizeVideoResponse>(
        init.finalize_endpoint,
        { method: "POST" }
      );
      setFinalizeRes(finalized);

      // -----------------------------
      // 4) CREATE JOB (enqueue worker)
      // -----------------------------
      setStep("create_job");

      // FastAPI expects a JSON body (JobCreateRequest).
      // config_overrides is optional but the body itself is required, so we send {}.
      const job = await apiJson<JobCreateResponse>(
        `/api/v1/videos/${init.video_id}/jobs`,
        {
          method: "POST",
          body: JSON.stringify({ config_overrides: {} }),
        }
      );
      setJobRes(job);

      setStep("done");
    } catch (e) {
      setError(String(e));
      setStep("idle");
    }
  }

  // Guard: if store/camera not selected, show a clear message.
  if (!storeId || !cameraId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Upload Video</CardTitle>
          <CardDescription>
            Select an organization + store + camera in the header first.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Upload Video</CardTitle>
          <CardDescription>
            Upload a full-day (or short test) clip, finalize it, then start a
            processing job.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Business date</Label>
              <Input
                type="date"
                value={businessDate}
                onChange={(e) => setBusinessDate(e.target.value)}
              />
              <div className="text-xs text-muted-foreground">
                This is the “attendance date” you’ll query later.
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">
                Recorded start time (optional, recommended)
              </Label>
              <Input
                type="datetime-local"
                value={recordedStartLocal}
                onChange={(e) => setRecordedStartLocal(e.target.value)}
              />
              <div className="text-xs text-muted-foreground">
                Used to map video frames → real timestamps (if your worker relies
                on it).
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">
                Uploaded by (optional)
              </Label>
              <Input
                value={uploadedBy}
                onChange={(e) => setUploadedBy(e.target.value)}
                placeholder="e.g. Store Manager"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Video file</Label>
              <Input
                type="file"
                accept="video/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <div className="text-xs text-muted-foreground">
                You can use your client’s 5-min clip for quick testing.
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" disabled={!canStart || step !== "idle"} onClick={run}>
              {step === "idle" ? "Start upload + job" : "Working…"}
            </Button>

            <Button type="button" variant="outline" disabled={step !== "idle"} onClick={reset}>
              Reset
            </Button>

            {error && <div className="text-sm text-destructive">{error}</div>}
          </div>

          {/* Progress / step indicator */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium">Step:</span>
              <Badge variant="secondary">{step}</Badge>
            </div>

            {step === "upload" && (
              <div className="space-y-1">
                <div className="text-sm">
                  <span className="font-medium">Upload progress:</span>{" "}
                  <span className="tabular-nums">{uploadPct}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded bg-muted">
                  <div
                    className="h-2 bg-primary"
                    style={{ width: `${Math.min(100, Math.max(0, uploadPct))}%` }}
                  />
                </div>
              </div>
            )}

            {/* After job creation, show next link(s) */}
            {jobRes && (
              <div className="rounded-lg border bg-muted/30 p-3">
                <div className="font-medium">Job created</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  job_id: <code className="text-xs">{jobRes.job_id}</code> • status:{" "}
                  <code className="text-xs">{jobRes.status}</code>
                </div>

                {!jobRes.enqueued && (
                  <div className="mt-2 text-sm text-destructive">
                    Not enqueued: {jobRes.queue_error ?? "(unknown queue error)"}
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button asChild>
                    <Link href={`/jobs/${jobRes.job_id}`}>Open job status</Link>
                  </Button>

                  <Button asChild variant="outline">
                    <Link href={`/reports/${jobRes.job_id}`}>Open report</Link>
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Debug panel: very helpful while wiring backend/frontend quickly */}
      <Card>
        <CardHeader>
          <CardTitle>Debug</CardTitle>
          <CardDescription>Raw backend responses from this wizard.</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
            {JSON.stringify({ initRes, uploadRes, finalizeRes, jobRes }, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
