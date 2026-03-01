import React from "react";
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { server } from "@/test/msw/server";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { resetRouterMocks } from "@/test/utils/router";

// Some code uses `fetch("/api/v1/...")`. Node's fetch requires absolute URLs,
// so we resolve relative paths against a stable base for tests.
const realFetch = globalThis.fetch?.bind(globalThis);
if (realFetch) {
  globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && input.startsWith("/")) {
      return realFetch(`http://localhost${input}`, init);
    }
    return realFetch(input as RequestInfo | URL, init);
  };
}

// Next.js modules are not available in unit tests; provide minimal mocks.
vi.mock("next/link", () => {
  return {
    default: ({
      href,
      children,
      ...props
    }: {
      href: string | { pathname?: string };
      children?: React.ReactNode;
    } & Record<string, unknown>) =>
      React.createElement(
        "a",
        {
          href: typeof href === "string" ? href : href?.pathname ?? "",
          ...props,
        },
        children
      ),
  };
});

const originalLocationAssign =
  typeof window !== "undefined" && window.location
    ? window.location.assign.bind(window.location)
    : null;
const originalLocationReplace =
  typeof window !== "undefined" && window.location
    ? window.location.replace.bind(window.location)
    : null;

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });

  // Avoid jsdom "navigation not implemented" warnings from scope/login redirects.
  if (typeof window !== "undefined" && window.location) {
    try {
      Object.defineProperty(window.location, "assign", {
        value: () => {},
        configurable: true,
      });
      Object.defineProperty(window.location, "replace", {
        value: () => {},
        configurable: true,
      });
    } catch {
      // Best-effort only.
    }
  }
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetRouterMocks();

  // Reset client-side stores between tests (Zustand persist uses localStorage).
  useAuth.getState().clear();
  useSelection.getState().reset();
  window.localStorage.clear();
});

afterAll(() => {
  server.close();
  if (typeof window !== "undefined" && window.location) {
    try {
      if (originalLocationAssign) {
        Object.defineProperty(window.location, "assign", {
          value: originalLocationAssign,
          configurable: true,
        });
      }
      if (originalLocationReplace) {
        Object.defineProperty(window.location, "replace", {
          value: originalLocationReplace,
          configurable: true,
        });
      }
    } catch {
      // Best-effort only.
    }
  }
});
