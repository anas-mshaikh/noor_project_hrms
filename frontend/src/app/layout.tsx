import type { Metadata } from "next";
import { cookies } from "next/headers";
import { headers } from "next/headers";
import "./globals.css";

import { Providers } from "./providers";
import { Shell } from "@/components/Shell";
import {
  LOCALE_COOKIE,
  localeToDir,
  normalizeLocale,
  pickLocaleFromAcceptLanguage
} from "@/lib/locale";

export const metadata: Metadata = {
  title: "Noor Project",
  description: "Admin dashboard for CCTV attendance processing",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const cookieLocale = normalizeLocale(cookieStore.get(LOCALE_COOKIE)?.value);
  const hdrs = await headers();
  const acceptLocale = pickLocaleFromAcceptLanguage(hdrs.get("accept-language"));
  const envDefault = normalizeLocale(process.env.NEXT_PUBLIC_DEFAULT_LOCALE);

  const locale =
    cookieStore.get(LOCALE_COOKIE)?.value
      ? cookieLocale
      : acceptLocale ?? (envDefault !== "en" ? envDefault : "en");
  const dir = localeToDir(locale);

  return (
    <html lang={locale} dir={dir} className="dark">
      <body className="antialiased">
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
