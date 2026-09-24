import { useState, useEffect, useRef } from 'react';
import { TriangleAlert as Alert, X as XIcon } from 'lucide-react';
import { ShieldCheck } from '../ui/icons';
import { TONES } from '../constants';
import { breakDetail } from '../lib/breakDetail';
import { amt, manrope, money0, mono } from '../lib/format';
import { useRecs } from '../data/RecsContext';

export function ConfirmDialog({ request, onCancel, onConfirm }) {
  const RECS = useRecs();
  const { decision, ids, source } = request;
  const approve = decision === 'Approved';
  const items = ids.map((id) => {
    const rec = RECS.find((r) => r.adjustments.some((a) => a.id === id));
    return {
      ...rec.adjustments.find((a) => a.id === id),
      rec,
    };
  });
  const total = items.reduce((s, a) => s + amt(a), 0);
  const ungrounded = items.filter((a) => !a.grounded);
  const noFix = items.filter((a) => !breakDetail(a, a.rec).fix);
  const [ackReview, setAckReview] = useState(false);
  const [ackUngrounded, setAckUngrounded] = useState(false);
  const [ackNoFix, setAckNoFix] = useState(false);
  const [reason, setReason] = useState('');
  const firstRef = useRef(null);
  useEffect(() => {
    firstRef.current && firstRef.current.focus();
  }, []);
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onCancel();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onCancel]);
  const ready = approve
    ? ackReview &&
      (!ungrounded.length || ackUngrounded) &&
      (!noFix.length || ackNoFix)
    : ackReview && reason.trim().length >= 5;
  const recNames = [...new Set(items.map((a) => a.rec.name))];
  const Box = ({ checked, onChange, children, tone }) => (
    <label
      className="flex items-start gap-2 text-[12px] cursor-pointer select-none rounded-lg px-2.5 py-2"
      style={{
        background: tone ? TONES[tone].bg : 'var(--bg-muted)',
        color: tone ? TONES[tone].fg : 'var(--text-secondary)',
      }}
    >
      <input
        type="checkbox"
        className="mt-0.5 shrink-0"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{children}</span>
    </label>
  );
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        background: 'rgba(0,20,50,0.45)',
        backdropFilter: 'blur(2px)',
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div
        className="w-full max-w-[560px] max-h-[90vh] flex flex-col rounded-2xl overflow-hidden"
        style={{
          background: 'var(--bg-card-solid)',
          border: '1px solid var(--border)',
          boxShadow: 'var(--card-shadow-md)',
        }}
      >
        <div
          className="px-5 py-4 shrink-0"
          style={{
            borderBottom: '1px solid var(--border)',
            background: approve ? 'var(--clr-green-bg)' : 'var(--clr-red-bg)',
          }}
        >
          <div className="flex items-center gap-2">
            {approve ? (
              <ShieldCheck
                size={18}
                style={{
                  color: 'var(--clr-green)',
                }}
              />
            ) : (
              <Alert
                size={18}
                style={{
                  color: 'var(--clr-red)',
                }}
              />
            )}
            <div
              id="confirm-title"
              className="text-[15px] font-bold"
              style={{
                ...manrope,
                color: approve ? 'var(--clr-green)' : 'var(--clr-red)',
              }}
            >
              {'Confirm '}
              {approve ? 'approval' : 'rejection'}
              {' of '}
              {items.length}
              {' adjustment'}
              {items.length > 1 ? 's' : ''}
            </div>
          </div>
          <div
            className="text-[11.5px] mt-1"
            style={{
              color: 'var(--text-secondary)',
            }}
          >
            {recNames.join(', ')}
            {' · total '}
            {money0(total)}
            {source ? ` · from ${source}` : ''}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 hx-space-y-3">
          <div
            className="rounded-lg overflow-hidden"
            style={{
              border: '1px solid var(--border)',
            }}
          >
            <table className="w-full border-collapse text-[11.5px]">
              <thead>
                <tr
                  style={{
                    background: 'var(--bg-muted)',
                  }}
                >
                  {['Adj', 'Master book', 'Pattern', 'Amount', 'Checks'].map(
                    (c) => (
                      <th
                        key={c}
                        className={`px-2.5 py-1.5 font-semibold ${c === 'Amount' ? 'text-right' : 'text-left'}`}
                        style={{
                          color: 'var(--text-muted)',
                          borderBottom: '1px solid var(--border)',
                        }}
                      >
                        {c}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {items.map((a, i) => {
                  const fix = !!breakDetail(a, a.rec).fix;
                  return (
                    <tr
                      key={a.id}
                      style={{
                        borderBottom:
                          i < items.length - 1
                            ? '1px solid var(--border-subtle)'
                            : 'none',
                      }}
                    >
                      <td
                        className="px-2.5 py-1.5 font-semibold"
                        style={{
                          color: 'var(--text-primary)',
                        }}
                      >
                        {a.id}
                      </td>
                      <td
                        className="px-2.5 py-1.5"
                        style={{
                          ...mono,
                          color: 'var(--text-primary)',
                        }}
                      >
                        {a.book}
                      </td>
                      <td
                        className="px-2.5 py-1.5"
                        style={{
                          color: 'var(--text-secondary)',
                        }}
                      >
                        {a.patternLabel}
                      </td>
                      <td
                        className="px-2.5 py-1.5 text-right tabular-nums"
                        style={{
                          ...mono,
                          color: 'var(--text-primary)',
                        }}
                      >
                        {a.amount}
                      </td>
                      <td className="px-2.5 py-1.5">
                        <div className="flex gap-1 flex-wrap">
                          {!a.grounded && (
                            <span
                              className="pill"
                              style={{
                                background: 'var(--clr-red-bg)',
                                color: 'var(--clr-red)',
                                fontSize: 10,
                              }}
                            >
                              ungrounded
                            </span>
                          )}
                          {!fix && (
                            <span
                              className="pill"
                              style={{
                                background: 'var(--clr-amber-bg)',
                                color: 'var(--clr-amber)',
                                fontSize: 10,
                              }}
                            >
                              no fix proposed
                            </span>
                          )}
                          {a.grounded && fix && (
                            <span
                              className="pill"
                              style={{
                                background: 'var(--clr-green-bg)',
                                color: 'var(--clr-green)',
                                fontSize: 10,
                              }}
                            >
                              ok
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {approve && (
            <div
              className="text-[11.5px] leading-relaxed"
              style={{
                color: 'var(--text-secondary)',
              }}
            >
              On confirmation these adjustments are released to FAS for posting
              to MOTIF. The decision is recorded against your name in the
              application audit.
            </div>
          )}
          <Box checked={ackReview} onChange={setAckReview}>
            {'I have reviewed '}
            {items.length > 1
              ? `all ${items.length} adjustments`
              : 'this adjustment'}
            {', the break evidence and the '}
            {approve ? 'proposed MOTIF postings' : 'reason for rejection'}.
          </Box>
          {approve && ungrounded.length > 0 && (
            <Box
              checked={ackUngrounded}
              onChange={setAckUngrounded}
              tone="risk"
            >
              {'I have manually verified the '}
              {ungrounded.length}
              {' ungrounded figure'}
              {ungrounded.length > 1 ? 's' : ''}
              {' ('}
              {ungrounded.map((a) => a.id).join(', ')}) against source data.
            </Box>
          )}
          {approve && noFix.length > 0 && (
            <Box checked={ackNoFix} onChange={setAckNoFix} tone="warn">
              {noFix.length}
              {' item'}
              {noFix.length > 1 ? 's have' : ' has'}
              {' no proposed fix ('}
              {noFix.map((a) => a.id).join(', ')}). I confirm the upstream item
              is resolved and approval is appropriate.
            </Box>
          )}
          {!approve && (
            <div>
              <label
                className="text-[11px] font-semibold"
                style={{
                  color: 'var(--text-muted)',
                }}
                htmlFor="reject-reason"
              >
                Reason for rejection (required)
              </label>
              <textarea
                id="reject-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                className="hx-input w-full mt-1 text-[12px] px-2.5 py-2 focus:outline-none"
                placeholder="e.g. Desk confirmed trade is genuine, will book in MOTIF"
              />
            </div>
          )}
        </div>
        <div
          className="px-5 py-3 flex items-center justify-end gap-2 shrink-0"
          style={{
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-muted)',
          }}
        >
          <button
            ref={firstRef}
            onClick={onCancel}
            className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border"
            style={{
              borderColor: 'var(--border)',
              color: 'var(--text-secondary)',
              background: 'var(--bg-card-solid)',
            }}
          >
            Cancel
          </button>
          <button
            disabled={!ready}
            onClick={() => onConfirm(reason.trim())}
            className="text-[12px] font-semibold px-3.5 py-2 rounded-lg flex items-center gap-1.5 transition-opacity"
            style={{
              background: approve ? 'var(--clr-green)' : 'var(--clr-red)',
              color: '#fff',
              opacity: ready ? 1 : 0.4,
              cursor: ready ? 'pointer' : 'not-allowed',
            }}
          >
            {approve ? <ShieldCheck size={13} /> : <XIcon size={13} />}
            {'Confirm '}
            {approve ? 'approval' : 'rejection'}
            {' ('}
            {items.length})
          </button>
        </div>
      </div>
    </div>
  );
}
