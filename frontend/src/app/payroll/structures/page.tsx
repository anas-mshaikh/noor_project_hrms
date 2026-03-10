"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import type { SalaryStructureCreateIn } from "@/lib/types";
import { useSalaryStructureCreate } from "@/features/payroll/hooks";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export default function PayrollStructuresPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:structure:read");
  const canWrite = granted.has("payroll:structure:write");
  const router = useRouter();
  const qc = useQueryClient();

  const [createOpen, setCreateOpen] = React.useState(false);
  const [code, setCode] = React.useState("");
  const [name, setName] = React.useState("");
  const [isActive, setIsActive] = React.useState(true);
  const createM = useSalaryStructureCreate();

  const [openId, setOpenId] = React.useState("");

  if (!user) {
    return <ErrorState title="Sign in required" error={new Error("Please sign in to manage salary structures.")} />;
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to salary structures.")} />;
  }

  async function onCreate() {
    const payload: SalaryStructureCreateIn = {
      code: code.trim(),
      name: name.trim(),
      is_active: isActive,
    };
    if (!payload.code || !payload.name) {
      toast.error("Code and name are required.");
      return;
    }
    try {
      const created = await createM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: ["payroll"] });
      setCreateOpen(false);
      setCode("");
      setName("");
      setIsActive(true);
      router.push(`/payroll/structures/${created.id}`);
      toast.success("Salary structure created");
    } catch (err) {
      import("@/lib/toastApiError").then(({ toastApiError }) => toastApiError(err));
    }
  }

  function onOpenExisting() {
    const id = parseUuidParam(openId);
    if (!id) {
      toast.error("Enter a valid salary structure UUID.");
      return;
    }
    router.push(`/payroll/structures/${id}`);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Salary structures"
        subtitle="Create structures and open a structure detail by UUID. The backend does not expose a structure list endpoint in v1."
        actions={
          canWrite ? (
            <Sheet open={createOpen} onOpenChange={setCreateOpen}>
              <SheetTrigger asChild>
                <Button type="button">Create structure</Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create salary structure</SheetTitle>
                  <SheetDescription>After creation you will be taken to the detail page to add component lines.</SheetDescription>
                </SheetHeader>
                <div className="space-y-4 px-4">
                  <div className="space-y-1"><Label htmlFor="structure-code">Code</Label><Input id="structure-code" value={code} onChange={(e) => setCode(e.target.value)} /></div>
                  <div className="space-y-1"><Label htmlFor="structure-name">Name</Label><Input id="structure-name" value={name} onChange={(e) => setName(e.target.value)} /></div>
                  <label className="flex items-center gap-2 text-sm text-text-2"><input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Active</label>
                </div>
                <SheetFooter>
                  <Button type="button" disabled={createM.isPending} onClick={() => void onCreate()}>
                    {createM.isPending ? "Creating..." : "Create structure"}
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          ) : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
          <div>
            <div className="text-sm font-semibold tracking-tight text-text-1">Open structure by ID</div>
            <div className="mt-1 text-sm text-text-2">Use a known structure UUID to open its detail page and manage lines.</div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="structure-open-id">Structure UUID</Label>
            <Input id="structure-open-id" value={openId} onChange={(e) => setOpenId(e.target.value)} placeholder="xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" onClick={onOpenExisting}>Open structure</Button>
          </div>
        </DSCard>

        <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-20)]">
          <div>
            <div className="text-sm font-semibold tracking-tight text-text-1">Why this page is limited</div>
            <div className="mt-1 text-sm text-text-2">
              Payroll v1 supports structure create, detail, and line-add, but it does not expose a browse endpoint for all structures. This screen stays honest to that backend surface.
            </div>
          </div>
          <EmptyState title="Create or open a structure" description="Create a new structure or open an existing one if you already have its UUID." align="center" />
        </DSCard>
      </div>
    </div>
  );
}
