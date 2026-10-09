"use client";
// Generated from apps/web/src/main.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.

import dynamic from "next/dynamic";

import "./_aof/finance.css";

// The console runs in the browser only, as it does upstream.
const FinanceShell = dynamic(() => import("./_aof/office/FinanceShell"), { ssr: false });

export default function FinanceLayout({ children }) {
  return <FinanceShell>{children}</FinanceShell>;
}
