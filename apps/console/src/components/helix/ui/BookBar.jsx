import { BAR_SEGMENTS } from '../constants';

export function BookBar({ b, height = 'h-3', rounded = true }) {
  return (
    <div
      className={`flex ${height} overflow-hidden flex-1 min-w-[60px]`}
      style={{
        borderRadius: rounded ? '9999px' : 0,
        background: 'var(--border-subtle)',
      }}
    >
      {BAR_SEGMENTS.map(
        (s) =>
          b[s.key] > 0 && (
            <div
              key={s.key}
              title={`${s.label}: ${b[s.key]}`}
              style={{
                backgroundColor: s.color,
                width: `${(b[s.key] / (b.total || 1)) * 100}%`,
              }}
            />
          ),
      )}
    </div>
  );
}

export function BookLegend({ rec }) {
  const b = rec.bookStats;
  return (
    <div className="flex items-center gap-2 mt-2 min-w-0 flex-wrap">
      <BookBar b={b} height="h-1.5" />
      <div className="flex items-center gap-x-2 gap-y-0.5 flex-wrap shrink-0">
        {BAR_SEGMENTS.filter((s) => b[s.key] > 0).map((s) => (
          <span
            key={s.key}
            className="flex items-center gap-1 whitespace-nowrap"
            style={{
              fontSize: 10,
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{
                backgroundColor: s.color,
              }}
            />
            <span
              className="font-semibold tabular-nums"
              style={{
                color: s.color,
              }}
            >
              {b[s.key]}
            </span>
            <span
              style={{
                color: 'var(--text-muted)',
              }}
            >
              {s.label.toLowerCase()}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
