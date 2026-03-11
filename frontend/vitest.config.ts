import path from "node:path";

import { defineConfig } from "vitest/config";

const isCi = process.env.CI === "1" || process.env.CI === "true";
const isAct = process.env.ACT === "true";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    // Keep tests fast and deterministic.
    isolate: true,
    restoreMocks: true,
    testTimeout: isAct ? 90_000 : isCi ? 45_000 : 15_000,
    hookTimeout: isAct ? 30_000 : isCi ? 20_000 : 10_000,
    maxWorkers: isAct ? 2 : isCi ? 4 : undefined,
    setupFiles: ["src/test/setup/vitest.setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
