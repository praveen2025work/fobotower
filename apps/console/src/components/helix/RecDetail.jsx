import { useState, useEffect } from 'react';
import { TriangleAlert as Alert, ArrowRight } from 'lucide-react';
import { AdjustmentsPanel } from './adjustments/AdjustmentsPanel';
import {
  PIPELINE,
  SECTION_LABEL,
  STEP_SECTION,
  currentStepIndex,
} from './constants';
import { manrope, mono } from './lib/format';
import { SessionPanel } from './session/SessionPanel';
import { BookLegend } from './ui/BookBar';
import { GroupPill, StatusPill } from './ui/Pills';
import { PipelineStep } from './ui/PipelineStep';

export function RecDetail({
  rec,
  statusOf,
  messages,
  pending,
  onSend,
  requestDecision,
  onOpenPattern,
  onOpenBook,
  onInspect,
  onOpenTrace,
  onOpenAll,
  callerName,
}) {
  const [draft, setDraft] = useState('');
  const [pane, setPane] = useState('session');
  const [focus, setFocus] = useState({
    section: 'session',
    tick: 0,
  });
  const curIdx = currentStepIndex(rec);
  const curStep = PIPELINE[curIdx];
  const sectionOf = (key) => (rec.analysis ? STEP_SECTION[key] : 'session');
  const go = (section) => {
    setPane(section);
    setFocus({
      section,
      tick: Date.now(),
    });
  };
  useEffect(() => {
    setDraft('');
    go(sectionOf(curStep.key));
  }, [rec.id]);
  const ask = (text) => {
    setDraft(text);
    setPane('session');
  };
  const pendingHere = rec.adjustments.filter(
    (a) => statusOf(a) === 'Pending',
  ).length;
  return (
    <div className="flex-1 min-w-0 flex flex-col gap-3 min-h-0">
      <div className="glass px-4 pt-3 pb-2.5 shrink-0">
        <div className="flex items-center gap-2 min-w-0 mb-3 flex-wrap">
          <GroupPill groupKey={rec.group} short={false} />
          <span
            className="text-[14px] font-bold truncate min-w-0"
            style={{
              ...manrope,
              color: 'var(--text-primary)',
            }}
          >
            {rec.l4}
          </span>
          <span
            className="text-[10px] tabular-nums shrink-0 hidden sm:block"
            style={{
              color: 'var(--text-muted)',
              ...mono,
            }}
          >
            {rec.id}
            {' · '}
            {rec.readyAt
              ? `Ready event ${rec.eventId} at ${rec.readyAt}`
              : `awaiting Ready event, MB Rec ready ${rec.mb.available}/${rec.mb.total}`}
          </span>
          <span className="ml-auto">
            <StatusPill status={rec.status} />
          </span>
        </div>
        <div className="flex items-center overflow-x-auto pb-0.5">
          {PIPELINE.map((s, i) => (
            <PipelineStep
              key={s.key}
              step={s}
              status={rec.steps[i]}
              isLast={i === PIPELINE.length - 1}
              isCurrent={i === curIdx}
              target={SECTION_LABEL[sectionOf(s.key)]}
              onGo={() => go(sectionOf(s.key))}
            />
          ))}
        </div>
        <div
          className="text-[10.5px] mt-1.5 flex items-center gap-1 flex-wrap"
          style={{
            color: 'var(--text-muted)',
          }}
        >
          <span>Current step:</span>
          <span
            className="font-semibold"
            style={{
              color:
                rec.steps[curIdx] === 'blocked'
                  ? 'var(--clr-red)'
                  : 'var(--text-secondary)',
            }}
          >
            {curStep.label}
            {rec.steps[curIdx] === 'blocked' ? ' (blocked)' : ''}
          </span>
          <ArrowRight size={10} />
          <button
            onClick={() => go(sectionOf(curStep.key))}
            className="font-semibold hover:underline"
            style={{
              color: 'var(--barcl-eagle)',
            }}
          >
            {SECTION_LABEL[sectionOf(curStep.key)]}
          </button>
          <span>· click any step to jump to it</span>
        </div>
        <BookLegend rec={rec} />
      </div>
      {rec.status === 'Blocked' && rec.breakNote && (
        <div
          className="flex items-start gap-2 border rounded-xl px-4 py-3 shrink-0"
          style={{
            backgroundColor: 'var(--clr-red-bg)',
            borderColor: 'var(--clr-red)',
          }}
        >
          <Alert
            size={15}
            className="mt-0.5 shrink-0"
            style={{
              color: 'var(--clr-red)',
            }}
          />
          <div
            className="text-xs leading-relaxed"
            style={{
              color: 'var(--clr-red)',
            }}
          >
            {rec.breakNote}
          </div>
        </div>
      )}
      {rec.analysis && (
        <div
          className="2xl:hidden flex gap-1 p-1 rounded-full self-start shrink-0"
          style={{
            background: 'var(--bg-card-solid)',
            border: '1px solid var(--border)',
          }}
          role="tablist"
        >
          {[
            ['session', 'Helix session'],
            [
              'adjustments',
              `Drafted adjustments${pendingHere ? ` (${pendingHere} pending)` : ''}`,
            ],
          ].map(([k, l]) => (
            <button
              key={k}
              role="tab"
              aria-selected={pane === k}
              onClick={() => setPane(k)}
              className="text-[11.5px] font-semibold px-3 py-1 rounded-full"
              style={
                pane === k
                  ? {
                      background: 'var(--bg-header)',
                      color: '#fff',
                    }
                  : {
                      color: 'var(--text-muted)',
                    }
              }
            >
              {l}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 min-h-0 flex gap-3 hx-mid">
        <div
          key={focus.section === 'session' ? `s-${focus.tick}` : 's'}
          className={`${pane === 'session' || !rec.analysis ? 'flex' : 'hidden'} 2xl:flex flex-[1.15] min-w-0 min-h-0 rounded-2xl ${focus.section === 'session' && focus.tick ? 'hx-flash' : ''}`}
        >
          <SessionPanel
            rec={rec}
            messages={messages}
            pending={pending}
            onSend={onSend}
            draft={draft}
            setDraft={setDraft}
            onInspect={onInspect}
            onOpenTrace={onOpenTrace}
            callerName={callerName}
            statusOf={statusOf}
          />
        </div>
        {rec.analysis && (
          <div
            className={`${pane === 'adjustments' ? 'flex' : 'hidden'} 2xl:flex flex-1 min-w-0 min-h-0`}
          >
            <AdjustmentsPanel
              rec={rec}
              statusOf={statusOf}
              requestDecision={requestDecision}
              onOpenPattern={onOpenPattern}
              onOpenBook={onOpenBook}
              onAsk={ask}
              focusTick={focus.section === 'adjustments' ? focus.tick : 0}
              onOpenAll={onOpenAll}
            />
          </div>
        )}
      </div>
    </div>
  );
}
