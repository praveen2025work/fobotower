import { type LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import clsx from "clsx";

interface StatCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  className?: string;
}

function StatCard({ icon: Icon, value, label, trend, trendValue, className }: StatCardProps) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up"
      ? "text-green-600"
      : trend === "down"
        ? "text-red-600"
        : "text-surface-400";

  return (
    <div
      className={clsx(
        "flex items-center gap-3 rounded-xl border border-surface-200 bg-card p-3 shadow-sm transition-shadow hover:shadow-md sm:block sm:p-5",
        className,
      )}
    >
      <div className="flex shrink-0 items-start justify-between">
        <div className="rounded-lg bg-primary-50 p-2 sm:p-2.5">
          <Icon size={18} className="text-primary-600" />
        </div>
        {trend && (
          <div className={clsx("flex items-center gap-1 text-xs font-medium", trendColor)}>
            <TrendIcon size={14} />
            {trendValue}
          </div>
        )}
      </div>
      <div className="min-w-0 sm:mt-4">
        <p className="text-xl font-bold leading-tight text-surface-900 sm:text-2xl">{value}</p>
        <p className="mt-0.5 text-xs leading-snug text-surface-500 sm:mt-1 sm:text-sm">{label}</p>
      </div>
    </div>
  );
}

export default StatCard;
