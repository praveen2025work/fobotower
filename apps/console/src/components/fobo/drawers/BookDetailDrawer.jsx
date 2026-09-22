'use client';

import { useEffect } from 'react';

import { useFoboBookStore } from '@/store/foboBookStore';

const money = (v) =>
  v === null || v === undefined
    ? '—'
    : `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

export default function BookDetailDrawer({ bookRef, onClose }) {
  const { data, loading, error, load, clear } = useFoboBookStore();

  useEffect(() => {
    load(bookRef);
    return clear;
  }, [bookRef, load, clear]);

  // Escape closes: a drawer that traps you is worse than no drawer.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const approved = data?.history?.filter((h) => h.outcome === 'approved').length ?? 0;
  const historyTotal = data?.history?.length ?? 0;

  return (
    <div
      className="fixed inset-0 flex justify-end"
      style={{ background: 'rgba(0,30,69,0.32)', zIndex: 60 }}
      onClick={onClose}
    >
      <aside
        role="dialog"
        aria-label={`${bookRef} detail`}
        className="h-full overflow-auto p-5 flex flex-col gap-4"
        style={{
          width: 420,
          background: 'var(--bg-card-solid)',
          borderLeft: '1px solid var(--border)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2
              className="text-lg font-bold"
              style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
            >
              {bookRef}
            </h2>
            {data && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {data.desk} · {data.legal_entity_id} · COB {data.business_date}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="pill"
            style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}
          >
            Close
          </button>
        </div>

        {loading && (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Loading {bookRef}…
          </p>
        )}
        {error && (
          <p className="text-sm" style={{ color: 'var(--clr-red)' }}>
            {error}
          </p>
        )}

        {data && (
          <>
            <div className="grid grid-cols-3 gap-2">
              <Tile label="Breaks today" value={data.total_breaks} />
              <Tile label="Still open" value={data.open_breaks} />
              <Tile
                label="Prior approval"
                value={
                  historyTotal
                    ? `${Math.round((approved / historyTotal) * 100)}%`
                    : '—'
                }
              />
            </div>

            <section>
              <div
                className="text-[11px] font-bold tracking-wide mb-1"
                style={{ color: 'var(--text-muted)' }}
              >
                BREAKS ON THIS BOOK TODAY
              </div>
              {data.breaks.length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  No breaks recorded.
                </p>
              )}
              <ul className="flex flex-col">
                {data.breaks.map((b) => (
                  <li
                    key={b.break_id}
                    className="py-2"
                    style={{ borderTop: '1px solid var(--border-subtle)' }}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className="text-xs"
                        style={{
                          color: 'var(--text-muted)',
                          fontFamily: 'var(--font-mono), monospace',
                        }}
                      >
                        {b.break_id}
                        {b.pattern_code ? ` · ${b.pattern_code}` : ''}
                      </span>
                      <span
                        className="text-sm font-semibold"
                        style={{
                          color: 'var(--text-primary)',
                          fontFamily: 'var(--font-mono), monospace',
                        }}
                      >
                        {money(b.delta)}
                      </span>
                    </div>
                    <div
                      className="text-xs mt-0.5"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      {b.reason_text ?? 'No cause identified'}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[11px]">
                      <span style={{ color: 'var(--text-muted)' }}>
                        FO {money(b.fo_value)} · BO {money(b.bo_value)}
                      </span>
                      {b.is_ungrounded && (
                        <span
                          className="pill"
                          style={{
                            background: 'var(--clr-red-bg)',
                            color: 'var(--clr-red)',
                          }}
                        >
                          ungrounded
                        </span>
                      )}
                      <span
                        className="pill ml-auto"
                        style={
                          b.outcome === 'approved'
                            ? {
                                background: 'var(--clr-green-bg)',
                                color: 'var(--clr-green)',
                              }
                            : b.outcome === 'rejected'
                              ? {
                                  background: 'var(--clr-red-bg)',
                                  color: 'var(--clr-red)',
                                }
                              : {
                                  background: 'var(--clr-amber-bg)',
                                  color: 'var(--clr-amber)',
                                }
                        }
                      >
                        {b.outcome ?? 'open'}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <div
                className="text-[11px] font-bold tracking-wide mb-1"
                style={{ color: 'var(--text-muted)' }}
              >
                PRIOR RESOLUTIONS ({historyTotal})
              </div>
              {historyTotal === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  No prior resolutions on this book.
                </p>
              )}
              <ul className="flex flex-col">
                {data.history.map((h) => (
                  <li
                    key={h.break_id}
                    className="py-1.5 flex items-baseline justify-between gap-2"
                    style={{ borderTop: '1px solid var(--border-subtle)' }}
                  >
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {h.cob_date} · {h.pattern_code}
                    </span>
                    <span
                      className="text-xs font-semibold"
                      style={{
                        color:
                          h.outcome === 'approved'
                            ? 'var(--clr-green)'
                            : 'var(--clr-red)',
                      }}
                    >
                      {h.outcome}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </aside>
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <div className="rounded-lg p-2 text-center" style={{ background: 'var(--bg-muted)' }}>
      <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
        {value}
      </div>
      <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
        {label}
      </div>
    </div>
  );
}
