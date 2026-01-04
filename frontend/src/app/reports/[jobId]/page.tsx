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
 * - GET /api/v1/jobs/{job_id}/attendance
 * - GET /api/v1/jobs/{job_id}/events?limit=1000
 * - GET /api/v1/jobs/{job_id}/metrics/hourly
 * - GET /api/v1/jobs/{job_id}/artifacts
 * - GET /api/v1/artifacts/{artifact_id}/download
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiJson, apiUrl } from "@/lib/api";
import type {
  ArtifactOut,
  AttendanceOut,
  EventOut,
  MetricsHourlyOut,
} from "@/lib/types";

import { AttendanceTable } from "@/components/AttendanceTable";
import { EventsTable } from "@/components/EventsTable";
import { MetricsChart } from "@/components/MetricsChart";

// function paramToString(v: string | string[] | undefined): string | undefined {
//   if (!v) return undefined;
//   return Array.isArray(v) ? v[0] : v;
// }

export default function ReportPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = Array.isArray(params?.jobId) ? params.jobId[0] : params?.jobId;

  const attendanceQ = useQuery({
    queryKey: ["attendance", jobId],
    enabled: Boolean(jobId),
    queryFn: () => {
      if (!jobId) throw new Error("Missing jobId");
      return apiJson<AttendanceOut[]>(`/api/v1/jobs/${jobId}/attendance`);
    },
  });

  const eventsQ = useQuery({
    queryKey: ["events", jobId],
    queryFn: () =>
      apiJson<EventOut[]>(`/api/v1/jobs/${jobId}/events?limit=1000`),
  });

  const metricsQ = useQuery({
    queryKey: ["metrics-hourly", jobId],
    queryFn: () =>
      apiJson<MetricsHourlyOut[]>(`/api/v1/jobs/${jobId}/metrics/hourly`),
  });

  const artifactsQ = useQuery({
    queryKey: ["artifacts", jobId],
    queryFn: () => apiJson<ArtifactOut[]>(`/api/v1/jobs/${jobId}/artifacts`),
  });

  if (!jobId) {
    return (
      <div className="rounded border bg-white p-4">
        <h1 className="text-xl font-semibold">Report</h1>
        <div className="mt-2 text-sm text-red-600">Missing jobId in route.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Report</h1>

        <div className="flex gap-2">
          <Link
            className="rounded border px-3 py-2 hover:bg-gray-50"
            href={`/jobs/${jobId}`}
          >
            Back to job
          </Link>

          <button
            className="rounded border px-3 py-2 hover:bg-gray-50"
            onClick={() => {
              attendanceQ.refetch();
              eventsQ.refetch();
              metricsQ.refetch();
              artifactsQ.refetch();
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="text-sm text-gray-600">
        job_id: <code className="text-xs">{jobId}</code>
      </div>

      {/* Attendance */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Attendance</h2>

        {attendanceQ.isLoading ? (
          <div className="mt-2 text-sm text-gray-600">Loading…</div>
        ) : attendanceQ.isError ? (
          <div className="mt-2 text-sm text-red-600">
            {String(attendanceQ.error)}
          </div>
        ) : (
          <div className="mt-3">
            <AttendanceTable rows={attendanceQ.data ?? []} />
          </div>
        )}
      </section>

      {/* Events */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Events</h2>

        {eventsQ.isLoading ? (
          <div className="mt-2 text-sm text-gray-600">Loading…</div>
        ) : eventsQ.isError ? (
          <div className="mt-2 text-sm text-red-600">
            {String(eventsQ.error)}
          </div>
        ) : (
          <div className="mt-3">
            <EventsTable rows={eventsQ.data ?? []} />
          </div>
        )}
      </section>

      {/* Metrics */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Hourly Metrics</h2>

        {metricsQ.isLoading ? (
          <div className="mt-2 text-sm text-gray-600">Loading…</div>
        ) : metricsQ.isError ? (
          <div className="mt-2 text-sm text-red-600">
            {String(metricsQ.error)}
          </div>
        ) : (
          <div className="mt-3">
            <MetricsChart rows={metricsQ.data ?? []} />
          </div>
        )}
      </section>

      {/* Artifacts */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Artifacts</h2>

        {artifactsQ.isLoading ? (
          <div className="mt-2 text-sm text-gray-600">Loading…</div>
        ) : artifactsQ.isError ? (
          <div className="mt-2 text-sm text-red-600">
            {String(artifactsQ.error)}
          </div>
        ) : (artifactsQ.data ?? []).length === 0 ? (
          <div className="mt-2 text-sm text-gray-600">No artifacts yet.</div>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {(artifactsQ.data ?? []).map((a) => (
              <li key={a.id} className="rounded border bg-gray-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">{a.type}</span>{" "}
                    <span className="text-xs text-gray-500">
                      {new Date(a.created_at).toLocaleString()}
                    </span>
                  </div>

                  {/* This link goes directly to the FastAPI backend. */}
                  <a
                    className="rounded bg-black px-3 py-2 text-white"
                    href={apiUrl(`/api/v1/artifacts/${a.id}/download`)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                </div>

                <div className="mt-2 text-xs text-gray-600">
                  path: <code>{a.path}</code>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
