"use client";
// Generated from apps/web/src/App.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.

import dynamic from "next/dynamic";

import { Loading } from "./_aof/components/ui";

// / in the console.
const Page = dynamic(() => import("./_aof/pages/Overview"), { ssr: false, loading: () => <Loading what="page" /> });

export default function OverviewPage() {
  return <Page />;
}
