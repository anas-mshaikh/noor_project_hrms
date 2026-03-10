import type {
  RosterOverrideUpsertIn,
  ShiftAssignmentCreateIn,
  UUID,
} from "@/lib/types";

export function buildAssignmentPayload(args: {
  shiftTemplateId: UUID | null;
  effectiveFrom: string;
  effectiveTo: string;
}): ShiftAssignmentCreateIn {
  if (!args.shiftTemplateId) throw new Error("Shift template is required.");
  if (!args.effectiveFrom) throw new Error("Effective from is required.");
  if (args.effectiveTo && args.effectiveTo < args.effectiveFrom) {
    throw new Error("Effective to must be on or after the start date.");
  }
  return {
    shift_template_id: args.shiftTemplateId,
    effective_from: args.effectiveFrom,
    effective_to: args.effectiveTo || null,
  };
}

export function buildOverridePayload(args: {
  overrideType: "SHIFT_CHANGE" | "WEEKOFF" | "WORKDAY" | "";
  shiftTemplateId: UUID | null;
  notes: string;
}): RosterOverrideUpsertIn {
  if (!args.overrideType) throw new Error("Override type is required.");
  if (args.overrideType === "SHIFT_CHANGE" && !args.shiftTemplateId) {
    throw new Error("Shift template is required for shift changes.");
  }
  if (args.overrideType !== "SHIFT_CHANGE" && args.shiftTemplateId) {
    throw new Error("Shift template is only allowed for shift changes.");
  }
  return {
    override_type: args.overrideType,
    shift_template_id: args.overrideType === "SHIFT_CHANGE" ? args.shiftTemplateId : null,
    notes: args.notes.trim() ? args.notes.trim() : null,
  };
}
