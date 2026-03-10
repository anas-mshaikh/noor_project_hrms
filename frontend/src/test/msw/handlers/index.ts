import { authHandlers } from "@/test/msw/handlers/auth.handlers";
import { attendanceHandlers } from "@/test/msw/handlers/attendance.handlers";
import { essHandlers } from "@/test/msw/handlers/ess.handlers";
import { hrCoreHandlers } from "@/test/msw/handlers/hrCore.handlers";
import { iamHandlers } from "@/test/msw/handlers/iam.handlers";
import { leaveHandlers } from "@/test/msw/handlers/leave.handlers";
import { mssHandlers } from "@/test/msw/handlers/mss.handlers";
import { payablesHandlers } from "@/test/msw/handlers/payables.handlers";
import { rosterHandlers } from "@/test/msw/handlers/roster.handlers";
import { scopeHandlers } from "@/test/msw/handlers/scope.handlers";
import { tenancyHandlers } from "@/test/msw/handlers/tenancy.handlers";
import { workflowHandlers } from "@/test/msw/handlers/workflow.handlers";
import { dmsHandlers } from "@/test/msw/handlers/dms.handlers";

export const handlers = [
  ...authHandlers,
  ...scopeHandlers,
  ...tenancyHandlers,
  ...hrCoreHandlers,
  ...essHandlers,
  ...mssHandlers,
  ...iamHandlers,
  ...workflowHandlers,
  ...dmsHandlers,
  ...attendanceHandlers,
  ...leaveHandlers,
  ...rosterHandlers,
  ...payablesHandlers,
];
