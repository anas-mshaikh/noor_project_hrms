"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { CompanyCreate, CompanyOut } from "@/lib/types";
import { createCompany, listCompanies } from "@/features/tenancy/api/tenancy";
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

export default function CompaniesPage() {
  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("tenancy:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const companiesQ = useQuery({
    queryKey: tenancyKeys.companies(),
    queryFn: () => listCompanies(),
  });

  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [legalName, setLegalName] = React.useState("");
  const [currencyCode, setCurrencyCode] = React.useState("");
  const [timezone, setTimezone] = React.useState("");

  const createM = useMutation({
    mutationFn: async () => {
      const payload: CompanyCreate = {
        name: name.trim(),
        legal_name: legalName.trim() ? legalName.trim() : null,
        currency_code: currencyCode.trim() ? currencyCode.trim() : null,
        timezone: timezone.trim() ? timezone.trim() : null,
      };
      if (!payload.name) {
        throw new Error("Company name is required.");
      }
      return createCompany(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setName("");
      setLegalName("");
      setCurrencyCode("");
      setTimezone("");
      await qc.invalidateQueries({ queryKey: tenancyKeys.companies() });
    },
    onError: (err) => toastApiError(err),
  });

  const companies = (companiesQ.data ?? []) as CompanyOut[];

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Companies"
          subtitle="Create and view companies for the active tenant."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Create company
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create company</SheetTitle>
                  <SheetDescription>
                    Companies are tenant-wide masters.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="company-name" className="text-xs text-text-2">
                      Name
                    </Label>
                    <Input
                      id="company-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="company-legal-name" className="text-xs text-text-2">
                      Legal name (optional)
                    </Label>
                    <Input
                      id="company-legal-name"
                      value={legalName}
                      onChange={(e) => setLegalName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="company-currency-code" className="text-xs text-text-2">
                      Currency code (optional)
                    </Label>
                    <Input
                      id="company-currency-code"
                      value={currencyCode}
                      onChange={(e) => setCurrencyCode(e.target.value)}
                      placeholder="e.g. SAR"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="company-timezone" className="text-xs text-text-2">
                      Timezone (optional)
                    </Label>
                    <Input
                      id="company-timezone"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      placeholder="e.g. Asia/Riyadh"
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
          isLoading={companiesQ.isLoading}
          error={companiesQ.error}
          onRetry={companiesQ.refetch}
          isEmpty={
            !companiesQ.isLoading && !companiesQ.error && companies.length === 0
          }
          emptyState={
            <EmptyState
              title="No companies yet"
              description="Create your first company to start setting up branches and org structure."
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setOpen(true)}>
                    Create company
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 6, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Legal name</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Timezone</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {companies.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell className="text-text-2">
                    {c.legal_name ?? "—"}
                  </TableCell>
                  <TableCell className="text-text-2">
                    {c.currency_code ?? "—"}
                  </TableCell>
                  <TableCell className="text-text-2">
                    {c.timezone ?? "—"}
                  </TableCell>
                  <TableCell className="text-text-2">{c.status}</TableCell>
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
              About companies
            </div>
            <div className="mt-2 text-sm text-text-2">
              Companies are tenant-wide masters used to group branches and HR
              structures. Most clients create one company per legal entity.
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">companies</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {companies.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">status</div>
                <div className="mt-1 text-sm font-medium text-text-1">
                  {companiesQ.isLoading
                    ? "Loading"
                    : companiesQ.error
                      ? "Error"
                      : "Ready"}
                </div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
