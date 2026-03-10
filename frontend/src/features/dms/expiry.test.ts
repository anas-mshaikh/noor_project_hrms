import { describe, expect, it } from "vitest";

import { expiryBucket, expiryLabel } from "@/features/dms/expiry";

describe("features/dms/expiry", () => {
  it("assigns days remaining to the correct bucket", () => {
    expect(expiryBucket(-1)).toBe("expired");
    expect(expiryBucket(0)).toBe("today");
    expect(expiryBucket(3)).toBe("week");
    expect(expiryBucket(14)).toBe("month");
    expect(expiryBucket(45)).toBe("later");
  });

  it("formats expiry labels", () => {
    expect(expiryLabel(0)).toBe("Expires today");
    expect(expiryLabel(1)).toBe("Expiring in 1 day");
    expect(expiryLabel(5)).toBe("Expiring in 5 days");
  });
});
