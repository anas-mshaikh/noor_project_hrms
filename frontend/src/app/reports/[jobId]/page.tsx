"use client";

/**
 * /reports/[jobId]
 *
 * Reads “results” tables for the job:
 * - attendance (per employee for that store/day)
 * - events (entry/exit stream)
 * - metrics/hourly (footfall buckets)
 * - artifacts (CSV/JSON/PDF download links)
 *
 * Backend endpoints used:
 * - GET /api/v1/branches/{branch_id}/jobs/{job_id}/attendance
 * - GET /api/v1/branches/{branch_id}/jobs/{job_id}/events?limit=1000
 * - GET /api/v1/branches/{branch_id}/jobs/{job_id}/metrics/hourly
 * - GET /api/v1/branches/{branch_id}/jobs/{job_id}/artifacts
 * - GET /api/v1/branches/{branch_id}/artifacts/{artifact_id}/download
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n";

import { apiDownload, apiJson, saveBlobAsFile } from "@/lib/api";
import { toastApiError } from "@/lib/toastApiError";
import { useSelection } from "@/lib/selection";
import type {
  ArtifactOut,
  AttendanceOut,
  EventOut,
  MetricsHourlyOut,
} from "@/lib/types";

import { AttendanceTable } from "@/components/AttendanceTable";
import { EventsTable } from "@/components/EventsTable";
import { MetricsChart } from "@/components/MetricsChart";
import { DailyInsights } from "@/components/DailyInsights";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// function paramToString(v: string | string[] | undefined): string | undefined {
//   if (!v) return undefined;
//   return Array.isArray(v) ? v[0] : v;
// }

export default function ReportPage() {
  const { t } = useTranslation();
  const params = useParams<{ jobId: string }>();
  const jobId = Array.isArray(params?.jobId) ? params.jobId[0] : params?.jobId;
  const branchId = useSelection((s) => s.branchId);

  const attendanceQ = useQuery({
    queryKey: ["attendance", branchId, jobId],
    enabled: Boolean(jobId && branchId),
    queryFn: () => {
      if (!jobId) throw new Error("Missing jobId");
      if (!branchId) throw new Error("Missing branchId");
      return apiJson<AttendanceOut[]>(
        `/api/v1/branches/${branchId}/jobs/${jobId}/attendance`
      );
    },
  });

  const eventsQ = useQuery({
    queryKey: ["events", branchId, jobId],
    enabled: Boolean(jobId && branchId),
    queryFn: () =>
      apiJson<EventOut[]>(
        `/api/v1/branches/${branchId}/jobs/${jobId}/events?limit=1000`
      ),
  });

  const metricsQ = useQuery({
    queryKey: ["metrics-hourly", branchId, jobId],
    enabled: Boolean(jobId && branchId),
    queryFn: () =>
      apiJson<MetricsHourlyOut[]>(
        `/api/v1/branches/${branchId}/jobs/${jobId}/metrics/hourly`
      ),
  });

  const artifactsQ = useQuery({
    queryKey: ["artifacts", branchId, jobId],
    enabled: Boolean(jobId && branchId),
    queryFn: () =>
      apiJson<ArtifactOut[]>(`/api/v1/branches/${branchId}/jobs/${jobId}/artifacts`),
  });

  if (!jobId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Report</CardTitle>
          <CardDescription className="text-destructive">
            Missing jobId in route.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!branchId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Report</CardTitle>
          <CardDescription className="text-muted-foreground">
            Select a branch to view this report.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link href="/scope">Select branch</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("page.reports.title", { defaultValue: "Report" })}
          </h1>
          <div className="mt-1 text-sm text-muted-foreground">
            job_id: <code className="text-xs">{jobId}</code>
          </div>
        </div>

        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href={`/jobs/${jobId}`}>Back to job</Link>
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={() => {
              attendanceQ.refetch();
              eventsQ.refetch();
              metricsQ.refetch();
              artifactsQ.refetch();
            }}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Daily Insights */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Insights</CardTitle>
          <CardDescription>Quick health check for this job.</CardDescription>
        </CardHeader>
        <CardContent>
          {attendanceQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : attendanceQ.isError ? (
            <div className="text-sm text-destructive">
              {String(attendanceQ.error)}
            </div>
          ) : (
            <DailyInsights rows={attendanceQ.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Attendance */}
      <Card>
        <CardHeader>
          <CardTitle>Attendance</CardTitle>
          <CardDescription>
            One row per employee for this store/day.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {attendanceQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : attendanceQ.isError ? (
            <div className="text-sm text-destructive">
              {String(attendanceQ.error)}
            </div>
          ) : (
            <AttendanceTable rows={attendanceQ.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Events */}
      <Card>
        <CardHeader>
          <CardTitle>Events</CardTitle>
          <CardDescription>
            Door entry/exit stream (inferred events are highlighted).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {eventsQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : eventsQ.isError ? (
            <div className="text-sm text-destructive">
              {String(eventsQ.error)}
            </div>
          ) : (
            <EventsTable rows={eventsQ.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Hourly Metrics</CardTitle>
          <CardDescription>Footfall buckets for this job.</CardDescription>
        </CardHeader>
        <CardContent>
          {metricsQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : metricsQ.isError ? (
            <div className="text-sm text-destructive">
              {String(metricsQ.error)}
            </div>
          ) : (
            <MetricsChart rows={metricsQ.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Artifacts */}
      <Card>
        <CardHeader>
          <CardTitle>Artifacts</CardTitle>
          <CardDescription>CSV/JSON exports for this job.</CardDescription>
        </CardHeader>
        <CardContent>
          {artifactsQ.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : artifactsQ.isError ? (
            <div className="text-sm text-destructive">
              {String(artifactsQ.error)}
            </div>
          ) : (artifactsQ.data ?? []).length === 0 ? (
            <div className="text-sm text-muted-foreground">No artifacts yet.</div>
          ) : (
            <ul className="space-y-2 text-sm">
              {(artifactsQ.data ?? []).map((a) => (
                <li key={a.id} className="rounded-lg border bg-muted/30 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="font-medium">{a.type}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(a.created_at).toLocaleString()}
                      </div>
                    </div>

                    <Button
                      type="button"
                      onClick={() => {
                        if (!branchId) return;
                        void (async () => {
                          try {
                            const out = await apiDownload(
                              `/api/v1/branches/${branchId}/artifacts/${a.id}/download`
                            );
                            saveBlobAsFile(out.blob, out.filename);
                          } catch (e) {
                            toastApiError(e, t);
                          }
                        })();
                      }}
                    >
                      Download
                    </Button>
                  </div>

                  <div className="mt-2 text-xs text-muted-foreground">
                    path: <code>{a.path}</code>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
