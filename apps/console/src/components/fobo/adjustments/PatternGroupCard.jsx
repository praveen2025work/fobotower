'use client';

const money = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

export default function PatternGroupCard({
  group,
  deltas = {},
  breakBooks = {},
  reasons = {},
  meta = {},
  onOpenPattern,
}) {
  const total = group.break_ids.reduce((sum, b) => sum + (deltas[b] ?? 0), 0);
  const auto = group.mode === 'auto';
  const ungrounded = meta.ungrounded_count ?? 0;
  const carried = meta.carried_runs ?? 0;

  return (
    <div
      className="rounded-xl p-3"
      style={{
        background: 'var(--bg-muted)',
        border: '1px solid var(--border-subtle)',
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="pill font-semibold"
          style={{
            background: auto ? 'var(--clr-purple-bg)' : 'var(--bg-hover)',
            color: auto ? 'var(--clr-purple)' : 'var(--text-secondary)',
          }}
        >
          {auto ? 'Auto' : 'Manual'}
        </span>
        <span
          className="text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          {group.label}
        </span>
        <span
          className="pill"
          style={{ background: 'var(--bg-hover)', color: 'var(--text-muted)' }}
        >
          {group.pattern_code}
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {group.break_ids.length} books
        </span>

        {ungrounded > 0 && (
          <span
            className="pill"
            style={{ background: 'var(--clr-red-bg)', color: 'var(--clr-red)' }}
          >
            {ungrounded} ungrounded
          </span>
        )}
        {carried > 0 && (
          <span
            className="pill"
            style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
          >
            carried {carried} run{carried === 1 ? '' : 's'}
          </span>
        )}
        {group.historical_approval_rate !== null &&
          group.historical_approval_rate !== undefined && (
            <span
              className="pill"
              style={{
                background: 'var(--clr-green-bg)',
                color: 'var(--clr-green)',
              }}
            >
              {Math.round(group.historical_approval_rate * 100)}% prior approval
            </span>
          )}

        <span
          className="ml-auto text-sm font-semibold"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono), monospace',
          }}
        >
          {money(total)}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onOpenPattern(group)}
          className="pill"
          style={{
            background: 'transparent',
            color: 'var(--clr-blue)',
            border: '1px solid var(--clr-blue)',
          }}
        >
          Pattern detail →
        </button>
      </div>

      <ul className="mt-2 flex flex-col">
        {group.break_ids.map((breakId) => (
          <li
            key={breakId}
            className="flex items-baseline gap-3 py-1"
            style={{ borderTop: '1px solid var(--border-subtle)' }}
          >
            <span
              className="text-xs font-medium shrink-0"
              style={{ color: 'var(--text-primary)', minWidth: 120 }}
            >
              {breakBooks[breakId] ?? breakId}
            </span>
            <span
              className="text-xs shrink-0"
              style={{
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-mono), monospace',
                minWidth: 92,
              }}
            >
              {money(deltas[breakId])}
            </span>
            <span
              className="text-xs truncate"
              style={{ color: 'var(--text-muted)' }}
            >
              {reasons[breakId] ?? ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
