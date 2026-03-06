import type { LucideIcon } from "lucide-react";
import {
  AtSign,
  BadgeCheck,
  Briefcase,
  Calendar,
  CheckSquare,
  FileUp,
  Inbox,
  LayoutDashboard,
  LayoutGrid,
  Library,
  ListTodo,
  MessageCircle,
  NotebookPen,
  Plug,
  Settings,
  Shield,
  SlidersHorizontal,
  Sparkles,
  StickyNote,
  UserPlus,
  Users,
  Video,
  Zap,
} from "lucide-react";

export type ModuleId =
  | "attendance"
  | "hr"
  | "ess"
  | "mss"
  | "tasks"
  | "inbox"
  | "notes"
  | "settings";

export type MatchMode = "exact" | "prefix";

export type NavItem = {
  id: string;
  href: string;
  title: string;
  description?: string;
  icon: LucideIcon;
  match?: MatchMode;
  // Permission gating (frontend convenience only; backend remains the source of truth).
  requiredPermissions?: string[];
  // Hide items that are placeholders / not part of Client V0 navigation.
  v0Hidden?: boolean;
};

export type ModuleDef = {
  id: ModuleId;
  label: string;
  href: string;
  icon: LucideIcon;
  isActive: (pathname: string) => boolean;
  sidebar: NavItem[];
  requiredPermissions?: string[];
  v0Hidden?: boolean;
};

function startsWithPath(pathname: string, base: string): boolean {
  return pathname === base || pathname.startsWith(`${base}/`);
}

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  // Keep UX parity with the old shell: Jobs/Reports are part of "Videos".
  if (item.href === "/videos") {
    return (
      startsWithPath(pathname, "/videos") ||
      startsWithPath(pathname, "/jobs") ||
      startsWithPath(pathname, "/reports")
    );
  }

  // Calibration lives under /cameras/* but conceptually belongs to Setup.
  if (item.href === "/setup") {
    return startsWithPath(pathname, "/setup") || startsWithPath(pathname, "/cameras");
  }

  const matchMode: MatchMode = item.match ?? "exact";
  return matchMode === "prefix"
    ? startsWithPath(pathname, item.href)
    : pathname === item.href;
}

const attendanceModule: ModuleDef = {
  id: "attendance",
  label: "Attendance",
  href: "/dashboard",
  icon: LayoutDashboard,
  isActive: (pathname) =>
    !(
      startsWithPath(pathname, "/attendance") ||
      startsWithPath(pathname, "/leave") ||
      startsWithPath(pathname, "/hr") ||
      startsWithPath(pathname, "/ess") ||
      startsWithPath(pathname, "/mss") ||
      startsWithPath(pathname, "/workflow") ||
      startsWithPath(pathname, "/tasks") ||
      startsWithPath(pathname, "/inbox") ||
      startsWithPath(pathname, "/notes") ||
      startsWithPath(pathname, "/settings")
    ),
  sidebar: [
    {
      id: "dashboard",
      href: "/dashboard",
      title: "Dashboard",
      description: "High-level attendance metrics",
      icon: LayoutDashboard,
      match: "exact",
      requiredPermissions: ["vision:results:read"],
    },
    {
      id: "setup",
      href: "/setup",
      title: "Setup",
      description: "Tenancy, branches, cameras",
      icon: Settings,
      match: "exact",
      requiredPermissions: ["vision:camera:write", "tenancy:write"],
    },
    {
      id: "employees",
      href: "/employees",
      title: "Employees",
      description: "Roster and face enrollment",
      icon: Users,
      match: "exact",
      requiredPermissions: ["hr:employee:read"],
    },
    {
      id: "videos",
      href: "/videos",
      title: "Videos",
      description: "Uploads and processing",
      icon: Video,
      match: "exact",
      requiredPermissions: ["vision:video:upload", "vision:job:run", "vision:results:read"],
    },
    {
      id: "admin-import",
      href: "/admin/import",
      title: "Admin Import",
      description: "Upload monthly excel",
      icon: FileUp,
      match: "exact",
      requiredPermissions: ["imports:write"],
    },
  ],
};

