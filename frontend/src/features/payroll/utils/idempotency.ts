export function newPayrollIdempotencyKey(prefix: string): string {
  const randomPart =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now()}`;

  return `${prefix}:${randomPart}`;
}
