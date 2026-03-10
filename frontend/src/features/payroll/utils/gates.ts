import type { PayrunOut } from "@/lib/types";

function includedCount(payrun: PayrunOut | null | undefined): number {
  const raw = payrun?.totals_json?.included_count;
  return typeof raw === "number" ? raw : Number(raw ?? 0) || 0;
}

export function canSubmitPayrun(payrun: PayrunOut | null | undefined): boolean {
  return (payrun?.status ?? "") === "DRAFT" && includedCount(payrun) > 0;
}

export function canPublishPayrun(payrun: PayrunOut | null | undefined): boolean {
  return (payrun?.status ?? "") === "APPROVED";
}
