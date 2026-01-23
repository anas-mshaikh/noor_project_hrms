/**
 * components/shell/Shell.tsx
 *
 * Global layout wrapper.
 *
 * Composition:
 * - ShellBackdrop (single background layer)
 * - TopBar (modules + actions)
 * - SidebarRail (icon-only, active module)
 * - Main content container
 */

import { ShellBackdrop } from "@/components/shell/ShellBackdrop";
import { SidebarRail } from "@/components/shell/SidebarRail";
import { TopBar } from "@/components/shell/TopBar";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen text-foreground">
      <ShellBackdrop />

      <TopBar />

      <div className="relative flex min-h-[calc(100vh-56px)]">
        <SidebarRail />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}

