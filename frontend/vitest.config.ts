import path from "node:path";

import { defineConfig } from "vitest/config";

const isCi = process.env.CI === "1" || process.env.CI === "true";
const isAct = process.env.ACT === "true";
const testTimeout = 120_000;
const hookTimeout = isAct ? 30_000 : isCi ? 30_000 : 20_000;

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
    testTimeout,
    hookTimeout,
    maxWorkers: 2,
    setupFiles: ["src/test/setup/vitest.setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
