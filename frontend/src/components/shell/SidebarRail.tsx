"use client";

/**
 * components/shell/SidebarRail.tsx
 *
 * Icon-only rail:
 * - Items depend on the active module.
 * - Vertically centered icons.
 * - Glass tooltip on hover (title + short description).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Building2 } from "lucide-react";

import { getActiveModule, isNavItemActive } from "@/config/navigation";
import { StorePicker } from "@/components/StorePicker";
import { useSelection } from "@/lib/selection";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export function SidebarRail() {
  const pathname = usePathname();
  const reducedMotion = useReducedMotion();
  const activeModule = getActiveModule(pathname);

  const showDebugIds =
    process.env.NEXT_PUBLIC_SHOW_DEBUG_IDS === "true" ||
    process.env.NODE_ENV === "development";

  const branchId = useSelection((s) => s.branchId);
  const cameraId = useSelection((s) => s.cameraId);

  return (
    <aside className="hidden w-[76px] shrink-0 border-r border-white/10 bg-white/[0.02] backdrop-blur-xl md:flex">
      <div className="flex h-full w-full flex-col">
        <div className="h-14" />

        {/* Centered module navigation */}
        <nav className="flex-1">
          <div className="flex h-full flex-col items-center justify-center gap-3">
            {activeModule.sidebar.map((item) => {
              const active = isNavItemActive(item, pathname);
              const Icon = item.icon;

              return (
                <Tooltip key={item.id}>
                  <TooltipTrigger asChild>
                    <motion.div
                      whileHover={
                        reducedMotion
                          ? { opacity: 1 }
                          : { y: -1, rotate: 0.8, scale: 1.02 }
                      }
                      transition={{ duration: 0.15 }}
                    >
                      <Button
                        asChild
                        size="icon"
                        variant="ghost"
                        className={cn(
                          "h-11 w-11 rounded-2xl border border-white/10 bg-white/[0.03]",
                          "text-muted-foreground shadow-sm",
                          "hover:bg-white/[0.06] hover:text-foreground",
                          "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0",
                          active &&
                            "bg-white/[0.08] text-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_10px_30px_-18px_rgba(168,85,247,0.55)]"
                        )}
                      >
                        <Link
                          href={item.href}
                          aria-label={item.description ? `${item.title}: ${item.description}` : item.title}
                        >
                          <Icon className="h-5 w-5" />
                        </Link>
                      </Button>
                    </motion.div>
                  </TooltipTrigger>

                  <TooltipContent
                    side="right"
                    sideOffset={10}
                    className={cn(
                      "w-64 rounded-xl border border-white/10 bg-white/[0.06] p-3 text-foreground shadow-lg backdrop-blur-xl"
                    )}
                  >
                    <div className="text-sm font-semibold leading-tight">
                      {item.title}
                    </div>
                    {item.description ? (
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {item.description}
                      </div>
                    ) : null}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </nav>

        {/* Context picker shortcut (optional but important for this app). */}
        <div className="flex items-center justify-center p-3">
          <Sheet>
            <SheetTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                className={cn(
                  "h-11 w-11 rounded-2xl border border-white/10 bg-white/[0.03] text-muted-foreground",
                  "hover:bg-white/[0.06] hover:text-foreground",
                  "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0"
                )}
                aria-label="Open context picker"
              >
                <Building2 className="h-5 w-5" />
              </Button>
            </SheetTrigger>

            <SheetContent
              side="left"
              className={cn(
                "w-full max-w-md border-r border-white/10 bg-white/[0.04] backdrop-blur-xl",
                "text-foreground"
              )}
            >
              <SheetHeader>
                <SheetTitle className="text-base tracking-tight">
                  Context
                </SheetTitle>
                <div className="text-xs text-muted-foreground">
                  Select tenant, company, branch, and camera.
                </div>
              </SheetHeader>
              <div className="px-4 pb-6">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                  <StorePicker />
                  {showDebugIds ? (
                    <div className="mt-2 text-[11px] text-muted-foreground">
                      {branchId ? `branch_id: ${branchId}` : "Select a branch"}
                      {cameraId ? ` • camera_id: ${cameraId}` : ""}
                    </div>
                  ) : null}
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </aside>
  );
}
