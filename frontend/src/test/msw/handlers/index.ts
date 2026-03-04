import { authHandlers } from "@/test/msw/handlers/auth.handlers";
import { essHandlers } from "@/test/msw/handlers/ess.handlers";
import { hrCoreHandlers } from "@/test/msw/handlers/hrCore.handlers";
import { iamHandlers } from "@/test/msw/handlers/iam.handlers";
import { mssHandlers } from "@/test/msw/handlers/mss.handlers";
import { scopeHandlers } from "@/test/msw/handlers/scope.handlers";
import { tenancyHandlers } from "@/test/msw/handlers/tenancy.handlers";

export const handlers = [
  ...authHandlers,
  ...scopeHandlers,
  ...tenancyHandlers,
  ...hrCoreHandlers,
  ...essHandlers,
  ...mssHandlers,
  ...iamHandlers,
];
