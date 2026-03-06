"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { isUuid, parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID, WorkflowDefinitionOut, WorkflowDefinitionStepIn } from "@/lib/types";
import { activateDefinition, listDefinitions, replaceDefinitionSteps } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";
import { DSCard } from "@/components/ds/DSCard";
import { ErrorState } from "@/components/ds/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusChip } from "@/components/ds/StatusChip";
import { EmptyState } from "@/components/ds/EmptyState";
import { cn } from "@/lib/utils";

export default function WorkflowDefinitionDetailPage({ params }: { params: { definitionId?: string } }) {
  const routeParams = useParams() as { definitionId?: string | string[] };
  const raw =
    (Array.isArray(routeParams.definitionId) ? routeParams.definitionId[0] : routeParams.definitionId) ??
    params?.definitionId ??
    null;
  const definitionId = parseUuidParam(raw) as UUID | null;

  const qc = useQueryClient();
  const companyId = useSelection((s) => s.companyId) as UUID | undefined;

  const defsQ = useQuery({
    queryKey: workflowKeys.definitions(companyId ?? null),
    queryFn: () => listDefinitions({ companyId: companyId ?? null }),
    enabled: Boolean(definitionId),
  });

  const definition = React.useMemo(() => {
    return (defsQ.data ?? []).find((d) => d.id === definitionId) ?? null;
  }, [defsQ.data, definitionId]);

  const [steps, setSteps] = React.useState<WorkflowDefinitionStepIn[]>([]);
  const [actionError, setActionError] = React.useState<unknown>(null);

  React.useEffect(() => {
    if (!definition) return;
    setSteps(
      (definition.steps ?? []).map((s) => ({
        step_index: s.step_index,
        assignee_type: s.assignee_type as WorkflowDefinitionStepIn["assignee_type"],
        assignee_role_code: s.assignee_role_code ?? null,
        assignee_user_id: s.assignee_user_id ?? null,
        scope_mode: (s.scope_mode ?? "TENANT") as WorkflowDefinitionStepIn["scope_mode"],
        fallback_role_code: s.fallback_role_code ?? null,
      }))
    );
  }, [definition]);

  function normalize(next: WorkflowDefinitionStepIn[]): WorkflowDefinitionStepIn[] {
    return next.map((s, idx) => ({ ...s, step_index: idx }));
  }

  function validate(): string | null {
    if (!steps.length) return "At least one step is required.";
    for (const [idx, s] of steps.entries()) {
      if (s.step_index !== idx) return "Steps must be sequential starting at 0.";
      if (s.assignee_type === "ROLE" && !s.assignee_role_code) {
        return `Step ${idx + 1}: ROLE requires role code.`;
      }
      if (s.assignee_type === "USER") {
        if (!s.assignee_user_id) return `Step ${idx + 1}: USER requires user id.`;
        if (!isUuid(String(s.assignee_user_id))) return `Step ${idx + 1}: invalid user id.`;
      }
    }
    return null;
  }

  const saveM = useMutation({
    mutationFn: async () => {
      const msg = validate();
      if (msg) throw new Error(msg);
      return replaceDefinitionSteps(definitionId as UUID, { steps });
    },
    onSuccess: async () => {
      setActionError(null);
      await qc.invalidateQueries({ queryKey: ["workflow", "definitions"] });
    },
    onError: (err) => {
      setActionError(err);
      toastApiError(err);
    },
  });

  const activateM = useMutation({
    mutationFn: async () => activateDefinition(definitionId as UUID),
    onSuccess: async () => {
      setActionError(null);
      await qc.invalidateQueries({ queryKey: ["workflow", "definitions"] });
    },
    onError: (err) => {
      setActionError(err);
      toastApiError(err);
    },
  });

  if (!raw) {
    return (
      <ErrorState
        title="Missing definition id"
        error={new Error("Open a definition from the list.")}
        details={
          <Button asChild variant="outline">
            <Link href="/settings/workflow/definitions">Back</Link>
          </Button>
        }
      />
    );
  }

  if (!definitionId) {
    return (
      <ErrorState
        title="Invalid definition id"
        error={new Error(`Got: ${String(raw)}`)}
        details={
          <Button asChild variant="outline">
            <Link href="/settings/workflow/definitions">Back</Link>
          </Button>
        }
      />
    );
  }

  if (defsQ.isLoading) {
    return (
      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="text-sm text-text-2">Loading definition…</div>
      </DSCard>
    );
  }

  if (defsQ.isError) {
    return (
      <ErrorState
        title="Failed to load definitions"
        error={defsQ.error}
        onRetry={() => void defsQ.refetch()}
      />
    );
  }

  if (!definition) {
    return (
      <ErrorState
        title="Not found"
        error={new Error("Definition not found in the current scope.")}
        details={
          <Button asChild variant="outline">
            <Link href="/settings/workflow/definitions">Back</Link>
          </Button>
        }
      />
    );
  }

  const selectClassName = cn(
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  return (
    <div className="space-y-4">
      {actionError ? (
        <ErrorState title="Action failed" error={actionError} variant="inline" className="max-w-none" />
      ) : null}

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="text-lg font-semibold tracking-tight text-text-1">{definition.name}</div>
            <div className="text-sm text-text-2">
              {definition.request_type_code} • v{definition.version ?? "—"}
            </div>
            <div className="text-xs text-text-3 font-mono">{definition.id}</div>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <StatusChip status={definition.is_active ? "ACTIVE" : "INACTIVE"} />
            <Button
              type="button"
              variant="secondary"
              disabled={activateM.isPending || definition.is_active}
              onClick={() => activateM.mutate()}
            >
              {definition.is_active ? "Active" : activateM.isPending ? "Activating..." : "Activate"}
            </Button>
          </div>
        </div>
      </DSCard>

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold tracking-tight text-text-1">Steps</div>
            <div className="mt-1 text-sm text-text-2">
              Steps must be sequential starting at 0. Save replaces all steps.
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                setSteps((prev) =>
                  normalize([
                    ...prev,
                    {
                      step_index: prev.length,
                      assignee_type: "MANAGER",
                      assignee_role_code: null,
                      assignee_user_id: null,
                      scope_mode: "TENANT",
                      fallback_role_code: null,
                    },
                  ])
                )
              }
            >
              Add step
            </Button>
            <Button type="button" disabled={saveM.isPending} onClick={() => saveM.mutate()}>
              {saveM.isPending ? "Saving..." : "Save steps"}
            </Button>
          </div>
        </div>

        {steps.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title="No steps"
              description="Add at least one step before activating."
              align="center"
            />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {steps.map((s, idx) => (
              <div
                key={idx}
                className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-medium text-text-1">Step {idx}</div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={idx === 0}
                      onClick={() =>
                        setSteps((prev) => {
                          const next = [...prev];
                          const t = next[idx - 1];
                          next[idx - 1] = next[idx];
                          next[idx] = t;
                          return normalize(next);
                        })
                      }
                    >
                      Up
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={idx === steps.length - 1}
                      onClick={() =>
                        setSteps((prev) => {
                          const next = [...prev];
                          const t = next[idx + 1];
                          next[idx + 1] = next[idx];
                          next[idx] = t;
                          return normalize(next);
                        })
                      }
                    >
                      Down
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="border-danger/30 text-danger hover:bg-danger/10"
                      onClick={() =>
                        setSteps((prev) => normalize(prev.filter((_, i) => i !== idx)))
                      }
                    >
                      Remove
                    </Button>
                  </div>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor={`wf-step-${idx}-assignee-type`} className="text-xs text-text-2">
                      Assignee type
                    </Label>
                    <select
                      id={`wf-step-${idx}-assignee-type`}
                      className={selectClassName}
                      value={s.assignee_type}
                      onChange={(e) =>
                        setSteps((prev) =>
                          normalize(
                            prev.map((p, i) =>
                              i === idx
                                ? {
                                    ...p,
                                    assignee_type: e.target.value as WorkflowDefinitionStepIn["assignee_type"],
                                    assignee_role_code: null,
                                    assignee_user_id: null,
                                  }
                                : p
                            )
                          )
                        )
                      }
                    >
                      <option value="MANAGER">MANAGER</option>
                      <option value="ROLE">ROLE</option>
                      <option value="USER">USER</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor={`wf-step-${idx}-scope-mode`} className="text-xs text-text-2">
                      Scope mode
                    </Label>
                    <select
                      id={`wf-step-${idx}-scope-mode`}
                      className={selectClassName}
                      value={s.scope_mode ?? "TENANT"}
                      onChange={(e) =>
                        setSteps((prev) =>
                          normalize(
                            prev.map((p, i) =>
                              i === idx
                                ? { ...p, scope_mode: e.target.value as WorkflowDefinitionStepIn["scope_mode"] }
                                : p
                            )
                          )
                        )
                      }
                    >
                      <option value="TENANT">TENANT</option>
                      <option value="COMPANY">COMPANY</option>
                      <option value="BRANCH">BRANCH</option>
                    </select>
                  </div>

                  {s.assignee_type === "ROLE" ? (
                    <div className="space-y-1 md:col-span-2">
                      <Label htmlFor={`wf-step-${idx}-role-code`} className="text-xs text-text-2">
                        Role code
                      </Label>
                      <Input
                        id={`wf-step-${idx}-role-code`}
                        value={s.assignee_role_code ?? ""}
                        onChange={(e) =>
                          setSteps((prev) =>
                            normalize(
                              prev.map((p, i) => (i === idx ? { ...p, assignee_role_code: e.target.value } : p))
                            )
                          )
                        }
                        placeholder="HR_ADMIN"
                      />
                    </div>
                  ) : null}

                  {s.assignee_type === "USER" ? (
                    <div className="space-y-1 md:col-span-2">
                      <Label htmlFor={`wf-step-${idx}-user-id`} className="text-xs text-text-2">
                        User id
                      </Label>
                      <Input
                        id={`wf-step-${idx}-user-id`}
                        value={s.assignee_user_id ?? ""}
                        onChange={(e) =>
                          setSteps((prev) =>
                            normalize(
                              prev.map((p, i) => (i === idx ? { ...p, assignee_user_id: e.target.value } : p))
                            )
                          )
                        }
                        placeholder="uuid"
                      />
                    </div>
                  ) : null}

                  <div className="space-y-1 md:col-span-2">
                    <Label htmlFor={`wf-step-${idx}-fallback-role`} className="text-xs text-text-2">
                      Fallback role (optional)
                    </Label>
                    <Input
                      id={`wf-step-${idx}-fallback-role`}
                      value={s.fallback_role_code ?? ""}
                      onChange={(e) =>
                        setSteps((prev) =>
                          normalize(
                            prev.map((p, i) => (i === idx ? { ...p, fallback_role_code: e.target.value } : p))
                          )
                        )
                      }
                      placeholder="EMPLOYEE"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </DSCard>

      <div>
        <Button asChild variant="outline">
          <Link href="/settings/workflow/definitions">Back</Link>
        </Button>
      </div>
    </div>
  );
}
