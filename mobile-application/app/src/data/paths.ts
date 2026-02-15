export const paths = {
  userMapping: (uid: string) => `users/${uid}`,

  monthDoc: (tenantId: string, branchId: string, monthKey: string) =>
    `tenants/${tenantId}/branches/${branchId}/months/${monthKey}`,

  employeeMonth: (
    tenantId: string,
    branchId: string,
    monthKey: string,
    employeeCode: string,
  ) =>
    `tenants/${tenantId}/branches/${branchId}/months/${monthKey}/employees/${employeeCode}`,

  leaderboardOverall: (tenantId: string, branchId: string, monthKey: string) =>
    `tenants/${tenantId}/branches/${branchId}/months/${monthKey}/leaderboards/overall`,

  leaderboardDept: (
    tenantId: string,
    branchId: string,
    monthKey: string,
    deptKey: string,
  ) =>
    `tenants/${tenantId}/branches/${branchId}/months/${monthKey}/leaderboards/dept-${deptKey}`,
};
