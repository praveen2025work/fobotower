import clsx from "clsx";

interface SparklineProps {
  /** Values normalised to 0..1 (success rate). */
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  /** Tailwind stroke colour class — defaults to accent teal. */
  strokeClass?: string;
}

/**
 * Tiny inline sparkline used in the fleet table. Renders a polyline + a
 * faint baseline. Returns an empty placeholder when no data so layout
 * doesn't shift while the query loads.
 */
function Sparkline({
  values,
  width = 96,
  height = 24,
  className,
  strokeClass = "stroke-accent-500",
}: SparklineProps) {
  if (!values || values.length === 0) {
    return (
      <div
        className={clsx("inline-block bg-surface-100", className)}
        style={{ width, height }}
        data-testid="sparkline-empty"
      />
    );
  }

  // Map each y to the SVG coordinate space. We assume values arrive as 0..1
  // already; clamp defensively.
  const stepX = values.length > 1 ? width / (values.length - 1) : width;
  const points = values
    .map((raw, i) => {
      const v = Math.max(0, Math.min(1, raw));
      const y = height - v * height;
      return `${(i * stepX).toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      className={clsx("inline-block", className)}
      role="img"
      aria-label="24h success rate sparkline"
    >
      <line
        x1={0}
        y1={height - 0.5}
        x2={width}
        y2={height - 0.5}
        className="stroke-surface-200"
        strokeWidth={1}
      />
      <polyline
        points={points}
        fill="none"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        className={strokeClass}
      />
    </svg>
  );
}

export default Sparkline;
