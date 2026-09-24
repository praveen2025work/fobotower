import { useEffect, useState } from 'react';
import {
  CircleCheck,
  CirclePause,
  Circle,
  TriangleAlert as Alert,
} from 'lucide-react';
import { fetchTrace } from '../data/helixApi';
import { mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';

/**
 * How the rec's LangGraph investigation executed, read from its checkpoints:
 * each step in order, what it produced, how long it took, and where the graph
 * is parked. Nothing here is computed in the browser.
 */

const STATE = {
  done: {
    icon: CircleCheck,
    fg: 'var(--clr-green)',
    bg: 'var(--clr-green-bg)',
    label: 'Done',
  },
  waiting: {
    icon: CirclePause,
    fg: 'var(--clr-amber)',
    bg: 'var(--clr-amber-bg)',
    label: 'Waiting',
  },
  pending: {
    icon: Circle,
    fg: 'var(--text-muted)',
    bg: 'var(--bg-muted)',
    label: 'Not reached',
  },
  skipped: {
    icon: Circle,
    fg: 'var(--text-muted)',
    bg: 'var(--bg-muted)',
    label: 'Skipped',
  },
  failed: {
    icon: Alert,
    fg: 'var(--clr-red)',
    bg: 'var(--clr-red-bg)',
    label: 'Failed',
  },
};

function Step({ step, last }) {
  const st = STATE[step.status] || STATE.pending;
  const Icon = st.icon;
  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center shrink-0">
        <span
          className="w-7 h-7 rounded-full flex items-center justify-center"
          style={{ background: st.bg, color: st.fg }}
        >
          <Icon size={14} />
        </span>
        {!last && (
          <span
            className="flex-1 w-px my-1"
            style={{ background: 'var(--border)' }}
          />
        )}
      </div>
      <div className="flex-1 min-w-0 pb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[13px] font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            {step.label}
          </span>
          <span
            className="text-[10px]"
            style={{ ...mono, color: 'var(--text-muted)' }}
          >
            {step.node}
          </span>
          <span
            className="pill ml-auto"
            style={{ background: st.bg, color: st.fg, fontSize: 10 }}
          >
            {st.label}
            {step.duration_ms != null && ` · ${step.duration_ms} ms`}
          </span>
        </div>
        <div
          className="text-[11.5px] mt-0.5"
          style={{ color: 'var(--text-secondary)' }}
        >
          {step.description}
        </div>
        {step.summary && (
          <div
            className="text-[12px] mt-1.5 font-medium"
            style={{ color: 'var(--text-primary)' }}
          >
            {step.summary}
          </div>
        )}
        {step.produced?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {step.produced.map((key) => (
              <span
                key={key}
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{
                  ...mono,
                  background: 'var(--bg-muted)',
                  color: 'var(--text-secondary)',
                }}
              >
                {key}
              </span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function WorkflowTraceDrawer({ rec, onClose }) {
  const [trace, setTrace] = useState({ state: 'loading' });
  useEffect(() => {
    let live = true;
    fetchTrace(rec.id)
      .then((body) => live && setTrace({ state: 'ready', body }))
      .catch((e) => live && setTrace({ state: 'error', error: e.message }));
    return () => {
      live = false;
    };
  }, [rec.id]);

  const t = trace.body?.trace;
  const subtitle = t
    ? `${t.thread_id} · workflow v${t.workflow_version} · ${t.checkpoints} checkpoints · ${t.total_ms} ms`
    : rec.name;
  return (
    <Drawer title="Graph run" subtitle={subtitle} width={640} onClose={onClose}>
      {trace.state === 'loading' && (
        <div
          className="py-10 text-center text-[12px]"
          style={{ color: 'var(--text-muted)' }}
        >
          Reading the checkpoints…
        </div>
      )}
      {trace.state === 'error' && (
        <div
          className="py-10 text-center text-[12px]"
          style={{ color: 'var(--clr-red)' }}
        >
          The trace could not be loaded: {trace.error}
        </div>
      )}
      {trace.state === 'ready' && !t && (
        <div
          className="py-10 text-center text-[12px]"
          style={{ color: 'var(--text-muted)' }}
        >
          No investigation has run for {rec.name}.
        </div>
      )}
      {t && (
        <>
          <div
            className="rounded-xl px-3.5 py-3 mb-4 text-[12px]"
            style={{
              background: 'var(--clr-blue-bg)',
              color: 'var(--clr-blue)',
            }}
          >
            {t.parked_at
              ? `Paused before "${t.parked_at}": the graph waits here for a controller decision, then resumes from this checkpoint.`
              : `Finished: ${t.status.replace(/_/g, ' ')}.`}
            {t.escalation_reason && ` Escalated: ${t.escalation_reason}.`}
          </div>
          <ol>
            {t.steps.map((s, i) => (
              <Step key={s.node} step={s} last={i === t.steps.length - 1} />
            ))}
          </ol>
        </>
      )}
    </Drawer>
  );
}
