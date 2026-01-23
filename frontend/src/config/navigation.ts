import type { LucideIcon } from "lucide-react";
import {
  AtSign,
  BadgeCheck,
  Briefcase,
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
};

export type ModuleDef = {
  id: ModuleId;
  label: string;
  href: string;
  icon: LucideIcon;
  isActive: (pathname: string) => boolean;
  sidebar: NavItem[];
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
      startsWithPath(pathname, "/hr") ||
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
    },
    {
      id: "setup",
      href: "/setup",
      title: "Setup",
      description: "Orgs, stores, cameras",
      icon: Settings,
      match: "exact",
    },
    {
      id: "employees",
      href: "/employees",
      title: "Employees",
      description: "Roster and face enrollment",
      icon: Users,
      match: "exact",
    },
    {
      id: "videos",
      href: "/videos",
      title: "Videos",
      description: "Uploads and processing",
      icon: Video,
      match: "exact",
    },
    {
      id: "admin-import",
      href: "/admin/import",
      title: "Admin Import",
      description: "Upload monthly excel",
      icon: FileUp,
      match: "exact",
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
    },
    {
      id: "hr-openings",
      href: "/hr/openings",
      title: "Openings",
      description: "Job openings and JDs",
      icon: Briefcase,
      match: "prefix",
    },
    {
      id: "hr-runs",
      href: "/hr/runs",
      title: "Runs",
      description: "Screening runs and results",
      icon: Zap,
      match: "prefix",
    },
    {
      id: "hr-pipeline",
      href: "/hr/pipeline",
      title: "Pipeline",
      description: "Stages and movements",
      icon: LayoutGrid,
      match: "exact",
    },
    {
      id: "hr-onboarding",
      href: "/hr/onboarding",
      title: "Onboarding",
      description: "New hires checklist",
      icon: UserPlus,
      match: "prefix",
    },
  ],
};

const tasksModule: ModuleDef = {
  id: "tasks",
  label: "Tasks",
  href: "/tasks",
  icon: CheckSquare,
  isActive: (pathname) => startsWithPath(pathname, "/tasks"),
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
  label: "Inbox",
  href: "/inbox",
  icon: Inbox,
  isActive: (pathname) => startsWithPath(pathname, "/inbox"),
  sidebar: [
    {
      id: "inbox-all",
      href: "/inbox",
      title: "All Messages",
      description: "Team and system threads",
      icon: Inbox,
      match: "exact",
    },
    {
      id: "inbox-groups",
      href: "/inbox/groups",
      title: "Groups",
      description: "Channels & groups",
      icon: MessageCircle,
      match: "prefix",
    },
    {
      id: "inbox-mentions",
      href: "/inbox/mentions",
      title: "Mentions",
      description: "Where you were tagged",
      icon: AtSign,
      match: "prefix",
    },
  ],
};

const notesModule: ModuleDef = {
  id: "notes",
  label: "Notes",
  href: "/notes",
  icon: NotebookPen,
  isActive: (pathname) => startsWithPath(pathname, "/notes"),
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
    },
    {
      id: "settings-access",
      href: "/settings/access",
      title: "Roles & Access",
      description: "Permissions",
      icon: Shield,
      match: "prefix",
    },
    {
      id: "settings-integrations",
      href: "/settings/integrations",
      title: "Integrations",
      description: "External services",
      icon: Plug,
      match: "prefix",
    },
  ],
};

export const MODULES: ModuleDef[] = [
  attendanceModule,
  hrModule,
  tasksModule,
  inboxModule,
  notesModule,
  settingsModule,
];

export function getActiveModule(pathname: string): ModuleDef {
  // Prefer explicit modules, fall back to Attendance for everything else.
  return MODULES.find((m) => m.isActive(pathname)) ?? attendanceModule;
}

