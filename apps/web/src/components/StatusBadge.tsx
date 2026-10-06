import clsx from "clsx";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-700 border-green-200",
  healthy: "bg-green-100 text-green-700 border-green-200",
  approved: "bg-green-100 text-green-700 border-green-200",
  pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
  suspended: "bg-red-100 text-red-700 border-red-200",
  rejected: "bg-red-100 text-red-700 border-red-200",
  error: "bg-red-100 text-red-700 border-red-200",
  inactive: "bg-surface-100 text-surface-500 border-surface-200",
  archived: "bg-surface-100 text-surface-500 border-surface-200",
  unknown: "bg-surface-100 text-surface-500 border-surface-200",
  degraded: "bg-orange-100 text-orange-700 border-orange-200",
  // Agent One Finance case, finding and decision states
  running: "bg-primary-50 text-primary-700 border-primary-200",
  awaiting_review: "bg-yellow-100 text-yellow-700 border-yellow-200",
  awaiting_publish: "bg-primary-50 text-primary-700 border-primary-200",
  review: "bg-yellow-100 text-yellow-700 border-yellow-200",
  release: "bg-primary-50 text-primary-700 border-primary-200",
  proposed: "bg-accent-50 text-accent-700 border-accent-200",
  escalated: "bg-orange-100 text-orange-700 border-orange-200",
  completed: "bg-green-100 text-green-700 border-green-200",
  published: "bg-green-100 text-green-700 border-green-200",
  approve: "bg-green-100 text-green-700 border-green-200",
  reject: "bg-red-100 text-red-700 border-red-200",
  failed: "bg-red-100 text-red-700 border-red-200",
  gate: "bg-amber-100 text-amber-800 border-amber-200",
  stopped: "bg-surface-100 text-surface-600 border-surface-300",
  read: "bg-surface-100 text-surface-600 border-surface-200",
  write: "bg-orange-100 text-orange-700 border-orange-200",
};

function StatusBadge({ status, className }: StatusBadgeProps) {
  // A run waiting at a tollgate: "paused_before_reason" reads "tollgate: reason".
  const gate = status.startsWith("paused_before_") ? status.slice("paused_before_".length) : null;
  const style =
    STATUS_STYLES[gate ? "gate" : status.toLowerCase()] ?? STATUS_STYLES.unknown;

  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        style,
        className,
      )}
    >
      {gate ? `tollgate: ${gate}` : status === "gate" ? "tollgate" : status.replace(/_/g, " ")}
    </span>
  );
}

export default StatusBadge;
