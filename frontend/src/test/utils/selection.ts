import type { MeResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";

/**
 * test/utils/selection.ts
 *
 * Helpers to seed/clear scope and auth state in a production-consistent way.
 *
 * NOTE:
 * - `useSelection` writes to both localStorage (persist) and non-HttpOnly cookie mirrors.
 * - These helpers always use the store APIs (do not manually poke localStorage).
 */

export function seedScope(opts: {
  tenantId: string;
  companyId?: string | null;
  branchId?: string | null;
}): void {
  const sel = useSelection.getState();
  sel.setTenantId(opts.tenantId);
  if (opts.companyId) sel.setCompanyId(opts.companyId);
  if (opts.branchId) sel.setBranchId(opts.branchId);
}

export function clearScope(): void {
  useSelection.persist.clearStorage();
  useSelection.getState().reset();
}

export function seedSession(session: MeResponse): void {
  useAuth.getState().setFromSession(session);
}
