'use client';

import { useState, useMemo, useEffect } from 'react';
import { CalendarDays as Calendar, Gauge, Workflow as WorkflowIcon } from 'lucide-react';
import { Analytics } from './Analytics';
import { EventBoard } from './EventBoard';
import { NotificationBell } from './NotificationBell';
import { RecDetail } from './RecDetail';
import { RecNav } from './RecNav';
import { ConfirmDialog } from './adjustments/ConfirmDialog';
import { AllAdjustmentsDrawer } from './drawers/AllAdjustmentsDrawer';
import { BookDrawer } from './drawers/BookDrawer';
import { McpInspector } from './drawers/McpInspector';
import { PatternDrawer } from './drawers/PatternDrawer';
import { adaptMessage, adaptRec } from './data/adapt';
import { decide, fetchBoard } from './data/helixApi';
import { RecsContext } from './data/RecsContext';
import { BoardStatus } from './BoardStatus';
import { WorkflowTraceDrawer } from './drawers/WorkflowTraceDrawer';
import { bookCounts, manrope, nowStamp } from './lib/format';
import { AgentOneClient, initialSession } from './lib/session';
import { DevCallerSwitch } from './workflow/DevCallerSwitch';
import { WorkflowView } from './workflow/WorkflowView';

// '2026-08-03' -> '03 Aug 2026', the business date the board is for.
const cobLabel = (cob) =>
  cob
    ? new Date(`${cob}T00:00:00Z`).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      })
    : '';

// The rec a controller most likely opened the console for.
const firstToOpen = (recs) =>
  (recs.find((r) => r.status === 'Awaiting Sign-off') || recs[0])?.id;

