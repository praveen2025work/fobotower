// The app shell — aria-ai's Layout (Barclays navy collapsible sidebar, top bar, error
// boundary per page), wired to Agent One Finance: navigation for the unified case view,
// the signed-in user from the Agent One Finance API, and the dev user switcher only when
// Agent One Finance runs on fixture entitlements. The sun / moon button switches between
// the Barclays light and dark themes (src/theme.ts).

import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";
import {
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Cable,
  Gauge,
  Inbox,
  LayoutDashboard,
  Layers,
  Menu,
  MoreHorizontal,
  Moon,
  ScrollText,
  Sun,
  Wand2,
  type LucideIcon,
  Presentation,
} from "lucide-react";

import { currentUser, setCurrentUser } from "../api/client";
import { useDevUsers, useInbox, useMe, usePlatform } from "../api/aof";
import { useTheme } from "../theme";
import ErrorBoundary from "./ErrorBoundary";
import NotificationBell from "./NotificationBell";

interface NavItem {
  readonly to: string;
  readonly icon: LucideIcon;
  readonly label: string;
  readonly badge?: number;
}

/** "Frank (FOBO controller, all books; owner)" -> name "Frank", role "FOBO controller", the rest as description. */
function splitName(full: string): { name: string; role: string | null; description: string | null } {
  const m = full.match(/^([^(]+?)\s*\((.*)\)\s*$/);
  if (!m) return { name: full, role: null, description: null };
  return { name: m[1], role: m[2].split(/[,;—]/)[0].trim() || null, description: m[2] };
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

// The sidebar starts collapsed (icons only); a person's choice is remembered.
const COLLAPSED_KEY = "aof.nav.collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) !== "0";
  } catch {
    return true;
  }
}

