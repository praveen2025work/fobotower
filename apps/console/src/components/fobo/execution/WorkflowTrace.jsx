'use client';

import { CheckIcon, ClockIcon } from '@/components/fobo/icons';

const STATUS = {
  done: { ring: 'var(--clr-green)', bg: 'var(--clr-green-bg)', text: 'var(--clr-green)', label: 'Done' },
  waiting: { ring: 'var(--clr-amber)', bg: 'var(--clr-amber-bg)', text: 'var(--clr-amber)', label: 'Waiting' },
  pending: { ring: 'var(--border)', bg: 'var(--bg-muted)', text: 'var(--text-muted)', label: 'Not run' },
  skipped: { ring: 'var(--border)', bg: 'var(--bg-muted)', text: 'var(--text-muted)', label: 'Skipped' },
};

/**
 * The LangGraph run, step by step, read from its checkpoints. Each step is
 * something that actually executed — its timing and output are recorded, not
 * reconstructed for display.
 */
export default function WorkflowTrace({ trace }) {
  if (!trace) return null;

  return (
    <section className="glass-card p-4 flex flex-col gap-3">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h3
          className="text-sm font-bold"
          style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
        >
          Workflow run
        </h3>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          LangGraph · {trace.checkpoints} checkpoints · {trace.total_ms} ms
        </span>
      </div>
      <p className="text-[11px] -mt-2" style={{ color: 'var(--text-muted)' }}>
        Steps, order and pause points from{' '}
        <code style={{ fontFamily: 'var(--font-mono), monospace' }}>
          config/workflow/fobo-investigation.yaml
        </code>
        {trace.workflow_version ? ` (v${trace.workflow_version})` : ''}
      </p>

      <ol className="relative flex flex-col">
        {trace.steps.map((step, i) => {
          const s = STATUS[step.status] ?? STATUS.pending;
          const last = i === trace.steps.length - 1;
          const isPlaybook = step.node === 'reason';
          return (
            <li key={step.node} className="relative flex gap-3 pb-3">
              {!last && (
                <span
                  aria-hidden="true"
                  className="absolute"
                  style={{
                    left: 13,
                    top: 28,
                    bottom: 0,
                    width: 2,
                    background:
                      step.status === 'done' ? 'var(--clr-green)' : 'var(--border-subtle)',
                  }}
                />
              )}
              <span
                aria-label={`${step.label}: ${s.label}`}
                className="relative flex items-center justify-center rounded-full shrink-0"
                style={{
                  width: 28,
                  height: 28,
                  background: s.bg,
                  color: s.text,
                  border: `2px ${step.status === 'pending' ? 'dashed' : 'solid'} ${s.ring}`,
                }}
              >
                {step.status === 'done' ? (
                  <CheckIcon size={13} />
                ) : step.status === 'waiting' ? (
                  <ClockIcon size={13} />
                ) : (
                  <span className="text-[11px] font-semibold">{i + 1}</span>
                )}
              </span>

              <div
                className="flex-1 min-w-0 rounded-lg px-3 py-2"
                style={{
                  background: isPlaybook ? 'var(--bg-active)' : 'transparent',
                  border: isPlaybook ? '1px solid var(--clr-blue)' : '1px solid transparent',
                }}
              >
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span
                    className="text-sm font-semibold"
                    style={{
                      color:
                        step.status === 'pending' ? 'var(--text-muted)' : 'var(--text-primary)',
                    }}
                  >
                    {step.label}
                  </span>
                  <code
                    className="text-[11px]"
                    style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono), monospace' }}
                  >
                    {step.node}
                  </code>
                  {step.duration_ms !== undefined && step.duration_ms !== null && (
                    <span
                      className="ml-auto text-[11px]"
                      style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono), monospace' }}
                    >
                      {step.duration_ms} ms
                    </span>
                  )}
                  {step.status !== 'done' && (
                    <span className="ml-auto text-[11px] font-medium" style={{ color: s.text }}>
                      {s.label}
                    </span>
                  )}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {step.description}
                </div>
                {step.summary && (
                  <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                    → {step.summary}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
