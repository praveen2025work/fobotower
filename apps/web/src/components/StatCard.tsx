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
        "rounded-xl border border-surface-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md",
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="rounded-lg bg-primary-50 p-2.5">
          <Icon size={20} className="text-primary-600" />
        </div>
        {trend && (
          <div className={clsx("flex items-center gap-1 text-xs font-medium", trendColor)}>
            <TrendIcon size={14} />
            {trendValue}
          </div>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold text-surface-900">{value}</p>
        <p className="mt-1 text-sm text-surface-500">{label}</p>
      </div>
    </div>
  );
}

export default StatCard;
