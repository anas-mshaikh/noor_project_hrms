import { authHandlers } from "@/test/msw/handlers/auth.handlers";
import { iamHandlers } from "@/test/msw/handlers/iam.handlers";
import { scopeHandlers } from "@/test/msw/handlers/scope.handlers";
import { tenancyHandlers } from "@/test/msw/handlers/tenancy.handlers";

export const handlers = [
  ...authHandlers,
  ...scopeHandlers,
  ...tenancyHandlers,
  ...iamHandlers,
];