export default function HelixApp() {
  const [view, setView] = useState('pipeline');
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [navPinned, setNavPinned] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [dark, setDark] = useState(false);
  const [drawer, setDrawer] = useState(null);
  const [confirmReq, setConfirmReq] = useState(null);
  const [recs, setRecs] = useState([]);
  const [activity, setActivity] = useState([]);
  const [hoursSaved, setHoursSaved] = useState(null);
  const [cob, setCob] = useState(null);
  const [caller, setCaller] = useState(null);
  const [devCallers, setDevCallers] = useState([]);
  const [sessions, setSessions] = useState({});
  const [pendingReply, setPendingReply] = useState({});
  const [load, setLoad] = useState({ state: 'loading', error: null });

  const loadBoard = async () => {
    setLoad({ state: 'loading', error: null });
    try {
      const board = await fetchBoard();
      const served = board.recs.map(adaptRec);
      setRecs(served);
      setActivity(board.activity);
      setHoursSaved(board.hoursSaved);
      setCob(board.cob);
      setCaller(board.caller);
      setDevCallers(board.devCallers || []);
      setSessions(
        Object.fromEntries(served.map((r) => [r.id, initialSession(r)])),
      );
      setSelectedId((id) => id || firstToOpen(served));
      setLoad({ state: 'ready', error: null });
    } catch (e) {
      setLoad({ state: 'error', error: e.message });
    }
  };
  useEffect(() => {
    loadBoard();
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      dark ? 'dark' : 'light',
    );
  }, [dark]);
  // Status is the server's: a decision returns the rec as it now stands.
  const statusOf = useMemo(() => (a) => a.status, []);
  const rec = recs.find((r) => r.id === selectedId) || recs[0];
  const stats = useMemo(
    () => ({
      total: recs.length,
      cleared: recs.filter((r) => r.status === 'Cleared').length,
      awaiting: recs.filter((r) => r.status === 'Awaiting Sign-off').length,
      blocked: recs.filter((r) => r.status === 'Blocked').length,
      books: recs.reduce((s, r) => s + r.bookStats.total, 0),
      booksAuto: recs.reduce((s, r) => s + r.bookStats.autoPost, 0),
      booksOpen: recs.reduce((s, r) => s + bookCounts(r.bookStats).open, 0),
      booksNotOpen: recs.reduce((s, r) => s + r.bookStats.notOpen, 0),
      waiting: recs.filter((r) => !r.readyAt).length,
      booksUnlocked: recs.reduce((s, r) => s + r.booksUnlocked, 0),
    }),
    [recs],
  );
  const pendingCount = useMemo(
    () =>
      recs.reduce(
        (s, r) =>
          s + r.adjustments.filter((a) => a.status === 'Pending').length,
        0,
      ),
    [recs],
  );
  const callCount = useMemo(
    () =>
      Object.values(sessions).reduce(
        (s, msgs) =>
          s + msgs.reduce((t, m) => t + (m.calls ? m.calls.length : 0), 0),
        0,
      ),
    [sessions],
  );
  const requestDecision = (ids, decision, source) => {
    const pending = new Set(
      recs
        .flatMap((r) => r.adjustments)
        .filter((a) => a.status === 'Pending')
        .map((a) => a.id),
    );
    const live = ids.filter((id) => pending.has(id));
    if (live.length)
      setConfirmReq({
        ids: live,
        decision,
        source,
      });
  };
  const appendToSession = (recId, message) =>
    setSessions((s) => ({ ...s, [recId]: [...(s[recId] || []), message] }));
  const applyDecision = async (reason) => {
    const { ids, decision } = confirmReq;
    setConfirmReq(null);
    // A selection can span recs (the all-adjustments drawer); each rec
    // records its own decision.
    const byRec = {};
    ids.forEach((id) => {
      const r = recs.find((x) => x.adjustments.some((a) => a.id === id));
      (byRec[r.id] = byRec[r.id] || []).push(id);
    });
    for (const [recId, recIds] of Object.entries(byRec)) {
      try {
        const res = await decide(recId, { ids: recIds, decision, reason });
        const updated = adaptRec(res.rec);
        setRecs((rs) => rs.map((x) => (x.id === recId ? updated : x)));
        setSessions((s) => ({ ...s, [recId]: updated.session }));
        setActivity(res.activity);
      } catch (e) {
        appendToSession(recId, {
          id: `${recId}-err-${Date.now()}`,
          role: 'system',
          tone: 'rejected',
          time: nowStamp(),
          text: `The decision on ${recIds.join(', ')} was not recorded: ${e.message}`,
        });
      }
    }
  };
  const sendMessage = async (text) => {
    const r = rec;
    const localId = `${r.id}-u-${Date.now()}`;
    appendToSession(r.id, {
      id: localId,
      role: 'user',
      time: nowStamp(),
      text,
    });
    setPendingReply((p) => ({
      ...p,
      [r.id]: true,
    }));
    try {
      const res = await AgentOneClient.send({ rec: r, message: text });
      setSessions((s) => ({
        ...s,
        [r.id]: [
          ...s[r.id].map((m) => (m.id === localId ? res.user : m)),
          adaptMessage(res.agent),
        ],
      }));
    } catch (e) {
      appendToSession(r.id, {
        id: `${r.id}-a-${Date.now()}`,
        role: 'agent',
        time: nowStamp(),
        blocks: [
          {
            type: 'risk',
            text: `The session could not be reached: ${e.message}`,
          },
        ],
      });
    } finally {
      setPendingReply((p) => ({
        ...p,
        [r.id]: false,
      }));
    }
  };
  const openInspector = (callId) =>
    setDrawer({
      type: 'mcp',
      recId: rec.id,
      callId,
    });
  const openTrace = () =>
    setDrawer({
      type: 'trace',
      recId: rec.id,
    });
  if (load.state !== 'ready' || !rec)
    return <BoardStatus load={load} onRetry={loadBoard} />;
  const tabStyle = (on) =>
    on
      ? {
          background: 'rgba(255,255,255,0.18)',
          color: '#FFFFFF',
          boxShadow: '0 1px 4px rgba(0,0,0,0.20)',
          border: '1px solid rgba(255,255,255,0.25)',
        }
      : {
          color: 'var(--text-on-brand2)',
        };
  return (
    <RecsContext.Provider value={recs}>
      <div
        className="min-h-screen lg:h-screen flex flex-col lg:overflow-hidden"
        style={{
          fontFamily: 'var(--hx-font-inter), sans-serif',
        }}
        data-theme={dark ? 'dark' : 'light'}
      >
        <div
          style={{
            background: 'var(--header-grad)',
          }}
          className="px-6 md:px-10 py-3 shrink-0 relative z-40"
        >
          <div className="flex items-center gap-4 flex-wrap">
            <div className="min-w-0">
              <div
                className="text-white text-lg font-extrabold tracking-tight truncate"
                style={manrope}
              >
                FOBO Control Tower
              </div>
              <div
                className="text-xs mt-0.5 truncate"
                style={{
                  color: 'var(--text-on-brand2)',
                }}
              >
                Helix · Agent One sessions across CATS vs MOTIF and Rec Factory
                recs
              </div>
            </div>
            <div
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full shrink-0"
              style={{
                background: 'rgba(255,255,255,0.10)',
                border: '1px solid rgba(255,255,255,0.15)',
              }}
            >
              <Calendar
                size={13}
                style={{
                  color: 'var(--text-on-brand2)',
                }}
              />
              <span className="text-[11px] font-semibold text-white tabular-nums">
                {cobLabel(cob)}
              </span>
              <span
                className="text-[10px] ml-1"
                style={{
                  color: 'var(--text-on-brand2)',
                }}
              >
                IST
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setView('pipeline')}
                className="text-xs font-semibold px-3.5 py-1.5 rounded-full transition-colors"
                style={tabStyle(view === 'pipeline')}
              >
                Pipeline
              </button>
              <button
                onClick={() => setView('analytics')}
                className="text-xs font-semibold px-3.5 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
                style={tabStyle(view === 'analytics')}
              >
                <Gauge size={12} />
                {' Agent Analytics'}
              </button>
              <button
                onClick={() => setView('workflow')}
                className="text-xs font-semibold px-3.5 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
                style={tabStyle(view === 'workflow')}
              >
                <WorkflowIcon size={12} />
                {' Workflow'}
              </button>
            </div>
            <div className="ml-auto flex items-center gap-2.5 shrink-0">
              <button
                onClick={() => setDark((d) => !d)}
                title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
                className="w-8 h-8 rounded-full flex items-center justify-center text-[14px] hover:opacity-80"
                style={{
                  backgroundColor: 'var(--bg-header-deep)',
                  color: 'var(--text-on-brand2)',
                }}
              >
                {dark ? '☀' : '◑'}
              </button>
              <DevCallerSwitch callers={devCallers} current={caller?.id} onSwitch={() => loadBoard()} />
              <NotificationBell
                activity={activity}
                onSelectRec={(id) => {
                  setSelectedId(id);
                  setView('pipeline');
                }}
              />
              <div className="text-right hidden sm:block">
                <div className="text-[12px] font-semibold text-white leading-tight">
                  {caller?.name}
                </div>
                <div
                  className="text-[10px] leading-tight"
                  style={{
                    color: 'var(--text-on-brand2)',
                  }}
                >
                  {caller?.title}
                </div>
              </div>
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold text-white shrink-0"
                style={{
                  background:
                    'linear-gradient(135deg, var(--barcl-eagle) 0%, #0088C4 100%)',
                  ...manrope,
                }}
              >
                {caller?.name?.[0]}
              </div>
            </div>
          </div>
        </div>
        {view === 'workflow' ? (
          <div className="flex-1 min-h-0 overflow-y-auto px-6 md:px-10 py-6">
            <div className="max-w-7xl mx-auto w-full">
              <WorkflowView callerKey={caller?.id} />
            </div>
          </div>
        ) : view === 'analytics' ? (
          <div className="flex-1 min-h-0 overflow-y-auto px-6 md:px-10 py-6">
            <div className="max-w-6xl mx-auto w-full">
              <Analytics
                statusOf={statusOf}
                callCount={callCount}
                hoursSaved={hoursSaved}
              />
            </div>
          </div>
        ) : (
          <>
            <EventBoard
              selectedId={selectedId}
              onSelect={setSelectedId}
              stats={{
                ...stats,
                pending: pendingCount,
              }}
            />
            <div className="flex-1 min-h-0 flex px-6 md:px-10 pt-3 pb-3 gap-3">
              <RecNav
                collapsed={navCollapsed}
                onToggleCollapse={() => setNavCollapsed((c) => !c)}
                pinned={navPinned}
                onTogglePin={() => setNavPinned((p) => !p)}
                selectedId={selectedId}
                onSelect={setSelectedId}
                pendingCount={pendingCount}
                statusOf={statusOf}
              />
              <RecDetail
                rec={rec}
                statusOf={statusOf}
                messages={sessions[rec.id]}
                pending={!!pendingReply[rec.id]}
                onSend={sendMessage}
                requestDecision={requestDecision}
                onOpenPattern={(p, l, rid) =>
                  setDrawer({
                    type: 'pattern',
                    pattern: p,
                    label: l,
                    recId: rid,
                  })
                }
                onOpenBook={(b, rid) =>
                  setDrawer({
                    type: 'book',
                    bookCode: b,
                    recId: rid,
                  })
                }
                onInspect={openInspector}
                onOpenTrace={openTrace}
                callerName={caller?.name}
                onOpenAll={() =>
                  setDrawer({
                    type: 'all',
                  })
                }
              />
            </div>
          </>
        )}
        <div
          className="text-center text-[11px] py-2 shrink-0"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          Draft UI, illustrative data. Every posting is double confirmed by a
          human before FAS posts to MOTIF.
        </div>
        {drawer?.type === 'all' && (
          <AllAdjustmentsDrawer
            statusOf={statusOf}
            requestDecision={requestDecision}
            onClose={() => setDrawer(null)}
          />
        )}
        {drawer?.type === 'pattern' && (
          <PatternDrawer
            {...drawer}
            statusOf={statusOf}
            requestDecision={requestDecision}
            onClose={() => setDrawer(null)}
          />
        )}
        {drawer?.type === 'book' && (
          <BookDrawer
            {...drawer}
            statusOf={statusOf}
            requestDecision={requestDecision}
            onClose={() => setDrawer(null)}
          />
        )}
        {drawer?.type === 'mcp' &&
          (() => {
            const r = recs.find((x) => x.id === drawer.recId);
            return (
              <McpInspector
                rec={r}
                calls={sessions[r.id].flatMap((m) => m.calls || [])}
                focusId={drawer.callId}
                onClose={() => setDrawer(null)}
              />
            );
          })()}
        {drawer?.type === 'trace' && (
          <WorkflowTraceDrawer
            rec={recs.find((x) => x.id === drawer.recId)}
            onClose={() => setDrawer(null)}
          />
        )}
        {confirmReq && (
          <ConfirmDialog
            request={confirmReq}
            onCancel={() => setConfirmReq(null)}
            onConfirm={applyDecision}
          />
        )}
      </div>
    </RecsContext.Provider>
  );
}
