"use client";

/**
 * components/shell/TopBar.tsx
 *
 * Global top bar:
 * - Logo (left)
 * - Module tabs (center, desktop)
 * - Actions (right): notifications, help, profile
 * - Mobile: single menu button opens a Sheet (see MobileMenuSheet)
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "@/lib/i18n";
import { toast } from "sonner";
import { Bell, CircleHelp, Menu, UserCircle2 } from "lucide-react";

import type { ModuleDef } from "@/config/navigation";
import { buildNavForPermissions, getActiveModuleFrom } from "@/config/navigation";
import { useAuth } from "@/lib/auth";
import { normalizeLocale } from "@/lib/locale";
import { useLocale } from "@/lib/useLocale";
import { useSelection } from "@/lib/selection";
import { apiJson } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { MobileMenuSheet } from "@/components/shell/MobileMenuSheet";

function ModuleTabs({ pathname, modules }: { pathname: string; modules: ModuleDef[] }) {
  const { t } = useTranslation();
  const activeModule = getActiveModuleFrom(modules, pathname);

  return (
    <div
      className={cn(
        "hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 backdrop-blur-xl md:flex"
      )}
      role="tablist"
      aria-label="Modules"
    >
      {modules.map((m) => {
        const active = m.id === activeModule.id;
        return (
          <Link
            key={m.id}
            href={m.href}
            role="tab"
            aria-selected={active}
            className={cn(
              "rounded-full px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors",
              "hover:bg-white/[0.06] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40",
              active &&
                "bg-gradient-to-r from-violet-500/20 to-fuchsia-500/15 text-foreground shadow-[0_0_0_1px_rgba(168,85,247,0.18),0_12px_30px_-18px_rgba(168,85,247,0.6)]"
            )}
          >
            {t(`nav.modules.${m.id}`, { defaultValue: m.label })}
          </Link>
        );
      })}
    </div>
  );
}

function TopBarIconButton({
  label,
  description,
  onClick,
  disabled,
  children,
}: {
  label: string;
  description?: string;
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {/* Radix tooltips won't trigger on disabled buttons; wrap in a span. */}
        <span className="inline-flex">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            aria-label={label}
            onClick={disabled ? undefined : onClick}
            disabled={disabled}
            className={cn(
              "h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] text-muted-foreground",
              "hover:bg-white/[0.06] hover:text-foreground",
              "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0"
            )}
          >
            {children}
          </Button>
        </span>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        sideOffset={10}
        className="rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-foreground shadow-lg backdrop-blur-xl"
      >
        <div className="text-xs font-medium">{label}</div>
        {description ? <div className="mt-1 text-xs text-text-2">{description}</div> : null}
      </TooltipContent>
    </Tooltip>
  );
}

export function TopBar() {
  const { t } = useTranslation();
  const { locale, setLocale } = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const permissions = useAuth((s) => s.permissions);
  const navModules = buildNavForPermissions(permissions);
  const activeModule = getActiveModuleFrom(navModules.length ? navModules : [], pathname);

  const [mobileOpen, setMobileOpen] = useState(false);

  const user = useAuth((s) => s.user);
  const userEmail = useAuth((s) => s.user?.email);
  const clearAuth = useAuth((s) => s.clear);
  const resetSelection = useSelection((s) => s.reset);

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-white/[0.03] backdrop-blur-xl">
      <MobileMenuSheet modules={navModules} open={mobileOpen} onOpenChange={setMobileOpen} />

      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 md:px-6">
        {/* Mobile menu */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className={cn(
            "md:hidden h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] text-muted-foreground",
            "hover:bg-white/[0.06] hover:text-foreground",
            "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0"
          )}
          aria-label={t("shell.open_menu", { defaultValue: "Open menu" })}
          onClick={() => setMobileOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Logo */}
        <Link
          href={activeModule.href}
          className="flex items-center gap-2 font-semibold tracking-tight"
          aria-label={t("shell.go_module_home", { defaultValue: "Go to module home" })}
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-fuchsia-500/20 ring-1 ring-white/10">
            <activeModule.icon className="h-4 w-4 text-foreground" />
          </span>
          <span className="hidden sm:inline">Noor Project</span>
        </Link>

        {/* Modules (desktop) */}
        <div className="ml-2">
          {navModules.length ? <ModuleTabs pathname={pathname} modules={navModules} /> : null}
        </div>

        {/* Right actions */}
        <div className="topbar-actions ml-auto flex items-center gap-2">
          <TopBarIconButton
            label={t("shell.notifications", { defaultValue: "Notifications" })}
            description={t("common.not_available_v0", { defaultValue: "Not available in Client V0" })}
            disabled
          >
            <Bell className="h-5 w-5" />
          </TopBarIconButton>

          <TopBarIconButton
            label={t("shell.help", { defaultValue: "Help" })}
            description={t("common.not_available_v0", { defaultValue: "Not available in Client V0" })}
            disabled
          >
            <CircleHelp className="h-5 w-5" />
          </TopBarIconButton>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="Open profile menu"
                className={cn(
                  "h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] text-muted-foreground",
                  "hover:bg-white/[0.06] hover:text-foreground",
                  "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0"
                )}
              >
                <UserCircle2 className="h-5 w-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56 border-white/10 bg-white/[0.06] text-foreground shadow-lg backdrop-blur-xl"
            >
              <DropdownMenuLabel>
                {userEmail ? (
                  <div className="truncate">
                    <div className="text-xs text-muted-foreground">
                      {t("shell.signed_in_as", { defaultValue: "Signed in as" })}
                    </div>
                    <div className="truncate">{userEmail}</div>
                  </div>
                ) : (
                  t("shell.account", { defaultValue: "Account" })
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  {t("language.label", { defaultValue: "Language" })}
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent className="border-white/10 bg-white/[0.06] text-foreground shadow-lg backdrop-blur-xl">
                  <DropdownMenuRadioGroup
                    value={locale}
                    onValueChange={(value) => {
                      void setLocale(normalizeLocale(value));
                    }}
                  >
                    <DropdownMenuRadioItem value="en">
                      {t("language.en", { defaultValue: "English" })}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="ar">
                      {t("language.ar", { defaultValue: "Arabic" })}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="de">
                      {t("language.de", { defaultValue: "German" })}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="fr">
                      {t("language.fr", { defaultValue: "French" })}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="es">
                      {t("language.es", { defaultValue: "Español" })}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                disabled
              >
                {t("shell.profile", { defaultValue: "Profile" })}
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/settings">
                  {t("shell.settings", { defaultValue: "Settings" })}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-white/10" />
              {user ? (
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={(e) => {
                    e.preventDefault();
                    void (async () => {
                      // Best-effort backend revocation; BFF will clear cookies too.
                      try {
                        await apiJson("/api/v1/auth/logout", { method: "POST" });
                      } catch {
                        // Ignore network errors on logout; we still clear local state.
                      } finally {
                        clearAuth();
                        resetSelection();
                        router.push("/login");
                        toast(t("shell.signed_out", { defaultValue: "Signed out" }));
                      }
                    })();
                  }}
                >
                  {t("common.sign_out", { defaultValue: "Sign out" })}
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem asChild>
                  <Link href="/login">
                    {t("common.sign_in", { defaultValue: "Sign in" })}
                  </Link>
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
