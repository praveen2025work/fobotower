import { useMemo, useEffect, useRef } from 'react';
import { Workflow, Zap } from 'lucide-react';
import { MessageSquare, Send, ShieldCheck, TableIcon } from '../ui/icons';
import { CONFIDENCE, SUGGESTIONS } from '../constants';
import { manrope, mono, sessionIdOf } from '../lib/format';
import { ToolCall } from '../mcp/ToolCall';
import { AnalysisTurn } from './AnalysisTurn';
import { ReplyBlocks } from './ReplyBlocks';
import { AgentAvatar } from '../ui/Kpi';

export function SessionPanel({
  rec,
  messages,
  pending,
  onSend,
  draft,
  setDraft,
  onInspect,
  onOpenTrace,
  callerName,
  statusOf,
}) {
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const analysisReady = rec.analysis && rec.analysis.confidence !== 'RUNNING';
  const conf = rec.analysis ? CONFIDENCE[rec.analysis.confidence] : null;
  const allCalls = messages.flatMap((m) => m.calls || []);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, pending, rec.id]);
  useEffect(() => {
    if (draft && inputRef.current) inputRef.current.focus();
  }, [draft]);
  const suggestions = useMemo(() => {
    if (!analysisReady) return [];
    if (rec.status === 'Blocked') return SUGGESTIONS.Blocked;
    const pend = rec.adjustments.filter((a) => statusOf(a) === 'Pending');
    if (!pend.length) {
      const manual = rec.adjustments.find((a) => a.type === 'Manual');
      return [
        'Summarise the session',
        manual ? `Explain ${manual.id}` : null,
        'Were all figures grounded?',
        'Show the MCP data',
      ].filter(Boolean);
    }
    const focus =
      pend.find((a) => !a.grounded) ||
      pend.find((a) => a.agedSessions > 0) ||
      pend[0];
    return [
      'What is safe to approve?',
      "Summarise what's pending",
      `Explain ${focus.id}`,
      'Draft a chase note for the desk',
      'Show the MCP data',
    ];
  }, [rec, analysisReady, statusOf]);
  const submit = (text) => {
    const t = (text != null ? text : draft).trim();
    if (!t || pending || !analysisReady) return;
    onSend(t);
    setDraft('');
  };
  return (
    <div className="glass flex flex-col min-h-0 min-w-0 flex-1 hx-session">
      <div
        className="px-4 pt-3 pb-2.5 shrink-0 flex items-center gap-2 flex-wrap"
        style={{
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <MessageSquare
          size={15}
          style={{
            color: 'var(--barcl-eagle)',
          }}
        />
        <span
          className="text-[15px] font-bold"
          style={{
            ...manrope,
            color: 'var(--text-primary)',
          }}
        >
          Helix session
        </span>
        <span
          className="text-[10px] truncate"
          style={{
            ...mono,
            color: 'var(--text-muted)',
          }}
        >
          {sessionIdOf(rec)}
        </span>
        {rec.graphRun && (
          <button
            onClick={onOpenTrace}
            title="How the LangGraph investigation ran, step by step"
            className="ml-auto pill flex items-center gap-1 hover:opacity-80"
            style={{
              background: 'var(--bg-muted)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <Workflow size={10} />
            {' Graph run'}
          </button>
        )}
        <button
          onClick={() => onInspect(null)}
          disabled={!allCalls.length}
          className={`${rec.graphRun ? '' : 'ml-auto '}pill flex items-center gap-1 hover:opacity-80`}
          style={{
            background: 'var(--bg-muted)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
            opacity: allCalls.length ? 1 : 0.5,
          }}
        >
          <TableIcon size={10} />
          {' MCP data ('}
          {allCalls.length})
        </button>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto px-4 py-3 hx-space-y-3.5"
        aria-live="polite"
      >
        {rec.analysis && (
          <div
            className="text-[10.5px] text-center"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            {'Session started '}
            {rec.readyAt}
            {' IST on Ready event '}
            {rec.eventId}
            {' · Agent One'}
          </div>
        )}
        {messages.map((m) => {
          if (m.role === 'system')
            return (
              <div
                key={m.id}
                className="flex items-center gap-2 text-[11px]"
                style={{
                  color:
                    m.tone === 'rejected'
                      ? 'var(--clr-red)'
                      : 'var(--clr-green)',
                }}
              >
                <span
                  className="flex-1 h-px"
                  style={{
                    background: 'var(--border-subtle)',
                  }}
                />
                <ShieldCheck size={11} className="shrink-0" />
                <span className="text-center">
                  {m.time}
                  {' · '}
                  {m.text}
                </span>
                <span
                  className="flex-1 h-px"
                  style={{
                    background: 'var(--border-subtle)',
                  }}
                />
              </div>
            );
          if (m.role === 'user')
            return (
              <div key={m.id} className="flex justify-end">
                <div className="max-w-[85%]">
                  <div
                    className="text-[10px] text-right mb-0.5"
                    style={{
                      color: 'var(--text-muted)',
                    }}
                  >
                    {`${callerName} · `}
                    {m.time}
                  </div>
                  <div
                    className="text-[12.5px] leading-relaxed px-3 py-2 rounded-2xl rounded-tr-md whitespace-pre-wrap"
                    style={{
                      background: 'var(--bg-header)',
                      color: '#fff',
                    }}
                  >
                    {m.text}
                  </div>
                </div>
              </div>
            );
          return (
            <div key={m.id} className="flex gap-2.5 min-w-0">
              <AgentAvatar />
              <div className="flex-1 min-w-0">
                <div
                  className="text-[10px] mb-1"
                  style={{
                    color: 'var(--text-muted)',
                  }}
                >
                  {'Agent One · '}
                  {m.time}
                </div>
                <div
                  className="rounded-2xl rounded-tl-md px-3.5 py-3"
                  style={{
                    background: 'var(--bg-card-solid)',
                    border: '1px solid var(--border)',
                  }}
                >
                  {m.kind === 'analysis' ? (
                    <AnalysisTurn
                      rec={rec}
                      calls={m.calls}
                      onInspect={onInspect}
                    />
                  ) : (
                    <>
                      <ReplyBlocks blocks={m.blocks} />
                      {m.calls && m.calls.length > 0 && (
                        <div className="mt-2.5 hx-space-y-1.5">
                          <div
                            className="text-[10px] font-semibold"
                            style={{
                              color: 'var(--text-muted)',
                            }}
                          >
                            Data from MCP calls
                          </div>
                          {m.calls.map((c) => (
                            <ToolCall
                              key={c.id}
                              call={c}
                              onInspect={onInspect}
                            />
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {pending && (
          <div className="flex gap-2.5 items-center">
            <AgentAvatar />
            <div
              className="rounded-2xl px-3 py-2 flex items-center gap-2 text-[11px]"
              style={{
                background: 'var(--bg-card-solid)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
              }}
            >
              <span className="hx-dots">
                <i />
                <i />
                <i />
              </span>
              {' Querying MB Rec via MCP'}
            </div>
          </div>
        )}
        {!rec.analysis && (
          <div className="text-center py-10">
            <Zap
              size={22}
              className="mx-auto mb-2"
              style={{
                color: 'var(--text-muted)',
              }}
            />
            <div
              className="text-sm font-semibold"
              style={{
                color: 'var(--text-secondary)',
              }}
            >
              Waiting for the Ready event
            </div>
            <div className="max-w-[260px] mx-auto mt-3">
              <div
                className="flex justify-between text-[10.5px] mb-1"
                style={{
                  color: 'var(--text-muted)',
                }}
              >
                <span>MB Rec readiness (One Fin UX)</span>
                <span className="tabular-nums">
                  {rec.mb.available}/{rec.mb.total}
                </span>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{
                  background: 'var(--border-subtle)',
                }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${(rec.mb.available / rec.mb.total) * 100}%`,
                    background: 'var(--barcl-eagle)',
                  }}
                />
              </div>
            </div>
            <div
              className="text-xs mt-3 max-w-[340px] mx-auto leading-relaxed"
              style={{
                color: 'var(--text-muted)',
              }}
            >
              One Fin UX sends an MB Rec readiness event as each master book is
              ready. When all books are ready, One Fin UX sends the Ready event
              and Helix starts this session automatically.
            </div>
          </div>
        )}
      </div>
      <div
        className="px-3 pt-2 pb-3 shrink-0"
        style={{
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        {suggestions.length > 0 && (
          <div className="flex gap-1.5 overflow-x-auto pb-2 hx-noscroll">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => submit(s)}
                disabled={pending}
                className="text-[11px] whitespace-nowrap px-2.5 py-1 rounded-full border hover:opacity-80"
                style={{
                  borderColor: 'var(--border)',
                  color: 'var(--text-secondary)',
                  background: 'var(--bg-card-solid)',
                  opacity: pending ? 0.5 : 1,
                }}
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            disabled={!analysisReady}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={
              analysisReady
                ? `Ask about ${rec.l4}: an adjustment id, a pattern, grounding, what to approve…`
                : rec.analysis
                  ? 'Available when the session analysis finishes'
                  : 'Session not open yet'
            }
            className="hx-input flex-1 text-[12.5px] px-3 py-2 resize-none focus:outline-none"
            aria-label="Message the Helix session"
          />
          <button
            onClick={() => submit()}
            disabled={!draft.trim() || pending || !analysisReady}
            className="h-9 w-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity"
            style={{
              background: 'var(--barcl-eagle)',
              color: '#fff',
              opacity: !draft.trim() || pending || !analysisReady ? 0.4 : 1,
            }}
            aria-label="Send"
          >
            <Send size={15} />
          </button>
        </div>
        <div
          className="text-[10px] mt-1.5"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          Enter to send, Shift+Enter for a new line. Answers are grounded in
          this session's MCP data; decisions are made in the sign-off controls.
        </div>
      </div>
    </div>
  );
}
