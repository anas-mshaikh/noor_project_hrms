"use client";

/**
 * /login
 *
 * Simple email/password login (through the Next.js BFF proxy).
 *
 * Notes:
 * - Tokens are stored in HttpOnly cookies by the BFF.
 * - Frontend stores only a redacted session view (user/roles/permissions/scope).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n";

import { apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type { MeResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const setFromSession = useAuth((s) => s.setFromSession);

  const setTenantId = useSelection((s) => s.setTenantId);
  const setCompanyId = useSelection((s) => s.setCompanyId);
  const setBranchId = useSelection((s) => s.setBranchId);

  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin");

  const loginM = useMutation({
    mutationFn: async () => {
      if (!email.trim()) {
        throw new Error(
          t("page.login.email_required", { defaultValue: "Email is required." })
        );
      }
      if (!password) {
        throw new Error(
          t("page.login.password_required", { defaultValue: "Password is required." })
        );
      }

      return apiJson<MeResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
    },
    onSuccess: (session) => {
      setFromSession(session);

      // Default client scope headers from the server-issued scope.
      setTenantId(session.scope?.tenant_id ? String(session.scope.tenant_id) : undefined);
      setCompanyId(session.scope?.company_id ? String(session.scope.company_id) : undefined);
      setBranchId(session.scope?.branch_id ? String(session.scope.branch_id) : undefined);

      router.push("/dashboard");
    },
  });

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("page.login.title", { defaultValue: "Sign in" })}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("page.login.subtitle", {
            defaultValue: "Use your admin/HR credentials to access the dashboard.",
          })}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("page.login.card_title", { defaultValue: "Login" })}</CardTitle>
          <CardDescription>
            {t("page.login.bootstrap_hint", {
              defaultValue: "If this is a fresh DB, you may need to bootstrap first.",
            })}{" "}
            <Link className="underline" href="/setup">
              bootstrap
            </Link>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">
              {t("page.login.email", { defaultValue: "Email" })}
            </Label>
            <Input
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("page.login.email", { defaultValue: "Email" })}
              autoComplete="email"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">
              {t("page.login.password", { defaultValue: "Password" })}
            </Label>
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
              {loginM.isPending
                ? t("page.login.signing_in", { defaultValue: "Signing in..." })
                : t("common.sign_in", { defaultValue: "Sign in" })}
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
