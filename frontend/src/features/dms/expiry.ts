export type DmsExpiryBucket = "expired" | "today" | "week" | "month" | "later";

export function expiryBucket(daysLeft: number): DmsExpiryBucket {
  if (daysLeft < 0) return "expired";
  if (daysLeft === 0) return "today";
  if (daysLeft <= 7) return "week";
  if (daysLeft <= 30) return "month";
  return "later";
}

export function expiryLabel(daysLeft: number): string {
  if (daysLeft < 0) return `Expired ${Math.abs(daysLeft)} day${Math.abs(daysLeft) === 1 ? "" : "s"} ago`;
  if (daysLeft === 0) return "Expires today";
  if (daysLeft === 1) return "Expiring in 1 day";
  return `Expiring in ${daysLeft} days`;
}