function Layout({ onUserChange }: { onUserChange: (user: string) => void }) {
  const [collapsed, setCollapsedState] = useState(() => readCollapsed());
  const setCollapsed = (v: boolean) => {
    setCollapsedState(v);
    try {
      localStorage.setItem(COLLAPSED_KEY, v ? "1" : "0");
    } catch {
      /* storage unavailable: the choice lasts for this visit */
    }
  };
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const user = currentUser();
  const me = useMe(user);
  const devUsers = useDevUsers();
  const inbox = useInbox();
  const platform = usePlatform();
  const [theme, setTheme] = useTheme();

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (userMenu && menuRef.current && !menuRef.current.contains(e.target as Node)) setUserMenu(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [userMenu]);

  const sections: { title: string; items: NavItem[] }[] = [
    {
      title: "Work",
      items: [
        { to: "/", icon: LayoutDashboard, label: "Overview" },
        { to: "/inbox", icon: Inbox, label: "Inbox", badge: inbox.data?.length || undefined },
        { to: "/capabilities", icon: Layers, label: "Capabilities" },
      ],
    },
    {
      title: "Platform",
      items: [
        { to: "/operations", icon: Gauge, label: "Operations" },
        { to: "/authoring", icon: Wand2, label: "Authoring" },
        { to: "/audit", icon: ScrollText, label: "Audit" },
        { to: "/connectors", icon: Cable, label: "Connectors" },
      ],
    },
  ];
  // Collapsing is for the desktop sidebar; the phone menu always shows labels.
  const compact = collapsed && !mobileOpen;
  const fixtures = devUsers.data ?? [];
  const meName = fixtures.find((u) => u.user_id === user)?.name ?? user ?? "Not signed in";
  const who = splitName(meName);

  return (
    <div className="flex h-screen overflow-hidden bg-surface-50">
      {mobileOpen && <div className="fixed inset-0 z-20 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-30 flex flex-col bg-nav-bg text-white transition-all duration-300 lg:static lg:translate-x-0",
          collapsed ? "lg:w-16" : "lg:w-60",
          mobileOpen ? "w-60 translate-x-0" : "-translate-x-full",
        )}
      >
        <div className={clsx("flex h-14 items-center border-b border-nav-line", compact ? "justify-center px-2" : "px-4")}>
          <div className="flex items-center gap-2.5">
            <div className="hx-mark flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-nav-bg">A1</div>
            {!compact && (
              <div>
                <h1 className="text-base font-bold leading-none tracking-tight">Agent One Finance</h1>
                <p className="mt-0.5 text-[10px] leading-none text-nav-muted">Governed AI, case by case</p>
              </div>
            )}
          </div>
        </div>

        <nav className="scrollbar-hide flex-1 overflow-y-auto py-2" aria-label="Main">
          {sections.map((section) => (
            <div key={section.title} className="mb-1">
              {!compact ? (
                <p className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-nav-muted">{section.title}</p>
              ) : (
                <div className="mx-3 my-2 border-t border-nav-line" />
              )}
              <div className="space-y-0.5 px-2">
                {section.items.map(({ to, icon: Icon, label, badge }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/"}
                    title={compact ? label : undefined}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      clsx(
                        "relative flex items-center rounded-lg transition-colors",
                        compact ? "justify-center p-2.5" : "gap-2.5 px-3 py-2 text-sm font-medium",
                        isActive ? "bg-nav-active text-nav-active-fg" : "text-nav-fg hover:bg-nav-hover hover:text-white",
                      )
                    }
                  >
                    <Icon size={compact ? 18 : 16} />
                    {!compact && <span>{label}</span>}
                    {!compact && badge ? (
                      <span className="ml-auto rounded-full bg-nav-mark px-1.5 py-0.5 text-[9px] font-bold text-nav-bg">{badge}</span>
                    ) : null}
                    {compact && badge ? <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-nav-mark" /> : null}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
          {/* The pitch page: a static page in public/pitch, opened beside the console. */}
          <div className="px-3 pt-2">
            <a
              href="/pitch/"
              target="_blank"
              rel="noreferrer"
              title={compact ? "About Agent One Finance" : undefined}
              className={clsx(
                "flex items-center rounded-lg text-nav-fg transition-colors hover:bg-nav-hover hover:text-white",
                compact ? "justify-center p-2.5" : "gap-2.5 px-3 py-2 text-sm font-medium",
              )}
            >
              <Presentation size={compact ? 18 : 16} />
              {!compact && <span>About Agent One Finance</span>}
            </a>
          </div>
        </nav>

        <div className="hidden border-t border-nav-line lg:block">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={clsx(
              "flex w-full items-center gap-2 py-3 text-xs text-nav-muted transition-colors hover:bg-nav-hover hover:text-white",
              collapsed ? "justify-center px-2" : "px-4",
            )}
          >
            {collapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span>Collapse</span></>}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between gap-2 border-b border-surface-200 bg-card px-3 sm:px-4">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <button onClick={() => setMobileOpen(true)} className="rounded-lg p-2 hover:bg-surface-100 lg:hidden" aria-label="Open menu">
              <Menu size={18} className="text-surface-500" />
            </button>
            <span className="flex items-center gap-1.5 lg:hidden">
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-nav-bg text-[11px] font-bold text-white">A1</span>
              <span className="text-sm font-bold text-surface-900">Agent One Finance</span>
            </span>
            {platform.data && me.data?.is_admin && (
              <span className="hidden text-xs text-surface-500 sm:inline">
                LLM <span className="font-medium text-surface-700">{platform.data.llm}</span> · Entitlement{" "}
                <span className="font-medium text-surface-700">{platform.data.entitlement}</span>
              </span>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            {me.data?.is_admin && (
              <span className="mr-1 hidden items-center gap-1.5 text-xs text-surface-500 sm:flex" title="Agent One Finance API">
                <Activity size={14} />
                API
                <span className={clsx("h-2 w-2 rounded-full", platform.isError ? "bg-red-400" : platform.data ? "bg-green-400" : "bg-surface-400")} />
              </span>
            )}
            <NotificationBell enabled={!!user} />
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="rounded-lg p-2 text-surface-500 transition-colors hover:bg-surface-100 hover:text-surface-700"
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title={theme === "dark" ? "Barclays light" : "Barclays dark"}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setUserMenu(!userMenu)}
                className="flex max-w-[13rem] items-center gap-2 rounded-lg py-1 pl-1 pr-2 transition-colors hover:bg-surface-100"
                aria-label="Signed-in user"
                aria-expanded={userMenu}
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
                  {initials(who.name)}
                </span>
                {/* Name and one short role; everything else is in the menu. Phones: initials only. */}
                <span className="hidden min-w-0 text-left leading-tight md:block">
                  <span className="block truncate text-sm font-medium text-surface-800">{who.name}</span>
                  {who.role && <span className="block truncate text-[11px] text-surface-500">{who.role}</span>}
                </span>
                <ChevronDown size={14} className="shrink-0 text-surface-400" />
              </button>
              {userMenu && (
                <div className="absolute right-0 top-full z-50 mt-1 w-80 max-w-[calc(100vw-1.5rem)] rounded-lg border border-surface-200 bg-card shadow-lg">
                  <div className="border-b border-surface-100 px-3 py-2.5">
                    <p className="text-sm font-semibold text-surface-900">{who.name}</p>
                    {who.description && <p className="text-xs text-surface-500">{who.description}</p>}
                    {me.data && me.data.roles.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {me.data.roles.map((r) => (
                          <span key={r} className="rounded bg-surface-100 px-1.5 py-0.5 text-[10px] font-medium text-surface-600">{r}</span>
                        ))}
                      </div>
                    )}
                    {me.data && Object.keys(me.data.data_scopes).length > 0 && (
                      <p className="mt-1.5 text-[11px] text-surface-500">
                        Data: {Object.entries(me.data.data_scopes).map(([k, v]) => `${k} ${v.includes("*") ? "all" : v.join(", ")}`).join(" · ")}
                      </p>
                    )}
                    {!!me.data?.covering_for?.length && (
                      <p className="mt-1 text-[11px] font-medium text-accent-700">Covering for {me.data.covering_for.join(", ")}</p>
                    )}
                  </div>
                  {fixtures.length > 0 && (
                    <div className="max-h-[50vh] overflow-y-auto py-1">
                      <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-surface-400">Switch user (development)</p>
                      {fixtures.map((u) => (
                        <button
                          key={u.user_id}
                          onClick={() => {
                            setCurrentUser(u.user_id);
                            setUserMenu(false);
                            onUserChange(u.user_id);
                          }}
                          className={clsx(
                            "flex w-full items-start gap-2 px-3 py-1.5 text-left text-sm hover:bg-surface-50",
                            user === u.user_id && "bg-primary-50 font-medium text-primary-700",
                          )}
                        >
                          <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", user === u.user_id ? "bg-primary-500" : "bg-surface-300")} />
                          <span className="min-w-0">
                            <span className="block">{splitName(u.name ?? u.user_id).name}</span>
                            <span className="block truncate text-[10px] text-surface-400">{splitName(u.name ?? u.user_id).description || u.roles.join(", ") || "no roles"}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="scrollbar-hide min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-3 pb-24 sm:p-4 sm:pb-24 lg:p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>

      {/* Phones: the main places one tap away, at the thumb; the rest under "More". */}
      <nav
        aria-label="Quick"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-surface-200 bg-card pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        {[sections[0].items[0], sections[0].items[1], sections[0].items[2], sections[1].items[0]].map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx("relative flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium", isActive ? "text-primary-700" : "text-surface-500")
            }
          >
            <Icon size={20} />
            {label}
            {badge ? (
              <span className="absolute right-[22%] top-1 min-w-[1.1rem] rounded-full bg-nav-mark px-1 text-center text-[9px] font-bold leading-4 text-nav-bg">{badge}</span>
            ) : null}
          </NavLink>
        ))}
        <button onClick={() => setMobileOpen(true)} className="flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium text-surface-500">
          <MoreHorizontal size={20} />
          More
        </button>
      </nav>
    </div>
  );
}

export default Layout;
