import type { UUID } from "@/lib/types";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(value: string): value is UUID {
  return UUID_RE.test(value);
}

export function parseUuidParam(value: unknown): UUID | null {
  if (typeof value !== "string") return null;
  const v = value.trim();
  if (!v) return null;
  return isUuid(v) ? (v as UUID) : null;
}

