"use client";

import * as React from "react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { EssProfilePatchIn, HrEmployee360Out } from "@/lib/types";
import { getMeProfile, patchMeProfile } from "@/features/ess/api/ess";
import { essKeys } from "@/features/ess/queryKeys";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function EssMeProfilePage() {
  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("ess:profile:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const profileQ = useQuery({
    queryKey: essKeys.meProfile(),
    queryFn: () => getMeProfile(),
  });

  const profile = profileQ.data as HrEmployee360Out | undefined;

  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [addressText, setAddressText] = React.useState("{}");

  React.useEffect(() => {
    if (!profile) return;
    setEmail(profile.person.email ?? "");
    setPhone(profile.person.phone ?? "");
    try {
      setAddressText(JSON.stringify(profile.person.address ?? {}, null, 2));
    } catch {
      setAddressText("{}");
    }
  }, [profile]);

  const patchM = useMutation({
    mutationFn: async () => {
      let address: Record<string, unknown> | null = {};
      const raw = addressText.trim();
      if (raw) {
        try {
          address = JSON.parse(raw) as Record<string, unknown>;
        } catch {
          throw new Error("Address must be valid JSON.");
        }
      }

      const payload: EssProfilePatchIn = {
        email: email.trim() ? email.trim() : null,
        phone: phone.trim() ? phone.trim() : null,
        address,
      };

      return patchMeProfile(payload);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: essKeys.meProfile() });
      toast.success("Profile updated");
    },
    onError: (err) => toastApiError(err),
  });

  if (profileQ.isLoading) {
    return (
      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="text-sm text-text-2">Loading…</div>
      </DSCard>
    );
  }

  if (profileQ.error) {
    const err = profileQ.error;
    if (err instanceof ApiError && err.code === "ess.not_linked") {
      return (
        <ErrorState title="Account not linked" error={err} />
      );
    }
    return (
      <ErrorState
        title="Could not load profile"
        error={profileQ.error}
        onRetry={profileQ.refetch}
      />
    );
  }

  if (!profile) {
    return (
      <EmptyState
        title="No profile"
        description="Your profile is not available."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Profile"
        subtitle="Review and update your contact information."
      />

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="ess-email" className="text-xs text-text-2">
              Email
            </Label>
            <Input
              id="ess-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={!canWrite}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ess-phone" className="text-xs text-text-2">
              Phone
            </Label>
            <Input
              id="ess-phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={!canWrite}
            />
          </div>
        </div>

        <div className="mt-6 space-y-1">
          <Label htmlFor="ess-address" className="text-xs text-text-2">
            Address (JSON)
          </Label>
          <textarea
            id="ess-address"
            className="min-h-28 w-full resize-y rounded-md border border-border-subtle bg-surface-1 px-3 py-2 font-mono text-xs text-text-1 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            value={addressText}
            onChange={(e) => setAddressText(e.target.value)}
            disabled={!canWrite}
          />
          <div className="text-xs text-text-3">
            Keep this minimal in Client V0 (e.g. city, country, line1).
          </div>
        </div>

        <div className="mt-6 flex items-center gap-2">
          <Button
            type="button"
            disabled={!canWrite || patchM.isPending}
            onClick={() => patchM.mutate()}
          >
            {patchM.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </DSCard>
    </div>
  );
}
