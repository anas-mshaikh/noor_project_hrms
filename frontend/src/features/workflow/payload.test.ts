import { describe, expect, it } from "vitest";

import { payloadToRows, stableStringify } from "./payload";

describe("features/workflow/payload", () => {
  it("stableStringify sorts object keys for deterministic output", () => {
    expect(stableStringify({ b: 2, a: 1 })).toBe(
      JSON.stringify({ a: 1, b: 2 }),
    );
    expect(stableStringify({ z: { b: 2, a: 1 } })).toBe(
      JSON.stringify({ z: { a: 1, b: 2 } }),
    );
  });

  it("payloadToRows renders primitives and stringifies nested structures", () => {
    expect(
      payloadToRows({
        b: true,
        a: "x",
        c: { b: 2, a: 1 },
        d: [2, 1],
        e: null,
      }),
    ).toEqual([
      { key: "a", value: "x" },
      { key: "b", value: "true" },
      { key: "c", value: JSON.stringify({ a: 1, b: 2 }) },
      { key: "d", value: JSON.stringify([2, 1]) },
      { key: "e", value: "null" },
    ]);
  });
});
