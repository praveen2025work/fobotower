'use client';

import { decisionPath } from './decisionPath';

const KIND_STYLE = {
  rule: { background: 'var(--clr-green-bg)', color: 'var(--clr-green)' },
  judgement: { background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' },
  category: { background: 'var(--bg-hover)', color: 'var(--text-secondary)' },
  side: { background: 'var(--bg-hover)', color: 'var(--text-secondary)' },
  playbook: { background: 'var(--clr-blue-bg)', color: 'var(--clr-blue)' },
  reasoner: { background: 'var(--clr-purple-bg)', color: 'var(--clr-purple)' },
  guard: { background: 'var(--clr-red-bg)', color: 'var(--clr-red)' },
};

const VERDICT_STYLE = {
  POST: { background: 'var(--clr-green)', color: '#fff' },
  DO_NOT_POST: { background: 'var(--clr-grey)', color: '#fff' },
  ESCALATE: { background: 'var(--clr-amber)', color: '#fff' },
  CORRECT_AND_REPOST: { background: 'var(--clr-blue)', color: '#fff' },
};

const money = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

export default function DecisionPaths({ findings = {}, breakBooks = {}, deltas = {} }) {
  const entries = Object.entries(findings);
  if (entries.length === 0) {
    return (
      <section className="glass-card p-4">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          No decisions recorded for this rec yet.
        </p>
      </section>
    );
  }

  return (
    <section className="glass-card p-4 flex flex-col gap-3">
      <div className="flex items-baseline gap-2 flex-wrap">
        <h3
          className="text-sm font-bold"
          style={{ fontFamily: 'var(--font-manrope), sans-serif' }}
        >
          How each break was decided
        </h3>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          path through the playbook · hover a step for detail
        </span>
      </div>

      <ul className="flex flex-col">
        {entries.map(([bid, f]) => (
          <li
            key={bid}
            className="flex items-center gap-3 py-2 flex-wrap"
            style={{ borderTop: '1px solid var(--border-subtle)' }}
          >
            <div className="shrink-0" style={{ width: 128 }}>
              <div className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                {breakBooks[bid] ?? bid}
              </div>
              <div
                className="text-[11px]"
                style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono), monospace' }}
              >
                {money(deltas[bid])}
              </div>
            </div>

            <ol className="flex items-center gap-1 flex-wrap flex-1 min-w-0">
              {decisionPath(f).map((step, i, all) => (
                <li key={`${bid}-${i}`} className="flex items-center gap-1">
                  <span
                    title={step.title}
                    className="pill"
                    style={
                      step.kind === 'verdict'
                        ? { ...VERDICT_STYLE[step.verdict], fontWeight: 700 }
                        : KIND_STYLE[step.kind]
                    }
                  >
                    {step.text}
                  </span>
                  {i < all.length - 1 && (
                    <span aria-hidden="true" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                      →
                    </span>
                  )}
                </li>
              ))}
            </ol>

            {f.requires_controller_confirmation && (
              <span
                className="pill shrink-0"
                title={`Unset: ${(f.conditional_on ?? []).join(', ')}`}
                style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
              >
                needs confirmation
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
