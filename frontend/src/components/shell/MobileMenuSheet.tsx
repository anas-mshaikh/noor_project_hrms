"use client";

/**
 * components/shell/MobileMenuSheet.tsx
 *
 * Mobile navigation sheet:
 * - Module switcher
 * - Active module nav items
 * - Context picker (Tenant/Company/Branch/Camera)
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "@/lib/i18n";

import { MODULES, getActiveModule, isNavItemActive } from "@/config/navigation";
import { StorePicker } from "@/components/StorePicker";
import { useLocale } from "@/lib/useLocale";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type MobileMenuSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function MobileMenuSheet({ open, onOpenChange }: MobileMenuSheetProps) {
  const { t } = useTranslation();
  const { isRtl } = useLocale();
  const pathname = usePathname();
  const activeModule = getActiveModule(pathname);

  const showDebugIds =
    process.env.NEXT_PUBLIC_SHOW_DEBUG_IDS === "true" ||
    process.env.NODE_ENV === "development";

  const branchId = useSelection((s) => s.branchId);
  const cameraId = useSelection((s) => s.cameraId);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isRtl ? "right" : "left"}
        className={cn(
          "bg-white/[0.04] backdrop-blur-xl",
          isRtl ? "border-l border-white/10" : "border-r border-white/10",
          "text-foreground"
        )}
      >
        <SheetHeader className="gap-2">
          <SheetTitle className="text-base tracking-tight">
            {t("shell.menu", { defaultValue: "Menu" })}
          </SheetTitle>
          <div className="text-xs text-muted-foreground">
            {t("shell.menu_switch_modules", {
              defaultValue: "Switch modules and navigate.",
            })}
          </div>
        </SheetHeader>

        {/* Modules */}
        <div className="px-4">
          <div className="mb-2 text-xs font-medium text-muted-foreground">
            {t("shell.modules", { defaultValue: "Modules" })}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {MODULES.map((m) => {
              const active = m.id === activeModule.id;
              const Icon = m.icon;
              return (
                <SheetClose key={m.id} asChild>
                  <Button
                    asChild
                    variant="ghost"
                    className={cn(
                      "h-auto items-start justify-start gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-start",
                      "hover:bg-white/[0.06]",
                      active &&
                        "border-violet-500/25 bg-gradient-to-r from-violet-500/15 to-fuchsia-500/10 shadow-[0_0_0_1px_rgba(168,85,247,0.16),0_12px_30px_-18px_rgba(168,85,247,0.55)]"
                    )}
                  >
                    <Link
                      href={m.href}
                      aria-label={t("shell.go_module_home", { defaultValue: "Go to module home" })}
                    >
                      <Icon className="mt-0.5 h-4 w-4 text-muted-foreground" />
                      <div className="text-xs font-medium">
                        {t(`nav.modules.${m.id}`, { defaultValue: m.label })}
                      </div>
                    </Link>
                  </Button>
                </SheetClose>
              );
            })}
          </div>
        </div>

        {/* Active module navigation */}
        <div className="mt-4 px-2">
          <div className="mb-2 px-2 text-xs font-medium text-muted-foreground">
            {t(`nav.modules.${activeModule.id}`, { defaultValue: activeModule.label })}
          </div>
          <div className="grid gap-1">
            {activeModule.sidebar.map((item) => {
              const active = isNavItemActive(item, pathname);
              const Icon = item.icon;
              return (
                <SheetClose key={item.id} asChild>
                  <Button
                    asChild
                    variant="ghost"
                    className={cn(
                      "h-auto w-full justify-start gap-3 rounded-2xl px-3 py-2 text-start",
                      "hover:bg-white/[0.06]",
                      active &&
                        "bg-white/[0.07] shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_12px_30px_-18px_rgba(0,0,0,0.55)]"
                    )}
                  >
                    <Link href={item.href}>
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {t(`nav.items.${item.id}.title`, { defaultValue: item.title })}
                        </div>
                        {item.description ? (
                          <div className="truncate text-xs text-muted-foreground">
                            {t(`nav.items.${item.id}.description`, {
                              defaultValue: item.description,
                            })}
                          </div>
                        ) : null}
                      </div>
                    </Link>
                  </Button>
                </SheetClose>
              );
            })}
          </div>
        </div>

        {/* Context */}
        <div className="mt-auto border-t border-white/10 p-4">
          <div className="text-xs font-medium text-muted-foreground">
            {t("shell.context", { defaultValue: "Context" })}
          </div>
          <div className="mt-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <StorePicker />
            {showDebugIds ? (
              <div className="mt-2 text-[11px] text-muted-foreground">
                {branchId
                  ? `branch_id: ${branchId}`
                  : t("shell.select_branch", { defaultValue: "Select a branch" })}
                {cameraId ? ` • camera_id: ${cameraId}` : ""}
              </div>
            ) : null}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
