// Generated from apps/web/src/components/mission-control/SeverityBadge.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
import clsx from "clsx";

const SEVERITY_STYLES = {
  high: "bg-red-100 text-red-700",
  medium: "bg-orange-100 text-orange-700",
  low: "bg-surface-100 text-surface-700",
};

function normalise(input) {
  const v = input.toLowerCase();
  if (v === "high" || v === "med" || v === "medium" || v === "low") {
    return v === "med" ? "medium" : v;
  }
  return "low";
}

/**
 * 11px uppercase pill used in the approval queue + incident strip. Spec
 * pins specific bg/fg pairs per severity — see README §Direction A §4.
 */
function SeverityBadge({ severity, className }) {
  const level = normalise(severity);
  return (
    <span
      data-severity={level}
      className={clsx(
        "inline-flex items-center justify-center rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider",
        SEVERITY_STYLES[level],
        className,
      )}
    >
      {level}
    </span>
  );
}

export default SeverityBadge;