const hrModule: ModuleDef = {
  id: "hr",
  label: "HR",
  href: "/hr",
  icon: Sparkles,
  isActive: (pathname) => startsWithPath(pathname, "/hr"),
  sidebar: [
    {
      id: "hr-overview",
      href: "/hr",
      title: "HR Overview",
      description: "Hiring performance and tasks",
      icon: Sparkles,
      match: "exact",
      requiredPermissions: ["hr:recruiting:read"],
    },
    {
      id: "hr-openings",
      href: "/hr/openings",
      title: "Openings",
      description: "Job openings and JDs",
      icon: Briefcase,
      match: "prefix",
      requiredPermissions: ["hr:recruiting:read"],
    },
    {
      id: "hr-runs",
      href: "/hr/runs",
      title: "Runs",
      description: "Screening runs and results",
      icon: Zap,
      match: "prefix",
      requiredPermissions: ["hr:recruiting:read"],
    },
    {
      id: "hr-pipeline",
      href: "/hr/pipeline",
      title: "Pipeline",
      description: "Stages and movements",
      icon: LayoutGrid,
      match: "exact",
      requiredPermissions: ["hr:recruiting:read"],
    },
    {
      id: "hr-employees",
      href: "/hr/employees",
      title: "Employees",
      description: "Employee directory and profiles",
      icon: Users,
      match: "prefix",
      requiredPermissions: ["hr:employee:read"],
    },
    {
      id: "hr-onboarding",
      href: "/hr/onboarding",
      title: "Onboarding",
      description: "New hires checklist",
      icon: UserPlus,
      match: "prefix",
      v0Hidden: true,
    },
  ],
};

const essModule: ModuleDef = {
  id: "ess",
  label: "Self Service",
  href: "/attendance/punch",
  icon: Users,
  isActive: (pathname) =>
    // ESS owns self-service attendance + leave routes.
    // Team calendar is a manager view and is highlighted under MSS instead.
    (startsWithPath(pathname, "/ess") ||
      startsWithPath(pathname, "/attendance") ||
      startsWithPath(pathname, "/leave")) &&
    !startsWithPath(pathname, "/leave/team-calendar"),
  requiredPermissions: [
    "ess:profile:read",
    "attendance:punch:read",
    "attendance:correction:read",
    "leave:balance:read",
    "leave:request:read",
  ],
  sidebar: [
    {
      id: "ess-attendance-punch",
      href: "/attendance/punch",
      title: "Punch",
      description: "Punch in and out",
      icon: LayoutDashboard,
      match: "exact",
      requiredPermissions: ["attendance:punch:read"],
    },
    {
      id: "ess-attendance-days",
      href: "/attendance/days",
      title: "Days",
      description: "Daily status and minutes",
      icon: LayoutGrid,
      match: "exact",
      requiredPermissions: ["attendance:correction:read"],
    },
    {
      id: "ess-attendance-corrections",
      href: "/attendance/corrections",
      title: "My Corrections",
      description: "Submitted attendance corrections",
      icon: MessageCircle,
      match: "prefix",
      requiredPermissions: ["attendance:correction:read"],
    },
    {
      id: "ess-leave",
      href: "/leave",
      title: "Leave",
      description: "Balances and requests",
      icon: Calendar,
      match: "prefix",
      requiredPermissions: ["leave:balance:read", "leave:request:read"],
    },
    {
      id: "ess-me",
      href: "/ess/me",
      title: "My Profile",
      description: "Your employee profile",
      icon: Users,
      match: "exact",
      requiredPermissions: ["ess:profile:read"],
    },
  ],
};

const mssModule: ModuleDef = {
  id: "mss",
  label: "My Team",
  href: "/mss/team",
  icon: Users,
  isActive: (pathname) =>
    startsWithPath(pathname, "/mss") || startsWithPath(pathname, "/leave/team-calendar"),
  requiredPermissions: ["hr:team:read", "leave:team:read"],
  sidebar: [
    {
      id: "mss-team",
      href: "/mss/team",
      title: "My Team",
      description: "Direct and indirect reports",
      icon: Users,
      match: "prefix",
      requiredPermissions: ["hr:team:read"],
    },
    {
      id: "mss-leave-team-calendar",
      href: "/leave/team-calendar",
      title: "Team Calendar",
      description: "Approved leave spans",
      icon: Calendar,
      match: "prefix",
      requiredPermissions: ["leave:team:read"],
    },
  ],
};

const tasksModule: ModuleDef = {
  id: "tasks",
  label: "Tasks",
  href: "/tasks",
  icon: CheckSquare,
  isActive: (pathname) => startsWithPath(pathname, "/tasks"),
  v0Hidden: true,
  sidebar: [
    {
      id: "tasks-my",
      href: "/tasks",
      title: "My Tasks",
      description: "Assigned to you",
      icon: ListTodo,
      match: "exact",
    },
    {
      id: "tasks-team",
      href: "/tasks/team",
      title: "Team Queue",
      description: "All pending tasks",
      icon: CheckSquare,
      match: "prefix",
    },
    {
      id: "tasks-approvals",
      href: "/tasks/approvals",
      title: "Approvals",
      description: "Review and sign off",
      icon: BadgeCheck,
      match: "prefix",
    },
  ],
};

