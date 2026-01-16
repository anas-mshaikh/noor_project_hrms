import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET() {
  const cookieStore = await cookies();
  const hasSession = Boolean(cookieStore.get("admin_session")?.value);
  return NextResponse.json({ is_admin: hasSession });
}
