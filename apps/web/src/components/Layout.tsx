// The app shell — aria-ai's Layout (Barclays navy collapsible sidebar, top bar, error
// boundary per page), wired to Helix: navigation for the unified case view,
// the signed-in user from the Helix API, and the dev user switcher only when
// Helix runs on fixture entitlements. The sun / moon button switches between
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
  User,
  Wand2,
  type LucideIcon,
} from "lucide-react";

import { currentUser, setCurrentUser } from "../api/client";
import { useDevUsers, useInbox, useMe, usePlatform } from "../api/helix";
import { useTheme } from "../theme";
import ErrorBoundary from "./ErrorBoundary";
import NotificationBell from "./NotificationBell";

interface NavItem {
  readonly to: string;
  readonly icon: LucideIcon;
  readonly label: string;
  readonly badge?: number;
}

// The sidebar starts collapsed (icons only); a person's choice is remembered.
const COLLAPSED_KEY = "helix.nav.collapsed";

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
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-nav-mark font-bold text-nav-bg">H</div>
            {!compact && (
              <div>
                <h1 className="text-base font-bold leading-none tracking-tight">Helix</h1>
                <p className="mt-0.5 text-[10px] leading-none text-nav-muted">Capabilities, governed</p>
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
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-nav-bg text-xs font-bold text-white">H</span>
              <span className="text-sm font-bold text-surface-900">Helix</span>
            </span>
            {platform.data && me.data?.is_admin && (
              <span className="hidden text-xs text-surface-500 sm:inline">
                LLM <span className="font-medium text-surface-700">{platform.data.llm}</span> · Entitlement{" "}
                <span className="font-medium text-surface-700">{platform.data.entitlement}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3">
            <div className="hidden items-center gap-1.5 text-xs text-surface-500 sm:flex">
              <Activity size={14} />
              <span>API</span>
              <span className={clsx("h-2 w-2 rounded-full", platform.isError ? "bg-red-400" : platform.data ? "bg-green-400" : "bg-surface-400")} />
            </div>
            <div className="hidden h-5 w-px bg-surface-200 sm:block" />
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
                onClick={() => fixtures.length > 0 && setUserMenu(!userMenu)}
                className="flex items-center gap-2 rounded-lg bg-surface-50 px-2.5 py-1.5 transition-colors hover:bg-surface-100"
                aria-label="Signed-in user"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                  <User size={12} />
                </div>
                {/* Phones show the avatar only; the menu still names who is signed in. */}
                <div className="hidden text-left text-xs md:block">
                  <span className="font-medium text-surface-700">{meName}</span>
                  {me.data && me.data.roles.length > 0 && (
                    <span className="ml-1.5 hidden rounded xl:inline bg-surface-200 px-1 py-0.5 text-[10px] text-surface-500">{me.data.roles.join(", ")}</span>
                  )}
                </div>
                {fixtures.length > 0 && <ChevronDown size={12} className="text-surface-400" />}
              </button>
              {userMenu && (
                <div className="absolute right-0 top-full z-50 mt-1 w-72 rounded-lg border border-surface-200 bg-card py-1 shadow-lg">
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-surface-400">Switch user (development)</p>
                  <p className="px-3 pb-1.5 text-xs text-surface-700 md:hidden">Signed in as {meName}</p>
                  {fixtures.map((u) => (
                    <button
                      key={u.user_id}
                      onClick={() => {
                        setCurrentUser(u.user_id);
                        setUserMenu(false);
                        onUserChange(u.user_id);
                      }}
                      className={clsx(
                        "flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-surface-50",
                        user === u.user_id && "bg-primary-50 font-medium text-primary-700",
                      )}
                    >
                      <span className={clsx("mt-1.5 h-2 w-2 rounded-full", user === u.user_id ? "bg-primary-500" : "bg-surface-300")} />
                      <span>
                        <span className="block">{u.name ?? u.user_id}</span>
                        <span className="block text-[10px] text-surface-400">{u.roles.join(", ") || "no roles"}</span>
                      </span>
                    </button>
                  ))}
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
