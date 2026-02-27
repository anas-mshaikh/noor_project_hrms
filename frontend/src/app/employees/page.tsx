"use client";

/**
 * /employees
 *
 * Canonical HR directory + attendance face enrollment helpers.
 *
 * Backend endpoints used:
 * - GET  /api/v1/hr/employees?branch_id=...
 * - POST /api/v1/hr/employees
 * - POST /api/v1/branches/{branch_id}/employees/{employee_id}/faces/register (multipart: file)
 * - POST /api/v1/branches/{branch_id}/faces/recognize (multipart: file, query: top_k)
 * - GET  /api/v1/branches/{branch_id}/mobile/accounts
 * - POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/provision
 * - POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/revoke
 * - POST /api/v1/mobile/resync/{firebase_uid}
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n";

import { apiForm, apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type {
  EmployeeDirectoryListOut,
  EmployeeDirectoryRowOut,
  FaceRecognizeOut,
  FaceRegisterOut,
  MobileAccountOut,
  UUID,
} from "@/lib/types";
import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type HREmployeeCreatePayload = {
  person: {
    first_name: string;
    last_name: string;
    dob?: string | null;
    nationality?: string | null;
    email?: string | null;
    phone?: string | null;
    address: Record<string, unknown>;
  };
  employee: {
    company_id: UUID;
    employee_code: string;
    join_date?: string | null;
    status: "ACTIVE" | "INACTIVE" | "TERMINATED";
  };
  employment: {
    start_date: string;
    branch_id: UUID;
    org_unit_id?: UUID | null;
    job_title_id?: UUID | null;
    grade_id?: UUID | null;
    manager_employee_id?: UUID | null;
    is_primary: boolean;
  };
};

type MobileProvisionOut = {
  firebase_uid: string;
  employee_id: string;
  employee_code: string;
  active: boolean;
  generated_password?: string | null;
};

export default function EmployeesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);

  // ----------------------------
  // Directory filters
  // ----------------------------
  const [q, setQ] = useState("");

  const employeesQ = useQuery({
    queryKey: ["hr-employees", companyId, branchId, q],
    enabled: Boolean(companyId && branchId),
    queryFn: () => {
      if (!branchId) throw new Error("Select a branch first.");
      const params = new URLSearchParams({
        branch_id: branchId,
        limit: "200",
        offset: "0",
      });
      if (q.trim()) params.set("q", q.trim());
      return apiJson<EmployeeDirectoryListOut>(`/api/v1/hr/employees?${params.toString()}`);
    },
  });

  const employees = useMemo<EmployeeDirectoryRowOut[]>(
    () => employeesQ.data?.items ?? [],
    [employeesQ.data]
  );

  const employeeById = useMemo(() => {
    const m = new Map<string, EmployeeDirectoryRowOut>();
    for (const e of employees) m.set(e.employee_id, e);
    return m;
  }, [employees]);

  // ----------------------------
  // Create employee (HR canonical)
  // ----------------------------
  const [employeeCode, setEmployeeCode] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [startDate, setStartDate] = useState(() => {
    // YYYY-MM-DD (local)
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  });

  const createEmployeeM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Select a company first.");
      if (!branchId) throw new Error("Select a branch first.");
      if (!employeeCode.trim()) throw new Error("employee_code is required.");
      if (!firstName.trim()) throw new Error("first_name is required.");
      if (!lastName.trim()) throw new Error("last_name is required.");
      if (!startDate.trim()) throw new Error("start_date is required.");

      const payload: HREmployeeCreatePayload = {
        person: {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim() ? email.trim() : null,
          phone: phone.trim() ? phone.trim() : null,
          address: {},
        },
        employee: {
          company_id: companyId as UUID,
          employee_code: employeeCode.trim(),
          join_date: startDate.trim(),
          status: "ACTIVE",
        },
        employment: {
          start_date: startDate.trim(),
          branch_id: branchId as UUID,
          org_unit_id: null,
          job_title_id: null,
          grade_id: null,
          manager_employee_id: null,
          is_primary: true,
        },
      };

      // Response is an Employee360 object; we don't need its exact shape here.
      return apiJson<unknown>("/api/v1/hr/employees", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      setEmployeeCode("");
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhone("");
      await qc.invalidateQueries({ queryKey: ["hr-employees", companyId, branchId] });
    },
  });

  // ----------------------------
  // Face enrollment (register N images)
  // ----------------------------
  const [targetEmployeeId, setTargetEmployeeId] = useState<string>("");
  const [faceFiles, setFaceFiles] = useState<File[]>([]);
  const [lastFaceUploads, setLastFaceUploads] = useState<FaceRegisterOut[] | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const uploadFacesM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!targetEmployeeId) throw new Error("Select an employee to enroll faces.");
      if (faceFiles.length === 0) throw new Error("Select 1..N face images first.");

      const out: FaceRegisterOut[] = [];
      for (const f of faceFiles) {
        const form = new FormData();
        form.append("file", f, f.name);
        const stored = await apiForm<FaceRegisterOut>(
          `/api/v1/branches/${branchId}/employees/${targetEmployeeId}/faces/register`,
          form,
          { method: "POST" }
        );
        out.push(stored);
      }
      return out;
    },
    onSuccess: (res) => {
      setLastFaceUploads(res);
      setFaceFiles([]);
      setFileInputKey((k) => k + 1);
    },
  });

  // ----------------------------
  // Face recognition (debug helper)
  // ----------------------------
  const [queryFace, setQueryFace] = useState<File | null>(null);
  const [topK, setTopK] = useState(5);

  const recognizeM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!queryFace) throw new Error("Select a face image to recognize.");
      const limit = Math.max(1, Math.min(20, Number(topK) || 5));

      const form = new FormData();
      form.append("file", queryFace, queryFace.name);

      return apiForm<FaceRecognizeOut>(
        `/api/v1/branches/${branchId}/faces/recognize?top_k=${encodeURIComponent(String(limit))}`,
        form,
        { method: "POST" }
      );
    },
  });

  // ----------------------------
  // Mobile accounts (branch-scoped)
  // ----------------------------
  const mobileAccountsQ = useQuery({
    queryKey: ["mobileAccounts", branchId],
    enabled: Boolean(branchId),
    queryFn: () => apiJson<MobileAccountOut[]>(`/api/v1/branches/${branchId}/mobile/accounts`),
    refetchOnWindowFocus: false,
  });

  const mobileByEmployeeId = useMemo(() => {
    const map = new Map<string, MobileAccountOut>();
    for (const row of mobileAccountsQ.data ?? []) map.set(row.employee_id, row);
    return map;
  }, [mobileAccountsQ.data]);

  const [mobileDialogOpen, setMobileDialogOpen] = useState(false);
  const [mobileDialogEmployee, setMobileDialogEmployee] = useState<EmployeeDirectoryRowOut | null>(null);
  const [mobileEmail, setMobileEmail] = useState("");
  const [mobileRole, setMobileRole] = useState<"employee" | "admin">("employee");
  const [mobileTempPassword, setMobileTempPassword] = useState("");
  const [mobileGeneratedPassword, setMobileGeneratedPassword] = useState<string | null>(null);

  const provisionMobileM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!mobileDialogEmployee) throw new Error("Select an employee first.");
      if (!mobileEmail.trim()) throw new Error("Email is required for MVP provisioning.");

      return apiJson<MobileProvisionOut>(
        `/api/v1/branches/${branchId}/employees/${mobileDialogEmployee.employee_id}/mobile/provision`,
        {
          method: "POST",
          body: JSON.stringify({
            email: mobileEmail.trim(),
            role: mobileRole,
            temp_password: mobileTempPassword.trim() || undefined,
          }),
        }
      );
    },
    onSuccess: async (res) => {
      setMobileGeneratedPassword(res.generated_password ?? null);
      await qc.invalidateQueries({ queryKey: ["mobileAccounts", branchId] });
    },
  });

  const revokeMobileM = useMutation({
    mutationFn: async (employeeId: string) => {
      if (!branchId) throw new Error("Select a branch first.");
      return apiJson<{ firebase_uid: string; active: boolean }>(
        `/api/v1/branches/${branchId}/employees/${employeeId}/mobile/revoke`,
        { method: "POST" }
      );
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["mobileAccounts", branchId] });
    },
  });

  const resyncMobileM = useMutation({
    mutationFn: async (firebaseUid: string) => {
      return apiJson<{ firebase_uid: string; resynced: boolean }>(
        `/api/v1/mobile/resync/${firebaseUid}`,
        { method: "POST" }
      );
    },
  });

  if (!companyId || !branchId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Employees</CardTitle>
          <CardDescription>
            {t("page.employees.select_scope", {
              defaultValue: "Select a tenant + company + branch first.",
            })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <StorePicker />
          </div>
        </CardContent>
      </Card>
    );
  }

  const employeeOptions = employees.map((e) => ({
    id: e.employee_id,
    label: `${e.employee_code} — ${e.full_name}`,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("nav.items.employees.title", { defaultValue: "Employees" })}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("page.employees.subtitle", {
            defaultValue:
              "HR directory + face enrollment + mobile provisioning (permission-driven).",
          })}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Directory</CardTitle>
          <CardDescription>List employees for the selected branch.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">Search</Label>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="name, code, email…" />
            </div>
            <div className="flex items-end">
              <Button type="button" variant="outline" onClick={() => employeesQ.refetch()}>
                Refresh
              </Button>
            </div>
          </div>

          {employeesQ.isError ? (
            <div className="text-sm text-destructive">
              {employeesQ.error instanceof Error ? employeesQ.error.message : String(employeesQ.error)}
            </div>
          ) : null}

          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Manager</TableHead>
                  <TableHead>Mobile</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(employeesQ.data?.items ?? []).map((e) => {
                  const mobile = mobileByEmployeeId.get(e.employee_id) ?? null;
                  return (
                    <TableRow key={e.employee_id}>
                      <TableCell className="font-mono text-xs">{e.employee_code}</TableCell>
                      <TableCell>{e.full_name}</TableCell>
                      <TableCell>
                        <Badge variant={e.status === "ACTIVE" ? "secondary" : "outline"}>
                          {e.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {e.manager_name ?? "—"}
                      </TableCell>
                      <TableCell className="space-x-2">
                        {mobile ? (
                          <>
                            <Badge variant={mobile.active ? "secondary" : "outline"}>
                              {mobile.active ? "ACTIVE" : "REVOKED"}
                            </Badge>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={revokeMobileM.isPending}
                              onClick={() => revokeMobileM.mutate(e.employee_id)}
                            >
                              Revoke
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={resyncMobileM.isPending}
                              onClick={() => resyncMobileM.mutate(mobile.firebase_uid)}
                            >
                              Resync
                            </Button>
                          </>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setMobileGeneratedPassword(null);
                              setMobileEmail("");
                              setMobileTempPassword("");
                              setMobileRole("employee");
                              setMobileDialogEmployee(e);
                              setMobileDialogOpen(true);
                            }}
                          >
                            Provision
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Create Employee</CardTitle>
          <CardDescription>
            Creates a canonical HR employee and assigns an active employment to the selected branch.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Employee code</Label>
              <Input value={employeeCode} onChange={(e) => setEmployeeCode(e.target.value)} placeholder="E001" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">First name</Label>
              <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Rahul" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Last name</Label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Sharma" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Email (optional)</Label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="rahul@example.com" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Phone (optional)</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+966…" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Start date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => createEmployeeM.mutate()} disabled={createEmployeeM.isPending}>
              {createEmployeeM.isPending ? "Creating…" : "Create"}
            </Button>
            {createEmployeeM.isError ? (
              <div className="text-sm text-destructive">
                {createEmployeeM.error instanceof Error ? createEmployeeM.error.message : String(createEmployeeM.error)}
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Enroll Face Templates</CardTitle>
          <CardDescription>
            Upload 1..N images; backend will crop/detect the best face and store training crops.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Employee</Label>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={targetEmployeeId}
                onChange={(e) => setTargetEmployeeId(e.target.value)}
              >
                <option value="">Select employee…</option>
                {employeeOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Face images</Label>
              <Input
                key={fileInputKey}
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => setFaceFiles(Array.from(e.target.files ?? []))}
              />
              <div className="text-xs text-muted-foreground">
                Use clear, front-facing images (1 person per image).
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => uploadFacesM.mutate()} disabled={uploadFacesM.isPending}>
              {uploadFacesM.isPending ? "Uploading…" : "Upload"}
            </Button>
            {uploadFacesM.isError ? (
              <div className="text-sm text-destructive">
                {uploadFacesM.error instanceof Error ? uploadFacesM.error.message : String(uploadFacesM.error)}
              </div>
            ) : null}
          </div>

          {lastFaceUploads ? (
            <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
              {JSON.stringify(lastFaceUploads, null, 2)}
            </pre>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recognize (Debug)</CardTitle>
          <CardDescription>
            Upload a face image and see the top matches for this branch.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs text-muted-foreground">Query image</Label>
              <Input type="file" accept="image/*" onChange={(e) => setQueryFace(e.target.files?.[0] ?? null)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Top K</Label>
              <Input value={String(topK)} onChange={(e) => setTopK(Number(e.target.value) || 5)} />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={() => recognizeM.mutate()} disabled={recognizeM.isPending}>
              {recognizeM.isPending ? "Running…" : "Recognize"}
            </Button>
            {recognizeM.isError ? (
              <div className="text-sm text-destructive">
                {recognizeM.error instanceof Error ? recognizeM.error.message : String(recognizeM.error)}
              </div>
            ) : null}
          </div>

          {recognizeM.data ? (
            <div className="space-y-3">
              <div className="text-sm">
                winner:{" "}
                <span className="font-mono text-xs">
                  {recognizeM.data.employee_id ?? "none"}
                </span>{" "}
                (confidence {recognizeM.data.confidence.toFixed(3)})
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-2">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Cosine sim</TableHead>
                      <TableHead>Confidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recognizeM.data.top_k.map((m) => {
                      const emp = employeeById.get(String(m.employee_id)) ?? null;
                      return (
                        <TableRow key={String(m.employee_id)}>
                          <TableCell>
                            {emp ? (
                              <div>
                                <div className="text-sm font-medium">{emp.full_name}</div>
                                <div className="text-xs text-muted-foreground font-mono">
                                  {emp.employee_code} • {emp.employee_id}
                                </div>
                              </div>
                            ) : (
                              <div className="font-mono text-xs">{String(m.employee_id)}</div>
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {m.cosine_similarity.toFixed(4)}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {m.confidence.toFixed(4)}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={mobileDialogOpen} onOpenChange={setMobileDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Provision Mobile Access</DialogTitle>
            <DialogDescription>
              Creates/enables Firebase user and writes `users/{"{uid}"}` mapping doc.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="text-sm text-muted-foreground">
              employee:{" "}
              <span className="font-mono text-xs">
                {mobileDialogEmployee?.employee_code} • {mobileDialogEmployee?.full_name}
              </span>
            </div>

            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={mobileEmail} onChange={(e) => setMobileEmail(e.target.value)} placeholder="employee@example.com" />
            </div>

            <div className="space-y-2">
              <Label>Role</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={mobileRole}
                  onChange={(e) => setMobileRole(e.target.value as "employee" | "admin")}
                >
                <option value="employee">employee</option>
                <option value="admin">admin</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label>Temp password (optional)</Label>
              <Input
                type="password"
                value={mobileTempPassword}
                onChange={(e) => setMobileTempPassword(e.target.value)}
                placeholder="leave blank to auto-generate"
              />
            </div>

            {mobileGeneratedPassword ? (
              <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm">
                Generated password:{" "}
                <span className="font-mono text-xs">{mobileGeneratedPassword}</span>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              onClick={() => provisionMobileM.mutate()}
              disabled={provisionMobileM.isPending}
            >
              {provisionMobileM.isPending ? "Provisioning…" : "Provision"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
