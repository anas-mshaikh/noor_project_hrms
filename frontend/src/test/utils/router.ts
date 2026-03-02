import { vi } from "vitest";

/**
 * test/utils/router.ts
 *
 * Stable Next.js App Router mocks for unit/component tests.
 *
 * Goal:
 * - avoid per-test `vi.mock("next/navigation")` blocks
 * - allow deterministic assertions on navigation (push/replace)
 */

let pathname = "/";
let searchParams = new URLSearchParams();
let params: Record<string, string | string[] | undefined> = {};

export const routerPush = vi.fn<(url: string) => void>();
export const routerReplace = vi.fn<(url: string) => void>();
export const routerRefresh = vi.fn<() => void>();
export const routerBack = vi.fn<() => void>();
export const routerForward = vi.fn<() => void>();
export const routerPrefetch = vi.fn<(url: string) => Promise<void>>(async () => {});

export function setPathname(nextPathname: string): void {
  pathname = nextPathname;
}

export function setSearchParams(
  next:
    | URLSearchParams
    | Record<string, string | number | boolean | null | undefined>
): void {
  if (next instanceof URLSearchParams) {
    searchParams = next;
    return;
  }

  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(next)) {
    if (v === null || v === undefined) continue;
    p.set(k, String(v));
  }
  searchParams = p;
}

export function setParams(next: Record<string, string | string[] | undefined>): void {
  params = next;
}

export function resetRouterMocks(): void {
  pathname = "/";
  searchParams = new URLSearchParams();
  params = {};
  routerPush.mockReset();
  routerReplace.mockReset();
  routerRefresh.mockReset();
  routerBack.mockReset();
  routerForward.mockReset();
  routerPrefetch.mockClear();
}

// Register the mock once at module load. Setup imports this file.
vi.mock("next/navigation", () => {
  return {
    useRouter: () => ({
      push: routerPush,
      replace: routerReplace,
      refresh: routerRefresh,
      back: routerBack,
      forward: routerForward,
      prefetch: routerPrefetch,
    }),
    usePathname: () => pathname,
    useSearchParams: () => searchParams,
    useParams: () => params,
  };
});
