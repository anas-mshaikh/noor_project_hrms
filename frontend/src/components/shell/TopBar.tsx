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
import { toast } from "sonner";
import { Bell, CircleHelp, Menu, UserCircle2 } from "lucide-react";

import { MODULES, getActiveModule } from "@/config/navigation";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { MobileMenuSheet } from "@/components/shell/MobileMenuSheet";

function ModuleTabs({ pathname }: { pathname: string }) {
  const activeModule = getActiveModule(pathname);

  return (
    <div
      className={cn(
        "hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 backdrop-blur-xl md:flex"
      )}
      role="tablist"
      aria-label="Modules"
    >
      {MODULES.map((m) => {
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
            {m.label}
          </Link>
        );
      })}
    </div>
  );
}

function TopBarIconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label={label}
          onClick={onClick}
          className={cn(
            "h-10 w-10 rounded-2xl border border-white/10 bg-white/[0.03] text-muted-foreground",
            "hover:bg-white/[0.06] hover:text-foreground",
            "focus-visible:ring-2 focus-visible:ring-violet-500/40 focus-visible:ring-offset-0"
          )}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        sideOffset={10}
        className="rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-foreground shadow-lg backdrop-blur-xl"
      >
        <div className="text-xs font-medium">{label}</div>
      </TooltipContent>
    </Tooltip>
  );
}

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const activeModule = getActiveModule(pathname);

  const [mobileOpen, setMobileOpen] = useState(false);

  const accessToken = useAuth((s) => s.accessToken);
  const refreshToken = useAuth((s) => s.refreshToken);
  const userEmail = useAuth((s) => s.user?.email);
  const clearAuth = useAuth((s) => s.clear);
  const resetSelection = useSelection((s) => s.reset);

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-white/[0.03] backdrop-blur-xl">
      <MobileMenuSheet open={mobileOpen} onOpenChange={setMobileOpen} />

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
          aria-label="Open menu"
          onClick={() => setMobileOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Logo */}
        <Link
          href={activeModule.href}
          className="flex items-center gap-2 font-semibold tracking-tight"
          aria-label="Go to module home"
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 to-fuchsia-500/20 ring-1 ring-white/10">
            <activeModule.icon className="h-4 w-4 text-foreground" />
          </span>
          <span className="hidden sm:inline">Attendance Admin</span>
        </Link>

        {/* Modules (desktop) */}
        <div className="ml-2">
          <ModuleTabs pathname={pathname} />
        </div>

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-2">
          <TopBarIconButton
            label="Notifications"
            onClick={() =>
              toast("Coming soon", {
                description: accessToken
                  ? "Notifications panel"
                  : "Sign in to view notifications",
              })
            }
          >
            <Bell className="h-5 w-5" />
          </TopBarIconButton>

          <TopBarIconButton
            label="Help"
            onClick={() => toast("Coming soon", { description: "Help & shortcuts" })}
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
                    <div className="text-xs text-muted-foreground">Signed in as</div>
                    <div className="truncate">{userEmail}</div>
                  </div>
                ) : (
                  "Account"
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                onSelect={(e) => {
                  e.preventDefault();
                  toast("Coming soon", { description: "Profile page" });
                }}
              >
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/settings">Settings</Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-white/10" />
              {accessToken ? (
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={(e) => {
                    e.preventDefault();
                    // Best-effort: clear local session. (Backend refresh token revocation can be added later.)
                    void refreshToken;
                    clearAuth();
                    resetSelection();
                    router.push("/login");
                    toast("Signed out");
                  }}
                >
                  Sign out
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem asChild>
                  <Link href="/login">Sign in</Link>
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
