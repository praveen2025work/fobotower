"use client";
// Generated from apps/web/src/App.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.

import dynamic from "next/dynamic";

import { Loading } from "../../_aof/components/ui";

// /capabilities/:id in the console.
const Page = dynamic(() => import("../../_aof/pages/CapabilityDetail"), {
  ssr: false,
  loading: () => <Loading what="page" />,
});

export default function CapabilityDetailPage() {
  return <Page />;
}
