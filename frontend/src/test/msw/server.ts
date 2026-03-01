import { setupServer } from "msw/node";

import { handlers } from "@/test/msw/handlers/index";

export const server = setupServer(...handlers);
