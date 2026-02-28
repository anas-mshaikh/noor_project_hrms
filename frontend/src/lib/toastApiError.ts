import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { getErrorUx } from "@/lib/errorUx";

type TFn = (key: string, options?: { defaultValue?: string }) => string;

function copyToClipboard(text: string): void {
  void navigator.clipboard.writeText(text).catch(() => {
    // Best-effort only.
  });
}

export function toastApiError(err: unknown, t?: TFn): void {
  const ux = getErrorUx(err);
  const apiErr = err instanceof ApiError ? err : null;
  const cid = apiErr?.correlationId ?? null;

  const referenceLine = cid ? `Reference: ${cid}` : null;
  const description = referenceLine ? `${ux.description}\n${referenceLine}` : ux.description;

  toast.error(t ? t("common.error", { defaultValue: ux.title }) : ux.title, {
    description,
    action: cid
      ? {
          label: t ? t("common.copy_ref", { defaultValue: "Copy ref" }) : "Copy ref",
          onClick: () => copyToClipboard(cid),
        }
      : undefined,
  });
}

