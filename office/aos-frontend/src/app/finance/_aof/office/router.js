// Generated from apps/web/office/templates/router.js by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
"use client";
// The few react-router pieces the console uses, on Next.js navigation, so the
// console's files are the same as upstream's. Paths in the console start at "/";
// in Agent One they live under FINANCE_BASE.

import NextLink from "next/link";
import { useParams as useNextParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, forwardRef, useContext } from "react";

export const FINANCE_BASE = "/finance";

const toHref = (to) => (to === "/" ? FINANCE_BASE : `${FINANCE_BASE}${to}`);

/** The path inside the console ("/cases/C1"), without FINANCE_BASE. */
function useConsolePath() {
  const path = usePathname() ?? "/";
  const rest = path.startsWith(FINANCE_BASE) ? path.slice(FINANCE_BASE.length) : path;
  return rest === "" ? "/" : rest;
}

export const Link = forwardRef(function Link({ to, replace, ...rest }, ref) {
  return <NextLink ref={ref} href={toHref(to)} replace={replace} {...rest} />;
});

export const NavLink = forwardRef(function NavLink({ to, end, className, style, children, ...rest }, ref) {
  const path = useConsolePath();
  const isActive = end || to === "/" ? path === to : path === to || path.startsWith(`${to}/`);
  const state = { isActive, isPending: false };
  return (
    <NextLink
      ref={ref}
      href={toHref(to)}
      aria-current={isActive ? "page" : undefined}
      className={typeof className === "function" ? className(state) : className}
      style={typeof style === "function" ? style(state) : style}
      {...rest}
    >
      {typeof children === "function" ? children(state) : children}
    </NextLink>
  );
});

export function useNavigate() {
  const router = useRouter();
  return (to, opts) => {
    if (typeof to === "number") return to < 0 ? router.back() : router.forward();
    return opts?.replace ? router.replace(toHref(to)) : router.push(toHref(to));
  };
}

export function useParams() {
  const raw = useNextParams() ?? {};
  const out = {};
  for (const [k, v] of Object.entries(raw)) {
    const s = Array.isArray(v) ? v.join("/") : v;
    try {
      out[k] = decodeURIComponent(s);
    } catch {
      out[k] = s;
    }
  }
  return out;
}

export function useLocation() {
  const pathname = useConsolePath();
  const params = useSearchParams();
  const search = params && params.toString() ? `?${params.toString()}` : "";
  return {
    pathname,
    search,
    hash: typeof window === "undefined" ? "" : window.location.hash,
    state: null,
    key: pathname,
  };
}

const OutletContext = createContext(null);
export const OutletProvider = OutletContext.Provider;

/** Where the current page renders inside the console's Layout. */
export function Outlet() {
  return useContext(OutletContext);
}