const inboxModule: ModuleDef = {
  id: "inbox",
  label: "Workflow",
  href: "/workflow/inbox",
  icon: Inbox,
  isActive: (pathname) =>
    startsWithPath(pathname, "/workflow") || startsWithPath(pathname, "/inbox"),
  requiredPermissions: ["workflow:request:read", "workflow:request:admin"],
  sidebar: [
    {
      id: "workflow-inbox",
      href: "/workflow/inbox",
      title: "Inbox",
      description: "Requests assigned to you",
      icon: Inbox,
      match: "prefix",
      requiredPermissions: ["workflow:request:read", "workflow:request:admin"],
    },
    {
      id: "workflow-outbox",
      href: "/workflow/outbox",
      title: "Outbox",
      description: "Requests you created",
      icon: MessageCircle,
      match: "prefix",
      requiredPermissions: ["workflow:request:read", "workflow:request:admin"],
    },
    {
      id: "inbox-all",
      href: "/inbox",
      title: "All Messages",
      description: "Team and system threads",
      icon: Inbox,
      match: "exact",
      v0Hidden: true,
    },
    {
      id: "inbox-groups",
      href: "/inbox/groups",
      title: "Groups",
      description: "Channels & groups",
      icon: MessageCircle,
      match: "prefix",
      v0Hidden: true,
    },
    {
      id: "inbox-mentions",
      href: "/inbox/mentions",
      title: "Mentions",
      description: "Where you were tagged",
      icon: AtSign,
      match: "prefix",
      v0Hidden: true,
    },
  ],
};

const notesModule: ModuleDef = {
  id: "notes",
  label: "Notes",
  href: "/notes",
  icon: NotebookPen,
  isActive: (pathname) => startsWithPath(pathname, "/notes"),
  v0Hidden: true,
  sidebar: [
    {
      id: "notes-all",
      href: "/notes",
      title: "All Notes",
      description: "Your notes and docs",
      icon: StickyNote,
      match: "exact",
    },
    {
      id: "notes-templates",
      href: "/notes/templates",
      title: "Templates",
      description: "Reusable forms",
      icon: NotebookPen,
      match: "prefix",
    },
    {
      id: "notes-library",
      href: "/notes/library",
      title: "Library",
      description: "Policies & SOPs",
      icon: Library,
      match: "prefix",
    },
  ],
};

const settingsModule: ModuleDef = {
  id: "settings",
  label: "Settings",
  href: "/settings",
  icon: SlidersHorizontal,
  isActive: (pathname) => startsWithPath(pathname, "/settings"),
  sidebar: [
    {
      id: "settings-general",
      href: "/settings",
      title: "General",
      description: "Org preferences",
      icon: SlidersHorizontal,
      match: "exact",
    },
    {
      id: "settings-org",
      href: "/settings/org",
      title: "Organization",
      description: "Company profile",
      icon: Settings,
      match: "prefix",
      requiredPermissions: ["tenancy:read", "tenancy:write"],
    },
    {
      id: "settings-access",
      href: "/settings/access",
      title: "Roles & Access",
      description: "Permissions",
      icon: Shield,
      match: "prefix",
      requiredPermissions: [
        "iam:user:read",
        "iam:user:write",
        "iam:role:assign",
        "iam:permission:read",
      ],
    },
    {
      id: "settings-integrations",
      href: "/settings/integrations",
      title: "Integrations",
      description: "External services",
      icon: Plug,
      match: "prefix",
      v0Hidden: true,
    },
    {
      id: "settings-workflow",
      href: "/settings/workflow",
      title: "Workflow",
      description: "Definitions and routing",
      icon: SlidersHorizontal,
      match: "prefix",
      requiredPermissions: ["workflow:definition:read", "workflow:definition:write"],
    },
  ],
};

export const MODULES: ModuleDef[] = [
  attendanceModule,
  hrModule,
  essModule,
  mssModule,
  tasksModule,
  inboxModule,
  notesModule,
  settingsModule,
];

function hasAnyPermission(
  required: string[] | undefined,
  permissions: Set<string>
): boolean {
  if (!required || required.length === 0) return true;
  return required.some((p) => permissions.has(p));
}

/**
 * Build a navigation view for the current user permissions.
 *
 * This is UI-only safety; backend `require_permission(...)` remains authoritative.
 */
export function buildNavForPermissions(permissionCodes: string[]): ModuleDef[] {
  const perms = new Set(permissionCodes);

  return MODULES.filter((m) => !m.v0Hidden)
    .map((m) => {
      const sidebar = m.sidebar.filter(
        (i) => !i.v0Hidden && hasAnyPermission(i.requiredPermissions, perms)
      );
      return { ...m, sidebar };
    })
    .filter((m) => hasAnyPermission(m.requiredPermissions, perms))
    .filter((m) => m.sidebar.length > 0);
}

export function getActiveModule(pathname: string): ModuleDef {
  // Prefer explicit modules, fall back to Attendance for everything else.
  return MODULES.find((m) => m.isActive(pathname)) ?? attendanceModule;
}

export function getActiveModuleFrom(modules: ModuleDef[], pathname: string): ModuleDef {
  return modules.find((m) => m.isActive(pathname)) ?? attendanceModule;
}
