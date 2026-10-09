// Generated from apps/web/src/components/StatCard.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import clsx from "clsx";
import { CountUp } from "./ui";

/** Numbers (and "12.5 h") count up; anything else shows as it is. */
function asNumber(value) {
  if (typeof value === "number") return <CountUp value={value} />;
  const m = /^(\d+(?:\.\d+)?)(\s*\S*)$/.exec(value);
  return m ? <CountUp value={Number(m[1])} suffix={m[2]} /> : value;
}

function StatCard({ icon: Icon, value, label, trend, trendValue, className }) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor = trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : "text-surface-400";

  return (
    <div className={clsx("hx-card flex items-center gap-3 rounded-xl p-3 shadow-sm sm:block sm:p-5", className)}>
      <div className="flex shrink-0 items-start justify-between">
        <div className="hx-chip rounded-lg p-2 sm:p-2.5">
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
        <p className="text-xl font-bold leading-tight text-surface-900 sm:text-2xl">{asNumber(value)}</p>
        <p className="mt-0.5 text-xs leading-snug text-surface-500 sm:mt-1 sm:text-sm">{label}</p>
      </div>
    </div>
  );
}

export default StatCard;
