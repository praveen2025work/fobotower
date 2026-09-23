'use client';

import { useEffect } from 'react';

import { useFoboSessionStore } from '@/store/foboSessionStore';
import { useFoboTraceStore } from '@/store/foboTraceStore';

import DecisionPaths from './DecisionPaths';
import WorkflowTrace from './WorkflowTrace';

function Tile({ label, value, sub, tone }) {
  return (
    <div className="glass-card p-3 flex flex-col gap-0.5">
      <div className="text-[11px] font-bold tracking-wide" style={{ color: 'var(--text-muted)' }}>
        {label}
      </div>
      <div
        className="text-2xl font-bold"
        style={{ color: tone ?? 'var(--text-primary)', fontFamily: 'var(--font-manrope), sans-serif' }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
          {sub}
        </div>
      )}
    </div>
  );
}

/**
 * How the selected rec's investigation actually executed: the LangGraph run,
 * and each break's path through the playbook.
 */
export default function ExecutionTab({ recId }) {
  const { trace, state, loading, error, loadTrace } = useFoboTraceStore();
  const sess = useFoboSessionStore();

  useEffect(() => {
    loadTrace(recId);
  }, [recId, loadTrace]);

  if (!recId) {
    return <p className="p-4 text-sm" style={{ color: 'var(--text-muted)' }}>Select a rec.</p>;
  }
  if (error) {
    return <p className="p-4 text-sm" style={{ color: 'var(--clr-red)' }}>{error}</p>;
  }
  if (loading || sess.loading) {
    return <p className="p-4 text-sm" style={{ color: 'var(--text-muted)' }}>Loading {recId}…</p>;
  }

  const header = sess.header;
  if (state === 'clear') {
    return (
      <section className="glass-card p-4">
        <h2 className="text-base font-bold">{header?.name}</h2>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          No open breaks on this rec, so no investigation ran.
        </p>
      </section>
    );
  }

  const d = sess.determinism ?? {};
  const findings = sess.findings ?? {};
  const version = Object.values(findings)[0]?.playbook_version;
  const reasoner = Object.values(findings).find((f) => !f.deterministic)?.reasoner ?? 'none';
  const llmCalls = Object.values(findings).filter(
    (f) => !f.deterministic && f.reasoner && f.reasoner !== 'none' && f.established,
  ).length;

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-base font-bold" style={{ fontFamily: 'var(--font-manrope), sans-serif' }}>
          {header?.name}
        </h2>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {header?.rec_id} · COB {header?.business_date}
          {version ? ` · playbook v${version}` : ''} · reasoner: {reasoner}
        </span>
      </header>

      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))' }}
      >
        <Tile
          label="SETTLED BY PLAYBOOK"
          value={`${d.deterministic ?? 0} / ${d.total ?? 0}`}
          sub={d.share != null ? `${Math.round(d.share * 100)}% — no LLM` : '—'}
          tone="var(--clr-green)"
        />
        <Tile
          label="NEEDED JUDGEMENT"
          value={d.escalated_to_reasoner ?? 0}
          sub={reasoner === 'none' ? 'escalated to a person' : `sent to ${reasoner}`}
          tone={d.escalated_to_reasoner ? 'var(--clr-amber)' : undefined}
        />
        <Tile label="LLM CALLS" value={llmCalls} sub={`reasoner: ${reasoner}`} />
        <Tile
          label="RUN TIME"
          value={trace ? `${trace.total_ms} ms` : '—'}
          sub={trace ? `${trace.steps.filter((s) => s.status === 'done').length} steps done` : ''}
        />
      </div>

      <div className="grid gap-3 items-start" style={{ gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 3fr)' }}>
        <WorkflowTrace trace={trace} />
        <DecisionPaths findings={findings} breakBooks={sess.breakBooks} deltas={sess.deltas} />
      </div>
    </div>
  );
}
