'use client';

import { useState } from 'react';

import { ChevronDownIcon, ChevronRightIcon } from '@/components/fobo/icons';

const money = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

export default function PatternGroupCard({
  group,
  deltas = {},
  breakBooks = {},
  reasons = {},
  meta = {},
  decided = {},
  pending = null,
  onOpenPattern,
  onOpenBook,
  onDecide,
}) {
  const total = group.break_ids.reduce((sum, b) => sum + (deltas[b] ?? 0), 0);
  const auto = group.mode === 'auto';
  const ungrounded = meta.ungrounded_count ?? 0;
  const carried = meta.carried_runs ?? 0;
  const groupOutcome = decided[group.group_id];
  const busy = pending === group.group_id;

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

        {groupOutcome ? (
          <span
            className="pill font-semibold"
            style={{
              background:
                groupOutcome === 'approved'
                  ? 'var(--clr-green-bg)'
                  : 'var(--clr-red-bg)',
              color:
                groupOutcome === 'approved'
                  ? 'var(--clr-green)'
                  : 'var(--clr-red)',
            }}
          >
            {groupOutcome === 'approved' ? '✓ Approved' : '✕ Rejected'}
          </span>
        ) : (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onDecide({ action: 'approve', groupId: group.group_id })
              }
              className="pill font-semibold"
              style={{
                background: 'var(--clr-green)',
                color: '#fff',
                opacity: busy ? 0.6 : 1,
              }}
            >
              {busy ? 'Working…' : `Approve all ${group.break_ids.length}`}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onDecide({ action: 'reject', groupId: group.group_id })
              }
              className="pill"
              style={{
                background: 'transparent',
                color: 'var(--clr-red)',
                border: '1px solid var(--clr-red)',
                opacity: busy ? 0.6 : 1,
              }}
            >
              Reject all
            </button>
          </>
        )}
      </div>

      <ul className="mt-2 flex flex-col">
        {group.break_ids.map((breakId) => (
          <BreakRow
            key={breakId}
            breakId={breakId}
            book={breakBooks[breakId] ?? breakId}
            delta={deltas[breakId]}
            reason={reasons[breakId]}
            outcome={decided[breakId]}
            onOpenBook={onOpenBook}
            onDecide={onDecide}
          />
        ))}
      </ul>
    </div>
  );
}

function BreakRow({ breakId, book, delta, reason, outcome, onOpenBook, onDecide }) {
  const [open, setOpen] = useState(false);

  return (
    <li style={{ borderTop: '1px solid var(--border-subtle)' }}>
      <div className="flex items-baseline gap-2 py-1">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? `Collapse ${book}` : `Expand ${book}`}
          className="flex items-center shrink-0"
          style={{ color: 'var(--text-muted)', width: 12 }}
        >
          {open ? <ChevronDownIcon /> : <ChevronRightIcon />}
        </button>

        <button
          type="button"
          onClick={() => onOpenBook(book)}
          className="text-xs font-medium shrink-0 text-left underline-offset-2 hover:underline"
          style={{ color: 'var(--clr-blue)', minWidth: 116 }}
        >
          {book}
        </button>

        <span
          className="text-xs shrink-0"
          style={{
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono), monospace',
            minWidth: 86,
          }}
        >
          {money(delta)}
        </span>

        <span className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
          {reason ?? ''}
        </span>

        <span className="ml-auto shrink-0 flex items-center gap-1">
          {outcome ? (
            <span
              className="text-xs font-semibold"
              style={{
                color:
                  outcome === 'approved' ? 'var(--clr-green)' : 'var(--clr-red)',
              }}
            >
              {outcome === 'approved' ? '✓' : '✕'}
            </span>
          ) : (
            <>
              <button
                type="button"
                aria-label={`Approve ${book}`}
                onClick={() => onDecide({ action: 'approve', breakId })}
                className="rounded"
                style={{
                  width: 20,
                  height: 20,
                  color: 'var(--clr-green)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: 11,
                  lineHeight: 1,
                }}
              >
                ✓
              </button>
              <button
                type="button"
                aria-label={`Reject ${book}`}
                onClick={() => onDecide({ action: 'reject', breakId })}
                className="rounded"
                style={{
                  width: 20,
                  height: 20,
                  color: 'var(--clr-red)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: 11,
                  lineHeight: 1,
                }}
              >
                ✕
              </button>
            </>
          )}
        </span>
      </div>

      {open && (
        <div
          className="ml-6 mb-2 rounded-lg px-3 py-2 text-xs flex flex-col gap-1"
          style={{ background: 'var(--bg-hover)' }}
        >
          <div style={{ color: 'var(--text-secondary)' }}>
            {reason ?? 'No cause identified'}
          </div>
          <div
            style={{
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono), monospace',
            }}
          >
            {breakId} · difference {money(delta)}
          </div>
          <button
            type="button"
            onClick={() => onOpenBook(book)}
            className="self-start underline underline-offset-2"
            style={{ color: 'var(--clr-blue)' }}
          >
            Open {book} detail
          </button>
        </div>
      )}
    </li>
  );
}
