import { NextResponse } from "next/server";
type LoginBody = {
  password?: string;
};

export async function POST(req: Request) {
  const adminPassword = process.env.ADMIN_PASSWORD ?? "";
  if (!adminPassword) {
    return NextResponse.json(
      { ok: false, error: "ADMIN_PASSWORD is not configured on the server." },
      { status: 500 }
    );
  }

  const body = (await req.json().catch(() => ({}))) as LoginBody;
  const password = (body.password ?? "").trim();

  if (password !== adminPassword) {
    return NextResponse.json(
      { ok: false, error: "Invalid password." },
      { status: 401 }
    );
  }

  const sessionValue = crypto.randomUUID();

  const res = NextResponse.json({ ok: true });
  res.cookies.set("admin_session", sessionValue, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days
  });

  return res;
}
