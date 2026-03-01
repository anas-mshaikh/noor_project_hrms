"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { GradeCreate, GradeOut, UUID } from "@/lib/types";
import { createGrade, listGrades } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function GradesPage() {
  const companyId = useSelection((s) => s.companyId);

  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("tenancy:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const gradesQ = useQuery({
    queryKey: companyId ? tenancyKeys.grades(companyId) : ["tenancy", "grades", "missing-company"],
    enabled: Boolean(companyId),
    queryFn: () => listGrades({ companyId: companyId as UUID }),
  });

  const grades = (gradesQ.data ?? []) as GradeOut[];

  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [level, setLevel] = React.useState<string>("");

  const createM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Company selection is required.");
      const parsedLevel = level.trim() ? Number(level) : null;
      if (level.trim() && Number.isNaN(parsedLevel)) {
        throw new Error("Level must be a number.");
      }
      const payload: GradeCreate = {
        company_id: companyId,
        name: name.trim(),
        level: parsedLevel,
      };
      if (!payload.name) throw new Error("Grade name is required.");
      return createGrade(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setName("");
      setLevel("");
      if (companyId) {
        await qc.invalidateQueries({ queryKey: tenancyKeys.grades(companyId) });
      }
    },
    onError: (err) => toastApiError(err),
  });

  if (!companyId) {
    return (
      <EmptyState
        title="Select a company"
        description="Grades are company-scoped. Select a company from the scope picker to continue."
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Grades"
          subtitle="Catalog used for HR profiles and future compensation rules."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Create grade
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create grade</SheetTitle>
                  <SheetDescription>Add a grade under the selected company.</SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="grade-name" className="text-xs text-text-2">
                      Name
                    </Label>
                    <Input
                      id="grade-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="grade-level" className="text-xs text-text-2">
                      Level (optional)
                    </Label>
                    <Input
                      id="grade-level"
                      value={level}
                      onChange={(e) => setLevel(e.target.value)}
                      inputMode="numeric"
                      placeholder="e.g. 1"
                    />
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    type="button"
                    disabled={!canWrite || createM.isPending}
                    onClick={() => createM.mutate()}
                  >
                    {createM.isPending ? "Creating..." : "Create"}
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          }
        />
      }
      main={
        <DataTable
          isLoading={gradesQ.isLoading}
          error={gradesQ.error}
          onRetry={gradesQ.refetch}
          isEmpty={!gradesQ.isLoading && !gradesQ.error && grades.length === 0}
          emptyState={
            <EmptyState
              title="No grades yet"
              description="Create your first grade to start standardizing levels."
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setOpen(true)}>
                    Create grade
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 6, cols: 3 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grades.map((g) => (
                <TableRow key={g.id}>
                  <TableCell className="font-medium">{g.name}</TableCell>
                  <TableCell className="text-text-2">{g.level ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs text-text-3">{g.id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Notes
            </div>
            <div className="mt-2 text-sm text-text-2">
              Grades are currently a simple catalog. Future milestones can link them to salary structures and payroll.
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">grades</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{grades.length}</div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">company</div>
                <div className="mt-1 text-sm font-medium text-text-1">Selected</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

