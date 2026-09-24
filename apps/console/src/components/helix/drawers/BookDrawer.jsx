import { Check } from 'lucide-react';
import { groupOf } from '../constants';
import { breakLegs } from '../lib/breakDetail';
import { amt, money, money0, mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { DecisionPill } from '../ui/Pills';
import { useRecs } from '../data/RecsContext';

export function BookDrawer({
  bookCode,
  recId,
  statusOf,
  requestDecision,
  onClose,
}) {
  const RECS = useRecs();
  const rec = RECS.find((r) => r.id === recId);
  const items = rec.adjustments.filter((a) => a.book === bookCode);
  return (
    <Drawer
      title={bookCode}
      subtitle={`${rec.name} · ${items.length} adjustment${items.length !== 1 ? 's' : ''} this session`}
      width={580}
      onClose={onClose}
    >
      <div className="hx-space-y-3">
        <div className="glass-sm p-3">
          <div
            className="text-[11px] font-semibold mb-2"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            Book summary
          </div>
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            {[
              ['Rec group', groupOf(rec.group).label],
              ['L4', rec.l4],
              ['Ready event', `${rec.eventId} at ${rec.readyAt}`],
              ['Breaks this session', items.length],
              [
                'Total exposure',
                money0(
                  items.reduce((s, a) => s + amt(a), 0),
                  rec.ccy,
                ),
              ],
              ['Rec status', rec.status],
            ].map(([l, v]) => (
              <div key={l}>
                <span
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  {l}
                  {': '}
                </span>
                <span
                  className="font-semibold"
                  style={{
                    color: 'var(--text-primary)',
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>
        {items.map((a) => {
          const st = statusOf(a),
            legs = breakLegs(a, rec);
          return (
            <div key={a.id} className="glass-sm overflow-hidden">
              <div
                className="flex items-center gap-2 px-3 py-2.5 flex-wrap"
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                }}
              >
                <span
                  className="pill"
                  style={
                    a.type === 'Auto'
                      ? {
                          background: 'var(--clr-blue-bg)',
                          color: 'var(--clr-blue)',
                        }
                      : {
                          background: 'var(--clr-purple-bg)',
                          color: 'var(--clr-purple)',
                        }
                  }
                >
                  {a.type}
                </span>
                <span
                  className="font-semibold text-[13px]"
                  style={{
                    color: 'var(--text-primary)',
                  }}
                >
                  {a.patternLabel}
                </span>
                <span
                  className="text-[10px]"
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  {a.id}
                </span>
                <span
                  className="tabular-nums ml-auto font-bold"
                  style={{
                    ...mono,
                    color: 'var(--text-primary)',
                  }}
                >
                  {a.amount}
                </span>
              </div>
              <div
                className="px-3 py-2 text-[12px]"
                style={{
                  color: 'var(--text-secondary)',
                }}
              >
                {a.reason}
              </div>
              <div className="px-3 pb-2">
                <div
                  className="text-[10px] font-semibold mb-1.5"
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  Legs from MB Rec (mbrec.get_break_legs)
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    ['CATS', legs.cats, 'var(--clr-blue)'],
                    ['MOTIF', legs.motif, 'var(--clr-purple)'],
                  ].map(([side, list, c]) => (
                    <div key={side}>
                      <div
                        className="text-[10px] font-semibold mb-1"
                        style={{
                          color: c,
                        }}
                      >
                        {side}
                      </div>
                      {!list.length ? (
                        <div
                          className="text-[11px] py-2 text-center rounded-lg"
                          style={{
                            background: 'var(--bg-muted)',
                            color: 'var(--text-muted)',
                          }}
                        >
                          No entries
                        </div>
                      ) : (
                        list.map((e, i) => (
                          <div
                            key={i}
                            className="rounded-lg px-2 py-1.5 mb-1 text-[11px]"
                            style={{
                              background: 'var(--bg-muted)',
                              border: '1px solid var(--border-subtle)',
                            }}
                          >
                            <div
                              className="font-semibold"
                              style={{
                                ...mono,
                                color: 'var(--text-primary)',
                              }}
                            >
                              {e.ref}
                            </div>
                            <div
                              style={{
                                color: 'var(--text-muted)',
                              }}
                            >
                              {e.time}
                            </div>
                            <div
                              className="font-semibold tabular-nums"
                              style={{
                                ...mono,
                                color: c,
                              }}
                            >
                              {money(e.amount, e.ccy)}
                            </div>
                            <div
                              className="pill mt-1"
                              style={
                                /Pending|not/.test(e.status)
                                  ? {
                                      background: 'var(--clr-amber-bg)',
                                      color: 'var(--clr-amber)',
                                    }
                                  : {
                                      background: 'var(--clr-green-bg)',
                                      color: 'var(--clr-green)',
                                    }
                              }
                            >
                              {e.status}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  ))}
                </div>
                <div
                  className="mt-2 text-[11px] leading-relaxed"
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  {legs.note}
                </div>
              </div>
              <div className="flex gap-2 px-3 pb-3">
                {st === 'Pending' ? (
                  <>
                    <button
                      onClick={() =>
                        requestDecision([a.id], 'Approved', bookCode)
                      }
                      className="flex-1 py-1.5 rounded-lg font-semibold text-[12px] flex items-center justify-center gap-1"
                      style={{
                        background: 'var(--clr-green)',
                        color: '#fff',
                      }}
                    >
                      <Check size={12} />
                      {' Approve'}
                    </button>
                    <button
                      onClick={() =>
                        requestDecision([a.id], 'Rejected', bookCode)
                      }
                      className="flex-1 py-1.5 rounded-lg font-semibold text-[12px] border"
                      style={{
                        borderColor: 'var(--border)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      Reject
                    </button>
                  </>
                ) : (
                  <DecisionPill status={st} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Drawer>
  );
}
