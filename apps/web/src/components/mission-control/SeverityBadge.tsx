import clsx from "clsx";

export type Severity = "high" | "medium" | "low";

interface SeverityBadgeProps {
  severity: string;
  className?: string;
}

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-surface-100 text-surface-700",
};

function normalise(input: string): Severity {
  const v = input.toLowerCase();
  if (v === "high" || v === "med" || v === "medium" || v === "low") {
    return v === "med" ? "medium" : (v as Severity);
  }
  return "low";
}

/**
 * 11px uppercase pill used in the approval queue + incident strip. Spec
 * pins specific bg/fg pairs per severity — see README §Direction A §4.
 */
function SeverityBadge({ severity, className }: SeverityBadgeProps) {
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
