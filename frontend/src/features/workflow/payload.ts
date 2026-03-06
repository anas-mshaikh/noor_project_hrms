export type PayloadRow = { key: string; value: string };

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sortKeysDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeysDeep);
  if (!isPlainObject(value)) return value;
  const out: Record<string, unknown> = {};
  for (const k of Object.keys(value).sort()) out[k] = sortKeysDeep(value[k]);
  return out;
}

export function stableStringify(value: unknown): string {
  try {
    return JSON.stringify(sortKeysDeep(value));
  } catch {
    // Last resort; avoid throwing in UI.
    return String(value);
  }
}

export function payloadToRows(payload: unknown): PayloadRow[] {
  if (!payload || typeof payload !== "object") return [];

  const obj = payload as Record<string, unknown>;
  const rows: PayloadRow[] = [];
  for (const k of Object.keys(obj).sort()) {
    const v = obj[k];
    if (v === undefined) continue;
    if (v === null) {
      rows.push({ key: k, value: "null" });
      continue;
    }
    if (
      typeof v === "string" ||
      typeof v === "number" ||
      typeof v === "boolean"
    ) {
      rows.push({ key: k, value: String(v) });
      continue;
    }
    rows.push({ key: k, value: stableStringify(v) });
  }
  return rows;
}
