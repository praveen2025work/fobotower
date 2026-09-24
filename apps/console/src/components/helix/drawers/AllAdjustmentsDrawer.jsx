import { useState, useMemo } from 'react';
import { RotateCcwClock as Aged, Check, ShieldAlert } from 'lucide-react';
import { RowDecision } from '../adjustments/RowDecision';
import { GROUPS } from '../constants';
import { amt, manrope, money0, mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { DecisionPill, GroupPill } from '../ui/Pills';
import { useRecs } from '../data/RecsContext';

export function AllAdjustmentsDrawer({ statusOf, requestDecision, onClose }) {
  const RECS = useRecs();
  const [st, setSt] = useState('Pending');
  const [grp, setGrp] = useState('ALL');
  const all = useMemo(
    () =>
      RECS.flatMap((r) =>
        r.adjustments.map((a) => ({
          ...a,
          status: statusOf(a),
          rec: r,
        })),
      ),
    [RECS, statusOf],
  );
  const rows = all
    .filter((a) => st === 'ALL' || a.status === st)
    .filter((a) => grp === 'ALL' || a.rec.group === grp);
  const count = (s) => all.filter((a) => a.status === s).length;
  const total = all.reduce((s, a) => s + amt(a), 0);
  const pillStyle = (on) =>
    on
      ? {
          background: 'var(--bg-header)',
          color: '#fff',
        }
      : {
          background: 'var(--bg-muted)',
          color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
        };
  const pendingRows = rows.filter((a) => a.status === 'Pending');
  return (
    <Drawer
      title="All adjustments today"
      subtitle={`${all.length} adjustments · ${money0(total)} total value`}
      width={720}
      onClose={onClose}
    >
      <div className="flex gap-2 flex-wrap mb-3">
        {['ALL', 'Pending', 'Posted', 'Approved', 'Rejected'].map((s) => (
          <button
            key={s}
            onClick={() => setSt(s)}
            className="pill"
            style={pillStyle(st === s)}
          >
            {s}
            {s !== 'ALL' ? ` · ${count(s)}` : ''}
          </button>
        ))}
      </div>
      <div className="flex gap-1.5 flex-wrap mb-4 items-center">
        <span
          className="text-[11px] mr-1"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          Rec group
        </span>
        <button
          onClick={() => setGrp('ALL')}
          className="pill"
          style={pillStyle(grp === 'ALL')}
        >
          All
        </button>
        {GROUPS.map((gp) => (
          <button
            key={gp.key}
            onClick={() => setGrp(gp.key)}
            className="pill"
            style={pillStyle(grp === gp.key)}
          >
            {gp.label}
          </button>
        ))}
        {pendingRows.length > 0 && (
          <button
            onClick={() =>
              requestDecision(
                pendingRows.map((a) => a.id),
                'Approved',
                'All adjustments view',
              )
            }
            className="ml-auto text-[11px] font-semibold text-white rounded-md px-2.5 py-1 flex items-center gap-1"
            style={{
              background: 'var(--clr-green)',
            }}
          >
            <Check size={11} />
            {' Review & approve '}
            {pendingRows.length}
          </button>
        )}
      </div>
      <div
        className="rounded-xl overflow-hidden"
        style={{
          border: '1px solid var(--border)',
        }}
      >
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr
              style={{
                background: 'var(--bg-muted)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              {['Master book', 'Amount', 'Pattern', 'Rec', 'Status', ''].map(
                (c) => (
                  <th
                    key={c}
                    className="text-left px-3 py-2 font-semibold"
                    style={{
                      color: 'var(--text-muted)',
                      ...manrope,
                    }}
                  >
                    {c}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((a, i) => (
              <tr
                key={a.id}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  background: i % 2 ? 'var(--bg-muted)' : 'transparent',
                }}
              >
                <td className="px-3 py-2">
                  <div
                    className="font-semibold"
                    style={{
                      ...mono,
                      color: 'var(--text-primary)',
                    }}
                  >
                    {a.book}
                  </div>
                  <div
                    style={{
                      color: 'var(--text-muted)',
                      fontSize: 10,
                    }}
                  >
                    {a.id}
                  </div>
                </td>
                <td
                  className="px-3 py-2 tabular-nums font-semibold"
                  style={{
                    ...mono,
                    color: 'var(--text-primary)',
                  }}
                >
                  {a.amount}
                </td>
                <td className="px-3 py-2">
                  <div
                    style={{
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {a.patternLabel}
                  </div>
                  {a.agedSessions > 0 && (
                    <span
                      className="flex items-center gap-1 text-[10px]"
                      style={{
                        color: 'var(--clr-amber)',
                      }}
                    >
                      <Aged size={9} /> {a.agedSessions}
                      {' sessions'}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <GroupPill groupKey={a.rec.group} />
                  <div
                    className="text-[10px] mt-0.5"
                    style={{
                      color: 'var(--text-muted)',
                    }}
                  >
                    {a.rec.l4}
                    {' · Ready '}
                    {a.rec.readyAt}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <DecisionPill status={a.status} />
                  {!a.grounded && (
                    <ShieldAlert
                      size={11}
                      className="mt-1"
                      style={{
                        color: 'var(--clr-red)',
                      }}
                    />
                  )}
                </td>
                <td className="px-3 py-2">
                  {a.status === 'Pending' && (
                    <RowDecision
                      size={11}
                      onApprove={() =>
                        requestDecision([a.id], 'Approved', a.book)
                      }
                      onReject={() =>
                        requestDecision([a.id], 'Rejected', a.book)
                      }
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div
            className="py-10 text-center text-[12px]"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            No adjustments match this filter.
          </div>
        )}
      </div>
    </Drawer>
  );
}
