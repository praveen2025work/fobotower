import { Check, ShieldAlert } from 'lucide-react';
import { RowDecision } from '../adjustments/RowDecision';
import { breakDetail } from '../lib/breakDetail';
import { amt, manrope, money0, mono, sessionIdOf } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { DecisionPill } from '../ui/Pills';
import { useRecs } from '../data/RecsContext';

export function PatternDrawer({
  pattern,
  label,
  recId,
  statusOf,
  requestDecision,
  onClose,
}) {
  const RECS = useRecs();
  const rec = RECS.find((r) => r.id === recId);
  const items = rec.adjustments
    .filter((a) => a.pattern === pattern)
    .map((a) => ({
      ...a,
      status: statusOf(a),
    }));
  const pend = items.filter((a) => a.status === 'Pending');
  const d = breakDetail(items[0], rec);
  const kpis = [
    ['Books in session', items.length, 'var(--barcl-eagle)'],
    [
      'Total value',
      money0(
        items.reduce((s, a) => s + amt(a), 0),
        rec.ccy,
      ),
      'var(--text-primary)',
    ],
    [
      'Pending',
      pend.length,
      pend.length ? 'var(--clr-amber)' : 'var(--clr-grey)',
    ],
    [
      'Ungrounded',
      items.filter((a) => !a.grounded).length,
      items.some((a) => !a.grounded) ? 'var(--clr-red)' : 'var(--clr-grey)',
    ],
  ];
  return (
    <Drawer
      title={label}
      subtitle={`${pattern} · ${rec.name} · ${sessionIdOf(rec)}`}
      width={600}
      onClose={onClose}
    >
      <div className="hx-space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {kpis.map(([l, v, c]) => (
            <div key={l} className="glass-sm p-3 text-center min-w-0">
              <div
                className="text-[16px] font-extrabold truncate"
                style={{
                  color: c,
                  ...manrope,
                }}
              >
                {v}
              </div>
              <div
                className="text-[10px] mt-1"
                style={{
                  color: 'var(--text-muted)',
                }}
              >
                {l}
              </div>
            </div>
          ))}
        </div>
        <div>
          <div
            className="text-[11px] font-semibold mb-1.5"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            Cause
          </div>
          <p
            className="text-[12.5px] leading-relaxed"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            {d.cause}
          </p>
        </div>
        <div>
          <div className="flex items-center mb-2">
            <div
              className="text-[11px] font-semibold"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              Books in this pattern
            </div>
            {pend.length > 0 && (
              <button
                onClick={() =>
                  requestDecision(
                    pend.map((a) => a.id),
                    'Approved',
                    `${pattern} group`,
                  )
                }
                className="ml-auto text-[11px] font-semibold text-white rounded-md px-2.5 py-1 flex items-center gap-1"
                style={{
                  background: 'var(--clr-green)',
                }}
              >
                <Check size={11} />
                {' Review & approve '}
                {pend.length}
              </button>
            )}
          </div>
          <div
            className="rounded-xl overflow-hidden"
            style={{
              border: '1px solid var(--border)',
            }}
          >
            {items.map((a, i) => (
              <div
                key={a.id}
                className="flex items-center gap-3 px-3 py-2.5"
                style={{
                  borderBottom:
                    i < items.length - 1
                      ? '1px solid var(--border-subtle)'
                      : 'none',
                }}
              >
                <div className="flex-1 min-w-0">
                  <div
                    className="font-semibold text-[12px]"
                    style={{
                      ...mono,
                      color: 'var(--text-primary)',
                    }}
                  >
                    {a.book}{' '}
                    <span
                      style={{
                        color: 'var(--text-muted)',
                      }}
                    >
                      {a.id}
                    </span>
                  </div>
                  <div
                    className="text-[11px]"
                    style={{
                      color: 'var(--text-muted)',
                    }}
                  >
                    {a.reason}
                  </div>
                </div>
                <span
                  className="tabular-nums font-semibold text-[12px]"
                  style={{
                    ...mono,
                    color: 'var(--text-primary)',
                  }}
                >
                  {a.amount}
                </span>
                {!a.grounded && (
                  <ShieldAlert
                    size={12}
                    style={{
                      color: 'var(--clr-red)',
                    }}
                  />
                )}
                {a.status === 'Pending' ? (
                  <RowDecision
                    size={11}
                    onApprove={() =>
                      requestDecision([a.id], 'Approved', a.book)
                    }
                    onReject={() => requestDecision([a.id], 'Rejected', a.book)}
                  />
                ) : (
                  <DecisionPill status={a.status} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Drawer>
  );
}
