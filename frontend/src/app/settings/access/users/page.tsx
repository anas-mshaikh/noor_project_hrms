"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { isUuid } from "@/lib/guards";
import { cn } from "@/lib/utils";
import { toastApiError } from "@/lib/toastApiError";
import type { IamUserCreateIn, IamUserOut, UsersListMeta } from "@/lib/types";
import { createUser, listUsers } from "@/features/iam/api/iam";
import { iamKeys } from "@/features/iam/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
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

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function UsersPage() {
  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("iam:user:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const [q, setQ] = React.useState("");
  const [status, setStatus] = React.useState<string>("");
  const [limit, setLimit] = React.useState(50);
  const [offset, setOffset] = React.useState(0);

  React.useEffect(() => {
    setOffset(0);
  }, [q, status, limit]);

  const usersQ = useQuery({
    queryKey: iamKeys.users({
      q: q.trim() ? q.trim() : null,
      status: status || null,
      limit,
      offset,
    }),
    queryFn: () =>
      listUsers({
        q: q.trim() ? q.trim() : null,
        status: status || null,
        limit,
        offset,
      }),
  });

  const items = (usersQ.data?.items ?? []) as IamUserOut[];
  const meta = (usersQ.data?.meta ?? { limit, offset, total: 0 }) as UsersListMeta;

  const total = meta.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const selectClassName = cn(
    "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  const [open, setOpen] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [newStatus, setNewStatus] = React.useState<"ACTIVE" | "DISABLED">("ACTIVE");

  const createM = useMutation({
    mutationFn: async () => {
      const payload: IamUserCreateIn = {
        email: email.trim(),
        phone: phone.trim() ? phone.trim() : null,
        password,
        status: newStatus,
      };
      if (!payload.email) throw new Error("Email is required.");
      if (!payload.password) throw new Error("Password is required.");
      return createUser(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setEmail("");
      setPhone("");
      setPassword("");
      setNewStatus("ACTIVE");
      await qc.invalidateQueries({ queryKey: ["iam", "users"] });
    },
    onError: (err) => toastApiError(err),
  });

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Users"
          subtitle="Create accounts and manage role assignments."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Create user
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create user</SheetTitle>
                  <SheetDescription>
                    New users are created in the active tenant. The backend assigns the default EMPLOYEE role in your current scope.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="user-email" className="text-xs text-text-2">
                      Email
                    </Label>
                    <Input
                      id="user-email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="user@company.com"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="user-phone" className="text-xs text-text-2">
                      Phone (optional)
                    </Label>
                    <Input
                      id="user-phone"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+966..."
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="user-password" className="text-xs text-text-2">
                      Password
                    </Label>
                    <Input
                      id="user-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="user-status" className="text-xs text-text-2">
                      Status
                    </Label>
                    <select
                      id="user-status"
                      className={selectClassName}
                      value={newStatus}
                      onChange={(e) => setNewStatus(e.target.value as "ACTIVE" | "DISABLED")}
                    >
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="DISABLED">DISABLED</option>
                    </select>
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
          toolbar={
            <FilterBar
              search={{
                value: q,
                onChange: setQ,
                placeholder: "Search users...",
              }}
              chips={
                <div className="flex items-center gap-2">
                  <div className="text-xs text-text-2">Status</div>
                  <select
                    className={cn(selectClassName, "h-9 py-1")}
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="DISABLED">DISABLED</option>
                  </select>
                </div>
              }
              rightActions={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-xs text-text-2">
                    {total ? (
                      <>
                        {offset + 1}-{Math.min(offset + limit, total)} of {total}
                      </>
                    ) : (
                      "—"
                    )}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!canPrev}
                    onClick={() => setOffset((o) => Math.max(0, o - limit))}
                  >
                    Prev
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!canNext}
                    onClick={() => setOffset((o) => o + limit)}
                  >
                    Next
                  </Button>
                  <select
                    className={cn(selectClassName, "h-9 py-1")}
                    value={String(limit)}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    aria-label="Rows per page"
                  >
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </select>
                </div>
              }
              onClearAll={() => {
                setQ("");
                setStatus("");
              }}
              clearDisabled={!q.trim() && !status}
            />
          }
          isLoading={usersQ.isLoading}
          error={usersQ.error}
          onRetry={usersQ.refetch}
          isEmpty={!usersQ.isLoading && !usersQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title={q.trim() || status ? "No matches" : "No users"}
              description={
                q.trim() || status
                  ? "Try adjusting your search or filters."
                  : "Create your first user to start assigning roles."
              }
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setOpen(true)}>
                    Create user
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 8, cols: 4 }}
        >
          <div className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((u, idx) => {
                  const id = typeof u.id === "string" ? u.id : "";
                  const canLink = Boolean(id) && isUuid(id);
                  return (
                    <TableRow key={canLink ? id : `${u.email}:${idx}`}>
                      <TableCell className="font-medium">
                        {canLink ? (
                          <Link
                            href={`/settings/access/users/${id}`}
                            className="underline-offset-4 hover:underline"
                          >
                            {u.email}
                          </Link>
                        ) : (
                          <div className="flex flex-wrap items-center gap-2">
                            <span>{u.email}</span>
                            <span className="text-xs text-text-3">(invalid id)</span>
                          </div>
                        )}
                      </TableCell>
                    <TableCell className="text-text-2">{u.phone ?? "—"}</TableCell>
                    <TableCell className="text-text-2">{u.status}</TableCell>
                    <TableCell className="text-text-2">{formatDateTime(u.created_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Notes
            </div>
            <div className="mt-2 text-sm text-text-2">
              Users are tenant-scoped. Role assignments can be tenant/company/branch scoped.
            </div>
          </DSCard>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">visible</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {items.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">total</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{total}</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
