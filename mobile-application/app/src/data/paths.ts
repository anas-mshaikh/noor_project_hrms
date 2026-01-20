export const paths = {
  userMapping: (uid: string) => `users/${uid}`,

  monthDoc: (orgId: string, storeId: string, monthKey: string) =>
    `orgs/${orgId}/stores/${storeId}/months/${monthKey}`,

  employeeMonth: (
    orgId: string,
    storeId: string,
    monthKey: string,
    employeeCode: string,
  ) =>
    `orgs/${orgId}/stores/${storeId}/months/${monthKey}/employees/${employeeCode}`,

  leaderboardOverall: (orgId: string, storeId: string, monthKey: string) =>
    `orgs/${orgId}/stores/${storeId}/months/${monthKey}/leaderboards/overall`,

  leaderboardDept: (
    orgId: string,
    storeId: string,
    monthKey: string,
    deptKey: string,
  ) =>
    `orgs/${orgId}/stores/${storeId}/months/${monthKey}/leaderboards/dept-${deptKey}`,
};
