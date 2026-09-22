'use client';

import { useState } from 'react';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

const money = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

/**
 * Everything awaiting sign-off, across every rec — not just the one open in
 * the centre. Its whole purpose is to tell a controller what is outstanding
 * elsewhere.
 */
export default function HumanInLoopPanel({
  items,
  pending,
  decided = {},
  busy = null,
  onDecide,
  onOpenRec,
}) {
  const [filter, setFilter] = useState('all');

  const shown =
    filter === 'all' ? items : items.filter((i) => i.mode === filter);

  return (
    <section className="glass-card p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2
          className="text-xs font-bold tracking-wide"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-manrope), sans-serif',
          }}
        >
          Human-in-Loop
        </h2>
        <span
          className="pill font-semibold"
          style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
        >
          {pending} pending
        </span>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter adjustments"
          className="ml-auto rounded px-1.5 py-0.5 text-[11px] outline-none"
          style={{
            background: 'var(--bg-muted)',
            border: '1px solid var(--border-subtle)',
            color: 'var(--text-secondary)',
          }}
        >
          <option value="all">All adjustments</option>
          <option value="auto">Auto only</option>
          <option value="manual">Manual only</option>
        </select>
      </div>

      {shown.length === 0 && (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Nothing awaiting sign-off.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {shown.map((item) => {
          const outcome = decided[item.group_id];
          const working = busy === item.group_id;
          return (
            <li
              key={item.group_id}
              className="rounded-xl p-2.5 flex flex-col gap-1.5"
              style={{
                background: 'var(--bg-muted)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="pill font-semibold"
                  style={REGION_STYLE[item.region]}
                >
                  {item.region}
                </span>
                <button
                  type="button"
                  onClick={() => onOpenRec(item.rec_id)}
                  className="text-[11px] truncate underline-offset-2 hover:underline"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {item.rec_name}
                </button>
              </div>

              <div className="flex items-baseline gap-2">
                <span
                  className="text-sm font-semibold truncate"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {item.label}
                </span>
                <span
                  className="ml-auto text-sm font-semibold shrink-0"
                  style={{
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-mono), monospace',
                  }}
                >
                  {money(item.total)}
                </span>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {item.book_count} books
                </span>
                {item.ungrounded_count > 0 && (
                  <span
                    className="pill"
                    style={{
                      background: 'var(--clr-red-bg)',
                      color: 'var(--clr-red)',
                    }}
                  >
                    {item.ungrounded_count} ungrounded
                  </span>
                )}
                {item.carried_runs > 0 && (
                  <span
                    className="pill"
                    style={{
                      background: 'var(--clr-amber-bg)',
                      color: 'var(--clr-amber)',
                    }}
                  >
                    carried {item.carried_runs}
                  </span>
                )}
              </div>

              {outcome ? (
                <span
                  className="pill self-start font-semibold"
                  style={{
                    background:
                      outcome === 'approved'
                        ? 'var(--clr-green-bg)'
                        : 'var(--clr-red-bg)',
                    color:
                      outcome === 'approved'
                        ? 'var(--clr-green)'
                        : 'var(--clr-red)',
                  }}
                >
                  {outcome === 'approved' ? '✓ Approved' : '✕ Rejected'}
                </span>
              ) : (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={working}
                    onClick={() =>
                      onDecide({
                        recId: item.rec_id,
                        action: 'approve',
                        groupId: item.group_id,
                      })
                    }
                    className="pill font-semibold"
                    style={{
                      background: 'var(--clr-green)',
                      color: '#fff',
                      opacity: working ? 0.6 : 1,
                    }}
                  >
                    {working ? 'Working…' : `✓ Approve ${item.book_count}`}
                  </button>
                  <button
                    type="button"
                    disabled={working}
                    onClick={() =>
                      onDecide({
                        recId: item.rec_id,
                        action: 'reject',
                        groupId: item.group_id,
                      })
                    }
                    className="pill"
                    style={{
                      background: 'transparent',
                      color: 'var(--clr-red)',
                      border: '1px solid var(--clr-red)',
                      opacity: working ? 0.6 : 1,
                    }}
                  >
                    ✕ Reject
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
