import type { Metadata } from "next";
import "./globals.css";

import { Providers } from "./providers";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "Attendance Admin",
  description: "Admin dashboard for CCTV attendance processing",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  /**
   * RootLayout is a SERVER component by default.
   * It can safely render client components (Providers/Shell) inside it.
   */
  return (
    <html lang="en">
      {/* Use system fonts to avoid build-time network fetches (Google Fonts). */}
      <body className="antialiased">
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
