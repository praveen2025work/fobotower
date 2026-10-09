// Generated from apps/web/src/components/mission-control/HealthBanner.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { Bot, Database, Eye, Heart, KeyRound } from "lucide-react";

/**
 * aria-ai's compact platform health strip, on Agent One Finance's health: database, the
 * LLM adapter, tracing (Phoenix) and the entitlement source.
 */
function HealthBanner({ health }) {
  if (!health) return null;
  const up = health.status === "healthy";
  const tone = up
    ? "border-success-100 bg-success-100/40 text-success-700"
    : "border-warning-100 bg-warning-100/40 text-warning-700";
  return (
    <div data-testid="health-banner" className={`flex flex-wrap items-center gap-4 border-b px-4 py-2 text-xs ${tone}`}>
      <Heart size={14} className={up ? "text-success-600" : "text-warning-600"} />
      <span className="font-medium uppercase tracking-wide">Platform {up ? "Healthy" : "Degraded"}</span>
      <span className="flex items-center gap-1.5">
        <Database size={12} />
        DB: {health.database}
      </span>
      <span className="flex items-center gap-1.5">
        <Bot size={12} />
        LLM: {health.llm}
      </span>
      <span className="flex items-center gap-1.5">
        <Eye size={12} />
        Tracing: {health.tracing}
      </span>
      <span className="flex items-center gap-1.5">
        <KeyRound size={12} />
        Entitlement: {health.entitlement}
      </span>
    </div>
  );
}

export default HealthBanner;
