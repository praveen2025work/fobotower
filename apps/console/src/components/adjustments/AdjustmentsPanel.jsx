import { useState, useMemo, useEffect, useRef } from 'react';
import {
  RotateCcwClock as Aged,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Layers,
  Maximize2 as Maximize,
  ShieldAlert,
} from 'lucide-react';
import { MessageSquare } from '../ui/icons';
import { RowDecision } from './RowDecision';
import { manrope, mono } from '../lib/format';
import { BreakDetailPanel } from '../mcp/BreakDetailPanel';
import { DecisionPill } from '../ui/Pills';

export function AdjustmentsPanel({
  rec,
  statusOf,
  requestDecision,
  onOpenPattern,
  onOpenBook,
  onAsk,
  focusTick,
  onOpenAll,
}) {
  const [expanded, setExpanded] = useState(null);
  const [flashKey, setFlashKey] = useState(null);
  const boxRef = useRef(null);
  const groupRefs = useRef({});
  const groups = useMemo(() => {
    const m = {};
    rec.adjustments.forEach((a) =>
      (m[a.pattern] = m[a.pattern] || {
        key: a.pattern,
        label: a.patternLabel,
        type: a.type,
        items: [],
      }).items.push({
        ...a,
        status: statusOf(a),
      }),
    );
    return Object.values(m).sort((x, y) => y.items.length - x.items.length);
  }, [rec, statusOf]);
  useEffect(() => {
    if (!focusTick) return;
    const target =
      groups.find((gp) => gp.items.some((a) => a.status === 'Pending')) ||
      groups[0];
    const raf = requestAnimationFrame(() => {
      const box = boxRef.current,
        el = target && groupRefs.current[target.key];
      if (!box) return;
      const reduce =
        window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const top = el
        ? box.scrollTop +
          el.getBoundingClientRect().top -
          box.getBoundingClientRect().top -
          44
        : 0;
      box.scrollTo({
        top,
        behavior: reduce ? 'auto' : 'smooth',
      });
      if (target) setFlashKey(`${target.key}-${focusTick}`);
    });
    return () => cancelAnimationFrame(raf);
  }, [focusTick]);
  return (
    <div
      ref={boxRef}
      className="glass p-4 flex-1 min-w-0 min-h-0 overflow-y-auto"
    >
      <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <div
          className="text-xs font-bold"
          style={{
            ...manrope,
            color: 'var(--text-primary)',
          }}
        >
          Drafted Adjustments
        </div>
        <div className="flex items-center gap-2">
          {groups.length > 0 && (
            <div
              className="text-[10.5px]"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              {rec.adjustments.length}
              {' adj · '}
              {groups.length}
              {' patterns'}
            </div>
          )}
          <button
            onClick={onOpenAll}
            className="pill flex items-center gap-1"
            style={{
              background: 'var(--bg-muted)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
            title="All adjustments across recs today"
          >
            <Maximize size={10} />
            {' All recs'}
          </button>
        </div>
      </div>
      {!groups.length ? (
        <div
          className="text-center py-8 text-[12px]"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          {rec.status === 'Blocked'
            ? 'No adjustments drafted. The break needs a source-system correction first.'
            : rec.analysis && rec.analysis.confidence === 'RUNNING'
              ? 'Adjustments appear here when the session analysis finishes.'
              : 'No adjustments for this rec.'}
        </div>
      ) : (
        <div className="hx-space-y-3">
          {groups.map((gp) => {
            const pend = gp.items.filter((a) => a.status === 'Pending');
            const ug = gp.items.filter((a) => !a.grounded).length;
            const aged = Math.max(0, ...gp.items.map((a) => a.agedSessions));
            return (
              <div
                key={
                  flashKey && flashKey.startsWith(`${gp.key}-`)
                    ? flashKey
                    : gp.key
                }
                ref={(el) => (groupRefs.current[gp.key] = el)}
                className={`rounded-lg overflow-hidden ${flashKey && flashKey.startsWith(`${gp.key}-`) ? 'hx-flash' : ''}`}
                style={{
                  border: '1px solid var(--border)',
                }}
              >
                <div
                  className="flex items-center gap-2 px-3 py-2 flex-wrap"
                  style={{
                    background: 'var(--bg-muted)',
                  }}
                >
                  <span
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                    style={
                      gp.type === 'Auto'
                        ? {
                            backgroundColor: 'var(--clr-blue-bg)',
                            color: 'var(--clr-blue)',
                          }
                        : {
                            backgroundColor: 'var(--clr-grey-bg)',
                            color: 'var(--text-primary)',
                          }
                    }
                  >
                    {gp.type}
                  </span>
                  <span
                    className="text-xs font-semibold min-w-0 truncate"
                    style={{
                      color: 'var(--text-primary)',
                    }}
                  >
                    {gp.label}
                  </span>
                  <span
                    className="text-[10px] shrink-0"
                    style={{
                      ...mono,
                      color: 'var(--text-muted)',
                    }}
                  >
                    {gp.key}
                  </span>
                  <span
                    className="flex items-center gap-1 shrink-0"
                    style={{
                      fontSize: 10,
                      color: 'var(--text-muted)',
                    }}
                  >
                    <Layers size={10} /> {gp.items.length}
                  </span>
                  <button
                    onClick={() => onOpenPattern(gp.key, gp.label, rec.id)}
                    className="flex items-center gap-0.5 shrink-0 hover:opacity-70"
                    style={{
                      fontSize: 10,
                      color: 'var(--barcl-eagle)',
                    }}
                  >
                    {'Detail '}
                    <ArrowRight size={9} />
                  </button>
                  {aged > 0 && (
                    <span
                      className="text-[10px] rounded-full px-1.5 py-0.5 flex items-center gap-1 shrink-0"
                      style={{
                        background: 'var(--clr-amber-bg)',
                        color: 'var(--clr-amber)',
                      }}
                    >
                      <Aged size={9} /> {aged}
                      {' sessions'}
                    </span>
                  )}
                  {ug > 0 && (
                    <span
                      className="text-[10px] rounded-full px-1.5 py-0.5 flex items-center gap-1 shrink-0"
                      style={{
                        background: 'var(--clr-red-bg)',
                        color: 'var(--clr-red)',
                      }}
                    >
                      <ShieldAlert size={9} /> {ug}
                      {' ungrounded'}
                    </span>
                  )}
                  {pend.length > 0 && (
                    <div className="ml-auto flex gap-1.5 shrink-0">
                      <button
                        onClick={() =>
                          requestDecision(
                            pend.map((a) => a.id),
                            'Approved',
                            `${gp.key} group`,
                          )
                        }
                        className="text-[11px] font-semibold text-white rounded-md px-2.5 py-1 flex items-center gap-1"
                        style={{
                          backgroundColor: 'var(--clr-green)',
                        }}
                      >
                        <Check size={11} />
                        {' Approve '}
                        {pend.length}
                      </button>
                      <button
                        onClick={() =>
                          requestDecision(
                            pend.map((a) => a.id),
                            'Rejected',
                            `${gp.key} group`,
                          )
                        }
                        className="text-[11px] font-semibold rounded-md px-2.5 py-1 border"
                        style={{
                          borderColor: 'var(--border)',
                          color: 'var(--text-muted)',
                        }}
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
                <div>
                  {gp.items.map((a, i) => {
                    const open = expanded === a.id;
                    return (
                      <div
                        key={a.id}
                        style={{
                          borderTop: i
                            ? '1px solid var(--border-subtle)'
                            : 'none',
                        }}
                      >
                        <div className="flex items-center gap-2 px-3 py-2 min-w-0">
                          <button
                            onClick={() => setExpanded(open ? null : a.id)}
                            className="shrink-0"
                            aria-expanded={open}
                            aria-label={`Break detail for ${a.id}`}
                          >
                            {open ? (
                              <ChevronDown
                                size={12}
                                style={{
                                  color: 'var(--text-muted)',
                                }}
                              />
                            ) : (
                              <ChevronRight
                                size={12}
                                style={{
                                  color: 'var(--text-muted)',
                                }}
                              />
                            )}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <button
                                onClick={() => onOpenBook(a.book, rec.id)}
                                className="text-xs font-semibold truncate hover:underline text-left"
                                style={{
                                  color: 'var(--barcl-eagle)',
                                }}
                              >
                                {a.book}
                              </button>
                              <span
                                className="text-[10px] shrink-0"
                                style={{
                                  color: 'var(--text-muted)',
                                }}
                              >
                                {a.id}
                              </span>
                            </div>
                            <div
                              className="text-[11px] tabular-nums"
                              style={{
                                color: 'var(--text-secondary)',
                              }}
                            >
                              {a.amount}
                            </div>
                            <div
                              className="text-[11px] truncate"
                              style={{
                                color: 'var(--text-muted)',
                              }}
                            >
                              {a.reason}
                            </div>
                          </div>
                          {a.agedSessions > 0 && (
                            <span
                              title={`Carried across ${a.agedSessions} sessions`}
                              className="shrink-0"
                              style={{
                                color: 'var(--clr-amber)',
                              }}
                            >
                              <Aged size={12} />
                            </span>
                          )}
                          {!a.grounded && (
                            <span
                              title="Numeric grounding failed"
                              className="shrink-0"
                              style={{
                                color: 'var(--clr-red)',
                              }}
                            >
                              <ShieldAlert size={13} />
                            </span>
                          )}
                          <button
                            onClick={() =>
                              onAsk(`Explain ${a.id} on ${a.book}`)
                            }
                            className="p-1 rounded border border-slate-200 shrink-0 hover:opacity-70"
                            style={{
                              color: 'var(--barcl-eagle)',
                            }}
                            title="Ask the session about this adjustment"
                            aria-label={`Ask about ${a.id}`}
                          >
                            <MessageSquare size={12} />
                          </button>
                          {a.status === 'Pending' ? (
                            <RowDecision
                              onApprove={() =>
                                requestDecision([a.id], 'Approved', a.book)
                              }
                              onReject={() =>
                                requestDecision([a.id], 'Rejected', a.book)
                              }
                            />
                          ) : (
                            <DecisionPill status={a.status} />
                          )}
                        </div>
                        {open && <BreakDetailPanel adj={a} rec={rec} />}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
