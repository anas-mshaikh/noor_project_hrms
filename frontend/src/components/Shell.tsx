"use client";

/**
 * components/Shell.tsx
 *
 * Global layout wrapper:
 * - top nav (Setup / Employees / Videos)
 * - StorePicker (select org/store/camera and persist it)
 * - content container
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { StorePicker } from "@/components/StorePicker";
import { useSelection } from "@/lib/selection";

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // We show these IDs as a tiny debug hint (helps while building MVP fast).
  const storeId = useSelection((s) => s.storeId);
  const cameraId = useSelection((s) => s.cameraId);

  const nav = [
    { href: "/setup", label: "Setup" },
    { href: "/employees", label: "Employees" },
    { href: "/videos", label: "Videos" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center justify-between gap-4">
            <Link href="/setup" className="font-semibold">
              Attendance Admin
            </Link>

            <nav className="flex items-center gap-2 text-sm">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded px-2 py-1 ${
                      active
                        ? "bg-gray-900 text-white"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex flex-col gap-2 sm:items-end">
            <StorePicker />

            {/* Small debug line; remove later if you want. */}
            <div className="text-xs text-gray-500">
              {storeId ? `store_id: ${storeId}` : "Select a store"}
              {cameraId ? ` • camera_id: ${cameraId}` : ""}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
