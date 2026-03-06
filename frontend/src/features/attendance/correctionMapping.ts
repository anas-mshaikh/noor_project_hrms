export type AttendanceCorrectionType =
  | "MISSED_PUNCH"
  | "MARK_PRESENT"
  | "MARK_ABSENT"
  | "WFH"
  | "ON_DUTY"
  | string;

export type RequestedOverrideStatus =
  | "PRESENT_OVERRIDE"
  | "ABSENT_OVERRIDE"
  | "WFH"
  | "ON_DUTY"
  | string;

/**
 * Backend requires both `correction_type` and `requested_override_status`.
 * In v1 UI we derive a safe default from the correction type.
 */
export function requestedOverrideForCorrectionType(
  correctionType: AttendanceCorrectionType
): RequestedOverrideStatus {
  switch (String(correctionType).toUpperCase()) {
    case "MARK_PRESENT":
      return "PRESENT_OVERRIDE";
    case "MARK_ABSENT":
      return "ABSENT_OVERRIDE";
    case "WFH":
      return "WFH";
    case "ON_DUTY":
      return "ON_DUTY";
    case "MISSED_PUNCH":
    default:
      // v1: treat missed punch as a present override (manual correction).
      return "PRESENT_OVERRIDE";
  }
}

