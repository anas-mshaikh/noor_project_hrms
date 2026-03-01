import { apiEnvelope, apiJson } from "@/lib/api";
import type {
  IamRoleAssignIn,
  IamUserCreateIn,
  IamUserOut,
  IamUserPatchIn,
  PermissionOut,
  RoleOut,
  UserRoleOut,
  UUID,
  UsersListMeta,
} from "@/lib/types";

/**
 * IAM API wrapper.
 *
 * Notes:
 * - Pure functions only (no React).
 * - Users list returns meta; use `apiEnvelope` (added in PR6) for that endpoint.
 */

export async function listRoles(init?: RequestInit): Promise<RoleOut[]> {
  return apiJson<RoleOut[]>("/api/v1/iam/roles", init);
}

export async function listPermissions(init?: RequestInit): Promise<PermissionOut[]> {
  return apiJson<PermissionOut[]>("/api/v1/iam/permissions", init);
}

export type UsersListOut = { items: IamUserOut[]; meta: UsersListMeta };

export async function listUsers(
  args: {
    limit: number;
    offset: number;
    q?: string | null;
    status?: string | null;
  },
  init?: RequestInit
): Promise<UsersListOut> {
  const qs = new URLSearchParams({
    limit: String(args.limit),
    offset: String(args.offset),
  });
  if (args.q) qs.set("q", args.q);
  if (args.status) qs.set("status", args.status);

  const env = await apiEnvelope<IamUserOut[]>(
    `/api/v1/iam/users?${qs.toString()}`,
    init
  );

  return { items: env.data ?? [], meta: (env.meta ?? { limit: args.limit, offset: args.offset, total: 0 }) as UsersListMeta };
}

export async function getUser(userId: UUID, init?: RequestInit): Promise<IamUserOut> {
  return apiJson<IamUserOut>(`/api/v1/iam/users/${userId}`, init);
}

export async function patchUser(
  userId: UUID,
  payload: IamUserPatchIn,
  init?: RequestInit
): Promise<IamUserOut> {
  return apiJson<IamUserOut>(`/api/v1/iam/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listUserRoles(userId: UUID, init?: RequestInit): Promise<UserRoleOut[]> {
  return apiJson<UserRoleOut[]>(`/api/v1/iam/users/${userId}/roles`, init);
}

export async function assignUserRole(
  userId: UUID,
  payload: IamRoleAssignIn,
  init?: RequestInit
): Promise<UserRoleOut> {
  return apiJson<UserRoleOut>(`/api/v1/iam/users/${userId}/roles`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function removeUserRole(
  userId: UUID,
  args: { roleCode: string; companyId?: UUID | null; branchId?: UUID | null },
  init?: RequestInit
): Promise<{ deleted: boolean }> {
  const qs = new URLSearchParams({ role_code: args.roleCode });
  if (args.companyId) qs.set("company_id", args.companyId);
  if (args.branchId) qs.set("branch_id", args.branchId);
  return apiJson<{ deleted: boolean }>(`/api/v1/iam/users/${userId}/roles?${qs.toString()}`, {
    method: "DELETE",
    ...init,
  });
}

export async function createUser(
  payload: IamUserCreateIn,
  init?: RequestInit
): Promise<IamUserOut> {
  return apiJson<IamUserOut>("/api/v1/iam/users", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}
