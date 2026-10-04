import clsx from "clsx";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";

interface KpiTileProps {
  label: string;
  value: string;
  /** Percentage delta (positive or negative). Pass null to hide. */
  delta?: number | null;
  /**
   * Direction in which "up" is good. Defaults to "down" — most operational
   * KPIs (cost, errors, latency) are better when they fall.
   */
  goodDirection?: "up" | "down";
  className?: string;
}

function deltaClass(
  delta: number,
  goodDirection: "up" | "down",
): string {
  if (delta === 0) return "text-surface-500";
  const isPositive = delta > 0;
  const isGood = goodDirection === "up" ? isPositive : !isPositive;
  return isGood ? "text-green-600" : "text-red-600";
}

/**
 * One slot in the {@link ScanningStrip}. Big mono number, small uppercase
 * label, optional ±delta with arrow.
 */
function KpiTile({
  label,
  value,
  delta,
  goodDirection = "down",
  className,
}: KpiTileProps) {
  const showDelta = delta !== undefined && delta !== null;
  const Arrow =
    !showDelta || delta === 0 ? Minus : delta > 0 ? ArrowUp : ArrowDown;
  const colour = showDelta ? deltaClass(delta as number, goodDirection) : "";

  return (
    <div
      className={clsx(
        "flex min-w-[120px] flex-col justify-center px-4",
        className,
      )}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-surface-500">
        {label}
      </span>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-xl font-semibold tabular-nums text-surface-900">
          {value}
        </span>
        {showDelta && (
          <span
            className={clsx("inline-flex items-center gap-0.5 text-xs", colour)}
            data-testid="kpi-delta"
          >
            <Arrow size={12} aria-hidden />
            {Math.abs(delta as number).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

export default KpiTile;
