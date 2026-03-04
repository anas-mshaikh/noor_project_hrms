import { apiJson } from "@/lib/api";
import type { EssProfilePatchIn, HrEmployee360Out } from "@/lib/types";

/**
 * ESS API wrapper (employee self service).
 */

export async function getMeProfile(init?: RequestInit): Promise<HrEmployee360Out> {
  return apiJson<HrEmployee360Out>("/api/v1/ess/me/profile", init);
}

export async function patchMeProfile(
  payload: EssProfilePatchIn,
  init?: RequestInit
): Promise<HrEmployee360Out> {
  return apiJson<HrEmployee360Out>("/api/v1/ess/me/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...init,
  });
}

