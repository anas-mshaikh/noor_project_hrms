"use client";

import { useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useSelection } from "@/lib/selection";

function scopeFingerprint(scope: {
  tenantId?: string;
  companyId?: string;
  branchId?: string;
}): string {
  return [scope.tenantId ?? "", scope.companyId ?? "", scope.branchId ?? ""].join("|");
}

/**
 * Scope changes must invalidate cached data aggressively.
 * Some older query keys do not encode scope dimensions directly, so we clear the
 * query client when tenant/company/branch changes to avoid cross-scope leakage.
 */
export function ScopeQueryReset(): null {
  const queryClient = useQueryClient();
  const tenantId = useSelection((s) => s.tenantId);
  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);
  const nextFingerprint = useMemo(
    () => scopeFingerprint({ tenantId, companyId, branchId }),
    [tenantId, companyId, branchId]
  );
  const prevFingerprint = useRef<string | null>(null);

  useEffect(() => {
    if (prevFingerprint.current == null) {
      prevFingerprint.current = nextFingerprint;
      return;
    }
    if (prevFingerprint.current === nextFingerprint) return;

    prevFingerprint.current = nextFingerprint;
    queryClient.clear();
  }, [nextFingerprint, queryClient]);

  return null;
}
