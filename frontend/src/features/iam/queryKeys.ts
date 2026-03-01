import type { UUID } from "@/lib/types";

export const iamKeys = {
  roles: () => ["iam", "roles"] as const,
  permissions: () => ["iam", "permissions"] as const,
  users: (args: { q?: string | null; status?: string | null; limit: number; offset: number }) =>
    ["iam", "users", args.q ?? null, args.status ?? null, args.limit, args.offset] as const,
  user: (userId: UUID) => ["iam", "user", userId] as const,
  userRoles: (userId: UUID) => ["iam", "user-roles", userId] as const,
};

