"use client";

/**
 * /login
 *
 * Simple email/password login against the FastAPI auth endpoints.
 * Stores tokens in localStorage (Zustand persist) and defaults scope headers
 * (tenant/company/branch) in selection state.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type { TokenResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const setFromTokenResponse = useAuth((s) => s.setFromTokenResponse);

  const setTenantId = useSelection((s) => s.setTenantId);
  const setCompanyId = useSelection((s) => s.setCompanyId);
  const setBranchId = useSelection((s) => s.setBranchId);

  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin");

  const loginM = useMutation({
    mutationFn: async () => {
      if (!email.trim()) throw new Error("Email is required.");
      if (!password) throw new Error("Password is required.");

      return apiJson<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
    },
    onSuccess: (t) => {
      setFromTokenResponse(t);

      // Default client scope headers from the server-issued scope.
      setTenantId(String(t.scope.tenant_id));
      setCompanyId(t.scope.company_id ? String(t.scope.company_id) : undefined);
      setBranchId(t.scope.branch_id ? String(t.scope.branch_id) : undefined);

      router.push("/dashboard");
    },
  });

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Use your admin/HR credentials to access the dashboard.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Login</CardTitle>
          <CardDescription>
            If this is a fresh DB, you may need to <Link className="underline" href="/setup">bootstrap</Link> first.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              autoComplete="email"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => loginM.mutate()} disabled={loginM.isPending}>
              {loginM.isPending ? "Signing in…" : "Sign in"}
            </Button>

            {loginM.isError ? (
              <div className="text-sm text-destructive">
                {loginM.error instanceof Error ? loginM.error.message : String(loginM.error)}
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

